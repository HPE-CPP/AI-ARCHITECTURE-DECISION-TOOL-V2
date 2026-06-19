"""
ArchGuide Technical Report - PDF Generator
Built with ReportLab Platypus for proper text flow and no overlapping.
"""
import re
from pathlib import Path
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm, cm
from reportlab.lib.colors import HexColor, white
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import (
    BaseDocTemplate, PageTemplate, Frame, Paragraph, Spacer, PageBreak,
    Table, TableStyle, KeepTogether, Image, Flowable, ListFlowable, ListItem,
    HRFlowable, NextPageTemplate,
)
from reportlab.platypus.tableofcontents import TableOfContents
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# ── Colour palette ───────────────────────────────────────────────────────────
NAVY      = HexColor("#0d1117")
NAVY_2    = HexColor("#161b22")
INDIGO    = HexColor("#6366f1")
INDIGO_LT = HexColor("#eef2ff")
EMERALD   = HexColor("#10b981")
EMERALD_LT= HexColor("#ecfdf5")
SLATE     = HexColor("#f8fafc")
SLATE_2   = HexColor("#f1f5f9")
BORDER    = HexColor("#e2e8f0")
INK       = HexColor("#0f172a")
INK_2     = HexColor("#1e293b")
MUTED     = HexColor("#64748b")
CODE_BG   = HexColor("#1e1e2e")
CODE_FG   = HexColor("#cdd6f4")
AMBER     = HexColor("#f59e0b")

PAGE_W, PAGE_H = A4
MARGIN_L = 22 * mm
MARGIN_R = 22 * mm
MARGIN_T = 22 * mm
MARGIN_B = 20 * mm

# ── Styles ───────────────────────────────────────────────────────────────────
styles = getSampleStyleSheet()

s_body = ParagraphStyle(
    "Body", parent=styles["Normal"],
    fontName="Helvetica", fontSize=10, leading=15,
    textColor=INK, spaceAfter=4, alignment=TA_JUSTIFY,
)
s_body_left = ParagraphStyle(
    "BodyLeft", parent=s_body, alignment=TA_LEFT,
)
s_h1 = ParagraphStyle(
    "H1", parent=styles["Normal"],
    fontName="Helvetica-Bold", fontSize=18, leading=24,
    textColor=INK, spaceBefore=14, spaceAfter=8,
    leftIndent=8 * mm, borderPadding=(2, 0, 2, 6),
)
s_h2 = ParagraphStyle(
    "H2", parent=styles["Normal"],
    fontName="Helvetica-Bold", fontSize=13, leading=17,
    textColor=INK, spaceBefore=12, spaceAfter=6,
    leftIndent=4 * mm,
    backColor=INDIGO_LT, borderPadding=(5, 5, 5, 8),
)
s_h3 = ParagraphStyle(
    "H3", parent=styles["Normal"],
    fontName="Helvetica-Bold", fontSize=11.5, leading=15,
    textColor=INDIGO, spaceBefore=10, spaceAfter=4,
)
s_h4 = ParagraphStyle(
    "H4", parent=styles["Normal"],
    fontName="Helvetica-Bold", fontSize=10.5, leading=14,
    textColor=INK_2, spaceBefore=8, spaceAfter=3,
)
s_h5 = ParagraphStyle(
    "H5", parent=styles["Normal"],
    fontName="Helvetica-BoldOblique", fontSize=9.5, leading=13,
    textColor=MUTED, spaceBefore=6, spaceAfter=2,
)
s_li = ParagraphStyle(
    "LI", parent=s_body, fontSize=9.5, leading=14,
    leftIndent=14, bulletIndent=4, spaceAfter=2, alignment=TA_LEFT,
)
s_quote = ParagraphStyle(
    "Quote", parent=styles["Normal"],
    fontName="Helvetica-Oblique", fontSize=10, leading=15,
    textColor=HexColor("#0f5132"),
    leftIndent=10, rightIndent=10,
    spaceBefore=6, spaceAfter=8, alignment=TA_LEFT,
    backColor=EMERALD_LT,
    borderPadding=(8, 8, 8, 12),
)
s_code = ParagraphStyle(
    "Code", parent=styles["Normal"],
    fontName="Courier", fontSize=8, leading=11,
    textColor=CODE_FG, backColor=CODE_BG,
    leftIndent=8, rightIndent=8,
    spaceBefore=4, spaceAfter=8,
    borderPadding=(8, 8, 8, 12),
)
s_table_header = ParagraphStyle(
    "TH", fontName="Helvetica-Bold", fontSize=8.5, leading=11,
    textColor=white, alignment=TA_LEFT,
)
s_table_cell = ParagraphStyle(
    "TD", fontName="Helvetica", fontSize=8, leading=11,
    textColor=INK, alignment=TA_LEFT,
)


