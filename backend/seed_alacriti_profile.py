"""
seed_alacriti_profile.py
========================
Fills the demo user's company profile with Alacriti's real data
so the Settings page is pre-populated for the demo.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql://leadforge_db_utkx_user:Ydw9AloKOqyYBhbLWTxSf4uY3Q0eESzB"
    "@dpg-dag9v0jl550s73aeqba0-a.oregon-postgres.render.com/leadforge_db_utkx",
)

from app.db.database import SessionLocal
from app.models import User

ALACRITI_PROFILE = {
    "company_name":        "Alacriti",
    "tagline":             "One Platform. Payments Modernization. Delivered.",
    "product_description": (
        "Alacriti is a cloud-native payments technology company that helps financial "
        "institutions modernize their payment infrastructure. Our unified platform "
        "connects banks and credit unions to RTP, FedNow, ACH, Fedwire, and SWIFT "
        "through a single API — eliminating the need for multiple vendor relationships "
        "and legacy point solutions."
    ),
    "key_strengths": (
        "Cloud-native architecture; Single API for all payment rails (RTP, FedNow, ACH, Fedwire, SWIFT); "
        "Proven at scale with 100+ financial institutions; "
        "Fastest time-to-live for FedNow and RTP onboarding; "
        "White-glove implementation and dedicated support"
    ),
    "differentiators": (
        "Only vendor offering a unified multi-rail payment hub from a single platform; "
        "No per-transaction fees on real-time rails; "
        "Pre-built connectors to major core processors (Fiserv, Jack Henry, FIS, Q2); "
        "ISO 20022-native from day one"
    ),
    "products": [
        "Orbipay EBPP (Bill Pay)",
        "RTP Connector",
        "FedNow Connector",
        "ACH Gateway",
        "Fedwire / SWIFT",
        "Payment Hub",
    ],
    "case_studies": [
        {"customer": "BECU", "outcome": "Launched RTP in under 90 days using Alacriti's pre-built Fiserv connector"},
        {"customer": "Alliant Credit Union", "outcome": "Replaced 3 payment vendors with single Alacriti platform, cutting ops cost 40%"},
        {"customer": "Suncoast Credit Union", "outcome": "First credit union live on FedNow via Alacriti — onboarded in 6 weeks"},
    ],
    "integrations": [
        "Fiserv", "Jack Henry", "FIS", "Q2", "Symitar",
        "Fedwire", "SWIFT", "Nacha ACH", "TCH RTP", "FedNow",
    ],
    "tone": "consultative",
}

def run():
    db = SessionLocal()
    user = db.query(User).filter(User.email == "demo@fintellipro.com").first()
    if not user:
        print("Demo user not found.")
        db.close()
        return

    for field, value in ALACRITI_PROFILE.items():
        setattr(user, field, value)

    db.commit()
    print(f"✅ Alacriti profile seeded for {user.email}")
    print(f"   company_name:  {user.company_name}")
    print(f"   tagline:       {user.tagline}")
    print(f"   products:      {len(user.products or [])} items")
    print(f"   case_studies:  {len(user.case_studies or [])} items")
    print(f"   integrations:  {len(user.integrations or [])} items")
    db.close()

if __name__ == "__main__":
    run()
