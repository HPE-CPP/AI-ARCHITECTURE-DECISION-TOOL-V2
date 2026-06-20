"""
SIGNAL COUNT CONSISTENCY
The app uses 12 architecture signals. This used to be 10; the two newer signals
are citation_requirement and context_size. These tests lock every place that
enumerates signals to the same 12 so a structure can never silently drift back
to 10 (which would drop signals from analysis, scoring, chat, or the form).
"""
import pytest

EXPECTED_SIGNALS = {
    "dataset_size",
    "query_volume",
    "latency_requirement",
    "data_volatility",
    "accuracy_requirement",
    "domain_specificity",
    "security_level",
    "cost_sensitivity",
    "deployment_preference",
    "user_scale",
    "citation_requirement",
    "context_size",
}


def test_signal_schema_and_options_have_12():
    from services.signal_extractor import SIGNAL_SCHEMA, SIGNAL_OPTIONS
    assert set(SIGNAL_SCHEMA) == EXPECTED_SIGNALS
    assert set(SIGNAL_OPTIONS) == EXPECTED_SIGNALS


def test_scoring_engine_covers_all_12():
    from services.scoring_engine import SCORING_RULES, SIGNAL_WEIGHTS
    assert set(SCORING_RULES) == EXPECTED_SIGNALS
    assert set(SIGNAL_WEIGHTS) == EXPECTED_SIGNALS


def test_chat_signal_labels_have_12():
    from app.routers.chat import SIGNAL_LABELS
    assert set(SIGNAL_LABELS) == EXPECTED_SIGNALS


def test_questionnaire_input_has_12_signal_fields():
    from app.schemas.session import QuestionnaireInput
    assert EXPECTED_SIGNALS <= set(QuestionnaireInput.model_fields)


def test_questionnaire_options_endpoint_returns_12(client):
    r = client.get("/api/v1/questionnaire/options")
    assert r.status_code == 200
    assert set(r.json()["signals"]) == EXPECTED_SIGNALS


def test_questionnaire_extraction_produces_12_signals():
    from services.signal_extractor import SignalExtractor
    # extract_from_questionnaire is pure mapping — no LLM call is made.
    extractor = SignalExtractor(None)
    signals = extractor.extract_from_questionnaire({"dataset_size": "large"})
    assert set(signals) == EXPECTED_SIGNALS


def test_extraction_prompt_demands_12_including_example():
    """The document-upload prompt must ask for 12 AND show the two new signals
    in its example output — otherwise the LLM mimics the example and drops them."""
    from services.signal_extractor import EXTRACTION_PROMPT
    assert "extract 12 architecture signals" in EXTRACTION_PROMPT
    # Each new signal appears once in the schema list and again in the example.
    assert EXTRACTION_PROMPT.count("citation_requirement") >= 2
    assert EXTRACTION_PROMPT.count("context_size") >= 2
