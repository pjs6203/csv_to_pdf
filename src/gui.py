#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
from pathlib import Path
from typing import Any, Dict

try:
    from PySide6.QtCore import QObject, Qt, QTimer, Signal
    from PySide6.QtGui import QColor, QFont, QPainter, QPixmap
    from PySide6.QtWidgets import (
        QApplication,
        QComboBox,
        QDoubleSpinBox,
        QFileDialog,
        QFrame,
        QGridLayout,
        QHBoxLayout,
        QLabel,
        QLineEdit,
        QMainWindow,
        QMessageBox,
        QPushButton,
        QScrollArea,
        QSizePolicy,
        QSplitter,
        QTabWidget,
        QVBoxLayout,
        QWidget,
    )
except ModuleNotFoundError as exc:
    raise SystemExit("PySide6 is required. Install dependencies with: python -m pip install -r requirements.txt") from exc

try:
    from . import csv_to_pdf
except ImportError:
    import csv_to_pdf  # type: ignore


APP_DIR = Path(__file__).resolve().parent
DEFAULT_PROFILE_CANDIDATES = [
    APP_DIR.parent / "profiles" / "default_profiles.json",
    APP_DIR / "profiles" / "default_profiles.json",
]

BG = "#eef2f7"
SURFACE = "#ffffff"
SURFACE_ALT = "#f8fafc"
BORDER = "#d7e0eb"
TEXT = "#172033"
MUTED = "#64748b"
ACCENT = "#2563eb"

FIELD_LABELS = {
    "DOCUMENT_TITLE": "Header title",
    "LEFT_MARGIN": "Left margin",
    "RIGHT_MARGIN": "Right margin",
    "HEADER_TEXT_Y": "Header text Y",
    "HEADER_LINE_Y": "Header line Y",
    "FOOTER_LINE_Y": "Footer line Y",
    "FOOTER_TEXT_Y": "Footer text Y",
    "CENTER_X": "Center rule X",
    "CENTER_LINE_TOP": "Center rule top",
    "HEADER_LEFT_W": "Header title width",
    "FOOTER_PAGE_W": "Footer page width",
    "PASSAGE_RANGE_X": "Passage range X",
    "PASSAGE_RANGE_Y": "Passage range Y",
    "PASSAGE_BOX_X": "Passage box X",
    "PASSAGE_BOX_TOP": "Passage box top",
    "PASSAGE_BOX_W": "Passage box width",
    "PASSAGE_BOX_MAX_H": "Passage box max height",
    "PASSAGE_PAD_BOTTOM": "Passage bottom padding",
    "PASSAGE_PAD_X": "Passage side padding",
    "PASSAGE_PAD_TOP": "Passage top padding",
    "CONTENT_FLOW": "Content flow",
    "RIGHT_X": "Question column X",
    "RIGHT_TOP": "Question column top",
    "STEM_W": "Question stem width",
    "STEM_INDENT": "Stem/option guide indent",
    "PASSAGE_QUESTION_GAP": "Passage to question gap",
    "STEM_OPTION_GAP": "Stem to first option gap",
    "OPTION_LINE_GAP": "Option line gap",
    "QUESTION_BLOCK_GAP": "Question block gap",
    "STACKED_ITEM_GAP": "Stacked item gap",
    "HEADER_FONT_SIZE": "Header font size",
    "HEADER_LEADING": "Header leading",
    "FOOTER_FONT_SIZE": "Footer font size",
    "FOOTER_LEADING": "Footer leading",
    "QRANGE_FONT_SIZE": "Range label font size",
    "QRANGE_LEADING": "Range label leading",
    "PASSAGE_FONT_SIZE": "Passage font size",
    "PASSAGE_LEADING": "Passage leading",
    "PASSAGE_ALIGNMENT": "Passage alignment",
    "PASSAGE_WRAP_MODE": "Passage wrap mode",
    "STEM_FONT_SIZE": "Stem font size",
    "STEM_LEADING": "Stem leading",
    "OPTION_FONT_SIZE": "Option font size",
    "OPTION_LEADING": "Option leading",
}


class WorkerSignals(QObject):
    preview_ready = Signal(int, str)
    preview_failed = Signal(int, str)
    convert_done = Signal(str, int)
    convert_failed = Signal(str)


