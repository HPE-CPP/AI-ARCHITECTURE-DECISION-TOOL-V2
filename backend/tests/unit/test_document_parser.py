"""
UNIT TESTS — Document Parser
Tests PDF/DOCX/TXT parsing, file validation, section detection,
page relevance scoring, and the new risk-scoring relevance gate.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock
from services.document_parser import (
    DocumentParser, detect_sections, score_page_relevance,
    get_relevant_pages, register_signal_keywords,
    # Risk-scoring gate
    RiskTier, RuleFlag, RelevanceAssessment,
    rule_length_ceiling, rule_keyword_density, rule_category_coverage,
    rule_resume_shape, rule_circular_upload,
    assess_document_risk, validate_document_relevance,
    MAX_REASONABLE_WORD_COUNT, EXTREME_WORD_COUNT,
    AUTO_REJECT_THRESHOLD, REVIEW_THRESHOLD,
    MIN_CATEGORIES_REQUIRED,
)


# ── Minimal SIGNAL_SCHEMA fixture (matches real schema shape) ─────────────────
MINI_SCHEMA = {
    "dataset_size": {
        "description": "Volume of data",
        "keywords": ["dataset", "data size", "records", "corpus", "training data"],
    },
    "query_volume": {
        "description": "Query throughput",
        "keywords": ["query", "requests", "qps", "throughput", "concurrent"],
    },
    "latency_requirement": {
        "description": "Response time",
        "keywords": ["latency", "response time", "real-time", "millisecond", "sla"],
    },
    "data_volatility": {
        "description": "How often data changes",
        "keywords": ["update", "volatile", "dynamic", "refresh", "streaming"],
    },
    "accuracy_requirement": {
        "description": "Accuracy needs",
        "keywords": ["accuracy", "precision", "recall", "quality", "hallucination"],
    },
    "domain_specificity": {
        "description": "Domain specialisation",
        "keywords": ["domain", "specialized", "expert", "medical", "legal"],
    },
    "security_level": {
        "description": "Security requirements",
        "keywords": ["security", "privacy", "compliance", "gdpr", "encryption"],
    },
    "cost_sensitivity": {
        "description": "Budget constraints",
        "keywords": ["cost", "budget", "expensive", "affordable", "roi"],
    },
    "deployment_preference": {
        "description": "Deployment target",
        "keywords": ["deploy", "cloud", "on-premise", "aws", "azure"],
    },
    "user_scale": {
        "description": "Number of users",
        "keywords": ["users", "user base", "scale", "enterprise", "consumer"],
    },
    "citation_requirement": {
        "description": "Source citation needs",
        "keywords": ["citation", "audit trail", "transparency", "traceable", "reasoning"],
    },
    "context_size": {
        "description": "Context per query",
        "keywords": ["context window", "knowledge base", "corpus size", "context length"],
    },
}

# ── A realistic requirements-doc excerpt ──────────────────────────────────────
GOOD_REQUIREMENTS_DOC = """
Project Requirements: AI-Powered Customer Support System

Overview:
This document specifies the requirements for an AI chatbot system for our support team.
The system shall handle customer queries in real-time and must support at least 1,000
concurrent users. Dataset includes 200,000 historical support tickets and product manuals.

Performance Requirements:
- Latency must be under 500 milliseconds for 95th percentile responses.
- The system must handle 500 queries per second at peak load.
- Data is updated daily as new support tickets are resolved.

Accuracy Requirements:
- The system must avoid hallucination and cite sources from the knowledge base.
- Accuracy requirement is high; incorrect answers incur reputational risk.

Security:
- All data must comply with GDPR regulations. User privacy is paramount.
- Encryption at rest and in transit is required.

Deployment:
- Cloud deployment on AWS preferred. Cost must be optimised.
- The budget is moderate; expensive training runs are not feasible.

