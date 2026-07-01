#!/usr/bin/env python3
"""
Generate a half-half worksheet PDF from a proofread CSV.

Input CSV columns:
  qrange, chapter, source_pages, passage, questions_json, underlines_json, notes

questions_json example:
  [{"num":"001","stem":"Which ...?","options":{"A":"...","B":"...","C":"...","D":"..."}}]

This script does not OCR. It trusts the CSV.
Pretendard fonts are NOT bundled. To get exact output, install/provide:
  Pretendard-Regular.ttf, Pretendard-Medium.ttf, Pretendard-Bold.ttf
via ./fonts or PRETENDARD_DIR.
"""
from __future__ import annotations

import argparse
import csv
import html
import json
import os
import tempfile
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Tuple

from reportlab.lib import colors
from reportlab.lib.enums import TA_JUSTIFY, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph

W, H = A4

# ---------------------------------------------------------------------------
# Layout constants reverse-measured from the reference PDF layout.
# Coordinate system here is ReportLab bottom-left.
# ---------------------------------------------------------------------------
LEFT_MARGIN = 38.27
RIGHT_MARGIN = 38.27
HEADER_TEXT_Y = H - 24.50
HEADER_LINE_Y = H - 51.02
FOOTER_LINE_Y = H - 807.87
FOOTER_TEXT_Y = H - 815.37
CENTER_X = W / 2.0
CENTER_LINE_TOP = H - 72.50
CENTER_LINE_BOTTOM = FOOTER_LINE_Y

PASSAGE_RANGE_X = 38.27
PASSAGE_RANGE_Y = H - 83.00
PASSAGE_BOX_X = 38.27
PASSAGE_BOX_TOP = H - 104.50
PASSAGE_BOX_W = 245.19
PASSAGE_BOX_MAX_H = 620.79
PASSAGE_PAD_BOTTOM = 18.00
PASSAGE_PAD_X = 13.50
PASSAGE_PAD_TOP = 11.00
PASSAGE_TEXT_W = PASSAGE_BOX_W - PASSAGE_PAD_X * 2

RIGHT_X = 317.81
RIGHT_TOP = H - 83.00
RIGHT_W = W - RIGHT_MARGIN - RIGHT_X
STEM_W = 220.70
STEM_INDENT = 23.00
STEM_OPTION_GAP = 4.20
OPTION_BLOCK_X = RIGHT_X + STEM_INDENT
OPTION_W = RIGHT_W - STEM_INDENT

DOCUMENT_TITLE = "Reading Worksheet"
HEADER_LEFT_W = 220.0
FOOTER_PAGE_W = 70.0
OPTION_LINE_GAP = 2.20
QUESTION_BLOCK_GAP = 10.30

HEADER_FONT_SIZE = 10.0
HEADER_LEADING = 12.0
FOOTER_FONT_SIZE = 10.0
FOOTER_LEADING = 12.0
QRANGE_FONT_SIZE = 10.3
QRANGE_LEADING = 12.5
PASSAGE_FONT_SIZE = 8.95
PASSAGE_LEADING = 12.75
STEM_FONT_SIZE = 8.55
STEM_LEADING = 11.50
OPTION_FONT_SIZE = 8.0
OPTION_LEADING = 10.75

FONT_REG = "Pretendard-Regular"
FONT_MED = "Pretendard-Medium"
FONT_BOLD = "Pretendard-Bold"

LAYOUT_FIELD_GROUPS = [
    (
        "Frame",
        [
            "DOCUMENT_TITLE",
            "LEFT_MARGIN",
            "RIGHT_MARGIN",
            "HEADER_TEXT_Y",
            "HEADER_LINE_Y",
            "FOOTER_LINE_Y",
            "FOOTER_TEXT_Y",
            "CENTER_X",
            "CENTER_LINE_TOP",
            "HEADER_LEFT_W",
            "FOOTER_PAGE_W",
        ],
    ),
    (
        "Passage",
        [
            "PASSAGE_RANGE_X",
            "PASSAGE_RANGE_Y",
            "PASSAGE_BOX_X",
            "PASSAGE_BOX_TOP",
            "PASSAGE_BOX_W",
            "PASSAGE_BOX_MAX_H",
            "PASSAGE_PAD_BOTTOM",
            "PASSAGE_PAD_X",
            "PASSAGE_PAD_TOP",
        ],
    ),
    (
        "Questions",
        [
            "RIGHT_X",
            "RIGHT_TOP",
            "STEM_W",
            "STEM_INDENT",
            "STEM_OPTION_GAP",
            "OPTION_LINE_GAP",
            "QUESTION_BLOCK_GAP",
        ],
    ),
    (
        "Typography",
        [
            "HEADER_FONT_SIZE",
            "HEADER_LEADING",
            "FOOTER_FONT_SIZE",
            "FOOTER_LEADING",
            "QRANGE_FONT_SIZE",
            "QRANGE_LEADING",
            "PASSAGE_FONT_SIZE",
            "PASSAGE_LEADING",
            "STEM_FONT_SIZE",
            "STEM_LEADING",
            "OPTION_FONT_SIZE",
            "OPTION_LEADING",
        ],
    ),
]
LAYOUT_KEYS = tuple(key for _group, keys in LAYOUT_FIELD_GROUPS for key in keys)
TEXT_LAYOUT_KEYS = {"DOCUMENT_TITLE"}


