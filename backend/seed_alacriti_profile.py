"""
Seed the logged-in user's company profile with Alacriti data.
Run with: python seed_alacriti_profile.py [user_email]
If no email is given, updates the first user in the DB.
"""
import sys
import os
from dotenv import load_dotenv

load_dotenv()

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "")
if not DATABASE_URL:
    sys.exit("DATABASE_URL not set")

engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)
db = Session()

# Import after engine is ready
sys.path.insert(0, os.path.dirname(__file__))
from app.models import User

email_filter = sys.argv[1] if len(sys.argv) > 1 else None
if email_filter:
    user = db.query(User).filter_by(email=email_filter).first()
else:
    user = db.query(User).first()

if not user:
    sys.exit(f"No user found{' for ' + email_filter if email_filter else ''}")

print(f"Updating profile for: {user.email}")

user.company_name = "Alacriti"

user.tagline = "One Platform. Payments Modernization. Delivered."

user.product_description = (
    "Alacriti is the engine behind modern money movement — helping financial institutions "
    "and businesses modernize their payments infrastructure and deliver a unified money "
    "movement experience to their consumers. It powers billions in payments every year for "
    "forward-thinking financial institutions, delivering the flexibility, scale, and speed "
    "today's users expect, with technology that transforms how money moves from real-time "
    "rails to seamless integration with legacy systems."
)

user.key_strengths = (
    "Flexibility of Solutions — consumer-centric, configurable solutions regardless of institution size. "
    "Strength of Technology — a tech stack built for rapid, secure, cost-effective delivery of "
    "traditional and faster payments rails. "
    "Single Source of Truth — one unified solution breaking down siloed infrastructure with improved "
    "visibility into rails performance, cash flow, and liquidity. "
    "Depth of Integration — out-of-the-box capability to connect with core banking, digital banking, "
    "fraud, and risk systems. "
    "Unparalleled Speed to Market — average implementation of just 3–4 months."
)

user.differentiators = (
    "ISO 20022-based, cloud-native core — Payments Hub securely orchestrates and processes all payment "
    "types (TCH RTP, FedNow, Zelle, Visa Direct, ACH, Wires) from a single solution. "
    "'Human-Driven Care, Tech-Powered Results' — customers describe Alacriti as a true partner: "
    "'Your team is always responsive.' "
    "Proven traction with real institutions — Royal Credit Union processed $15.5MM in instant payments "
    "within 3 months of launch; ABNB Federal Credit Union moved $5M across 2,300+ transactions in two months. "
    "Strong integration ecosystem — AWS, Fiserv, Alkami, Backbase, Q2, Apiture, The Clearing House, "
    "Socure, Glia, and the U.S. Faster Payments Council."
)

user.products = [
    # Money Movement Apps
    "Unified Money Movement (UMM) — payments/transfers for FIs",
    "Loan Payments",
    "P2P (Zelle)",
    "EBPP — Electronic Bill Presentment and Payments for billers",
    "Payouts — business-to-consumer payouts",
    "Transfers A2A",
    "RfP (Request for Payment)",
    # Payments Platform
    "Payments Hub — centralized infrastructure for instant payments, wires, ACH",
    "RTP (TCH network)",
    "FedNow",
    "Wires (Fedwire)",
    "Global Transfers / Cross-Border Payments",
    "Zelle",
    "Visa Direct",
    "ACH",
    "Instant Payments (RTP + FedNow + Visa Direct)",
    # Risk & Fraud
    "Bank Account Validation & Verification",
]

user.integrations = [
    "AWS",
    "Fiserv",
    "Alkami",
    "Backbase",
    "Q2",
    "Apiture",
    "The Clearing House",
    "Socure",
    "Glia",
    "U.S. Faster Payments Council",
]

user.tone = "consultative"

db.commit()
print("✓ Alacriti profile saved successfully")
db.close()