# ── Inline markdown stripper ─────────────────────────────────────────────────
def inline_md(text):
    """Convert markdown bold/italic/code into ReportLab HTML-like markup."""
    # Escape special chars first
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    # Step 1: Extract backtick spans into placeholders BEFORE bold/italic so
    # that asterisks inside code (e.g. `motion.*`) don't trigger italic regex.
    code_spans: dict[str, str] = {}
    counter = [0]
    def extract_code(m: re.Match) -> str:
        key = f"__CODE_{counter[0]}__"
        code_spans[key] = f'<font face="Courier" color="#5b21b6">{m.group(1)}</font>'
        counter[0] += 1
        return key
    text = re.sub(r"`(.+?)`", extract_code, text)

    # Step 2: Bold and italic — safe now, no bare asterisks from code spans
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"<i>\1</i>", text)

    # Step 3: Restore code spans
    for key, val in code_spans.items():
        text = text.replace(key, val)

    # Strip markdown links to plain text
    text = re.sub(r"\[(.+?)\]\(.+?\)", r"\1", text)
    return text


# ── Custom flowables ─────────────────────────────────────────────────────────
class AccentRule(Flowable):
    """A horizontal rule with two-tone accent."""
    def __init__(self, width=120 * mm, color=INDIGO, thickness=0.6):
        super().__init__()
        self.width = width
        self.color = color
        self.thickness = thickness
        self.height = thickness + 1

    def draw(self):
        self.canv.setStrokeColor(self.color)
        self.canv.setLineWidth(self.thickness)
        self.canv.line(0, 0, self.width, 0)


class H1Box(Flowable):
    """A H1 heading with an accent bar on the left."""
    def __init__(self, text, width=PAGE_W - MARGIN_L - MARGIN_R):
        super().__init__()
        self.text = text
        self.width = width
        self.height = 14 * mm
        self.bar_color = INDIGO

    def wrap(self, available_w, available_h):
        return (self.width, self.height)

    def draw(self):
        # Accent bar
        self.canv.setFillColor(self.bar_color)
        self.canv.rect(0, 0, 5, self.height, fill=1, stroke=0)
        # Text
        self.canv.setFillColor(INK)
        self.canv.setFont("Helvetica-Bold", 18)
        self.canv.drawString(11, self.height / 2 - 3, self.text)


