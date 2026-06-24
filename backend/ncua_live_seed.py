"""
FintelliPro — NCUA Real Data Seed
===================================
Wipes dummy data and loads 50 REAL credit unions from NCUA 5300 Call Report
public data (Q3 2024). Charter numbers, assets, members are actual NCUA figures.

Run from backend/ with venv active:
    python ncua_live_seed.py
"""
import sys, os, uuid as _uuid
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.db.database import SessionLocal, init_db
from app.models import Company, Contact, Signal, User, AIMessage, Campaign
from app.services.regulatory.cuna_ncua import CUNAIntelligenceClient, LEGACY_PROCESSORS
from app.services.regulatory.ncua_real_data import REAL_NCUA_CUS

TARGET = 50

G="\033[92m"; Y="\033[93m"; C="\033[96m"; W="\033[0m"; B="\033[1m"
def ok(s):   print(f"  {G}✓{W} {s}")
def warn(s): print(f"  {Y}⚠{W}  {s}")
def hdr(s):  print(f"\n{B}{C}{s}{W}\n  {'─'*52}")


def maturity_from_core(core: str) -> int:
    if not core: return 2
    c = core.lower()
    if any(x in c for x in ["mambu","nymbus","q2","alkami","narni"]): return 5
    if any(x in c for x in ["corelation","keystone","open solutions"]): return 4
    if any(x in c for x in ["fiserv","dna","portico","gold"]): return 3
    return 2  # jack henry / symitar / sharetec / episys = legacy


def build_signals(raw: dict, cuna) -> list:
    assets  = int(raw.get("TotalAssets",  0) or 0)
    shares  = int(raw.get("TotalShares",  0) or 0)
    loans   = int(raw.get("TotalLoans",   0) or 0)
    members = int(raw.get("NumberOfMembers", 0) or 0)
    nw      = int(raw.get("TotalNetWorth", 0) or 0)
    core    = raw.get("CoreProcessor", "") or ""
    licu    = bool(raw.get("LowIncomeDesignation", False))
    branches= int(raw.get("SiteCount", 0) or 0)

    nwr = round(nw / assets * 100, 1) if assets else 0
    lts = round(loans / shares * 100, 1) if shares else 0
    sigs = []

    # Asset tier
    if assets >= 1_000_000_000:
        sigs.append(("growth", f"Enterprise CU — ${assets/1e9:.1f}B assets (Tier 1)", 90, "ncua_5300"))
    elif assets >= 500_000_000:
        sigs.append(("growth", f"Large CU — ${assets/1e6:.0f}M assets (Tier 1)", 82, "ncua_5300"))
    elif assets >= 100_000_000:
        sigs.append(("growth", f"Mid-market CU — ${assets/1e6:.0f}M assets (Tier 2)", 72, "ncua_5300"))

    # Members
    if members >= 500_000:
        sigs.append(("growth", f"Massive member base: {members:,} members", 88, "ncua_5300"))
    elif members >= 100_000:
        sigs.append(("growth", f"Large member base: {members:,} members", 78, "ncua_5300"))
    elif members >= 20_000:
        sigs.append(("growth", f"Growing membership: {members:,} members", 62, "ncua_5300"))

    # Capital
    if nwr >= 10:
        sigs.append(("growth", f"Strongly capitalised: {nwr}% NWR — tech budget available", 76, "ncua_5300"))
    elif nwr >= 7:
        sigs.append(("growth", f"Well-capitalised: {nwr}% NWR", 62, "ncua_5300"))
    elif 0 < nwr < 6:
        sigs.append(("pain_point", f"Capital pressure: {nwr}% NWR — lead with cost reduction", 68, "ncua_5300"))

    # Loan-to-share
    if lts >= 85:
        sigs.append(("growth", f"High loan demand: {lts}% LTS — faster digital origination needed", 78, "ncua_5300"))
    elif 0 < lts < 50:
        sigs.append(("operational_gap", f"Low loan utilisation: {lts}% LTS — digital origination gap", 70, "ncua_5300"))

    # Core processor
    if core and any(lp.lower() in core.lower() for lp in LEGACY_PROCESSORS):
        sigs.append(("operational_gap", f"Legacy core: {core} — API overlay opportunity", 86, "ncua_profile"))
    elif not core:
        sigs.append(("operational_gap", "Core processor undisclosed — likely legacy", 60, "ncua_profile"))

    # LICU
    if licu:
        sigs.append(("regulatory_risk", "NCUA Low-Income Designated (LICU) — compliance investment mandate", 72, "ncua_profile"))

    # Multi-branch
    if branches >= 15:
        sigs.append(("operational_gap", f"Large branch network ({branches} locations) — orchestration complexity", 65, "ncua_profile"))

    # CUNA top 2
    for p in sorted(cuna.get_industry_priorities(), key=lambda x: x["urgency"], reverse=True)[:2]:
        sigs.append((p["signal_type"], f"CUNA Industry Signal: {p['priority']}", p["urgency"], "cuna_intelligence"))

    return sigs


def calc_score(raw: dict, maturity: int, signals: list) -> int:
    pain   = [s[2] for s in signals if s[0] in ("pain_point", "operational_gap")]
    growth = [s[2] for s in signals if s[0] == "growth"]
    pa = sum(pain)   / len(pain)   if pain   else 40
    ga = sum(growth) / len(growth) if growth else 30
    gap  = (6 - maturity) * 18
    base = gap*0.30 + pa*0.25 + ga*0.20 + 85*0.15 + 80*0.10
    return min(100, int(base * 1.15))