class PreviewCanvas(QFrame):
    def __init__(self) -> None:
        super().__init__()
        self.pixmap: QPixmap | None = None
        self.message = "No preview"
        self.setObjectName("PreviewCanvas")
        self.setMinimumSize(420, 620)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def set_pixmap(self, pixmap: QPixmap) -> None:
        self.pixmap = pixmap
        self.message = ""
        self.update()

    def set_message(self, message: str) -> None:
        self.pixmap = None
        self.message = message
        self.update()

    def paintEvent(self, _event: Any) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor(SURFACE_ALT))

        if self.pixmap and not self.pixmap.isNull():
            margin = 28
            available = self.rect().adjusted(margin, margin, -margin, -margin)
            scaled = self.pixmap.scaled(
                available.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            x = available.x() + (available.width() - scaled.width()) // 2
            y = available.y() + (available.height() - scaled.height()) // 2
            painter.fillRect(x + 8, y + 10, scaled.width(), scaled.height(), QColor(15, 23, 42, 35))
            painter.drawPixmap(x, y, scaled)
            return

        painter.setPen(QColor(MUTED))
        painter.setFont(QFont("Segoe UI", 11))
        painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self.message)


def hidden_subprocess_kwargs() -> Dict[str, Any]:
    if os.name == "nt" and hasattr(subprocess, "CREATE_NO_WINDOW"):
        return {"creationflags": subprocess.CREATE_NO_WINDOW}
    return {}


def find_pdftoppm() -> str | None:
    runtime = Path.home() / ".cache" / "codex-runtimes" / "codex-primary-runtime" / "dependencies"
    candidates = [
        runtime / "native" / "poppler" / "Library" / "bin" / "pdftoppm.exe",
        runtime / "native" / "poppler" / "bin" / "pdftoppm.cmd",
        runtime / "bin" / "pdftoppm.cmd",
    ]
    for path in candidates:
        if path.exists():
            return str(path)

    found = shutil.which("pdftoppm")
    if found:
        return found
    return None