# ── Page templates ───────────────────────────────────────────────────────────
def cover_page(canv, doc):
    canv.saveState()
    # Full background
    canv.setFillColor(NAVY)
    canv.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)
    # Top accent
    canv.setFillColor(INDIGO)
    canv.rect(0, PAGE_H - 4 * mm, PAGE_W, 4 * mm, fill=1, stroke=0)
    # Side stripe
    canv.setFillColor(EMERALD)
    canv.rect(0, PAGE_H - 100 * mm, 6 * mm, 96 * mm, fill=1, stroke=0)

    # Brand name
    canv.setFillColor(white)
    canv.setFont("Helvetica-Bold", 56)
    canv.drawCentredString(PAGE_W / 2, PAGE_H - 100 * mm, "ARCHGUIDE.")

    # Tagline
    canv.setFillColor(INDIGO)
    canv.setFont("Helvetica", 14)
    canv.drawCentredString(PAGE_W / 2, PAGE_H - 115 * mm,
                           "AI Architecture Decision Intelligence Platform")

    # Divider
    canv.setStrokeColor(INDIGO)
    canv.setLineWidth(0.6)
    canv.line(PAGE_W / 2 - 50 * mm, PAGE_H - 122 * mm,
              PAGE_W / 2 + 50 * mm, PAGE_H - 122 * mm)

    # Subtitle
    canv.setFillColor(EMERALD)
    canv.setFont("Helvetica-Bold", 10)
    canv.drawCentredString(PAGE_W / 2, PAGE_H - 132 * mm,
                           "COMPLETE TECHNICAL PROJECT REPORT")

    canv.setFillColor(HexColor("#a0aec0"))
    canv.setFont("Helvetica", 10.5)
    canv.drawCentredString(PAGE_W / 2, PAGE_H - 145 * mm,
                           "System Design  -  Engineering Deep-Dive  -  Architecture Analysis")
    canv.drawCentredString(PAGE_W / 2, PAGE_H - 152 * mm,
                           "Feature Breakdown  -  Tech Stack  -  Mentor Questions")

    # Metadata box
    box_y = 35 * mm
    box_h = 50 * mm
    canv.setFillColor(NAVY_2)
    canv.rect(MARGIN_L, box_y, PAGE_W - 2 * MARGIN_L, box_h, fill=1, stroke=0)
    canv.setFillColor(INDIGO)
    canv.rect(MARGIN_L, box_y, 3, box_h, fill=1, stroke=0)

    canv.setFillColor(INDIGO)
    canv.setFont("Helvetica-Bold", 9)
    canv.drawString(MARGIN_L + 8 * mm, box_y + box_h - 8 * mm, "DOCUMENT METADATA")

    metadata = [
        ("Version", "1.0"),
        ("Classification", "Internal Engineering Documentation"),
        ("Date", "May 2026"),
        ("Platform", "Full-Stack AI  -  FastAPI + Next.js 15"),
    ]
    for i, (k, v) in enumerate(metadata):
        y = box_y + box_h - 18 * mm - i * 7 * mm
        canv.setFillColor(HexColor("#94a3b8"))
        canv.setFont("Helvetica-Bold", 8.5)
        canv.drawString(MARGIN_L + 8 * mm, y, k.upper())
        canv.setFillColor(white)
        canv.setFont("Helvetica", 9.5)
        canv.drawString(MARGIN_L + 45 * mm, y, v)

    # Bottom accent
    canv.setFillColor(EMERALD)
    canv.rect(0, 0, PAGE_W, 4 * mm, fill=1, stroke=0)
    canv.restoreState()


def normal_page(canv, doc):
    """Header + footer for content pages."""
    canv.saveState()
    # Top hairline
    canv.setStrokeColor(BORDER)
    canv.setLineWidth(0.3)
    canv.line(MARGIN_L, PAGE_H - 14 * mm, PAGE_W - MARGIN_R, PAGE_H - 14 * mm)
    # Header text
    canv.setFillColor(MUTED)
    canv.setFont("Helvetica-Bold", 7.5)
    canv.drawString(MARGIN_L, PAGE_H - 11 * mm, "ARCHGUIDE")
    canv.setFont("Helvetica", 7.5)
    canv.drawRightString(PAGE_W - MARGIN_R, PAGE_H - 11 * mm,
                         "Technical Project Report - May 2026")

    # Bottom hairline
    canv.setStrokeColor(BORDER)
    canv.line(MARGIN_L, 13 * mm, PAGE_W - MARGIN_R, 13 * mm)
    # Footer
    canv.setFillColor(MUTED)
    canv.setFont("Helvetica", 8)
    canv.drawCentredString(PAGE_W / 2, 8 * mm, f"{doc.page}")
    canv.setFont("Helvetica", 7)
    canv.drawString(MARGIN_L, 8 * mm, "Confidential")
    canv.drawRightString(PAGE_W - MARGIN_R, 8 * mm, "ArchGuide.")
    canv.restoreState()


