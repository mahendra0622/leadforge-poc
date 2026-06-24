"""
LeadForge POC — Database Seeder (UUID-fixed)
Run: python seed.py
"""
import sys, os, uuid as _uuid
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.db.database import SessionLocal, init_db
from app.models import Company, Contact, Signal, User
from app.core.security import hash_password

# Proper UUID format — PostgreSQL UUID columns require 8-4-4-4-12 hex format
U_USER   = "a0000000-0000-0000-0000-000000000001"
U_CO_001 = "b0000000-0000-0000-0000-000000000001"
U_CO_002 = "b0000000-0000-0000-0000-000000000002"
U_CO_003 = "b0000000-0000-0000-0000-000000000003"
U_CO_004 = "b0000000-0000-0000-0000-000000000004"
U_CO_005 = "b0000000-0000-0000-0000-000000000005"
U_CO_006 = "b0000000-0000-0000-0000-000000000006"
U_CT_001 = "c0000000-0000-0000-0000-000000000001"
U_CT_002 = "c0000000-0000-0000-0000-000000000002"
U_CT_003 = "c0000000-0000-0000-0000-000000000003"
U_CT_004 = "c0000000-0000-0000-0000-000000000004"
U_CT_005 = "c0000000-0000-0000-0000-000000000005"
U_CT_006 = "c0000000-0000-0000-0000-000000000006"


