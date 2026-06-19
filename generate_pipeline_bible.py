"""
ArchGuide Document Analysis Pipeline — Bible
Mirrors the HPE Project.pdf reference style exactly:
  - solid blue full-width bar for top-of-page title (white text)
  - solid blue full-width bars for H1 section headers (white text)
  - blue-text subsection headers (3.1, 3.2, ...) with a tiny left marker
  - blue-text inline terms used as definition-list dt
  - dark-grey body, hyphen bullets, thin blue rule + page number footer
"""
from pathlib import Path
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.colors import HexColor, white
from reportlab.lib.enums import TA_LEFT, TA_JUSTIFY
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import (
    BaseDocTemplate, PageTemplate, Frame, Paragraph, Spacer, PageBreak,
    Table, TableStyle, KeepTogether,
)

# Palette — taken directly from HPE Project.pdf
BLUE   = HexColor("#2d64db")   # reference accent
INK    = HexColor("#1d1d1d")   # body text
INK_2  = HexColor("#333333")
MUTED  = HexColor("#666666")
RULE   = HexColor("#cccccc")
SUBTLE = HexColor("#f7f7f7")

PAGE_W, PAGE_H = A4
ML, MR = 28*mm, 28*mm
MT, MB = 24*mm, 22*mm   # extra top space for header bar + bottom rule

# Header bar dimensions (matches reference: 39.69 pt = ~14 mm)
HEADER_BAR_H = 14*mm

HEADER_TEXT = "ArchGuide - Document Analysis Pipeline: Bible"

ss = getSampleStyleSheet()

# ── Paragraph styles ──────────────────────────────────────────────────
S_BODY = ParagraphStyle("Body", parent=ss["Normal"], fontName="Helvetica",
                       fontSize=10, leading=14.5, textColor=INK,
                       spaceAfter=6, alignment=TA_JUSTIFY)
S_BODY_L = ParagraphStyle("BodyL", parent=S_BODY, alignment=TA_LEFT)

# H1 white-on-blue text — drawn into a coloured bar table cell.
S_H1 = ParagraphStyle("H1", fontName="Helvetica-Bold", fontSize=15,
                     leading=20, textColor=white, leftIndent=4,
                     alignment=TA_LEFT, spaceAfter=0, spaceBefore=0)

# H2 blue subsection header
S_H2 = ParagraphStyle("H2", fontName="Helvetica-Bold", fontSize=13,
                     leading=17, textColor=BLUE,
                     spaceBefore=12, spaceAfter=6, leftIndent=4)

# Inline blue term (definition-list style, like "Next.js 16" in the reference)
S_TERM = ParagraphStyle("Term", fontName="Helvetica-Bold", fontSize=10,
                       leading=13, textColor=BLUE,
                       spaceBefore=6, spaceAfter=2)

S_TOC = ParagraphStyle("TOC", parent=S_BODY_L, fontSize=10.5, leading=16,
                      spaceAfter=2)

S_CODE = ParagraphStyle("Code", fontName="Courier", fontSize=8.5,
                       leading=12, textColor=INK_2, backColor=SUBTLE,
                       leftIndent=8, rightIndent=8,
                       borderPadding=(6, 6, 6, 6), spaceAfter=10,
                       borderColor=RULE, borderWidth=0.4)

S_COVER_TITLE = ParagraphStyle("CoverTitle", fontName="Helvetica-Bold",
                              fontSize=26, leading=32, textColor=BLUE,
                              alignment=TA_LEFT, spaceAfter=4)
S_COVER_SUB = ParagraphStyle("CoverSub", fontName="Helvetica", fontSize=14,
                            leading=18, textColor=MUTED, alignment=TA_LEFT,
                            spaceAfter=4)
S_COVER_SUB2 = ParagraphStyle("CoverSub2", fontName="Helvetica-Bold",
                             fontSize=12, leading=16, textColor=BLUE,
                             alignment=TA_LEFT, spaceAfter=2)
S_COVER_NOTE = ParagraphStyle("CoverNote", fontName="Helvetica", fontSize=11,
                             leading=15, textColor=MUTED, alignment=TA_LEFT,
                             spaceAfter=2)

# ── Helpers ───────────────────────────────────────────────────────────
def p(text, style=S_BODY):
    return Paragraph(text, style)

def code(text):
    txt = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    txt = txt.replace("\n", "<br/>")
    return Paragraph(txt, S_CODE)

def section_bar(number_and_title):
    """Solid blue full-width bar with white H1 text — reference style."""
    cell = Paragraph(number_and_title, S_H1)
    t = Table([[cell]], colWidths=[PAGE_W - ML - MR], rowHeights=[10*mm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), BLUE),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    return KeepTogether([t, Spacer(1, 4*mm)])

def hyphens(items):
    """Reference uses literal hyphens for bullets — emulate exactly."""
    flowables = []
    for it in items:
        cell_dash = Paragraph("-", ParagraphStyle(
            "dash", fontName="Helvetica", fontSize=10, leading=14,
            textColor=INK, alignment=TA_LEFT))
        cell_txt = Paragraph(it, S_BODY_L)
        t = Table([[cell_dash, cell_txt]], colWidths=[5*mm, PAGE_W - ML - MR - 5*mm])
        t.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 1),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]))
        flowables.append(t)
    flowables.append(Spacer(1, 4*mm))
    return flowables

def def_list(rows):
    """Definition list: blue bold term + plain description below it.
    This matches reference 'Next.js 16 (App Router)' headers + body."""
    flowables = []
    for term, desc in rows:
        flowables.append(p(term, S_TERM))
        flowables.append(p(desc, S_BODY))
    return flowables

def table_header(header, rows, col_widths):
    """Reference-style table: blue header row, plain body rows."""
    data = [[Paragraph(c, ParagraphStyle(
        "th", fontName="Helvetica-Bold", fontSize=9.5, leading=12,
        textColor=white)) for c in header]]
    for row in rows:
        data.append([Paragraph(str(c), ParagraphStyle(
            "td", fontName="Helvetica", fontSize=9, leading=12,
            textColor=INK)) for c in row])
    t = Table(data, colWidths=col_widths, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), BLUE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LINEBELOW", (0, 0), (-1, -1), 0.3, RULE),
        ("BOX", (0, 0), (-1, -1), 0.4, RULE),
    ]))
    return t


