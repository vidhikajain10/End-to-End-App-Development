"""
AI App Builder — Python Backend (FastAPI)
=========================================
Run:  uvicorn server:app --reload --port 3000
Open: http://localhost:3000
"""

import os
import re
import json
import shutil
import zipfile
import asyncio
import httpx
from pathlib import Path
from datetime import datetime
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import StreamingResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from fastapi import HTTPException
from fastapi.responses import StreamingResponse, FileResponse
try:
    import psycopg2
except Exception:
    psycopg2 = None



# ─── App Setup ───────────────────────────────────────────────────────────────
app = FastAPI(title="AI App Builder", version="2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
PROJECTS_DIR = Path("/tmp/generated_apps")
PROJECTS_DIR.mkdir(parents=True, exist_ok=True)

DATABASE_URL = os.getenv("DATABASE_URL")

def save_project(app_name, prompt):
    if not DATABASE_URL:
        print("DATABASE_URL not configured")
        return

    if psycopg2 is None:
        print("psycopg2 not available")
        return

    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        
    except Exception as e:
        print("Database Error:", e)
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO projects (app_name, prompt)
        VALUES (%s, %s)
    """, (app_name, prompt))

    conn.commit()
    cur.close()
    conn.close()


# ─── Request Models ───────────────────────────────────────────────────────────
class Options(BaseModel):
    docker: bool = True
    auth: bool = False
    postgres: bool = False
    tests: bool = True
    apiKey: str = ""


class GenerateRequest(BaseModel):
    idea: str
    options: Options = Options()


# ─── Helpers ─────────────────────────────────────────────────────────────────
def slugify(text: str) -> str:
    """Convert idea text to a safe folder name."""
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")[:40] or "my_app"


def sse(type_: str, **data) -> str:
    """Format a Server-Sent Event line."""
    payload = json.dumps({"type": type_, **data})
    return f"data: {payload}\n\n"


def count_lines(files: list[dict]) -> int:
    return sum(len(f.get("content", "").splitlines()) for f in files)


# ─── AI Generation ───────────────────────────────────────────────────────────
async def call_ai(system_prompt: str, user_prompt: str, api_key: str) -> str:
    """Call Anthropic Claude API and return text response."""
    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "Content-Type": "application/json",
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
            },
            json={
                "model": "claude-sonnet-4-20250514",
                "max_tokens": 4096,
                "system": system_prompt,
                "messages": [{"role": "user", "content": user_prompt}],
            },
        )
    if not resp.is_success:
        raise RuntimeError(f"AI API error {resp.status_code}: {resp.text[:200]}")
    data = resp.json()
    return data["content"][0]["text"]


async def generate_project_ai(idea: str, options: Options) -> dict:
    """Use Claude AI to generate the full project."""
    system_prompt = """You are an expert full-stack Python developer.
Generate a COMPLETE, WORKING web application based on the user's idea.
Respond ONLY with valid JSON (no markdown, no backticks, no explanation).
JSON structure:
{
  "projectName": "snake_case_name",
  "stack": "description of tech stack",
  "files": [
    { "path": "relative/file/path.ext", "content": "full file content here" }
  ]
}
Rules:
- Generate a REAL working Python app
- Main entry: app.py using FastAPI or Flask
- Include index.html with full working UI (served by the backend)
- Include requirements.txt with all dependencies
- Include README.md with install/run instructions
- Include static/style.css and static/app.js
- package.json is NOT needed (this is Python)
- All contents must be complete and functional
- requirements.txt must include uvicorn if FastAPI is used"""

    user_prompt = f"""App idea: {idea}

Options:
- Docker: {"yes" if options.docker else "no"}
- Auth system: {"yes" if options.auth else "no"}
- PostgreSQL: {"yes" if options.postgres else "no"}
- Test suite: {"yes" if options.tests else "no"}

Generate a complete, production-ready Python project."""

    raw = await call_ai(system_prompt, user_prompt, options.apiKey)
    clean = re.sub(r"```json\n?", "", raw, flags=re.IGNORECASE)
    clean = re.sub(r"```\n?", "", clean).strip()
    return json.loads(clean)


def build_readme(idea: str, project_data: dict, files: list[str]) -> str:
    name = project_data.get("projectName", "generated_app")
    stack = project_data.get("stack", "FastAPI + HTML/CSS/JS")
    file_list = "\n".join(f"- {f}" for f in files[:20])
    if len(files) > 20:
        file_list += f"\n- ...and {len(files) - 20} more"
    return f"""# {name}

> Generated by AI App Builder (Python Edition)

## About
{idea}

## Tech Stack
{stack}

## Files ({len(files)} total)
{file_list}

## Quick Start

### Prerequisites
- Python 3.9+
- pip

### Install & Run
```bash
# Create virtual environment (recommended)
python -m venv venv

# Activate it
# Windows:
venv\\Scripts\\activate
# Mac/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Start the app
python app.py
# OR
uvicorn app:app --reload --port 3000
```

The app will be available at: http://localhost:3000

---
*Generated by AI App Builder — Python Edition*
"""


def build_fallback_project(idea: str, options: Options) -> dict:
    """Smart fallback when no API key is provided."""
    name = slugify(idea)
    title = idea[:60]

    files = [
        {
            "path": "app.py",
            "content": f'''"""
{title}
Generated by AI App Builder — Python Edition
"""
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from pathlib import Path
import uvicorn

app = FastAPI(title="{title}")

# Serve static files (CSS, JS)
if Path("static").exists():
    app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/", response_class=HTMLResponse)
async def root():
    html = Path("templates/index.html").read_text()
    return HTMLResponse(content=html)

@app.get("/api/health")
async def health():
    return {{"status": "ok", "app": "{title}"}}

@app.get("/api/data")
async def get_data():
    return {{"message": "Hello from {title}!", "items": ["Item 1", "Item 2", "Item 3"]}}

if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=3000, reload=True)
''',
        },
        {
            "path": "requirements.txt",
            "content": "fastapi==0.110.0\nuvicorn[standard]==0.28.0\npython-multipart==0.0.9\nhttpx==0.27.0\n"
            + ("psycopg2-binary==2.9.9\n" if options.postgres else "")
            + ("pytest==8.1.0\nhttpx==0.27.0\n" if options.tests else ""),
        },
        {
            "path": "templates/index.html",
            "content": f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title}</title>
  <link rel="stylesheet" href="/static/style.css">
</head>
<body>
  <div id="app">
    <header>
      <h1>{title}</h1>
      <p class="subtitle">Built with AI App Builder — Python Edition</p>
    </header>
    <main>
      <div class="card">
        <h2>🚀 Your App is Ready!</h2>
        <p>Customize this app in VS Code. The backend runs on FastAPI.</p>
        <button id="actionBtn" class="btn">Fetch Data from API</button>
      </div>
      <div class="card" id="output" style="display:none">
        <h3>API Response</h3>
        <pre id="outputText"></pre>
      </div>
    </main>
  </div>
  <script src="/static/app.js"></script>
</body>
</html>""",
        },
        {
            "path": "static/style.css",
            "content": """*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
:root {
  --bg: #0f172a; --bg2: #1e293b; --border: #334155;
  --text: #f1f5f9; --text2: #94a3b8;
  --accent: #6366f1; --accent-hover: #818cf8;
  --radius: 12px;
}
body { font-family: system-ui, sans-serif; background: var(--bg); color: var(--text); min-height: 100vh; display: flex; align-items: center; justify-content: center; padding: 20px; }
#app { width: 100%; max-width: 700px; }
header { text-align: center; margin-bottom: 40px; }
header h1 { font-size: 2rem; font-weight: 800; background: linear-gradient(135deg, #6366f1, #a855f7); -webkit-background-clip: text; -webkit-text-fill-color: transparent; margin-bottom: 8px; }
.subtitle { color: var(--text2); }
.card { background: var(--bg2); border: 1px solid var(--border); border-radius: var(--radius); padding: 28px; margin-bottom: 16px; }
.card h2, .card h3 { margin-bottom: 12px; }
.card p { color: var(--text2); line-height: 1.7; }
pre { background: #0c0d10; border-radius: 8px; padding: 16px; font-size: 13px; color: #22c78a; overflow-x: auto; margin-top: 8px; }
.btn { display: inline-block; margin-top: 16px; padding: 10px 24px; background: var(--accent); color: #fff; border: none; border-radius: 8px; font-size: 15px; font-weight: 600; cursor: pointer; transition: background .2s; }
.btn:hover { background: var(--accent-hover); }
""",
        },
        {
            "path": "static/app.js",
            "content": f"""// {title} — Frontend Logic
document.addEventListener('DOMContentLoaded', () => {{
  const btn = document.getElementById('actionBtn');
  const output = document.getElementById('output');
  const outputText = document.getElementById('outputText');

  btn.addEventListener('click', async () => {{
    btn.textContent = 'Loading...';
    btn.disabled = true;
    try {{
      const res = await fetch('/api/data');
      const data = await res.json();
      output.style.display = 'block';
      outputText.textContent = JSON.stringify(data, null, 2);
      btn.textContent = '✓ Data fetched!';
      btn.style.background = '#22c55e';
    }} catch (err) {{
      outputText.textContent = 'Error: ' + err.message;
      output.style.display = 'block';
      btn.textContent = 'Retry';
      btn.disabled = false;
    }}
  }});
}});
""",
        },
    ]

    if options.docker:
        files.append(
            {
                "path": "Dockerfile",
                "content": """FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 3000
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "3000"]
""",
            }
        )
        files.append(
            {
                "path": "docker-compose.yml",
                "content": f"""version: '3.8'
services:
  app:
    build: .
    ports:
      - "3000:3000"
    environment:
      - ENV=production
""",
            }
        )

    if options.tests:
        files.append(
            {
                "path": "tests/test_app.py",
                "content": f"""\"\"\"Tests for {title}\"\"\"
import pytest
from httpx import AsyncClient
from app import app


@pytest.mark.asyncio
async def test_health():
    async with AsyncClient(app=app, base_url="http://test") as client:
        resp = await client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_data_endpoint():
    async with AsyncClient(app=app, base_url="http://test") as client:
        resp = await client.get("/api/data")
    assert resp.status_code == 200
    assert "message" in resp.json()
""",
            }
        )

    file_paths = [f["path"] for f in files]
    files.append({"path": "README.md", "content": build_readme(idea, {"projectName": name, "stack": "FastAPI + HTML/CSS/JS"}, file_paths)})

    return {
        "projectName": name,
        "stack": "FastAPI + Jinja2 + HTML/CSS/JS" + (" + Docker" if options.docker else "") + (" + pytest" if options.tests else ""),
        "files": files,
    }


