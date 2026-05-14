"""
Architecture Scoring Engine
Deterministic rule-based scoring for RAG, Fine-Tuning, CAG, and Hybrid architectures.
"""
import copy
import logging
from typing import Optional
from services.signal_extractor import SIGNAL_SCHEMA

logger = logging.getLogger(__name__)

# Scoring rules: each signal value maps to score adjustments for each architecture
# Format: signal_value -> {architecture: score_delta}
SCORING_RULES: dict[str, dict[str, dict[str, float]]] = {
    # Each value maps to how well each architecture fits that signal value.
    # Hybrid should only compete when signals genuinely require BOTH retrieval
    # flexibility AND fine-tuned model accuracy — not as a universal fallback.
    "dataset_size": {
        "small":      {"RAG": 0.3, "FineTuning": 0.6, "CAG": 0.9, "Hybrid": 0.3},
        "medium":     {"RAG": 0.7, "FineTuning": 0.7, "CAG": 0.5, "Hybrid": 0.5},
        "large":      {"RAG": 0.9, "FineTuning": 0.5, "CAG": 0.2, "Hybrid": 0.65},
        "very_large": {"RAG": 1.0, "FineTuning": 0.3, "CAG": 0.1, "Hybrid": 0.7},
    },
    "query_volume": {
        "low":       {"RAG": 0.5, "FineTuning": 0.4, "CAG": 0.8, "Hybrid": 0.3},
        "medium":    {"RAG": 0.7, "FineTuning": 0.6, "CAG": 0.5, "Hybrid": 0.5},
        "high":      {"RAG": 0.8, "FineTuning": 0.8, "CAG": 0.3, "Hybrid": 0.6},
        "very_high": {"RAG": 0.6, "FineTuning": 0.9, "CAG": 0.1, "Hybrid": 0.7},
    },
    "latency_requirement": {
        # Hybrid adds a retrieval step — strict/ultra-low latency strongly disfavors it.
        "relaxed":   {"RAG": 0.8, "FineTuning": 0.5, "CAG": 0.7, "Hybrid": 0.4},
        "moderate":  {"RAG": 0.7, "FineTuning": 0.7, "CAG": 0.5, "Hybrid": 0.5},
        "strict":    {"RAG": 0.4, "FineTuning": 0.9, "CAG": 0.3, "Hybrid": 0.55},
        "ultra_low": {"RAG": 0.2, "FineTuning": 1.0, "CAG": 0.2, "Hybrid": 0.4},
    },
    "data_volatility": {
        # High volatility is RAG's unique strength — Hybrid's FT component hurts here.
        "static":   {"RAG": 0.5, "FineTuning": 0.9, "CAG": 0.8, "Hybrid": 0.4},
        "low":      {"RAG": 0.7, "FineTuning": 0.7, "CAG": 0.6, "Hybrid": 0.5},
        "moderate": {"RAG": 0.9, "FineTuning": 0.4, "CAG": 0.3, "Hybrid": 0.6},
        "high":     {"RAG": 1.0, "FineTuning": 0.2, "CAG": 0.1, "Hybrid": 0.5},
    },
    "accuracy_requirement": {
        # Rebalanced: grounded retrieval with citations is RAG's defining
        # strength, so RAG should match or beat FT on very_high accuracy when
        # the failure mode is "wrong answers / hallucinations". FT still
        # dominates 'critical' (regulatory/clinical) because that's where
        # internalised domain understanding matters more than citations.
        "moderate":  {"RAG": 0.6, "FineTuning": 0.5, "CAG": 0.7, "Hybrid": 0.4},
        "high":      {"RAG": 0.85, "FineTuning": 0.7, "CAG": 0.5, "Hybrid": 0.6},
        "very_high": {"RAG": 0.9, "FineTuning": 0.8, "CAG": 0.4, "Hybrid": 0.7},
        "critical":  {"RAG": 0.78, "FineTuning": 0.95, "CAG": 0.2, "Hybrid": 0.7},
    },
    "domain_specificity": {
        # Rebalanced: 'specialized' (internal company knowledge, standard
        # industry domain) is well-served by RAG with a domain corpus.
        # 'highly_specialized' (clinical medicine, derivatives, niche
        # research) genuinely needs FT for vocabulary/reasoning patterns
        # that prompting cannot convey. CAG remains low because, by
        # definition, specialized corpora are usually too large for context.
        "general":            {"RAG": 0.7, "FineTuning": 0.3, "CAG": 0.8, "Hybrid": 0.3},
        "moderate":           {"RAG": 0.8, "FineTuning": 0.6, "CAG": 0.5, "Hybrid": 0.5},
        "specialized":        {"RAG": 0.85, "FineTuning": 0.75, "CAG": 0.45, "Hybrid": 0.6},
        "highly_specialized": {"RAG": 0.68, "FineTuning": 0.95, "CAG": 0.25, "Hybrid": 0.65},
    },
    "security_level": {
        "standard": {"RAG": 0.8, "FineTuning": 0.7, "CAG": 0.7, "Hybrid": 0.5},
        "elevated": {"RAG": 0.7, "FineTuning": 0.7, "CAG": 0.5, "Hybrid": 0.6},
        "high":     {"RAG": 0.5, "FineTuning": 0.8, "CAG": 0.3, "Hybrid": 0.65},
        "critical": {"RAG": 0.3, "FineTuning": 0.9, "CAG": 0.1, "Hybrid": 0.6},
    },
    "cost_sensitivity": {
        # Hybrid is the most expensive option — high/very_high cost sensitivity should
        # strongly disfavor it.
        "low":       {"RAG": 0.7, "FineTuning": 0.8, "CAG": 0.5, "Hybrid": 0.65},
        "moderate":  {"RAG": 0.7, "FineTuning": 0.6, "CAG": 0.6, "Hybrid": 0.5},
        "high":      {"RAG": 0.6, "FineTuning": 0.4, "CAG": 0.8, "Hybrid": 0.3},
        "very_high": {"RAG": 0.5, "FineTuning": 0.2, "CAG": 0.9, "Hybrid": 0.2},
    },
    "deployment_preference": {
        # FIX: "hybrid deployment" (cloud + on-prem mix) ≠ "Hybrid architecture".
        # Removed circular 1.0 self-boost; Hybrid gets a modest advantage (0.75) since
        # hybrid deployment environments benefit from its flexibility, not a perfect score.
        "cloud":      {"RAG": 0.9, "FineTuning": 0.7, "CAG": 0.6, "Hybrid": 0.6},
        "on_premise": {"RAG": 0.5, "FineTuning": 0.8, "CAG": 0.7, "Hybrid": 0.6},
        "hybrid":     {"RAG": 0.7, "FineTuning": 0.6, "CAG": 0.4, "Hybrid": 0.75},
        "edge":       {"RAG": 0.3, "FineTuning": 0.9, "CAG": 0.5, "Hybrid": 0.4},
    },
    "user_scale": {
        # FIX: Removed Hybrid=1.0 for enterprise. Enterprise scale favors RAG and
        # FineTuning equally; Hybrid is an option, not the automatic winner.
        "small":      {"RAG": 0.5, "FineTuning": 0.5, "CAG": 0.9, "Hybrid": 0.2},
        "medium":     {"RAG": 0.7, "FineTuning": 0.6, "CAG": 0.5, "Hybrid": 0.5},
        "large":      {"RAG": 0.9, "FineTuning": 0.7, "CAG": 0.2, "Hybrid": 0.65},
        "enterprise": {"RAG": 0.8, "FineTuning": 0.8, "CAG": 0.1, "Hybrid": 0.75},
    },
}