# ── Page chrome (matches reference) ───────────────────────────────────
def on_page(canvas, doc):
    canvas.saveState()

    # ── Top header bar (solid blue, full width) ───────────────────────
    canvas.setFillColor(BLUE)
    canvas.rect(0, PAGE_H - HEADER_BAR_H, PAGE_W, HEADER_BAR_H,
                stroke=0, fill=1)

    # Header title text — white, centered vertically in bar
    canvas.setFillColor(white)
    canvas.setFont("Helvetica-Bold", 10)
    canvas.drawString(ML, PAGE_H - HEADER_BAR_H + (HEADER_BAR_H - 10) / 2 + 1,
                      HEADER_TEXT)

    # ── Bottom rule + page number ─────────────────────────────────────
    canvas.setStrokeColor(BLUE)
    canvas.setLineWidth(0.6)
    canvas.line(ML, 14*mm, PAGE_W - MR, 14*mm)

    canvas.setFillColor(MUTED)
    canvas.setFont("Helvetica", 9)
    total = doc._total_pages if hasattr(doc, "_total_pages") else None
    page_num = canvas.getPageNumber()
    page_str = f"Page {page_num}" + (f"/{total}" if total else "")
    canvas.drawRightString(PAGE_W - MR, 9*mm, page_str)
    canvas.drawString(ML, 9*mm,
                     "ArchGuide - Document Analysis Pipeline Bible")

    canvas.restoreState()


