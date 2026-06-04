# DocuMind Backend

FastAPI + SQLite (WAL + FTS5). No vector DB — Agent-driven navigation only.

## Setup

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .
Copy-Item .env.example .env
# edit .env — set MIMO_API_KEY at minimum
```

## Run

```powershell
uvicorn app.main:app --reload --port 8000
```

OpenAPI docs at http://127.0.0.1:8000/docs

## Endpoints (v1)

| Method | Path                              | Purpose                           |
|--------|-----------------------------------|-----------------------------------|
| GET    | /api/health                       | server + LLM provider status      |
| GET    | /api/folders                      | list folders (with doc counts)    |
| POST   | /api/folders                      | create folder                     |
| PATCH  | /api/folders/{fid}                | rename / recolor                  |
| DELETE | /api/folders/{fid}                | soft-delete folder + cascade docs |
| GET    | /api/folders/{fid}/docs           | list docs in folder               |
| POST   | /api/folders/{fid}/upload         | upload file (sha256 dedup)        |
| DELETE | /api/docs/{did}                   | soft-delete doc                   |
| POST   | /api/docs/{did}/reindex           | re-run ingest pipeline            |
| POST   | /api/chat                         | Agent SSE stream                  |
| GET    | /api/settings                     | view settings                     |
| POST   | /api/settings/provider            | switch mimo / lmstudio            |
| POST   | /api/settings/llm_check           | capability self-test              |
