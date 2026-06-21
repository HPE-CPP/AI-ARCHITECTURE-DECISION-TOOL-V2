import os
import sys

# Add backend to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from services.document_parser import (
    RelevanceAssessment, RiskTier, RuleFlag, 
    build_user_facing_message, log_relevance_assessment
)

# 1. Good requirements doc
assessment_good = RelevanceAssessment(
    passed=True,
    risk_tier=RiskTier.CLEAR,
    total_risk_score=0.0,
    flags=[
        RuleFlag(rule_name="circular_upload", triggered=False, risk_points=0, detail="No circular-upload markers found."),
        RuleFlag(rule_name="length_ceiling", triggered=False, risk_points=0, detail="Length within normal range."),
        RuleFlag(rule_name="keyword_density", triggered=False, risk_points=0, detail="Healthy keyword density (66.29/1000 words)."),
        RuleFlag(rule_name="category_coverage", triggered=False, risk_points=0, detail="10/12 categories matched."),
        RuleFlag(rule_name="resume_shape", triggered=False, risk_points=0, detail="No resume-like structural signature.")
    ]
)

# 2. Extreme length doc
assessment_long = RelevanceAssessment(
    passed=False,
    risk_tier=RiskTier.AUTO_REJECT,
    total_risk_score=70.0,
    flags=[
        RuleFlag(rule_name="circular_upload", triggered=False, risk_points=0, detail="No circular-upload markers found."),
        RuleFlag(rule_name="length_ceiling", triggered=True, risk_points=70, detail="Document is 60,000 words (~120 pages) — far beyond typical requirements doc length, resembles a book/manual."),
        RuleFlag(rule_name="keyword_density", triggered=False, risk_points=0, detail="Healthy keyword density (25.00/1000 words)."),
        RuleFlag(rule_name="category_coverage", triggered=False, risk_points=0, detail="8/12 categories matched."),
        RuleFlag(rule_name="resume_shape", triggered=False, risk_points=0, detail="No resume-like structural signature.")
    ],
    rejection_reason="length_ceiling",
    rejection_message="Document is 60,000 words (~120 pages) — far beyond typical requirements doc length, resembles a book/manual."
)

# 3. Resume doc
assessment_resume = RelevanceAssessment(
    passed=False,
    risk_tier=RiskTier.AUTO_REJECT,
    total_risk_score=95.0,
    flags=[
        RuleFlag(rule_name="circular_upload", triggered=False, risk_points=0, detail="No circular-upload markers found."),
        RuleFlag(rule_name="length_ceiling", triggered=False, risk_points=0, detail="Length within normal range."),
        RuleFlag(rule_name="keyword_density", triggered=True, risk_points=40, detail="Very low keyword density (0.00/1000 words)."),
        RuleFlag(rule_name="category_coverage", triggered=True, risk_points=45, detail="Only 0/12 categories matched — touches almost no requirement topics."),
        RuleFlag(rule_name="resume_shape", triggered=True, risk_points=50, detail="Strong resume/CV structural signature (score=5): contact info, date ranges, short bulleted lines, no spec language.")
    ],
    rejection_reason="resume_shape",
    rejection_message="Strong resume/CV structural signature (score=5): contact info, date ranges, short bulleted lines, no spec language."
)

print("--- User Messages ---")
print("Good:", build_user_facing_message(assessment_good))
print("Long:", build_user_facing_message(assessment_long))
print("Resume:", build_user_facing_message(assessment_resume))

print("\n--- Generating Logs ---")
log_relevance_assessment("sess-1", "good.pdf", assessment_good)
log_relevance_assessment("sess-2", "long.pdf", assessment_long)
log_relevance_assessment("sess-3", "resume.pdf", assessment_resume)

with open("logs/relevance_gate.log", "r") as f:
    print(f.read())
