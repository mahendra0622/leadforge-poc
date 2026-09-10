"""Quick diagnostic: print regulatory_data fields for 5 CUs."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.db.database import SessionLocal, init_db
from app.models import Company

init_db()
db = SessionLocal()
cos = db.query(Company).filter_by(industry="credit_unions").limit(5).all()
for c in cos:
    rd = c.regulatory_data or {}
    print(f"\n{c.name}")
    for k in ["roa", "roe", "net_worth_ratio", "financial_health_score", "growth_momentum_score", "modernization_urgency"]:
        print(f"  {k}: {rd.get(k, 'MISSING')}")
    print(f"  all keys: {sorted(rd.keys())}")
db.close()
print("\nDone.")
