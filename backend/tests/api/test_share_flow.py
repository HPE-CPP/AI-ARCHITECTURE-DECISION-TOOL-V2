"""
SHARE LINK FLOW
Reproduces the public /r/{id} -> GET /api/v1/share/{id} path end to end:
create a completed analysis, then fetch it through the no-auth share endpoint.
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
class TestShareFlow:

    def _create_completed(self, client) -> str:
        r = client.post("/api/v1/questionnaire", json=FLAT_ANSWERS)
        assert r.status_code == 200, r.text
        return r.json()["analysis_id"]

    def test_share_returns_completed_analysis(self, client):
        analysis_id = self._create_completed(client)
        r = client.get(f"/api/v1/share/{analysis_id}")
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["recommended"]
        assert data.get("confidence", 0) > 0

    def test_share_unknown_id_returns_404(self, client):
        import uuid
        r = client.get(f"/api/v1/share/{uuid.uuid4()}")
        assert r.status_code == 404

    def test_share_invalid_uuid_returns_404(self, client):
        r = client.get("/api/v1/share/not-a-uuid")
        assert r.status_code == 404

    def test_share_matches_analysis_id_used_in_link(self, client):
        """The share link is built from analysis_id; confirm that same id is
        what the share endpoint accepts (no id mismatch)."""
        analysis_id = self._create_completed(client)
        shared = client.get(f"/api/v1/share/{analysis_id}").json()
        assert shared["analysis_id"] == analysis_id
