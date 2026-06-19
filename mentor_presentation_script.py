"""
Run this script to generate the mentor presentation PDF.
Requirements: pip install fpdf2
"""
from fpdf import FPDF

class PDF(FPDF):
    def header(self):
        self.set_fill_color(15, 23, 42)
        self.rect(0, 0, 210, 20, 'F')
        self.set_text_color(255, 255, 255)
        self.set_font('Helvetica', 'B', 11)
        self.set_xy(0, 5)
        self.cell(0, 10, 'ArchGuide Backend - 5-Minute Mentor Presentation Script', align='C')
        self.set_text_color(0, 0, 0)
        self.ln(18)

    def footer(self):
        self.set_y(-12)
        self.set_font('Helvetica', 'I', 8)
        self.set_text_color(120, 120, 120)
        self.cell(0, 10, f'Page {self.page_no()}', align='C')

    def section_title(self, title, subtitle=''):
        self.set_fill_color(15, 23, 42)
        self.set_text_color(255, 255, 255)
        self.set_font('Helvetica', 'B', 11)
        self.cell(0, 8, title, fill=True, ln=True)
        if subtitle:
            self.set_fill_color(230, 234, 240)
            self.set_text_color(60, 60, 60)
            self.set_font('Helvetica', 'I', 9)
            self.cell(0, 6, subtitle, fill=True, ln=True)
        self.set_text_color(0, 0, 0)
        self.ln(2)

    def say(self, text):
        self.set_font('Helvetica', '', 10)
        self.set_text_color(20, 20, 20)
        self.set_fill_color(240, 249, 255)
        self.set_draw_color(59, 130, 246)
        self.set_line_width(0.5)
        # Draw left accent bar
        x, y = self.get_x(), self.get_y()
        self.rect(x, y, 2, 14, 'F')
        self.set_xy(x + 5, y)
        self.set_font('Helvetica', 'B', 8)
        self.set_text_color(59, 130, 246)
        self.cell(15, 5, 'SAY:', ln=False)
        self.set_font('Helvetica', 'I', 10)
        self.set_text_color(20, 20, 20)
        self.multi_cell(0, 5, text)
        self.ln(2)

    def focus(self, text):
        self.set_fill_color(254, 243, 199)
        self.set_draw_color(234, 179, 8)
        self.set_line_width(0.3)
        x, y = self.get_x(), self.get_y()
        self.rect(x, y, 2, 10, 'F')
        self.set_xy(x + 5, y)
        self.set_font('Helvetica', 'B', 8)
        self.set_text_color(161, 98, 7)
        self.cell(20, 5, 'FOCUS ON:', ln=False)
        self.set_font('Helvetica', '', 9)
        self.set_text_color(20, 20, 20)
        self.multi_cell(0, 5, text)
        self.ln(2)

    def tip(self, text):
        self.set_fill_color(240, 253, 244)
        x, y = self.get_x(), self.get_y()
        self.rect(x, y, 2, 10, 'F')
        self.set_fill_color(34, 197, 94)
        self.rect(x, y, 2, 10, 'F')
        self.set_xy(x + 5, y)
        self.set_font('Helvetica', 'B', 8)
        self.set_text_color(21, 128, 61)
        self.cell(15, 5, 'TIP:', ln=False)
        self.set_font('Helvetica', '', 9)
        self.set_text_color(20, 20, 20)
        self.multi_cell(0, 5, text)
        self.ln(2)

    def code(self, text):
        self.set_fill_color(30, 30, 30)
        self.set_text_color(180, 255, 180)
        self.set_font('Courier', '', 8)
        self.multi_cell(0, 5, text, fill=True)
        self.set_text_color(0, 0, 0)
        self.ln(2)

    def timing_badge(self, text):
        self.set_fill_color(239, 68, 68)
        self.set_text_color(255, 255, 255)
        self.set_font('Helvetica', 'B', 9)
        self.cell(40, 6, f'  {text}', fill=True)
        self.ln(4)

    def bullet(self, items):
        self.set_font('Helvetica', '', 9)
        self.set_text_color(30, 30, 30)
        for item in items:
            self.cell(8, 5, chr(149))
            self.multi_cell(0, 5, item)
        self.ln(2)

    def divider(self):
        self.set_draw_color(200, 200, 200)
        self.set_line_width(0.3)
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(4)


pdf = PDF()
pdf.set_auto_page_break(auto=True, margin=15)
pdf.set_margins(10, 10, 10)

# ── PAGE 1: Overview + main.py ────────────────────────────────────────────────
pdf.add_page()

