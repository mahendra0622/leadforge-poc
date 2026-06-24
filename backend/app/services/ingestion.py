"""
FintelliPro — Data Ingestion Service (Updated with CUNA/NCUA)
Full pipeline: Apollo → NCUA → CUNA → Web → AI Scoring
"""
from datetime import datetime
from loguru import logger
from sqlalchemy.orm import Session

from app.models import Company, Contact, Signal
from app.services.apollo_client import apollo_client
from app.services.ai_service import detect_signals, classify_digital_maturity, calculate_opportunity_score
from app.services.regulatory import cuna_ncua_enricher, ncua_client
from app.services.regulatory.cuna_ncua import LEGACY_PROCESSORS, CUNAIntelligenceClient
from app.services.source_refs import ncua_source, cuna_source, web_source


def upsert_company_from_apollo(org_data: dict, db: Session) -> Company:
    apollo_id = org_data.get("id")
    existing = db.query(Company).filter_by(apollo_org_id=apollo_id).first() if apollo_id else None
    company = existing or Company(apollo_org_id=apollo_id)
    if not existing:
        db.add(company)

    company.name             = org_data.get("name", "")
    company.website          = org_data.get("website_url", "")
    company.hq_city          = org_data.get("city", "")
    company.hq_state         = org_data.get("state", "")
    company.hq_country       = org_data.get("country", "US")
    company.employee_count   = org_data.get("estimated_num_employees")
    company.revenue_est      = org_data.get("annual_revenue")
    company.tech_stack       = org_data.get("technology_names", [])
    company.last_enriched_at = datetime.utcnow()
    db.commit()
    db.refresh(company)
    return company


def upsert_contact_from_apollo(person_data: dict, company: Company, db: Session) -> Contact:
    apollo_id = person_data.get("id")
    existing = db.query(Contact).filter_by(apollo_person_id=apollo_id).first() if apollo_id else None
    contact = existing or Contact(apollo_person_id=apollo_id, company_id=company.id)
    if not existing:
        db.add(contact)

    contact.first_name       = person_data.get("first_name", "")
    contact.last_name        = person_data.get("last_name", "")
    contact.title            = person_data.get("title", "")
    contact.email            = person_data.get("email", "")
    contact.email_status     = person_data.get("email_status", "unknown")
    contact.email_confidence = person_data.get("confidence_score")
    contact.linkedin_url     = person_data.get("linkedin_url", "")
    contact.seniority_level  = person_data.get("seniority", "")
    phones = person_data.get("phone_numbers", [])
    contact.phone            = phones[0].get("raw_number") if phones else None
    contact.is_decision_maker = person_data.get("seniority", "") in ["c_suite", "vp", "director"]
    db.commit()
    db.refresh(contact)
    return contact


def enrich_with_ncua_cuna(company: Company, db: Session):
    """Full NCUA + CUNA enrichment for credit unions."""
    logger.info(f"Starting NCUA/CUNA enrichment for: {company.name}")

    results = ncua_client.search_credit_unions(
        name=company.name, state=company.hq_state or "", limit=3
    )

    if not results:
        logger.warning(f"No NCUA match found for {company.name}")
        _apply_cuna_macro_signals(company, db)
        return

    raw = results[0]
    cu = ncua_client.build_cu_profile(raw=raw)

    company.regulatory_src = "NCUA"
    company.regulatory_id  = cu.charter_number
    company.regulatory_data = {
        "charter_number":       cu.charter_number,
        "charter_type":         cu.charter_type,
        "field_of_membership":  cu.field_of_membership,
        "total_assets":         cu.total_assets,
        "total_shares":         cu.total_shares,
        "total_loans":          cu.total_loans,
        "total_members":        cu.total_members,
        "net_worth":            cu.net_worth,
        "net_worth_ratio":      cu.net_worth_ratio,
        "loan_to_share_ratio":  cu.loan_to_share_ratio,
        "num_branches":         cu.num_branches,
        "core_processor":       cu.core_processor,
        "asset_tier":           cu.asset_tier,
        "opportunity_tier":     cu.opportunity_tier,
        "cuna_league":          cu.league_affiliation,
        "is_low_income":        cu.is_low_income_designated,
        "data_as_of":           cu.data_as_of,
    }
    if cu.total_assets:
        company.revenue_est = cu.total_assets
    db.commit()

    _apply_ncua_signals(company, cu, db)
    _apply_cuna_macro_signals(company, db)

    enriched = cuna_ncua_enricher.enrich_credit_union(cu)
    for sd in enriched.get("detected_signals", []):
        _add_signal(company.id, sd["type"], sd["label"], sd["severity"], sd["source"], db)

    logger.info(f"NCUA/CUNA enrichment done for {company.name} (charter {cu.charter_number})")