def main():
    print(f"\n{B}{C}FintelliPro — NCUA Real Data Seed{W}")
    print(f"  Loading {TARGET} real credit unions from NCUA 5300 Call Report (Q3 2024)\n")

    init_db()
    db   = SessionLocal()
    cuna = CUNAIntelligenceClient()

    # ── Step 1: Wipe ───────────────────────────────────────────
    hdr("Step 1 — Wiping existing data")
    db.query(Signal).delete()
    db.query(AIMessage).delete()
    db.query(Contact).delete()
    db.query(Company).delete()
    db.commit()
    ok("All companies / contacts / signals deleted")
    ok("Demo user preserved")

    # ── Step 2: Load real dataset ──────────────────────────────
    hdr("Step 2 — Loading NCUA 5300 real data")
    raw_list = sorted(
        REAL_NCUA_CUS[:TARGET],
        key=lambda r: int(r.get("TotalAssets", 0) or 0),
        reverse=True
    )
    ok(f"Loaded {len(raw_list)} CUs from ncua_real_data.py")
    ok("Source: NCUA 5300 Call Report Q3 2024 · Actual charter numbers")

    # ── Step 3: Insert ─────────────────────────────────────────
    hdr(f"Step 3 — Inserting {len(raw_list)} CUs into database")
    inserted = 0

    for raw in raw_list:
        assets  = int(raw.get("TotalAssets",  0) or 0)
        shares  = int(raw.get("TotalShares",  0) or 0)
        loans   = int(raw.get("TotalLoans",   0) or 0)
        members = int(raw.get("NumberOfMembers", 0) or 0)
        nw      = int(raw.get("TotalNetWorth", 0) or 0)
        core    = raw.get("CoreProcessor", "") or ""
        charter = str(raw.get("CharterNumber", ""))
        name    = raw.get("CUName", "")
        city    = raw.get("City", "")
        state   = raw.get("State", "")
        licu    = bool(raw.get("LowIncomeDesignation", False))
        branches= int(raw.get("SiteCount", 0) or 0)
        website = raw.get("WebSiteUrl", "")

        nwr = round(nw / assets * 100, 2) if assets else 0
        lts = round(loans / shares * 100, 2) if shares else 0

        if assets >= 1_000_000_000:   tier = "Large (>$1B)"
        elif assets >= 250_000_000:   tier = "Mid ($250M–$1B)"
        else:                          tier = "Community ($50M–$250M)"

        maturity = maturity_from_core(core)
        signals  = build_signals(raw, cuna)
        opp      = calc_score(raw, maturity, signals)

        co_id = str(_uuid.uuid4())
        db.add(Company(
            id             = co_id,
            apollo_org_id  = f"ncua_{charter}",
            name           = name,
            website        = website,
            industry       = "credit_unions",
            hq_city        = city,
            hq_state       = state,
            hq_country     = "US",
            revenue_est    = assets,
            employee_count = max(10, members // 80) if members else None,
            tech_stack     = [core] if core else [],
            regulatory_src = "NCUA",
            regulatory_id  = charter,
            regulatory_data = {
                "charter_number":       charter,
                "charter_type":         raw.get("CharterTypeName", ""),
                "field_of_membership":  raw.get("TypeOfMembership", ""),
                "total_assets":         assets,
                "total_shares":         shares,
                "total_loans":          loans,
                "total_members":        members,
                "net_worth":            nw,
                "net_worth_ratio":      nwr,
                "loan_to_share_ratio":  lts,
                "num_branches":         branches,
                "core_processor":       core,
                "asset_tier":           tier,
                "is_licu":              licu,
                "data_as_of":           raw.get("CycleDate", "2024-Q3"),
            },
            digital_maturity  = maturity,
            opportunity_score = opp,
            outreach_status   = "new",
        ))
        db.flush()

        for (sig_type, label, severity, source) in signals:
            db.add(Signal(
                id=str(_uuid.uuid4()), company_id=co_id,
                signal_type=sig_type, signal_label=label,
                severity=severity, source=source, is_active=True,
            ))

        inserted += 1
        print(f"  {G}✓{W} [{inserted:02d}] {name:<44} ${assets/1e6:>8,.0f}M  score:{opp}")

    db.commit()

    # ── Summary ────────────────────────────────────────────────
    all_cos = db.query(Company).all()
    total_assets  = sum(c.revenue_est or 0 for c in all_cos)
    total_members = sum((c.regulatory_data or {}).get("total_members", 0) for c in all_cos)
    total_signals = db.query(Signal).count()
    avg_score     = sum(c.opportunity_score or 0 for c in all_cos) / len(all_cos) if all_cos else 0
    licu_count    = sum(1 for c in all_cos if (c.regulatory_data or {}).get("is_licu"))
    legacy_count  = sum(1 for c in all_cos if c.tech_stack and
                        any(lp.lower() in (c.tech_stack[0] or "").lower() for lp in LEGACY_PROCESSORS))

    print(f"\n{B}{C}Summary{W}\n  {'─'*52}")
    print(f"  {B}CUs loaded:        {inserted}{W}")
    print(f"  Combined assets:   ${total_assets/1e9:.1f}B")
    print(f"  Total members:     {total_members:,}")
    print(f"  Total signals:     {total_signals}")
    print(f"  Avg opp. score:    {avg_score:.0f}/100")
    print(f"  Legacy core:       {legacy_count} CUs  ({legacy_count/inserted*100:.0f}%)")
    print(f"  LICU designated:   {licu_count} CUs")
    print(f"\n  {G}Login: demo@fintellipro.com / demo1234{W}")
    print(f"  Open:  http://localhost:3000")
    print(f"\n  {G}✅ Done — {inserted} real NCUA CUs in your database.{W}\n")
    db.close()


if __name__ == "__main__":
    main()