def current_layout() -> Dict[str, Any]:
    return {key: globals()[key] for key in LAYOUT_KEYS}


DEFAULT_LAYOUT = current_layout()


def _recompute_layout() -> None:
    global CENTER_LINE_BOTTOM, PASSAGE_TEXT_W, RIGHT_W, OPTION_BLOCK_X, OPTION_W
    CENTER_LINE_BOTTOM = FOOTER_LINE_Y
    PASSAGE_TEXT_W = PASSAGE_BOX_W - PASSAGE_PAD_X * 2
    RIGHT_W = W - RIGHT_MARGIN - RIGHT_X
    OPTION_BLOCK_X = RIGHT_X + STEM_INDENT
    OPTION_W = RIGHT_W - STEM_INDENT


def apply_layout(layout: Dict[str, Any] | None) -> Dict[str, Any]:
    if not layout:
        return current_layout()
    for key, value in layout.items():
        if key not in LAYOUT_KEYS:
            continue
        globals()[key] = str(value) if key in TEXT_LAYOUT_KEYS else float(value)
    _recompute_layout()
    return current_layout()


def _layout_from_json(path: str, profile_name: str | None = None) -> Dict[str, Any]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if "profiles" in data:
        profiles = data["profiles"]
        if not profile_name:
            profile_name = next(iter(profiles))
        profile = profiles[profile_name]
        return profile.get("layout", profile)
    return data.get("layout", data)


def _candidate_font_dirs() -> List[Path]:
    dirs: List[Path] = []
    if os.environ.get("PRETENDARD_DIR"):
        dirs.append(Path(os.environ["PRETENDARD_DIR"]))
    dirs += [Path.cwd() / "fonts", Path(__file__).resolve().parent / "fonts"]

    # Convenience for local runtime only. Do not commit font files.
    tmp = Path(tempfile.gettempdir()) / "pretendard_runtime_fonts"
    try:
        for z in Path("/mnt/data").glob("Pretendard*.zip"):
            tmp.mkdir(exist_ok=True)
            with zipfile.ZipFile(z) as zin:
                for name in zin.namelist():
                    low = name.lower()
                    if low.endswith((".ttf", ".otf")) and "pretendard" in low:
                        out = tmp / Path(name).name
                        if not out.exists():
                            out.write_bytes(zin.read(name))
            dirs.append(tmp)
            break
    except Exception:
        pass
    return dirs


def _find_font(name_part: str, dirs: List[Path]) -> Path | None:
    low_part = name_part.lower()
    for d in dirs:
        if not d.exists():
            continue
        files = list(d.rglob("*.ttf")) + list(d.rglob("*.otf"))
        for f in files:
            if low_part in f.name.lower():
                return f
    return None


