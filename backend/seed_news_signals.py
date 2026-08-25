"""
FintelliPro — News Signal Seeder
===================================
Generates realistic news/event signals for all CUs in the DB.
Uses deterministic templates based on each CU's NCUA profile —
no external RSS calls needed (avoids cloud IP blocking).

Each CU gets 2-4 varied signals covering:
  - Leadership changes  (growth)
  - Tech / core upgrade (operational_gap)
  - Regulatory / FedNow (regulatory_risk)
  - Growth milestones   (growth)
  - Member services     (operational_gap)
  - Fintech partnership (growth)
  - Security / fraud    (pain_point)

Run:
    python seed_news_signals.py
"""

import sys, os, uuid, random, math
from datetime import datetime, timedelta
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.db.database import SessionLocal, init_db
from app.models import Company, Signal

random.seed(0)  # deterministic so re-runs are idempotent-ish

G="\033[92m"; Y="\033[93m"; C="\033[96m"; W="\033[0m"; B="\033[1m"
def ok(s):   print(f"  {G}✓{W} {s}")
def info(s): print(f"  → {s}")
def hdr(s):  print(f"\n{B}{C}{s}{W}\n  {'─'*54}")

# ── Signal template library ────────────────────────────────────────
# Each template: (signal_type, label_template, severity_base, source_label, source_url_tmpl)
# Placeholders: {name}, {city}, {state}, {core_short}, {assets_b}, {assets_m}, {members_k}

TEMPLATES = {
    "growth": [
        ("{name} announces record asset growth, surpassing ${assets_m}M milestone",
         82, "cuinsight.com",
         "https://www.cuinsight.com/press-release/{slug}-record-growth"),
        ("{name} appoints new Chief Digital Officer to accelerate digital banking roadmap",
         88, "cutoday.info",
         "https://www.cutoday.info/Fresh-Today/{slug}-cdo-appointment"),
        ("{name} reports {members_k}K member milestone, fastest-growing CU in {state}",
         79, "cuinsight.com",
         "https://www.cuinsight.com/press-release/{slug}-member-growth"),
        ("{name} completes merger with regional credit union, expanding {state} footprint",
         85, "American Banker",
         "https://www.americanbanker.com/creditunions/{slug}-merger"),
        ("{name} launches fintech partnership for embedded lending at point-of-sale",
         80, "cutimes.com",
         "https://www.cutimes.com/2025/03/{slug}-fintech-partnership"),
        ("{name} opens {city} flagship branch, investing $12M in member experience",
         72, "cutoday.info",
         "https://www.cutoday.info/Fresh-Today/{slug}-branch-opening"),
        ("{name} CTO joins CUNA Technology Council advisory board",
         74, "cuinsight.com",
         "https://www.cuinsight.com/{slug}-cto-cuna-council"),
        ("{name} secures CDFI certification, unlocking $8M federal investment",
         77, "NCUA Press",
         "https://ncua.gov/press-releases/2025/{slug}-cdfi"),
    ],
    "operational_gap": [
        ("{name} selects new digital banking platform to replace {core_short} legacy stack",
         90, "cutimes.com",
         "https://www.cutimes.com/2025/02/{slug}-core-modernization"),
        ("{name} launches mobile app overhaul targeting Gen-Z members in {state}",
         78, "finovate.com",
         "https://finovate.com/fintech/2025/{slug}-mobile-launch"),
        ("{name} issues RFP for real-time payment rails integration",
         86, "paymentsdive.com",
         "https://www.paymentsdive.com/news/{slug}-rtp-rfp"),
        ("{name} announces core conversion timeline — evaluating Corelation, Fiserv DNA",
         92, "cutoday.info",
         "https://www.cutoday.info/Fresh-Today/{slug}-core-rfp"),
        ("{name} reports 34% increase in digital account openings, straining legacy systems",
         81, "BAI Banking Strategies",
         "https://www.bai.org/banking-strategies/{slug}-digital-growth"),
        ("{name} CIO departing after 8 years — technology strategy review underway",
         83, "cuinsight.com",
         "https://www.cuinsight.com/{slug}-cio-departure"),
        ("{name} pilots AI-powered loan decisioning with regional fintech partner",
         76, "finovate.com",
         "https://finovate.com/fintech/2025/{slug}-ai-lending"),
    ],
    "regulatory_risk": [
        ("{name} completes FedNow go-live, first in {state} to offer instant payments",
         84, "paymentsdive.com",
         "https://www.paymentsdive.com/news/{slug}-fednow-golive"),
        ("NCUA issues {name} Matters Requiring Attention letter — BSA program gaps cited",
         91, "NCUA Enforcement",
         "https://ncua.gov/regulation-supervision/regulatory-alerts/{slug}-mra"),
        ("{name} Board approves $4.2M cybersecurity investment following NCUA exam findings",
         88, "cutoday.info",
         "https://www.cutoday.info/Fresh-Today/{slug}-cybersecurity-spend"),
        ("{name} prepares for Section 1033 open banking compliance — API build underway",
         82, "americanbanker.com",
         "https://www.americanbanker.com/creditunions/{slug}-1033-prep"),
        ("CFPB names {name} in complaint trend — members cite slow digital transfer speeds",
         86, "consumerfinance.gov",
         "https://www.consumerfinance.gov/complaint-database/{slug}"),
        ("{name} signs FedNow service agreement, targets Q3 2025 go-live",
         80, "paymentsdive.com",
         "https://www.paymentsdive.com/news/{slug}-fednow-signup"),
        ("{name} expands LICU programs following NCUA low-income designation renewal",
         75, "NCUA Press",
         "https://ncua.gov/press-releases/2025/{slug}-licu-renewal"),
    ],
    "pain_point": [
        ("{name} mobile banking app suffers 6-hour outage during peak deposit window",
         89, "cutimes.com",
         "https://www.cutimes.com/2025/01/{slug}-app-outage"),
        ("{name} members report ACH delays — back-office queue backlog under investigation",
         84, "cutoday.info",
         "https://www.cutoday.info/Fresh-Today/{slug}-ach-delays"),
        ("{name} discloses third-party data incident affecting 18K member records",
         93, "databreaches.net",
         "https://www.databreaches.net/2025/{slug}-data-incident"),
        ("{name} reports $1.1M in card fraud losses in Q1 — above peer median",
         87, "cuinsight.com",
         "https://www.cuinsight.com/{slug}-fraud-losses"),
        ("{name} faces class-action suit over overdraft fee practices",
         85, "americanbanker.com",
         "https://www.americanbanker.com/creditunions/{slug}-overdraft-lawsuit"),
    ],
}


