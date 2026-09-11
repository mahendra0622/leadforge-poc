"""
FintelliPro — Community Banks Seed
====================================
Fetches 50 community banks from the FDIC BankFind API, enriches with
financials (NIM, Tier 1 capital, ROA/ROE), generates bank-specific signals,
and seeds Apollo-style decision-maker contacts.

Selection criteria:
  - FDIC-insured, active, US-chartered
  - Assets $500M–$10B (community bank range)
  - Geographic diversity (max 4 per state)
  - Ranked by composite score: asset size + ROA + loan activity

Run:
    python seed_community_banks.py
"""
import sys, os, uuid, re, urllib.request, urllib.parse, json, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy.orm.attributes import flag_modified
from app.db.database import SessionLocal, init_db
from app.models import Company, Signal, Contact

G="\033[92m"; Y="\033[93m"; C="\033[96m"; R="\033[91m"; W="\033[0m"; B="\033[1m"

TARGET = 50
MAX_PER_STATE = 4
FDIC_BASE = "https://banks.data.fdic.gov/api"

# ── Core processor → digital maturity ────────────────────────────────────────

CORE_MATURITY = {
    # Modern / cloud-native
    "finxact": 5, "mambu": 5, "thought machine": 5, "temenos": 5,
    "nymbus": 5, "q2": 4, "alkami": 4, "ncino": 4,
    # Mid-tier
    "fiserv": 3, "finastra": 3, "meridian link": 3, "corelation": 3,
    # Legacy
    "jack henry": 2, "silverlake": 2, "bankers edge": 2, "metavante": 2,
    "open solutions": 2, "fis": 2, "dna": 2,
}

def core_from_name(bank_name: str) -> tuple[str, int]:
    """Heuristically assign core processor + maturity from bank name/size."""
    name = bank_name.lower()
    # Well-known banks with known cores
    known = {
        "s&t bank":            ("Jack Henry SilverLake", 2),
        "tri counties bank":   ("Jack Henry", 2),
        "byline bank":         ("Fiserv", 3),
        "glacier bank":        ("Jack Henry", 2),
        "heartland bank":      ("Jack Henry", 2),
        "pinnacle bank":       ("FIS", 2),
        "seacoast bank":       ("Fiserv", 3),
        "veritex":             ("nCino", 4),
        "crossfirst":          ("Nymbus", 5),
    }
    for k, v in known.items():
        if k in name:
            return v
    # Default heuristic by name patterns
    if any(x in name for x in ["community", "peoples", "heritage", "first", "farmers"]):
        return ("Jack Henry", 2)
    if any(x in name for x in ["commerce", "commerce", "enterprise"]):
        return ("Fiserv", 3)
    return ("Jack Henry", 2)


# ── FDIC helpers ─────────────────────────────────────────────────────────────

def fdic_get(endpoint: str, params: dict) -> dict:
    url = f"{FDIC_BASE}/{endpoint}?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read())


def fetch_institutions(limit: int = 300) -> list[dict]:
    """Fetch community banks $500M–$10B assets, sorted by assets."""
    data = fdic_get("institutions", {
        "filters": "ACTIVE:1 AND ASSET:[500000 TO 10000000]",
        "fields": "CERT,NAME,CITY,STALP,STNAME,ASSET,DEP,LNLSNET,EQ,NETINC,ROA,ROAE,REPDTE,WEBADDR,NAMEHCR",
        "sort_by": "ASSET",
        "sort_order": "DESC",
        "limit": limit,
        "offset": 0,
    })
    return [b["data"] for b in data.get("data", [])]


def fetch_financials(cert: int) -> dict:
    """Fetch latest quarterly financials for one bank."""
    data = fdic_get("financials", {
        "filters": f"CERT:{cert}",
        "fields": "CERT,REPDTE,ASSET,ROA,ROAE,NIMY,NIM,NETINC,INTINC,NONII,RBCT1,RBCRWAJ,LNLSNET,DEP,EQ,LNLSGR,INTEXPY",
        "sort_by": "REPDTE",
        "sort_order": "DESC",
        "limit": 1,
    })
    if data.get("data"):
        return data["data"][0]["data"]
    return {}


# ── Selection scoring ─────────────────────────────────────────────────────────

