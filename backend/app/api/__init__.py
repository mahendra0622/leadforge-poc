"""
FintelliPro — API Routes (all in one file for POC)
Split into separate files for production
"""
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional
from datetime import datetime

from app.db.database import get_db
from app.core.security import get_current_user, create_access_token, hash_password, verify_password
from app.models import Company, Contact, Signal, AIMessage, Campaign, OutreachEvent, User
from app.schemas import (
    UserRegister, UserLogin, TokenResponse, UserProfile,
    CompanyCreate, CompanyResponse,
    ContactResponse, SignalResponse,
    GenerateMessageRequest, GenerateMessageResponse,
    CampaignCreate, CampaignResponse,
    DashboardStats,
)
from app.services.ai_service import generate_outreach_message
from app.services.ingestion import run_full_enrichment
from app.services.source_refs import format_hover_text
from loguru import logger


# ──────────────────────────────────────────
# AUTH
# ──────────────────────────────────────────
auth_router = APIRouter()


@auth_router.post("/register", response_model=TokenResponse)
def register(data: UserRegister, db: Session = Depends(get_db)):
    if db.query(User).filter_by(email=data.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")
    user = User(
        email=data.email,
        hashed_password=hash_password(data.password),
        full_name=data.full_name,
        company_name=data.company_name,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    token = create_access_token({"sub": user.id})
    return {"access_token": token, "token_type": "bearer", "user": {"id": user.id, "email": user.email, "name": user.full_name}}


@auth_router.post("/login", response_model=TokenResponse)
def login(data: UserLogin, db: Session = Depends(get_db)):
    user = db.query(User).filter_by(email=data.email).first()
    if not user or not user.hashed_password or not verify_password(data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_access_token({"sub": user.id})
    return {"access_token": token, "token_type": "bearer", "user": {"id": user.id, "email": user.email, "name": user.full_name}}


@auth_router.get("/me")
def get_me(current_user: User = Depends(get_current_user)):
    return {
        "id": current_user.id,
        "email": current_user.email,
        "name": current_user.full_name,
        "company_name": current_user.company_name,
        "product_description": current_user.product_description,
        "key_strengths": current_user.key_strengths,
        "differentiators": current_user.differentiators,
        "tone": current_user.tone,
        "gmail_email": current_user.gmail_email,
        "auth_provider": current_user.auth_provider or "password",
        "tagline": current_user.tagline,
        "products": current_user.products,
        "case_studies": current_user.case_studies,
        "integrations": current_user.integrations,
    }


@auth_router.put("/profile")
def update_profile(data: UserProfile, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    current_user.company_name = data.company_name
    current_user.product_description = data.product_description
    current_user.key_strengths = data.key_strengths
    current_user.differentiators = data.differentiators
    current_user.tone = data.tone
    current_user.tagline = data.tagline
    if data.products is not None:
        current_user.products = data.products
    if data.case_studies is not None:
        current_user.case_studies = data.case_studies
    if data.integrations is not None:
        current_user.integrations = data.integrations
    db.commit()
    return {"status": "updated"}


# ──────────────────────────────────────────
# COMPANIES
# ──────────────────────────────────────────
companies_router = APIRouter()


@companies_router.get("/")
def list_companies(
    industry: Optional[str] = None,
    min_score: int = 0,
    status: Optional[str] = None,
    search: Optional[str] = None,
    page: int = 1,
    per_page: int = 25,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    q = db.query(Company)
    if industry:
        q = q.filter(Company.industry == industry)
    if min_score > 0:
        q = q.filter(Company.opportunity_score >= min_score)
    if status:
        q = q.filter(Company.outreach_status == status)
    if search:
        q = q.filter(Company.name.ilike(f"%{search}%"))

    total = q.count()
    companies = q.order_by(Company.opportunity_score.desc()).offset((page - 1) * per_page).limit(per_page).all()

    result = []
    for co in companies:
        signal_count = db.query(Signal).filter_by(company_id=co.id, is_active=True).count()
        top_contact = db.query(Contact).filter_by(company_id=co.id, is_decision_maker=True).first()
        result.append({
            "id": co.id,
            "name": co.name,
            "industry": co.industry,
            "hq_city": co.hq_city,
            "hq_state": co.hq_state,
            "revenue_est": co.revenue_est,
            "employee_count": co.employee_count,
            "opportunity_score": co.opportunity_score,
            "digital_maturity": co.digital_maturity,
            "outreach_status": co.outreach_status,
            "regulatory_src": co.regulatory_src,
            "tech_stack": co.tech_stack,
            "signal_count": signal_count,
            "top_contact": {
                "id": top_contact.id,
                "name": f"{top_contact.first_name} {top_contact.last_name}".strip(),
                "title": top_contact.title,
                "email": top_contact.email,
                "email_status": top_contact.email_status,
            } if top_contact else None,
        })

    return {"data": result, "total": total, "page": page, "per_page": per_page}


@companies_router.get("/{company_id}")
def get_company(company_id: str, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    co = db.query(Company).filter_by(id=company_id).first()
    if not co:
        raise HTTPException(status_code=404, detail="Company not found")

    signals = db.query(Signal).filter_by(company_id=co.id, is_active=True).all()
    contacts = db.query(Contact).filter_by(company_id=co.id).all()

    return {
        "id": co.id, "name": co.name, "website": co.website,
        "industry": co.industry, "hq_city": co.hq_city, "hq_state": co.hq_state,
        "revenue_est": co.revenue_est, "employee_count": co.employee_count,
        "tech_stack": co.tech_stack, "opportunity_score": co.opportunity_score,
        "digital_maturity": co.digital_maturity, "outreach_status": co.outreach_status,
        "regulatory_src": co.regulatory_src, "regulatory_data": co.regulatory_data,
        "signals": [{"id": s.id, "type": s.signal_type, "label": s.signal_label, "severity": s.severity, "source": s.source, "source_url": s.source_url, "source_file": s.source_file, "source_page": s.source_page, "source_hover": format_hover_text(s)} for s in signals],
        "contacts": [{"id": c.id, "name": f"{c.first_name} {c.last_name}".strip(), "title": c.title, "email": c.email, "email_status": c.email_status, "is_decision_maker": c.is_decision_maker, "linkedin_url": c.linkedin_url} for c in contacts],
    }


@companies_router.patch("/{company_id}/status")
def update_status(company_id: str, body: dict, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    co = db.query(Company).filter_by(id=company_id).first()
    if not co:
        raise HTTPException(status_code=404, detail="Company not found")
    co.outreach_status = body.get("status", co.outreach_status)
    db.commit()
    return {"status": "updated", "new_status": co.outreach_status}


# ──────────────────────────────────────────
# AI ENGINE
# ──────────────────────────────────────────
ai_router = APIRouter()


@ai_router.post("/generate-message")
def generate_message(
    req: GenerateMessageRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    company = db.query(Company).filter_by(id=req.company_id).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    contact = db.query(Contact).filter_by(id=req.contact_id).first()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")

    signals = db.query(Signal).filter_by(company_id=company.id, is_active=True).all()
    signals_dict = {
        "digital_maturity": company.digital_maturity or 3,
        "opportunity_score": company.opportunity_score or 50,
        "operational_gaps": [{"label": s.signal_label, "severity": s.severity} for s in signals if s.signal_type == "operational_gap"],
        "pain_points": [{"label": s.signal_label, "urgency": s.severity} for s in signals if s.signal_type == "pain_point"],
        "growth_signals": [{"label": s.signal_label, "strength": s.severity} for s in signals if s.signal_type == "growth"],
    }

    provider_profile = {
        "company_name": current_user.company_name or "FintelliPay",
        "product_description": current_user.product_description or "API-first real-time payment platform",
        "key_strengths": current_user.key_strengths or "Real-time payments, API integration, fraud prevention",
        "differentiators": current_user.differentiators or "No core replacement needed, 48-hour integration",
        "tone": req.tone or current_user.tone or "consultative",
    }

    company_data = {
        "name": company.name, "industry": company.industry,
        "hq_city": company.hq_city, "hq_state": company.hq_state,
        "revenue_est": company.revenue_est, "employee_count": company.employee_count,
        "tech_stack": company.tech_stack or [],
    }

    contact_data = {
        "first_name": contact.first_name, "last_name": contact.last_name,
        "title": contact.title, "email": contact.email,
        "linkedin_url": contact.linkedin_url,
    }

    result = generate_outreach_message(
        message_type=req.message_type,
        company_data=company_data,
        contact_data=contact_data,
        provider_profile=provider_profile,
        signals=signals_dict,
    )

    # Save to DB
    msg = AIMessage(
        company_id=company.id, contact_id=contact.id,
        owner_id=current_user.id, message_type=req.message_type,
        subject_line=result.get("subject_line"), body=result.get("body", ""),
        tone=provider_profile["tone"], model_used=result.get("model", "claude-sonnet-4-20250514"),
        tokens_used=result.get("tokens_used", 0), approved=False, sent=False,
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)

    return {
        "id": msg.id, "message_type": msg.message_type,
        "subject_line": msg.subject_line, "body": msg.body,
        "tone": msg.tone, "tokens_used": msg.tokens_used,
        "created_at": msg.created_at,
    }


@ai_router.get("/messages/{company_id}")
def list_messages(company_id: str, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    msgs = db.query(AIMessage).filter_by(company_id=company_id).order_by(AIMessage.created_at.desc()).all()
    return [{"id": m.id, "type": m.message_type, "subject": m.subject_line, "body": m.body[:200] + "..." if len(m.body) > 200 else m.body, "approved": m.approved, "sent": m.sent, "created_at": m.created_at} for m in msgs]


# ──────────────────────────────────────────
# PIPELINE
# ──────────────────────────────────────────
pipeline_router = APIRouter()


@pipeline_router.post("/run")
def run_pipeline(
    body: dict,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    industry = body.get("industry", "credit_unions")
    logger.info(f"Manual pipeline trigger for industry: {industry}")
    background_tasks.add_task(run_full_enrichment, industry, db)
    return {"status": "started", "industry": industry, "message": "Pipeline running in background. Check /api/companies in ~30 seconds."}


@pipeline_router.get("/status")
def pipeline_status(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    total = db.query(Company).count()
    enriched = db.query(Company).filter(Company.apollo_org_id.isnot(None)).count()
    with_regulatory = db.query(Company).filter(Company.regulatory_src.isnot(None)).count()
    scored = db.query(Company).filter(Company.opportunity_score > 0).count()
    total_signals = db.query(Signal).count()
    return {
        "companies_total": total,
        "apollo_enriched": enriched,
        "regulatory_enriched": with_regulatory,
        "opportunity_scored": scored,
        "total_signals": total_signals,
    }


# ──────────────────────────────────────────
# CAMPAIGNS
# ──────────────────────────────────────────
campaigns_router = APIRouter()


@campaigns_router.get("/")
def list_campaigns(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    camps = db.query(Campaign).filter_by(owner_id=current_user.id).order_by(Campaign.created_at.desc()).all()
    return [{"id": c.id, "name": c.name, "industry": c.industry, "status": c.status, "channel": c.channel, "total_sent": c.total_sent, "total_opens": c.total_opens, "total_replies": c.total_replies, "open_rate": round(c.total_opens / c.total_sent * 100, 1) if c.total_sent > 0 else 0, "reply_rate": round(c.total_replies / c.total_sent * 100, 1) if c.total_sent > 0 else 0, "created_at": c.created_at} for c in camps]


@campaigns_router.post("/")
def create_campaign(data: CampaignCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    camp = Campaign(owner_id=current_user.id, **data.dict())
    db.add(camp)
    db.commit()
    db.refresh(camp)
    return {"id": camp.id, "name": camp.name, "status": camp.status}


# ──────────────────────────────────────────
# DASHBOARD
# ──────────────────────────────────────────
dashboard_router = APIRouter()


@dashboard_router.get("/stats")
def get_dashboard_stats(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return {
        "total_leads": db.query(Company).count(),
        "apollo_enriched": db.query(Company).filter(Company.apollo_org_id.isnot(None)).count(),
        "high_score_leads": db.query(Company).filter(Company.opportunity_score >= 80).count(),
        "active_campaigns": db.query(Campaign).filter(Campaign.status == "active", Campaign.owner_id == current_user.id).count(),
        "emails_sent_today": 0,
        "open_rate_avg": 34.2,
        "reply_rate_avg": 8.7,
    }


# ──────────────────────────────────────────
# Apollo route
# ──────────────────────────────────────────
apollo_router_obj = APIRouter()


@apollo_router_obj.post("/enrich/{company_id}")
def trigger_enrich(company_id: str, background_tasks: BackgroundTasks, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    company = db.query(Company).filter_by(id=company_id).first()
    if not company:
        raise HTTPException(status_code=404, detail="Not found")
    from app.services.ingestion import run_ai_signal_detection
    background_tasks.add_task(run_ai_signal_detection, company, db)
    return {"status": "enrichment_queued", "company": company.name}


# ──────────────────────────────────────────
# NCUA / CUNA REGULATORY ROUTES
# ──────────────────────────────────────────
from app.services.regulatory.cuna_ncua import (
    NCUAClient, CUNAIntelligenceClient, CUNANCUAEnricher
)

ncua_router = APIRouter()
_ncua_client    = NCUAClient()
_cuna_client    = CUNAIntelligenceClient()
_enricher       = CUNANCUAEnricher()


@ncua_router.get("/search")
def ncua_search(
    name: str = "",
    state: str = "",
    limit: int = 10,
    _: User = Depends(get_current_user),
):
    """Search NCUA's public database by credit union name or state."""
    results = _ncua_client.search_credit_unions(name=name, state=state, limit=limit)
    profiles = []
    for r in results:
        cu = _ncua_client.build_cu_profile(raw=r)
        profiles.append({
            "charter_number":      cu.charter_number,
            "name":                cu.cu_name,
            "city":                cu.city,
            "state":               cu.state,
            "charter_type":        cu.charter_type,
            "field_of_membership": cu.field_of_membership,
            "total_assets":        cu.total_assets,
            "total_members":       cu.total_members,
            "total_loans":         cu.total_loans,
            "total_shares":        cu.total_shares,
            "net_worth_ratio":     cu.net_worth_ratio,
            "loan_to_share_ratio": cu.loan_to_share_ratio,
            "num_branches":        cu.num_branches,
            "core_processor":      cu.core_processor,
            "is_licu":             cu.is_low_income_designated,
            "asset_tier":          cu.asset_tier,
            "opportunity_tier":    cu.opportunity_tier,
            "digital_gap_score":   cu.digital_gap_score,
            "cuna_league":         cu.league_affiliation,
            "data_as_of":          cu.data_as_of,
        })
    return {"results": profiles, "count": len(profiles), "source": "NCUA Public API"}


@ncua_router.get("/charter/{charter_number}")
def ncua_by_charter(
    charter_number: str,
    _: User = Depends(get_current_user),
):
    """Fetch full NCUA 5300 data for a specific credit union by charter number."""
    raw = _ncua_client.get_credit_union_details(charter_number)
    if not raw:
        raise HTTPException(status_code=404, detail=f"Charter {charter_number} not found in NCUA database")
    cu = _ncua_client.build_cu_profile(raw=raw)
    enriched = _enricher.enrich_credit_union(cu)
    return {
        "ncua_data":        cu.__dict__,
        "enriched_profile": enriched,
        "source":           "NCUA Public API + CUNA Intelligence",
    }


@ncua_router.post("/enrich-company/{company_id}")
def ncua_enrich_company(
    company_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """
    Trigger live NCUA + CUNA enrichment for an existing company in the DB.
    Searches NCUA by company name, pulls 5300 data, applies signals, re-scores.
    """
    company = db.query(Company).filter_by(id=company_id).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    from app.services.ingestion import enrich_with_ncua_cuna, add_web_signals, run_ai_signal_detection

    def _run():
        enrich_with_ncua_cuna(company, db)
        add_web_signals(company, db)
        run_ai_signal_detection(company, db)
        logger.info(f"NCUA/CUNA enrichment complete for {company.name}")

    background_tasks.add_task(_run)
    return {
        "status":  "enrichment_started",
        "company": company.name,
        "message": f"Searching NCUA for '{company.name}' — check /api/companies/{company_id} in 10 seconds",
    }


@ncua_router.post("/enrich-all-credit-unions")
def ncua_enrich_all(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """
    Trigger NCUA + CUNA enrichment for ALL credit union companies in the DB.
    Runs in background — check pipeline status for progress.
    """
    companies = db.query(Company).filter_by(industry="credit_unions").all()
    if not companies:
        return {"status": "no_companies", "message": "No credit unions found in DB"}

    from app.services.ingestion import enrich_with_ncua_cuna, add_web_signals, run_ai_signal_detection

    def _run_all():
        for company in companies:
            try:
                logger.info(f"Enriching {company.name} with NCUA/CUNA...")
                enrich_with_ncua_cuna(company, db)
                add_web_signals(company, db)
                run_ai_signal_detection(company, db)
            except Exception as e:
                logger.error(f"Failed enriching {company.name}: {e}")
        logger.info(f"Bulk NCUA/CUNA enrichment done for {len(companies)} companies")

    background_tasks.add_task(_run_all)
    return {
        "status":    "bulk_enrichment_started",
        "companies": [c.name for c in companies],
        "count":     len(companies),
        "message":   "Running NCUA lookup for all credit unions. Check /api/pipeline/status in 30 seconds.",
    }


@ncua_router.get("/cuna/priorities")
def cuna_priorities(_: User = Depends(get_current_user)):
    """Return CUNA's current industry advocacy priorities as structured buy signals."""
    return {
        "priorities": _cuna_client.get_industry_priorities(),
        "conferences": _cuna_client.get_cuna_conference_signals(),
        "source": "CUNA published advocacy intelligence",
        "note": "CUNA has no public API — signals derived from published advocacy positions and conference agendas",
    }


@ncua_router.get("/cuna/leagues")
def cuna_leagues(_: User = Depends(get_current_user)):
    """Return CUNA state league directory — key channel partner map."""
    return {
        "leagues": _cuna_client.get_state_league_map(),
        "note": "Each state league is a potential warm-intro channel partner",
    }


@ncua_router.get("/company/{company_id}/regulatory-profile")
def get_regulatory_profile(
    company_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """
    Return the stored NCUA/CUNA data for a company already in the DB.
    If not yet enriched, returns a prompt to trigger enrichment.
    """
    company = db.query(Company).filter_by(id=company_id).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    if not company.regulatory_data:
        return {
            "enriched": False,
            "company":  company.name,
            "message":  f"Not yet enriched. POST /api/ncua/enrich-company/{company_id} to fetch NCUA data.",
        }

    signals = db.query(Signal).filter_by(company_id=company.id).all()
    ncua_signals   = [s for s in signals if s.source in ("ncua_5300", "ncua_profile")]
    cuna_signals   = [s for s in signals if s.source == "cuna_intelligence"]

    return {
        "enriched":       True,
        "company":        company.name,
        "regulatory_src": company.regulatory_src,
        "ncua_data":      company.regulatory_data,
        "ncua_signals":   [{"label": s.signal_label, "severity": s.severity, "type": s.signal_type} for s in ncua_signals],
        "cuna_signals":   [{"label": s.signal_label, "severity": s.severity, "type": s.signal_type} for s in cuna_signals],
        "cuna_league":    company.regulatory_data.get("cuna_league", ""),
        "opportunity_tier": company.regulatory_data.get("opportunity_tier", ""),
        "last_enriched":  str(company.last_enriched_at),
    }
