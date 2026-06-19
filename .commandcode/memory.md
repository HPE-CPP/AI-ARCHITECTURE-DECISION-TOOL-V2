# ArchGuide — AI Architecture Decision Platform

## Executive Summary

Full-stack app that recommends RAG, Fine-Tuning, CAG, or Hybrid architecture for a user's use case.
Core mental model: **messy input → 12 normalized signals → deterministic weighted scoring → explainable recommendation**.
LLMs are used only for extraction from documents, never for the final recommendation.

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Next.js 16 (App Router), React 19, Tailwind CSS 4, Framer Motion |
| Auth | Firebase (Google Sign-In) |
| Backend | FastAPI, SQLAlchemy (sync + psycopg2) |
| Database | PostgreSQL (Supabase) |
| Cache | Redis (Upstash) |
| Vector DB | Qdrant Cloud (in-memory fallback for local dev) |
| LLM | OpenAI / Ollama (with Groq free fallback) |
| Hosting | Vercel (frontend) + Railway (backend, Dockerfile) |

## The 12 Canonical Signals

`dataset_size`, `query_volume`, `latency_requirement`, `data_volatility`, `accuracy_requirement`,
`domain_specificity`, `security_level`, `cost_sensitivity`, `deployment_preference`, `user_scale`,
`citation_requirement`, `context_size`

All input modes (document upload, questionnaire) eventually map to this schema.
Scoring rules, follow-up questions, cost analysis, and result rendering all depend on these 12 signals.

## Domain Model (5 ORM Tables)

- **User** — Firebase UID (PK), name, email (unique), provider, photo_url
- **Project** — workspace container, owned by user, status: empty/in_progress/completed
- **Session** — one analysis run, linked to project, status: draft/processing/completed/error
- **Signal** — one per signal per session, composite index on (session_id, signal_name)
- **Result** — final recommendation, one per session (unique), ranking, scores, why_not, sensitivity, trace

## Two Input Modes

### Document Upload (`.pdf`, `.docx`, `.txt`, max 50MB)
Flow: parse → section detect → Qdrant index → LLM extraction (+ keyword pre-extraction + heuristic fallback) → source verification → anti-hallucination → scoring → persist

### Questionnaire
User answers 12 signals step-by-step → direct mapping with confidence 0.85 → scoring → persist.
No LLM needed. Flat schema sent directly (NOT wrapped in `{answers: {...}}`).

## Pipeline Guardrails (Anti-Hallucination)

1. **Source verification** (`backend/services/signal_extractor.py` lines 530-566):
   LLM `source_text` must literally appear in document; fuzzy fallback if not. Does NOT penalize confidence on failure.

2. **Value normalization** (`backend/app/services/signal_service.py` lines 127-132):
   "on-premise" → "on_premise", "Very High" → "very_high"

3. **Anti-hallucination nulling** (`backend/app/services/signal_service.py` lines 135-168):
   Nulls values below confidence threshold (0.3) OR not in `SCORING_RULES` allowed values.

## Scoring Engine (`backend/services/scoring_engine.py`)

Deterministic weighted scoring with two synergy bonuses:
- **Hybrid synergy**: triggered when ≥2 distinct strong pulls on BOTH RAG and FineTuning sides + ≥1 maximal RAG pull
- **CAG synergy**: +14 points when dataset_size=small AND volatility=static/low AND query_volume=low/medium

Also computes sensitivity analysis (perturbs signals, checks if recommendation flips) with LRU cache (max 1000 entries).

## Key File Map

