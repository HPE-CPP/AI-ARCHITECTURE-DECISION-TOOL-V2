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

### Run Backend

```bash
uvicorn main:app --reload
```

Backend will run on:

```
http://127.0.0.1:8000
```

---

## Notes

* Make sure you are using **Python 3.11**
* Do NOT use Python 3.13 (causes dependency issues)
* Always activate `venv` before running backend

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
uvicorn main:app --reload
```

Frontend + Backend should now be running locally.
