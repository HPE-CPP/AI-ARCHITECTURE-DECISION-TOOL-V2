"""Verify scoring engine produces expected arch for each test doc.

Signals are hand-derived from the test doc contents in tests/docs/.
This bypasses the LLM extractor so we test the scoring layer in isolation.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from services.scoring_engine import ScoringEngine


def sig(value, conf=0.85):
    return {"value": value, "confidence": conf}


CASES = {
    "01_perfect_rag": {
        "expected": "RAG",
        "signals": {
            "dataset_size": sig("large"),            # 80GB, 40k docs
            "query_volume": sig("medium"),           # 5-10 qps peak
            "latency_requirement": sig("relaxed"),   # sub-2s acceptable
            "data_volatility": sig("low"),           # weekly updates
            "accuracy_requirement": sig("very_high"),# no hallucinations, cited
            "domain_specificity": sig("specialized"),# GlobalRetail internal
            "security_level": sig("high"),           # on-prem, internal
            "cost_sensitivity": sig("high"),         # fixed IT budget
            "deployment_preference": sig("on_premise"),
            "user_scale": sig("medium"),             # 500 daily users
        },
    },
    "01_perfect_rag_aggressive_llm": {
        # Realistic worst-case: LLM picks highly_specialized + critical
        # (over-aggressive but still a doc that should land on RAG).
        "expected": "RAG",
        "signals": {
            "dataset_size": sig("large"),
            "query_volume": sig("medium"),
            "latency_requirement": sig("relaxed"),
            "data_volatility": sig("low"),
            "accuracy_requirement": sig("critical"),       # LLM over-picks
            "domain_specificity": sig("highly_specialized"),# LLM over-picks
            "security_level": sig("high"),
            "cost_sensitivity": sig("high"),
            "deployment_preference": sig("on_premise"),
            "user_scale": sig("medium"),
        },
    },
    "02_perfect_finetuning": {
        "expected": "FineTuning",
        "signals": {
            "dataset_size": sig("very_large"),       # 1.2 TB, 2.3M reports
            "query_volume": sig("low"),              # 300/day
            "latency_requirement": sig("relaxed"),   # 30s acceptable
            "data_volatility": sig("static"),        # historical archive
            "accuracy_requirement": sig("critical"), # FDA, zero hallucination
            "domain_specificity": sig("highly_specialized"),
            "security_level": sig("critical"),       # HIPAA, on-prem only
            "cost_sensitivity": sig("low"),          # dedicated budget
            "deployment_preference": sig("on_premise"),
            "user_scale": sig("small"),              # radiologists
        },
    },
    "03_perfect_cag": {
        "expected": "CAG",
        "signals": {
            "dataset_size": sig("small"),            # 800 pages, fits 400k tokens
            "query_volume": sig("low"),              # 50-100/day
            "latency_requirement": sig("moderate"),  # <1s target
            "data_volatility": sig("static"),        # annual update
            "accuracy_requirement": sig("very_high"),# legal malpractice risk
            "domain_specificity": sig("specialized"),# legal templates, expected
            "security_level": sig("high"),           # client confidential
            "cost_sensitivity": sig("high"),         # limited budget
            "deployment_preference": sig("on_premise"),
            "user_scale": sig("small"),              # 25 associates
        },
    },
    "03_perfect_cag_aggressive_llm": {
        # If LLM over-classifies as highly_specialized + critical
        "expected": "CAG",
        "signals": {
            "dataset_size": sig("small"),
            "query_volume": sig("low"),
            "latency_requirement": sig("moderate"),
            "data_volatility": sig("static"),
            "accuracy_requirement": sig("critical"),
            "domain_specificity": sig("highly_specialized"),
            "security_level": sig("high"),
            "cost_sensitivity": sig("high"),
            "deployment_preference": sig("on_premise"),
            "user_scale": sig("small"),
        },
    },
    "04_perfect_hybrid": {
        "expected": "Hybrid",
        "signals": {
            "dataset_size": sig("large"),            # 500GB static
            "query_volume": sig("high"),             # 800/min peak
            "latency_requirement": sig("strict"),    # <200ms
            "data_volatility": sig("high"),          # continuous mkt data
            "accuracy_requirement": sig("critical"), # SEC compliance
            "domain_specificity": sig("highly_specialized"),
            "security_level": sig("critical"),       # SEC/MiFID/PCI
            "cost_sensitivity": sig("low"),          # no ceiling
            "deployment_preference": sig("hybrid"),  # cloud + on-prem
            "user_scale": sig("enterprise"),
        },
    },
    "10_stress_hybrid": {
        "expected": "Hybrid",
        "signals": {
            "dataset_size": sig("very_large"),       # 2.1TB
            "query_volume": sig("very_high"),        # 50k users
            "latency_requirement": sig("strict"),    # real-time ops
            "data_volatility": sig("high"),          # streaming feeds
            "accuracy_requirement": sig("very_high"),
            "domain_specificity": sig("specialized"),
            "security_level": sig("high"),           # GDPR/SOX
            "cost_sensitivity": sig("moderate"),
            "deployment_preference": sig("hybrid"),
            "user_scale": sig("enterprise"),
        },
    },
}


def main():
    engine = ScoringEngine()
    print(f"{'Doc':<28} {'Expected':<12} {'Got':<12} {'Scores (R/F/C/H)':<28} {'Result'}")
    print("-" * 100)
    pass_count = 0
    for name, case in CASES.items():
        result = engine.score(case["signals"])
        got = result["recommended"]
        scores = result["scores"]
        score_str = f"{scores['RAG']:.1f}/{scores['FineTuning']:.1f}/{scores['CAG']:.1f}/{scores['Hybrid']:.1f}"
        ok = got == case["expected"]
        status = "PASS" if ok else "FAIL"
        if ok:
            pass_count += 1
        print(f"{name:<28} {case['expected']:<12} {got:<12} {score_str:<28} {status}")
    print("-" * 100)
    print(f"Total: {pass_count}/{len(CASES)} passed")


if __name__ == "__main__":
    main()