| Responsibility | File |
|---|---|
| **Production entrypoint** | `backend/main.py` |
| **Dev entrypoint** (extra features) | `backend/app/main.py` |
| Config / env | `backend/config.py` |
| ORM models | `backend/app/db/models.py` |
| DB session (pool_size=10, max_overflow=20) | `backend/app/db/session.py` |
| **Scoring engine** | `backend/services/scoring_engine.py` |
| **Signal extraction** (LLM+keyword+heuristic) | `backend/services/signal_extractor.py` |
| Anti-hallucination + signal persistence | `backend/app/services/signal_service.py` |
| Recommendation persistence | `backend/app/services/recommendation_service.py` |
| Document parsing | `backend/services/document_parser.py` |
| LLM client (OpenAI/Ollama/Groq) | `backend/services/llm_client.py` |
| Qdrant vector store | `backend/app/utils/faiss_store.py` |
| Embeddings | `backend/app/utils/embeddings.py` |
| Redis cache | `backend/app/services/cache_service.py` |
| Cost analysis (INR, heuristic) | `backend/app/services/cost_analysis.py` |
| Firebase auth (security.py) | `backend/app/core/security.py` |
| Rate limiter | `backend/app/limiter.py` |
| Upload router | `backend/app/routers/upload.py` |
| Analysis router | `backend/app/routers/analysis.py` |
| Questionnaire router | `backend/app/routers/questionnaire.py` |
| Chat router | `backend/app/routers/chat.py` |
| Score preview router | `backend/app/routers/score_preview.py` |
| Share router | `backend/app/routers/share_router.py` |
| Projects router | `backend/app/routers/projects.py` |
| Frontend API client | `frontend/src/lib/api.ts` |
| API base URL resolver | `frontend/src/lib/api-base.ts` |
| Project store | `frontend/src/lib/projects-store.ts` |
| Firebase init | `frontend/src/lib/firebase.ts` |
| Auth context | `frontend/src/lib/auth-context.tsx` |
| Results page | `frontend/src/app/results/[analysisId]/page.tsx` |
| What-If Editor | `frontend/src/components/WhatIfEditor.tsx` |
| Document upload component | `frontend/src/components/DocumentUpload.tsx` |
| Landing page | `frontend/src/app/page.tsx` |
| Results dashboard | `frontend/src/components/ResultsDashboard.tsx` |

## Existing Features Confirmed Working

- Score preview endpoint (`POST /api/v1/score-preview`) — wired to WhatIfEditor
- What-If Editor — 809 lines, live sliders, radar chart, cost comparison, save via followup
- Share router — public read-only, no-auth, completed analyses only, status check has a bug
- Chat — streaming + non-streaming, prompt injection guard, token streaming
- Decision trace — timestamped pipeline steps during processing
- Follow-up system — missing/low-confidence signal re-scoring
- Export PDF (analysis + cost) — typed `ExportRequest` schema for DoS protection
- Security headers middleware — `X-Content-Type-Options`, `X-Frame-Options`, CSP, Referrer-Policy

## Known Issues (15 verified)

1. **Two divergent `main.py` files** — `backend/main.py` (production, Dockerfile) is missing: `score_preview` router, `share_router`, orphan session recovery, FAISS cleanup, Alembic auto-migration. `backend/app/main.py` (dev) is missing: `SecurityHeadersMiddleware`, `SlowAPIMiddleware`.
2. **No rate limiting on chat/share endpoints** — `POST /chat`, `POST /chat/stream`, `GET /share/{id}` have zero `@limiter.limit`. Budget drain + scrape risk.
3. **Chat `SIGNAL_LABELS` missing 2 signals** — `citation_requirement` and `context_size` absent from context builder and system prompt.
4. **`QuestionnaireInput` schema has no value validation** — any string accepted, invalid values silently skipped.
5. **`share_router.py` ghost status check** — checks `not in ("complete", "completed")` but Session enum uses `"completed"` only. Also has duplicate comment (line 52).
6. **No `pool_recycle` in DB session** — PostgreSQL connection pools behind load balancers will silently close idle connections.
7. **Health check is a lie** — returns `{"status": "ok"}` without checking PostgreSQL, Redis, or LLM provider.
8. **Firebase dummy config** — when env vars missing, initializes with `{apiKey: "__unconfigured__"}` creating broken instance.
9. **Redis no circuit breaker** — every failure adds connection timeout latency per request.
10. **Blocking `shutil.rmtree` in async upload** — blocks event loop during temp file cleanup.
11. **No request body size limit middleware** — non-upload endpoints accept unlimited payloads.
12. **No cleanup of old Qdrant vectors or completed sessions** — only orphaned `processing` sessions recovered.
13. **Production Qdrant check is cosmetic** — logs connection but doesn't verify functionality, silent failures.
14. **No Alembic migrations in production entrypoint** — uses `create_all()` only, `source_verified` column potentially missing.
15. **Duplicate `ScorePreviewResult` interface** in `api.ts` — defined twice (lines 307-312 and 318-323).
