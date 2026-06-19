"""Generate a ~10 MB test .txt file with realistic architecture requirements.
Upload using the .txt upload option — faster generation than PDF.
"""
from pathlib import Path

OUTPUT = Path(__file__).resolve().parents[1] / "tests" / "pdf_versions" / "99_large_10mb.txt"

BLOCK = """
SECTION: Architecture Requirements Specification
================================================

DATA VOLUME AND SCALE:
The GlobalPay cross-border payment platform expects to process approximately
2 million transactions per day at launch growing to 15 million transactions
per day within 18 months. Peak throughput is expected at 3,500 transactions
per second during holiday shopping seasons. Total daily data generation is
estimated at 50 GB of structured data and 200 GB of log data.

QUERY PATTERNS AND LATENCY:
Transaction lookups require 2,500 queries per second at peak with sub-100ms
response time for 95th percentile. Fraud detection queries require sub-50ms
response time as they are in the critical path. Compliance verification
queries have a relaxed 2-second SLA. Customer-facing balance inquiries
require 10,000 queries per second at peak with strict sub-200ms latency.

DATA VOLATILITY:
Transaction data is written once and rarely modified serving as an immutable
audit log. Exchange rates are updated every 15 minutes from 3 external
providers with automatic failover. Fraud detection models are retrained
daily using the previous 90 days of transaction data representing roughly
5 TB per training cycle.

ACCURACY REQUIREMENTS:
Zero tolerance for errors in financial calculations, currency conversions,
or routing decisions. Fraud detection must maintain a false positive rate
below 0.1 percent while keeping false negatives below 0.01 percent.
Exchange rate accuracy must be maintained to 6 decimal places.

DOMAIN SPECIFICITY:
Highly regulated financial services domain requiring deep knowledge of
SWIFT SEPA ACH wire transfers real-time payment schemes GDPR PSD2 AML KYC
OFAC sanctions screening FATCA ISO 20022 messaging and PCI DSS compliance.
This is a strong candidate for fine-tuning on specialized financial data.

SECURITY AND COMPLIANCE:
PCI DSS Level 1 compliance is mandatory. SOC 2 Type II certification must
be achieved within 12 months. Multi-factor authentication with hardware
security keys. Complete audit logging with tamper-evident logs retained for
7 years. Data residency requirements across 45 plus jurisdictions.

COST SENSITIVITY:
Initial budget of $5 million for year one. Ongoing operational costs must
not exceed $300,000 per month. Cost per transaction target under $0.002.
Total cost of ownership over 3 years not to exceed $15 million.

DEPLOYMENT:
Primary deployment on AWS us-east-1 with disaster recovery in eu-west-2.
Kubernetes for container orchestration with automated scaling policies.
Edge computing for latency-sensitive fraud detection checks. Hybrid
architecture combining dedicated instances with serverless burst capacity.

USER SCALE:
50,000 plus active merchants and 10 million plus end users globally.
Support for 120 plus currencies across 45 plus countries. Moderate to
high user scale requiring horizontal scaling and multi-region deployment.

INTEGRATION REQUIREMENTS:
15 plus banking partners via REST SOAP and ISO 20022 messaging protocols.
3 currency exchange rate providers with automatic failover. 2 fraud
detection engines plus one custom-built internal engine. Regulatory
compliance databases from 45 plus different countries.

PERFORMANCE REQUIREMENTS:
99.99 percent uptime SLA for transaction processing. Sub-200ms end-to-end
latency for 99th percentile requests. Support 3x peak-to-average traffic
ratio. Automatic failover under 30 seconds with no data loss.

CITATION REQUIREMENTS:
All compliance-related answers must cite specific regulatory documents
with exact section references. Financial calculations must reference the
source rate provider and timestamp of the rate query.

CONTEXT SIZE:
The regulatory document corpus spans approximately 50,000 pages across
45 jurisdictions. Each jurisdiction maintains 500 to 2,000 pages of
compliance requirements in varying document formats.

====================================================================
END OF SECTION
====================================================================

"""


def main():
    target = 10 * 1024 * 1024
    with open(OUTPUT, "w", encoding="utf-8") as f:
        written = 0
        while written < target:
            f.write(BLOCK)
            written += len(BLOCK)
    mb = OUTPUT.stat().st_size / (1024 * 1024)
    print(f"Generated: {OUTPUT}")
    print(f"Size: {mb:.1f} MB")
    print(f"Lines: {sum(1 for _ in open(OUTPUT, encoding='utf-8'))}")


if __name__ == "__main__":
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    main()
