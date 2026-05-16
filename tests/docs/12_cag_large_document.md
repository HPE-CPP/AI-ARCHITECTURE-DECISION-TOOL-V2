# Internal Knowledge Retrieval System — Requirements Specification
**Project:** Research Reference Assistant  
**Organisation:** Helix Policy Institute  
**Document Version:** 1.0  
**Classification:** Internal Use Only

---

## 1. Executive Summary

Helix Policy Institute is a mid-sized policy research organisation with a small team of 15 analysts. The institute requires a lightweight knowledge retrieval assistant that allows analysts to quickly search and query a fixed library of reference materials, standard operating procedures, and publicly available research publications.

This document specifies the technical and operational requirements for the system. The solution must be simple to operate, cost-efficient, and deployable on the institute's existing on-premises data centre infrastructure without reliance on cloud services.

---

## 2. Organisational Context

The institute employs approximately 40 staff in total. The AI assistant is intended for a small team of 15 policy analysts who regularly consult a fixed corpus of reference materials during their research work. No other departments will access the system in the foreseeable future.

This is a small pilot deployment. There are no plans for enterprise-wide rollout or scaling beyond the current small team.

---

## 3. Dataset Description

### 3.1 Corpus Composition

The knowledge base is a small bounded corpus of reference materials:

- 300 published policy research reports (open-access, publicly available)
- 120 standard operating procedure documents
- 80 reference guides and glossaries

Total corpus: approximately 500 documents. The entire dataset is drawn from public data and open-source publications. No proprietary, confidential, or personally identifiable information is included.

### 3.2 Dataset Size

The corpus is small and well-defined. The total volume of text across all 500 documents is estimated at under 50,000 pages of readable content — well within the scope of a small bounded dataset manageable through direct context-based retrieval.

### 3.3 Data Volatility

The corpus is static and rarely changes. Reference materials are reviewed and updated on an annual cycle by the institute's librarian team. There is no streaming data ingestion, no daily or weekly updates, and no dynamic data feeds. The historical archive nature of the corpus means content is effectively immutable between annual review cycles.

---

## 4. Query Volume and Throughput

### 4.1 Expected Load

The system is an internal tool used exclusively by a small team of 15 analysts. Expected usage:

- Daily active users: 8 to 12 analysts on a typical workday
- Average queries per day: 30 to 60 queries total across the small team
- Peak concurrent sessions: 3 to 4 analysts at once

Query volume is low by design. This is not a public-facing or high-traffic system. There is no expectation of concurrent or high-volume usage beyond the small team.

### 4.2 Query Patterns

Analysts submit ad hoc reference queries during research sessions. Queries are not time-critical — analysts compose queries, submit, and review responses at their own pace. Batch processing of queries during off-peak hours is acceptable.

---

## 5. Latency Requirements

Given the asynchronous and research-oriented nature of the workflow, response times of up to 3 to 5 seconds are fully acceptable. Analysts are not interacting with clients in real time. Batch processing mode is the expected operational pattern.

Ultra-low latency is not required. The system does not need to support real-time inference or streaming responses. Asynchronous query handling is the preferred design to simplify the infrastructure.

---

## 6. Accuracy and Quality

### 6.1 Quality Expectations

As an internal tool and prototype for internal use only, moderate accuracy levels are acceptable during the pilot phase. Analysts understand that the system is a research aid, not a definitive authority. Responses will be reviewed and verified by analysts before use in published work.

### 6.2 Coverage

The system need only answer questions grounded in the provided corpus. Out-of-scope queries (anything not covered by the 500 documents) should be gracefully declined rather than answered with uncertain content.

---

## 7. Domain Specificity

The assistant covers a broad range of general-purpose policy and research topics. The reference corpus spans public policy, economics, governance, and social science — all established fields covered by publicly available literature. No proprietary vocabulary, specialist clinical terminology, or highly specialised domain expertise is required to operate the system.

This is a general-purpose knowledge assistant, not a domain-expert system. General-purpose information retrieval over a well-defined corpus is the primary objective.

---

## 8. Security and Compliance

The knowledge base contains only public data drawn entirely from open-source publications and publicly available government documents. No sensitive, confidential, or personally identifiable information is stored within the system.

Security requirements are standard, commensurate with the entirely public nature of the corpus. No GDPR, HIPAA, or PCI-DSS compliance requirements apply to this system.

---

## 9. Cost Sensitivity

### 9.1 Budget Constraints

The institute operates under very tight budget constraints. The technology budget allocated to this project is minimal. Infrastructure spending must be kept at minimal cost throughout the project lifecycle.

The institute cannot justify recurring per-query cloud API costs or expensive managed services. Very tight budget control is a primary constraint that directly shapes the acceptable architecture options.

### 9.2 Preferred Cost Profile

A self-hosted solution with a one-time setup cost is strongly preferred over a subscription or pay-per-query model. The small team size (15 users) and low query volume (30 to 60 queries per day) make per-query cloud pricing economically unjustifiable.

---

## 10. Deployment

The system will be deployed on the institute's local data centre using existing on-premises server hardware. The data centre already hosts the institute's file servers, internal tools, and administrative systems.

Cloud deployment is not considered for this project. The institute's IT policy requires all internal tools to run within the local data centre. No data should be transmitted to external cloud providers.

---

## 11. User Scale

The initial deployment serves a small team of 15 analysts. There is no roadmap for scaling to additional users or departments within the next two years. The system is explicitly sized for this small team.

---

## 12. Summary

A simple, cost-efficient general-purpose knowledge assistant for a small team of policy analysts. The key characteristics that define this deployment are:

- **Small bounded corpus** (500 documents, public data, open-source)
- **Static data** (rarely changes, annual review cycle, historical archive)
- **Low query volume** (30–60 queries/day from a small team of 15)
- **Relaxed latency** (batch processing, asynchronous, 3–5 seconds acceptable)
- **Very tight budget** (minimal cost, no cloud spend, self-hosted only)
- **General-purpose domain** (public policy and research, no specialised vocabulary)
- **On-premises data centre** deployment on existing hardware

The combination of a small static corpus, low query volume, very tight budget, and general-purpose domain makes this an ideal candidate for a context-based retrieval approach where the entire corpus can be provided directly as context, eliminating the need for vector databases, retrieval pipelines, or model fine-tuning.
