# FintelliPro POC — Claude Context

## What this project is
A credit union sales intelligence platform (LeadForge / FintelliPro).
Tracks 100 real US credit unions, enriches them with NCUA financial data,
payment rail participation, news signals, and contact data to surface
prioritised sales opportunities.

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | React + Vite + TypeScript, Tailwind CSS, React Query, Axios |
| Backend | FastAPI (Python 3.11), SQLAlchemy 2.x, Alembic, Celery |
| Database | PostgreSQL (Render managed) |
| Cache/Queue | Redis (Render managed) |
| Auth | JWT + Google OAuth2 |
| AI | Anthropic Claude API (outreach message generation) |
| Frontend host | Netlify |
| Backend host | Render (Docker runtime — Python runtime kept failing) |

---

## Live Service URLs

| Service | URL |
|---------|-----|
| Frontend | https://whimsical-moxie-9c3132.netlify.app |
| Backend API | https://leadforge-backend-2f6w.onrender.com |
| GitHub | https://github.com/mahendra0622/leadforge-poc |

## Render Infrastructure IDs
- **Web service**: `srv-dagbe1bl550s73bd2sfg`
- **PostgreSQL DB**: `dpg-dag9v0jl550s73aeqba0-a` (DB name: `leadforge_db_utkx`)
- **Redis**: `red-daga31e7bikc73ft2ca0`
- **Render API key**: `rnd_CHfhNRj3rkijhKsNznpnPPKT4Wv2`
- **Netlify site ID**: `64990c57-0c5b-4cbd-947c-ccc4f45b40c8` (token saved in CLI)

## Database Connection
```
# External (from local machine):
postgresql://leadforge_db_utkx_user:Ydw9AloKOqyYBhbLWTxSf4uY3Q0eESzB@dpg-dag9v0jl550s73aeqba0-a.oregon-postgres.render.com/leadforge_db_utkx

# Internal (used by Render service via env var DATABASE_URL):
postgresql://leadforge_db_utkx_user:Ydw9AloKOqyYBhbLWTxSf4uY3Q0eESzB@dpg-dag9v0jl550s73aeqba0-a/leadforge_db_utkx
```

---

## Demo Credentials
- Email: `demo@fintellipro.com` / Password: `demo1234`
- Google OAuth: client ID `1012112446824-js3r394nt3ptigrmm5m0ba569d7jch22.apps.googleusercontent.com`
- Google redirect URI: `https://leadforge-backend-2f6w.onrender.com/api/auth/gmail/callback`

---

## Key Files

| File | Purpose |
|------|---------|
| `backend/app/main.py` | FastAPI app entry point, startup hooks |
| `backend/app/api/__init__.py` | All API routes |
| `backend/app/models/__init__.py` | SQLAlchemy models (Company, Signal, Contact, User…) |
| `backend/app/schemas/__init__.py` | Pydantic response schemas |
| `backend/app/services/regulatory/ncua_real_data.py` | Static data: 100 real CUs with NCUA financials |
| `frontend/src/App.v2.tsx` | Entire frontend (single-file React app) |
| `frontend/src/main.tsx` | React entry, QueryClient config (staleTime: 0) |
| `netlify.toml` | Netlify build + API proxy config |
| `backend/Dockerfile` | Docker image used by Render |
| `backend/requirements.txt` | Python dependencies |

---

## Seed / Utility Scripts (run as Render one-off jobs)

```bash
# Trigger a Render job:
# POST https://api.render.com/v1/services/srv-dagbe1bl550s73bd2sfg/jobs
# Body: {"startCommand": "python <script>.py"}

python ncua_live_seed.py          # Seed 100 CUs with NCUA data
python seed_contacts_outreach.py  # Seed Apollo contacts + outreach history
python seed_news_signals.py       # Seed news signals (from real_news_data.json)
python seed_real_news.py          # Re-seed news from real_news_data.json
python compute_financial_metrics.py  # Compute ROA/ROE/scores, write to regulatory_data
python seed_payments.py           # Fetch live RTP + FedNow lists, cross-ref 100 CUs
python check_metrics.py           # Diagnostic: print regulatory_data for 5 CUs
```