def composite_score(b: dict) -> float:
    asset  = b.get("ASSET", 0) or 0
    roa    = b.get("ROA",   0) or 0
    loans  = b.get("LNLSNET", 0) or 0
    deps   = b.get("DEP", 1) or 1
    # Normalise to 0-1 within community bank range
    asset_n  = min(asset / 10_000_000, 1.0)
    roa_n    = min(max(roa, 0) / 2.0, 1.0)
    ldr_n    = min(loans / deps, 1.2) / 1.2
    return asset_n * 0.5 + roa_n * 0.3 + ldr_n * 0.2


def select_50(institutions: list[dict]) -> list[dict]:
    """Pick 50 with geographic diversity, ranked by composite score."""
    scored = sorted(institutions, key=composite_score, reverse=True)
    state_count: dict[str, int] = {}
    selected = []
    for b in scored:
        state = b.get("STALP", "")
        if state_count.get(state, 0) >= MAX_PER_STATE:
            continue
        state_count[state] = state_count.get(state, 0) + 1
        selected.append(b)
        if len(selected) >= TARGET:
            break
    return selected


# ── Signal generation ─────────────────────────────────────────────────────────

def build_bank_signals(name: str, fin: dict, rd: dict) -> list[dict]:
    sigs = []
    asset  = (fin.get("ASSET")  or rd.get("total_assets_k", 0)) * 1000
    roa    = fin.get("ROA")   or 0
    roe    = fin.get("ROAE")  or 0
    nimy   = fin.get("NIMY")  or 0   # NIM as %
    t1_rat = fin.get("RBCRWAJ") or 0  # Tier 1 capital ratio %
    loans  = (fin.get("LNLSNET") or 0) * 1000
    deps   = (fin.get("DEP")     or 0) * 1000
    netinc = (fin.get("NETINC")  or 0) * 1000
    ldr    = round(loans / deps * 100, 1) if deps else 0

    # NIM signals
    if nimy and nimy < 2.8:
        sigs.append({"type": "pain_point", "sev": 85,
                     "label": f"NIM compressed at {nimy:.2f}% — cost reduction and fee income diversification urgency",
                     "source": "fdic_financials"})
    elif nimy and nimy < 3.3:
        sigs.append({"type": "pain_point", "sev": 72,
                     "label": f"NIM under pressure at {nimy:.2f}% — efficiency tech and digital deposits opportunity",
                     "source": "fdic_financials"})
    elif nimy and nimy > 4.5:
        sigs.append({"type": "growth", "sev": 74,
                     "label": f"Strong NIM at {nimy:.2f}% — profitable bank with budget for technology investment",
                     "source": "fdic_financials"})

    # ROA signals
    if roa and roa < 0.5:
        sigs.append({"type": "pain_point", "sev": 82,
                     "label": f"ROA at {roa:.2f}% — below peer average, operational efficiency is top priority",
                     "source": "fdic_financials"})
    elif roa and roa > 1.2:
        sigs.append({"type": "growth", "sev": 76,
                     "label": f"High ROA {roa:.2f}% — outperforming peers, actively investing in growth capabilities",
                     "source": "fdic_financials"})

    # Capital position
    if t1_rat and t1_rat > 14:
        sigs.append({"type": "growth", "sev": 73,
                     "label": f"Well-capitalised at {t1_rat:.1f}% Tier 1 — technology spend not capital-constrained",
                     "source": "fdic_financials"})
    elif t1_rat and t1_rat < 9:
        sigs.append({"type": "pain_point", "sev": 80,
                     "label": f"Tier 1 capital ratio {t1_rat:.1f}% — constrained; lead with cost-saving ROI",
                     "source": "fdic_financials"})

    # Loan-to-deposit
    if ldr > 90:
        sigs.append({"type": "growth", "sev": 78,
                     "label": f"Loan-to-deposit ratio {ldr:.0f}% — active lender, needs origination and underwriting tech",
                     "source": "fdic_financials"})
    elif ldr < 55:
        sigs.append({"type": "operational_gap", "sev": 75,
                     "label": f"Low LDR {ldr:.0f}% — excess deposits signal need for digital acquisition and engagement tools",
                     "source": "fdic_financials"})

    # Asset size signal
    if asset >= 5_000_000_000:
        sigs.append({"type": "growth", "sev": 80,
                     "label": f"Large community bank (${asset/1e9:.1f}B) — enterprise-grade technology budget",
                     "source": "fdic_financials"})
    elif asset >= 1_000_000_000:
        sigs.append({"type": "growth", "sev": 70,
                     "label": f"$1B+ community bank — actively modernising to compete with regional banks",
                     "source": "fdic_financials"})

    # Core modernisation urgency
    core = rd.get("core_processor", "")
    maturity = rd.get("digital_maturity_score", 2)
    if maturity <= 2 and asset >= 1_000_000_000:
        sigs.append({"type": "operational_gap", "sev": 88,
                     "label": f"Legacy core ({core}) at $1B+ scale — core modernisation or middleware layer is inevitable",
                     "source": "fdic_financials"})
    elif maturity <= 2:
        sigs.append({"type": "operational_gap", "sev": 78,
                     "label": f"Legacy core processor ({core}) — digital banking layer and API modernisation opportunity",
                     "source": "fdic_financials"})

    return sigs


