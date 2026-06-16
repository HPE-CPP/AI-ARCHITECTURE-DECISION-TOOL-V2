"""
Cost Analysis Service — generates detailed cost estimates for each architecture
based on extracted signals. All costs are in Indian Rupees (INR).
Conversion basis: 1 USD ≈ Rs. 84 (2025 rate). Figures are rounded to
defensible industry-average values for Indian cloud deployments.
"""
from __future__ import annotations

# ---------------------------------------------------------------------------
# INR Cost model
# ---------------------------------------------------------------------------

# Monthly cost estimates (INR) per architecture, broken into categories.
# Each category maps signal values to cost ranges [low, high].
# Sources: AWS India / Azure India / GCP Mumbai pricing + OpenAI API costs
# converted at Rs. 84/USD.  Numbers reflect realistic workloads, not toy demos.

_INFRA_COST: dict[str, dict[str, dict[str, list[int]]]] = {
    # Compute / GPU costs (EC2/GCP instance + orchestration)
    "compute": {
        "dataset_size": {
            "small":      {"RAG": [17000, 42000],     "FineTuning": [67000, 168000],    "CAG": [8500, 25000],     "Hybrid": [84000, 210000]},
            "medium":     {"RAG": [42000, 126000],    "FineTuning": [168000, 420000],   "CAG": [17000, 50000],    "Hybrid": [210000, 504000]},
            "large":      {"RAG": [126000, 336000],   "FineTuning": [420000, 1008000],  "CAG": [42000, 126000],   "Hybrid": [504000, 1260000]},
            "very_large": {"RAG": [336000, 840000],   "FineTuning": [1008000, 2520000], "CAG": [126000, 336000],  "Hybrid": [1260000, 2940000]},
        },
        "query_volume": {
            "low":       {"RAG": [8500, 25000],    "FineTuning": [4200, 12600],    "CAG": [4200, 12600],    "Hybrid": [12600, 33600]},
            "medium":    {"RAG": [25000, 67000],   "FineTuning": [12600, 33600],   "CAG": [12600, 42000],   "Hybrid": [33600, 84000]},
            "high":      {"RAG": [67000, 168000],  "FineTuning": [33600, 84000],   "CAG": [42000, 126000],  "Hybrid": [84000, 210000]},
            "very_high": {"RAG": [168000, 420000], "FineTuning": [84000, 210000],  "CAG": [126000, 336000], "Hybrid": [210000, 504000]},
        },
    },
    # Storage costs (vector DB, model artifacts, embeddings, object storage)
    "storage": {
        "dataset_size": {
            "small":      {"RAG": [1700, 4200],    "FineTuning": [4200, 12600],   "CAG": [420, 1700],     "Hybrid": [5900, 16800]},
            "medium":     {"RAG": [4200, 16800],   "FineTuning": [12600, 33600],  "CAG": [840, 4200],     "Hybrid": [16800, 42000]},
            "large":      {"RAG": [16800, 50400],  "FineTuning": [33600, 84000],  "CAG": [2500, 8400],    "Hybrid": [42000, 126000]},
            "very_large": {"RAG": [50400, 168000], "FineTuning": [84000, 252000], "CAG": [8400, 33600],   "Hybrid": [126000, 336000]},
        },
    },
    # API / LLM inference costs (OpenAI / Bedrock / self-hosted model tokens)
    "api_inference": {
        "query_volume": {
            "low":       {"RAG": [8400, 25000],    "FineTuning": [2500, 8400],    "CAG": [6700, 21000],    "Hybrid": [10900, 29400]},
            "medium":    {"RAG": [25000, 84000],   "FineTuning": [8400, 29400],   "CAG": [21000, 67000],   "Hybrid": [29400, 100800]},
            "high":      {"RAG": [84000, 252000],  "FineTuning": [29400, 84000],  "CAG": [67000, 210000],  "Hybrid": [100800, 294000]},
            "very_high": {"RAG": [252000, 672000], "FineTuning": [84000, 252000], "CAG": [210000, 588000], "Hybrid": [294000, 756000]},
        },
    },
    # Networking & data transfer (CDN, VPC, egress)
    "networking": {
        "user_scale": {
            "small":      {"RAG": [1700, 4200],   "FineTuning": [840, 2500],    "CAG": [840, 2500],    "Hybrid": [2500, 5900]},
            "medium":     {"RAG": [4200, 12600],  "FineTuning": [2500, 6700],   "CAG": [2500, 6700],   "Hybrid": [5900, 16800]},
            "large":      {"RAG": [12600, 33600], "FineTuning": [6700, 16800],  "CAG": [6700, 16800],  "Hybrid": [16800, 42000]},
            "enterprise": {"RAG": [33600, 84000], "FineTuning": [16800, 42000], "CAG": [16800, 42000], "Hybrid": [42000, 100800]},
        },
    },
}