pdf.set_font('Helvetica', 'B', 16)
pdf.set_text_color(15, 23, 42)
pdf.ln(2)
pdf.cell(0, 10, 'ArchGuide Backend - 5-Minute Mentor Script', ln=True, align='C')
pdf.set_font('Helvetica', '', 9)
pdf.set_text_color(100, 100, 100)
pdf.cell(0, 6, 'Tanmay Sachan  |  HPE Architecture Decision Tool', ln=True, align='C')
pdf.ln(4)
pdf.divider()

# One-liner
pdf.set_fill_color(15, 23, 42)
pdf.set_text_color(255, 255, 255)
pdf.set_font('Helvetica', 'B', 10)
pdf.cell(0, 8, '  ONE-LINE SUMMARY (memorise this)', fill=True, ln=True)
pdf.set_fill_color(248, 250, 252)
pdf.set_text_color(15, 23, 42)
pdf.set_font('Helvetica', 'I', 11)
pdf.multi_cell(0, 7,
    '"The user describes their project - by uploading documents or answering questions.\n'
    'The backend extracts signals using an LLM, scores 4 architecture patterns against those\n'
    'signals, and returns a recommendation with cost analysis - cached in Redis, stored in PostgreSQL."',
    fill=True)
pdf.ln(4)

# Flow diagram
pdf.section_title('SYSTEM FLOW  (draw this on whiteboard while speaking)', '')
pdf.set_font('Courier', 'B', 9)
pdf.set_text_color(15, 23, 42)
pdf.set_fill_color(248, 250, 252)
flow = (
    "  User uploads docs / fills questionnaire\n"
    "            |\n"
    "    Frontend (Next.js)  -->  HTTP POST  -->  FastAPI\n"
    "            |\n"
    "    document_parser  ->  signal_extractor  ->  scoring_engine\n"
    "            |                   |                    |\n"
    "      raw text          LLM extracts signals    rule-based scoring\n"
    "                                                     |\n"
    "                              Recommendation + Cost Analysis\n"
    "                                                     |\n"
    "                        Saved to PostgreSQL + cached in Redis\n"
    "                                                     |\n"
    "                               Results shown in frontend"
)
pdf.multi_cell(0, 5, flow, fill=True)
pdf.ln(4)

# TIMING OVERVIEW
pdf.section_title('TIMING PLAN', 'Stick to this - 5 minutes goes fast')
timings = [
    ('0:00 - 0:40', 'One-liner + System Flow diagram', '40 sec'),
    ('0:40 - 1:30', 'main.py - entry point walkthrough', '50 sec'),
    ('1:30 - 3:00', 'Routers - what each one does', '90 sec'),
    ('3:00 - 4:30', 'Pipeline Services - the intelligence', '90 sec'),
    ('4:30 - 5:00', 'Wrap up + invite questions', '30 sec'),
]
pdf.set_font('Helvetica', '', 9)
for slot, topic, dur in timings:
    pdf.set_fill_color(248, 250, 252)
    pdf.set_text_color(15, 23, 42)
    pdf.cell(40, 6, slot, fill=True, border=1)
    pdf.cell(110, 6, topic, fill=True, border=1)
    pdf.set_fill_color(239, 68, 68)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(30, 6, dur, fill=True, border=1, align='C')
    pdf.ln()
pdf.ln(4)

pdf.divider()

# SECTION 1 - main.py
pdf.section_title('PART 1 - main.py  (Entry Point)', 'File: backend/app/main.py  |  Target: 50 seconds')
pdf.timing_badge('0:40 -> 1:30')

pdf.say(
    '"main.py is the entry point of our FastAPI application. Think of it as the front door of the backend.\n\n'
    'It does five things at startup:\n'
    '1. Creates the FastAPI app with a title and version\n'
    '2. Configures CORS so our Next.js frontend can talk to it\n'
    '3. Registers all 6 routers under the /api/v1 prefix\n'
    '4. Connects to PostgreSQL, Redis, and runs Alembic database migrations automatically\n'
    '5. Recovers any sessions that got stuck in processing state during a server crash\n\n'
    'The key line to show is the include_router block - that is where all 6 feature areas plug in."'
)

pdf.focus('Show this exact code block from main.py lines 74-80:')
pdf.code(
    '  prefix = settings.API_PREFIX  # "/api/v1"\n'
    '  app.include_router(upload.router,        prefix=prefix, tags=["Upload"])\n'
    '  app.include_router(analysis.router,      prefix=prefix, tags=["Analysis"])\n'
    '  app.include_router(questionnaire.router, prefix=prefix, tags=["Questionnaire"])\n'
    '  app.include_router(projects.router,      prefix=prefix, tags=["Projects"])\n'
    '  app.include_router(users.router,         prefix=prefix, tags=["Users"])\n'
    '  app.include_router(chat.router,          prefix=prefix, tags=["Chat"])'
)