def section_break_page(canv, doc, num, title, subtitle):
    canv.saveState()
    canv.setFillColor(NAVY)
    canv.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)
    canv.setFillColor(INDIGO)
    canv.rect(0, 0, 6 * mm, PAGE_H, fill=1, stroke=0)
    canv.setFillColor(EMERALD)
    canv.rect(0, PAGE_H - 60 * mm, 6 * mm, 60 * mm, fill=1, stroke=0)

    canv.setFillColor(INDIGO)
    canv.setFont("Helvetica-Bold", 11)
    canv.drawCentredString(PAGE_W / 2, PAGE_H / 2 + 30 * mm, f"SECTION  {num}")

    canv.setFillColor(white)
    canv.setFont("Helvetica-Bold", 30)
    canv.drawCentredString(PAGE_W / 2, PAGE_H / 2 + 8 * mm, title)

    canv.setFillColor(HexColor("#94a3b8"))
    canv.setFont("Helvetica", 11)
    canv.drawCentredString(PAGE_W / 2, PAGE_H / 2 - 5 * mm, subtitle)

    # Bottom accent
    canv.setFillColor(EMERALD)
    canv.rect(0, 0, PAGE_W, 4 * mm, fill=1, stroke=0)
    canv.restoreState()


# ── Markdown parser ──────────────────────────────────────────────────────────
def parse_markdown(md_text):
    """Yield (type, content) tuples from markdown text."""
    lines = md_text.splitlines()
    i = 0
    while i < len(lines):
        raw = lines[i]
        stripped = raw.strip()

        # Code fence
        if stripped.startswith("```"):
            code_buf = []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith("```"):
                code_buf.append(lines[i])
                i += 1
            yield ("code", "\n".join(code_buf))
            i += 1
            continue

        # Table
        if stripped.startswith("|"):
            table_rows = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                row_text = lines[i].strip()
                cells = [c.strip() for c in row_text.split("|") if c.strip() != ""]
                # Skip separator rows
                if not all(re.match(r"^[-: ]+$", c) for c in cells):
                    table_rows.append(cells)
                i += 1
            if table_rows:
                yield ("table", table_rows)
            continue

        # HR
        if re.match(r"^---+$", stripped):
            yield ("hr", None)
            i += 1
            continue

        # Headings
        h_match = re.match(r"^(#{1,6})\s+(.+)$", raw)
        if h_match:
            level = len(h_match.group(1))
            yield (f"h{level}", h_match.group(2).strip())
            i += 1
            continue

        # List items - collect all consecutive items as a group
        if re.match(r"^[-*]\s+", raw):
            items = []
            while i < len(lines) and re.match(r"^[-*]\s+", lines[i]):
                items.append(re.sub(r"^[-*]\s+", "", lines[i]))
                i += 1
            yield ("ulist", items)
            continue

        # Numbered list
        if re.match(r"^\d+\.\s+", raw):
            items = []
            while i < len(lines) and re.match(r"^\d+\.\s+", lines[i]):
                items.append(re.sub(r"^\d+\.\s+", "", lines[i]))
                i += 1
            yield ("olist", items)
            continue

        # Blockquote
        if stripped.startswith(">"):
            quote_lines = []
            while i < len(lines) and lines[i].strip().startswith(">"):
                quote_lines.append(re.sub(r"^>\s?", "", lines[i].strip()))
                i += 1
            yield ("quote", " ".join(quote_lines))
            continue

        # Paragraph - collect until blank line or special token
        if stripped:
            para_lines = [raw]
            i += 1
            while i < len(lines):
                nxt = lines[i].strip()
                if (not nxt or nxt.startswith("#") or nxt.startswith("```") or
                    nxt.startswith("|") or nxt.startswith(">") or
                    re.match(r"^[-*]\s+", lines[i]) or
                    re.match(r"^\d+\.\s+", lines[i]) or
                    re.match(r"^---+$", nxt)):
                    break
                para_lines.append(lines[i])
                i += 1
            yield ("p", " ".join(para_lines))
            continue

        # Blank line
        i += 1
        yield ("blank", None)


