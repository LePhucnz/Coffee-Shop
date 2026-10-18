"""
Sprint 6 (FR-13): xuất báo cáo lương / phiếu lương ra PDF bằng reportlab.
Tiếng Việt cần font Unicode: tự tìm Arial (Windows/macOS), DejaVu hoặc Liberation (Linux),
hoặc đặt biến môi trường PDF_FONT_PATH / PDF_FONT_BOLD_PATH. Không tìm thấy font thì bỏ dấu để vẫn đọc được.
"""
import io
import os
import unicodedata
from datetime import datetime
from typing import List, Optional, Sequence, Tuple

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

FONT_CANDIDATES = [
    (os.getenv("PDF_FONT_PATH", ""), os.getenv("PDF_FONT_BOLD_PATH", "")),
    ("C:/Windows/Fonts/arial.ttf", "C:/Windows/Fonts/arialbd.ttf"),
    ("C:/Windows/Fonts/tahoma.ttf", "C:/Windows/Fonts/tahomabd.ttf"),
    ("/System/Library/Fonts/Supplemental/Arial.ttf", "/System/Library/Fonts/Supplemental/Arial Bold.ttf"),
    ("/Library/Fonts/Arial.ttf", "/Library/Fonts/Arial Bold.ttf"),
    ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
    ("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
     "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"),
    ("/usr/share/fonts/TTF/DejaVuSans.ttf", "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf"),
]

BRAND = colors.HexColor("#cf6800")
HEAD_BG = colors.HexColor("#eee7db")
LINE = colors.HexColor("#e6dfd5")

_fonts: Optional[Tuple[str, str, bool]] = None


def _register_fonts() -> Tuple[str, str, bool]:
    """Trả về (font thường, font đậm, có hỗ trợ tiếng Việt hay không)"""
    global _fonts
    if _fonts:
        return _fonts
    for regular, bold in FONT_CANDIDATES:
        if regular and os.path.isfile(regular):
            try:
                pdfmetrics.registerFont(TTFont("VN", regular))
                pdfmetrics.registerFont(TTFont("VN-Bold", bold if bold and os.path.isfile(bold) else regular))
                _fonts = ("VN", "VN-Bold", True)
                return _fonts
            except Exception:
                continue
    _fonts = ("Helvetica", "Helvetica-Bold", False)
    return _fonts


def _text(value, unicode_ok: bool) -> str:
    text = "" if value is None else str(value)
    if unicode_ok:
        return text
    text = text.replace("đ", "d").replace("Đ", "D")
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")


def build_pdf(title: str, subtitle: str, info: Sequence[Tuple[str, str]],
              tables: List[dict], wide: bool = False, notes: Sequence[str] = ()) -> bytes:
    """
    tables: mỗi bảng {"tieu_de": str, "header": [...], "rows": [[...]], "widths": [mm...] (tùy chọn),
                      "align_right": [chỉ số cột canh phải], "bold_last": bool}
    """
    regular, bold, unicode_ok = _register_fonts()
    t = lambda v: _text(v, unicode_ok)
    buf = io.BytesIO()
    pagesize = landscape(A4) if wide else A4
    doc = SimpleDocTemplate(buf, pagesize=pagesize, leftMargin=12 * mm, rightMargin=12 * mm,
                            topMargin=12 * mm, bottomMargin=12 * mm, title=t(title))
    h1 = ParagraphStyle("h1", fontName=bold, fontSize=16, leading=20, textColor=colors.HexColor("#18181b"))
    sub = ParagraphStyle("sub", fontName=regular, fontSize=9, leading=12, textColor=colors.HexColor("#71717a"))
    h2 = ParagraphStyle("h2", fontName=bold, fontSize=11, leading=14, spaceBefore=6, spaceAfter=4, textColor=BRAND)
    cell = ParagraphStyle("cell", fontName=regular, fontSize=8, leading=10)
    cell_b = ParagraphStyle("cellb", fontName=bold, fontSize=8, leading=10)
    note = ParagraphStyle("note", fontName=regular, fontSize=8, leading=11, textColor=colors.HexColor("#52525b"))

    story = [Paragraph(t("QL Ca Làm · " + title), h1),
             Paragraph(t(subtitle), sub), Spacer(1, 4 * mm)]
    if info:
        rows = []
        pairs = list(info)
        for i in range(0, len(pairs), 2):
            row = []
            for k, v in pairs[i:i + 2]:
                row += [Paragraph(t(k), cell), Paragraph(t(v), cell_b)]
            while len(row) < 4:
                row.append("")
            rows.append(row)
        width = pagesize[0] - 24 * mm
        info_table = Table(rows, colWidths=[width * 0.18, width * 0.32, width * 0.18, width * 0.32])
        info_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#fbf8f4")),
            ("BOX", (0, 0), (-1, -1), 0.5, LINE),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]))
        story += [info_table, Spacer(1, 4 * mm)]

    for spec in tables:
        if spec.get("tieu_de"):
            story.append(Paragraph(t(spec["tieu_de"]), h2))
        right = set(spec.get("align_right", []))
        data = [[Paragraph(t(h), cell_b) for h in spec["header"]]]
        for row in spec["rows"]:
            data.append([Paragraph(t(v), cell) for v in row])
        if not spec["rows"]:
            data.append([Paragraph(t("Không có dữ liệu"), cell)] + [""] * (len(spec["header"]) - 1))
        widths = [w * mm for w in spec["widths"]] if spec.get("widths") else None
        table = Table(data, colWidths=widths, repeatRows=1)
        style = [
            ("BACKGROUND", (0, 0), (-1, 0), HEAD_BG),
            ("LINEBELOW", (0, 0), (-1, -1), 0.4, LINE),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ]
        for c in right:
            for r in range(len(data)):
                if isinstance(data[r][c], Paragraph):
                    data[r][c].style = ParagraphStyle(f"r{c}{r}", parent=data[r][c].style, alignment=2)
        if spec.get("bold_last") and spec["rows"]:
            style.append(("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#fff4e6")))
            for c, p in enumerate(data[-1]):
                if isinstance(p, Paragraph):
                    p.style = ParagraphStyle(f"bl{c}", parent=p.style, fontName=bold)
        table.setStyle(TableStyle(style))
        story += [table, Spacer(1, 3 * mm)]

    for n in notes:
        story.append(Paragraph(t(n), note))
    story.append(Spacer(1, 2 * mm))
    story.append(Paragraph(t(f"Xuất lúc {datetime.now():%H:%M %d/%m/%Y}"), note))
    doc.build(story)
    return buf.getvalue()