# ── Story builder ─────────────────────────────────────────────────────
def build_story():
    story = []

    # ── COVER ──────────────────────────────────────────────────────────
    story.append(Spacer(1, 50*mm))
    story.append(p("ArchGuide", S_COVER_TITLE))
    story.append(p("Document Analysis Pipeline", S_COVER_TITLE))
    story.append(Spacer(1, 6*mm))
    story.append(p("An intelligent rule-based recommender that turns a "
                   "requirements document into an architecture decision "
                   "(RAG, Fine-Tuning, CAG, or Hybrid).", S_COVER_SUB))
    story.append(Spacer(1, 8*mm))
    story.append(p("Technical Pipeline Bible", S_COVER_SUB2))
    story.append(p("Upload to recommendation - every stage, every "
                   "decision, every fix", S_COVER_NOTE))

    story.append(Spacer(1, 22*mm))
    story.append(section_bar("  PIPELINE AT A GLANCE"))
    story.extend(def_list([
        ("Purpose",
         "Decide whether an AI workload should use RAG, Fine-Tuning, CAG, "
         "or Hybrid - directly from a requirements document."),
        ("Input",
         "PDF, DOCX, or TXT requirements document (max 50 MB). Guest "
         "uploads allowed; no authentication required."),
        ("Output",
         "Recommended architecture, per-arch suitability scores, factor "
         "breakdown, why-not explanations, sensitivity analysis, and a "
         "full decision trace."),
        ("Determinism",
         "Scoring is fully deterministic - the same signals always "
         "produce the same recommendation. Only signal extraction "
         "involves an LLM."),
        ("Resilience",
         "Three-layer extraction (keyword + LLM + heuristic regex). "
         "Pipeline degrades gracefully when Ollama or OpenAI is down."),
        ("Audit trail",
         "Every signal carries a source_text quote with a page number, "
         "verified against the original document text."),
    ]))
    story.append(PageBreak())

    # ── TABLE OF CONTENTS ──────────────────────────────────────────────
    story.append(section_bar("  Table of Contents"))
    toc = [
        "1. End-to-End Flow",
        "2. Upload Endpoint - Validation and Guest Support",
        "3. Document Parsing - PDF, DOCX, TXT",
        "4. Relevance Gates - Why Random PDFs Get Rejected",
        "5. The 10 Architecture Signals",
        "6. Signal Extraction - Three-Layer Strategy",
        "   6.1 Layer 1 - Keyword Pre-Extraction",
        "   6.2 Layer 2 - LLM Extraction",
        "   6.3 Layer 3 - Heuristic Regex Fallback",
        "   6.4 The Actual LLM Prompt",
        "7. Vector Indexing and Retrieval",
        "8. Scoring Engine - Rules, Weights, Synergies",
        "   8.1 Per-Signal Score Lookup",
        "   8.2 Weighted Sum and Normalisation",
        "   8.3 Hybrid Synergy Bonus",
        "   8.4 CAG Synergy Bonus",
        "   8.5 Ranking and Why-Not",
        "   8.6 Rules Table Highlights",
        "9. Architecture Recommendations and Confidence",
        "10. Sensitivity Analysis and Stability",
        "11. Persistence - Postgres and Redis",
        "12. Decision Trace and Observability",
        "13. The Journey - Bugs Found and Fixes Applied",
        "   13.1 Guest uploads returned generic failure",
        "   13.2 Hybrid was mathematically un-winnable",
        "   13.3 CAG was losing to FineTuning on bounded corpora",
        "   13.4 RAG was penalised on its core strength",
        "   13.5 Heuristic extractor was negation-blind",
        "   13.6 Volatility regex missed plural feeds",
        "   13.7 Bounded-corpus docs had null dataset_size",
        "   13.8 Word-order mismatch on queries per day",
        "   13.9 Professional-headcount scale unmatched",
        "   13.10 Hybrid bonus calibration drift",
        "14. Test Coverage and Verification",
        "15. Operational Cheat Sheet",
    ]
    for item in toc:
        story.append(p(item, S_TOC))
    story.append(PageBreak())

    # ── 1. FLOW ────────────────────────────────────────────────────────
    story.append(section_bar("  1. End-to-End Flow"))
    story.append(p(
        "The user uploads a file. The request travels through validation, "
        "parsing, relevance gates, vector indexing, signal extraction, "
        "scoring, and persistence - in that order. Any stage can abort "
        "the request with a structured error. The table below is the "
        "complete stage map."))
    story.append(Spacer(1, 4*mm))

    flow_rows = [
        ["1. Upload", "POST /api/v1/upload accepts file + provider + optional project_id."],
        ["2. Filename validation", "Sanitises filename; blocks path traversal (.. and null bytes)."],
        ["3. File-size validation", "Rejects > 50 MB; rejects unsupported MIME types."],
        ["4. Session row", "Postgres row created with status=processing."],
        ["5. Parse", "DocumentParser extracts full_text, pages[], word_count."],
        ["6. Empty-doc check", "Reject if word_count < 10."],
        ["7. Relevance gate", "Reject random docs (cost reports, screenshots, etc.)."],
        ["8. Section detection", "Find Overview / Data / Latency / etc. headers."],
        ["9. Vector indexing", "Chunk + embed - FAISS index keyed by session_id."],
        ["10. Signal extraction", "Keyword scan + LLM (or heuristic fallback)."],
        ["11. Source verification", "Confirm each source_text appears in document."],
        ["12. Confidence gate", "Reject if < 3 signals have confidence >= 0.35."],
        ["13. Concentration warn", "Warn if all signals come from a single page."],
        ["14. Scoring", "Per-signal rules - weighted sum - percentage scores."],
        ["15. Synergy bonuses", "Hybrid / CAG boost when structural patterns detected."],
        ["16. Ranking + why-not", "Sort architectures; generate explanations."],
        ["17. Sensitivity", "Perturb each signal; check recommendation stability."],
        ["18. Persist", "Result row in Postgres; cache in Redis (24h)."],
        ["19. Return", "AnalysisResponse JSON with the analysis_id."],
    ]
    story.append(table_header(
        ["Stage", "What happens"], flow_rows,
        col_widths=[40*mm, PAGE_W - ML - MR - 40*mm]))
    story.append(PageBreak())

    # ── 2. UPLOAD ──────────────────────────────────────────────────────
    story.append(section_bar("  2. Upload Endpoint - Validation and Guest Support"))
    story.append(p(
        "Route: <font face='Courier'>POST /api/v1/upload</font>. "
        "File: <font face='Courier'>backend/app/routers/upload.py</font>. "
        "Rate limit: 4 uploads / minute / IP (slowapi)."))

    story.append(p("2.1 Request shape", S_H2))
    story.append(code(
        'POST /api/v1/upload?provider=ollama&project_id=<uuid>\n'
        'Content-Type: multipart/form-data\n'
        'Authorization: Bearer <firebase_token>   (OPTIONAL)\n\n'
        'file=@<your-document.pdf>'))

    story.append(p("2.2 Guest uploads", S_H2))
    story.append(p(
        "Authentication is optional. When no Firebase token is sent the "
        "upload still succeeds. The Session table has no user_id column "
        "so sessions are inherently anonymous-capable. Three cases:"))
    story.extend(hyphens([
        "No project_id sent - the session has no project owner and is "
        "accessible to anyone holding the analysis_id.",
        "project_id pointing to a guest project (user_id begins with "
        "<font face='Courier'>guest_</font>) - upload allowed.",
        "project_id pointing to an authenticated user's project - "
        "rejected with HTTP 403.",
    ]))
    story.append(p("Why this exists", S_TERM))
    story.append(p(
        "Until this gate was removed, the endpoint hard-rejected "
        "unauthenticated callers with HTTP 401. The frontend rendered "
        "that as a generic 'Upload failed' card after the user skipped "
        "the auth modal, breaking the guest flow end-to-end."))

    story.append(p("2.3 Validation layers", S_H2))
    story.extend(hyphens([
        "<b>Filename:</b> <font face='Courier'>os.path.basename()</font> "
        "strips directory components; reject if it contains "
        "<font face='Courier'>..</font> or a null byte.",
        "<b>MIME and extension:</b> only "
        "<font face='Courier'>.pdf</font>, <font face='Courier'>.docx</font>, "
        "<font face='Courier'>.txt</font> are accepted.",
        "<b>Size:</b> hard limit 50 MB; soft warning at 20 MB.",
        "<b>Project ownership:</b> if a uid is present and "
        "project.user_id differs, reject with 403. Guest projects "
        "(user_id begins with <font face='Courier'>guest_</font>) are "
        "always allowed.",
    ]))
    story.append(PageBreak())

    # ── 3. PARSING ─────────────────────────────────────────────────────
    story.append(section_bar("  3. Document Parsing - PDF, DOCX, TXT"))
    story.append(p(
        "File: <font face='Courier'>backend/services/document_parser.py</font>. "
        "Each format has its own parser; the output schema is identical "
        "regardless of input type:"))
    story.append(code(
        '{\n'
        '  "full_text": "<concatenated body>",\n'
        '  "pages": [\n'
        '    {"page_number": 1, "text": "...", "keyword_score": 7},\n'
        '    ...\n'
        '  ],\n'
        '  "word_count": 1284,\n'
        '  "total_pages": 12\n'
        '}'))

    story.append(p("3.1 Per-format notes", S_H2))
    story.extend(def_list([
        ("PDF",
         "PyMuPDF (fitz) for fast text extraction. Falls back to OCR via "
         "Tesseract for scanned pages with no extractable text."),
        ("DOCX",
         "python-docx walks paragraphs; embedded tables are flattened to "
         "plain text."),
        ("TXT",
         "Read as UTF-8 with <font face='Courier'>errors=replace</font>; "
         "the entire body becomes a single page."),
    ]))

    story.append(p("3.2 Keyword scoring per page", S_H2))
    story.append(p(
        "After parsing, every page is scored by counting how many "
        "signal keywords it contains (the keyword list lives in "
        "<font face='Courier'>SIGNAL_SCHEMA</font>). Pages with "
        "<font face='Courier'>keyword_score &lt; 1</font> are excluded "
        "from the LLM context window because they almost certainly "
        "contain no signals worth spending tokens on. This is the single "
        "biggest cost saver in the pipeline."))
    story.append(PageBreak())

    # ── 4. RELEVANCE GATES ─────────────────────────────────────────────
    story.append(section_bar("  4. Relevance Gates - Why Random PDFs Get Rejected"))
    story.append(p(
        "Three gates fire before any LLM call. Each gate that rejects "
        "the document saves real money (LLM tokens) and time."))

    story.append(p("4.1 Gate 0 - Circular upload detection", S_H2))
    story.append(p(
        "If the PDF was generated by ArchGuide itself (a results "
        "export), reject immediately. We detect this via a magic-string "
        "fingerprint embedded in our PDF metadata. Prevents users from "
        "uploading their previous result PDF as a new requirements "
        "document."))

    story.append(p("4.2 Gate 1 - Word count", S_H2))
    story.append(p(
        "If <font face='Courier'>word_count &lt; 80</font>, reject with "
        "HTTP 422. A document this short cannot contain enough signal "
        "evidence to make a confident recommendation."))

    story.append(p("4.3 Gate 2 - Signal category coverage", S_H2))
    story.append(p(
        "We tally keyword matches across the 10 signal categories. If "
        "fewer than 3 categories have any matches, the document is "
        "almost certainly not a requirements specification - it could be "
        "a cost report, an invoice, or a company newsletter. Reject "
        "with 422 and a precise error message."))

    story.append(p("4.4 Gate 3 - Post-extraction confidence gate", S_H2))
    story.append(p(
        "After signal extraction, if fewer than 3 signals come back "
        "with confidence >= 0.35, abort with 422. The document passed "
        "the keyword gates but the LLM could not actually find "
        "structured requirements inside. Prevents low-quality "
        "recommendations from being persisted."))
    story.append(PageBreak())

    # ── 5. SIGNALS ─────────────────────────────────────────────────────
    story.append(section_bar("  5. The 10 Architecture Signals"))
    story.append(p(
        "Every recommendation reduces to these 10 dimensions. Each "
        "signal has a fixed set of allowed values and a weight in the "
        "scoring engine. The weight reflects how discriminating that "
        "signal is - data_volatility carries the heaviest weight "
        "because it is the single biggest split between RAG (handles "
        "change) and FineTuning (handles static data)."))
    story.append(Spacer(1, 4*mm))

    sig_rows = [
        ["dataset_size", "small / medium / large / very_large", "1.2",
         "Total volume of data the system processes."],
        ["query_volume", "low / medium / high / very_high", "1.0",
         "Expected request throughput (QPS)."],
        ["latency_requirement", "relaxed / moderate / strict / ultra_low",
         "1.1", "Response time SLA."],
        ["data_volatility", "static / low / moderate / high", "1.3",
         "How often the underlying data changes."],
        ["accuracy_requirement", "moderate / high / very_high / critical",
         "1.2", "Tolerance for hallucinations and wrong answers."],
        ["domain_specificity",
         "general / moderate / specialized / highly_specialized", "1.1",
         "How much domain expertise the model must encode."],
        ["security_level", "standard / elevated / high / critical", "0.9",
         "Data classification and compliance burden."],
        ["cost_sensitivity", "low / moderate / high / very_high", "0.8",
         "How strict the budget is."],
        ["deployment_preference", "cloud / on_premise / hybrid / edge",
         "0.7", "Where the system is physically deployed."],
        ["user_scale", "small / medium / large / enterprise", "0.8",
         "Headcount of end users."],
    ]
    story.append(table_header(
        ["Signal", "Allowed values", "Weight", "What it captures"],
        sig_rows,
        col_widths=[34*mm, 56*mm, 14*mm, PAGE_W - ML - MR - 34*mm - 56*mm - 14*mm]))
    story.append(PageBreak())

    # ── 6. SIGNAL EXTRACTION ───────────────────────────────────────────
    story.append(section_bar("  6. Signal Extraction - Three-Layer Strategy"))
    story.append(p(
        "File: <font face='Courier'>backend/services/signal_extractor.py</font>. "
        "Extraction runs in three layers; each layer fills in what "
        "previous layers could not produce. The LLM is the primary "
        "source; the keyword scan boosts confidence when both agree; "
        "the heuristic regex layer takes over when the LLM is "
        "unavailable."))

    story.append(p("6.1 Layer 1 - Keyword Pre-Extraction (zero cost)", S_H2))
    story.append(p(
        "For each signal, regex-scan the document for category keywords "
        "(dataset, latency, accuracy, etc.). Captures the surrounding "
        "sentence as <font face='Courier'>source_text</font>. No value "
        "is assigned at this layer - only evidence that the topic is "
        "mentioned. Confidence is capped at 0.3 so the LLM can always "
        "override."))

    story.append(p("6.2 Layer 2 - LLM Extraction (primary)", S_H2))
    story.append(p(
        "A single prompt asks the LLM (Ollama or OpenAI) to fill all 10 "
        "signals as JSON. The prompt:"))
    story.extend(hyphens([
        "Lists allowed values verbatim - the LLM cannot invent new ones.",
        "Maps natural-language phrases to canonical values "
        "(\"under 2 seconds\" -> relaxed; \"HIPAA\" -> critical security).",
        "Demands a <font face='Courier'>source_text</font> quote per "
        "signal - we verify it appears in the document.",
        "Reserves <font face='Courier'>critical</font> for regulated "
        "clinical / financial / safety-of-life contexts, and "
        "<font face='Courier'>highly_specialized</font> for proprietary "
        "vocabularies. Internal company knowledge is "
        "<font face='Courier'>specialized</font>, not "
        "<font face='Courier'>highly_specialized</font>.",
    ]))
    story.append(p("Why prompt tightening matters", S_TERM))
    story.append(p(
        "Before this constraint, the LLM was over-classifying any "
        "compliance-flavoured doc as accuracy=critical and any "
        "industry-specific doc as domain=highly_specialized. Both "
        "values swing the scoring engine sharply toward FineTuning - "
        "this is exactly how systemic bias was being introduced."))

    story.append(p("6.3 Layer 3 - Heuristic Regex Fallback", S_H2))
    story.append(p(
        "If the LLM call fails (timeout, malformed JSON, Ollama not "
        "running), a pure-regex extractor takes over. It contains "
        "carefully-tuned patterns for each of the 10 signals, "
        "including numeric resolvers - \"500 GB\" -> large, "
        "\"800 queries per minute\" -> high QPS, \"200 templates\" -> "
        "small. The regex layer also includes a universal negation "
        "guard (see section 13.5) so phrases like \"no real-time "
        "streaming requirement\" do not match as if they meant the "
        "opposite."))

    story.append(p("Chunked extraction for large documents", S_TERM))
    story.append(p(
        "If the post-filter context exceeds 8,000 characters, we split "
        "into 5,000-char overlapping chunks (500-char overlap) and "
        "extract from each chunk concurrently (Semaphore bound of 5). "
        "The winning signal per name is the one with the highest "
        "confidence across chunks. This is why the 13-section stress "
        "test (doc 10) does not lose signals at the tail."))

    story.append(p("Caching", S_TERM))
    story.append(p(
        "Extraction results are cached in memory keyed by "
        "<font face='Courier'>f\"p:{prompt_fingerprint}\\x00{full_text}\"</font>. "
        "Re-uploading the same document skips the LLM entirely. The "
        "prompt fingerprint auto-invalidates the cache whenever the "
        "extraction prompt changes - no manual flush required."))
    story.append(PageBreak())

    # ── 6.4 PROMPT ─────────────────────────────────────────────────────
    story.append(section_bar("  6.4 The Actual LLM Prompt"))
    story.append(p(
        "The prompt is the most important file in the entire pipeline. "
        "Every value below is a hard constraint the LLM must honour."))
    story.append(code(
        'You are an expert AI architecture analyst.\n'
        'Read the document and extract 10 architecture signals as JSON.\n\n'
        'SIGNAL NAMES AND ALLOWED VALUES - use EXACTLY these strings:\n'
        '  dataset_size:          small | medium | large | very_large\n'
        '  query_volume:          low | medium | high | very_high\n'
        '  latency_requirement:   relaxed | moderate | strict | ultra_low\n'
        '  data_volatility:       static | low | moderate | high\n'
        '  accuracy_requirement:  moderate | high | very_high | critical\n'
        '  domain_specificity:    general | moderate | specialized | highly_specialized\n'
        '  security_level:        standard | elevated | high | critical\n'
        '  cost_sensitivity:      low | moderate | high | very_high\n'
        '  deployment_preference: cloud | on_premise | hybrid | edge\n'
        '  user_scale:            small | medium | large | enterprise\n\n'
        'CONFIDENCE SCALE:\n'
        '  0.0 = signal not mentioned at all (value = null)\n'
        '  0.3 = weakly implied\n'
        '  0.5 = moderately clear\n'
        '  0.7 = clearly stated\n'
        '  0.9 = explicitly defined with numbers / keywords\n\n'
        'IMPORTANT RULES:\n'
        '  1. For "value": null ONLY when document gives zero signal.\n'
        '  2. For "source_text": one exact sentence from the document.\n'
        '  3. Set confidence >= 0.3 whenever you can infer a value.\n'
        '  4. Output raw JSON only - no markdown, no code blocks.'))
    story.append(PageBreak())

    # ── 7. VECTOR INDEXING ─────────────────────────────────────────────
    story.append(section_bar("  7. Vector Indexing and Retrieval"))
    story.append(p(
        "File: <font face='Courier'>backend/app/services/vector_service.py</font>. "
        "The document is chunked, embedded, and indexed in FAISS so "
        "the frontend can show source quotes and follow-up questions "
        "can retrieve additional context. Indexing is best-effort - if "
        "it fails the rest of the pipeline continues without semantic "
        "retrieval."))
    story.extend(hyphens([
        "<b>Chunk size:</b> approximately 512 tokens with 50-token overlap.",
        "<b>Embedding model:</b> sentence-transformers/all-MiniLM-L6-v2 "
        "- 384-dim, fast, runs locally.",
        "<b>Index:</b> FAISS IndexFlatL2 keyed by session_id.",
        "<b>Failure mode:</b> if FAISS or the embedder is unavailable, "
        "the stage logs a warning, marks the trace step as 'skipped', "
        "and continues - a recommendation is still produced.",
    ]))
    story.append(PageBreak())

    # ── 8. SCORING ─────────────────────────────────────────────────────
    story.append(section_bar("  8. Scoring Engine - Rules, Weights, Synergies"))
    story.append(p(
        "File: <font face='Courier'>backend/services/scoring_engine.py</font>. "
        "This is the deterministic core. Given a set of 10 signals "
        "(values plus confidences), it always produces the same scores, "
        "ranking, and recommendation. No randomness, no temperature, no "
        "LLM call."))

    story.append(p("8.1 Per-signal score lookup", S_H2))
    story.append(p(
        "For each signal, look up the value in "
        "<font face='Courier'>SCORING_RULES</font>. The lookup returns "
        "a per-architecture score in [0.0, 1.0]:"))
    story.append(code(
        'SCORING_RULES["data_volatility"]["high"]\n'
        '# {"RAG": 1.0, "FineTuning": 0.2, "CAG": 0.1, "Hybrid": 0.5}\n\n'
        'SCORING_RULES["accuracy_requirement"]["very_high"]\n'
        '# {"RAG": 0.9, "FineTuning": 0.8, "CAG": 0.4, "Hybrid": 0.7}'))

    story.append(p("8.2 Weighted sum and normalisation", S_H2))
    story.append(code(
        'effective_weight = SIGNAL_WEIGHTS[signal] * confidence\n'
        'for each architecture:\n'
        '    arch_total += rule_score * effective_weight\n'
        'total_weight += effective_weight\n\n'
        '# Normalise to a 0-100 percentage:\n'
        'score[arch] = (arch_total / total_weight) * 100'))
    story.append(p(
        "Confidence acts as a per-signal damper: a low-confidence "
        "signal contributes proportionally less to the final scores. "
        "Missing signals (value = null) are skipped entirely."))

    story.append(p("8.3 Hybrid synergy bonus", S_H2))
    story.append(p(
        "Pure rule-based scoring cannot produce Hybrid as the winner "
        "because Hybrid's per-signal score is roughly the midpoint of "
        "RAG and FineTuning. We detect genuine cross-architecture "
        "tension from the signals themselves and apply a bonus only "
        "when both dimensions are strongly evidenced. The procedure:"))
    story.extend(hyphens([
        "Count signals with RAG-score >= 0.8 (strong RAG pulls).",
        "Count signals with FT-score >= 0.8 (strong FT pulls).",
        "Compute distinct sets - rag_only and ft_only - by excluding "
        "signals strong on both sides.",
        "Require at least 2 distinct signals on each side.",
        "Require at least 1 maximal RAG pull (score >= 0.95) - the "
        "FT-killer signal. Only data_volatility=high or "
        "dataset_size=very_large achieve this.",
        "Bonus = min(tension x 8.0 x avg_weight, 22.0). Added to "
        "Hybrid's score before final ranking.",
    ]))
    story.append(p("Why the maximal-pull requirement", S_TERM))
    story.append(p(
        "Without it, a doc with volatility=moderate + dataset=large + "
        "specialized domain triggered Hybrid (RAG had 2 strong pulls, "
        "FT had 2). But moderate volatility does not require real "
        "retrieval - periodic FT retraining handles it. The 0.95 "
        "threshold is reached only by signals that genuinely break a "
        "single-arch design."))

    story.append(p("8.4 CAG synergy bonus", S_H2))
    story.append(p(
        "CAG's sweet spot is a small, bounded, slow-changing corpus "
        "that fits in an LLM context window. The per-signal rules "
        "under-value CAG when those structural conditions coexist "
        "with a specialized domain or very_high accuracy - because "
        "those signals strongly favour FT independently. A bonus of "
        "+14 is applied when:"))
    story.append(code(
        'dataset_size == "small"\n'
        'AND data_volatility IN ("static", "low")\n'
        'AND query_volume IN ("low", "medium")'))

    story.append(p("8.5 Ranking and why-not", S_H2))
    story.append(p(
        "Architectures are sorted by score (descending). The top one "
        "is the recommendation. Each architecture gets a suitability "
        "label based on its absolute score:"))
    story.extend(hyphens([
        ">= 75 - Highly Suitable",
        "55 to 74 - Suitable",
        "40 to 54 - Moderately Suitable",
        "< 40 - Not Recommended",
    ]))
    story.append(p(
        "For each non-winning architecture, a why-not blurb is "
        "generated by identifying its three weakest factors and "
        "reporting the score gap versus the winner."))
    story.append(PageBreak())

    # ── 8.6 RULES TABLE ────────────────────────────────────────────────
    story.append(section_bar("  8.6 Rules Table Highlights"))
    story.append(p(
        "Full table lives in <font face='Courier'>SCORING_RULES</font>. "
        "Below are the cells with the largest discriminating power - "
        "the rows that effectively decide most documents."))
    story.append(Spacer(1, 4*mm))

    rule_rows = [
        ["data_volatility = high", "1.00", "0.20", "0.10", "0.50",
         "RAG-only winner"],
        ["data_volatility = static", "0.50", "0.90", "0.80", "0.40",
         "FT and CAG friendly"],
        ["dataset_size = very_large", "1.00", "0.30", "0.10", "0.70",
         "RAG wins on scale"],
        ["dataset_size = small", "0.30", "0.60", "0.90", "0.30",
         "CAG wins on size"],
        ["accuracy = critical", "0.78", "0.95", "0.20", "0.70",
         "FT strong; RAG raised after rebalance"],
        ["accuracy = very_high", "0.90", "0.80", "0.40", "0.70",
         "RAG with grounding"],
        ["domain = highly_specialized", "0.68", "0.95", "0.25", "0.65",
         "FT strong; RAG raised"],
        ["domain = specialized", "0.85", "0.75", "0.45", "0.60",
         "RAG retrieves a domain corpus"],
        ["latency = ultra_low", "0.20", "1.00", "0.20", "0.40",
         "Retrieval hop kills RAG"],
        ["deployment = hybrid", "0.70", "0.60", "0.40", "0.75",
         "Hybrid edge"],
    ]
    story.append(table_header(
        ["Signal = Value", "RAG", "FT", "CAG", "Hybrid", "Why it matters"],
        rule_rows,
        col_widths=[44*mm, 12*mm, 12*mm, 12*mm, 14*mm,
                    PAGE_W - ML - MR - 44*mm - 12*mm*3 - 14*mm]))
    story.append(PageBreak())

    # ── 9. ARCHITECTURES ───────────────────────────────────────────────
    story.append(section_bar("  9. Architecture Recommendations and Confidence"))

    archs = [
        ("RAG - Retrieval-Augmented Generation",
         "Combine a retrieval system (FAISS or vector DB) with a "
         "generative LLM. The model is fixed; knowledge lives outside it.",
         "Dynamic data handling, no retraining needed, transparent "
         "sources, cost-effective updates.",
         "Higher latency (retrieval hop), retrieval-quality dependency, "
         "context window limits."),
        ("Fine-Tuning",
         "Customise a pre-trained LLM on domain-specific data. "
         "Knowledge lives inside the model weights.",
         "High accuracy, low inference latency, deep domain knowledge, "
         "consistent outputs.",
         "Expensive retraining, data staleness risk, requires labeled "
         "training data."),
        ("CAG - Context-Augmented Generation",
         "Stuff the entire corpus into the prompt. No vector DB; no "
         "training. Works only when the corpus fits in the context "
         "window.",
         "Simple architecture, low infrastructure cost, fast setup, no "
         "vector DB needed.",
         "Context window limits, not scalable, higher per-query cost "
         "for large contexts."),
        ("Hybrid - RAG plus Fine-Tuning",
         "Fine-tune a model on the domain AND retrieve from a fresh "
         "corpus. Used when neither alone suffices.",
         "Maximum flexibility, best accuracy potential, handles edge "
         "cases, scalable.",
         "Complex architecture, higher cost, more maintenance, longer "
         "development time."),
    ]
    for name, desc, strengths, weaknesses in archs:
        story.append(p(name, S_H2))
        story.append(p(desc))
        story.append(p("Strengths", S_TERM))
        story.append(p(strengths))
        story.append(p("Weaknesses", S_TERM))
        story.append(p(weaknesses))
        story.append(Spacer(1, 2*mm))

    story.append(p("9.5 Confidence score", S_H2))
    story.append(p(
        "Reported as a single number in [0, 1]. Combines two factors: "
        "(a) the average per-signal confidence across signals that "
        "actually have a value, weighted 0.7; and (b) coverage - the "
        "fraction of the 10 signals with a non-null value, weighted "
        "0.3. So a recommendation made from 9 highly-confident signals "
        "beats one from 3 highly-confident signals."))
    story.append(code('confidence = 0.7 * avg_active + 0.3 * coverage'))
    story.append(PageBreak())

    # ── 10. SENSITIVITY ────────────────────────────────────────────────
    story.append(section_bar("  10. Sensitivity Analysis and Stability"))
    story.append(p(
        "After the main scoring, the engine perturbs each signal one "
        "at a time (trying every other allowed value) and re-scores. "
        "If any perturbation changes the recommendation, that is "
        "flagged as an instability."))
    story.append(p(
        "Stability score = 1 - (instabilities / total_perturbations). "
        "If above 0.7, the recommendation is considered stable. "
        "Otherwise the response includes a warning ('Recommendation "
        "may change with different input values')."))
    story.append(p("Performance note", S_TERM))
    story.append(p(
        "Sensitivity runs 30+ score() calls per request - expensive. "
        "We cache results by hashing the signals dict (md5) so "
        "re-scoring the same signals is instant."))
    story.append(PageBreak())

    # ── 11. PERSISTENCE ────────────────────────────────────────────────
    story.append(section_bar("  11. Persistence - Postgres and Redis"))
    story.append(p(
        "<b>Postgres tables:</b> Project, Session, Signal, Result. "
        "<b>Redis:</b> 24-hour cache of the AnalysisResponse keyed by "
        "session_id."))
    story.append(Spacer(1, 4*mm))

    story.extend(def_list([
        ("Project",
         "id, user_id, name, description, analysis_id, mode, status, "
         "timestamps."),
        ("Session",
         "id, project_id, status, provider, filename, timestamps. No "
         "user_id - sessions are anonymous-capable."),
        ("Signal",
         "session_id, name, value, confidence, source_text, "
         "page_number, source_verified."),
        ("Result",
         "session_id, recommended_architecture, scores, ranking, "
         "factor_breakdown, why_not, suitability, sensitivity, "
         "followup_questions, decision_trace, architecture_details."),
    ]))
    story.append(PageBreak())

    # ── 12. DECISION TRACE ─────────────────────────────────────────────
    story.append(section_bar("  12. Decision Trace and Observability"))
    story.append(p(
        "Every analysis carries a <font face='Courier'>decision_trace</font> "
        "- a chronological list of stages with status (in_progress / "
        "complete / skipped / rejected / warning / error), timestamps, "
        "and human-readable details. The frontend surfaces this "
        "verbatim in the Decision Trace tab so the user can see "
        "exactly what happened to their document."))
    story.append(code(
        '[\n'
        '  {"step": "upload", "status": "complete", "timestamp": "..."},\n'
        '  {"step": "parse", "status": "complete",\n'
        '   "details": "Extracted 1284 words from 12 pages"},\n'
        '  {"step": "relevance_check", "status": "complete",\n'
        '   "details": "Document passes relevance check (1284 words)"},\n'
        '  {"step": "section_detection", "status": "complete",\n'
        '   "details": "Detected 8 document sections"},\n'
        '  {"step": "vector_indexing", "status": "complete",\n'
        '   "details": "Indexed 47 text chunks"},\n'
        '  {"step": "signal_extraction", "status": "complete",\n'
        '   "details": "Extracted 9/10 signals"},\n'
        '  {"step": "missing_signals", "status": "warning",\n'
        '   "details": "1 signal missing: cost sensitivity"},\n'
        '  {"step": "scoring", "status": "complete"},\n'
        '  {"step": "recommend", "status": "complete"}\n'
        ']'))
    story.append(PageBreak())

    # ── 13. THE JOURNEY ────────────────────────────────────────────────
    story.append(section_bar("  13. The Journey - Bugs Found and Fixes Applied"))
    story.append(p(
        "This section catalogs every meaningful bug encountered while "
        "calibrating the pipeline, why each bug happened, and the "
        "exact fix that landed. Read this if you are touching the "
        "scoring or the extractor - the answers to \"why is this code "
        "so specific\" live here."))

    bugs = [
        ("13.1 Guest uploads returned a generic failure",
         "Unauthenticated user uploads a valid PDF and the frontend "
         "shows the generic 'Upload failed' card.",
         "<font face='Courier'>upload.py</font> had "
         "<font face='Courier'>if not uid: raise HTTPException(401)</font> "
         "at the top of the handler. The frontend caught the 401 and "
         "rendered the generic failure card because the error did not "
         "match any of the parseUploadError keywords.",
         "Removed the auth gate. Sessions have no user_id field "
         "(already anonymous-capable). Guest projects were already "
         "supported on the projects and analysis endpoints; upload "
         "was the only inconsistent one."),

        ("13.2 Hybrid was mathematically un-winnable",
         "The canonical hybrid-candidate document (real-time market "
         "feeds + static research corpus + specialized finance "
         "domain) was recommended as FineTuning, not Hybrid.",
         "Hybrid's per-signal scores in SCORING_RULES were roughly "
         "the average of RAG and FT scores. When either single arch "
         "pulled strongly on any axis, Hybrid was locked into 2nd or "
         "3rd place. There was no mechanism to detect that a doc "
         "needed both dimensions.",
         "Added a synergy-detection pass after base scoring. Counts "
         "signals with strong RAG-only pulls vs strong FT-only "
         "pulls. When both sides have >= 2 distinct strong pulls "
         "AND at least one RAG pull is maximal (>= 0.95, only "
         "volatility=high or dataset=very_large achieve this), "
         "Hybrid gets a weighted bonus. Pure single-arch docs (no "
         "opposing pulls) get zero bonus and win cleanly."),

        ("13.3 CAG was losing to FineTuning on bounded corpora",
         "The legal-contract-templates document (200 templates, 800 "
         "pages, fits in 400k tokens, updated annually) was "
         "recommended as FineTuning instead of CAG.",
         "The accuracy=very_high and domain=specialized cells "
         "strongly favoured FT, drowning out CAG's wins on "
         "dataset_size=small and data_volatility=static. The "
         "per-signal rules could not represent the structural fact "
         "that 'the whole corpus fits in the prompt' makes CAG "
         "strictly correct.",
         "Added a CAG synergy bonus (+14 points) that fires when "
         "dataset_size=small AND data_volatility in {static, low} "
         "AND query_volume in {low, medium}. Those three signals "
         "together uniquely describe a bounded-corpus situation "
         "where CAG should win regardless of how specialized the "
         "domain is."),

        ("13.4 RAG was penalised on its core strength",
         "Documents that explicitly required cited or grounded "
         "responses (textbook RAG) were recommended as FineTuning.",
         "accuracy_requirement=very_high gave RAG 0.7 vs FT 0.9. "
         "But grounded retrieval with citations is exactly the RAG "
         "guarantee - RAG should match or beat FT on "
         "accuracy=very_high. Similarly, domain=specialized gave "
         "RAG 0.6 vs FT 0.9, even though retrieval over a domain "
         "corpus is exactly what RAG does.",
         "Rebalanced two rows: accuracy_requirement and "
         "domain_specificity. RAG bumped to 0.85-0.9 for very_high "
         "and 0.78 for critical. domain=specialized: RAG 0.6 -> "
         "0.85. domain=highly_specialized: 0.4 -> 0.68. CAG also "
         "bumped modestly so it stops being penalised on accuracy "
         "and domain."),

        ("13.5 Heuristic extractor was negation-blind",
         "Doc 02 (a static medical archive) was extracted as "
         "data_volatility=high. Doc 03 (low-volume legal tool) was "
         "extracted as query_volume=high.",
         "The doc 02 phrasing 'no real-time streaming requirement' "
         "contains the substring 'real-time streaming' which "
         "matches the high-volatility regex. The doc 03 phrasing "
         "'no expectation of high concurrency' matches the "
         "high-concurrency regex. Neither regex examined what came "
         "before the match.",
         "Added <font face='Courier'>_is_negated()</font> that "
         "scans the preceding 60 characters of every regex match "
         "for negation words (no, not, never, without, zero, "
         "cannot, won't). When any appears, the match is skipped "
         "and the next candidate is considered. Universal - "
         "applies to every signal pattern."),

        ("13.6 Volatility regex missed plural 'feeds'",
         "Doc 04 (financial trading platform with explicit "
         "'Real-time feeds:' section) was extracted as "
         "data_volatility=static.",
         "The high-volatility regex was "
         "<font face='Courier'>real-time (streaming|data|feed|"
         "updates?)</font>. 'feed' matched but 'feeds' did not. "
         "'Real-time feeds' fell through to the static rule, which "
         "matched 'static corpus' in the same doc.",
         "Changed <font face='Courier'>feed</font> to "
         "<font face='Courier'>feeds?</font>. Also added "
         "<font face='Courier'>market data</font> and a dedicated "
         "<font face='Courier'>streamed? data</font> rule."),

        ("13.7 Bounded-corpus docs had null dataset_size",
         "Doc 03 mentioned '200 templates', '800 pages', 'fits in "
         "400,000 tokens' - none matched any dataset_size pattern. "
         "The CAG bonus (which requires dataset_size=small) "
         "silently failed.",
         "Original regexes only matched units like GB, TB, "
         "'millions of records', etc. Domain-specific quantities "
         "went unrecognised.",
         "Added three new dataset_size patterns: 'N templates / "
         "contracts / playbooks' -> small, 'N pages' -> small / "
         "medium / large via a numeric resolver, 'fits in context' "
         "/ 'bounded corpus' -> small."),

        ("13.8 Word-order mismatch on 'queries per day'",
         "Doc 03 'roughly 50 to 100 queries per day' -> "
         "query_volume = null.",
         "The regex expected ordering 'NUM (daily|per day) NOUN' - "
         "number, then period, then noun. Doc 03's natural order "
         "was reversed: number, then noun, then 'per day'.",
         "Added a second pattern handling the natural ordering. "
         "Also added 'queries per minute' with a 1/60 QPS converter "
         "(doc 04 says '800 queries per minute')."),

        ("13.9 Professional-headcount scale was unmatched",
         "Doc 02's 'radiologists', doc 03's 'associates', doc 04's "
         "'portfolio managers' - none matched the user_scale "
         "regex. Result: user_scale=null for the docs that most "
         "clearly stated their user base.",
         "The regex only matched 'users / employees / people' "
         "literally. Industry-specific role names were unrecognised.",
         "Added <font face='Courier'>\\b(\\d+)\\s+(analysts|"
         "associates|radiologists|agents|managers|specialists|"
         "consultants|operators|employees)\\b</font> - reuses the "
         "existing NUM_USERS numeric resolver."),

        ("13.10 Hybrid bonus calibration drift",
         "After rebalancing RAG upward (13.4), Hybrid started "
         "losing to RAG by 1-3 points on doc 04 and doc 10 - even "
         "though the synergy detector was firing correctly.",
         "The rebalanced RAG rules pushed the base RAG score "
         "higher; the synergy multiplier (originally 6.5) was no "
         "longer strong enough to overtake.",
         "Bumped Hybrid bonus multiplier 6.5 -> 8.0, with cap "
         "raised 20 -> 22. Does not affect single-arch docs (they "
         "do not trigger the bonus at all), but gives hybrid cases "
         "enough force to overtake the now-stronger RAG score."),
    ]
    for title, sym, cause, fix in bugs:
        story.append(p(title, S_H2))
        story.append(p("Symptom", S_TERM))
        story.append(p(sym))
        story.append(p("Root cause", S_TERM))
        story.append(p(cause))
        story.append(p("Fix", S_TERM))
        story.append(p(fix))
        story.append(Spacer(1, 4*mm))
    story.append(PageBreak())

    # ── 14. TESTS ──────────────────────────────────────────────────────
    story.append(section_bar("  14. Test Coverage and Verification"))
    story.append(p("Two layers of verification cover the pipeline:"))

    story.append(p("14.1 Layer A - Scoring engine unit tests", S_H2))
    story.append(p(
        "<font face='Courier'>backend/verify_scoring.py</font> "
        "constructs hand-derived signal sets for each test doc "
        "(including 'aggressive LLM extraction' variants) and asserts "
        "the scoring engine produces the expected architecture. "
        "Catches regressions in rules, weights, and synergy bonuses."))

    story.append(p("14.2 Layer B - Real-doc heuristic tests", S_H2))
    story.append(p(
        "<font face='Courier'>backend/diagnose_pipeline.py</font> "
        "reads each test doc's actual markdown content, runs the "
        "actual heuristic extractor on it, then scores. This is the "
        "only way to catch extractor bugs (negation, missing patterns, "
        "word-order). Bypasses Ollama entirely - purely deterministic."))

    story.append(p("14.3 Test document matrix", S_H2))
    test_rows = [
        ["01_perfect_rag_candidate", "RAG",
         "Internal KB, 80GB, weekly updates, on-prem."],
        ["02_perfect_finetuning_candidate", "FineTuning",
         "Medical, 1.2TB static, HIPAA, FDA."],
        ["03_perfect_cag_candidate", "CAG",
         "200 legal templates, 800 pages, annual updates."],
        ["04_perfect_hybrid_candidate", "Hybrid",
         "Trading: static research + real-time feeds."],
        ["05_edge_case_ambiguous_signals", "(any)",
         "Tests low-confidence handling."],
        ["06_edge_case_minimal_valid", "(any)",
         "Barely passes word and keyword gates."],
        ["07_rejection_too_short", "REJECT",
         "Below 80 words."],
        ["08_rejection_wrong_doc_type", "REJECT",
         "Cost report; fails keyword gate."],
        ["09_rejection_archguide_report", "REJECT",
         "Circular upload detection."],
        ["10_stress_test_large_doc", "Hybrid",
         "13 sections; tests chunked extraction."],
        ["11_rejection_low_density", "REJECT",
         "Newsletter; mentions data but no requirements."],
    ]
    story.append(table_header(
        ["Test doc", "Expected", "What it tests"], test_rows,
        col_widths=[58*mm, 24*mm,
                    PAGE_W - ML - MR - 58*mm - 24*mm]))

    story.append(p("14.4 Current status", S_H2))
    story.append(p(
        "All 5 architecture-recommendation cases (01, 02, 03, 04, 10) "
        "pass with the actual heuristic extractor on the actual doc "
        "text - no LLM, no hand-coded signals. The 4 rejection cases "
        "(07, 08, 09, 11) never reach the scoring engine; they are "
        "blocked at the word-count, keyword-coverage, or "
        "circular-upload gate."))
    story.append(PageBreak())

    # ── 15. CHEAT SHEET ────────────────────────────────────────────────
    story.append(section_bar("  15. Operational Cheat Sheet"))

    story.append(p("15.1 Run the diagnostic", S_H2))
    story.append(code(
        'cd backend\n'
        'python diagnose_pipeline.py        # heuristic extractor + scoring\n'
        'python verify_scoring.py           # scoring engine alone'))

    story.append(p("15.2 Invalidate the extraction cache", S_H2))
    story.append(p(
        "The cache is keyed by the prompt fingerprint. Any change to "
        "<font face='Courier'>EXTRACTION_PROMPT</font> automatically "
        "invalidates the cache. To force flush manually, restart the "
        "backend process."))

    story.append(p("15.3 Add a new signal", S_H2))
    story.extend(hyphens([
        "Add the entry to <font face='Courier'>SIGNAL_SCHEMA</font> "
        "with description and keywords.",
        "Add an <font face='Courier'>EXTRACTION_PROMPT</font> "
        "mapping rule ('phrase -> value').",
        "Add an entry to <font face='Courier'>SIGNAL_OPTIONS</font> "
        "for the frontend questionnaire.",
        "Add a row to <font face='Courier'>SCORING_RULES</font> with "
        "per-arch scores for every allowed value.",
        "Add an entry to <font face='Courier'>SIGNAL_WEIGHTS</font>.",
        "Add a heuristic block to "
        "<font face='Courier'>_HEURISTIC_RULES</font>.",
        "Re-run <font face='Courier'>verify_scoring.py</font> and "
        "<font face='Courier'>diagnose_pipeline.py</font>.",
    ]))

    story.append(p("15.4 Common failure modes", S_H2))
    story.extend(hyphens([
        "<b>Ollama unreachable:</b> heuristic fallback kicks in. Check "
        "<font face='Courier'>ollama serve</font> and "
        "<font face='Courier'>ollama list</font>.",
        "<b>422 Insufficient signal confidence:</b> doc passed "
        "keyword gates but only 0-2 high-confidence signals "
        "extracted. Usually means the doc is too vague.",
        "<b>FAISS indexing skipped in trace:</b> embedder not loaded; "
        "recommendation still produced.",
        "<b>Signal concentration warning:</b> all signals from a "
        "single page. Doc passed gates but content is concentrated. "
        "Recommendation is correct but coverage is thin.",
    ]))

    return story