# Weight importance of each signal
SIGNAL_WEIGHTS: dict[str, float] = {
    "dataset_size": 1.2,
    "query_volume": 1.0,
    "latency_requirement": 1.1,
    "data_volatility": 1.3,
    "accuracy_requirement": 1.2,
    "domain_specificity": 1.1,
    "security_level": 0.9,
    "cost_sensitivity": 0.8,
    "deployment_preference": 0.7,
    "user_scale": 0.8,
}

ARCHITECTURE_DESCRIPTIONS = {
    "RAG": {
        "full_name": "Retrieval-Augmented Generation",
        "description": "Combines a retrieval system with a generative LLM. Best for dynamic knowledge bases with frequently changing data.",
        "strengths": ["Dynamic data handling", "No retraining needed", "Transparent sources", "Cost-effective updates"],
        "weaknesses": ["Higher latency", "Retrieval quality dependency", "Context window limits"],
    },
    "FineTuning": {
        "full_name": "Fine-Tuning",
        "description": "Customizes a pre-trained LLM on domain-specific data. Best for specialized domains requiring high accuracy.",
        "strengths": ["High accuracy", "Low inference latency", "Deep domain knowledge", "Consistent outputs"],
        "weaknesses": ["Expensive retraining", "Data staleness risk", "Requires labeled data"],
    },
    "CAG": {
        "full_name": "Context-Augmented Generation",
        "description": "Provides context directly in the prompt without vector DB. Best for small, well-defined knowledge sets.",
        "strengths": ["Simple architecture", "Low infrastructure cost", "Fast setup", "No vector DB needed"],
        "weaknesses": ["Context window limits", "Not scalable", "Higher per-query cost for large contexts"],
    },
    "Hybrid": {
        "full_name": "Hybrid Architecture",
        "description": "Combines RAG + Fine-Tuning for maximum capability. Best for enterprise-scale deployments with complex requirements.",
        "strengths": ["Maximum flexibility", "Best accuracy potential", "Handles edge cases", "Scalable"],
        "weaknesses": ["Complex architecture", "Higher cost", "More maintenance", "Longer development time"],
    },
}


