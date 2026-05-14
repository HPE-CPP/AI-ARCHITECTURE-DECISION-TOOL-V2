# Pipeline Test Guide

Convert each markdown file to PDF before uploading. You can do this free at:
https://www.markdowntopdf.com or paste into Google Docs and export as PDF.

---

## Files and What to Expect

| File | Expected Result | Tests |
|------|----------------|-------|
| 01_perfect_rag_candidate | PASS — RAG recommended | All 10 signals extracted, on-premise, specialized domain, weekly updates |
| 02_perfect_finetuning_candidate | PASS — Fine-Tuning recommended | Static dataset, HIPAA, critical accuracy, on-premise, proprietary domain |
| 03_perfect_cag_candidate | PASS — CAG recommended | Tiny bounded corpus, fits in context, low volume, on-premise |
| 04_perfect_hybrid_candidate | PASS — Hybrid recommended | Real-time feeds + static corpus, cloud + on-premise, enterprise scale |
| 05_edge_case_ambiguous_signals | PASS — lower confidence | Vague requirements, LLM must infer, expect moderate confidence score |
| 06_edge_case_minimal_valid | PASS — barely clears gates | 80+ words, 3+ signal categories, minimal detail |
| 07_rejection_too_short | REJECT — too short | Under 80 words, blocked at word count gate |
| 08_rejection_wrong_doc_type | REJECT — wrong doc type | Cost analysis report, no system requirements, blocked at keyword gate |
| 09_rejection_archguide_report | REJECT — circular upload | ArchGuide-generated PDF, blocked at circular upload detection |
| 10_stress_test_large_doc | PASS — Hybrid recommended | Long doc, chunked processing, all 10 signals spread across sections |
| 11_rejection_low_density | REJECT — wrong doc type | Company newsletter, mentions data/users but no system requirements |

---

## What Each Test Proves

### Valid Documents (01 to 06, 10)
- All 10 signals get extracted and verified against source text
- Confidence scores reflect how explicitly requirements are stated
- 01 and 02 should be high confidence (0.7+)
- 05 should be lower confidence (0.4 to 0.6) since signals are implied not stated
- 06 tests the minimum viable document — just enough to pass

### Rejection Documents (07, 08, 09, 11)
- 07 tests the word count gate (Layer 1)
- 08 and 11 test the keyword category gate (Layer 2) — both are real documents but not requirements docs
- 09 tests circular upload detection (Layer 0) — specifically targets ArchGuide-generated PDFs
- None of these should ever reach the LLM

### Stress Test (10)
- Tests chunked parallel extraction (document is long enough to split)
- All signals should be found even though they are spread across 13 sections
- Should not trigger signal concentration warning since signals come from different pages

---

## Signal Concentration Warning

If you see a warning saying "all signals extracted from a single page" — that means
the document passed the gates but all its useful content was in one paragraph.
Files 05 and 06 might trigger this if the LLM clusters all findings onto page 1.
This is expected and correct behaviour.

---

## Green Flags (signs the pipeline is working correctly)

- Rejections happen BEFORE signal extraction (check Decision Trace — no signal_extraction step for rejected docs)
- Confidence scores scale with how explicitly requirements are written (01 > 05 > 06)
- Source text shown in the results actually appears in the document
- Architecture recommendation changes between 01, 02, 03, 04 (each should give a different one)

## Red Flags (signs something is wrong)

- A rejection file gets through and produces a recommendation
- All 4 architecture files produce the same recommendation
- Confidence is 90%+ for the ambiguous file (05) — means LLM is overconfident
- Source text shown in results does NOT appear in the uploaded document