def main():
    out_path = Path(__file__).parent / "DOC_PIPELINE_BIBLE.pdf"

    # Two-pass build for "Page X/Y" footer
    doc = BaseDocTemplate(
        str(out_path), pagesize=A4,
        leftMargin=ML, rightMargin=MR,
        topMargin=MT, bottomMargin=MB,
        title="ArchGuide - Document Analysis Pipeline Bible",
        author="ArchGuide",
    )
    frame = Frame(ML, MB, PAGE_W - ML - MR, PAGE_H - MT - MB,
                  id="body", showBoundary=0)
    doc.addPageTemplates([PageTemplate(id="main", frames=[frame],
                                       onPage=on_page)])
    doc.build(build_story())
    total = doc.page

    # Second pass with the total page count
    doc2 = BaseDocTemplate(
        str(out_path), pagesize=A4,
        leftMargin=ML, rightMargin=MR,
        topMargin=MT, bottomMargin=MB,
        title="ArchGuide - Document Analysis Pipeline Bible",
        author="ArchGuide",
    )
    doc2._total_pages = total
    frame2 = Frame(ML, MB, PAGE_W - ML - MR, PAGE_H - MT - MB,
                   id="body", showBoundary=0)
    doc2.addPageTemplates([PageTemplate(id="main", frames=[frame2],
                                        onPage=on_page)])
    doc2.build(build_story())

    print(f"Wrote {out_path} ({total} pages)")


if __name__ == "__main__":
    main()