# ── Build flowables from markdown tokens ─────────────────────────────────────
def build_flowables(tokens):
    flowables = []
    section_break_keys = {
        "1. PROJECT OVERVIEW":            ("01", "Project Overview",       "Vision  -  Problem  -  Users  -  Architecture"),
        "2. COMPLETE FEATURE BREAKDOWN":  ("02", "Feature Breakdown",      "13 features explained in full depth"),
        "3. DOCUMENT ANALYSIS":           ("03", "Document Analysis",      "Deep Engineering Whitepaper"),
        "4. TECH STACK ANALYSIS":         ("04", "Tech Stack Analysis",    "Every library, framework and service"),
        "5. SYSTEM DESIGN":               ("05", "System Design",          "Flows  -  Schema  -  Scaling"),
        "6. ENGINEERING CHALLENGES":      ("06", "Engineering Challenges", "Real bugs  -  Root causes  -  Lessons"),
        "7. THOUGHTFUL MENTOR":           ("07", "Mentor Questions",       "15 high-signal questions"),
        "8. GLOSSARY":                    ("08", "Glossary",               "25 terms explained simply"),
        "9. FRONTEND PERFORMANCE":        ("09", "Performance Optimization","From 42 to 95 on Lighthouse"),
    }

    for tok, content in tokens:
        if tok == "blank":
            flowables.append(Spacer(1, 3))
            continue

        if tok == "hr":
            flowables.append(Spacer(1, 2))
            flowables.append(HRFlowable(width="100%", thickness=0.4, color=BORDER))
            flowables.append(Spacer(1, 4))
            continue

        if tok == "h1":
            # Check section break
            upper = content.upper()
            sb = None
            for key, val in section_break_keys.items():
                if key in upper:
                    sb = val
                    break

            if sb:
                num, title, subtitle = sb
                flowables.append(NextPageTemplate("section_break"))
                flowables.append(PageBreak())
                # Store the section meta on a marker flowable
                flowables.append(SectionMarker(num, title, subtitle))
                flowables.append(NextPageTemplate("normal"))
                flowables.append(PageBreak())
            else:
                flowables.append(H1Box(content))
                flowables.append(Spacer(1, 4))
            continue

        if tok == "h2":
            flowables.append(Paragraph(inline_md(content), s_h2))
            continue

        if tok == "h3":
            flowables.append(Spacer(1, 2))
            flowables.append(Paragraph(inline_md(content), s_h3))
            flowables.append(HRFlowable(width=70 * mm, thickness=0.4, color=INDIGO,
                                         spaceAfter=4))
            continue

        if tok == "h4":
            flowables.append(Paragraph(inline_md(content), s_h4))
            continue

        if tok in ("h5", "h6"):
            flowables.append(Paragraph(inline_md(content), s_h5))
            continue

        if tok == "p":
            flowables.append(Paragraph(inline_md(content), s_body_left))
            continue

        if tok == "ulist":
            items = [
                ListItem(Paragraph(inline_md(it), s_li),
                         leftIndent=14, bulletColor=EMERALD)
                for it in content
            ]
            lf = ListFlowable(
                items, bulletType="bullet", bulletFontSize=8,
                bulletColor=EMERALD, leftIndent=18,
            )
            flowables.append(lf)
            flowables.append(Spacer(1, 4))
            continue

        if tok == "olist":
            items = [
                ListItem(Paragraph(inline_md(it), s_li), leftIndent=14)
                for it in content
            ]
            lf = ListFlowable(
                items, bulletType="1", bulletFontSize=9,
                bulletColor=INDIGO, leftIndent=18,
            )
            flowables.append(lf)
            flowables.append(Spacer(1, 4))
            continue

        if tok == "quote":
            flowables.append(Paragraph(inline_md(content), s_quote))
            continue

        if tok == "code":
            # Convert code text to a Preformatted-like rendering using a Table
            # so we get proper background and width control
            code_text = content
            # Escape for Paragraph
            escaped = (code_text
                       .replace("&", "&amp;")
                       .replace("<", "&lt;")
                       .replace(">", "&gt;"))
            # Replace newlines with <br/> for Paragraph
            escaped = escaped.replace("\n", "<br/>")
            # Replace multiple spaces with non-breaking spaces to preserve indentation
            escaped = re.sub(r"  ", "&nbsp;&nbsp;", escaped)
            code_para = Paragraph(escaped, s_code)
            # Wrap in a single-cell Table for the dark background
            tbl = Table([[code_para]], colWidths=[PAGE_W - MARGIN_L - MARGIN_R])
            tbl.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), CODE_BG),
                ("LINEABOVE", (0, 0), (-1, -1), 0, CODE_BG),
                ("LEFTPADDING", (0, 0), (-1, -1), 12),
                ("RIGHTPADDING", (0, 0), (-1, -1), 12),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ("LINEBEFORE", (0, 0), (0, -1), 3, INDIGO),
            ]))
            flowables.append(tbl)
            flowables.append(Spacer(1, 6))
            continue

        if tok == "table":
            rows = content
            if not rows:
                continue
            header = [Paragraph(inline_md(c), s_table_header) for c in rows[0]]
            body_rows = []
            for r in rows[1:]:
                body_rows.append([Paragraph(inline_md(c), s_table_cell) for c in r])
            data = [header] + body_rows
            n_cols = len(rows[0])
            col_w = (PAGE_W - MARGIN_L - MARGIN_R) / n_cols
            tbl = Table(data, colWidths=[col_w] * n_cols, repeatRows=1)
            style = TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), NAVY),
                ("TEXTCOLOR", (0, 0), (-1, 0), white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8.5),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("LINEBELOW", (0, 0), (-1, 0), 0.5, INDIGO),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ])
            # Alternating row backgrounds
            for ri in range(1, len(data)):
                if ri % 2 == 0:
                    style.add("BACKGROUND", (0, ri), (-1, ri), SLATE)
                else:
                    style.add("BACKGROUND", (0, ri), (-1, ri), white)
                style.add("LINEBELOW", (0, ri), (-1, ri), 0.2, BORDER)
            tbl.setStyle(style)
            flowables.append(Spacer(1, 4))
            flowables.append(tbl)
            flowables.append(Spacer(1, 8))
            continue

    return flowables


