# 🤖 AI App Builder — Python Edition (FastAPI)

Generate complete Python web apps from a text description.
Downloads as a ZIP — extract and run with `python app.py`.

---

## ⚡ Quick Start

### Step 1 — Make sure Python 3.9+ is installed
```bash
python --version   # should say 3.9 or higher
```

### Step 2 — Create a virtual environment (recommended)
```bash
python -m venv venv

# Activate:
# Windows PowerShell:
venv\Scripts\Activate.ps1
# Windows CMD:
venv\Scripts\activate.bat
# Mac / Linux:
source venv/bin/activate
```

### Step 3 — Install dependencies
```bash
pip install -r requirements.txt
```

### Step 4 — Start the server
```bash
uvicorn server:app --reload --port 3000
```

### Step 5 — Open the dashboard
```
http://localhost:3000
```

---

## 🔑 Anthropic API Key (optional)

1. Get key from https://console.anthropic.com
2. Paste into the **API Key** field in the dashboard
3. Generate → Claude AI writes all the Python code

Without key → smart FastAPI template is generated (still fully working).

---

## 📦 What Gets Generated

Every generated project contains:

| File | Purpose |
|------|---------|
| `app.py` | FastAPI main app |
| `requirements.txt` | All pip dependencies |
| `templates/index.html` | Frontend UI |
| `static/style.css` | Styles |
| `static/app.js` | Frontend JS |
| `README.md` | Install & run guide |
| `Dockerfile` | (if Docker enabled) |
| `tests/test_app.py` | (if Tests enabled) |

---

## 🚀 After Downloading a Generated ZIP

```bash
# 1. Extract the ZIP
# 2. Open in VS Code:  code .

# 3. Create venv and install:
python -m venv venv
venv\Scripts\activate     # Windows
pip install -r requirements.txt

# 4. Run:
python app.py
# → http://localhost:3000
```

---

## 🌐 API Routes (this server)

| Route | Method | Description |
|-------|--------|-------------|
| `GET /` | GET | Dashboard UI |
| `POST /generate` | POST | Generate app (SSE stream) |
| `GET /download/{id}` | GET | Download ZIP |
| `GET /projects` | GET | List all projects |
| `GET /files/{id}` | GET | File tree of project |
| `GET /file/{id}/{path}` | GET | File content |

---

*Made with AI App Builder — Python Edition*