pdf.tip('Mention: "Every API call from the frontend hits /api/v1/<something> - this is where that prefix comes from."')

# ── PAGE 2: Routers ───────────────────────────────────────────────────────────
pdf.add_page()

pdf.section_title('PART 2 - Routers  (Feature Areas)', 'Folder: backend/app/routers/  |  Target: 90 seconds')
pdf.timing_badge('1:30 -> 3:00')

pdf.say(
    '"We have 6 routers, each owning a specific feature. Think of each router as a mini controller -\n'
    'it receives the HTTP request, validates it, calls the right service, and returns the response.\n\n'
    'Let me walk through each one quickly:"'
)

routers = [
    ('upload.py',
     'POST /api/v1/upload',
     'Accepts PDF or document uploads from the user. Validates the file,\n'
     '    saves it, then kicks off the full processing pipeline asynchronously.\n'
     '    Returns a session_id the frontend uses to poll for results.'),
    ('questionnaire.py',
     'POST /api/v1/questionnaire',
     'Handles the guided flow - instead of uploading a doc, the user answers\n'
     '    structured questions. The answers are converted into the same signal\n'
     '    format as document uploads, so both paths share the same scoring engine.'),
    ('analysis.py',
     'GET /api/v1/analysis/{session_id}',
     'Returns the final recommendation for a session. Frontend polls this\n'
     '    every few seconds until status changes from "processing" to "complete".'),
    ('projects.py',
     'GET/POST/DELETE /api/v1/projects',
     'Full CRUD for user projects. A project groups multiple analysis sessions\n'
     '    together so users can compare different architecture decisions.'),
    ('users.py',
     'POST /api/v1/users/verify',
     'Handles authentication. Takes a Firebase JWT token from the frontend,\n'
     '    verifies it server-side, and returns the user profile.'),
    ('chat.py',
     'POST /api/v1/chat',
     'Powers the follow-up chat feature. User can ask questions about their\n'
     '    recommendation. Uses streaming responses so answers appear word by word.'),
]

for name, route, desc in routers:
    pdf.set_fill_color(15, 23, 42)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font('Helvetica', 'B', 9)
    pdf.cell(40, 6, f'  {name}', fill=True)
    pdf.set_fill_color(59, 130, 246)
    pdf.set_font('Courier', '', 8)
    pdf.cell(0, 6, f'  {route}', fill=True, ln=True)
    pdf.set_text_color(30, 30, 30)
    pdf.set_font('Helvetica', '', 9)
    pdf.set_fill_color(248, 250, 252)
    pdf.multi_cell(0, 5, f'    {desc}', fill=True)
    pdf.ln(1)

pdf.ln(2)
pdf.tip(
    'Key point to emphasise: "Upload and Questionnaire are two DIFFERENT entry points but they both produce\n'
    'the same signal format - so the scoring engine is completely reused. That is the key design decision."'
)

pdf.divider()

# SECTION 3 - Pipeline Services
pdf.section_title('PART 3 - Pipeline Services  (The Intelligence)', 'Folder: backend/services/  |  Target: 90 seconds')
pdf.timing_badge('3:00 -> 4:30')

pdf.say(
    '"This is where the actual AI logic lives. When a file is uploaded or questionnaire is submitted,\n'
    'these 5 services run sequentially - like an assembly line:"'
)

# Pipeline visual
pdf.set_fill_color(30, 30, 30)
pdf.set_text_color(180, 255, 180)
pdf.set_font('Courier', 'B', 9)
pipeline = (
    "  document_parser\n"
    "       |\n"
    "       v\n"
    "  signal_extractor  <-- LLM call happens here\n"
    "       |\n"
    "       v\n"
    "  scoring_engine    <-- deterministic, no LLM\n"
    "       |\n"
    "       v\n"
    "  recommendation_service  -->  final output\n"
    "       |\n"
    "       v  (cached)\n"
    "  extraction_cache  +  Redis"
)
pdf.multi_cell(0, 5, pipeline, fill=True)
pdf.set_text_color(0, 0, 0)
pdf.ln(4)

