"""
UNIT TESTS — Scoring Engine
Tests deterministic scoring logic, edge cases, normalization,
zero-signal fallback, sensitivity analysis, and why_not generation.
"""
import pytest
from services.scoring_engine import ScoringEngine


@pytest.mark.unit
class TestScoringEngineBasic:

    def setup_method(self):
        self.engine = ScoringEngine()

    def test_score_returns_all_architectures(self, complete_signals):
        result = self.engine.score(complete_signals)
        assert set(result["scores"].keys()) == {"RAG", "FineTuning", "CAG", "Hybrid"}

    def test_score_returns_required_keys(self, complete_signals):
        result = self.engine.score(complete_signals)
        required_keys = {"scores", "ranking", "recommended", "confidence",
                         "suitability", "factor_breakdown", "why_not", "architecture_details"}
        assert required_keys.issubset(result.keys())

    def test_scores_are_normalized_to_percentage(self, complete_signals):
        result = self.engine.score(complete_signals)
        for arch, score in result["scores"].items():
            assert 0.0 <= score <= 100.0, f"{arch} score {score} out of range"

    def test_ranking_has_all_four_architectures(self, complete_signals):
        result = self.engine.score(complete_signals)
        assert len(result["ranking"]) == 4
        assert set(result["ranking"]) == {"RAG", "FineTuning", "CAG", "Hybrid"}

    def test_recommended_matches_ranking_first(self, complete_signals):
        result = self.engine.score(complete_signals)
        assert result["recommended"] == result["ranking"][0]

    def test_ranking_is_descending_order(self, complete_signals):
        result = self.engine.score(complete_signals)
        scores = result["scores"]
        ranked_scores = [scores[arch] for arch in result["ranking"]]
        assert ranked_scores == sorted(ranked_scores, reverse=True)

    def test_confidence_is_between_zero_and_one(self, complete_signals):
        result = self.engine.score(complete_signals)
        assert 0.0 <= result["confidence"] <= 1.0

    def test_suitability_labels_are_valid(self, complete_signals):
        result = self.engine.score(complete_signals)
        valid_labels = {"Highly Suitable", "Suitable", "Moderately Suitable", "Not Recommended"}
        for arch, label in result["suitability"].items():
            assert label in valid_labels, f"Invalid suitability label '{label}' for {arch}"

    def test_architecture_details_has_all_fields(self, complete_signals):
        result = self.engine.score(complete_signals)
        for arch, details in result["architecture_details"].items():
            assert "full_name" in details
            assert "description" in details
            assert "strengths" in details
            assert "weaknesses" in details


@pytest.mark.unit
class TestScoringEngineEdgeCases:

    def setup_method(self):
        self.engine = ScoringEngine()

    def test_zero_signals_does_not_crash(self, empty_signals):
        """AUDIT FINDING AI-003: Zero signals must not return arbitrary result."""
        result = self.engine.score(empty_signals)
        # Scores should all be 0.0 when no signals
        for arch, score in result["scores"].items():
            assert score == 0.0, f"Expected 0.0 for {arch} with no signals, got {score}"

    def test_zero_signals_warns_via_low_confidence(self, empty_signals):
        """When no signals are present, confidence should be 0."""
        result = self.engine.score(empty_signals)
        assert result["confidence"] == 0.0

    def test_partial_signals_still_produces_ranking(self, partial_signals):
        result = self.engine.score(partial_signals)
        assert len(result["ranking"]) == 4
        assert result["recommended"] is not None

    def test_single_signal_produces_valid_result(self):
        signals = {
            "data_volatility": {"value": "high", "confidence": 0.9,
                                 "source_text": "updated daily", "page_number": 1},
            **{k: {"value": None, "confidence": 0.0, "source_text": "", "page_number": 0}
               for k in ["dataset_size", "query_volume", "latency_requirement",
                          "accuracy_requirement", "domain_specificity", "security_level",
                          "cost_sensitivity", "deployment_preference", "user_scale"]},
        }
        result = self.engine.score(signals)
        # RAG should be top for high data volatility
        assert result["recommended"] == "RAG"

    def test_low_confidence_signal_is_excluded(self):
        """Signals with confidence < 0.1 must not influence scores."""
        signals = {
            "dataset_size": {"value": "large", "confidence": 0.05,  # below threshold
                             "source_text": "lots of data", "page_number": 1},
            **{k: {"value": None, "confidence": 0.0, "source_text": "", "page_number": 0}
               for k in ["query_volume", "latency_requirement", "data_volatility",
                          "accuracy_requirement", "domain_specificity", "security_level",
                          "cost_sensitivity", "deployment_preference", "user_scale"]},
        }
        # The low-confidence signal should be skipped → all scores 0
        result = self.engine.score(signals)
        for score in result["scores"].values():
            assert score == 0.0

    def test_invalid_signal_value_is_handled_gracefully(self):
        """Values not in SCORING_RULES must not crash the engine."""
        signals = {
            "dataset_size": {"value": "INVENTED_INVALID_VALUE", "confidence": 0.9,
                             "source_text": "test", "page_number": 1},
            **{k: {"value": None, "confidence": 0.0, "source_text": "", "page_number": 0}
               for k in ["query_volume", "latency_requirement", "data_volatility",
                          "accuracy_requirement", "domain_specificity", "security_level",
                          "cost_sensitivity", "deployment_preference", "user_scale"]},
        }
        result = self.engine.score(signals)
        # Should not raise, invalid values are skipped
        assert isinstance(result["scores"], dict)

    def test_confidence_above_one_is_clamped(self):
        """Overflow confidence values must not produce scores > 100."""
        signals = {
            "dataset_size": {"value": "large", "confidence": 999.0,
                             "source_text": "test", "page_number": 1},
            **{k: {"value": None, "confidence": 0.0, "source_text": "", "page_number": 0}
               for k in ["query_volume", "latency_requirement", "data_volatility",
                          "accuracy_requirement", "domain_specificity", "security_level",
                          "cost_sensitivity", "deployment_preference", "user_scale"]},
        }
        result = self.engine.score(signals)
        for score in result["scores"].values():
            assert score <= 100.0