# --- Routes ---

class RegisterRequest(BaseModel):
    username: str
    email: str
    password: str


class LoginRequest(BaseModel):
    email: str
    password: str


@app.post("/register")
async def register(req: RegisterRequest):

    if psycopg2 is None:
        raise HTTPException(500, "Database unavailable")

    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()

    cur.execute(
        """
        INSERT INTO users (username, email, password_hash)
        VALUES (%s, %s, %s)
        """,
        (req.username, req.email, req.password)
    )

    conn.commit()
    cur.close()
    conn.close()

    return {"success": True,
            "message": "User created successfully"}


@app.post("/login")
async def login(req: LoginRequest):

    if psycopg2 is None:
        raise HTTPException(500, "Database unavailable")

    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()

    cur.execute(
        """
        SELECT id, username
        FROM users
        WHERE email=%s AND password_hash=%s
        """,
        (req.email, req.password)
    )

    user = cur.fetchone()

    cur.close()
    conn.close()

    if not user:
        raise HTTPException(401, "Invalid credentials")

    return {
        "success": True,
        "user_id": user[0],
        "username": user[1]
    }







# ─── Routes ──────────────────────────────────────────────────────────────────
@app.get("/")
async def home():
    return FileResponse("login.html")


@app.get("/register-page")
async def register_page():
    return FileResponse("register.html")


