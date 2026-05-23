# ArchGuide / AI Architecture Decision Tool

> Stop guessing between RAG, Fine-Tuning, CAG, and Hybrid. ArchGuide analyses your requirements and recommends the right AI architecture instantly.

**Live Demo:** [https://archguide-ashy.vercel.app](https://archguide-ashy.vercel.app)

---

## Stack

| Layer | Technology |
|---|---|
| Frontend | Next.js 16, React 19, Tailwind CSS, Framer Motion |
| Backend | FastAPI (Python 3.11), SQLAlchemy, Alembic |
| Database | PostgreSQL (Supabase) |
| Cache | Redis (Upstash) |
| Auth | Firebase (Google Sign-In) |
| LLM | OpenAI / Groq (free fallback) |
| Vector DB | Qdrant Cloud |
| Hosting | Vercel (frontend) + Railway (backend) |

---

## Cloud Deployment

The app is fully deployed:

- **Frontend:** [https://archguide-ashy.vercel.app](https://archguide-ashy.vercel.app)
- **Backend:** [https://archguide-backend-production.up.railway.app](https://archguide-backend-production.up.railway.app)
- **API Docs:** [https://archguide-backend-production.up.railway.app/docs](https://archguide-backend-production.up.railway.app/docs)

---

## Local Setup Guide

### Prerequisites

- Python 3.10 or 3.11 (not 3.13)
- Node.js 18+
- PostgreSQL
- Redis

---

### 1. Clone Repository

```bash
git clone https://github.com/HPE-CPP/AI-ARCHITECTURE-DECISION-TOOL-V2
cd AI-ARCHITECTURE-DECISION-TOOL-V2
```

---

### 2. Backend Setup

#### 2.1 Navigate to backend

```bash
cd backend
```

#### 2.2 Create virtual environment

```bash
python -m venv venv
```

#### 2.3 Activate environment

Windows:
```bash
venv\Scripts\Activate
```

Mac/Linux:
```bash
source venv/bin/activate
```

#### 2.4 Install dependencies

```bash
pip install -r requirements.txt
```

#### 2.5 Setup PostgreSQL

Install PostgreSQL and create a database:

```sql
CREATE DATABASE "hpe-project";
```

#### 2.6 Setup Redis

Install Redis locally or use [Upstash](https://upstash.com) (free). Ensure it is running on `localhost:6379`.

#### 2.7 Create backend `.env`

Create `backend/.env` with:

```env
DATABASE_URL=postgresql://postgres:YOUR_PASSWORD@localhost:5432/hpe-project

REDIS_URL=redis://localhost:6379
REDIS_TOKEN=

# LLM — use either OpenAI or Groq (free)
OPENAI_API_KEY=sk-...
# GROQ_API_KEY=gsk_...   ← free alternative if no OpenAI key
DEFAULT_LLM_PROVIDER=openai

CORS_ORIGINS=["http://localhost:3000"]

FIREBASE_CREDENTIALS_PATH=./firebase-service-account.json
```

> **LLM fallback:** If `OPENAI_API_KEY` is not set, the backend automatically falls back to Groq (free). Get a Groq key at [console.groq.com](https://console.groq.com).

#### 2.8 Run Alembic migrations

```bash
alembic upgrade head
```

#### 2.9 Run backend

```bash
uvicorn main:app --reload
```

Expected output:
```
PostgreSQL connection successful!
Application startup complete.
Uvicorn running on http://0.0.0.0:8000
```

---

### 3. Frontend Setup

#### 3.1 Navigate to frontend

```bash
cd frontend
```

#### 3.2 Install dependencies

```bash
npm install
```

#### 3.3 Create `.env.local`

Create `frontend/.env.local` with:

```env
NEXT_PUBLIC_FIREBASE_API_KEY=your_api_key
NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN=your_project.firebaseapp.com
NEXT_PUBLIC_FIREBASE_PROJECT_ID=your_project_id
NEXT_PUBLIC_FIREBASE_STORAGE_BUCKET=your_project.appspot.com
NEXT_PUBLIC_FIREBASE_MESSAGING_SENDER_ID=xxxx
NEXT_PUBLIC_FIREBASE_APP_ID=xxxx

NEXT_PUBLIC_API_URL=http://localhost:8000
```

#### 3.4 Setup Firebase

1. Go to [console.firebase.google.com](https://console.firebase.google.com)
2. Create a project → Add Web App → copy config values into `.env.local`
3. Enable **Google** sign-in under Authentication → Sign-in methods
4. Add `localhost` to Authentication → Settings → Authorized domains

#### 3.5 Run frontend

```bash
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

---

### 4. Running the Project

Run in two terminals simultaneously:

**Terminal 1 — Backend:**
```bash
cd backend
venv\Scripts\Activate      # Windows
uvicorn main:app --reload
```

**Terminal 2 — Frontend:**
```bash
cd frontend
npm run dev
```

---

### 5. Verification

| Service | URL |
|---|---|
| Frontend | http://localhost:3000 |
| Backend API | http://localhost:8000/docs |
| Health check | http://localhost:8000/api/v1/health |

---

### 6. Common Issues

**`uvicorn: command not found`**
- Virtual environment not activated

**Firebase sign-in not working**
- Check `.env.local` values are correct
- Make sure `localhost` is in Firebase Authorized Domains

**Database connection refused**
- PostgreSQL not running, or wrong password in `DATABASE_URL`

**VS Code import errors**
- Set Python interpreter to `backend/venv/Scripts/python.exe`

---

### 7. Notes

- Backend reads from `backend/.env`
- Frontend reads from `frontend/.env.local`
- Restart frontend after any env changes
- Do not use Python 3.13
- Redis is optional for local dev — the app works without it (caching disabled)
