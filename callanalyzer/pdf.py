"""Turn an AI insights report (Markdown) into a shareable PDF. Pure Python (fpdf2), works on Windows and online."""
from __future__ import annotations

import re
from pathlib import Path

import markdown
from fpdf import FPDF

FONTS = Path(__file__).parent / "fonts"
ACCENT = (42, 120, 214)

# Emoji the font can't draw -> plain symbols; anything else outside the font is dropped.
SWAPS = {"✅": "✓", "✔️": "✓", "❌": "✗", "⚠️": "!", "⚠": "!", "🟡": "•", "🟢": "•", "🔴": "•", "➖": "–",
         "📈": "", "📉": "", "💡": "", "⭐": "*", "‍": "", "️": ""}


class _Doc(FPDF):
    def __init__(self, title: str, sub: str):
        super().__init__(format="A4")
        self.t, self.sub = title, sub
        self.add_font("dv", "", FONTS / "DejaVuSans.ttf")
        self.add_font("dv", "B", FONTS / "DejaVuSans-Bold.ttf")
        self.add_font("dv", "I", FONTS / "DejaVuSans.ttf")
        self.add_font("dv", "BI", FONTS / "DejaVuSans-Bold.ttf")
        self.set_margins(16, 18, 16)
        self.set_auto_page_break(True, 18)

    def header(self):
        if self.page_no() == 1:
            return
        self.set_font("dv", "", 8)
        self.set_text_color(120, 120, 120)
        self.cell(0, 6, self.t, align="L")
        self.ln(8)

    def footer(self):
        self.set_y(-12)
        self.set_font("dv", "", 8)
        self.set_text_color(120, 120, 120)
        self.cell(0, 6, f"{self.sub}   ·   Page {self.page_no()} of {{nb}}", align="C")


def _clean(text: str, cmap: dict) -> str:
    for a, b in SWAPS.items():
        text = text.replace(a, b)
    return "".join(c for c in text if c in "\n\t" or ord(c) in cmap)


def report_pdf(md: str, title: str, subtitle: str = "", footer: str = "", kpis: list | None = None,
               charts: list | None = None) -> bytes:
    doc = _Doc(title, footer or title)
    doc.add_page()
    cmap = doc.fonts["dv"]["cmap"] if isinstance(doc.fonts["dv"], dict) else doc.fonts["dv"].cmap
    # title block
    doc.set_fill_color(*ACCENT)
    doc.rect(0, 0, doc.w, 4, "F")
    doc.set_fill_color(255, 255, 255)
    doc.set_font("dv", "B", 20)
    doc.set_text_color(25, 25, 25)
    doc.multi_cell(0, 10, _clean(title, cmap), new_x="LMARGIN", new_y="NEXT", align="L")
    if subtitle:
        doc.set_font("dv", "", 9.5)
        doc.set_text_color(100, 100, 100)
        doc.multi_cell(0, 5.5, _clean(subtitle, cmap), new_x="LMARGIN", new_y="NEXT", align="L")
    doc.ln(2)
    doc.set_draw_color(*ACCENT)
    doc.set_line_width(0.5)
    doc.line(doc.l_margin, doc.get_y(), doc.w - doc.r_margin, doc.get_y())
    doc.ln(4)
    if kpis:
        _tiles(doc, kpis, cmap)
    for ch in charts or []:
        _bars(doc, *ch, cmap=cmap)
    # body: tables are drawn with fpdf's table layout, everything else via HTML
    md = re.sub(r"(?m)^(\s*)[*+] ", r"\1- ", _clean(md, cmap))
    md = re.sub(r"(?m)^([^\n|-].*)\n(\s*[-\d])", r"\1\n\n\2", md)  # lists need a blank line before them
    doc.set_text_color(30, 30, 30)
    for kind, chunk in _blocks(md):
        if kind == "table":
            _table(doc, chunk)
        elif chunk.strip():
            html = markdown.markdown(chunk, extensions=["sane_lists"])
            html = re.sub(r"<(/?)h1>", r"<\1h2>", html)
            html = re.sub(r"</?code>", "", html)
            doc.write_html(html, font_family="dv", li_prefix_color=ACCENT, tag_styles=_styles())
    return bytes(doc.output())


def _rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _tiles(doc: FPDF, tiles: list, cmap) -> None:
    """A row of KPI tiles: (label, value, colour)."""
    n = len(tiles)
    gap = 3
    w = (doc.w - doc.l_margin - doc.r_margin - gap * (n - 1)) / n
    y = doc.get_y()
    for i, (label, value, color) in enumerate(tiles):
        x = doc.l_margin + i * (w + gap)
        r, g, b = _rgb(color)
        doc.set_fill_color(int(r * .1 + 255 * .9), int(g * .1 + 255 * .9), int(b * .1 + 255 * .9))
        doc.rect(x, y, w, 18, "F")
        doc.set_fill_color(r, g, b)
        doc.rect(x, y, w, 1.2, "F")
        doc.set_xy(x, y + 2.5)
        size = 7.0
        doc.set_font("dv", "", size)
        while doc.get_string_width(_clean(label, cmap)) > w - 2 and size > 5:
            size -= .5
            doc.set_font("dv", "", size)
        doc.set_text_color(90, 90, 90)
        doc.cell(w, 4, _clean(label, cmap), align="C")
        doc.set_xy(x, y + 7.5)
        doc.set_font("dv", "B", 13 if len(value) < 10 else 10)
        doc.set_text_color(r, g, b)
        doc.cell(w, 7, _clean(value, cmap), align="C")
    doc.set_fill_color(255, 255, 255)
    doc.set_text_color(30, 30, 30)
    doc.set_y(y + 23)


