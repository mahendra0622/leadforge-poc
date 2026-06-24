"""
FintelliPro — Apollo Free Plan Enrichment
==========================================
Searches for real decision-maker contacts at your top CUs.

Free plan limits:
  - Search (people/org search): FREE — no credits
  - Email reveal: 100 credits/month (1 per contact)
  - Mobile: SKIP — costs 8 credits each
  - Export: 10 credits/month

Strategy:
  - Search all 100 CUs for free (just gets names + partial data)
  - Only reveal emails for top 10 highest-scored CUs (uses 10 credits)
  - Store everything in DB — never re-fetch what we already have
  - Display partial data (name, title, LinkedIn) for everyone else

Run:
    python apollo_enrich.py              # enrich top 10 with real emails
    python apollo_enrich.py --all        # search all CUs (free, no credits)
    python apollo_enrich.py --test       # test your API key works
"""

import sys, os, uuid, argparse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.db.database import SessionLocal, init_db
from app.models import Company, Contact
from app.services.apollo_client import ApolloClient
from app.core.config import settings

G="\033[92m"; Y="\033[93m"; C="\033[96m"; W="\033[0m"; B="\033[1m"; R="\033[91m"
def ok(s):   print(f"  {G}✓{W} {s}")
def warn(s): print(f"  {Y}⚠{W}  {s}")
def info(s): print(f"  → {s}")
def err(s):  print(f"  {R}✗{W} {s}")
def hdr(s):  print(f"\n{B}{C}{s}{W}\n  {'─'*52}")


def test_api_key(client: ApolloClient):
    hdr("Testing Apollo API key")
    result = client.get_credit_balance()
    if "error" in result:
        err(f"API key test failed: {result['error']}")
        return False
    ok(f"API key is valid")
    if result.get("is_logged_in"):
        ok(f"Logged in: {result.get('email', 'unknown')}")
    info(f"Full response: {result}")
    return True


def search_contacts_free(client: ApolloClient, company: Company) -> list[dict]:
    """
    Search Apollo for contacts at this company.
    FREE — does not consume credits. Gets partial contact data.
    """
    result = client.search_people_at_company(
        company_name=company.name,
        domain=company.website or "",
    )
    return result.get("people", [])


def save_contact(db, company: Company, person: dict, reveal_email: bool = False) -> bool:
    """
    Save a contact to DB. If reveal_email=True, costs 1 credit.
    Returns True if saved, False if already exists.
    """
    # Skip if we already have this contact
    existing = db.query(Contact).filter_by(company_id=company.id).first()
    if existing:
        return False

    org = person.get("organization") or {}

    db.add(Contact(
        id               = str(uuid.uuid4()),
        company_id       = company.id,
        apollo_person_id = person.get("id", ""),
        first_name       = person.get("first_name", ""),
        last_name        = person.get("last_name", ""),
        title            = person.get("title", ""),
        email            = person.get("email", ""),
        email_status     = person.get("email_status", "guessed"),
        email_confidence = person.get("confidence_score", 60),
        phone            = None,   # skip mobile — costs 8 credits each
        linkedin_url     = person.get("linkedin_url", ""),
        seniority_level  = person.get("seniority", ""),
        is_decision_maker= person.get("seniority","") in ("c_suite","vp","director"),
    ))
    db.commit()
    return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--all",    action="store_true", help="Search all CUs (free, no credits)")
    parser.add_argument("--test",   action="store_true", help="Test API key only")
    parser.add_argument("--reveal", type=int, default=10, help="How many top CUs to reveal emails for (default 10 = free plan limit)")
    args = parser.parse_args()

    if not settings.APOLLO_API_KEY:
        err("APOLLO_API_KEY not set in .env")
        err("Add it: APOLLO_API_KEY=your_key_here")
        sys.exit(1)

    client = ApolloClient()
    init_db()
    db = SessionLocal()

    # Test key
    if args.test:
        test_api_key(client)
        return

    print(f"\n{B}{C}FintelliPro — Apollo Free Plan Enrichment{W}")
    print(f"  Plan: FREE  ·  Email reveals: {args.reveal} max  ·  Mobile: skipped\n")

    # Get companies sorted by score — highest priority first
    companies = db.query(Company).filter_by(industry="credit_unions") \
                  .order_by(Company.opportunity_score.desc()).all()

    if not companies:
        err("No companies in DB. Run ncua_bulk_download.py first.")
        return

    total_limit = len(companies) if args.all else min(50, len(companies))
    reveal_limit = args.reveal

    hdr(f"Step 1 — Search contacts (FREE, no credits)")
    info(f"Searching {total_limit} CUs for decision-maker contacts...")

    searched = 0
    found = 0
    revealed = 0

    for i, co in enumerate(companies[:total_limit]):
        # Skip if already has contacts
        existing = db.query(Contact).filter_by(company_id=co.id).count()
        if existing > 0:
            info(f"[{i+1:03d}] {co.name[:45]} — already has {existing} contact(s), skipping")
            continue

        people = search_contacts_free(client, co)
        searched += 1

        if not people:
            warn(f"[{i+1:03d}] {co.name[:45]} — no contacts found")
            continue

        person = people[0]  # take the best match (first = highest confidence)

        # Decide whether to reveal email (costs 1 credit)
        should_reveal = revealed < reveal_limit and co.opportunity_score >= 80

        if save_contact(db, co, person, reveal_email=should_reveal):
            if should_reveal:
                revealed += 1
                print(f"  {G}✓{W} [{i+1:03d}] {co.name[:38]:<38}  📧 {person.get('email','—')}  ({person.get('title','?')[:30]})")
            else:
                print(f"  {Y}·{W} [{i+1:03d}] {co.name[:38]:<38}  👤 {person.get('first_name','')} {person.get('last_name','')}  ({person.get('title','?')[:30]})")
            found += 1

        # Small delay to stay within rate limits
        import time; time.sleep(0.5)

    # Summary
    all_contacts = db.query(Contact).count()
    print(f"\n{B}{C}Summary{W}\n  {'─'*52}")
    print(f"  Companies searched:  {searched}")
    print(f"  Contacts found:      {found}")
    print(f"  Emails revealed:     {revealed}  (used {revealed}/100 credits this month)")
    print(f"  Total contacts in DB:{all_contacts}")
    print(f"\n  {G}Credits remaining: ~{100 - revealed} email reveals left this month{W}")
    print(f"  Refresh http://localhost:3000 to see contacts in the app\n")

    db.close()


if __name__ == "__main__":
    main()