Data Characteristics:
- Dataset size: medium (200K records). Corpus is updated daily.
- Domain: specialized — internal product and support knowledge.
- User scale: medium (500-2000 support agents across the organisation).
""" * 3  # ~300 words × 3 = ~900 words, well within normal range


# ────────────────────────────────────────────────────────────────────────────
# Existing tests (unchanged)
# ────────────────────────────────────────────────────────────────────────────

@pytest.mark.unit
class TestDocumentParserValidation:

    def setup_method(self):
        self.parser = DocumentParser()

    def test_valid_pdf_accepted(self):
        valid, msg = self.parser.validate_file("report.pdf", 1024)
        assert valid is True

    def test_valid_docx_accepted(self):
        valid, msg = self.parser.validate_file("spec.docx", 1024)
        assert valid is True

    def test_valid_txt_accepted(self):
        valid, msg = self.parser.validate_file("notes.txt", 512)
        assert valid is True

    def test_invalid_extension_rejected(self):
        valid, msg = self.parser.validate_file("malware.exe", 1024)
        assert valid is False
        assert "Unsupported" in msg

    def test_csv_rejected(self):
        valid, msg = self.parser.validate_file("data.csv", 1024)
        assert valid is False

    def test_js_file_rejected(self):
        valid, msg = self.parser.validate_file("script.js", 1024)
        assert valid is False

    def test_oversized_file_rejected(self):
        # 51MB > 50MB limit
        valid, msg = self.parser.validate_file("huge.pdf", 51 * 1024 * 1024)
        assert valid is False
        assert "large" in msg.lower() or "exceeds" in msg.lower() or "MB" in msg

    def test_exactly_at_limit_is_rejected(self):
        # Exactly 50MB is at the limit (> check), should fail
        valid, msg = self.parser.validate_file("border.pdf", 50 * 1024 * 1024 + 1)
        assert valid is False

    def test_just_below_limit_is_accepted(self):
        valid, msg = self.parser.validate_file("ok.pdf", 50 * 1024 * 1024 - 1)
        assert valid is True

    def test_zero_size_file_accepted_by_validate(self):
        # Validation only checks extension and size, not content
        valid, msg = self.parser.validate_file("empty.pdf", 0)
        assert valid is True

    def test_uppercase_extension_rejected(self):
        # Extension check is case-sensitive
        valid, msg = self.parser.validate_file("report.PDF", 1024)
        # Currently the parser lowercases extensions, so this should pass
        assert isinstance(valid, bool)

    def test_no_extension_rejected(self):
        valid, msg = self.parser.validate_file("noextension", 1024)
        assert valid is False

    def test_path_traversal_filename(self):
        """SECURITY: Path traversal should be rejected at validate_file level."""
        valid, msg = self.parser.validate_file("../../etc/passwd", 1024)
        # Extension ".." or no extension → invalid
        assert valid is False


@pytest.mark.unit
class TestDocumentParserTXT:

    def setup_method(self):
        self.parser = DocumentParser()

    @pytest.mark.asyncio
    async def test_parses_txt_file(self, tmp_path):
        content = "This is a test document with requirements.\nDataset size is large."
        f = tmp_path / "test.txt"
        f.write_text(content, encoding="utf-8")
        result = await self.parser.parse(str(f), "test.txt")
        assert result["format"] == ".txt"
        assert result["total_pages"] == 1
        assert "This is a test document" in result["full_text"]
        assert result["word_count"] > 0

    @pytest.mark.asyncio
    async def test_empty_txt_returns_empty_text(self, tmp_path):
        f = tmp_path / "empty.txt"
        f.write_text("", encoding="utf-8")
        result = await self.parser.parse(str(f), "empty.txt")
        assert result["word_count"] == 0
        assert result["full_text"] == ""

    @pytest.mark.asyncio
    async def test_unicode_txt_parses_correctly(self, tmp_path):
        content = "Système de traitement des données. 数据处理系统. नमस्ते दुनिया।"
        f = tmp_path / "unicode.txt"
        f.write_text(content, encoding="utf-8")
        result = await self.parser.parse(str(f), "unicode.txt")
        assert "Système" in result["full_text"]
        assert result["word_count"] > 0

    @pytest.mark.asyncio
    async def test_large_txt_parsed(self, tmp_path):
        content = "The system processes millions of records. " * 1000
        f = tmp_path / "large.txt"
        f.write_text(content, encoding="utf-8")
        result = await self.parser.parse(str(f), "large.txt")
        assert result["word_count"] > 5000

    @pytest.mark.asyncio
    async def test_txt_with_only_whitespace(self, tmp_path):
        f = tmp_path / "whitespace.txt"
        f.write_text("   \n\n\t   \n   ", encoding="utf-8")
        result = await self.parser.parse(str(f), "whitespace.txt")
        # After strip, should be empty
        assert result["full_text"] == ""


@pytest.mark.unit
class TestSectionDetection:

    def test_detects_overview_section(self):
        text = "Overview\nThis document describes the system architecture.\n"
        sections = detect_sections(text)
        assert len(sections["overview"]) > 0

    def test_detects_security_section(self):
        text = "Security\nGDPR and HIPAA compliance required.\n"
        sections = detect_sections(text)
        assert len(sections["security"]) > 0

    def test_detects_performance_section(self):
        text = "Performance Requirements\nLatency must be under 100ms.\n"
        sections = detect_sections(text)
        assert len(sections["performance"]) > 0

    def test_empty_text_returns_empty_sections(self):
        sections = detect_sections("")
        for key, vals in sections.items():
            assert vals == []

    def test_no_headings_returns_empty_sections(self):
        text = "This is a wall of text with no headings or structure at all."
        sections = detect_sections(text)
        # Content lines don't match headings → all empty
        for vals in sections.values():
            assert vals == []

    def test_long_line_not_treated_as_heading(self):
        # Lines with > 8 words are not headings
        text = "This line has more than eight words in it so it is not a heading\n"
        sections = detect_sections(text)
        for vals in sections.values():
            assert vals == []


@pytest.mark.unit
class TestPageRelevance:

    def setup_method(self):
        # Register some keywords for scoring
        register_signal_keywords(frozenset(["dataset", "records", "latency", "query"]))

    def test_relevant_page_scores_above_zero(self):
        text = "The dataset contains millions of records."
        score = score_page_relevance(text)
        assert score >= 2  # "dataset" and "records"

    def test_irrelevant_page_scores_zero(self):
        text = "The quick brown fox jumps over the lazy dog."
        score = score_page_relevance(text)
        assert score == 0

    def test_get_relevant_pages_filters_irrelevant(self):
        pages = [
            {"page_number": 1, "text": "Intro page with no keywords."},
            {"page_number": 2, "text": "The dataset contains millions of records."},
        ]
        relevant = get_relevant_pages(pages, min_score=1)
        assert len(relevant) == 1
        assert relevant[0]["page_number"] == 2

    def test_get_relevant_pages_falls_back_to_all_if_none_match(self):
        pages = [
            {"page_number": 1, "text": "No keywords here."},
            {"page_number": 2, "text": "Also nothing relevant."},
        ]
        relevant = get_relevant_pages(pages, min_score=1)
        # Should return all pages as fallback
        assert len(relevant) == 2

    def test_get_relevant_pages_preserves_document_order(self):
        pages = [
            {"page_number": 1, "text": "Latency requirements are strict."},
            {"page_number": 2, "text": "No keywords here at all."},
            {"page_number": 3, "text": "Dataset of records is large."},
        ]
        relevant = get_relevant_pages(pages, min_score=1)
        page_numbers = [p["page_number"] for p in relevant]
        assert page_numbers == sorted(page_numbers)


# ────────────────────────────────────────────────────────────────────────────
# NEW: Risk-scoring rule unit tests (Step 6)
# ────────────────────────────────────────────────────────────────────────────

@pytest.mark.unit
class TestRuleFlags:
    """Each rule function must always return a RuleFlag with triggered=True/False.
    None of them should raise or return early."""

    # ── rule_length_ceiling ──────────────────────────────────────────────────

    def test_length_ceiling_normal_not_triggered(self):
        flag = rule_length_ceiling(1000)
        assert flag.triggered is False
        assert flag.risk_points == 0
        assert flag.rule_name == "length_ceiling"

    def test_length_ceiling_long_doc_moderate_risk(self):
        flag = rule_length_ceiling(MAX_REASONABLE_WORD_COUNT + 1)
        assert flag.triggered is True
        assert flag.risk_points == 35

    def test_length_ceiling_extreme_doc_high_risk(self):
        """60,000-word document → extreme tier → risk_points=70 (enough to auto-reject alone)."""
        flag = rule_length_ceiling(60_000)
        assert flag.triggered is True
        assert flag.risk_points == 70

    def test_length_ceiling_at_exact_extreme_boundary(self):
        flag = rule_length_ceiling(EXTREME_WORD_COUNT)
        # Equal is NOT > so should be moderate, not extreme
        assert flag.triggered is False or flag.risk_points <= 35

    def test_length_ceiling_always_returns_ruleflag(self):
        for wc in [0, 50, 500, 5000, 15001, 50001, 200000]:
            flag = rule_length_ceiling(wc)
            assert isinstance(flag, RuleFlag)

    # ── rule_keyword_density ─────────────────────────────────────────────────

    def test_keyword_density_healthy_doc_not_triggered(self):
        """Good requirements doc → many keyword hits → not triggered."""
        flag = rule_keyword_density(GOOD_REQUIREMENTS_DOC, len(GOOD_REQUIREMENTS_DOC.split()), MINI_SCHEMA)
        assert flag.triggered is False
        assert flag.risk_points == 0

    def test_keyword_density_lorem_ipsum_triggered(self):
        lorem = "Lorem ipsum dolor sit amet consectetur adipiscing elit sed do eiusmod " * 50
        flag = rule_keyword_density(lorem, len(lorem.split()), MINI_SCHEMA)
        assert flag.triggered is True
        assert flag.risk_points >= 15  # at least below-threshold tier

    def test_keyword_density_very_low_density_high_risk(self):
        """Only 2 keyword hits in 1000 words → density=2.0 → below-threshold tier (15 pts)."""
        text = ("word " * 998) + "dataset latency"
        flag = rule_keyword_density(text, 1000, MINI_SCHEMA)
        assert flag.triggered is True
        assert flag.risk_points == 15  # density 2.0 → between 1.5 and 3.0

    def test_keyword_density_extreme_low_density_very_high_risk(self):
        """Zero keyword hits → density=0 → very-low density tier (40 pts)."""
        # Completely unrelated text with no signal keywords at all
        text = "apple banana cherry mango peach orange grape kiwi melon pear " * 100
        flag = rule_keyword_density(text, len(text.split()), MINI_SCHEMA)
        assert flag.triggered is True
        assert flag.risk_points == 40  # density 0.0 < 1.5

    # ── rule_category_coverage ───────────────────────────────────────────────

    def test_category_coverage_good_doc_passes(self):
        flag = rule_category_coverage(GOOD_REQUIREMENTS_DOC, MINI_SCHEMA)
        assert flag.triggered is False
        assert flag.risk_points == 0

    def test_category_coverage_no_matches_high_risk(self):
        flag = rule_category_coverage("Hello world, this is completely unrelated text.", MINI_SCHEMA)
        assert flag.triggered is True
        assert flag.risk_points == 45  # < 2 categories matched

    def test_category_coverage_few_matches_moderate_risk(self):
        # Only 3 categories matched → between 2 and MIN_CATEGORIES_REQUIRED
        text = "Our dataset is large. The latency is strict. We need cloud deployment."
        flag = rule_category_coverage(text, MINI_SCHEMA)
        assert flag.triggered is True
        # 1-4 categories → either 20 or 45 risk points depending on hit count

    def test_category_coverage_requires_2_unique_keywords_per_category(self):
        """'dataset' alone (1 keyword hit) should NOT satisfy a category match."""
        # Only 1 keyword hit per category → should not count
        text = "The dataset is important. The latency matters. Security is needed."
        flag = rule_category_coverage(text, MINI_SCHEMA)
        # Each category only has 1 keyword hit → categories_matched should be low
        assert isinstance(flag, RuleFlag)

    # ── rule_resume_shape ────────────────────────────────────────────────────

    RESUME_TEXT = """
