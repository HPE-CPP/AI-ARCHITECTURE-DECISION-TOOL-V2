"""
Cost Analysis Service — generates detailed cost estimates for each architecture
based on extracted signals (dataset_size, query_volume, user_scale, etc.).
"""
from __future__ import annotations

# ---------------------------------------------------------------------------
# Cost model data
# ---------------------------------------------------------------------------

# Monthly cost estimates (USD) per architecture, broken into categories.
# Each category maps signal values to cost ranges [low, high].
# These are industry-average estimates for LLM-based architectures.

_INFRA_COST: dict[str, dict[str, dict[str, list[int]]]] = {
    # Compute / GPU costs
    "compute": {
        "dataset_size": {
            "small":      {"RAG": [200, 500],    "FineTuning": [800, 2000],   "CAG": [100, 300],    "Hybrid": [1000, 2500]},
            "medium":     {"RAG": [500, 1500],   "FineTuning": [2000, 5000],  "CAG": [200, 600],    "Hybrid": [2500, 6000]},
            "large":      {"RAG": [1500, 4000],  "FineTuning": [5000, 12000], "CAG": [500, 1500],   "Hybrid": [6000, 15000]},
            "very_large": {"RAG": [4000, 10000], "FineTuning": [12000, 30000],"CAG": [1500, 4000],  "Hybrid": [15000, 35000]},
        },
        "query_volume": {
            "low":       {"RAG": [100, 300],    "FineTuning": [50, 150],    "CAG": [50, 150],    "Hybrid": [150, 400]},
            "medium":    {"RAG": [300, 800],    "FineTuning": [150, 400],   "CAG": [150, 500],   "Hybrid": [400, 1000]},
            "high":      {"RAG": [800, 2000],   "FineTuning": [400, 1000],  "CAG": [500, 1500],  "Hybrid": [1000, 2500]},
            "very_high": {"RAG": [2000, 5000],  "FineTuning": [1000, 2500], "CAG": [1500, 4000], "Hybrid": [2500, 6000]},
        },
    },
    # Storage costs (vector DB, model artifacts, embeddings)
    "storage": {
        "dataset_size": {
            "small":      {"RAG": [20, 50],    "FineTuning": [50, 150],   "CAG": [5, 20],     "Hybrid": [70, 200]},
            "medium":     {"RAG": [50, 200],   "FineTuning": [150, 400],  "CAG": [10, 50],    "Hybrid": [200, 500]},
            "large":      {"RAG": [200, 600],  "FineTuning": [400, 1000], "CAG": [30, 100],   "Hybrid": [500, 1500]},
            "very_large": {"RAG": [600, 2000], "FineTuning": [1000, 3000],"CAG": [100, 400],  "Hybrid": [1500, 4000]},
        },
    },
    # API / inference costs (LLM API calls)
    "api_inference": {
        "query_volume": {
            "low":       {"RAG": [100, 300],   "FineTuning": [30, 100],   "CAG": [80, 250],    "Hybrid": [130, 350]},
            "medium":    {"RAG": [300, 1000],  "FineTuning": [100, 350],  "CAG": [250, 800],   "Hybrid": [350, 1200]},
            "high":      {"RAG": [1000, 3000], "FineTuning": [350, 1000], "CAG": [800, 2500],  "Hybrid": [1200, 3500]},
            "very_high": {"RAG": [3000, 8000], "FineTuning": [1000, 3000],"CAG": [2500, 7000], "Hybrid": [3500, 9000]},
        },
    },
    # Networking & data transfer
    "networking": {
        "user_scale": {
            "small":      {"RAG": [20, 50],   "FineTuning": [10, 30],   "CAG": [10, 30],   "Hybrid": [30, 70]},
            "medium":     {"RAG": [50, 150],  "FineTuning": [30, 80],   "CAG": [30, 80],   "Hybrid": [70, 200]},
            "large":      {"RAG": [150, 400], "FineTuning": [80, 200],  "CAG": [80, 200],  "Hybrid": [200, 500]},
            "enterprise": {"RAG": [400, 1000],"FineTuning": [200, 500], "CAG": [200, 500], "Hybrid": [500, 1200]},
        },
    },
}

# One-time setup / development costs
_SETUP_COST: dict[str, list[int]] = {
    "RAG":        [5000, 15000],
    "FineTuning": [15000, 40000],
    "CAG":        [2000, 8000],
    "Hybrid":     [25000, 60000],
}

# Training / retraining costs (relevant for FineTuning & Hybrid)
_TRAINING_COST: dict[str, dict[str, list[int]]] = {
    "dataset_size": {
        "small":      {"RAG": [0, 0],    "FineTuning": [500, 2000],   "CAG": [0, 0],   "Hybrid": [500, 2000]},
        "medium":     {"RAG": [0, 0],    "FineTuning": [2000, 6000],  "CAG": [0, 0],   "Hybrid": [2000, 6000]},
        "large":      {"RAG": [0, 0],    "FineTuning": [6000, 15000], "CAG": [0, 0],   "Hybrid": [6000, 15000]},
        "very_large": {"RAG": [0, 0],    "FineTuning": [15000, 40000],"CAG": [0, 0],   "Hybrid": [15000, 40000]},
    },
    "data_volatility": {
        "static":   {"RAG": [0, 0], "FineTuning": [0, 0],      "CAG": [0, 0], "Hybrid": [0, 0]},
        "low":      {"RAG": [0, 0], "FineTuning": [200, 800],   "CAG": [0, 0], "Hybrid": [200, 800]},
        "moderate": {"RAG": [0, 0], "FineTuning": [800, 2500],  "CAG": [0, 0], "Hybrid": [800, 2500]},
        "high":     {"RAG": [0, 0], "FineTuning": [2500, 6000], "CAG": [0, 0], "Hybrid": [2500, 6000]},
    },
}

