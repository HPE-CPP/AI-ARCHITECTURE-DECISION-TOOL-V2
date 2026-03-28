# AI Architecture Decision Tool : Local Setup Guide

This guide sets up the full stack locally:

* Frontend (Next.js)
* Backend (FastAPI)
* PostgreSQL (database)
* Redis (required)
* Firebase (authentication)

---

## 1. Clone Repository

```bash
git clone https://github.com/Hrithik875/AI-ARCHITECTURE-DECISION-TOOL-V2
cd AI-ARCHITECTURE-DECISION-TOOL-V2
```

---

## 2. Backend Setup

### 2.1 Navigate to backend

```bash
cd backend
```

---

### 2.2 Create virtual environment

Use Python 3.10 or 3.11.

```bash
python -m venv venv
```

---

### 2.3 Activate environment

Windows:

```bash
venv\Scripts\Activate
```

---

### 2.4 Install dependencies

```bash
pip install -r requirements.txt
```

---

### 2.5 Setup PostgreSQL

* Install PostgreSQL
* Create database:

```sql
CREATE DATABASE "hpe-project";
```

---

### 2.6 Setup Redis

* Install Redis locally (or use a hosted instance like Upstash)
* Ensure it is running on:

```text
localhost:6379
```

---

### 2.7 Create backend `.env`

Create file:

```bash
backend/.env
```

Add:

```env
DATABASE_URL=postgresql://postgres:YOUR_PASSWORD@localhost:5432/hpe-project

REDIS_URL=redis://localhost:6379
REDIS_TOKEN=your_token_if_required

OPENAI_API_KEY=your_key
```

---

### 2.8 Run backend

```bash
uvicorn app.main:app --reload
```

Expected output includes:

```text
PostgreSQL connection successful!
Application startup complete.
```

---

## 3. Frontend Setup

### 3.1 Navigate to frontend

```bash
cd frontend
```

---

### 3.2 Install dependencies

```bash
npm install
```

---

### 3.3 Create `.env.local`

Create:

```bash
frontend/.env.local
```

---

### 3.4 Setup Firebase

1. Go to https://console.firebase.google.com/
2. Create project
3. Add Web App
4. Copy config values

---

### 3.5 Add environment variables

```env
NEXT_PUBLIC_FIREBASE_API_KEY=your_api_key
NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN=your_project.firebaseapp.com
NEXT_PUBLIC_FIREBASE_PROJECT_ID=your_project_id
NEXT_PUBLIC_FIREBASE_STORAGE_BUCKET=your_project.appspot.com
NEXT_PUBLIC_FIREBASE_MESSAGING_SENDER_ID=xxxx
NEXT_PUBLIC_FIREBASE_APP_ID=xxxx

NEXT_PUBLIC_API_URL=http://localhost:8000
```

---

### 3.6 Run frontend

```bash
npm run dev
```

Open:

```text
http://localhost:3000
```

---

## 4. Running the Project

Run in two terminals:

### Backend

```bash
cd backend
venv\Scripts\Activate
uvicorn app.main:app --reload
```

---

### Frontend

```bash
cd frontend
npm run dev
```

---

## 5. Verification

* Backend: http://127.0.0.1:8000/docs
* Frontend: http://localhost:3000
* Login: Google sign-in should open popup

---

## 6. Common Issues

### FastAPI not found

* Virtual environment not activated

### Firebase not configured

* `.env.local` missing or incorrect
* Firebase config not updated in `firebase.ts`

### VS Code import errors

* Select interpreter:

```text
backend/venv/Scripts/python.exe
```

---

## 7. Notes

* Backend uses `.env`
* Frontend uses `.env.local`
* Restart frontend after any env changes
* Do not use Python 3.13

---
