"""
FintelliPro — Financial Metrics Enricher
==========================================
Computes ROA, ROE, financial health score, growth momentum score,
and modernization urgency from NCUA data already in the DB.
Adds new financial signals. Non-destructive — patches regulatory_data only.

Run:
    python compute_financial_metrics.py
"""
import sys, os, uuid
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.db.database import SessionLocal, init_db
from app.models import Company, Signal
from sqlalchemy.orm.attributes import flag_modified
from app.services.regulatory.ncua_real_data import REAL_NCUA_CUS

G="\033[92m"; Y="\033[93m"; C="\033[96m"; R="\033[91m"; W="\033[0m"; B="\033[1m"
def ok(s):   print(f"  {G}✓{W} {s}")
def warn(s): print(f"  {Y}⚠{W}  {s}")
def hdr(s):  print(f"\n{B}{C}{s}{W}\n  {'─'*58}")


# ── Build name → net_income lookup from static data ─────────────
NET_INCOME_MAP = {
    r["CUName"]: int(r.get("NetIncome", 0) or 0)
    for r in REAL_NCUA_CUS
}


def compute_metrics(rd: dict, net_income: int) -> dict:
    """Compute all financial ratios from regulatory_data fields."""
    assets  = int(rd.get("total_assets",  0) or 0)
    shares  = int(rd.get("total_shares",  0) or 0)
    loans   = int(rd.get("total_loans",   0) or 0)
    nw      = int(rd.get("net_worth",     0) or 0)
    members = int(rd.get("total_members", 0) or 0)

    roa = round(net_income / assets * 100, 2) if assets else 0
    roe = round(net_income / nw * 100,     2) if nw     else 0
    nwr = round(nw / assets * 100,         2) if assets else 0
    lts = round(loans / shares * 100,      2) if shares else 0
    assets_per_member = round(assets / members)            if members else 0
    loans_per_member  = round(loans  / members)            if members else 0
    net_income_per_member = round(net_income / members, 2) if members else 0

    return {
        "net_income":             net_income,
        "roa":                    roa,          # Return on Assets %
        "roe":                    roe,          # Return on Equity %
        "net_worth_ratio":        nwr,
        "loan_to_share_ratio":    lts,
        "assets_per_member":      assets_per_member,
        "loans_per_member":       loans_per_member,
        "net_income_per_member":  net_income_per_member,
    }


def financial_health_score(m: dict) -> int:
    """
    Composite 0-100 score for financial health.
    High NWR + strong ROA + profitable = healthy budget for technology.
    """
    score = 50  # baseline

    nwr = m.get("net_worth_ratio", 0)
    if nwr >= 12:    score += 25
    elif nwr >= 10:  score += 18
    elif nwr >= 7:   score += 8
    elif nwr < 6:    score -= 15

    roa = m.get("roa", 0)
    if roa >= 1.0:   score += 20
    elif roa >= 0.6: score += 12
    elif roa >= 0.3: score += 4
    elif roa < 0:    score -= 20
    elif roa < 0.3:  score -= 8

    lts = m.get("loan_to_share_ratio", 0)
    if lts >= 80:    score += 10
    elif lts >= 60:  score += 5
    elif lts < 40:   score -= 8

    return max(0, min(100, score))


def growth_momentum_score(m: dict, assets: int, members: int) -> int:
    """
    Composite 0-100 score for growth momentum.
    Large + growing + high loan demand = actively investing.
    """
    score = 40

    if assets >= 5_000_000_000:  score += 30
    elif assets >= 1_000_000_000: score += 22
    elif assets >= 500_000_000:   score += 14
    elif assets >= 100_000_000:   score += 6

    if members >= 500_000:  score += 20
    elif members >= 100_000: score += 12
    elif members >= 20_000:  score += 5

    lts = m.get("loan_to_share_ratio", 0)
    if lts >= 85:    score += 15
    elif lts >= 70:  score += 8
    elif lts < 40:   score -= 10

    roe = m.get("roe", 0)
    if roe >= 10:    score += 10
    elif roe >= 5:   score += 5

    return max(0, min(100, score))


def modernization_urgency_score(m: dict, digital_maturity: int, assets: int) -> int:
    """
    Composite 0-100 score for how urgently a CU needs to modernize.
    Low digital maturity + high loan demand + large asset base = urgent buyer.
    """
    score = 30
    score += (5 - (digital_maturity or 3)) * 15  # 0–60 from maturity gap

    lts = m.get("loan_to_share_ratio", 0)
    if lts >= 80:  score += 20
    elif lts >= 60: score += 10

    roa = m.get("roa", 0)
    if roa < 0.3:  score += 15  # profitability pressure → cost-reduction urgency
    elif roa > 1.0: score += 8  # profitable → budget to invest

    if assets >= 1_000_000_000: score += 10
    elif assets >= 250_000_000: score += 5

    return max(0, min(100, score))