# Maintenance / ops multiplier based on deployment
_MAINTENANCE_MULTIPLIER: dict[str, dict[str, float]] = {
    "cloud":      {"RAG": 1.0, "FineTuning": 1.0, "CAG": 1.0, "Hybrid": 1.0},
    "on_premise":  {"RAG": 1.4, "FineTuning": 1.3, "CAG": 1.2, "Hybrid": 1.5},
    "hybrid":     {"RAG": 1.2, "FineTuning": 1.2, "CAG": 1.1, "Hybrid": 1.3},
    "edge":       {"RAG": 1.5, "FineTuning": 1.4, "CAG": 1.3, "Hybrid": 1.6},
}

# Security premium multiplier
_SECURITY_MULTIPLIER: dict[str, float] = {
    "standard": 1.0,
    "elevated": 1.1,
    "high":     1.25,
    "critical": 1.5,
}

_ARCHITECTURES = ["RAG", "FineTuning", "CAG", "Hybrid"]

_ARCH_FULL_NAMES = {
    "RAG": "Retrieval-Augmented Generation",
    "FineTuning": "Fine-Tuning",
    "CAG": "Context-Augmented Generation",
    "Hybrid": "Hybrid Architecture",
}


# ---------------------------------------------------------------------------
# Core estimation logic
# ---------------------------------------------------------------------------

def _get_signal_value(signals: dict, name: str, default: str) -> str:
    """Extract signal value with fallback."""
    sig = signals.get(name, {})
    if isinstance(sig, dict):
        return sig.get("value") or default
    return default


def _sum_range(ranges: list[list[int]]) -> list[int]:
    """Sum a list of [low, high] ranges."""
    return [sum(r[0] for r in ranges), sum(r[1] for r in ranges)]


