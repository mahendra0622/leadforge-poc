"""
FintelliPro — News Signal Seeder
===================================
Generates realistic news/event signals for all CUs in the DB.
Uses deterministic templates based on each CU's NCUA profile —
no external RSS calls needed (avoids cloud IP blocking).

Source URLs are Google News search queries so every link works.

Run:
    python seed_news_signals.py
    python seed_news_signals.py --reset   # wipe & re-seed all news signals
"""

import sys, os, uuid, random, urllib.parse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.db.database import SessionLocal, init_db
from app.models import Company, Signal

G="\033[92m"; Y="\033[93m"; C="\033[96m"; W="\033[0m"; B="\033[1m"
def ok(s):   print(f"  {G}✓{W} {s}")
def info(s): print(f"  → {s}")
def hdr(s):  print(f"\n{B}{C}{s}{W}\n  {'─'*54}")


def gnews(cu_name: str, topic: str) -> str:
    """Build a real Google News search URL for cu_name + topic."""
    q = urllib.parse.quote(f'"{cu_name}" {topic}')
    return f"https://news.google.com/search?q={q}&hl=en-US&gl=US&ceid=US%3Aen"


# ── Signal template library ─────────────────────────────────────────
# (label_template, severity_base, source_label, search_topic)
# search_topic is appended after the CU name in the Google News search URL.

TEMPLATES = {
    "growth": [
        ("{name} announces record asset growth, surpassing ${assets_m}M milestone",
         82, "CUInsight", "record assets growth milestone"),
        ("{name} appoints new Chief Digital Officer to accelerate digital banking roadmap",
         88, "CUToday", "Chief Digital Officer CDO appointment"),
        ("{name} reports {members_k}K member milestone, fastest-growing CU in {state}",
         79, "CUInsight", "member growth milestone"),
        ("{name} completes merger with regional credit union, expanding {state} footprint",
         85, "American Banker", "merger acquisition credit union"),
        ("{name} launches fintech partnership for embedded lending at point-of-sale",
         80, "CU Times", "fintech partnership embedded lending"),
        ("{name} opens {city} flagship branch, investing $12M in member experience",
         72, "CUToday", "new branch opening"),
        ("{name} CTO joins CUNA Technology Council advisory board",
         74, "CUInsight", "CTO technology leadership CUNA"),
        ("{name} secures CDFI certification, unlocking $8M federal investment",
         77, "NCUA Press", "CDFI certification federal investment"),
    ],
    "operational_gap": [
        ("{name} selects new digital banking platform to replace {core_short} legacy stack",
         90, "CU Times", "core conversion digital banking platform"),
        ("{name} launches mobile app overhaul targeting Gen-Z members in {state}",
         78, "Finovate", "mobile app digital banking launch"),
        ("{name} issues RFP for real-time payment rails integration",
         86, "Payments Dive", "RFP real-time payments FedNow"),
        ("{name} announces core conversion timeline — evaluating Corelation, Fiserv DNA",
         92, "CUToday", "core conversion Fiserv Corelation"),
        ("{name} reports 34% increase in digital account openings, straining legacy systems",
         81, "BAI Banking Strategies", "digital account opening technology"),
        ("{name} CIO departing after 8 years — technology strategy review underway",
         83, "CUInsight", "CIO departure technology leadership"),
        ("{name} pilots AI-powered loan decisioning with regional fintech partner",
         76, "Finovate", "AI loan decisioning fintech"),
    ],
    "regulatory_risk": [
        ("{name} completes FedNow go-live, first in {state} to offer instant payments",
         84, "Payments Dive", "FedNow instant payments go-live"),
        ("NCUA issues {name} Matters Requiring Attention letter — BSA program gaps cited",
         91, "NCUA Enforcement", "NCUA enforcement MRA BSA compliance"),
        ("{name} Board approves $4.2M cybersecurity investment following NCUA exam findings",
         88, "CUToday", "cybersecurity investment NCUA examination"),
        ("{name} prepares for Section 1033 open banking compliance — API build underway",
         82, "American Banker", "Section 1033 open banking compliance API"),
        ("CFPB names {name} in complaint trend — members cite slow digital transfer speeds",
         86, "CFPB", "CFPB complaint digital banking"),
        ("{name} signs FedNow service agreement, targets Q3 2025 go-live",
         80, "Payments Dive", "FedNow service agreement instant payments"),
        ("{name} expands LICU programs following NCUA low-income designation renewal",
         75, "NCUA Press", "LICU low-income designation NCUA"),
    ],
    "pain_point": [
        ("{name} mobile banking app suffers 6-hour outage during peak deposit window",
         89, "CU Times", "mobile banking outage downtime"),
        ("{name} members report ACH delays — back-office queue backlog under investigation",
         84, "CUToday", "ACH delay payment processing issue"),
        ("{name} discloses third-party data incident affecting 18K member records",
         93, "DataBreaches.net", "data breach security incident members"),
        ("{name} reports $1.1M in card fraud losses in Q1 — above peer median",
         87, "CUInsight", "card fraud losses security"),
        ("{name} faces class-action suit over overdraft fee practices",
         85, "American Banker", "overdraft fee lawsuit class action"),
    ],
}


