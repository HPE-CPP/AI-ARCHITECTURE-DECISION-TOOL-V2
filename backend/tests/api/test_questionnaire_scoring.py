"""
QUESTIONNAIRE SCORING REGRESSION
Guards the guided-flow bug where answers were wrapped under an "answers" key,
arrived as all-None signals, and scored 0. These tests assert a REAL, non-zero
recommendation comes back — for both the flat payload (what the frontend now
sends) and the legacy wrapped payload (which the backend still tolerates).
"""
import pytest

FLAT_ANSWERS = {
    "dataset_size": "large",
    "query_volume": "high",
    "latency_requirement": "strict",
    "data_volatility": "moderate",
    "accuracy_requirement": "high",
    "domain_specificity": "specialized",
    "security_level": "high",
    "cost_sensitivity": "moderate",
    "deployment_preference": "cloud",
    "user_scale": "large",
    "citation_requirement": "high",
    "context_size": "large",
}


@pytest.mark.api
class TestQuestionnaireScoring:

    def test_flat_payload_scores_non_zero(self, client):
        """The shape the frontend now sends must produce a real recommendation."""
        r = client.post("/api/v1/questionnaire", json=FLAT_ANSWERS)
        assert r.status_code == 200
        data = r.json()
        assert data["recommended"], "No architecture recommended"
        assert data["confidence"] and data["confidence"] > 0, (
            f"Confidence scored 0 — signals did not reach the scoring engine: {data.get('confidence')}"
        )

    def test_wrapped_payload_still_scores_non_zero(self, client):
        """Legacy {answers: {...}} shape must keep working via the unwrap validator."""
        r = client.post("/api/v1/questionnaire", json={"answers": FLAT_ANSWERS})
        assert r.status_code == 200
        data = r.json()
        assert data["recommended"]
        assert data["confidence"] and data["confidence"] > 0

    def test_signals_actually_populated(self, client):
        """The returned signals must carry the submitted values, not nulls."""
        r = client.post("/api/v1/questionnaire", json=FLAT_ANSWERS)
        assert r.status_code == 200
        signals = r.json().get("signals") or {}
        assert signals.get("dataset_size", {}).get("value") == "large"
        assert signals.get("security_level", {}).get("value") == "high"

    def test_both_shapes_agree(self, client):
        """Flat and wrapped payloads must yield the same recommendation."""
        flat = client.post("/api/v1/questionnaire", json=FLAT_ANSWERS).json()
        wrapped = client.post("/api/v1/questionnaire", json={"answers": FLAT_ANSWERS}).json()
        assert flat["recommended"] == wrapped["recommended"]