@app.get("/dashboard")
async def dashboard():
    return FileResponse("dashboard.html")


@app.get("/builder")
async def builder():
    return FileResponse("index.html")



@app.post("/generate")
async def generate(req: GenerateRequest):
    """Main generation endpoint — streams SSE progress events."""
    idea = req.idea.strip()
    save_project(
    app_name=slugify(idea),
    prompt=idea
)
    if not idea:
        raise HTTPException(400, "No idea provided")

    options = req.options
    project_id = f"{slugify(idea)}_{int(datetime.now().timestamp() * 1000)}"
    project_dir = PROJECTS_DIR / project_id

    async def stream():
        def s(type_, **data):
            return sse(type_, **data)

        yield s("log", agent="system", msg="Pipeline initialized. Python backend active.")
        yield s("agent", agent="planner", status="active")
        yield s("progress", pct=5, label="Analyzing idea...")
        await asyncio.sleep(0.4)

        yield s("log", agent="planner", msg=f'Parsing idea: "{idea[:60]}..."')
        yield s("progress", pct=15, label="Planning architecture...")
        await asyncio.sleep(0.4)

        yield s("log", agent="planner", msg="Identifying modules: routes, templates, static, models...")
        yield s("agent", agent="planner", status="done")
        yield s("agent", agent="developer", status="active")
        yield s("arrow", index=1, done=True)
        yield s("progress", pct=25, label="Generating code...")

        # AI or fallback
        try:
            if options.apiKey:
                yield s("log", agent="developer", msg="Calling Claude AI to generate all files...")
                project_data = await generate_project_ai(idea, options)
            else:
                yield s("log", agent="developer", msg="No API key — using smart Python template...")
                project_data = build_fallback_project(idea, options)
        except Exception as e:
            yield s("log", agent="developer", msg=f"AI note: {str(e)[:80]} — using smart template")
            project_data = build_fallback_project(idea, options)

        yield s("progress", pct=50, label="Writing files to disk...")
        yield s("log", agent="developer", msg=f"Stack: {project_data.get('stack', 'FastAPI + HTML')}")

        # Write files
        project_dir.mkdir(parents=True, exist_ok=True)
        written_files = []
        for file in project_data["files"]:
            file_path = project_dir / file["path"]
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(file["content"], encoding="utf-8")
            written_files.append(file["path"])
            yield s("log", agent="developer", msg=f'Writing <span class="dim">{file["path"]}</span>')
            await asyncio.sleep(0.07)

        yield s("agent", agent="developer", status="done")
        yield s("agent", agent="tester", status="active")
        yield s("arrow", index=2, done=True)
        yield s("progress", pct=70, label="Validating generated files...")
        await asyncio.sleep(0.3)

        # Validate
        has_app = any("app.py" in f for f in written_files)
        has_req = any("requirements.txt" in f for f in written_files)
        has_index = any("index.html" in f for f in written_files)
        ok = '<span class="hi">✓</span>'
        warn = '<span class="warn">⚠ missing</span>'
        yield s("log", agent="tester", msg=f"app.py: {ok if has_app else warn}")
        yield s("log", agent="tester", msg=f"requirements.txt: {ok if has_req else warn}")
        index_msg = ok if has_index else '<span class="warn">not needed</span>'
        yield s("log", agent="tester", msg=f"index.html: {index_msg}")

        # Always ensure requirements.txt
        if not has_req:
            req_path = project_dir / "requirements.txt"
            req_path.write_text("fastapi==0.110.0\nuvicorn[standard]==0.28.0\n")
            written_files.append("requirements.txt")

        yield s("agent", agent="tester", status="done")
        yield s("agent", agent="reviewer", status="active")
        yield s("arrow", index=3, done=True)
        yield s("progress", pct=82, label="Code review pass...")
        await asyncio.sleep(0.3)

        yield s("log", agent="reviewer", msg=f"<span class=\"hi\">✓</span> {len(written_files)} files validated")
        yield s("agent", agent="reviewer", status="done")
        yield s("agent", agent="executor", status="active")
        yield s("arrow", index=4, done=True)
        yield s("progress", pct=90, label="Creating ZIP archive...")
        await asyncio.sleep(0.2)

        # Create ZIP
        zip_path = PROJECTS_DIR / f"{project_id}.zip"
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for file_path in project_dir.rglob("*"):
                if file_path.is_file():
                    arcname = project_id / file_path.relative_to(project_dir)
                    zf.write(file_path, arcname)

        zip_size_kb = zip_path.stat().st_size / 1024
        yield s("log", agent="executor", msg=f'<span class="hi">✓</span> ZIP created — {zip_size_kb:.1f} KB')
        yield s("progress", pct=100, label="Complete!")
        yield s("agent", agent="executor", status="done")

        total_lines = count_lines(project_data["files"])
        file_contents = {f["path"]: f["content"] for f in project_data["files"]}

        yield s(
            "done",
            projectId=project_id,
            files=written_files,
            stats={
                "files": len(written_files),
                "lines": total_lines,
                "agents": 5,
                "retries": 0,
                "stack": project_data.get("stack", "FastAPI + HTML/CSS/JS"),
            },
            fileContents=file_contents,
        )

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )


@app.get("/download/{project_id}")
async def download_zip(project_id: str):
    """Return the ZIP file for download."""
    zip_path = PROJECTS_DIR / f"{project_id}.zip"
    if not zip_path.exists():
        raise HTTPException(404, "ZIP not found")
    return FileResponse(
        path=zip_path,
        filename=f"{project_id}.zip",
        media_type="application/zip",
    )


@app.get("/projects")
async def list_projects():
    """List all generated projects."""
    projects = []
    for item in PROJECTS_DIR.iterdir():
        if item.is_dir():
            projects.append({
                "id": item.name,
                "created": datetime.fromtimestamp(item.stat().st_ctime).isoformat(),
            })
    return JSONResponse(sorted(projects, key=lambda x: x["created"], reverse=True))


@app.get("/files/{project_id}")
async def list_files(project_id: str):
    """List files inside a project."""
    project_dir = PROJECTS_DIR / project_id
    if not project_dir.exists():
        raise HTTPException(404, "Project not found")

    result = []
    for path in sorted(project_dir.rglob("*")):
        rel = path.relative_to(project_dir)
        result.append({
            "type": "folder" if path.is_dir() else "file",
            "path": str(rel).replace("\\", "/"),
        })
    return JSONResponse(result)


@app.get("/file/{project_id}/{file_path:path}")
async def get_file(project_id: str, file_path: str):
    """Get content of a specific file."""
    full_path = PROJECTS_DIR / project_id / file_path
    if not full_path.exists() or not full_path.is_file():
        raise HTTPException(404, "File not found")
    return FileResponse(full_path, media_type="text/plain")


# Serve dashboard UI
app.mount("/", StaticFiles(directory=".", html=True), name="static")