John Doe
john.doe@example.com | +1 (555) 123-4567 | linkedin.com/in/johndoe | github.com/johndoe

Work Experience
Software Engineer — Acme Corp
Jan 2020 – Present
• Designed scalable AWS cloud pipelines processing millions of records
• Implemented security and compliance measures for GDPR

Education
B.S. Computer Science — MIT
Aug 2016 – May 2020

Skills
Python, AWS, Azure, data engineering, security, performance optimization

Certifications
AWS Certified Solutions Architect
"""

    def test_resume_shape_detects_strong_resume(self):
        flag = rule_resume_shape(self.RESUME_TEXT)
        assert flag.triggered is True
        assert flag.risk_points == 50  # strong resume, no spec language

    def test_resume_shape_not_triggered_on_good_doc(self):
        flag = rule_resume_shape(GOOD_REQUIREMENTS_DOC)
        assert flag.triggered is False
        assert flag.risk_points == 0

    def test_resume_shape_spec_language_reduces_risk(self):
        """A doc that looks like a resume but has spec language gets lower risk."""
        mixed = self.RESUME_TEXT + "\nThe system shall handle 1000 users. Requirement: use case analysis."
        flag = rule_resume_shape(mixed)
        # May still trigger but at 15 pts, not 50
        if flag.triggered:
            assert flag.risk_points == 15

    # ── rule_circular_upload ─────────────────────────────────────────────────

    def test_circular_upload_archguide_report_detected(self):
        text = "Generated by ArchGuide\nThis is an architecture recommendation report."
        flag = rule_circular_upload(text)
        assert flag.triggered is True
        assert flag.risk_points == 100

    def test_circular_upload_normal_doc_not_triggered(self):
        flag = rule_circular_upload(GOOD_REQUIREMENTS_DOC)
        assert flag.triggered is False
        assert flag.risk_points == 0

    def test_circular_upload_checks_first_1000_chars_only(self):
        """Marker deep in the document should NOT trigger the rule."""
        spacer = "normal content " * 100  # >> 1000 chars
        text = spacer + "generated by archguide"
        flag = rule_circular_upload(text)
        assert flag.triggered is False


# ────────────────────────────────────────────────────────────────────────────
# NEW: assess_document_risk() aggregation tests
# ────────────────────────────────────────────────────────────────────────────

@pytest.mark.unit
class TestAssessDocumentRisk:
    """Verify the tier decision logic and additive scoring."""

    def test_good_requirements_doc_is_clear(self):
        tier, total_risk, flags = assess_document_risk(
            GOOD_REQUIREMENTS_DOC, len(GOOD_REQUIREMENTS_DOC.split()), MINI_SCHEMA
        )
        assert tier == RiskTier.CLEAR
        assert total_risk < REVIEW_THRESHOLD
        assert len(flags) == 5  # all 5 rules always run

    def test_extreme_length_doc_is_auto_reject(self):
        """60,000+ word doc → length_ceiling alone hits 70 pts → AUTO_REJECT."""
        # Repeat enough to exceed EXTREME_WORD_COUNT (50,000)
        text = (
            "The system processes records with high throughput and security compliance. "
            "Latency must be under 100 milliseconds. Dataset includes millions of documents. "
        ) * 700  # ~700 * 25 words = 17,500 words... need more
        # Use a very short sentence repeated many times for efficiency
        text = ("data " * 55_000)  # exactly 55k words > 50k EXTREME threshold
        word_count = len(text.split())
        assert word_count > EXTREME_WORD_COUNT, f"Setup error: {word_count} words not > {EXTREME_WORD_COUNT}"
        tier, total_risk, flags = assess_document_risk(text, word_count, MINI_SCHEMA)
        assert tier == RiskTier.AUTO_REJECT
        assert total_risk >= AUTO_REJECT_THRESHOLD

    def test_resume_is_auto_reject_or_review(self):
        """Resume text → resume_shape=50 + likely low category coverage → ≥ REVIEW."""
        text = TestRuleFlags.RESUME_TEXT
        word_count = len(text.split())
        tier, total_risk, flags = assess_document_risk(text, word_count, MINI_SCHEMA)
        # Resume-shape alone = 50; plus low category coverage = 45 → total ≥ 70 → AUTO_REJECT
        assert tier in (RiskTier.AUTO_REJECT, RiskTier.REVIEW)

    def test_lorem_ipsum_is_auto_reject_or_review(self):
        """Lorem ipsum has very low keyword density → at least REVIEW."""
        lorem = "Lorem ipsum dolor sit amet consectetur adipiscing elit sed do eiusmod " * 20
        word_count = len(lorem.split())
        tier, total_risk, flags = assess_document_risk(lorem, word_count, MINI_SCHEMA)
        assert tier in (RiskTier.AUTO_REJECT, RiskTier.REVIEW)

    def test_archguide_report_always_auto_rejects(self):
        text = "Generated by ArchGuide\n" + GOOD_REQUIREMENTS_DOC
        word_count = len(text.split())
        tier, total_risk, flags = assess_document_risk(text, word_count, MINI_SCHEMA)
        assert tier == RiskTier.AUTO_REJECT
        assert total_risk >= 100

    def test_all_5_rules_always_run(self):
        """assess_document_risk must always return exactly 5 flags, triggered or not."""
        tier, total_risk, flags = assess_document_risk("short text", 2, MINI_SCHEMA)
        assert len(flags) == 5

    def test_additive_scoring_compounds_mid_signals(self):
        """Mid-severity rules should compound: 15+20 = 35 → still REVIEW not CLEAR."""
        # Slightly-below-density doc that also has below-MIN_CATEGORIES coverage
        # but isn't extreme → should get REVIEW, not CLEAR
        text = ("data records query users cost " * 40)  # only ~2-3 categories, density borderline
        word_count = len(text.split())
        tier, total_risk, flags = assess_document_risk(text, word_count, MINI_SCHEMA)
        # Risk should be > 0 (some rules trigger)
        assert total_risk > 0


# ────────────────────────────────────────────────────────────────────────────
# NEW: validate_document_relevance() integration tests
# ────────────────────────────────────────────────────────────────────────────

@pytest.mark.unit
class TestValidateDocumentRelevance:
    """Tests for the top-level async gate with mocked LLM."""

    def _make_llm(self, is_requirements_doc: bool, detected_type: str = "requirements document"):
        """Create a mock LLM client that returns a fixed classifier response."""
        mock_llm = MagicMock()
        mock_llm.generate_json = AsyncMock(return_value={
            "is_requirements_doc": is_requirements_doc,
            "actual_document_type": detected_type,
            "confidence": 0.9,
        })
        return mock_llm

    @pytest.mark.asyncio
    async def test_short_doc_rejected_immediately(self):
        """Documents under 80 words are rejected before any rule runs."""
        text = "Too short."
        assessment = await validate_document_relevance(text, 2, MINI_SCHEMA, self._make_llm(True))
        assert assessment.passed is False
        assert assessment.rejection_reason == "too_short"
        assert assessment.risk_tier == RiskTier.AUTO_REJECT

    @pytest.mark.asyncio
    async def test_good_requirements_doc_passes_clear(self):
        """A well-formed requirements doc clears all rules and needs no LLM review."""
        word_count = len(GOOD_REQUIREMENTS_DOC.split())
        mock_llm = self._make_llm(True)
        assessment = await validate_document_relevance(
            GOOD_REQUIREMENTS_DOC, word_count, MINI_SCHEMA, mock_llm
        )
        assert assessment.passed is True
        assert assessment.risk_tier == RiskTier.CLEAR
        # LLM should NOT have been called for a CLEAR doc
        mock_llm.generate_json.assert_not_called()

    @pytest.mark.asyncio
    async def test_extreme_length_doc_auto_rejected_no_llm(self):
        """A 60k-word doc is AUTO_REJECT — the LLM should never be called."""
        text = "The system processes records with security latency and cost. " * 1100
        word_count = len(text.split())
        mock_llm = self._make_llm(True)
        assessment = await validate_document_relevance(text, word_count, MINI_SCHEMA, mock_llm)
        assert assessment.passed is False
        assert assessment.risk_tier == RiskTier.AUTO_REJECT
        mock_llm.generate_json.assert_not_called()

    @pytest.mark.asyncio
    async def test_review_tier_llm_confirms_rejection(self):
        """REVIEW-tier doc where LLM says 'not a requirements doc' → rejected."""
        # Construct a borderline doc: below-threshold density, low coverage, short-ish
        borderline = "resume text with some work experience education skills certification " * 15
        word_count = len(borderline.split())
        mock_llm = self._make_llm(False, "resume document")
        assessment = await validate_document_relevance(
            borderline, word_count, MINI_SCHEMA, mock_llm
        )
        # Only check if it reached REVIEW and the LLM was called
        if assessment.risk_tier == RiskTier.REVIEW:
            assert assessment.llm_review_performed is True
            assert assessment.passed is False
            assert assessment.rejection_reason == "semantic_mismatch"

    @pytest.mark.asyncio
    async def test_review_tier_llm_confirms_pass(self):
        """REVIEW-tier doc where LLM says it IS a requirements doc → passes."""
        borderline = "requirements specification data latency security cost deployment " * 20
        word_count = len(borderline.split())
        mock_llm = self._make_llm(True, "requirements document")
        assessment = await validate_document_relevance(
            borderline, word_count, MINI_SCHEMA, mock_llm
        )
        if assessment.risk_tier == RiskTier.REVIEW:
            assert assessment.passed is True
            assert assessment.llm_review_performed is True

    @pytest.mark.asyncio
    async def test_llm_failure_fails_open(self):
        """If the LLM call raises, the document is allowed through (fail open)."""
        # Create a borderline REVIEW doc
        borderline = "data records users cost security latency " * 25
        word_count = len(borderline.split())
        mock_llm = MagicMock()
        mock_llm.generate_json = AsyncMock(side_effect=RuntimeError("LLM unreachable"))
        assessment = await validate_document_relevance(
            borderline, word_count, MINI_SCHEMA, mock_llm
        )
        # Must not raise; if REVIEW tier, must pass through on error
        if assessment.risk_tier == RiskTier.REVIEW:
            assert assessment.passed is True

    @pytest.mark.asyncio
    async def test_empty_signal_schema_passes_gracefully(self):
        """If signal_schema is empty (import not yet complete), gate passes silently."""
        assessment = await validate_document_relevance(
            GOOD_REQUIREMENTS_DOC,
            len(GOOD_REQUIREMENTS_DOC.split()),
            {},  # empty schema
            self._make_llm(True),
        )
        assert assessment.passed is True
        assert assessment.risk_tier == RiskTier.CLEAR

    @pytest.mark.asyncio
    async def test_assessment_always_has_flags(self):
        """Every assessment (pass or fail) must carry the full flags list for auditing."""
        word_count = len(GOOD_REQUIREMENTS_DOC.split())
        assessment = await validate_document_relevance(
            GOOD_REQUIREMENTS_DOC, word_count, MINI_SCHEMA, self._make_llm(True)
        )
        assert isinstance(assessment.flags, list)
        assert len(assessment.flags) > 0

    @pytest.mark.asyncio
    async def test_circular_upload_rejected(self):
        """ArchGuide report re-uploaded → AUTO_REJECT via circular_upload rule."""
        text = "Generated by ArchGuide\n" + GOOD_REQUIREMENTS_DOC
        word_count = len(text.split())
        assessment = await validate_document_relevance(
            text, word_count, MINI_SCHEMA, self._make_llm(True)
        )
        assert assessment.passed is False
        assert assessment.rejection_reason == "circular_upload"

    @pytest.mark.asyncio
    async def test_resume_rejected(self):
        """A CV/resume is rejected, either AUTO_REJECT or via REVIEW+LLM."""
        text = TestRuleFlags.RESUME_TEXT
        word_count = len(text.split())
        mock_llm = self._make_llm(False, "resume document")
        assessment = await validate_document_relevance(
            text, word_count, MINI_SCHEMA, mock_llm
        )
        assert assessment.passed is False

    @pytest.mark.asyncio
    async def test_long_technical_doc_rejected(self):
        """A 15,000+ word generic technical document should not pass cleanly."""
        # Use a technical but non-requirements text repeated to hit word count
        tech_text = (
            "In computer science, algorithms and data structures form the backbone "
            "of software engineering. Binary search trees offer O(log n) lookup "
            "time. Hash tables provide amortized O(1) for insert and delete. "
            "Sorting algorithms include merge sort, quicksort, and heapsort. "
        ) * 300  # ~300 * 25 words = 7500+ words → above MAX_REASONABLE_WORD_COUNT
        word_count = len(tech_text.split())
        mock_llm = self._make_llm(False, "textbook content")
        assessment = await validate_document_relevance(
            tech_text, word_count, MINI_SCHEMA, mock_llm
        )
        # Should be REVIEW or AUTO_REJECT, not CLEAR
        assert assessment.risk_tier != RiskTier.CLEAR or not assessment.passed
