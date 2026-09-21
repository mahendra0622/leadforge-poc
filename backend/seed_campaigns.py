"""
seed_campaigns.py
==================
Seeds realistic demo campaigns for the demo user.
"""
import os, sys, uuid
from datetime import datetime, timedelta
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql://leadforge_db_utkx_user:Ydw9AloKOqyYBhbLWTxSf4uY3Q0eESzB"
    "@dpg-dag9v0jl550s73aeqba0-a.oregon-postgres.render.com/leadforge_db_utkx",
)

from app.db.database import SessionLocal
from app.models import User, Campaign

CAMPAIGNS = [
    {
        "name": "Q3 FedNow — Large CUs ($1B+)",
        "industry": "credit_unions",
        "status": "active",
        "channel": "email",
        "min_score": 75,
        "total_sent": 48,
        "total_opens": 21,
        "total_replies": 6,
        "from_name": "Alex Kumar",
        "from_email": "alex@alacriti.com",
        "days_ago": 18,
    },
    {
        "name": "RTP Modernization — Mid-Market CUs",
        "industry": "credit_unions",
        "status": "active",
        "channel": "email",
        "min_score": 65,
        "total_sent": 73,
        "total_opens": 29,
        "total_replies": 9,
        "from_name": "Alex Kumar",
        "from_email": "alex@alacriti.com",
        "days_ago": 34,
    },
    {
        "name": "LinkedIn Outreach — Payment Leaders",
        "industry": "credit_unions",
        "status": "paused",
        "channel": "linkedin",
        "min_score": 70,
        "total_sent": 35,
        "total_opens": 18,
        "total_replies": 4,
        "from_name": "Alex Kumar",
        "from_email": None,
        "days_ago": 52,
    },
    {
        "name": "Community Banks — ACH Gateway",
        "industry": "banks",
        "status": "draft",
        "channel": "email",
        "min_score": 60,
        "total_sent": 0,
        "total_opens": 0,
        "total_replies": 0,
        "from_name": "Alex Kumar",
        "from_email": "alex@alacriti.com",
        "days_ago": 5,
    },
    {
        "name": "FedNow Early Adopters — Q2 Follow-up",
        "industry": "credit_unions",
        "status": "completed",
        "channel": "email",
        "min_score": 80,
        "total_sent": 22,
        "total_opens": 11,
        "total_replies": 5,
        "from_name": "Alex Kumar",
        "from_email": "alex@alacriti.com",
        "days_ago": 90,
    },
]


def run():
    db = SessionLocal()
    user = db.query(User).filter(User.email == "demo@fintellipro.com").first()
    if not user:
        print("Demo user not found.")
        db.close()
        return

    # Remove existing demo campaigns to avoid duplication
    existing = db.query(Campaign).filter_by(owner_id=user.id).all()
    for c in existing:
        db.delete(c)
    db.flush()

    now = datetime.utcnow()
    for data in CAMPAIGNS:
        days_ago = data.pop("days_ago")
        camp = Campaign(
            id=str(uuid.uuid4()),
            owner_id=user.id,
            created_at=now - timedelta(days=days_ago),
            **data,
        )
        db.add(camp)

    db.commit()
    print(f"✅ Seeded {len(CAMPAIGNS)} campaigns for {user.email}")
    for c in db.query(Campaign).filter_by(owner_id=user.id).all():
        sent = c.total_sent
        opens = c.total_opens
        replies = c.total_replies
        open_r = round(opens / sent * 100, 1) if sent > 0 else 0
        reply_r = round(replies / sent * 100, 1) if sent > 0 else 0
        print(f"  [{c.status:10}] {c.name} — {sent} sent, {open_r}% open, {reply_r}% reply")
    db.close()


if __name__ == "__main__":
    run()
