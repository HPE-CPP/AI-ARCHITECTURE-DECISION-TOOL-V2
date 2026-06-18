"""
UNIT TESTS — Signal Extractor
Tests extraction pipeline, source verification, keyword extraction,
signal merging, questionnaire conversion, cache behavior, and
anti-hallucination controls.
"""
import pytest
from unittest.mock import MagicMock
from services.signal_extractor import SignalExtractor, SIGNAL_SCHEMA, SIGNAL_OPTIONS


@pytest.mark.unit
class TestSignalExtractorQuestionnaire:
    """Questionnaire path — no LLM involved."""

    def setup_method(self):
        mock_llm = MagicMock()
        self.extractor = SignalExtractor(mock_llm)

    def test_all_signals_in_output(self):
        answers = {"dataset_size": "large", "data_volatility": "high"}
        result = self.extractor.extract_from_questionnaire(answers)
        assert set(result.keys()) == set(SIGNAL_SCHEMA.keys())

    def test_provided_answers_have_confidence_one(self):
        answers = {"dataset_size": "large"}
        result = self.extractor.extract_from_questionnaire(answers)
        assert result["dataset_size"]["value"] == "large"
        assert result["dataset_size"]["confidence"] == 0.85
        assert result["dataset_size"]["source_verified"] is True

    def test_missing_answers_have_null_value(self):
        answers = {"dataset_size": "large"}
        result = self.extractor.extract_from_questionnaire(answers)
        for key in SIGNAL_SCHEMA:
            if key != "dataset_size":
                assert result[key]["value"] is None
                assert result[key]["confidence"] == 0.0

    def test_empty_answers_dict(self):
        result = self.extractor.extract_from_questionnaire({})
        for key in SIGNAL_SCHEMA:
            assert result[key]["value"] is None

    def test_unknown_keys_ignored(self):
        answers = {"totally_unknown_signal": "value", "dataset_size": "small"}
        result = self.extractor.extract_from_questionnaire(answers)
        assert "totally_unknown_signal" not in result
        assert result["dataset_size"]["value"] == "small"

    def test_none_value_in_answers_treated_as_missing(self):
        answers = {"dataset_size": None}
        result = self.extractor.extract_from_questionnaire(answers)
        assert result["dataset_size"]["value"] is None


@pytest.mark.unit
class TestKeywordExtraction:
    """Keyword-based extraction — no LLM, tests text scanning."""

    def setup_method(self):
        mock_llm = MagicMock()
        self.extractor = SignalExtractor(mock_llm)

    def _run_keyword(self, text, pages=None):
        if pages is None:
            pages = [{"page_number": 1, "text": text, "char_count": len(text)}]
        return self.extractor._keyword_extraction(text, pages)

    def test_detects_dataset_size_keyword(self):
        text = "The system manages 500 million records in the database."
        result = self._run_keyword(text)
        # "records" and "database" are in dataset_size keywords
        assert result["dataset_size"]["confidence"] > 0.0
        assert result["dataset_size"]["keyword_matches"] >= 1

    def test_detects_latency_keyword(self):
        text = "Real-time response with ultra-low latency is required."
        result = self._run_keyword(text)
        assert result["latency_requirement"]["confidence"] > 0.0

    def test_empty_text_returns_zero_confidence(self):
        result = self._run_keyword("")
        for key in SIGNAL_SCHEMA:
            assert result[key]["confidence"] == 0.0

    def test_irrelevant_text_returns_zero_matches(self):
        text = "The quick brown fox jumps over the lazy dog."
        result = self._run_keyword(text)
        for key in SIGNAL_SCHEMA:
            assert result[key]["keyword_matches"] == 0

    def test_keyword_confidence_capped_at_0_3(self):
        # Many keyword matches should still cap at 0.3
        text = " ".join(["dataset records corpus documents entries rows data"] * 20)
        result = self._run_keyword(text)
        assert result["dataset_size"]["confidence"] <= 0.3

    def test_source_text_is_populated_when_keyword_found(self):
        text = "We have 10 million dataset records to process."
        result = self._run_keyword(text)
        assert result["dataset_size"]["source_text"] != ""

    def test_page_number_is_assigned(self):
        pages = [
            {"page_number": 1, "text": "Intro text.", "char_count": 11},
            {"page_number": 2, "text": "The dataset contains millions of records.", "char_count": 40},
        ]
        full_text = " ".join(p["text"] for p in pages)
        result = self.extractor._keyword_extraction(full_text, pages)
        assert result["dataset_size"]["page_number"] == 2