def build_financial_signals(name: str, m: dict, fh: int, gm: int, mu: int) -> list[dict]:
    """Generate signal records from financial metrics."""
    signals = []
    roa = m.get("roa", 0)
    roe = m.get("roe", 0)
    nwr = m.get("net_worth_ratio", 0)
    lts = m.get("loan_to_share_ratio", 0)
    ni  = m.get("net_income", 0)
    apm = m.get("assets_per_member", 0)

    # ROA signals
    if roa >= 1.0:
        signals.append({
            "type": "growth", "sev": 82,
            "label": f"Strong ROA {roa}% — healthy budget for technology investment",
            "source": "ncua_financials",
        })
    elif 0 < roa < 0.3:
        signals.append({
            "type": "pain_point", "sev": 78,
            "label": f"ROA pressure at {roa}% — cost-efficiency technology opportunity",
            "source": "ncua_financials",
        })
    elif roa < 0:
        signals.append({
            "type": "pain_point", "sev": 88,
            "label": f"Operating at a loss (ROA {roa}%) — urgent cost-reduction mandate",
            "source": "ncua_financials",
        })

    # ROE signal
    if roe >= 12:
        signals.append({
            "type": "growth", "sev": 76,
            "label": f"High ROE {roe}% — profitable CU actively investing in infrastructure",
            "source": "ncua_financials",
        })

    # Capital position
    if nwr >= 12:
        signals.append({
            "type": "growth", "sev": 74,
            "label": f"Well-capitalised at {nwr}% NWR — technology spend not capital-constrained",
            "source": "ncua_financials",
        })
    elif nwr < 6:
        signals.append({
            "type": "pain_point", "sev": 80,
            "label": f"Capital constrained ({nwr}% NWR) — lead with cost-saving ROI",
            "source": "ncua_financials",
        })

    # High-value membership
    if apm >= 50_000:
        signals.append({
            "type": "growth", "sev": 72,
            "label": f"High-value membership (${apm/1000:.0f}K assets/member) — digital engagement ROI is compelling",
            "source": "ncua_financials",
        })

    # Financial health score signal
    if fh >= 75:
        signals.append({
            "type": "growth", "sev": 70,
            "label": f"Financial Health Score {fh}/100 — strong balance sheet supports tech investment",
            "source": "ncua_financials",
        })
    elif fh < 45:
        signals.append({
            "type": "pain_point", "sev": 75,
            "label": f"Financial Health Score {fh}/100 — position as cost-reduction tool",
            "source": "ncua_financials",
        })

    # Modernization urgency
    if mu >= 75:
        signals.append({
            "type": "operational_gap", "sev": mu,
            "label": f"Modernization Urgency Score {mu}/100 — strong digital transformation pressure",
            "source": "ncua_financials",
        })

    return signals


def main():
    print(f"\n{B}{C}FintelliPro — Financial Metrics Enricher{W}")

    init_db()
    db = SessionLocal()

    companies = db.query(Company).filter_by(industry="credit_unions").all()
    print(f"  Processing {len(companies)} credit unions\n")

    hdr("Computing financial ratios + scores")

    updated = 0
    signals_added = 0

    for co in companies:
        rd = co.regulatory_data or {}
        net_income = NET_INCOME_MAP.get(co.name, 0)

        metrics = compute_metrics(rd, net_income)
        assets  = int(rd.get("total_assets", 0) or 0)
        members = int(rd.get("total_members", 0) or 0)

        fh_score = financial_health_score(metrics)
        gm_score = growth_momentum_score(metrics, assets, members)
        mu_score = modernization_urgency_score(metrics, co.digital_maturity or 3, assets)

        # Patch regulatory_data with all new fields — assign a new dict so SQLAlchemy detects the change
        co.regulatory_data = {**rd, **metrics,
                              "financial_health_score": fh_score,
                              "growth_momentum_score":  gm_score,
                              "modernization_urgency":  mu_score}
        flag_modified(co, "regulatory_data")

        # Remove any existing financial signals to avoid duplicates
        db.query(Signal).filter(
            Signal.company_id == co.id,
            Signal.source == "ncua_financials",
        ).delete(synchronize_session=False)

        # Insert new signals
        new_sigs = build_financial_signals(co.name, metrics, fh_score, gm_score, mu_score)
        for s in new_sigs:
            db.add(Signal(
                id           = str(uuid.uuid4()),
                company_id   = co.id,
                signal_type  = s["type"],
                signal_label = s["label"],
                severity     = s["sev"],
                source       = s["source"],
                is_active    = True,
            ))
        signals_added += len(new_sigs)
        updated += 1

        roa_str = f"{metrics['roa']:+.2f}%"
        roe_str = f"{metrics['roe']:+.2f}%"
        print(f"  {G}✓{W} {co.name[:46]:<46} ROA:{roa_str:>7}  ROE:{roe_str:>7}  FH:{fh_score:3d}  MU:{mu_score:3d}")

    db.commit()

    hdr("Summary")
    print(f"  CUs enriched:        {updated}")
    print(f"  Signals added:       {signals_added}")
    total_sigs = db.query(Signal).count()
    print(f"  Total signals in DB: {total_sigs}")

    # Quick stats
    cos = db.query(Company).filter_by(industry="credit_unions").all()
    healthy  = sum(1 for c in cos if (c.regulatory_data or {}).get("financial_health_score", 0) >= 70)
    stressed = sum(1 for c in cos if (c.regulatory_data or {}).get("financial_health_score", 0) < 45)
    print(f"\n  Financially healthy (FH≥70): {healthy} CUs")
    print(f"  Financially stressed (FH<45): {stressed} CUs")
    print(f"\n  {G}✅ Financial metrics enriched for all CUs.{W}\n")
    db.close()


if __name__ == "__main__":
    main()
