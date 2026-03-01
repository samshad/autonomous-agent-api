# Autonomous E-Commerce Agent API

Async FastAPI API that acts as an **autonomous customer support agent**: natural language → ReAct loop + tool use (order lookup, cancel, list) → PostgreSQL via SQLAlchemy → natural language response.

## Features

- **Natural language to action**: e.g. *"Cancel my order #12345"* → validated DB update
- **ReAct orchestration**: Reason → Act (tools) → Observe → repeat
- **Strict schema validation**: Pydantic + JSON Schema for LLM tool binding
- **100% async**: FastAPI, SQLAlchemy async ORM, `asyncpg`, `httpx` for LLM
- **DDD layout**: `api/` → `agent/` → `services/` → `repository/`
- **Neon Serverless Postgres**: SSL and pool settings tuned for Neon (scale-to-zero safe).

## Database: Neon Serverless Postgres

The app is configured for **Neon** serverless Postgres:

1. Create a project at [Neon Console](https://console.neon.tech) and copy the connection string.
2. In the Connect dialog, use the connection string and change the scheme to `postgresql+asyncpg://`.
3. Ensure the URL includes `?sslmode=require` (Neon requires SSL).
4. Optional: use the pooler endpoint for serverless/scale-to-zero.
5. Set `DATABASE_URL` in `.env`. Optionally set `POOL_RECYCLE_SECONDS` (e.g. `300`) to avoid stale connections after suspend.

## Quick start with Docker

```bash
# Build and run API + Postgres
docker compose up -d

# Optional: run Ollama in Docker (or use host Ollama at host.docker.internal)
docker compose -f docker-compose.yml -f docker-compose.ollama.yml up -d

# Seed DB (run once; from host with DB on 5432)
uv run python scripts/seed_db.py
# Or inside API container:
docker compose exec api python -c "
import asyncio
from agent_api.core.database import init_db
from agent_api.models.domain import Base
# ... or run scripts/seed_db.py with DATABASE_URL pointing to db:5432
"
```

Then call the API:

```bash
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "What is the status of order 10001?"}'
```

## Local development

- **Python 3.12+**, **uv**
- Create `.env` from `.env.example`, set `DATABASE_URL` and optionally `OLLAMA_BASE_URL` (e.g. `http://localhost:11434`).
- Ollama must expose an **OpenAI-compatible** `/v1/chat/completions` endpoint (e.g. via a proxy or Ollama’s compatibility layer).

```bash
uv sync
uv run python scripts/seed_db.py
uv run uvicorn agent_api.main:app --reload --port 8000
```

## Project layout

```
src/agent_api/
├── main.py           # FastAPI app
├── api/              # Presentation: routes, dependencies
├── core/              # Config, DB, logging, exceptions
├── models/            # Domain ORM, HTTP schemas, agent payloads
├── repository/        # Data access (order_repo)
├── services/          # Business logic (commerce)
└── agent/             # ReAct engine, LLM client, tool registry, tools
```

## Tests

```bash
uv run pytest
# With coverage
uv run pytest --cov=agent_api --cov-report=term-missing
```

## Environment

| Variable                 | Description                                              | Default / example |
|--------------------------|----------------------------------------------------------|-------------------|
| `DATABASE_URL`           | Neon (or any) Postgres URL; use `postgresql+asyncpg://...?sslmode=require` for Neon | `postgresql+asyncpg://...` |
| `POOL_RECYCLE_SECONDS`   | Recycle DB connections after this many seconds (Neon scale-to-zero) | `300` |
| `OLLAMA_BASE_URL`        | LLM API base (OpenAI-compatible)                        | `http://localhost:11434` |
| `OLLAMA_MODEL`           | Model name                                              | `llama3.1` |
| `LOG_LEVEL`              | Logging level                                           | `INFO` |

## License

MIT
