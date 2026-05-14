# AI Assistant Requirements
**Project:** Legal Contract Review Chatbot  
**Client:** Meridian Law Partners LLP  
**Date:** May 2026

---

## 1. Overview

Meridian Law Partners requires an AI assistant that helps junior associates review and query a fixed set of standard contract templates. The firm uses a library of 200 master contract templates that are reviewed and updated once per year by the senior partners committee. The assistant must answer questions about specific clauses, flag deviations from standard language, and explain the implications of contract terms.

---

## 2. Dataset Description

The knowledge base is extremely small and well-defined:

- 200 standard contract templates (total approximately 800 pages)
- A glossary of 150 firm-specific legal terms
- 50 annotated case summaries explaining key precedents

The entire dataset fits comfortably within 400,000 tokens. This is a closed, bounded corpus. No external legal databases, no internet access, no real-time data feeds. The dataset is static — templates are updated once annually during the firm's annual review cycle. There is no streaming, no daily updates, and no dynamic data ingestion.

---

## 3. Query Patterns

Associates query the system during contract review sessions:

- "Does clause 7.3 match our standard indemnity language?"
- "What is the firm's preferred arbitration clause?"
- "Flag any deviation from standard liability cap wording."

The user base is small — 25 associates at the firm. Query volume is low, roughly 50 to 100 queries per day total. There is no expectation of high concurrency. At most 5 associates may use the tool simultaneously.

---

## 4. Latency Requirements

Responses must arrive within 1 second. Associates are reviewing contracts in real time alongside clients. Any delay beyond 1 second breaks their workflow. Ultra-low latency is not required but sub-second response is the target.

---

## 5. Accuracy and Compliance

Legal accuracy is critical. The assistant must only reference the firm's own templates and must never generate content that is not grounded in the provided documents. Any hallucinated clause could constitute legal malpractice. Source citation is required for every response. The system will be audited by senior partners quarterly.

---

## 6. Domain Specificity

Meridian Law Partners specialises in corporate M&A, private equity, and commercial real estate. The contract templates use firm-specific clause numbering and terminology that differs from general legal databases. The domain is highly specialized and proprietary.

---

## 7. Security

All contract templates are confidential client work product. The system must run on the firm's private on-premise servers. No data can leave the firm's network. Access is restricted to credentialed associates and partners only.

---

## 8. Cost Sensitivity

The firm has a limited technology budget. The solution must avoid recurring per-query cloud API costs. A self-hosted, cost-efficient solution is strongly preferred. The firm cannot justify open-ended inference costs for a 25-person user base.

---

## 9. Deployment

On-premise deployment on the firm's existing server infrastructure. Cloud deployment is prohibited. The system must work without internet access during operation.

---

## 10. Summary

A bounded, self-contained AI assistant over a small, static, well-defined document set. No retrieval complexity needed — the entire corpus can be provided as context. Speed, accuracy, and cost efficiency are the priorities.