def register_fonts() -> Tuple[str, str, str]:
    dirs = _candidate_font_dirs()
    reg = _find_font("Pretendard-Regular", dirs)
    med = _find_font("Pretendard-Medium", dirs) or _find_font("Pretendard-SemiBold", dirs)
    bold = _find_font("Pretendard-Bold", dirs)
    if reg and med and bold:
        pdfmetrics.registerFont(TTFont(FONT_REG, str(reg)))
        pdfmetrics.registerFont(TTFont(FONT_MED, str(med)))
        pdfmetrics.registerFont(TTFont(FONT_BOLD, str(bold)))
        return FONT_REG, FONT_MED, FONT_BOLD

    fallback_reg = next(
        (
            p
            for p in [
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf",
                "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
            ]
            if Path(p).exists()
        ),
        None,
    )
    fallback_bold = next(
        (
            p
            for p in [
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf",
            ]
            if Path(p).exists()
        ),
        fallback_reg,
    )
    if not fallback_reg:
        raise RuntimeError("No usable TTF/OTF font found. Set PRETENDARD_DIR.")
    pdfmetrics.registerFont(TTFont(FONT_REG, fallback_reg))
    pdfmetrics.registerFont(TTFont(FONT_MED, fallback_bold or fallback_reg))
    pdfmetrics.registerFont(TTFont(FONT_BOLD, fallback_bold or fallback_reg))
    return FONT_REG, FONT_MED, FONT_BOLD


def pstyle(name: str, font: str, size: float, leading: float, alignment=TA_LEFT, **kw) -> ParagraphStyle:
    return ParagraphStyle(name, fontName=font, fontSize=size, leading=leading, alignment=alignment, **kw)


def make_styles(fonts: Tuple[str, str, str]) -> Dict[str, ParagraphStyle]:
    reg, med, bold = fonts
    return {
        "header_left": pstyle("header_left", reg, HEADER_FONT_SIZE, HEADER_LEADING),
        "header_right": pstyle("header_right", reg, HEADER_FONT_SIZE, HEADER_LEADING, alignment=TA_RIGHT),
        "footer": pstyle(
            "footer",
            reg,
            FOOTER_FONT_SIZE,
            FOOTER_LEADING,
            alignment=TA_RIGHT,
            textColor=colors.Color(0.86, 0.86, 0.86),
        ),
        "qrange": pstyle("qrange", bold, QRANGE_FONT_SIZE, QRANGE_LEADING),
        "passage": pstyle("passage", med, PASSAGE_FONT_SIZE, PASSAGE_LEADING, alignment=TA_JUSTIFY, spaceAfter=0),
        "stem": pstyle("stem", reg, STEM_FONT_SIZE, STEM_LEADING, alignment=TA_LEFT, leftIndent=STEM_INDENT, firstLineIndent=-STEM_INDENT),
        # Option block starts at the same guide line as wrapped stem lines.
        # Wrapped option lines align to the option text after the marker.
        "option": pstyle("option", reg, OPTION_FONT_SIZE, OPTION_LEADING, alignment=TA_LEFT, leftIndent=0, firstLineIndent=0),
    }


def esc(s: Any) -> str:
    s = "" if s is None else str(s)
    s = html.escape(s, quote=False)
    for tag in ["u", "br"]:
        s = s.replace(f"&lt;{tag}&gt;", f"<{tag}>").replace(f"&lt;/{tag}&gt;", f"</{tag}>")
        s = s.replace(f"&lt;{tag}/&gt;", f"<{tag}/>")
    return s


def display_qrange(value: str) -> str:
    normalized = (value or "").strip().replace("~", "-")
    if "-" not in normalized:
        return normalized
    start, end = normalized.split("-", 1)
    if start == end:
        return start
    return f"{start}~{end}"


def phrase_underline_xml(text: str, phrases: List[str]) -> str:
    out = esc(text)
    for phrase in sorted((p for p in phrases if p), key=len, reverse=True):
        ep = esc(phrase)
        out = out.replace(ep, f"<u>{ep}</u>", 1)
    return out


def para(text: str, style: ParagraphStyle, width: float) -> Tuple[Paragraph, float]:
    p = Paragraph(text, style)
    _w, h = p.wrap(width, 10000)
    return p, h


def draw_para(c: canvas.Canvas, p: Paragraph, x: float, y_top: float, width: float) -> float:
    _w, h = p.wrap(width, 10000)
    p.drawOn(c, x, y_top - h)
    return h


def fit_paragraph_xml(text_xml: str, base_style: ParagraphStyle, width: float, max_h: float,
                      min_size: float = 7.1, leading_ratio: float = 1.425) -> Tuple[Paragraph, ParagraphStyle, float]:
    style = base_style
    p, h = para(text_xml, style, width)
    if h <= max_h:
        return p, style, h
    size = style.fontSize
    while h > max_h and size > min_size:
        size -= 0.15
        style = ParagraphStyle(style.name + "_fit", parent=base_style, fontSize=size, leading=size * leading_ratio)
        p, h = para(text_xml, style, width)
    return p, style, h


