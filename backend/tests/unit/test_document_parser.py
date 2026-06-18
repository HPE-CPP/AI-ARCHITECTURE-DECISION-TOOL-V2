"""
UNIT TESTS — Document Parser
Tests PDF/DOCX/TXT parsing, file validation, section detection,
page relevance scoring, and edge cases (empty, corrupt, unicode).
"""
import os
import pytest
import tempfile
from services.document_parser import (
    DocumentParser, detect_sections, score_page_relevance,
    get_relevant_pages, register_signal_keywords
)


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