services = [
    ('document_parser.py',
     'Step 1: Text Extraction',
     'Takes the raw uploaded file and extracts clean text from it.\n'
     '    Scores each page by relevance - only sends signal-rich pages to the LLM.\n'
     '    This saves tokens and makes extraction faster.'),
    ('signal_extractor.py',
     'Step 2: Signal Extraction (LLM)',
     'Sends the cleaned text to the LLM and asks it to extract 8 key signals:\n'
     '    dataset_size, query_volume, latency_requirement, data_volatility,\n'
     '    accuracy_requirement, domain_specificity, update_frequency, cost_sensitivity.\n'
     '    Also uses SHA-256 caching - if same document uploaded again, skips LLM entirely.'),
    ('scoring_engine.py',
     'Step 3: Architecture Scoring (No LLM)',
     'This is pure deterministic logic - no AI involved.\n'
     '    Each signal value maps to score deltas for RAG, Fine-Tuning, CAG, and Hybrid.\n'
     '    Example: high data_volatility gives RAG +1.0, FineTuning +0.2, CAG +0.1\n'
     '    The architecture with the highest total score wins.'),
    ('llm_client.py',
     'Utility: Unified LLM Wrapper',
     'Single class that supports both Ollama (local, free) and OpenAI (cloud).\n'
     '    Provider is switched via a query param on each request.\n'
     '    Uses connection pooling for Ollama to save 10-50ms per call.'),
    ('extraction_cache.py',
     'Utility: SHA-256 In-Memory Cache',
     'Hashes the document content. If the same doc was processed in the last hour,\n'
     '    returns cached signals instantly - no LLM call needed. Saves cost and time.'),
]

for name, label, desc in services:
    pdf.set_fill_color(15, 23, 42)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font('Helvetica', 'B', 9)
    pdf.cell(55, 6, f'  {name}', fill=True)
    pdf.set_fill_color(99, 102, 241)
    pdf.set_font('Helvetica', 'I', 8)
    pdf.cell(0, 6, f'  {label}', fill=True, ln=True)
    pdf.set_text_color(30, 30, 30)
    pdf.set_font('Helvetica', '', 9)
    pdf.set_fill_color(248, 250, 252)
    pdf.multi_cell(0, 5, f'    {desc}', fill=True)
    pdf.ln(1)

# ── PAGE 3: Closing + Cheat Sheet ─────────────────────────────────────────────
pdf.add_page()

pdf.section_title('PART 4 - Closing Statement', 'Target: 30 seconds')
pdf.timing_badge('4:30 -> 5:00')
pdf.say(
    '"To summarise the backend architecture:\n\n'
    'main.py bootstraps everything. Routers are the API surface - 6 of them, each owning a feature.\n'
    'The pipeline services are where intelligence happens - document parsing, LLM-based signal\n'
    'extraction, and deterministic scoring. Results are cached in Redis for 15 minutes so the\n'
    'LLM pipeline does not re-run on every page refresh.\n\n'
    'Happy to go deeper on any specific part."'
)

pdf.divider()

# CHEAT SHEET
pdf.section_title('QUICK REFERENCE CHEAT SHEET', 'Keep this open on your phone/laptop during the presentation')

pdf.set_font('Helvetica', 'B', 10)
pdf.set_fill_color(15, 23, 42)
pdf.set_text_color(255, 255, 255)
pdf.cell(0, 7, '  KEY FILES AT A GLANCE', fill=True, ln=True)

cheat = [
    ('backend/app/main.py', 'App factory, router registration, startup hooks'),
    ('backend/app/routers/upload.py', 'POST /api/v1/upload - file upload entry point'),
    ('backend/app/routers/questionnaire.py', 'POST /api/v1/questionnaire - guided flow entry point'),
    ('backend/app/routers/analysis.py', 'GET /api/v1/analysis/{id} - poll for results'),
    ('backend/app/routers/projects.py', 'CRUD for projects'),
    ('backend/app/routers/users.py', 'Firebase JWT verification'),
    ('backend/app/routers/chat.py', 'Streaming follow-up chat'),
    ('backend/services/document_parser.py', 'Step 1: extract text from file'),
    ('backend/services/signal_extractor.py', 'Step 2: LLM extracts 8 signals'),
    ('backend/services/scoring_engine.py', 'Step 3: score RAG/FT/CAG/Hybrid'),
    ('backend/services/llm_client.py', 'Ollama or OpenAI wrapper'),
    ('backend/services/extraction_cache.py', 'SHA-256 cache, skip LLM on repeat'),
    ('backend/app/services/cache_service.py', 'Redis get/set for results (15 min TTL)'),
    ('backend/app/services/cost_analysis.py', 'Estimates cloud cost per architecture'),
    ('backend/config.py', 'All env vars in one Pydantic settings class'),
]