@pytest.mark.unit
class TestScoringEngineWhy_Not:

    def setup_method(self):
        self.engine = ScoringEngine()

    def test_why_not_excludes_recommended(self, complete_signals):
        result = self.engine.score(complete_signals)
        recommended = result["recommended"]
        assert recommended not in result["why_not"]

    def test_why_not_covers_all_non_recommended(self, complete_signals):
        result = self.engine.score(complete_signals)
        recommended = result["recommended"]
        non_recommended = set(result["ranking"]) - {recommended}
        assert set(result["why_not"].keys()) == non_recommended

    def test_why_not_contains_score_gap(self, complete_signals):
        result = self.engine.score(complete_signals)
        for arch, reason in result["why_not"].items():
            assert "points lower" in reason


@pytest.mark.unit
class TestSensitivityAnalysis:

    def setup_method(self):
        self.engine = ScoringEngine()

    def test_sensitivity_returns_required_keys(self, complete_signals):
        result = self.engine.sensitivity_analysis(complete_signals)
        assert "is_stable" in result
        assert "stability_score" in result
        assert "instabilities" in result

    def test_stability_score_in_range(self, complete_signals):
        result = self.engine.sensitivity_analysis(complete_signals)
        assert 0.0 <= result["stability_score"] <= 1.0

    def test_instability_entries_have_required_fields(self, complete_signals):
        result = self.engine.sensitivity_analysis(complete_signals)
        for inst in result["instabilities"]:
            assert "signal" in inst
            assert "original_value" in inst
            assert "perturbed_value" in inst
            assert "original_recommendation" in inst
            assert "new_recommendation" in inst

    def test_does_not_mutate_input_signals(self, complete_signals):
        """AUDIT FINDING AI-003: Sensitivity analysis must not corrupt input dict."""
        import copy
        original = copy.deepcopy(complete_signals)
        self.engine.sensitivity_analysis(complete_signals)
        assert complete_signals == original

    def test_empty_signals_sensitivity_does_not_crash(self, empty_signals):
        result = self.engine.sensitivity_analysis(empty_signals)
        assert isinstance(result, dict)
        assert "is_stable" in result


@pytest.mark.unit
class TestOverallConfidence:

    def setup_method(self):
        self.engine = ScoringEngine()

    def test_all_high_confidence_signals_gives_high_overall(self, complete_signals):
        result = self.engine.score(complete_signals)
        # With 10 signals all at ~0.8 confidence, overall should be > 0.5
        assert result["confidence"] > 0.5

    def test_all_zero_confidence_gives_zero_overall(self, empty_signals):
        result = self.engine.score(empty_signals)
        assert result["confidence"] == 0.0
