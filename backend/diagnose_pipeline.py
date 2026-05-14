"""Run the actual heuristic extractor on each test doc and report
what signals come out + what arch scores. This bypasses the LLM so we
see deterministic behavior — what the pipeline would do at minimum."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from services.signal_extractor import SignalExtractor, SIGNAL_SCHEMA
from services.scoring_engine import ScoringEngine

DOCS = {
    "01_RAG":        "../tests/docs/01_perfect_rag_candidate.md",
    "02_FT":         "../tests/docs/02_perfect_finetuning_candidate.md",
    "03_CAG":        "../tests/docs/03_perfect_cag_candidate.md",
    "04_Hybrid":     "../tests/docs/04_perfect_hybrid_candidate.md",
    "10_Hybrid_Big": "../tests/docs/10_stress_test_large_doc.md",
}

EXPECTED = {
    "01_RAG": "RAG",
    "02_FT": "FineTuning",
    "03_CAG": "CAG",
    "04_Hybrid": "Hybrid",
    "10_Hybrid_Big": "Hybrid",
}


def main():
    here = Path(__file__).parent
    extractor = SignalExtractor(llm_client=None)
    engine = ScoringEngine()

    for name, path in DOCS.items():
        text = (here / path).read_text(encoding="utf-8")
        # Single page = whole doc
        pages = [{"page_number": 1, "text": text}]

        # Force heuristic extraction (no LLM)
        signals = extractor._heuristic_extraction(text, pages)
        # Merge with keyword extraction like the real pipeline does
        kw = extractor._keyword_extraction(text, pages)
        merged = extractor._merge_signals(kw, signals)

        result = engine.score(merged)
        got = result["recommended"]
        scores = result["scores"]
        expected = EXPECTED[name]
        status = "PASS" if got == expected else "FAIL"

        print(f"\n=== {name} ({status} — expected {expected}, got {got}) ===")
        print(f"Scores: RAG={scores['RAG']}  FT={scores['FineTuning']}  CAG={scores['CAG']}  Hybrid={scores['Hybrid']}")
        print("Extracted signals:")
        for key in SIGNAL_SCHEMA:
            s = merged.get(key, {})
            val = s.get("value")
            conf = s.get("confidence", 0)
            print(f"  {key:25} = {str(val):20} (conf={conf:.2f})")


if __name__ == "__main__":
    main()