# One-time setup / development costs (INR)
# Includes: architecture design, dev effort, initial deployment, testing
_SETUP_COST: dict[str, list[int]] = {
    "RAG":        [420000, 1260000],    # Rs. 4.2L - 12.6L
    "FineTuning": [1260000, 3360000],   # Rs. 12.6L - 33.6L
    "CAG":        [168000, 672000],     # Rs. 1.68L - 6.72L
    "Hybrid":     [2100000, 5040000],   # Rs. 21L - 50.4L
}

# Training / periodic retraining costs (monthly amortised, INR)
# FineTuning & Hybrid require periodic re-runs; RAG & CAG do not.
_TRAINING_COST: dict[str, dict[str, list[int]]] = {
    "dataset_size": {
        "small":      {"RAG": [0, 0], "FineTuning": [42000, 168000],    "CAG": [0, 0], "Hybrid": [42000, 168000]},
        "medium":     {"RAG": [0, 0], "FineTuning": [168000, 504000],   "CAG": [0, 0], "Hybrid": [168000, 504000]},
        "large":      {"RAG": [0, 0], "FineTuning": [504000, 1260000],  "CAG": [0, 0], "Hybrid": [504000, 1260000]},
        "very_large": {"RAG": [0, 0], "FineTuning": [1260000, 3360000], "CAG": [0, 0], "Hybrid": [1260000, 3360000]},
    },
    "data_volatility": {
        "static":   {"RAG": [0, 0], "FineTuning": [0, 0],          "CAG": [0, 0], "Hybrid": [0, 0]},
        "low":      {"RAG": [0, 0], "FineTuning": [16800, 67000],   "CAG": [0, 0], "Hybrid": [16800, 67000]},
        "moderate": {"RAG": [0, 0], "FineTuning": [67000, 210000],  "CAG": [0, 0], "Hybrid": [67000, 210000]},
        "high":     {"RAG": [0, 0], "FineTuning": [210000, 504000], "CAG": [0, 0], "Hybrid": [210000, 504000]},
    },
}

# Deployment overhead multiplier (on-premise/edge adds DevOps costs)
_MAINTENANCE_MULTIPLIER: dict[str, dict[str, float]] = {
    "cloud":      {"RAG": 1.0, "FineTuning": 1.0, "CAG": 1.0, "Hybrid": 1.0},
    "on_premise": {"RAG": 1.4, "FineTuning": 1.3, "CAG": 1.2, "Hybrid": 1.5},
    "hybrid":     {"RAG": 1.2, "FineTuning": 1.2, "CAG": 1.1, "Hybrid": 1.3},
    "edge":       {"RAG": 1.5, "FineTuning": 1.4, "CAG": 1.3, "Hybrid": 1.6},
}

# Security compliance premium (WAF, audit tools, encryption overhead)
_SECURITY_MULTIPLIER: dict[str, float] = {
    "standard": 1.0,
    "elevated": 1.1,
    "high":     1.25,
    "critical": 1.5,
}

_ARCHITECTURES = ["RAG", "FineTuning", "CAG", "Hybrid"]

