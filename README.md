# FintelliPro POC — AI-Powered Fintech B2B Intelligence Platform

> Version 1.0.0 · FastAPI + React + PostgreSQL + Claude AI

---

## What This Is

FintelliPro is a production-grade POC for a B2B sales intelligence platform that helps fintech companies identify, analyze, and engage potential clients across 9 regulated industries. It combines Apollo.ai contact enrichment, regulatory data (NCUA/FDIC/NAIC), web signal detection, and Claude AI to generate hyper-personalized outreach.

---

## Quick Start (3 commands)

```bash
# 1. Copy environment config
cp .env.example .env

# 2. Run the automated setup (installs everything)
bash setup.sh

# 3. Start the app (two terminals)
# Terminal 1:
cd backend && source venv/bin/activate && uvicorn app.main:app --reload
# Terminal 2:
cd frontend && npm run dev
```

Open: http://localhost:3000
Login: demo@fintellipro.com / demo1234

---

## Project Structure

```
fintellipro-poc/
├── backend/
│   ├── app/
│   │   ├── main.py               # FastAPI app entry point
│   │   ├── api/__init__.py       # All route handlers
│   │   ├── core/
│   │   │   ├── config.py         # Pydantic settings
│   │   │   └── security.py       # JWT auth utilities
│   │   ├── db/
│   │   │   └── database.py       # SQLAlchemy engine + session
│   │   ├── models/__init__.py    # All DB models (6 tables)
│   │   ├── schemas/__init__.py   # Pydantic request/response schemas
│   │   └── services/
│   │       ├── ai_service.py     # Claude AI signal detection + outreach
│   │       ├── apollo_client.py  # Apollo.ai API wrapper
│   │       └── ingestion.py      # Full data pipeline orchestrator
│   ├── seed.py                   # DB seed with demo data
│   ├── tests/test_api.py         # pytest test suite
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── App.tsx               # All pages + components
│   │   ├── lib/api.ts            # Axios client with JWT interceptor
│   │   ├── store/authStore.ts    # Zustand auth state
│   │   └── main.tsx              # React entry point
│   ├── package.json
│   ├── vite.config.ts
│   └── Dockerfile
├── docker-compose.yml            # Full stack (postgres + redis + backend + frontend)
├── setup.sh                      # One-command automated setup
└── .env.example                  # Environment variable template
```

---

## Prerequisites

| Tool        | Version  | Install From         |
|-------------|----------|----------------------|
| Python      | 3.11+    | python.org           |
| Node.js     | 18+      | nodejs.org           |
| Docker Desktop | Latest | docker.com           |

---

## Manual Setup (Step by Step)

### Step 1 — Start the database
```bash
docker compose up -d db redis
# Wait ~10 seconds for postgres to be ready
```

### Step 2 — Backend
```bash
cd backend
python3 -m venv venv
source venv/bin/activate      # Mac/Linux
# venv\Scripts\activate       # Windows

pip install -r requirements.txt

# Set env vars (or add to .env)
export DATABASE_URL="postgresql://fintellipro:fintellipro_dev@localhost:5432/fintellipro"
export SECRET_KEY="any-32-char-secret-key"
export ANTHROPIC_API_KEY="sk-ant-..."   # optional — uses mock if absent
export APOLLO_API_KEY="..."              # optional — uses mock if absent

# Seed the database
python seed.py

# Start the API server
uvicorn app.main:app --reload
# → Running at http://localhost:8000
# → API docs at http://localhost:8000/docs
```

### Step 3 — Frontend
```bash
cd frontend
npm install
npm run dev
# → Running at http://localhost:3000
```

---

## API Keys

The POC works WITHOUT API keys using built-in mock data and templates.

To enable live AI:
- **Claude (Anthropic):** https://console.anthropic.com → API Keys → add to `.env` as `ANTHROPIC_API_KEY`
- **Apollo.ai:** https://app.apollo.io → Settings → API Keys → add as `APOLLO_API_KEY`

---

## API Endpoints

| Method | Endpoint                        | Description                    |
|--------|---------------------------------|--------------------------------|
| POST   | /api/auth/register              | Create account                 |
| POST   | /api/auth/login                 | Get JWT token                  |
| GET    | /api/auth/me                    | Current user profile           |
| PUT    | /api/auth/profile               | Update fintech profile         |
| GET    | /api/companies/                 | List leads (filterable)        |
| GET    | /api/companies/:id              | Lead detail with signals       |
| PATCH  | /api/companies/:id/status       | Update outreach status         |
| POST   | /api/ai/generate-message        | Generate AI outreach message   |
| GET    | /api/ai/messages/:company_id    | List generated messages        |
| POST   | /api/pipeline/run               | Trigger discovery pipeline     |
| GET    | /api/pipeline/status            | Pipeline stats                 |
| GET    | /api/dashboard/stats            | Dashboard KPIs                 |
| GET    | /api/campaigns/                 | List campaigns                 |
| POST   | /api/campaigns/                 | Create campaign                |

Full interactive docs: http://localhost:8000/docs

---

## Running Tests

```bash
cd backend
source venv/bin/activate
pytest tests/ -v

# With coverage report:
pytest tests/ -v --cov=app --cov-report=term-missing
```

---

## Docker (Full Stack)

Run everything in Docker (no local Python/Node needed):
```bash
# Copy and edit your .env first
cp .env.example .env

# Start everything
docker compose up

# First time: seed the database
docker compose exec backend python seed.py
```

---

## Demo Login

| Field    | Value                       |
|----------|-----------------------------|
| Email    | demo@fintellipro.com        |
| Password | demo1234                    |

---

## Tech Stack

| Layer      | Technology                          |
|------------|-------------------------------------|
| Backend    | Python 3.11, FastAPI, SQLAlchemy    |
| Database   | PostgreSQL 16 + pgvector            |
| Cache/Queue| Redis 7                             |
| AI         | Claude Sonnet (Anthropic API)       |
| Enrichment | Apollo.ai API                       |
| Frontend   | React 18, TypeScript, Vite          |
| Styling    | Tailwind CSS                        |
| State      | Zustand + TanStack Query            |
| Auth       | JWT (python-jose + bcrypt)          |
| Container  | Docker + Docker Compose             |

---

## Environment Variables

| Variable              | Required | Description                          |
|-----------------------|----------|--------------------------------------|
| DATABASE_URL          | Yes      | PostgreSQL connection string         |
| REDIS_URL             | Yes      | Redis connection string              |
| SECRET_KEY            | Yes      | JWT signing key (min 32 chars)       |
| ANTHROPIC_API_KEY     | No       | Claude AI (mock used if absent)      |
| APOLLO_API_KEY        | No       | Apollo enrichment (mock if absent)   |
| FRONTEND_URL          | No       | CORS origin (default: localhost:3000)|

---

## Next Steps After POC

1. Add real Apollo API key → pull live credit union contacts
2. Add Anthropic API key → enable live Claude message generation
3. Configure Gmail OAuth → enable actual email sending
4. Deploy to Railway.app (backend) + Vercel (frontend) in ~30 minutes
5. Onboard 3 pilot customers and gather conversion data

---

Built with FastAPI · React · Claude AI · Apollo.ai