pdf.set_font('Helvetica', '', 8)
for i, (file, desc) in enumerate(cheat):
    bg = (248, 250, 252) if i % 2 == 0 else (255, 255, 255)
    pdf.set_fill_color(*bg)
    pdf.set_text_color(15, 23, 42)
    pdf.cell(90, 5, f'  {file}', fill=True, border=1)
    pdf.set_text_color(60, 60, 60)
    pdf.cell(0, 5, f'  {desc}', fill=True, border=1, ln=True)

pdf.ln(4)

pdf.set_font('Helvetica', 'B', 10)
pdf.set_fill_color(15, 23, 42)
pdf.set_text_color(255, 255, 255)
pdf.cell(0, 7, '  SIGNALS THE LLM EXTRACTS (signal_extractor.py)', fill=True, ln=True)

signals = [
    ('dataset_size', 'small / medium / large / very_large'),
    ('query_volume', 'low / medium / high / very_high'),
    ('latency_requirement', 'relaxed / moderate / strict / ultra_low'),
    ('data_volatility', 'static / low / moderate / high'),
    ('accuracy_requirement', 'moderate / high / very_high / critical'),
    ('domain_specificity', 'general / moderate / high / very_high'),
    ('update_frequency', 'rarely / monthly / weekly / daily'),
    ('cost_sensitivity', 'low / medium / high / very_high'),
]

pdf.set_font('Helvetica', '', 8)
for i, (sig, vals) in enumerate(signals):
    bg = (248, 250, 252) if i % 2 == 0 else (255, 255, 255)
    pdf.set_fill_color(*bg)
    pdf.set_text_color(59, 130, 246)
    pdf.set_font('Courier', 'B', 8)
    pdf.cell(60, 5, f'  {sig}', fill=True, border=1)
    pdf.set_text_color(60, 60, 60)
    pdf.set_font('Helvetica', '', 8)
    pdf.cell(0, 5, f'  {vals}', fill=True, border=1, ln=True)

pdf.ln(4)

# LIKELY MENTOR QUESTIONS
pdf.set_font('Helvetica', 'B', 10)
pdf.set_fill_color(15, 23, 42)
pdf.set_text_color(255, 255, 255)
pdf.cell(0, 7, '  LIKELY MENTOR QUESTIONS + ANSWERS', fill=True, ln=True)
pdf.ln(2)

qas = [
    (
        'Q: Why two LLM providers?',
        'Ollama runs locally for free during development - no API cost, no data leaving the machine.\n'
        '   OpenAI is for production where quality matters more. Provider is switched via a query param,\n'
        '   so nothing in the pipeline changes - only llm_client.py switches internally.'
    ),
    (
        'Q: Why FAISS and not a cloud vector DB?',
        'FAISS runs locally with zero cost and zero latency. For this scale (single-tenant analysis\n'
        '   sessions), a cloud vector DB would be overkill. We can migrate later if needed.'
    ),
    (
        'Q: Why Redis if results are already in PostgreSQL?',
        'Redis serves the polling loop. The frontend polls /analysis/{id} every 2-3 seconds.\n'
        '   Without Redis, each poll hits PostgreSQL. With Redis, the first DB write is cached\n'
        '   for 15 minutes - subsequent polls are sub-millisecond memory reads.'
    ),
    (
        'Q: Why is scoring_engine.py deterministic and not an LLM?',
        'LLMs are non-deterministic - the same input can produce different scores each time.\n'
        '   Architecture recommendations need to be explainable and reproducible. Rule-based\n'
        '   scoring gives us a clear audit trail: signal X with value Y added Z points to RAG.'
    ),
    (
        'Q: How does authentication work?',
        'Firebase handles login on the frontend and issues a JWT token. Every API request\n'
        '   sends this token in the Authorization header. The backend verifies it server-side\n'
        '   using the Firebase Admin SDK in app/core/security.py - no passwords stored.'
    ),
]

for q, a in qas:
    pdf.set_fill_color(239, 68, 68)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font('Helvetica', 'B', 9)
    pdf.cell(0, 6, f'  {q}', fill=True, ln=True)
    pdf.set_fill_color(254, 242, 242)
    pdf.set_text_color(30, 30, 30)
    pdf.set_font('Helvetica', '', 9)
    pdf.multi_cell(0, 5, f'   {a}', fill=True)
    pdf.ln(2)

output_path = r'C:\Users\tanma\OneDrive\Desktop\ArchGuide_Mentor_Script.pdf'
pdf.output(output_path)
print(f"PDF saved to: {output_path}")
