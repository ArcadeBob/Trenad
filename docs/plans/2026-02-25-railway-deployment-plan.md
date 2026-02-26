# Railway Deployment Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Deploy the stock pattern scanner to Railway with a shareable public URL, zero application code changes.

**Architecture:** Add three config files to the repo root (railway.toml, runtime.txt, requirements.txt) plus a .gitignore. Railway auto-detects Python, installs deps, and runs the start command. A persistent volume stores the SQLite database.

**Tech Stack:** Railway (PaaS), Python 3.13, FastAPI, Uvicorn, Nixpacks (Railway's buildpack)

---

## Task 1: Add .gitignore

The repo has no .gitignore — `__pycache__/`, `scanner.db`, and other artifacts are untracked but visible. Clean this up before deploying.

**Files:**
- Create: `.gitignore`

**Step 1: Create .gitignore**

```gitignore
__pycache__/
*.pyc
*.pyo
*.db
*.xlsx
.pytest_cache/
*.egg-info/
dist/
build/
.env
```

**Step 2: Verify ignored files are excluded**

Run: `git status`
Expected: `__pycache__/`, `scanner.db`, and `.pytest_cache/` no longer appear as untracked.

**Step 3: Commit**

```bash
git add .gitignore
git commit -m "chore: add .gitignore"
```

---

## Task 2: Add Root-Level requirements.txt

Railway's Nixpacks builder looks for `requirements.txt` at the repo root to detect a Python project. Copy the existing one from `stock_pattern_scanner/`.

**Files:**
- Create: `requirements.txt`

**Step 1: Create root requirements.txt**

Same content as `stock_pattern_scanner/requirements.txt`, minus test-only deps:

```txt
fastapi>=0.104.0
uvicorn[standard]>=0.24.0
yfinance>=0.2.31
pandas>=2.1.0
numpy>=1.25.0
openpyxl>=3.1.2
jinja2>=3.1.2
aiofiles>=23.2.1
sse-starlette>=1.8.0
scipy>=1.11.0
```

Note: `pytest` and `httpx` are excluded — they're dev/test deps, not needed in production.

**Step 2: Verify deps install cleanly**

Run: `pip install -r requirements.txt --dry-run 2>&1 | tail -5`
Expected: All packages already satisfied (since they're installed locally).

**Step 3: Commit**

```bash
git add requirements.txt
git commit -m "build: add root requirements.txt for Railway deploy"
```

---

## Task 3: Add runtime.txt

Pins the Python version so Railway uses the same version as local dev.

**Files:**
- Create: `runtime.txt`

**Step 1: Create runtime.txt**

```txt
python-3.13.6
```

**Step 2: Commit**

```bash
git add runtime.txt
git commit -m "build: add runtime.txt to pin Python 3.13.6"
```

---

## Task 4: Add railway.toml

Configures the build and deploy commands. The start command `cd`s into `stock_pattern_scanner/` so all relative imports and template paths work.

**Files:**
- Create: `railway.toml`

**Step 1: Create railway.toml**

```toml
[build]
builder = "nixpacks"

[deploy]
startCommand = "cd stock_pattern_scanner && uvicorn app:app --host 0.0.0.0 --port ${PORT:-8000}"
healthcheckPath = "/"
healthcheckTimeout = 30
restartPolicyType = "on_failure"
restartPolicyMaxRetries = 3
```

Notes:
- `${PORT:-8000}` uses Railway's assigned port, falls back to 8000 for local testing.
- `healthcheckPath = "/"` lets Railway verify the app is responding.
- Restart policy auto-recovers from crashes.

**Step 2: Commit**

```bash
git add railway.toml
git commit -m "build: add railway.toml with deploy configuration"
```

---

## Task 5: Verify Locally

Confirm the exact start command Railway will use works on the local machine.

**Step 1: Test the Railway start command**

Run from repo root:
```bash
cd stock_pattern_scanner && PORT=8000 uvicorn app:app --host 0.0.0.0 --port 8000 &
sleep 3
curl -s http://localhost:8000/ | head -5
kill %1
```

Expected: HTML output containing "Stock Pattern Scanner".

**Step 2: Run full test suite to confirm nothing broke**

Run: `cd stock_pattern_scanner && python -m pytest tests/ -v`
Expected: All 40 tests PASS.

---

## Task 6: Push to GitHub

**Step 1: Verify all config files are committed**

Run: `git log --oneline -5`
Expected: Commits for .gitignore, requirements.txt, runtime.txt, railway.toml visible.

**Step 2: Check remote exists**

Run: `git remote -v`
If no remote, add one:
```bash
git remote add origin https://github.com/<username>/Trenad.git
```

**Step 3: Push**

```bash
git push -u origin master
```

---

## Task 7: Railway Setup (Manual — User Steps)

These steps are done in the Railway web dashboard, not by Claude.

1. **Sign up** at [railway.com](https://railway.com) (GitHub OAuth)
2. **New Project** → "Deploy from GitHub repo" → select `Trenad`
3. **Add Volume:**
   - Go to service Settings → Volumes
   - Mount path: `/app/data`
   - This persists the SQLite database across deploys
4. **Add Environment Variable:**
   - `SCANNER_DB_PATH` = `/app/data/scanner.db`
5. **Deploy** — Railway auto-builds and deploys
6. **Get URL** — Settings → Networking → Generate Domain
   - You'll get something like `trenad-production.up.railway.app`
7. **Test** — Open the URL, run a scan, verify SSE progress and results work

---

## Verification Checklist

After Railway deploys:

- [ ] Dashboard loads at the public URL
- [ ] Can start a scan with default watchlist
- [ ] SSE progress bar updates in real-time
- [ ] Results table populates after scan completes
- [ ] Excel export downloads successfully
- [ ] Scan data persists after a redeploy (volume test)