def seed():
    print("Initialising database tables...")
    init_db()
    db = SessionLocal()

    # Demo user
    if not db.query(User).filter_by(email="demo@leadforge.ai").first():
        db.add(User(
            id=U_USER,
            email="demo@leadforge.ai",
            hashed_password=hash_password("demo1234"),
            full_name="Alex Kumar",
            company_name="LeadForge",
            product_description="API-first real-time payment platform that integrates with legacy core banking systems in under 48 hours",
            key_strengths="Real-time payments, API-first architecture, fraud prevention, compliance support, zero core replacement required",
            differentiators="48-hour integration SLA, no rip-and-replace, 99.99% uptime, SOC2 Type II certified",
            tone="consultative",
        ))
        db.commit()
        print("  ✓ Demo user created — demo@leadforge.ai / demo1234")
    else:
        print("  · Demo user already exists")

    # Companies
    companies = [
        {"id": U_CO_001, "apollo_org_id": "apo_org_001", "name": "Coastal Community Credit Union",
         "industry": "credit_unions", "website": "coastalcu.example.com",
         "hq_city": "San Diego", "hq_state": "CA", "revenue_est": 480_000_000, "employee_count": 220,
         "tech_stack": ["Jack Henry", "Symitar", "Salesforce"], "regulatory_src": "NCUA",
         "regulatory_id": "24680", "regulatory_data": {"total_assets": 480_000_000, "total_members": 48500, "charter_type": "State"},
         "digital_maturity": 2, "opportunity_score": 94, "outreach_status": "new"},
        {"id": U_CO_002, "apollo_org_id": "apo_org_002", "name": "SunBridge Insurance Group",
         "industry": "insurance", "website": "sunbridge.example.com",
         "hq_city": "Atlanta", "hq_state": "GA", "revenue_est": 1_200_000_000, "employee_count": 850,
         "tech_stack": ["Guidewire", "Salesforce", "Duck Creek"], "regulatory_src": "NAIC",
         "regulatory_id": "00815", "regulatory_data": {"gwp": 1_200_000_000, "lines": ["P&C", "Auto"], "state_count": 32},
         "digital_maturity": 3, "opportunity_score": 87, "outreach_status": "contacted"},
        {"id": U_CO_003, "apollo_org_id": "apo_org_003", "name": "HorizonLend Mortgage",
         "industry": "lending", "website": "horizonlend.example.com",
         "hq_city": "Dallas", "hq_state": "TX", "revenue_est": 320_000_000, "employee_count": 180,
         "tech_stack": ["Encompass", "Salesforce"], "regulatory_src": None,
         "regulatory_id": None, "regulatory_data": None,
         "digital_maturity": 4, "opportunity_score": 88, "outreach_status": "replied"},
        {"id": U_CO_004, "apollo_org_id": "apo_org_004", "name": "ClarityRCM Health",
         "industry": "healthcare", "website": "clarityrcm.example.com",
         "hq_city": "Nashville", "hq_state": "TN", "revenue_est": 145_000_000, "employee_count": 310,
         "tech_stack": ["Epic", "Waystar", "Microsoft Azure"], "regulatory_src": None,
         "regulatory_id": None, "regulatory_data": None,
         "digital_maturity": 2, "opportunity_score": 91, "outreach_status": "qualified"},
        {"id": U_CO_005, "apollo_org_id": "apo_org_005", "name": "River Valley Credit Union",
         "industry": "credit_unions", "website": "rivervalleycu.example.com",
         "hq_city": "Portland", "hq_state": "OR", "revenue_est": 280_000_000, "employee_count": 145,
         "tech_stack": ["Fiserv", "DNA Core"], "regulatory_src": "NCUA",
         "regulatory_id": "13579", "regulatory_data": {"total_assets": 280_000_000, "total_members": 28200, "charter_type": "Federal"},
         "digital_maturity": 3, "opportunity_score": 76, "outreach_status": "new"},
        {"id": U_CO_006, "apollo_org_id": "apo_org_006", "name": "PacWest Utilities Corp",
         "industry": "utilities", "website": "pacwestutil.example.com",
         "hq_city": "Portland", "hq_state": "OR", "revenue_est": 890_000_000, "employee_count": 1200,
         "tech_stack": ["SAP", "Oracle Utilities"], "regulatory_src": None,
         "regulatory_id": None, "regulatory_data": None,
         "digital_maturity": 2, "opportunity_score": 72, "outreach_status": "new"},
    ]
    for cd in companies:
        if not db.query(Company).filter_by(id=cd["id"]).first():
            db.add(Company(**cd))
    db.commit()
    print(f"  ✓ {len(companies)} companies seeded")

    # Contacts
    contacts = [
        {"id": U_CT_001, "company_id": U_CO_001, "apollo_person_id": "ap_001",
         "first_name": "Jennifer", "last_name": "Walsh", "title": "VP of Technology",
         "email": "j.walsh@coastalcu.example.com", "email_status": "verified",
         "email_confidence": 98, "phone": "+1-619-555-0142",
         "linkedin_url": "linkedin.com/in/jennifer-walsh", "is_decision_maker": True, "seniority_level": "vp"},
        {"id": U_CT_002, "company_id": U_CO_001, "apollo_person_id": "ap_002",
         "first_name": "Marcus", "last_name": "Chen", "title": "Chief Digital Officer",
         "email": "m.chen@coastalcu.example.com", "email_status": "verified",
         "email_confidence": 95, "phone": None,
         "linkedin_url": "linkedin.com/in/marcus-chen-cdo", "is_decision_maker": True, "seniority_level": "c_suite"},
        {"id": U_CT_003, "company_id": U_CO_002, "apollo_person_id": "ap_003",
         "first_name": "David", "last_name": "Ruiz", "title": "SVP Claims Technology",
         "email": "d.ruiz@sunbridge.example.com", "email_status": "verified",
         "email_confidence": 95, "phone": "+1-404-555-0317",
         "linkedin_url": "linkedin.com/in/david-ruiz-ins", "is_decision_maker": True, "seniority_level": "vp"},
        {"id": U_CT_004, "company_id": U_CO_003, "apollo_person_id": "ap_004",
         "first_name": "Anthony", "last_name": "Bell", "title": "CTO",
         "email": "a.bell@horizonlend.example.com", "email_status": "verified",
         "email_confidence": 99, "phone": "+1-214-555-0198",
         "linkedin_url": "linkedin.com/in/anthony-bell-cto", "is_decision_maker": True, "seniority_level": "c_suite"},
        {"id": U_CT_005, "company_id": U_CO_004, "apollo_person_id": "ap_005",
         "first_name": "Rachel", "last_name": "Kim", "title": "Chief Revenue Officer",
         "email": "r.kim@clarityrcm.example.com", "email_status": "verified",
         "email_confidence": 96, "phone": "+1-615-555-0274",
         "linkedin_url": "linkedin.com/in/rachel-kim-rcm", "is_decision_maker": True, "seniority_level": "c_suite"},
        {"id": U_CT_006, "company_id": U_CO_005, "apollo_person_id": "ap_006",
         "first_name": "Linda", "last_name": "Okafor", "title": "Director of IT Modernization",
         "email": "l.okafor@rivervalleycu.example.com", "email_status": "probable",
         "email_confidence": 88, "phone": "+1-503-555-0461",
         "linkedin_url": "linkedin.com/in/linda-okafor", "is_decision_maker": True, "seniority_level": "director"},
    ]
    for cd in contacts:
        if not db.query(Contact).filter_by(id=cd["id"]).first():
            db.add(Contact(**cd))
    db.commit()
    print(f"  ✓ {len(contacts)} contacts seeded")

    # Signals
    signals = [
        (U_CO_001, "operational_gap", "Legacy Symitar core — no real-time payment rails", 85, "web_scrape"),
        (U_CO_001, "operational_gap", "No mobile banking app detected", 75, "web_scrape"),
        (U_CO_001, "pain_point", "Members report slow ACH transfers (2-3 day delays)", 80, "reviews"),
        (U_CO_001, "pain_point", "Paper-based loan application process", 70, "web_scrape"),
        (U_CO_001, "growth", "Hiring: Head of Digital Banking (3 open roles)", 78, "jobs"),
        (U_CO_001, "digital_gap", "No developer API documentation found", 65, "web_scrape"),
        (U_CO_002, "pain_point", "7-day average claims payout delay", 88, "news"),
        (U_CO_002, "operational_gap", "Manual claims adjudication workflow", 80, "ai_detection"),
        (U_CO_002, "growth", "Expanding into 8 new states this year", 75, "news"),
        (U_CO_003, "pain_point", "7-day average loan close time", 85, "ai_detection"),
        (U_CO_003, "operational_gap", "Manual income verification process", 72, "web_scrape"),
        (U_CO_003, "growth", "Series B raised — $42M for growth", 90, "news"),
        (U_CO_004, "pain_point", "18% claim denial rate — above industry average", 92, "ai_detection"),
        (U_CO_004, "operational_gap", "Manual ERA processing — no automation", 85, "web_scrape"),
        (U_CO_004, "growth", "Acquired 2 regional RCM companies this year", 80, "news"),
        (U_CO_005, "pain_point", "App store rating 3.2 stars — below average", 72, "web_scrape"),
        (U_CO_005, "operational_gap", "No open banking API layer", 68, "web_scrape"),
        (U_CO_005, "growth", "Asset growth 18% YoY", 65, "regulatory"),
        (U_CO_006, "operational_gap", "30% of bills still sent via paper mail", 78, "web_scrape"),
        (U_CO_006, "pain_point", "Payment portal outages reported by customers", 70, "reviews"),
        (U_CO_006, "growth", "Smart grid project — $120M capital investment", 72, "news"),
    ]
    sig_count = 0
    for (company_id, sig_type, label, severity, source) in signals:
        if not db.query(Signal).filter_by(company_id=company_id, signal_label=label).first():
            db.add(Signal(
                id=str(_uuid.uuid4()),
                company_id=company_id,
                signal_type=sig_type,
                signal_label=label,
                severity=severity,
                source=source,
                is_active=True,
            ))
            sig_count += 1
    db.commit()
    print(f"  ✓ {sig_count} signals seeded")

    db.close()
    print("\n✅ Seed complete!")
    print("\nLogin credentials:")
    print("  Email:    demo@leadforge.ai")
    print("  Password: demo1234")
    print("\nOpen: http://localhost:3000")


if __name__ == "__main__":
    seed()