def make_option_style(base_style: ParagraphStyle) -> ParagraphStyle:
    marker_w = (
        pdfmetrics.stringWidth("(A)", FONT_MED, base_style.fontSize)
        + pdfmetrics.stringWidth(" ", base_style.fontName, base_style.fontSize)
    )
    return ParagraphStyle(
        base_style.name + "_opt",
        parent=base_style,
        leftIndent=marker_w,
        firstLineIndent=-marker_w,
    )


def option_xml(label: str, text: Any, underlines: List[str]) -> str:
    marker = f'<font name="{FONT_MED}">({esc(label)})</font> '
    return marker + phrase_underline_xml(text, underlines)


def draw_static_frame(c: canvas.Canvas, chapter: str, page_no: int, styles: Dict[str, ParagraphStyle]) -> None:
    c.setStrokeColor(colors.Color(0.33, 0.33, 0.33))
    c.setLineWidth(1.0)
    c.line(LEFT_MARGIN, HEADER_LINE_Y, W - RIGHT_MARGIN, HEADER_LINE_Y)

    c.setStrokeColor(colors.Color(0.47, 0.47, 0.47))
    c.setLineWidth(0.7)
    c.line(LEFT_MARGIN, FOOTER_LINE_Y, W - RIGHT_MARGIN, FOOTER_LINE_Y)

    c.setStrokeColor(colors.Color(0.84, 0.84, 0.84))
    c.setLineWidth(0.6)
    c.line(CENTER_X, CENTER_LINE_TOP, CENTER_X, CENTER_LINE_BOTTOM)

    draw_para(c, Paragraph(esc(DOCUMENT_TITLE), styles["header_left"]), LEFT_MARGIN, HEADER_TEXT_Y, HEADER_LEFT_W)
    draw_para(c, Paragraph(esc(chapter), styles["header_right"]), LEFT_MARGIN, HEADER_TEXT_Y, W - LEFT_MARGIN - RIGHT_MARGIN)
    draw_para(c, Paragraph(f"page {page_no}", styles["footer"]), W - RIGHT_MARGIN - FOOTER_PAGE_W, FOOTER_TEXT_Y, FOOTER_PAGE_W)


def draw_passage(c: canvas.Canvas, row: Dict[str, str], styles: Dict[str, ParagraphStyle]) -> None:
    qrange = display_qrange(row.get("qrange") or "")
    draw_para(c, Paragraph(esc(qrange), styles["qrange"]), PASSAGE_RANGE_X, PASSAGE_RANGE_Y, PASSAGE_BOX_W)

    try:
        underlines = json.loads(row.get("underlines_json") or "[]")
        if not isinstance(underlines, list):
            underlines = []
    except Exception:
        underlines = []
    passage_xml = phrase_underline_xml(row.get("passage") or "", underlines)
    p, style, h = fit_paragraph_xml(
        passage_xml,
        styles["passage"],
        PASSAGE_TEXT_W,
        PASSAGE_BOX_MAX_H - PASSAGE_PAD_TOP - PASSAGE_PAD_BOTTOM,
    )
    box_h = min(PASSAGE_BOX_MAX_H, h + PASSAGE_PAD_TOP + PASSAGE_PAD_BOTTOM)
    c.setFillColor(colors.Color(0.917647, 0.917647, 0.917647))
    c.rect(PASSAGE_BOX_X, PASSAGE_BOX_TOP - box_h, PASSAGE_BOX_W, box_h, stroke=0, fill=1)
    c.setFillColor(colors.black)
    p.drawOn(c, PASSAGE_BOX_X + PASSAGE_PAD_X, PASSAGE_BOX_TOP - PASSAGE_PAD_TOP - h)