def generate_cost_analysis(result: dict) -> dict:
    """
    Generate a detailed cost analysis for all architectures based on
    the analysis result (which includes signals, recommended arch, etc.).

    Returns a dict with per-architecture cost breakdowns, comparisons,
    and recommendations.
    """
    signals = result.get("signals", {})
    recommended = result.get("recommended", "RAG")
    scores = result.get("scores", {})

    # Extract signal values
    dataset_size = _get_signal_value(signals, "dataset_size", "medium")
    query_volume = _get_signal_value(signals, "query_volume", "medium")
    user_scale = _get_signal_value(signals, "user_scale", "medium")
    data_volatility = _get_signal_value(signals, "data_volatility", "low")
    deployment = _get_signal_value(signals, "deployment_preference", "cloud")
    security = _get_signal_value(signals, "security_level", "standard")

    security_mult = _SECURITY_MULTIPLIER.get(security, 1.0)
    maint_mults = _MAINTENANCE_MULTIPLIER.get(deployment, _MAINTENANCE_MULTIPLIER["cloud"])

    arch_costs: dict[str, dict] = {}

    for arch in _ARCHITECTURES:
        maint_mult = maint_mults.get(arch, 1.0)

        # --- Monthly operational costs ---
        compute = _lookup_infra("compute", "dataset_size", dataset_size, arch)
        compute_qv = _lookup_infra("compute", "query_volume", query_volume, arch)
        compute = [compute[0] + compute_qv[0], compute[1] + compute_qv[1]]

        storage = _lookup_infra("storage", "dataset_size", dataset_size, arch)
        api_inference = _lookup_infra("api_inference", "query_volume", query_volume, arch)
        networking = _lookup_infra("networking", "user_scale", user_scale, arch)

        # Training / retraining (monthly amortised)
        training_ds = _lookup_training("dataset_size", dataset_size, arch)
        training_vol = _lookup_training("data_volatility", data_volatility, arch)
        training = [training_ds[0] + training_vol[0], training_ds[1] + training_vol[1]]

        # Maintenance overhead
        base_monthly = _sum_range([compute, storage, api_inference, networking, training])
        maintenance = [
            int(base_monthly[0] * (maint_mult - 1.0)),
            int(base_monthly[1] * (maint_mult - 1.0)),
        ]

        # Security premium
        pre_security = _sum_range([compute, storage, api_inference, networking, training, maintenance])
        security_addn = [
            int(pre_security[0] * (security_mult - 1.0)),
            int(pre_security[1] * (security_mult - 1.0)),
        ]

        monthly_total = _sum_range([pre_security, security_addn])

        # --- One-time costs ---
        setup = _SETUP_COST.get(arch, [10000, 30000])

        # --- Annual projection ---
        annual = [monthly_total[0] * 12 + setup[0], monthly_total[1] * 12 + setup[1]]

        # --- Cost per query estimate ---
        qv_map = {"low": 1000, "medium": 10000, "high": 100000, "very_high": 500000}
        monthly_queries = qv_map.get(query_volume, 10000)
        cost_per_query = [
            round(monthly_total[0] / max(monthly_queries, 1), 4),
            round(monthly_total[1] / max(monthly_queries, 1), 4),
        ]

        arch_costs[arch] = {
            "full_name": _ARCH_FULL_NAMES.get(arch, arch),
            "is_recommended": arch == recommended,
            "suitability_score": scores.get(arch, 0),
            "breakdown": {
                "compute":       {"label": "Compute & GPU",      "monthly": compute},
                "storage":       {"label": "Storage",             "monthly": storage},
                "api_inference": {"label": "API / Inference",     "monthly": api_inference},
                "networking":    {"label": "Networking",          "monthly": networking},
                "training":      {"label": "Training / Retrain",  "monthly": training},
                "maintenance":   {"label": "Maintenance & Ops",   "monthly": maintenance},
                "security":      {"label": "Security Premium",    "monthly": security_addn},
            },
            "monthly_total": monthly_total,
            "setup_cost": setup,
            "annual_total": annual,
            "cost_per_query": cost_per_query,
        }

    # --- Comparative insights ---
    cheapest = min(_ARCHITECTURES, key=lambda a: arch_costs[a]["monthly_total"][0])
    most_expensive = max(_ARCHITECTURES, key=lambda a: arch_costs[a]["monthly_total"][1])

    rec_cost = arch_costs[recommended]["monthly_total"]
    cheapest_cost = arch_costs[cheapest]["monthly_total"]
    savings_vs_cheapest = [rec_cost[0] - cheapest_cost[0], rec_cost[1] - cheapest_cost[1]]

    # Cost efficiency score: suitability score / cost (higher is better)
    efficiency: dict[str, float] = {}
    for arch in _ARCHITECTURES:
        avg_cost = (arch_costs[arch]["monthly_total"][0] + arch_costs[arch]["monthly_total"][1]) / 2
        suit_score = scores.get(arch, 50)
        efficiency[arch] = round(suit_score / max(avg_cost / 1000, 0.1), 2)

    best_value = max(_ARCHITECTURES, key=lambda a: efficiency[a])

    # Build cost recommendations
    cost_recommendations = []
    if recommended != cheapest:
        cost_recommendations.append(
            f"{_ARCH_FULL_NAMES[recommended]} is recommended for best performance but "
            f"{_ARCH_FULL_NAMES[cheapest]} is the most cost-effective option, "
            f"saving ${savings_vs_cheapest[0]:,}-${savings_vs_cheapest[1]:,}/month."
        )
    else:
        cost_recommendations.append(
            f"{_ARCH_FULL_NAMES[recommended]} is both the recommended architecture and the most cost-effective choice."
        )

    if best_value != recommended:
        cost_recommendations.append(
            f"{_ARCH_FULL_NAMES[best_value]} offers the best cost-efficiency ratio "
            f"(value score: {efficiency[best_value]})."
        )

    if deployment != "cloud":
        overhead = int((maint_mults.get(recommended, 1.0) - 1.0) * 100)
        if overhead > 0:
            cost_recommendations.append(
                f"On-premise/edge deployment adds ~{overhead}% maintenance overhead. "
                f"Consider cloud deployment to reduce operational costs."
            )

    if security in ("high", "critical"):
        prem = int((security_mult - 1.0) * 100)
        cost_recommendations.append(
            f"High security requirements add a ~{prem}% cost premium across all categories."
        )

    return {
        "architectures": arch_costs,
        "summary": {
            "recommended": recommended,
            "recommended_name": _ARCH_FULL_NAMES.get(recommended, recommended),
            "cheapest": cheapest,
            "cheapest_name": _ARCH_FULL_NAMES.get(cheapest, cheapest),
            "most_expensive": most_expensive,
            "most_expensive_name": _ARCH_FULL_NAMES.get(most_expensive, most_expensive),
            "best_value": best_value,
            "best_value_name": _ARCH_FULL_NAMES.get(best_value, best_value),
            "efficiency_scores": efficiency,
        },
        "cost_recommendations": cost_recommendations,
        "parameters_used": {
            "dataset_size": dataset_size,
            "query_volume": query_volume,
            "user_scale": user_scale,
            "data_volatility": data_volatility,
            "deployment_preference": deployment,
            "security_level": security,
        },
    }


def _lookup_infra(category: str, signal: str, value: str, arch: str) -> list[int]:
    """Look up infrastructure cost range."""
    cat = _INFRA_COST.get(category, {})
    sig = cat.get(signal, {})
    val = sig.get(value, {})
    return val.get(arch, [0, 0])


def _lookup_training(signal: str, value: str, arch: str) -> list[int]:
    """Look up training cost range."""
    sig = _TRAINING_COST.get(signal, {})
    val = sig.get(value, {})
    return val.get(arch, [0, 0])