_ARCH_FULL_NAMES = {
    "RAG":        "Retrieval-Augmented Generation",
    "FineTuning": "Fine-Tuning",
    "CAG":        "Cache-Augmented Generation",
    "Hybrid":     "Hybrid Architecture",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_signal_value(signals: dict, name: str, default: str) -> str:
    sig = signals.get(name, {})
    if isinstance(sig, dict):
        return sig.get("value") or default
    return default


def _sum_range(ranges: list[list[int]]) -> list[int]:
    return [sum(r[0] for r in ranges), sum(r[1] for r in ranges)]


def _inr_short(n: int) -> str:
    """Format large INR numbers in crore/lakh shorthand for text strings."""
    if n >= 10_000_000:
        return f"Rs. {n / 10_000_000:.1f} Cr"
    if n >= 100_000:
        return f"Rs. {n / 100_000:.1f} L"
    if n >= 1000:
        return f"Rs. {n // 1000}K"
    return f"Rs. {n:,}"


def _inr_range_short(r: list[int]) -> str:
    if r[0] == r[1] == 0:
        return "Nil"
    if r[0] == r[1]:
        return _inr_short(r[0])
    return f"{_inr_short(r[0])} - {_inr_short(r[1])}"


# ---------------------------------------------------------------------------
# Core estimation logic
# ---------------------------------------------------------------------------

def generate_cost_analysis(result: dict) -> dict:
    """
    Generate a detailed INR cost analysis for all architectures based on
    extracted signals.

    Returns a dict with per-architecture cost breakdowns, comparisons,
    and recommendations.
    """
    signals = result.get("signals", {})
    recommended = result.get("recommended", "RAG")
    scores = result.get("scores", {})

    dataset_size  = _get_signal_value(signals, "dataset_size",          "medium")
    query_volume  = _get_signal_value(signals, "query_volume",           "medium")
    user_scale    = _get_signal_value(signals, "user_scale",             "medium")
    data_volatility = _get_signal_value(signals, "data_volatility",      "low")
    deployment    = _get_signal_value(signals, "deployment_preference",  "cloud")
    security      = _get_signal_value(signals, "security_level",         "standard")

    security_mult = _SECURITY_MULTIPLIER.get(security, 1.0)
    maint_mults   = _MAINTENANCE_MULTIPLIER.get(deployment, _MAINTENANCE_MULTIPLIER["cloud"])

    arch_costs: dict[str, dict] = {}

    for arch in _ARCHITECTURES:
        maint_mult = maint_mults.get(arch, 1.0)

        # Monthly operational costs
        compute_ds = _lookup_infra("compute", "dataset_size", dataset_size, arch)
        compute_qv = _lookup_infra("compute", "query_volume", query_volume, arch)
        compute    = [compute_ds[0] + compute_qv[0], compute_ds[1] + compute_qv[1]]

        storage       = _lookup_infra("storage",       "dataset_size", dataset_size,  arch)
        api_inference = _lookup_infra("api_inference", "query_volume", query_volume,   arch)
        networking    = _lookup_infra("networking",    "user_scale",   user_scale,     arch)

        # Training (monthly amortised)
        training_ds  = _lookup_training("dataset_size",    dataset_size,   arch)
        training_vol = _lookup_training("data_volatility", data_volatility, arch)
        training = [training_ds[0] + training_vol[0], training_ds[1] + training_vol[1]]

        # Maintenance overhead
        base_monthly = _sum_range([compute, storage, api_inference, networking, training])
        maintenance  = [
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

        # One-time costs
        setup = _SETUP_COST.get(arch, [840000, 2520000])

        # Annual projection (monthly × 12 + setup)
        annual = [monthly_total[0] * 12 + setup[0], monthly_total[1] * 12 + setup[1]]

        # Cost per query estimate (INR)
        qv_map = {"low": 1000, "medium": 10000, "high": 100000, "very_high": 500000}
        monthly_queries = qv_map.get(query_volume, 10000)
        cost_per_query = [
            round(monthly_total[0] / max(monthly_queries, 1), 4),
            round(monthly_total[1] / max(monthly_queries, 1), 4),
        ]

        arch_costs[arch] = {
            "full_name":        _ARCH_FULL_NAMES.get(arch, arch),
            "is_recommended":   arch == recommended,
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
            "setup_cost":    setup,
            "annual_total":  annual,
            "cost_per_query": cost_per_query,
        }

    # Comparative insights
    cheapest       = min(_ARCHITECTURES, key=lambda a: arch_costs[a]["monthly_total"][0])
    most_expensive = max(_ARCHITECTURES, key=lambda a: arch_costs[a]["monthly_total"][1])

    rec_cost      = arch_costs[recommended]["monthly_total"]
    cheapest_cost = arch_costs[cheapest]["monthly_total"]
    savings_lo = rec_cost[0] - cheapest_cost[0]
    savings_hi = rec_cost[1] - cheapest_cost[1]

    # Cost efficiency: suitability score / avg monthly cost
    efficiency: dict[str, float] = {}
    for arch in _ARCHITECTURES:
        avg_cost   = (arch_costs[arch]["monthly_total"][0] + arch_costs[arch]["monthly_total"][1]) / 2
        suit_score = scores.get(arch, 50)
        efficiency[arch] = round(suit_score / max(avg_cost / 100000, 0.1), 2)

    best_value = max(_ARCHITECTURES, key=lambda a: efficiency[a])

    # Build cost recommendations
    cost_recommendations: list[str] = []
    if recommended != cheapest:
        cost_recommendations.append(
            f"{_ARCH_FULL_NAMES[recommended]} is recommended for best performance, but "
            f"{_ARCH_FULL_NAMES[cheapest]} is the most cost-effective option, "
            f"saving {_inr_range_short([savings_lo, savings_hi])}/month."
        )
    else:
        cost_recommendations.append(
            f"{_ARCH_FULL_NAMES[recommended]} is both the recommended architecture and the most cost-effective choice."
        )

    if best_value != recommended:
        cost_recommendations.append(
            f"{_ARCH_FULL_NAMES[best_value]} offers the best cost-to-performance ratio "
            f"(efficiency score: {efficiency[best_value]})."
        )

    if deployment != "cloud":
        overhead = int((maint_mults.get(recommended, 1.0) - 1.0) * 100)
        if overhead > 0:
            cost_recommendations.append(
                f"On-premise/edge deployment adds ~{overhead}% maintenance overhead compared to cloud. "
                f"Migrating to cloud could meaningfully reduce operational costs."
            )

    if security in ("high", "critical"):
        prem = int((security_mult - 1.0) * 100)
        cost_recommendations.append(
            f"Your security requirements ({security.replace('_', ' ')}) add a ~{prem}% cost premium "
            f"across all categories for compliance tooling and audit infrastructure."
        )

    rec_monthly_avg = (rec_cost[0] + rec_cost[1]) // 2
    cost_recommendations.append(
        f"Budget {_inr_short(rec_monthly_avg)}/month for {_ARCH_FULL_NAMES[recommended]} operations, "
        f"plus a one-time setup investment of {_inr_range_short(_SETUP_COST.get(recommended, [0, 0]))}."
    )

    return {
        "architectures": arch_costs,
        "summary": {
            "recommended":       recommended,
            "recommended_name":  _ARCH_FULL_NAMES.get(recommended, recommended),
            "cheapest":          cheapest,
            "cheapest_name":     _ARCH_FULL_NAMES.get(cheapest, cheapest),
            "most_expensive":    most_expensive,
            "most_expensive_name": _ARCH_FULL_NAMES.get(most_expensive, most_expensive),
            "best_value":        best_value,
            "best_value_name":   _ARCH_FULL_NAMES.get(best_value, best_value),
            "efficiency_scores": efficiency,
        },
        "cost_recommendations": cost_recommendations,
        "parameters_used": {
            "dataset_size":         dataset_size,
            "query_volume":         query_volume,
            "user_scale":           user_scale,
            "data_volatility":      data_volatility,
            "deployment_preference": deployment,
            "security_level":       security,
        },
    }


def _lookup_infra(category: str, signal: str, value: str, arch: str) -> list[int]:
    cat = _INFRA_COST.get(category, {})
    sig = cat.get(signal, {})
    val = sig.get(value, {})
    return val.get(arch, [0, 0])


def _lookup_training(signal: str, value: str, arch: str) -> list[int]:
    sig = _TRAINING_COST.get(signal, {})
    val = sig.get(value, {})
    return val.get(arch, [0, 0])