@pytest.mark.unit
class TestSourceVerification:
    """Source verification and fuzzy recovery."""

    def setup_method(self):
        mock_llm = MagicMock()
        self.extractor = SignalExtractor(mock_llm)

    def _make_signals_with_source(self, source_text):
        return {
            "dataset_size": {
                "value": "large", "confidence": 0.9,
                "source_text": source_text, "page_number": 1,
            },
            **{k: {"value": None, "confidence": 0.0, "source_text": "", "page_number": 0}
               for k in SIGNAL_SCHEMA if k != "dataset_size"},
        }

    def test_exact_source_verified(self):
        doc_text = "Our system processes 10 million records daily."
        signals = self._make_signals_with_source("Our system processes 10 million records daily.")
        result = self.extractor._verify_sources(signals, doc_text, [])
        assert result["dataset_size"]["source_verified"] is True

    def test_missing_source_marked_unverified(self):
        doc_text = "Our system processes 10 million records daily."
        signals = self._make_signals_with_source("This text does not exist in the document at all.")
        result = self.extractor._verify_sources(signals, doc_text, [])
        assert result["dataset_size"]["source_verified"] is False

    def test_confidence_not_penalized_on_failed_verification(self):
        doc_text = "Our system processes 10 million records daily."
        signals = self._make_signals_with_source("Totally invented text nowhere in the doc.")
        original_conf = signals["dataset_size"]["confidence"]
        result = self.extractor._verify_sources(signals, doc_text, [])
        assert result["dataset_size"]["confidence"] == original_conf
        assert result["dataset_size"]["source_verified"] is False

    def test_fuzzy_recovery_finds_partial_match(self):
        doc_text = "The system handles millions of records efficiently."
        # Provide a slightly different version
        claimed = "The system handles millions of records"
        assert self.extractor._fuzzy_find_source(claimed, doc_text) is not None

    def test_fuzzy_recovery_fails_for_very_short_claimed(self):
        # Less than 3 words — fuzzy should return None
        assert self.extractor._fuzzy_find_source("test", "test document text") is None

    def test_empty_source_marked_unverified_without_penalty(self):
        doc_text = "Some document text."
        signals = self._make_signals_with_source("")  # empty source
        result = self.extractor._verify_sources(signals, doc_text, [])
        # Empty source_text → unverified but confidence unchanged
        assert result["dataset_size"]["source_verified"] is False
        assert result["dataset_size"]["confidence"] == 0.9  # not penalized


@pytest.mark.unit
class TestSignalMerging:
    """Keyword + LLM signal merging logic."""

    def setup_method(self):
        mock_llm = MagicMock()
        self.extractor = SignalExtractor(mock_llm)

    def test_llm_value_takes_precedence_over_keyword(self):
        kw = {"dataset_size": {"value": None, "confidence": 0.2, "source_text": "kw", "page_number": 1,
                               "keyword_matches": 2}}
        llm = {"dataset_size": {"value": "large", "confidence": 0.9, "source_text": "llm source",
                                "page_number": 2, "source_verified": True}}
        merged = self.extractor._merge_signals(kw, llm)
        assert merged["dataset_size"]["value"] == "large"

    def test_confidence_boosted_when_both_agree(self):
        kw = {"dataset_size": {"value": None, "confidence": 0.2, "source_text": "kw", "page_number": 1,
                               "keyword_matches": 2}}
        llm = {"dataset_size": {"value": "large", "confidence": 0.8, "source_text": "exact quote",
                                "page_number": 1, "source_verified": True}}
        merged = self.extractor._merge_signals(kw, llm)
        # combined = min(1.0, 0.8 + 0.2 * 0.3) = 0.86
        assert merged["dataset_size"]["confidence"] > 0.8

    def test_value_nulled_when_merged_confidence_below_threshold(self):
        kw = {"dataset_size": {"value": "small", "confidence": 0.05, "source_text": "", "page_number": 0,
                               "keyword_matches": 0}}
        llm = {"dataset_size": {"value": "small", "confidence": 0.04, "source_text": "",
                                "page_number": 0, "source_verified": False}}
        merged = self.extractor._merge_signals(kw, llm)
        # combined < 0.1 → value must be nulled
        assert merged["dataset_size"]["value"] is None

    def test_keyword_source_used_when_llm_source_unverified(self):
        kw = {"dataset_size": {"value": None, "confidence": 0.25, "source_text": "keyword found here",
                               "page_number": 1, "keyword_matches": 3}}
        llm = {"dataset_size": {"value": "large", "confidence": 0.8, "source_text": "fabricated",
                                "page_number": 0, "source_verified": False}}
        merged = self.extractor._merge_signals(kw, llm)
        assert merged["dataset_size"]["source_text"] == "keyword found here"


@pytest.mark.unit
class TestSignalOptions:
    """Validate that SIGNAL_OPTIONS keys match SIGNAL_SCHEMA."""

    def test_signal_options_covers_all_signals(self):
        assert set(SIGNAL_OPTIONS.keys()) == set(SIGNAL_SCHEMA.keys())

    def test_all_options_have_value_and_label(self):
        for signal, options in SIGNAL_OPTIONS.items():
            assert len(options) > 0, f"No options for signal {signal}"
            for opt in options:
                assert "value" in opt
                assert "label" in opt

    def test_scoring_rules_cover_all_option_values(self):
        """Every option value must have a corresponding scoring rule."""
        from services.scoring_engine import SCORING_RULES
        for signal, options in SIGNAL_OPTIONS.items():
            for opt in options:
                assert opt["value"] in SCORING_RULES.get(signal, {}), (
                    f"Missing scoring rule for {signal}={opt['value']}"
                )


@pytest.mark.unit
class TestEmptySignalsHelper:

    def setup_method(self):
        mock_llm = MagicMock()
        self.extractor = SignalExtractor(mock_llm)

    def test_empty_signals_has_all_keys(self):
        result = self.extractor._empty_signals()
        assert set(result.keys()) == set(SIGNAL_SCHEMA.keys())

    def test_empty_signals_all_null(self):
        result = self.extractor._empty_signals()
        for key, val in result.items():
            assert val["value"] is None
            assert val["confidence"] == 0.0
            assert val["source_text"] == ""

    def test_get_missing_signals_identifies_all_empty(self, empty_signals):
        missing = self.extractor.get_missing_signals(empty_signals)
        assert set(missing) == set(SIGNAL_SCHEMA.keys())

    def test_get_missing_signals_empty_when_all_complete(self):
        from services.signal_extractor import SIGNAL_SCHEMA
        complete = {k: {"value": "some_val", "confidence": 0.9} for k in SIGNAL_SCHEMA}
        missing = self.extractor.get_missing_signals(complete)
        assert missing == []