class SectionMarker(Flowable):
    """Invisible marker that records section info for the page template."""
    def __init__(self, num, title, subtitle):
        super().__init__()
        self.num = num
        self.title = title
        self.subtitle = subtitle
        self.width = 0
        self.height = 0

    def draw(self):
        # Store on canvas so the page template can read it
        self.canv._section_break = (self.num, self.title, self.subtitle)


# ── TOC page (custom drawn) ──────────────────────────────────────────────────
def toc_page(canv, doc):
    canv.saveState()
    canv.setFillColor(SLATE)
    canv.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)
    canv.setFillColor(INDIGO)
    canv.rect(0, PAGE_H - 1.5 * mm, PAGE_W, 1.5 * mm, fill=1, stroke=0)

    # Header
    canv.setFillColor(INDIGO)
    canv.setFont("Helvetica-Bold", 10)
    canv.drawCentredString(PAGE_W / 2, PAGE_H - 30 * mm, "TABLE OF CONTENTS")
    canv.setStrokeColor(INDIGO)
    canv.setLineWidth(0.4)
    canv.line(PAGE_W / 2 - 40 * mm, PAGE_H - 33 * mm,
              PAGE_W / 2 + 40 * mm, PAGE_H - 33 * mm)

    sections = [
        ("01", "Project Overview",          "Vision, problem statement, target users"),
        ("02", "Feature Breakdown",         "13 features explained in full depth"),
        ("03", "Document Analysis",         "12-stage pipeline deep-dive"),
        ("04", "Tech Stack Analysis",       "Every library, framework and service"),
        ("05", "System Design",             "Flows, schema, scaling strategy"),
        ("06", "Engineering Challenges",    "9 real bugs with root causes and fixes"),
        ("07", "Mentor Questions",          "15 high-signal questions"),
        ("08", "Glossary",                  "25 terms explained simply"),
        ("09", "Performance Optimization",  "From 42 to 95 on Lighthouse — 12 optimizations"),
    ]
    y = PAGE_H - 50 * mm
    for num, title, desc in sections:
        # Number badge
        canv.setFillColor(INDIGO)
        canv.roundRect(MARGIN_L + 8 * mm, y - 6, 11 * mm, 11 * mm, 1.5, fill=1, stroke=0)
        canv.setFillColor(white)
        canv.setFont("Helvetica-Bold", 9.5)
        canv.drawCentredString(MARGIN_L + 8 * mm + 5.5 * mm, y - 1, num)

        # Title
        canv.setFillColor(INK)
        canv.setFont("Helvetica-Bold", 12)
        canv.drawString(MARGIN_L + 25 * mm, y + 1, title)

        # Description
        canv.setFillColor(MUTED)
        canv.setFont("Helvetica", 9)
        canv.drawString(MARGIN_L + 25 * mm, y - 5, desc)

        # Dotted leader
        canv.setStrokeColor(BORDER)
        canv.setLineWidth(0.3)
        canv.setDash(1, 2)
        canv.line(MARGIN_L + 110 * mm, y - 2, PAGE_W - MARGIN_R - 5 * mm, y - 2)
        canv.setDash()

        y -= 18 * mm

    # Footer accent
    canv.setFillColor(INDIGO)
    canv.rect(0, 0, PAGE_W, 1.5 * mm, fill=1, stroke=0)
    canv.restoreState()