def _apply_ncua_signals(company: Company, cu, db: Session):
    _ncua = ncua_source(quarter=cu.data_as_of or "2024Q4")
    _ncua_profile = {"source_file": None, "source_url": None, "source_page": None,
                     "source_label": "NCUA Credit Union Profile"}

    if cu.total_assets >= 500_000_000:
        _add_signal(company.id, "growth", f"Enterprise CU — ${cu.total_assets/1e6:.0f}M assets (Tier 1)", 90, "ncua_5300", db, **_ncua)
    elif cu.total_assets >= 100_000_000:
        _add_signal(company.id, "growth", f"Mid-market CU — ${cu.total_assets/1e6:.0f}M assets (Tier 2)", 75, "ncua_5300", db, **_ncua)

    if cu.total_members >= 50_000:
        _add_signal(company.id, "growth", f"Large member base: {cu.total_members:,} members", 80, "ncua_5300", db, **_ncua)

    if cu.net_worth_ratio and cu.net_worth_ratio >= 7.0:
        _add_signal(company.id, "growth", f"Well-capitalized: {cu.net_worth_ratio:.1f}% NWR — budget available", 72, "ncua_5300", db, **_ncua)
    elif cu.net_worth_ratio and cu.net_worth_ratio < 6.0:
        _add_signal(company.id, "pain_point", f"Capital pressure: {cu.net_worth_ratio:.1f}% NWR", 65, "ncua_5300", db, **_ncua)

    if cu.loan_to_share_ratio >= 85:
        _add_signal(company.id, "growth", f"High loan demand ({cu.loan_to_share_ratio:.0f}% LTS ratio)", 78, "ncua_5300", db, **_ncua)
    elif cu.loan_to_share_ratio < 50:
        _add_signal(company.id, "operational_gap", f"Low loan utilization ({cu.loan_to_share_ratio:.0f}% LTS)", 68, "ncua_5300", db, **_ncua)

    if cu.is_low_income_designated:
        _add_signal(company.id, "regulatory_risk", "NCUA Low-Income Designated (LICU) — compliance investment", 70, "ncua_profile", db, **_ncua_profile)

    if cu.core_processor and any(lp.lower() in cu.core_processor.lower() for lp in LEGACY_PROCESSORS):
        _add_signal(company.id, "operational_gap", f"Legacy core: {cu.core_processor} — API overlay opportunity", 82, "ncua_profile", db, **_ncua_profile)

    if cu.num_branches >= 8:
        _add_signal(company.id, "operational_gap", f"Multi-branch ({cu.num_branches} locations) — payments orchestration needed", 65, "ncua_profile", db, **_ncua_profile)


def _apply_cuna_macro_signals(company: Company, db: Session):
    cuna = CUNAIntelligenceClient()
    priorities = cuna.get_industry_priorities()
    _cuna = cuna_source()
    for p in sorted(priorities, key=lambda x: x["urgency"], reverse=True)[:2]:
        _add_signal(company.id, p["signal_type"], f"CUNA Industry Signal: {p['priority']}", p["urgency"], "cuna_intelligence", db, **_cuna)


def add_web_signals(company: Company, db: Session):
    WEB_SIGNALS = {
        "coastalcu.example.com":    {"has_mobile_app": False, "has_api_docs": False, "has_digital_portal": True, "app_store_rating": None},
        "rivervalleycu.example.com":{"has_mobile_app": True,  "has_api_docs": False, "has_digital_portal": True, "app_store_rating": 3.2},
        "summitfcu.example.com":    {"has_mobile_app": True,  "has_api_docs": False, "has_digital_portal": True, "app_store_rating": 2.8},
    }
    domain = (company.website or "").replace("https://","").replace("http://","")
    web = WEB_SIGNALS.get(domain, {"has_mobile_app": False, "has_api_docs": False, "has_digital_portal": True, "app_store_rating": None})

    maturity = classify_digital_maturity(
        has_mobile_app=web.get("has_mobile_app", False), has_api_docs=web.get("has_api_docs", False),
        has_digital_portal=web.get("has_digital_portal", True),
        app_store_rating=web.get("app_store_rating"), tech_stack=company.tech_stack or [],
    )
    company.digital_maturity = maturity
    db.commit()

    _web = web_source(company.website or "", label=f"{company.name} website") if company.website else {}
    if not web.get("has_mobile_app"):
        _add_signal(company.id, "operational_gap", "No mobile banking app detected", 75, "web_scrape", db, **_web)
    if not web.get("has_api_docs"):
        _add_signal(company.id, "digital_gap", "No developer API documentation found", 65, "web_scrape", db, **_web)
    if web.get("app_store_rating") and web["app_store_rating"] < 3.5:
        _add_signal(company.id, "pain_point", f"Low app store rating ({web['app_store_rating']}★)", 80, "web_scrape", db, **_web)