def pick_signals(co: "Company", rng: random.Random) -> list[dict]:
    """Pick 2-4 relevant news signals for a CU based on its profile."""
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
    slug = name.lower().replace(" ","").replace("'","")[:20]

    ctx = dict(
        name=name, city=city, state=state,
        core_short=core_short, assets_m=assets_m,
        assets_b=assets_b, members_k=members_k, slug=slug,
    )

    # Weighted pool — bias toward types that match the CU's profile
    pool: list[tuple[str, tuple]] = []

    # Everyone gets a growth signal
    for t in TEMPLATES["growth"]:
        pool.append(("growth", t))

    # Operational gap — weight by score (high score = likely legacy)
    if score >= 70:
        for t in TEMPLATES["operational_gap"]:
            pool.append(("operational_gap", t))
            pool.append(("operational_gap", t))  # double weight

    # Regulatory signals
    for t in TEMPLATES["regulatory_risk"]:
        pool.append(("regulatory_risk", t))
    if licu:  # LICU CUs get extra regulatory signals
        pool.append(("regulatory_risk", TEMPLATES["regulatory_risk"][-1]))

    # Pain point — smaller CUs more likely to have pain signal
    if assets < 5_000_000_000:
        for t in TEMPLATES["pain_point"]:
            pool.append(("pain_point", t))

    # Shuffle deterministically
    rng.shuffle(pool)

    # Deduplicate by template label, pick 2-4
    seen_labels = set()
    chosen = []
    for sig_type, (label_tmpl, sev_base, src_label, src_url_tmpl) in pool:
        try:
            label = "News: " + label_tmpl.format(**ctx)
            if label in seen_labels:
                continue
            seen_labels.add(label)
        except KeyError:
            continue

        # Severity: jitter ±8 based on score
        sev = min(95, max(65, sev_base + rng.randint(-5, 8) + (score - 75) // 10))

        src_url = src_url_tmpl.format(**ctx)

        chosen.append({
            "signal_type":  sig_type,
            "signal_label": label,
            "severity":     sev,
            "source":       f"news_{src_label.split('.')[0].lower().replace(' ','_')[:20]}",
            "source_url":   src_url,
            "source_label": src_label,
        })

        target = 3 if assets >= 1_000_000_000 else (2 if assets >= 250_000_000 else 2)
        if len(chosen) >= target:
            break

    return chosen


def main():
    print(f"\n{B}{C}FintelliPro — News Signal Seeder{W}")

    init_db()
    db = SessionLocal()

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
        # Skip if news signals already exist for this CU
        existing_news = db.query(Signal).filter(
            Signal.company_id == co.id,
            Signal.source.like("news_%"),
        ).count()
        if existing_news > 0:
            info(f"{co.name}: {existing_news} news signals already exist — skipping")
            continue

        signals = pick_signals(co, rng)
        added = 0
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
            added += 1

        total_added += added
        ok(f"{co.name:<44} +{added} signals")

    db.commit()

    # Summary
    total_sigs  = db.query(Signal).count()
    news_sigs   = db.query(Signal).filter(Signal.source.like("news_%")).count()

    print(f"\n{B}{C}Done!{W}\n  {'─'*54}")
    print(f"  News signals added:  {total_added}")
    print(f"  Total signals in DB: {total_sigs}")
    print(f"  News signals total:  {news_sigs}")
    print(f"\n  {G}✅ Refresh the dashboard to see news signals.{W}\n")
    db.close()


if __name__ == "__main__":
    main()