# ── Custom DocTemplate with section break support ────────────────────────────
class CustomDocTemplate(BaseDocTemplate):
    def __init__(self, filename, **kwargs):
        super().__init__(filename, **kwargs)
        frame_normal = Frame(
            MARGIN_L, MARGIN_B + 5 * mm,
            PAGE_W - MARGIN_L - MARGIN_R,
            PAGE_H - MARGIN_T - MARGIN_B - 10 * mm,
            id="normal_frame",
        )
        frame_section = Frame(
            0, 0, PAGE_W, PAGE_H, id="sb_frame",
            leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0,
        )
        templates = [
            PageTemplate(id="cover", frames=[frame_section], onPage=cover_page),
            PageTemplate(id="toc", frames=[frame_section], onPage=toc_page),
            PageTemplate(id="normal", frames=[frame_normal], onPage=normal_page),
            PageTemplate(id="section_break", frames=[frame_section],
                         onPage=self.section_break_handler),
        ]
        self.addPageTemplates(templates)
        self.pending_section = None

    def section_break_handler(self, canv, doc):
        if self.pending_section:
            num, title, subtitle = self.pending_section
            section_break_page(canv, doc, num, title, subtitle)
            self.pending_section = None

    def afterFlowable(self, flowable):
        if isinstance(flowable, SectionMarker):
            self.pending_section = (flowable.num, flowable.title, flowable.subtitle)


# ── Build ────────────────────────────────────────────────────────────────────
def build():
    md_path = Path("ARCHGUIDE_PROJECT_REPORT.md")
    out_path = Path("ARCHGUIDE_PROJECT_REPORT.pdf")

    doc = CustomDocTemplate(
        str(out_path),
        pagesize=A4,
        leftMargin=MARGIN_L, rightMargin=MARGIN_R,
        topMargin=MARGIN_T, bottomMargin=MARGIN_B,
        title="ArchGuide - Technical Project Report",
        author="ArchGuide Engineering",
    )

    story = []
    # Cover page (just a placeholder that triggers cover template)
    story.append(NextPageTemplate("toc"))
    story.append(PageBreak())
    # TOC page
    story.append(NextPageTemplate("normal"))
    story.append(PageBreak())

    # Now content
    md_text = md_path.read_text(encoding="utf-8")
    tokens = list(parse_markdown(md_text))
    story.extend(build_flowables(tokens))

    doc.build(story)
    size_kb = out_path.stat().st_size // 1024
    print(f"Done: {out_path}  ({size_kb} KB)")


if __name__ == "__main__":
    build()
