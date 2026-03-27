# Local Setup Guide

Follow these steps to run the project on your local machine.

---

## 1. Clone the Repository

```bash
git clone <your-repo-url>
cd AI-ARCHITECTURE-DECISION-TOOL-V2
```

---

## 2. Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

Frontend will run on:

```
http://localhost:3000
```

---

## 3. Backend Setup

Open a **new terminal**

```bash
cd backend
```

---

### Create Virtual Environment (Python 3.11)

```bash
C:\Users\<your-username>\AppData\Local\Programs\Python\Python311\python.exe -m venv venv
```

---

### Activate Virtual Environment

```bash
venv\Scripts\activate
```

---

### Install Dependencies

```bash
pip install -r requirements.txt
```

---

### Configure Environment Variables

Copy the `.env` file and fill in your credentials:

```
DATABASE_URL=postgresql+psycopg2://USER:PASSWORD@HOST:PORT/DATABASE
REDIS_URL=rediss://your-host.upstash.io:6379
REDIS_TOKEN=your-upstash-redis-token
OPENAI_API_KEY=your-openai-api-key
```

Required services:
- **Supabase** — PostgreSQL database (free tier works)
- **Upstash** — Redis (free tier works)
- **OpenAI** — API key for analysis + embeddings

---

### Run Database Migrations

> Tables are auto-created on first startup. For future schema changes:

```bash
alembic revision --autogenerate -m "describe your change"
alembic upgrade head
```

---

### Run Backend

```bash
uvicorn app.main:app --reload
```

Backend will run on:

```
http://127.0.0.1:8000
API Docs: http://127.0.0.1:8000/docs
```

---

## Notes

* Make sure you are using **Python 3.11**
* Do NOT use Python 3.13 (causes dependency issues)
* Always activate `venv` before running backend
* Entry point changed from `main:app` to `app.main:app`

---

## Running Both

Use two terminals:

### Terminal 1 (Frontend)

```bash
cd frontend
npm run dev
```

### Terminal 2 (Backend)

```bash
cd backend
venv\Scripts\activate
uvicorn app.main:app --reload
```

Frontend + Backend should now be running locally.