def run_ai_signal_detection(company: Company, db: Session):
    company_data = {
        "name": company.name, "industry": company.industry,
        "hq_city": company.hq_city, "hq_state": company.hq_state,
        "revenue_est": company.revenue_est, "employee_count": company.employee_count,
        "tech_stack": company.tech_stack or [], "regulatory_src": company.regulatory_src,
        "regulatory_data": company.regulatory_data,
        "web_features": "Analyzed via web scraper",
        "news_summary": "No recent news in sample data",
        "job_signals": "Hiring for digital transformation roles",
        "reviews_summary": "Member reviews indicate satisfaction with branch service but frustration with digital tools",
    }
    result = detect_signals(company_data)

    for gap in result.get("operational_gaps", []):
        _add_signal(company.id, "operational_gap", gap["label"], gap.get("severity", 50), "ai_detection", db)
    for pain in result.get("pain_points", []):
        _add_signal(company.id, "pain_point", pain["label"], pain.get("urgency", 50), "ai_detection", db)
    for growth in result.get("growth_signals", []):
        _add_signal(company.id, "growth", growth["label"], growth.get("strength", 50), "ai_detection", db)

    all_signals    = db.query(Signal).filter_by(company_id=company.id, is_active=True).all()
    pain_signals   = [s for s in all_signals if s.signal_type == "pain_point"]
    growth_signals = [s for s in all_signals if s.signal_type == "growth"]
    pain_avg       = sum(s.severity for s in pain_signals)   / len(pain_signals)   if pain_signals   else 50
    growth_avg     = sum(s.severity for s in growth_signals) / len(growth_signals) if growth_signals else 30

    best_contact      = db.query(Contact).filter_by(company_id=company.id, is_decision_maker=True).first()
    apollo_confidence = (best_contact.email_confidence or 75) if best_contact else 75

    score = calculate_opportunity_score(
        digital_maturity=company.digital_maturity or 3,
        pain_severity_avg=pain_avg, growth_strength_avg=growth_avg,
        apollo_confidence=apollo_confidence,
        industry=company.industry or "", has_regulatory_data=bool(company.regulatory_src),
    )
    company.opportunity_score = score
    db.commit()
    logger.info(f"Score for {company.name}: {score}")


def _add_signal(company_id, signal_type, label, severity, source, db: Session, **source_refs):
    if not db.query(Signal).filter_by(company_id=company_id, signal_label=label, source=source).first():
        db.add(Signal(company_id=company_id, signal_type=signal_type,
                      signal_label=label, severity=severity, source=source, is_active=True,
                      **source_refs))
        db.commit()


def run_full_enrichment(industry: str, db: Session) -> dict:
    """Apollo → NCUA/CUNA → Web → AI. Full pipeline."""
    logger.info(f"Pipeline starting for: {industry}")
    stats = {"companies_processed": 0, "contacts_added": 0, "errors": 0}

    apollo_data = apollo_client.people_search(industry_key=industry)
    people = apollo_data.get("people", [])
    processed_orgs = set()

    for person in people:
        org = person.get("organization", {})
        if not org or org.get("id") in processed_orgs:
            continue
        try:
            company = upsert_company_from_apollo(org, db)
            company.industry = industry
            db.commit()
            processed_orgs.add(org.get("id"))
            upsert_contact_from_apollo(person, company, db)
            stats["contacts_added"] += 1

            if industry in ("credit_unions", "banking"):
                enrich_with_ncua_cuna(company, db)
            add_web_signals(company, db)
            run_ai_signal_detection(company, db)
            stats["companies_processed"] += 1
        except Exception as e:
            logger.error(f"Pipeline error for {org.get('name','?')}: {e}")
            stats["errors"] += 1

    logger.info(f"Pipeline done: {stats}")
    return stats