# ── Contact seeding ───────────────────────────────────────────────────────────

DECISION_MAKER_TITLES = [
    ("CEO",                   True),
    ("Chief Digital Officer", True),
    ("Chief Technology Officer", True),
    ("SVP Digital Banking",   False),
    ("VP Technology",         False),
]

FIRST_NAMES = ["James","Michael","Robert","David","Jennifer","Sarah","Lisa","Mark",
               "John","Thomas","Karen","Nancy","Patricia","William","Richard","Susan"]
LAST_NAMES  = ["Johnson","Williams","Brown","Davis","Miller","Wilson","Moore","Taylor",
               "Anderson","Thomas","Jackson","White","Harris","Martin","Thompson","Garcia"]

import random
random.seed(42)

def make_contact(company_id: str, bank_name: str, title: str, is_dm: bool) -> Contact:
    fn = random.choice(FIRST_NAMES)
    ln = random.choice(LAST_NAMES)
    slug = bank_name.lower().replace(" ", "").replace("&","and")[:15]
    email = f"{fn.lower()}.{ln.lower()}@{slug}.com"
    li_slug = f"{fn.lower()}-{ln.lower()}-{random.randint(10,99)}"
    return Contact(
        id              = str(uuid.uuid4()),
        company_id      = company_id,
        first_name      = fn,
        last_name       = ln,
        title           = title,
        email           = email,
        email_status    = "likely_valid",
        email_confidence= random.randint(72, 95),
        linkedin_url    = f"https://www.linkedin.com/in/{li_slug}",
        is_decision_maker = is_dm,
    )


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print(f"\n{B}{C}FintelliPro — Community Banks Seed{W}")

    print(f"\n  {Y}Fetching institutions from FDIC API...{W}")
    institutions = fetch_institutions(limit=300)
    print(f"  Fetched {len(institutions)} banks in $500M–$10B range")

    selected = select_50(institutions)
    states = sorted({b.get("STALP") for b in selected})
    print(f"  Selected {len(selected)} banks across {len(states)} states: {', '.join(states)}\n")

    init_db()
    db = SessionLocal()

    # Remove existing community bank data
    existing = db.query(Company).filter_by(industry="community_banks").all()
    if existing:
        print(f"  {Y}Removing {len(existing)} existing community bank records...{W}")
        for co in existing:
            db.query(Signal).filter_by(company_id=co.id).delete(synchronize_session=False)
            db.query(Contact).filter_by(company_id=co.id).delete(synchronize_session=False)
            db.delete(co)
        db.commit()

    print(f"  {C}Seeding {len(selected)} community banks...{W}\n")
    total_signals = 0
    total_contacts = 0

    for i, b in enumerate(selected):
        cert  = b.get("CERT")
        name  = b.get("NAME", "")
        city  = b.get("CITY", "")
        state = b.get("STALP", "")
        asset_k = b.get("ASSET", 0) or 0  # in thousands

        # Fetch detailed financials
        time.sleep(0.1)  # be polite to FDIC API
        fin = fetch_financials(cert)

        roa   = fin.get("ROA")   or b.get("ROA")  or 0
        roe   = fin.get("ROAE")  or b.get("ROAE") or 0
        nimy  = fin.get("NIMY")  or 0
        t1    = fin.get("RBCRWAJ") or 0
        loans = fin.get("LNLSNET") or b.get("LNLSNET") or 0
        deps  = fin.get("DEP")     or b.get("DEP")     or 0
        netinc= fin.get("NETINC")  or b.get("NETINC")  or 0
        eq    = fin.get("EQ")      or b.get("EQ")      or 0
        ldr   = round(loans / deps * 100, 1) if deps else 0

        core, maturity = core_from_name(name)

        # Opportunity score
        opp = 50
        if nimy  and nimy  < 3.0:  opp += 15
        if roa   and roa   < 0.8:  opp += 10
        if t1    and t1    > 12:   opp += 8
        if ldr   > 85:             opp += 10
        if maturity <= 2:          opp += 15
        if asset_k >= 5_000_000:   opp += 12
        opp = min(opp, 100)

        # Financial health score (0-100)
        fh = 50
        if roa  >= 1.0: fh += 20
        elif roa >= 0.6: fh += 10
        elif roa < 0.3:  fh -= 15
        if t1 >= 12: fh += 15
        elif t1 < 8: fh -= 12
        if nimy >= 3.5: fh += 15
        elif nimy < 2.8: fh -= 10
        fh = max(0, min(100, fh))

        # Modernisation urgency score (0-100)
        mu = 30
        mu += (5 - maturity) * 15
        if ldr > 85: mu += 15
        if roa < 0.5: mu += 10
        if asset_k >= 1_000_000: mu += 10
        mu = max(0, min(100, mu))

        # Growth momentum score (0-100)
        gm = 40
        if asset_k >= 5_000_000: gm += 25
        elif asset_k >= 1_000_000: gm += 15
        if ldr >= 80: gm += 15
        if roa >= 1.0: gm += 12
        if nimy >= 4.0: gm += 8
        gm = max(0, min(100, gm))

        website = (b.get("WEBADDR") or "").strip()
        if website and not website.startswith("http"):
            website = "https://" + website

        rd = {
            "fdic_cert":           cert,
            "holding_company":     b.get("NAMEHCR", ""),
            "total_assets_k":      asset_k,        # thousands
            "total_deposits_k":    deps,
            "net_loans_k":         loans,
            "equity_k":            int(eq) if eq else 0,
            "net_income_k":        netinc,
            "roa":                 round(roa,  2),
            "roe":                 round(roe,  2),
            "nim":                 round(nimy, 2),   # NIM %
            "tier1_capital_ratio": round(t1,   2),
            "loan_to_deposit":     ldr,
            "core_processor":      core,
            "digital_maturity_score": maturity,
            "report_date":         fin.get("REPDTE") or b.get("REPDTE", ""),
            "financial_health_score":   fh,
            "growth_momentum_score":    gm,
            "modernization_urgency":    mu,
            "is_rtp_participant":   None,
            "is_fednow_participant": None,
        }

        co = Company(
            id              = str(uuid.uuid4()),
            name            = name,
            website         = website,
            industry        = "community_banks",
            hq_city         = city,
            hq_state        = state,
            revenue_est     = asset_k * 1000,        # store in dollars
            digital_maturity= maturity,
            opportunity_score = opp,
            outreach_status = "new",
            tech_stack      = [core],
            regulatory_src  = "FDIC",
            regulatory_id   = str(cert),
            regulatory_data = rd,
        )
        db.add(co)
        db.flush()  # get co.id

        # Signals
        sigs = build_bank_signals(name, fin, rd)
        for s in sigs:
            db.add(Signal(
                id=str(uuid.uuid4()), company_id=co.id,
                signal_type=s["type"], signal_label=s["label"],
                severity=s["sev"], source=s["source"], is_active=True,
            ))
        total_signals += len(sigs)

        # Contacts (2-3 per bank)
        n_contacts = 2 if i % 3 == 0 else 3
        for title, is_dm in DECISION_MAKER_TITLES[:n_contacts]:
            db.add(make_contact(co.id, name, title, is_dm))
        total_contacts += n_contacts

        asset_b = asset_k / 1_000_000
        nim_str = f"{nimy:.2f}%" if nimy else "—"
        print(f"  {G}✓{W} {name[:42]:<42} ${asset_b:.1f}B  NIM:{nim_str:>6}  ROA:{roa:.2f}%  [{state}]")

    db.commit()

    print(f"\n{B}{C}Summary{W}")
    print(f"  ─────────────────────────────────────")
    print(f"  Banks seeded:    {len(selected)}")
    print(f"  Signals:         {total_signals}")
    print(f"  Contacts:        {total_contacts}")
    total_co = db.query(Company).count()
    print(f"  Total companies: {total_co}")
    print(f"\n  {G}✅ Community banks seeded.{W}\n")
    db.close()


if __name__ == "__main__":
    main()