class CsvToPdfApp(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("csv_to_pdf")
        self.resize(1280, 820)
        self.setMinimumSize(1080, 720)

        self.profiles: Dict[str, Dict[str, Any]] = {}
        self.layout_controls: Dict[str, QWidget] = {}
        self.signals = WorkerSignals()
        self.render_lock = threading.Lock()
        self.preview_token = 0
        self.preview_dir = tempfile.TemporaryDirectory(prefix="csv_to_pdf_preview_")
        self.suspend_preview = False

        self._load_default_profiles()
        self._build_ui()
        self._connect_signals()
        self._select_initial_profile()
        self.preview_canvas.set_message("Choose a CSV to preview.")
        self.statusBar().showMessage("Ready")

    def _load_default_profiles(self) -> None:
        self.profiles = {"Default": {"description": "Built-in default layout.", "layout": {}}}
        for path in DEFAULT_PROFILE_CANDIDATES:
            if path.exists():
                data = json.loads(path.read_text(encoding="utf-8"))
                self.profiles.update(data.get("profiles", {}))
                break

    def _build_ui(self) -> None:
        self._apply_style()
        root = QWidget()
        root.setObjectName("Root")
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(18, 16, 18, 14)
        root_layout.setSpacing(14)
        self.setCentralWidget(root)

        header = QFrame()
        header.setObjectName("Header")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        title_box = QVBoxLayout()
        title_box.setSpacing(2)
        title = QLabel("csv_to_pdf")
        title.setObjectName("AppTitle")
        title_box.addWidget(title)
        header_layout.addLayout(title_box, 1)
        self.open_output_button = QPushButton("Open Output")
        self.convert_button = QPushButton("Convert")
        self.convert_button.setObjectName("PrimaryButton")
        header_layout.addWidget(self.open_output_button)
        header_layout.addWidget(self.convert_button)
        root_layout.addWidget(header)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setObjectName("MainSplitter")
        root_layout.addWidget(splitter, 1)

        controls_panel = QFrame()
        controls_panel.setObjectName("SidePanel")
        controls_layout = QVBoxLayout(controls_panel)
        controls_layout.setContentsMargins(16, 16, 16, 16)
        controls_layout.setSpacing(14)

        self.profile_combo = QComboBox()
        self.profile_combo.addItems(list(self.profiles))
        profile_row = QHBoxLayout()
        profile_row.addWidget(self._field_label("Profile"))
        profile_row.addWidget(self.profile_combo, 1)
        self.reset_button = QPushButton("Reset")
        self.load_profile_button = QPushButton("Load")
        self.save_profile_button = QPushButton("Save")
        profile_row.addWidget(self.reset_button)
        profile_row.addWidget(self.load_profile_button)
        profile_row.addWidget(self.save_profile_button)
        controls_layout.addLayout(profile_row)

        tabs = QTabWidget()
        tabs.addTab(self._files_tab(), "Files")
        tabs.addTab(self._layout_tab(), "Layout")
        controls_layout.addWidget(tabs, 1)
        splitter.addWidget(controls_panel)

        preview_panel = QFrame()
        preview_panel.setObjectName("PreviewPanel")
        preview_layout = QVBoxLayout(preview_panel)
        preview_layout.setContentsMargins(16, 16, 16, 16)
        preview_layout.setSpacing(12)
        preview_head = QHBoxLayout()
        preview_title = QLabel("Preview")
        preview_title.setObjectName("SectionTitle")
        self.preview_status = QLabel("Idle")
        self.preview_status.setObjectName("MutedLabel")
        self.refresh_preview_button = QPushButton("Refresh")
        preview_head.addWidget(preview_title)
        preview_head.addWidget(self.preview_status, 1)
        preview_head.addWidget(self.refresh_preview_button)
        preview_layout.addLayout(preview_head)
        self.preview_canvas = PreviewCanvas()
        preview_layout.addWidget(self.preview_canvas, 1)
        splitter.addWidget(preview_panel)
        splitter.setSizes([470, 810])

    def _apply_style(self) -> None:
        QApplication.instance().setStyle("Fusion")
        self.setStyleSheet(
            f"""
            QMainWindow, QWidget#Root {{
                background: {BG};
                color: {TEXT};
                font-family: "Segoe UI";
                font-size: 10pt;
            }}
            QLabel#AppTitle {{
                color: {TEXT};
                font-size: 20px;
                font-weight: 700;
            }}
            QLabel {{
                color: {TEXT};
                background: transparent;
            }}
            QLabel#SectionTitle {{
                color: {TEXT};
                font-size: 14px;
                font-weight: 700;
            }}
            QLabel#MutedLabel {{
                color: {MUTED};
                font-size: 9.5pt;
            }}
            QFrame#SidePanel, QFrame#PreviewPanel {{
                background: {SURFACE};
                border: 1px solid {BORDER};
                border-radius: 14px;
            }}
            QFrame#PreviewCanvas {{
                background: {SURFACE_ALT};
                border: 1px solid {BORDER};
                border-radius: 12px;
            }}
            QFrame#FieldGroup {{
                background: {SURFACE_ALT};
                border: 1px solid {BORDER};
                border-radius: 10px;
            }}
            QLineEdit, QDoubleSpinBox, QComboBox {{
                background: #ffffff;
                border: 1px solid #cbd5e1;
                border-radius: 8px;
                color: {TEXT};
                min-height: 28px;
                padding: 5px 8px;
                selection-background-color: {ACCENT};
            }}
            QLineEdit:focus, QDoubleSpinBox:focus, QComboBox:focus {{
                border: 1px solid {ACCENT};
            }}
            QPushButton {{
                background: #e8eef7;
                border: 1px solid #cbd5e1;
                border-radius: 8px;
                color: {TEXT};
                min-height: 30px;
                padding: 5px 12px;
            }}
            QPushButton:hover {{
                background: #dde7f3;
            }}
            QPushButton#PrimaryButton {{
                background: {ACCENT};
                border: 1px solid {ACCENT};
                color: #ffffff;
                font-weight: 700;
            }}
            QPushButton#PrimaryButton:hover {{
                background: #1d4ed8;
            }}
            QTabWidget::pane {{
                border: 0;
            }}
            QTabBar::tab {{
                background: #e8eef7;
                border: 1px solid #d7e0eb;
                border-radius: 8px;
                padding: 8px 14px;
                margin-right: 6px;
                color: {MUTED};
            }}
            QTabBar::tab:selected {{
                background: #ffffff;
                color: {TEXT};
                border-color: #cbd5e1;
                font-weight: 700;
            }}
            QScrollArea {{
                border: 0;
                background: transparent;
            }}
            QScrollBar:vertical {{
                background: #edf2f7;
                border: 0;
                border-radius: 5px;
                width: 10px;
                margin: 0;
            }}
            QScrollBar::handle:vertical {{
                background: #cbd5e1;
                border-radius: 5px;
                min-height: 32px;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0;
            }}
            QScrollBar:horizontal {{
                height: 0;
            }}
            QStatusBar {{
                background: transparent;
                color: {MUTED};
            }}
            """
        )

    def _field_label(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setMinimumWidth(92)
        return label

    def _files_tab(self) -> QWidget:
        page = QWidget()
        layout = QGridLayout(page)
        layout.setContentsMargins(2, 14, 2, 2)
        layout.setHorizontalSpacing(8)
        layout.setVerticalSpacing(10)

        self.csv_path_edit = QLineEdit()
        self.output_path_edit = QLineEdit()
        self.font_dir_edit = QLineEdit()
        rows = [
            ("CSV input", self.csv_path_edit, self.browse_csv),
            ("Output PDF", self.output_path_edit, self.browse_output),
            ("Font folder", self.font_dir_edit, self.browse_font_dir),
        ]
        for row, (label_text, edit, handler) in enumerate(rows):
            layout.addWidget(self._field_label(label_text), row, 0)
            layout.addWidget(edit, row, 1)
            button = QPushButton("Browse")
            button.clicked.connect(handler)
            layout.addWidget(button, row, 2)

        layout.setColumnStretch(1, 1)
        layout.setRowStretch(len(rows), 1)
        return page

    def _layout_tab(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(2, 14, 2, 2)
        content_layout.setSpacing(12)

        for group_name, keys in csv_to_pdf.LAYOUT_FIELD_GROUPS:
            group = QFrame()
            group.setObjectName("FieldGroup")
            group_layout = QGridLayout(group)
            group_layout.setContentsMargins(12, 12, 12, 12)
            group_layout.setHorizontalSpacing(10)
            group_layout.setVerticalSpacing(8)
            title = QLabel(group_name)
            title.setObjectName("SectionTitle")
            group_layout.addWidget(title, 0, 0, 1, 2)

            row = 1
            for key in keys:
                label = QLabel(FIELD_LABELS.get(key, key))
                label.setMinimumWidth(150)
                group_layout.addWidget(label, row, 0)
                control = self._layout_control(key)
                group_layout.addWidget(control, row, 1)
                row += 1

            group_layout.setColumnStretch(1, 1)
            content_layout.addWidget(group)

        content_layout.addStretch(1)
        scroll.setWidget(content)
        return scroll

    def _layout_control(self, key: str) -> QWidget:
        if key == "CONTENT_FLOW":
            combo = QComboBox()
            combo.addItems(["side_by_side", "stacked_columns"])
            combo.currentTextChanged.connect(self.schedule_preview)
            self.layout_controls[key] = combo
            return combo

        if key in csv_to_pdf.TEXT_LAYOUT_KEYS:
            edit = QLineEdit()
            edit.textChanged.connect(self.schedule_preview)
            self.layout_controls[key] = edit
            return edit

        spin = QDoubleSpinBox()
        spin.setRange(-2000.0, 5000.0)
        spin.setDecimals(2)
        spin.setSingleStep(0.5 if "FONT" not in key and "LEADING" not in key else 0.1)
        spin.setKeyboardTracking(True)
        spin.valueChanged.connect(self.schedule_preview)
        self.layout_controls[key] = spin
        return spin

    def _connect_signals(self) -> None:
        self.profile_combo.currentTextChanged.connect(self.apply_profile)
        self.reset_button.clicked.connect(lambda: self.apply_profile(self.profile_combo.currentText()))
        self.load_profile_button.clicked.connect(self.load_profile_file)
        self.save_profile_button.clicked.connect(self.save_profile_file)
        self.refresh_preview_button.clicked.connect(self.render_preview)
        self.convert_button.clicked.connect(self.convert)
        self.open_output_button.clicked.connect(self.open_output)
        self.csv_path_edit.textChanged.connect(self.schedule_preview)
        self.font_dir_edit.textChanged.connect(self.schedule_preview)

        self.preview_timer = QTimer(self)
        self.preview_timer.setSingleShot(True)
        self.preview_timer.timeout.connect(self.render_preview)
        self.signals.preview_ready.connect(self._preview_ready)
        self.signals.preview_failed.connect(self._preview_failed)
        self.signals.convert_done.connect(self._convert_done)
        self.signals.convert_failed.connect(self._convert_failed)

    def _select_initial_profile(self) -> None:
        first = next(iter(self.profiles))
        self.profile_combo.setCurrentText(first)
        self.apply_profile(first)

    def merged_layout(self, name: str) -> Dict[str, Any]:
        layout = dict(csv_to_pdf.DEFAULT_LAYOUT)
        profile = self.profiles.get(name, {})
        layout.update(profile.get("layout", {}))
        return layout

    def apply_profile(self, name: str) -> None:
        layout = self.merged_layout(name)
        self.suspend_preview = True
        try:
            for key, control in self.layout_controls.items():
                value = layout.get(key, csv_to_pdf.DEFAULT_LAYOUT[key])
                control.blockSignals(True)
                if isinstance(control, QComboBox):
                    idx = control.findText(str(value))
                    control.setCurrentIndex(idx if idx >= 0 else 0)
                elif isinstance(control, QLineEdit):
                    control.setText(str(value))
                elif isinstance(control, QDoubleSpinBox):
                    control.setValue(float(value))
                control.blockSignals(False)
        finally:
            self.suspend_preview = False
        self.statusBar().showMessage(f"Loaded profile: {name}")
        self.schedule_preview()

    def current_layout(self) -> Dict[str, Any]:
        layout: Dict[str, Any] = {}
        for key, control in self.layout_controls.items():
            if isinstance(control, QComboBox):
                layout[key] = control.currentText()
            elif isinstance(control, QLineEdit):
                layout[key] = control.text().strip()
            elif isinstance(control, QDoubleSpinBox):
                layout[key] = float(control.value())
        return layout

    def browse_csv(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Choose CSV", "", "CSV files (*.csv);;All files (*.*)")
        if not path:
            return
        self.csv_path_edit.setText(path)
        if not self.output_path_edit.text().strip():
            self.output_path_edit.setText(str(Path(path).with_suffix(".pdf")))

    def browse_output(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Choose output PDF", "", "PDF files (*.pdf)")
        if path:
            self.output_path_edit.setText(path)

    def browse_font_dir(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Choose font folder")
        if path:
            self.font_dir_edit.setText(path)

    def load_profile_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Load profile", "", "JSON files (*.json);;All files (*.*)")
        if not path:
            return
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
            profiles = data.get("profiles")
            if profiles:
                self.profiles.update(profiles)
            else:
                self.profiles[Path(path).stem] = {"description": "", "layout": data.get("layout", data)}
            self.profile_combo.clear()
            self.profile_combo.addItems(list(self.profiles))
            self.profile_combo.setCurrentText(next(reversed(self.profiles)))
            self.apply_profile(self.profile_combo.currentText())
        except Exception as exc:
            QMessageBox.critical(self, "Profile load failed", str(exc))

    def save_profile_file(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Save profile", "", "JSON files (*.json)")
        if not path:
            return
        try:
            name = self.profile_combo.currentText().strip() or "Custom"
            data = {"profiles": {name: {"description": "Saved from csv_to_pdf GUI.", "layout": self.current_layout()}}}
            Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            self.statusBar().showMessage(f"Saved profile: {path}")
        except Exception as exc:
            QMessageBox.critical(self, "Profile save failed", str(exc))

    def schedule_preview(self) -> None:
        if self.suspend_preview:
            return
        self.preview_timer.start(500)

    def render_preview(self) -> None:
        csv_path = self.csv_path_edit.text().strip()
        if not csv_path:
            self.preview_canvas.set_message("Choose a CSV to preview.")
            self.preview_status.setText("Idle")
            return
        if not Path(csv_path).exists():
            self.preview_canvas.set_message("CSV file not found.")
            self.preview_status.setText("Waiting")
            return

        pdftoppm = find_pdftoppm()
        if not pdftoppm:
            self.preview_canvas.set_message("Poppler pdftoppm was not found.")
            self.preview_status.setText("Renderer missing")
            return

        layout = self.current_layout()
        font_dir = self.font_dir_edit.text().strip() or None
        self.preview_token += 1
        token = self.preview_token
        self.preview_status.setText("Rendering...")
        thread = threading.Thread(target=self._preview_worker, args=(token, csv_path, layout, font_dir, pdftoppm), daemon=True)
        thread.start()

    def _preview_worker(self, token: int, csv_path: str, layout: Dict[str, Any], font_dir: str | None, pdftoppm: str) -> None:
        try:
            base = Path(self.preview_dir.name)
            pdf_path = base / f"preview_{token}.pdf"
            png_prefix = base / f"preview_{token}"
            png_path = base / f"preview_{token}.png"
            with self.render_lock:
                csv_to_pdf.generate_pdf(csv_path, str(pdf_path), layout=layout, font_dir=font_dir, page_limit=1)
                subprocess.run(
                    [pdftoppm, "-r", "120", "-png", "-f", "1", "-l", "1", "-singlefile", str(pdf_path), str(png_prefix)],
                    check=True,
                    capture_output=True,
                    text=True,
                    **hidden_subprocess_kwargs(),
                )
            if not png_path.exists():
                raise RuntimeError("Preview image was not generated.")
            self.signals.preview_ready.emit(token, str(png_path))
        except Exception as exc:
            self.signals.preview_failed.emit(token, str(exc))

    def _preview_ready(self, token: int, png_path: str) -> None:
        if token != self.preview_token:
            return
        pixmap = QPixmap(png_path)
        if pixmap.isNull():
            self._preview_failed(token, "Preview image could not be loaded.")
            return
        self.preview_canvas.set_pixmap(pixmap)
        self.preview_status.setText("Updated")

    def _preview_failed(self, token: int, message: str) -> None:
        if token != self.preview_token:
            return
        self.preview_canvas.set_message(message)
        self.preview_status.setText("Failed")

    def convert(self) -> None:
        csv_path = self.csv_path_edit.text().strip()
        output_path = self.output_path_edit.text().strip()
        if not csv_path or not output_path:
            QMessageBox.warning(self, "Missing files", "Choose a CSV input and output PDF path.")
            return
        if not Path(csv_path).exists():
            QMessageBox.warning(self, "Missing CSV", "The selected CSV file does not exist.")
            return
        layout = self.current_layout()
        font_dir = self.font_dir_edit.text().strip() or None
        self.convert_button.setEnabled(False)
        self.statusBar().showMessage("Converting...")
        thread = threading.Thread(target=self._convert_worker, args=(csv_path, output_path, layout, font_dir), daemon=True)
        thread.start()

    def _convert_worker(self, csv_path: str, output_path: str, layout: Dict[str, Any], font_dir: str | None) -> None:
        try:
            with self.render_lock:
                page_count = csv_to_pdf.generate_pdf(csv_path, output_path, layout=layout, font_dir=font_dir)
            self.signals.convert_done.emit(output_path, page_count)
        except Exception as exc:
            self.signals.convert_failed.emit(str(exc))

    def _convert_done(self, output_path: str, page_count: int) -> None:
        self.convert_button.setEnabled(True)
        self.statusBar().showMessage(f"Wrote {page_count} page(s): {output_path}")
        QMessageBox.information(self, "Conversion complete", f"Wrote {page_count} page(s).")
        self.schedule_preview()

    def _convert_failed(self, message: str) -> None:
        self.convert_button.setEnabled(True)
        self.statusBar().showMessage("Conversion failed")
        QMessageBox.critical(self, "Conversion failed", message)

    def open_output(self) -> None:
        path = self.output_path_edit.text().strip()
        if not path:
            return
        if os.name == "nt":
            os.startfile(path)  # type: ignore[attr-defined]
        else:
            opener = "open" if sys.platform == "darwin" else "xdg-open"
            subprocess.Popen([opener, path])

    def closeEvent(self, event: Any) -> None:
        self.preview_dir.cleanup()
        super().closeEvent(event)


def main() -> int:
    app = QApplication(sys.argv)
    window = CsvToPdfApp()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