## Deploy Commands (local)
```bash
# Deploy frontend to Netlify:
cd frontend && npm run build
npx netlify-cli deploy --prod --dir=frontend/dist

# Trigger Render redeploy: just git push — auto-deploy is on
git add . && git commit -m "..." && git push
```

---

## Data Model — Company.regulatory_data (JSON column)
Stores all enriched fields as a flat JSON object:

```json
{
  "charter_number": "...",
  "total_assets": 4812000000,
  "total_members": 348000,
  "net_worth": 541200000,
  "net_worth_ratio": 11.24,
  "total_loans": 3902000000,
  "total_shares": 4815000000,
  "loan_to_share_ratio": 81.01,
  "core_processor": "Jack Henry CU*BASE",
  "asset_tier": "large",

  "net_income": 36000000,
  "roa": 0.75,
  "roe": 6.65,
  "assets_per_member": 13828,
  "financial_health_score": 85,
  "growth_momentum_score": 72,
  "modernization_urgency": 60,

  "is_rtp_participant": true,
  "is_fednow_participant": false
}
```

## Signal Sources
| source | Description |
|--------|-------------|
| `ncua_financials` | ROA/ROE pressure, capital position, health scores |
| `payment_rails` | RTP/FedNow participation status |
| `news` | Google News RSS articles per CU |
| `manual` | Seeded from seed.py |

---

## What Has Been Built (Phases)

### ✅ Phase 1 — NCUA Financial Ratios
- Script: `compute_financial_metrics.py`
- Adds: ROA, ROE, NWR, loan-to-share, assets/member, 3 composite scores
- Frontend: Overview tab → Financials + Performance Ratios + Intelligence Scores sections

### ✅ Phase 3 — Payment Rails (RTP + FedNow)
- Script: `seed_payments.py`
- RTP: live scrape from theclearinghouse.org (1305 institutions, 477 CUs)
- FedNow: downloads XLSX from frbservices.org Bloomreach CMS asset URL
  `https://www.frbservices.org/binaries/content/assets/crsocms/financial-services/fednow/fednow-live-participants.xlsx`
  (URL discovered via resourceapi: `https://www.frbservices.org/resourceapi/financial-services/fednow/organizations`)
- Result: 36 RTP, 35 FedNow, 27 both, 56 neither (out of 100 CUs)
- Frontend: Overview tab → Payment Rails section with colour-coded badges

### ⏳ Phase 2 — App Store Ratings
- iTunes Search API (free) + google-play-scraper for iOS/Android ratings
- Store in regulatory_data as `ios_rating`, `android_rating`, `app_store_reviews`

### ⏳ Phase 4 — NCUA Public Data
- Merger filings, CUSO registry, officer/executive directory
- Source: ncua.gov public datasets

### ⏳ Phase 5 — Contact Role Classification (Claude AI)
- Batch classify existing Apollo contacts by decision-making power
- Use Anthropic API, update `is_decision_maker` flag

### ⏳ Phase 6 — Tech Stack from Job Postings
- Infer vendor tech stack from job posting keywords

### ⏳ Phase 7 — Vendor Churn from News
- Detect RFP/vendor-switch language in news signals

---

## Critical Notes

1. **SQLAlchemy JSON mutations**: Always use `flag_modified(co, "regulatory_data")` after
   patching the JSON column, AND assign a new dict (`co.regulatory_data = {**rd, ...}`).
   Without both, changes are silently dropped.

2. **Render Docker vs Python runtime**: Python runtime on Render kept failing (exit code 1,
   no useful error). All deployments use the Docker runtime (`backend/Dockerfile`).

3. **Netlify proxy**: `netlify.toml` must have the `/api/*` redirect before the `/*` catch-all.
   Never commit `.netlify/` directory (has absolute local paths).

4. **React Query staleTime**: Set to `0` in `main.tsx` — always fetches fresh data on mount.

5. **FedNow XLSX URL**: The direct download URL was found via the Bloomreach CMS resourceapi.
   The main page at `/financial-services/fednow/organizations` is JS-rendered but the API at
   `/resourceapi/financial-services/fednow/organizations` returns JSON with the embedded XLSX link.