def draw_questions(c: canvas.Canvas, row: Dict[str, str], styles: Dict[str, ParagraphStyle]) -> None:
    try:
        questions = json.loads(row.get("questions_json") or "[]")
        if not isinstance(questions, list):
            questions = []
    except Exception:
        questions = []
    try:
        underlines = json.loads(row.get("underlines_json") or "[]")
        if not isinstance(underlines, list):
            underlines = []
    except Exception:
        underlines = []

    y = RIGHT_TOP
    max_y_bottom = FOOTER_LINE_Y + 10.0

    def layout_height(stem_style, option_style) -> float:
        yy = RIGHT_TOP
        for q in questions:
            num = str(q.get("num", "")).zfill(3)
            stem_text = f'<font name="{FONT_BOLD}">{num}.</font> ' + phrase_underline_xml(q.get("stem", ""), underlines)
            _, stem_h = para(stem_text, stem_style, STEM_W)
            yy -= stem_h + STEM_OPTION_GAP
            opts = q.get("options") or {}
            if isinstance(opts, list):
                opts = {chr(ord("A") + i): v for i, v in enumerate(opts)}
            for lab in sorted(opts.keys()):
                op_xml = option_xml(lab, opts[lab], underlines)
                _, oh = para(op_xml, option_style, OPTION_W)
                yy -= oh + OPTION_LINE_GAP
            yy -= QUESTION_BLOCK_GAP
        return RIGHT_TOP - yy

    stem_style = styles["stem"]
    option_style = make_option_style(styles["option"])
    available = RIGHT_TOP - max_y_bottom
    total_h = layout_height(stem_style, option_style)
    if total_h > available:
        scale = max(0.82, available / max(total_h, 1))
        stem_size = max(7.1, stem_style.fontSize * scale)
        opt_size = max(6.8, option_style.fontSize * scale)
        stem_style = ParagraphStyle("stem_fit", parent=stem_style, fontSize=stem_size, leading=stem_size * 1.345)
        base_option = ParagraphStyle("option_fit_base", parent=styles["option"], fontSize=opt_size, leading=opt_size * 1.34)
        option_style = make_option_style(base_option)

    for q in questions:
        num = str(q.get("num", "")).zfill(3)
        stem_xml = f'<font name="{FONT_BOLD}">{num}.</font> ' + phrase_underline_xml(q.get("stem", ""), underlines)
        p, h = para(stem_xml, stem_style, STEM_W)
        draw_para(c, p, RIGHT_X, y, STEM_W)
        y -= h + STEM_OPTION_GAP

        opts = q.get("options") or {}
        if isinstance(opts, list):
            opts = {chr(ord("A") + i): v for i, v in enumerate(opts)}
        for label in sorted(opts.keys()):
            op_xml = option_xml(label, opts[label], underlines)
            op, oh = para(op_xml, option_style, OPTION_W)
            draw_para(c, op, OPTION_BLOCK_X, y, OPTION_W)
            y -= oh + OPTION_LINE_GAP
        y -= QUESTION_BLOCK_GAP


def read_rows(csv_path: str) -> List[Dict[str, str]]:
    with open(csv_path, "r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def draw_page(c: canvas.Canvas, row: Dict[str, str], page_no: int, styles: Dict[str, ParagraphStyle]) -> None:
    draw_static_frame(c, row.get("chapter") or "", page_no, styles)
    draw_passage(c, row, styles)
    draw_questions(c, row, styles)


def generate_pdf(
    csv_path: str,
    out_path: str,
    layout: Dict[str, Any] | None = None,
    font_dir: str | None = None,
) -> int:
    old_font_dir = os.environ.get("PRETENDARD_DIR")
    if font_dir:
        os.environ["PRETENDARD_DIR"] = font_dir
    try:
        apply_layout(layout)
        fonts = register_fonts()
        styles = make_styles(fonts)
        rows = read_rows(csv_path)
        c = canvas.Canvas(out_path, pagesize=A4)
        for i, row in enumerate(rows, 1):
            draw_page(c, row, i, styles)
            c.showPage()
        c.save()
        return len(rows)
    finally:
        if font_dir:
            if old_font_dir is None:
                os.environ.pop("PRETENDARD_DIR", None)
            else:
                os.environ["PRETENDARD_DIR"] = old_font_dir


def main() -> int:
    parser = argparse.ArgumentParser(description="CSV -> half-half worksheet PDF")
    parser.add_argument("csv", help="proofread CSV file")
    parser.add_argument("--out", default="csv_to_pdf.pdf", help="output PDF path")
    parser.add_argument("--layout-json", help="layout or profile JSON path")
    parser.add_argument("--profile", help="profile name inside a profile JSON")
    parser.add_argument("--font-dir", help="directory containing Pretendard font files")
    parser.add_argument("--title", help="override header title")
    args = parser.parse_args()

    layout = _layout_from_json(args.layout_json, args.profile) if args.layout_json else {}
    if args.title:
        layout["DOCUMENT_TITLE"] = args.title
    page_count = generate_pdf(args.csv, args.out, layout=layout, font_dir=args.font_dir)
    print(f"Wrote {page_count} page(s): {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
