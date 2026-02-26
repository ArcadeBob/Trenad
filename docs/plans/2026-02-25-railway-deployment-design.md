# Railway Deployment Design

**Goal:** Deploy the stock pattern scanner to Railway so it's accessible via a shareable public URL for demos.

**Decision:** Railway over Vercel (serverless incompatible with long-running scans, SSE, SQLite) and Fly.io (unnecessary DevOps overhead for a demo app).

---

## Architecture

```
GitHub repo (master branch)
    │
    └── push triggers Railway auto-deploy

Railway Service
    ├── Python 3.13 runtime (auto-detected)
    ├── pip install -r requirements.txt
    ├── Procfile: uvicorn app:app --host 0.0.0.0 --port $PORT
    │
    ├── Web server (FastAPI + Uvicorn)
    │   ├── GET /              → Dashboard HTML
    │   ├── POST /api/scan     → Starts background thread
    │   ├── GET /api/scan/{id}/progress → SSE stream
    │   ├── GET /api/scan/{id}/results  → JSON results
    │   └── GET /api/export/excel/{id}  → File download
    │
    ├── SQLite DB → /app/data/scanner.db (persistent volume)
    └── Temp files → /tmp/scan_*.xlsx (ephemeral)
```

## Scope

**In scope:**
- Procfile, runtime.txt, railway.toml (3 new config files)
- Zero application code changes
- Persistent volume for SQLite
- Auto-deploy on push to master

**Out of scope (YAGNI):**
- Docker/Dockerfile — Railway auto-detects Python
- CI/CD pipeline — Railway handles this
- Custom domain — can add later
- Auth/rate limiting — demo use only
- External logging — Railway has built-in logs

## Environment Variables

| Variable | Value | Purpose |
|----------|-------|---------|
| `SCANNER_DB_PATH` | `/app/data/scanner.db` | Persistent SQLite location |
| `PORT` | (set by Railway) | Dynamic port binding |

## Manual Setup Steps (post-deploy)

1. Push code to GitHub
2. Create Railway account, link repo
3. Add persistent volume at `/app/data`
4. Set `SCANNER_DB_PATH` env var
5. Railway auto-deploys, provides public URL