def _bars(doc: FPDF, title: str, items: list, vmax: float, cmap=None) -> None:
    """A small horizontal bar chart: items = (label, value, text, colour)."""
    if not items:
        return
    if doc.get_y() + 10 + 6.5 * len(items) > doc.h - 20:
        doc.add_page()
    doc.set_font("dv", "B", 10)
    doc.set_text_color(40, 40, 40)
    doc.cell(0, 7, _clean(title, cmap), new_x="LMARGIN", new_y="NEXT")
    full = doc.w - doc.l_margin - doc.r_margin
    lw, tw = full * .38, 26
    bw = full - lw - tw
    doc.set_font("dv", "", 8)
    for label, value, text, color in items:
        y = doc.get_y()
        lab = _clean(str(label), cmap)
        while doc.get_string_width(lab) > lw - 3 and len(lab) > 4:
            lab = lab[:-2]
        if lab != _clean(str(label), cmap):
            lab = lab.rstrip() + "…"
        doc.set_text_color(50, 50, 50)
        doc.set_xy(doc.l_margin, y)
        doc.cell(lw - 2, 5.5, lab, align="R")
        doc.set_fill_color(238, 240, 244)
        doc.rect(doc.l_margin + lw, y + 1, bw, 3.6, "F")
        doc.set_fill_color(*_rgb(color))
        doc.rect(doc.l_margin + lw, y + 1, max(.5, bw * min(1, float(value) / (vmax or 1))), 3.6, "F")
        doc.set_xy(doc.l_margin + lw + bw + 1.5, y)
        doc.cell(tw, 5.5, _clean(text, cmap))
        doc.set_y(y + 6.5)
    doc.set_fill_color(255, 255, 255)
    doc.set_text_color(30, 30, 30)
    doc.ln(4)


def _blocks(md: str):
    """Split Markdown into ("text", ...) and ("table", rows) pieces."""
    lines, buf, i = md.split("\n"), [], 0
    while i < len(lines):
        if lines[i].strip().startswith("|") and i + 1 < len(lines) and re.match(r"^\s*\|?[\s:|-]+\|?\s*$", lines[i + 1]) \
                and "-" in lines[i + 1]:
            if buf:
                yield "text", "\n".join(buf)
                buf = []
            rows = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                if not re.match(r"^\s*\|?[\s:|-]+\|?\s*$", lines[i]):
                    rows.append([c.strip() for c in lines[i].strip().strip("|").split("|")])
                i += 1
            yield "table", rows
        else:
            buf.append(lines[i])
            i += 1
    if buf:
        yield "text", "\n".join(buf)


def _table(doc: FPDF, rows: list[list[str]]) -> None:
    from fpdf.fonts import FontFace
    n = max(len(r) for r in rows)
    rows = [r + [""] * (n - len(r)) for r in rows]
    plain = [[re.sub(r"\*\*|__|\*|`", "", c) for c in r] for r in rows]
    need = [min(max(len(r[j]) for r in plain), 45) + 4 for j in range(n)]
    doc.ln(2)
    doc.set_font("dv", "", 8.5)
    doc.set_draw_color(205, 210, 220)
    doc.set_line_width(0.2)
    with doc.table(col_widths=need, text_align="LEFT", line_height=4.6, padding=1.6, first_row_as_headings=True,
                   headings_style=FontFace(emphasis="BOLD", color=(25, 25, 25), fill_color=(226, 236, 250)),
                   cell_fill_color=(247, 249, 252), cell_fill_mode="ROWS", borders_layout="HORIZONTAL_LINES") as t:
        for r in plain:
            row = t.row()
            for c in r:
                row.cell(c)
    doc.ln(3)


def _styles() -> dict:
    from fpdf.fonts import TextStyle
    return {
        "h2": TextStyle(font_family="dv", font_style="B", font_size_pt=14, color=ACCENT, t_margin=5, b_margin=1),
        "h3": TextStyle(font_family="dv", font_style="B", font_size_pt=12, color=(40, 40, 40), t_margin=5, b_margin=1),
        "h4": TextStyle(font_family="dv", font_style="B", font_size_pt=11, color=(40, 40, 40), t_margin=4, b_margin=1),
        "p": TextStyle(font_family="dv", font_size_pt=10, t_margin=1, b_margin=2),
        "li": TextStyle(font_family="dv", font_size_pt=10, t_margin=1),
    }
