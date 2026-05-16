"""
Document Processing Service
Handles PDF, DOCX, and TXT file parsing with page-level text extraction.
"""
import os
import tempfile
from typing import Optional
import fitz  # PyMuPDF
from docx import Document

# Flat set of all signal keywords used for page relevance scoring.
# Populated by signal_extractor at import time to avoid circular deps.
_SIGNAL_KEYWORDS: frozenset[str] = frozenset()


def register_signal_keywords(keywords: frozenset[str]) -> None:
    global _SIGNAL_KEYWORDS
    _SIGNAL_KEYWORDS = keywords


def score_page_relevance(text: str) -> int:
    """Count unique signal keywords found on a single page."""
    text_lower = text.lower()
    return sum(1 for kw in _SIGNAL_KEYWORDS if kw in text_lower)


def get_relevant_pages(pages: list[dict], min_score: int = 1) -> list[dict]:
    """
    Return pages that contain at least `min_score` signal keywords,
    sorted descending by relevance score then restored to original page order.
    Falls back to all pages if none pass the threshold.
    """
    scored = [(page, score_page_relevance(page.get("text", ""))) for page in pages]
    relevant = [p for p, s in scored if s >= min_score]
    if not relevant:
        return pages  # nothing matched — keep everything
    # Restore document order so LLM sees coherent narrative
    relevant_set = {id(p) for p in relevant}
    return [p for p in pages if id(p) in relevant_set]


class DocumentParser:
    """Multi-format document parser with page-level extraction."""

    ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt"}
    MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB

    def __init__(self):
        self.supported_formats = {
            ".pdf": self._parse_pdf,
            ".docx": self._parse_docx,
            ".txt": self._parse_txt,
        }

    def validate_file(self, filename: str, file_size: int) -> tuple[bool, str]:
        """Validate file extension and size."""
        ext = os.path.splitext(filename)[1].lower()
        if ext not in self.ALLOWED_EXTENSIONS:
            return False, f"Unsupported file type: {ext}. Allowed: {', '.join(self.ALLOWED_EXTENSIONS)}"
        if file_size > self.MAX_FILE_SIZE:
            return False, f"File too large ({file_size / 1024 / 1024:.1f}MB). Max: {self.MAX_FILE_SIZE / 1024 / 1024:.0f}MB"
        return True, "OK"

    async def parse(self, file_path: str, filename: str) -> dict:
        """Parse a document and return structured text with page numbers."""
        ext = os.path.splitext(filename)[1].lower()
        parser = self.supported_formats.get(ext)
        if not parser:
            raise ValueError(f"Unsupported file format: {ext}")

        pages = parser(file_path)
        full_text = "\n\n".join([p["text"] for p in pages if p["text"].strip()])

        return {
            "filename": filename,
            "format": ext,
            "total_pages": len(pages),
            "pages": pages,
            "full_text": full_text,
            "char_count": len(full_text),
            "word_count": len(full_text.split()),
        }

    def _parse_pdf(self, file_path: str) -> list[dict]:
        """Extract text from PDF with page numbers."""
        pages = []
        try:
            doc = fitz.open(file_path)
            for page_num in range(len(doc)):
                page = doc[page_num]
                text = page.get_text("text")
                pages.append({
                    "page_number": page_num + 1,
                    "text": text.strip(),
                    "char_count": len(text.strip()),
                })
            doc.close()
        except Exception as e:
            raise RuntimeError(f"Failed to parse PDF: {str(e)}")
        return pages

    def _parse_docx(self, file_path: str) -> list[dict]:
        """Extract text from DOCX. Treats the whole document as one page."""
        try:
            doc = Document(file_path)
            paragraphs = []
            for para in doc.paragraphs:
                if para.text.strip():
                    paragraphs.append(para.text.strip())
            full_text = "\n\n".join(paragraphs)
            return [{
                "page_number": 1,
                "text": full_text,
                "char_count": len(full_text),
            }]
        except Exception as e:
            raise RuntimeError(f"Failed to parse DOCX: {str(e)}")

    def _parse_txt(self, file_path: str) -> list[dict]:
        """Extract text from TXT file."""
        try:
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                text = f.read()
            return [{
                "page_number": 1,
                "text": text.strip(),
                "char_count": len(text.strip()),
            }]
        except Exception as e:
            raise RuntimeError(f"Failed to parse TXT: {str(e)}")


# Section Detection
SECTION_KEYWORDS = {
    "overview": ["overview", "introduction", "background", "summary", "purpose", "scope", "objective"],
    "functional_requirements": ["functional", "features", "use case", "user story", "capability", "functionality"],
    "non_functional_requirements": ["non-functional", "nfr", "performance", "scalability", "reliability", "availability"],
    "data_description": ["data", "dataset", "database", "schema", "data source", "data model", "corpus"],
    "constraints": ["constraint", "limitation", "restriction", "boundary", "assumption"],
    "performance": ["performance", "latency", "throughput", "response time", "speed", "sla"],
    "security": ["security", "privacy", "compliance", "gdpr", "hipaa", "encryption", "authentication", "authorization"],
}


def detect_sections(text: str) -> dict[str, list[str]]:
    """Detect document sections using keyword heuristics.
    Returns dict mapping section type to list of relevant text chunks.
    """
    lines = text.split("\n")
    sections: dict[str, list[str]] = {key: [] for key in SECTION_KEYWORDS}
    current_section: Optional[str] = None
    current_buffer: list[str] = []

    for line in lines:
        line_lower = line.lower().strip()
        detected = None
        for section, keywords in SECTION_KEYWORDS.items():
            if any(kw in line_lower for kw in keywords):
                # Check if this looks like a heading (short line with keyword)
                if len(line_lower.split()) <= 8:
                    detected = section
                    break

        if detected:
            # Save previous buffer
            if current_section and current_buffer:
                sections[current_section].append("\n".join(current_buffer))
            current_section = detected
            current_buffer = [line.strip()]
        elif current_section:
            current_buffer.append(line.strip())

    # Flush last buffer
    if current_section and current_buffer:
        sections[current_section].append("\n".join(current_buffer))

    return sections
