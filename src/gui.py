#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Any, Dict

try:
    from . import csv_to_pdf
except ImportError:
    import csv_to_pdf  # type: ignore


APP_DIR = Path(__file__).resolve().parent
DEFAULT_PROFILE_CANDIDATES = [
    APP_DIR.parent / "profiles" / "default_profiles.json",
    APP_DIR / "profiles" / "default_profiles.json",
]

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
    "RIGHT_X": "Question column X",
    "RIGHT_TOP": "Question column top",
    "STEM_W": "Question stem width",
    "STEM_INDENT": "Stem/option guide indent",
    "STEM_OPTION_GAP": "Stem to first option gap",
    "OPTION_LINE_GAP": "Option line gap",
    "QUESTION_BLOCK_GAP": "Question block gap",
    "HEADER_FONT_SIZE": "Header font size",
    "HEADER_LEADING": "Header leading",
    "FOOTER_FONT_SIZE": "Footer font size",
    "FOOTER_LEADING": "Footer leading",
    "QRANGE_FONT_SIZE": "Range label font size",
    "QRANGE_LEADING": "Range label leading",
    "PASSAGE_FONT_SIZE": "Passage font size",
    "PASSAGE_LEADING": "Passage leading",
    "STEM_FONT_SIZE": "Stem font size",
    "STEM_LEADING": "Stem leading",
    "OPTION_FONT_SIZE": "Option font size",
    "OPTION_LEADING": "Option leading",
}


class ScrollFrame(ttk.Frame):
    def __init__(self, parent: tk.Widget) -> None:
        super().__init__(parent)
        self.canvas = tk.Canvas(self, borderwidth=0, highlightthickness=0)
        self.scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.inner = ttk.Frame(self.canvas)
        self.window_id = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.scrollbar.grid(row=0, column=1, sticky="ns")
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        self.inner.bind("<Configure>", self._on_inner_configure)
        self.canvas.bind("<Configure>", self._on_canvas_configure)

    def _on_inner_configure(self, _event: tk.Event) -> None:
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _on_canvas_configure(self, event: tk.Event) -> None:
        self.canvas.itemconfigure(self.window_id, width=event.width)


class CsvToPdfApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("csv_to_pdf")
        self.root.geometry("900x720")
        self.profiles: Dict[str, Dict[str, Any]] = {}
        self.layout_vars = {key: tk.StringVar() for key in csv_to_pdf.LAYOUT_KEYS}
        self.csv_path = tk.StringVar()
        self.output_path = tk.StringVar()
        self.font_dir = tk.StringVar()
        self.profile_name = tk.StringVar()
        self.status = tk.StringVar(value="Ready")
        self._load_default_profiles()
        self._build_ui()
        self._select_initial_profile()

    def _load_default_profiles(self) -> None:
        self.profiles = {"Default": {"description": "Built-in default layout.", "layout": {}}}
        for path in DEFAULT_PROFILE_CANDIDATES:
            if path.exists():
                data = json.loads(path.read_text(encoding="utf-8"))
                self.profiles.update(data.get("profiles", {}))
                break

    def _select_initial_profile(self) -> None:
        first = next(iter(self.profiles))
        self.profile_name.set(first)
        self.apply_profile(first)

    def _build_ui(self) -> None:
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(1, weight=1)

        top = ttk.Frame(self.root, padding=12)
        top.grid(row=0, column=0, sticky="ew")
        top.columnconfigure(1, weight=1)

        ttk.Label(top, text="Profile").grid(row=0, column=0, sticky="w", padx=(0, 8))
        self.profile_combo = ttk.Combobox(top, textvariable=self.profile_name, values=list(self.profiles), state="readonly")
        self.profile_combo.grid(row=0, column=1, sticky="ew")
        self.profile_combo.bind("<<ComboboxSelected>>", lambda _event: self.apply_profile(self.profile_name.get()))
        ttk.Button(top, text="Reset", command=lambda: self.apply_profile(self.profile_name.get())).grid(row=0, column=2, padx=6)
        ttk.Button(top, text="Load Profile", command=self.load_profile_file).grid(row=0, column=3, padx=6)
        ttk.Button(top, text="Save Profile", command=self.save_profile_file).grid(row=0, column=4)

        notebook = ttk.Notebook(self.root)
        notebook.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 8))
        notebook.add(self._files_tab(notebook), text="Files")
        notebook.add(self._layout_tab(notebook), text="Layout")

        bottom = ttk.Frame(self.root, padding=(12, 0, 12, 12))
        bottom.grid(row=2, column=0, sticky="ew")
        bottom.columnconfigure(0, weight=1)
        ttk.Label(bottom, textvariable=self.status).grid(row=0, column=0, sticky="w")
        ttk.Button(bottom, text="Open Output", command=self.open_output).grid(row=0, column=1, padx=6)
        ttk.Button(bottom, text="Convert", command=self.convert).grid(row=0, column=2)

    def _files_tab(self, parent: tk.Widget) -> ttk.Frame:
        frame = ttk.Frame(parent, padding=16)
        frame.columnconfigure(1, weight=1)
        rows = [
            ("CSV input", self.csv_path, self.browse_csv),
            ("Output PDF", self.output_path, self.browse_output),
            ("Font folder", self.font_dir, self.browse_font_dir),
        ]
        for row, (label, var, command) in enumerate(rows):
            ttk.Label(frame, text=label).grid(row=row, column=0, sticky="w", pady=6, padx=(0, 8))
            ttk.Entry(frame, textvariable=var).grid(row=row, column=1, sticky="ew", pady=6)
            ttk.Button(frame, text="Browse", command=command).grid(row=row, column=2, padx=(8, 0), pady=6)
        return frame

    def _layout_tab(self, parent: tk.Widget) -> ScrollFrame:
        scroll = ScrollFrame(parent)
        row = 0
        for group_name, keys in csv_to_pdf.LAYOUT_FIELD_GROUPS:
            label = ttk.Label(scroll.inner, text=group_name, font=("", 10, "bold"))
            label.grid(row=row, column=0, columnspan=4, sticky="w", pady=(14, 6), padx=8)
            row += 1
            for i, key in enumerate(keys):
                col = 0 if i % 2 == 0 else 2
                if i % 2 == 0 and i:
                    row += 1
                ttk.Label(scroll.inner, text=FIELD_LABELS.get(key, key)).grid(row=row, column=col, sticky="w", padx=8, pady=4)
                ttk.Entry(scroll.inner, textvariable=self.layout_vars[key], width=24).grid(row=row, column=col + 1, sticky="ew", padx=8, pady=4)
            row += 1
        for col in (1, 3):
            scroll.inner.columnconfigure(col, weight=1)
        return scroll

    def merged_layout(self, name: str) -> Dict[str, Any]:
        layout = dict(csv_to_pdf.DEFAULT_LAYOUT)
        profile = self.profiles.get(name, {})
        layout.update(profile.get("layout", {}))
        return layout

    def apply_profile(self, name: str) -> None:
        layout = self.merged_layout(name)
        for key, var in self.layout_vars.items():
            value = layout.get(key, csv_to_pdf.DEFAULT_LAYOUT[key])
            var.set(str(value))
        self.status.set(f"Loaded profile: {name}")

    def current_layout(self) -> Dict[str, Any]:
        layout: Dict[str, Any] = {}
        for key, var in self.layout_vars.items():
            value = var.get().strip()
            if key in csv_to_pdf.TEXT_LAYOUT_KEYS:
                layout[key] = value
            else:
                layout[key] = float(value)
        return layout

    def browse_csv(self) -> None:
        path = filedialog.askopenfilename(filetypes=[("CSV files", "*.csv"), ("All files", "*.*")])
        if path:
            self.csv_path.set(path)
            if not self.output_path.get().strip():
                self.output_path.set(str(Path(path).with_suffix(".pdf")))

    def browse_output(self) -> None:
        path = filedialog.asksaveasfilename(defaultextension=".pdf", filetypes=[("PDF files", "*.pdf")])
        if path:
            self.output_path.set(path)

    def browse_font_dir(self) -> None:
        path = filedialog.askdirectory()
        if path:
            self.font_dir.set(path)

    def load_profile_file(self) -> None:
        path = filedialog.askopenfilename(filetypes=[("JSON files", "*.json"), ("All files", "*.*")])
        if not path:
            return
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
            profiles = data.get("profiles")
            if profiles:
                self.profiles.update(profiles)
            else:
                self.profiles[Path(path).stem] = {"description": "", "layout": data.get("layout", data)}
            self.profile_combo.configure(values=list(self.profiles))
            self.profile_name.set(next(reversed(self.profiles)))
            self.apply_profile(self.profile_name.get())
        except Exception as exc:
            messagebox.showerror("Profile load failed", str(exc))

    def save_profile_file(self) -> None:
        path = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON files", "*.json")])
        if not path:
            return
        try:
            name = self.profile_name.get().strip() or "Custom"
            data = {"profiles": {name: {"description": "Saved from csv_to_pdf GUI.", "layout": self.current_layout()}}}
            Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            self.status.set(f"Saved profile: {path}")
        except Exception as exc:
            messagebox.showerror("Profile save failed", str(exc))

    def convert(self) -> None:
        csv_path = self.csv_path.get().strip()
        output_path = self.output_path.get().strip()
        if not csv_path or not output_path:
            messagebox.showwarning("Missing files", "Choose a CSV input and output PDF path.")
            return
        try:
            layout = self.current_layout()
        except ValueError as exc:
            messagebox.showerror("Invalid layout value", str(exc))
            return
        self.status.set("Converting...")
        font_dir = self.font_dir.get().strip() or None
        thread = threading.Thread(target=self._convert_worker, args=(csv_path, output_path, layout, font_dir), daemon=True)
        thread.start()

    def _convert_worker(self, csv_path: str, output_path: str, layout: Dict[str, Any], font_dir: str | None) -> None:
        try:
            page_count = csv_to_pdf.generate_pdf(csv_path, output_path, layout=layout, font_dir=font_dir)
        except Exception as exc:
            message = str(exc)
            self.root.after(0, lambda: self._convert_failed(message))
            return
        self.root.after(0, lambda: self._convert_done(output_path, page_count))

    def _convert_done(self, output_path: str, page_count: int) -> None:
        self.status.set(f"Wrote {page_count} page(s): {output_path}")
        messagebox.showinfo("Conversion complete", f"Wrote {page_count} page(s).")

    def _convert_failed(self, message: str) -> None:
        self.status.set("Conversion failed")
        messagebox.showerror("Conversion failed", message)

    def open_output(self) -> None:
        path = self.output_path.get().strip()
        if not path:
            return
        if os.name == "nt":
            os.startfile(path)  # type: ignore[attr-defined]
        else:
            opener = "open" if sys.platform == "darwin" else "xdg-open"
            subprocess.Popen([opener, path])


def main() -> None:
    root = tk.Tk()
    CsvToPdfApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
