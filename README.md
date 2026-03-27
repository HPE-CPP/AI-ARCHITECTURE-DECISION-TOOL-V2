# 🛠️ AI Architecture Decision Tool

A professional, full-stack AI platform designed to help architects and engineers make data-driven decisions on system design, infrastructure, and technical trade-offs.

---

## 🚀 Getting Started

### 1. Clone the Repository
```bash
git clone https://github.com/Hrithik875/AI-ARCHITECTURE-DECISION-TOOL-V2
cd AI-ARCHITECTURE-DECISION-TOOL-V2
```

---

## 🎨 Frontend Setup (Next.js)

The frontend is built with Next.js 15, Framer Motion for premium animations, and Lucide for iconography.

1. **Navigate to the frontend directory:**
   ```bash
   cd frontend
   ```

2. **Install dependencies:**
   ```bash
   npm install
   ```

3. **Configure Environment Variables:**
   Create a `.env.local` file in the `frontend/` directory (you can copy from `.env.example`):
   ```bash
   cp .env.example .env.local
   ```
   **Required variables:**
   - `NEXT_PUBLIC_FIREBASE_API_KEY`: Your Firebase SDK config
   - `NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN`: Your Firebase Auth domain
   - `NEXT_PUBLIC_API_URL`: `http://localhost:8000` (for local development)

4. **Run the development server:**
   ```bash
   npm run dev
   ```
   Access at: [http://localhost:3000](http://localhost:3000)

---

## ⚙️ Backend Setup (FastAPI)

The backend provides the AI analysis engine, vector storage (FAISS), and PostgreSQL persistence via SQLAlchemy.

1. **Navigate to the backend directory:**
   ```bash
   cd backend
   ```

2. **Create a Virtual Environment:**
   *Recommended: Python 3.11 (Avoid 3.13 due to dependency compatibility)*
   ```bash
   python -m venv venv
   venv\Scripts\activate  # Windows
   # or
   source venv/bin/activate # Linux/macOS
   ```

3. **Install Dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure Environment Variables:**
   Create a `.env` file in the `backend/` directory (copy from `.env.example`):
   ```bash
   cp .env.example .env
   ```
   **Required Credentials:**
   - `DATABASE_URL`: PostgreSQL connection string (Supabase recommended)
   - `REDIS_URL` & `REDIS_TOKEN`: Upstash Redis credentials
   - `OPENAI_API_KEY`: For embeddings and cloud-based LLM analysis

5. **Run the API server:**
   ```bash
   uvicorn app.main:app --reload
   ```
   - **Local URL:** [http://127.0.0.1:8000](http://127.0.0.1:8000)
   - **Interactive Docs (Swagger):** [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

---

## 🛠️ Tech Stack

- **Frontend**: Next.js 15, TypeScript, Framer Motion, Tailwind CSS
- **Backend**: FastAPI (Python 3.11), SQLAlchemy, Alembic
- **Database**: PostgreSQL (Persistence), FAISS (Vector Store for RAG)
- **AI/LLM**: OpenAI (Analysis/Embeddings), Ollama (Local support)
- **Auth**: Firebase Authentication

---

## 📝 Important Notes

- **Database**: Tables are auto-created on the first run. For manual migrations, use `alembic upgrade head`.
- **Python Version**: Stick to **Python 3.11**. Later versions may have issues with specific machine learning dependencies.
- **Entry Point**: Always run the backend using `uvicorn app.main:app` (ensure you are in the `/backend` folder).

---

## 🏃 Running Both (Local Dev)

To run the full platform locally, open two terminal tabs:

**Terminal 1 (Frontend):**
```bash
cd frontend && npm run dev
```

**Terminal 2 (Backend):**
```bash
cd backend && venv\Scripts\activate && uvicorn app.main:app --reload
```

---
*Built for modern architects.* 🏛️✨