class ScoringEngine:
    """Deterministic architecture scoring engine."""

    def __init__(self):
        self.rules = SCORING_RULES
        self.weights = SIGNAL_WEIGHTS
        self.architectures = ["RAG", "FineTuning", "CAG", "Hybrid"]
        # B-12 FIX: Cache sensitivity results to avoid 30+ score() calls on every re-score.
        self._sensitivity_cache: dict[str, dict] = {}

    def _hash_signals(self, signals: dict) -> str:
        """Create a deterministic hash of the signals dictionary for caching."""
        import hashlib
        import json
        # Sort keys to ensure deterministic serialization
        serialized = json.dumps(signals, sort_keys=True)
        return hashlib.md5(serialized.encode("utf-8")).hexdigest()

    def score(self, signals: dict[str, dict]) -> dict:
        """Compute architecture scores from extracted signals."""
        scores = {arch: 0.0 for arch in self.architectures}
        factor_breakdown: dict[str, dict[str, float]] = {arch: {} for arch in self.architectures}
        total_weight = 0.0
        evaluated_factors = 0

        for signal_name, signal_data in signals.items():
            value = signal_data.get("value")
            confidence = signal_data.get("confidence", 0.0)

            if not value or confidence < 0.1:
                # Skip missing or very low confidence signals
                for arch in self.architectures:
                    factor_breakdown[arch][signal_name] = 0.0
                continue

            # Get scoring rules for this signal value
            signal_rules = self.rules.get(signal_name, {})
            value_scores = signal_rules.get(value, {})

            if not value_scores:
                for arch in self.architectures:
                    factor_breakdown[arch][signal_name] = 0.0
                continue

            weight = self.weights.get(signal_name, 1.0)
            # Apply confidence as a modifier
            effective_weight = weight * confidence
            total_weight += effective_weight
            evaluated_factors += 1

            for arch in self.architectures:
                arch_score = value_scores.get(arch, 0.5)
                weighted_score = arch_score * effective_weight
                scores[arch] += weighted_score
                factor_breakdown[arch][signal_name] = round(arch_score, 2)

        # Normalize scores to percentages
        if total_weight > 0:
            for arch in self.architectures:
                scores[arch] = round((scores[arch] / total_weight) * 100, 1)

        # Hybrid synergy adjustment.
        # The per-signal rules score Hybrid as roughly the midpoint of RAG and
        # FineTuning, which mathematically prevents Hybrid from ever winning
        # when one single architecture is strongly favoured — even when the
        # document genuinely requires *both* retrieval flexibility and
        # fine-tuned model expertise. We correct that here by detecting
        # cross-architecture *tension* from the signals themselves:
        #
        #   - count signals that strongly pull toward RAG  (per-signal >= 0.8)
        #   - count signals that strongly pull toward FineTuning (>= 0.8)
        #
        # If only one side has strong pulls, the single architecture is the
        # right answer and no bonus is applied. If *both* sides have multiple
        # strong pulls, Hybrid earns a proportional bonus — never enough to
        # override a clear single-arch winner, but enough to let Hybrid take
        # the lead when the document genuinely sits at the intersection.
        if total_weight > 0 and signals:
            STRONG_PULL = 0.8
            # A "maximal" RAG-only pull (>= 0.95) corresponds to signals
            # like data_volatility=high or dataset_size=very_large — i.e.
            # the cases where a single FT model genuinely can't keep up
            # (data goes stale faster than retraining cycles) or where the
            # corpus is too large to ingest into training. Without at
            # least one such signal, retraining-with-citations or
            # RAG-with-grounding can subsume the requirements without
            # needing both architectures.
            MAXIMAL_PULL = 0.95
            rag_pulls = [
                (sig, factor_breakdown["RAG"].get(sig, 0.0))
                for sig in signals
                if factor_breakdown["RAG"].get(sig, 0.0) >= STRONG_PULL
            ]
            ft_pulls = [
                (sig, factor_breakdown["FineTuning"].get(sig, 0.0))
                for sig in signals
                if factor_breakdown["FineTuning"].get(sig, 0.0) >= STRONG_PULL
            ]
            # Genuine tension requires at least 2 strong pulls on each side,
            # from *different* signals (a single signal can pull both ways
            # weakly but that is not tension), AND at least one maximal-
            # strength RAG pull (the unforgiving FT-killer signal).
            rag_sigs = {s for s, _ in rag_pulls}
            ft_sigs = {s for s, _ in ft_pulls}
            distinct_rag = rag_sigs - ft_sigs
            distinct_ft = ft_sigs - rag_sigs
            has_maximal_rag_pull = any(
                score >= MAXIMAL_PULL for sig, score in rag_pulls if sig in distinct_rag
            )
            if len(distinct_rag) >= 2 and len(distinct_ft) >= 2 and has_maximal_rag_pull:
                tension = min(len(distinct_rag), len(distinct_ft))
                # Weight the bonus by the signal weights on each side so a
                # tension across high-weight signals (dataset_size,
                # data_volatility, accuracy_requirement) matters more than
                # tension across low-weight ones.
                rag_weight_sum = sum(self.weights.get(s, 1.0) for s in distinct_rag)
                ft_weight_sum = sum(self.weights.get(s, 1.0) for s in distinct_ft)
                avg_weight = (rag_weight_sum + ft_weight_sum) / (len(distinct_rag) + len(distinct_ft))
                # Bonus scales with tension and average signal weight.
                # Calibrated against the canonical hybrid case (real-time
                # feeds + static corpus + specialized domain + critical
                # accuracy): the FT side of the rules table has more
                # strong-score cells than the RAG side, so a doc with 2 RAG
                # pulls and 4-5 FT pulls otherwise looks FT-dominant even
                # though the cross-pull means a single arch under-serves
                # the requirements. The multiplier is sized so that genuine
                # hybrid cases clear the FT lead by a comfortable margin,
                # while a single dominant arch (no opposing pulls at all)
                # gets no bonus and wins cleanly.
                # Multiplier increased after rebalancing RAG/CAG upward:
                # those changes pushed single-arch scores higher, so the
                # Hybrid bonus needed more force to overtake in canonical
                # hybrid cases while still leaving pure single-arch docs
                # untouched (those don't trigger the bonus at all).
                bonus = min(tension * 8.0 * avg_weight, 22.0)
                scores["Hybrid"] = round(scores["Hybrid"] + bonus, 1)

        # CAG synergy adjustment.
        # CAG's sweet spot is a small, bounded, slow-changing corpus that
        # fits entirely in an LLM context window. The per-signal rules
        # under-value CAG when those structural conditions coexist with a
        # specialized domain or strict-accuracy requirement, because those
        # latter signals strongly favour FT independently. But for a tiny
        # static corpus, CAG matches FT's accuracy simply by including the
        # whole corpus in the prompt — no training, no retrieval system.
        # When all three "bounded corpus" structural signals align, apply
        # a fixed bonus so CAG can overtake the FT-favouring pulls.
        if total_weight > 0 and signals:
            dataset_val = signals.get("dataset_size", {}).get("value")
            volatility_val = signals.get("data_volatility", {}).get("value")
            volume_val = signals.get("query_volume", {}).get("value")
            if (
                dataset_val == "small"
                and volatility_val in ("static", "low")
                and volume_val in ("low", "medium")
            ):
                scores["CAG"] = round(scores["CAG"] + 14.0, 1)

        # Rank architectures
        ranked = sorted(self.architectures, key=lambda a: scores[a], reverse=True)

        # Compute suitability categories
        suitability = {}
        for arch in self.architectures:
            s = scores[arch]
            if s >= 75:
                suitability[arch] = "Highly Suitable"
            elif s >= 55:
                suitability[arch] = "Suitable"
            elif s >= 40:
                suitability[arch] = "Moderately Suitable"
            else:
                suitability[arch] = "Not Recommended"

        # AI-5.2 FIX: Detect zero-signal state and flag it so callers can warn users.
        # When all signals are missing, scores are all 0.0 and ranking is arbitrary.
        data_sufficient = evaluated_factors > 0

        return {
            "scores": scores,
            "ranking": ranked,
            "recommended": ranked[0],
            "confidence": self._compute_overall_confidence(signals),
            "suitability": suitability,
            "factor_breakdown": factor_breakdown,
            "evaluated_factors": evaluated_factors,
            "total_factors": len(SIGNAL_SCHEMA) if hasattr(self, 'rules') else 10,
            "architecture_details": ARCHITECTURE_DESCRIPTIONS,
            "why_not": self._generate_why_not(ranked, scores, factor_breakdown),
            # AI-5.2: False when no signals were evaluated — frontend should show a warning.
            "data_sufficient": data_sufficient,
        }

    def _compute_overall_confidence(self, signals: dict) -> float:
        """Compute overall confidence of the recommendation.

        Only signals that actually have a non-null value contribute to the
        average — signals that were nulled by anti-hallucination should not
        inflate coverage or be counted in the mean (they were not scored).
        Coverage (fraction of 10 signals that have a value) acts as a separate
        penalty so a recommendation from 3 signals is less confident than one
        from 9, even if per-signal confidence is the same.
        """
        total = len(signals)
        if total == 0:
            return 0.0

        valued = [(s.get("value"), s.get("confidence", 0)) for s in signals.values()]
        active_confs = [c for v, c in valued if v is not None and c > 0.0]

        if not active_confs:
            return 0.0

        avg_active = sum(active_confs) / len(active_confs)
        coverage = len(active_confs) / total

        return round(avg_active * 0.7 + coverage * 0.3, 2)

    def _generate_why_not(self, ranked: list, scores: dict, breakdown: dict) -> dict[str, str]:
        """Generate explanations for why non-recommended architectures rank lower."""
        why_not = {}
        top = ranked[0]
        top_score = scores[top]

        for arch in ranked[1:]:
            arch_score = scores[arch]
            gap = top_score - arch_score

            # Find weakest factors for this architecture
            factors = breakdown.get(arch, {})
            weak_factors = sorted(
                [(k, v) for k, v in factors.items() if v > 0],
                key=lambda x: x[1],
            )[:3]

            if weak_factors:
                weak_names = ", ".join([f[0].replace("_", " ") for f in weak_factors])
                why_not[arch] = f"Scored {gap:.1f} points lower than {top}. Weakest on: {weak_names}."
            else:
                why_not[arch] = f"Scored {gap:.1f} points lower than {top}."

        return why_not

    def sensitivity_analysis(self, signals: dict, perturbation_steps: int = 3) -> dict:
        """Perturb each signal and check if recommendation changes."""
        
        # B-12 FIX: Check cache first
        sig_hash = self._hash_signals(signals)
        if sig_hash in self._sensitivity_cache:
            return self._sensitivity_cache[sig_hash]
            
        base_result = self.score(signals)
        base_recommended = base_result["recommended"]
        instabilities = []

        # For each signal, try different values
        for signal_name in SIGNAL_SCHEMA:
            original = signals.get(signal_name, {}).copy()
            possible_values = list(self.rules.get(signal_name, {}).keys())

            for alt_value in possible_values:
                if alt_value == original.get("value"):
                    continue

                # AI-5.3 FIX: Use copy.deepcopy() instead of dict() shallow copy.
                # dict(signals) only copies the top-level keys; nested signal dicts
                # are still references. A mutation inside score() would corrupt the
                # caller's original signal dict, causing subtle scoring bugs.
                perturbed = copy.deepcopy(signals)
                perturbed[signal_name] = {
                    **original,
                    "value": alt_value,
                    "confidence": max(original.get("confidence", 0.5), 0.5),
                }

                perturbed_result = self.score(perturbed)
                if perturbed_result["recommended"] != base_recommended:
                    instabilities.append({
                        "signal": signal_name,
                        "original_value": original.get("value"),
                        "perturbed_value": alt_value,
                        "original_recommendation": base_recommended,
                        "new_recommendation": perturbed_result["recommended"],
                        "score_delta": round(
                            perturbed_result["scores"][perturbed_result["recommended"]]
                            - base_result["scores"][base_recommended], 1
                        ),
                    })

        stability_score = max(0, 1.0 - (len(instabilities) / (len(SIGNAL_SCHEMA) * 3)))

        result = {
            "is_stable": stability_score > 0.7,
            "stability_score": round(stability_score, 2),
            "instabilities": instabilities,
            "warning": "Recommendation may change with different input values" if stability_score <= 0.7 else None,
        }
        
        # Prevent cache from growing unbounded
        if len(self._sensitivity_cache) > 1000:
            self._sensitivity_cache.clear()
            
        self._sensitivity_cache[sig_hash] = result
        return result