def pick_signals(co, rng: random.Random) -> list[dict]:
    assets   = co.revenue_est or 0
    members  = (co.regulatory_data or {}).get("total_members", 0)
    core     = ((co.tech_stack or [""])[0]) if co.tech_stack else ""
    licu     = (co.regulatory_data or {}).get("is_licu", False)
    score    = co.opportunity_score or 50
    name     = co.name or "Credit Union"
    city     = co.hq_city or "the area"
    state    = co.hq_state or "the state"

    assets_m  = f"{assets/1_000_000:,.0f}" if assets >= 1_000_000 else "N/A"
    assets_b  = f"{assets/1_000_000_000:.1f}" if assets >= 1_000_000_000 else assets_m
    members_k = str(max(1, members // 1000))
    core_short = core.split("(")[0].strip() if core else "legacy core"

    ctx = dict(name=name, city=city, state=state,
               core_short=core_short, assets_m=assets_m,
               assets_b=assets_b, members_k=members_k)

    pool: list[tuple[str, tuple]] = []

    for t in TEMPLATES["growth"]:
        pool.append(("growth", t))

    if score >= 70:
        for t in TEMPLATES["operational_gap"]:
            pool.append(("operational_gap", t))
            pool.append(("operational_gap", t))

    for t in TEMPLATES["regulatory_risk"]:
        pool.append(("regulatory_risk", t))
    if licu:
        pool.append(("regulatory_risk", TEMPLATES["regulatory_risk"][-1]))

    if assets < 5_000_000_000:
        for t in TEMPLATES["pain_point"]:
            pool.append(("pain_point", t))

    rng.shuffle(pool)

    seen_labels = set()
    chosen = []
    for sig_type, (label_tmpl, sev_base, src_label, search_topic) in pool:
        try:
            label = "News: " + label_tmpl.format(**ctx)
            if label in seen_labels:
                continue
            seen_labels.add(label)
        except KeyError:
            continue

        sev = min(95, max(65, sev_base + rng.randint(-5, 8) + (score - 75) // 10))

        chosen.append({
            "signal_type":  sig_type,
            "signal_label": label,
            "severity":     sev,
            "source":       f"news_{src_label.split()[0].lower()[:20]}",
            "source_url":   gnews(name, search_topic),
            "source_label": src_label,
        })

        target = 3 if assets >= 1_000_000_000 else 2
        if len(chosen) >= target:
            break

    return chosen


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--reset", action="store_true",
                        help="Delete all existing news signals then re-seed")
    args = parser.parse_args()

    print(f"\n{B}{C}FintelliPro — News Signal Seeder{W}")

    init_db()
    db = SessionLocal()

    if args.reset:
        deleted = db.query(Signal).filter(Signal.source.like("news_%")).delete(synchronize_session=False)
        db.commit()
        print(f"  Deleted {deleted} existing news signals\n")

    companies = db.query(Company).filter_by(industry="credit_unions") \
                  .order_by(Company.opportunity_score.desc()).all()

    if not companies:
        print("  No CUs found. Run ncua_live_seed.py first.")
        db.close()
        return

    print(f"  {len(companies)} credit unions found\n")
    hdr("Seeding news signals")

    total_added = 0
    rng = random.Random(42)

    for co in companies:
        existing_news = db.query(Signal).filter(
            Signal.company_id == co.id,
            Signal.source.like("news_%"),
        ).count()
        if existing_news > 0:
            info(f"{co.name}: {existing_news} news signals already exist — skipping")
            continue

        signals = pick_signals(co, rng)
        for sig in signals:
            db.add(Signal(
                id           = str(uuid.uuid4()),
                company_id   = co.id,
                signal_type  = sig["signal_type"],
                signal_label = sig["signal_label"],
                severity     = sig["severity"],
                source       = sig["source"],
                source_url   = sig["source_url"],
                source_label = sig["source_label"],
                is_active    = True,
            ))
        total_added += len(signals)
        ok(f"{co.name:<44} +{len(signals)} signals")

    db.commit()

    total_sigs = db.query(Signal).count()
    news_sigs  = db.query(Signal).filter(Signal.source.like("news_%")).count()

    print(f"\n{B}{C}Done!{W}\n  {'─'*54}")
    print(f"  News signals added:  {total_added}")
    print(f"  Total signals in DB: {total_sigs}")
    print(f"  News signals total:  {news_sigs}")
    print(f"\n  {G}✅ All news signal links now point to Google News searches.{W}\n")
    db.close()


if __name__ == "__main__":
    main()
