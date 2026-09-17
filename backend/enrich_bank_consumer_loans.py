"""
enrich_bank_consumer_loans.py
==============================
Fetches FDIC Call Report data for community banks via the public BankFind API
(api.fdic.gov) and enriches regulatory_data with consumer lending metrics.

Fields written to Company.regulatory_data (non-destructive patch):
  total_assets          — int, dollars
  total_loans           — int, dollars  (net loans & leases)
  consumer_loans        — int, dollars
  consumer_loan_ratio   — float, consumer_loans / total_loans * 100 (%)
  roa                   — float, Return on Assets (%)
  net_income            — int, dollars
  net_worth             — int, dollars  (equity)
  net_worth_ratio       — float, equity / assets * 100 (%)
  fdic_report_date      — str, YYYYMMDD of the call report period

Signals created (source="fdic_consumer"):
  consumer_loan_ratio >= 40%: moderate signal (severity 65)
  consumer_loan_ratio >= 25%: informational (severity 45)

Safe to re-run: old fdic_consumer signals deleted before new ones are written.
Only runs on industry='community_banks'. Never touches credit_unions rows.
"""

import os, sys, time, logging, urllib.request, json
sys.path.insert(0, os.path.dirname(__file__))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

FDIC_URL = "https://api.fdic.gov/banks/financials"
FIELDS   = "REPDTE,ASSET,LNLSNET,LNCON,ROA,NETINC,EQ"

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql://leadforge_db_utkx_user:Ydw9AloKOqyYBhbLWTxSf4uY3Q0eESzB"
    "@dpg-dag9v0jl550s73aeqba0-a.oregon-postgres.render.com/leadforge_db_utkx",
)

from app.db.database import SessionLocal
from app.models import Company, Signal
from sqlalchemy.orm.attributes import flag_modified


def fetch_fdic(cert: str) -> dict | None:
    """Returns latest quarterly financials dict for a bank CERT, or None."""
    url = (
        f"{FDIC_URL}?filters=CERT%3A{cert}"
        f"&fields={FIELDS}&limit=1&sort_by=REPDTE&sort_order=DESC"
    )
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            payload = json.loads(r.read())
        rows = payload.get("data", [])
        return rows[0]["data"] if rows else None
    except Exception as e:
        log.warning("FDIC API error for CERT %s: %s", cert, e)
        return None


def _severity_and_label(name: str, ratio: float) -> tuple:
    if ratio >= 40:
        return 65, (
            f"{name} has high consumer loan concentration: "
            f"{ratio:.1f}% of total loans"
        )
    return 45, (
        f"{name} consumer loan concentration: {ratio:.1f}% of total loans"
    )


def enrich(db) -> None:
    banks = db.query(Company).filter_by(industry="community_banks").all()
    updated = skipped = 0

    for bank in banks:
        cert = str(bank.regulatory_id)
        row = fetch_fdic(cert)
        time.sleep(0.15)  # stay well under the 20 req/s rate limit

        if not row:
            log.warning("✗ %s (CERT=%s) — no FDIC data", bank.name, cert)
            skipped += 1
            continue

        # All monetary values from FDIC API are in thousands of dollars
        asset_k    = row.get("ASSET", 0) or 0
        loans_k    = row.get("LNLSNET", 0) or 0
        consumer_k = row.get("LNCON", 0) or 0
        netinc_k   = row.get("NETINC", 0) or 0
        eq_k       = row.get("EQ", 0) or 0
        roa        = row.get("ROA") or 0.0
        repdte     = row.get("REPDTE", "")

        # Convert to dollars
        total_assets   = asset_k    * 1000
        total_loans    = loans_k    * 1000
        consumer_loans = consumer_k * 1000
        net_income     = netinc_k   * 1000
        net_worth      = eq_k       * 1000

        consumer_ratio = round(consumer_loans / total_loans * 100, 1) if total_loans > 0 else 0.0
        nwr            = round(net_worth / total_assets * 100, 2) if total_assets > 0 else 0.0

        # Non-destructive patch
        rd = bank.regulatory_data or {}
        bank.regulatory_data = {
            **rd,
            "total_assets":        total_assets,
            "total_loans":         total_loans,
            "consumer_loans":      consumer_loans,
            "consumer_loan_ratio": consumer_ratio,
            "roa":                 round(float(roa), 4),
            "net_income":          net_income,
            "net_worth":           net_worth,
            "net_worth_ratio":     nwr,
            "fdic_report_date":    repdte,
        }
        flag_modified(bank, "regulatory_data")

        # Refresh signals
        db.query(Signal).filter_by(company_id=bank.id, source="fdic_consumer").delete()

        if consumer_ratio > 0 and total_loans > 0:
            sev, label = _severity_and_label(bank.name, consumer_ratio)
            db.add(Signal(
                company_id   = bank.id,
                signal_type  = "consumer_lending",
                source       = "fdic_consumer",
                signal_label = label,
                severity     = sev,
                is_active    = True,
                source_label = f"FDIC Call Report {repdte}",
                raw_evidence = (
                    f"Consumer loans: ${consumer_loans:,}  |  "
                    f"Total loans: ${total_loans:,}  |  "
                    f"Ratio: {consumer_ratio:.1f}%"
                ),
            ))

        updated += 1
        log.info(
            "✓ %s — consumer %.1f%%  assets=$%.1fB  ROA=%.2f%%",
            bank.name, consumer_ratio, total_assets / 1e9, roa,
        )

    db.commit()
    log.info("Done. Enriched %d banks, skipped %d.", updated, skipped)


def main():
    db = SessionLocal()
    try:
        enrich(db)
    finally:
        db.close()


if __name__ == "__main__":
    main()
