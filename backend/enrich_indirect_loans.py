"""
enrich_indirect_loans.py
========================
Downloads NCUA 5300 Call Report (latest quarter) and enriches credit union
records with indirect lending data.

Fields written to Company.regulatory_data (non-destructive patch):
  indirect_loans  — float, raw dollar amount of indirect loans outstanding
  indirect_ratio  — float, indirect_loans / total_loans * 100 (percentage, 1 dp)

Signals created (source="ncua_indirect"):
  - ratio < 20%:  informational (severity 40)
  - 20–50%:       moderate signal (severity 65) — meaningful indirect exposure
  - >50%:         high signal (severity 80) — heavy indirect book

Safe to re-run: old ncua_indirect signals are deleted before new ones are created.
Only runs on industry='credit_unions'. Never touches community_banks rows.
"""

import os, sys, io, csv, urllib.request, zipfile, logging
sys.path.insert(0, os.path.dirname(__file__))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
log = logging.getLogger(__name__)

NCUA_URL = "https://ncua.gov/files/publications/analysis/call-report-data-2026-06.zip"

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql://leadforge_db_utkx_user:Ydw9AloKOqyYBhbLWTxSf4uY3Q0eESzB"
    "@dpg-dag9v0jl550s73aeqba0-a.oregon-postgres.render.com/leadforge_db_utkx",
)

from app.db.database import SessionLocal
from app.models import Company, Signal
from sqlalchemy.orm.attributes import flag_modified


def download_5300() -> zipfile.ZipFile:
    log.info("Downloading NCUA 5300 from %s ...", NCUA_URL)
    req = urllib.request.Request(NCUA_URL, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=120) as r:
        data = r.read()
    log.info("Downloaded %.1f MB", len(data) / 1e6)
    return zipfile.ZipFile(io.BytesIO(data))


def parse_5300(z: zipfile.ZipFile) -> dict:
    """Returns {cu_number: {total_loans, indirect_loans}}."""
    total_loans = {}   # CU_NUMBER → ACCT_025B
    indirect_loans = {}  # CU_NUMBER → ACCT_618A

    with z.open("FS220.txt") as f:
        for row in csv.DictReader(io.TextIOWrapper(f, encoding="latin-1")):
            v = (row.get("ACCT_025B") or "0").strip()
            total_loans[row["CU_NUMBER"]] = int(v) if v else 0

    with z.open("FS220A.txt") as f:
        for row in csv.DictReader(io.TextIOWrapper(f, encoding="latin-1")):
            v = (row.get("ACCT_618A") or "0").strip()
            indirect_loans[row["CU_NUMBER"]] = int(v) if v else 0

    result = {}
    for cid in total_loans:
        result[cid] = {
            "total_loans": total_loans[cid],
            "indirect_loans": indirect_loans.get(cid, 0),
        }
    log.info("Parsed 5300 data: %d CU records", len(result))
    return result


def _severity_and_summary(name: str, indirect: float, ratio: float) -> tuple:
    if ratio >= 50:
        return 80, f"{name} has heavy indirect loan exposure: {ratio:.1f}% of total loans"
    if ratio >= 20:
        return 65, f"{name} has meaningful indirect lending: {ratio:.1f}% of total loans"
    return 40, f"{name} indirect loans: {ratio:.1f}% of total loan book"


def enrich(db, five300: dict) -> None:
    cus = db.query(Company).filter_by(industry="credit_unions").all()
    updated = 0
    skipped = 0

    for cu in cus:
        cid = str(cu.regulatory_id)
        if cid not in five300:
            skipped += 1
            continue

        rec = five300[cid]
        total = rec["total_loans"]
        indirect = rec["indirect_loans"]

        if total <= 0:
            # No loan data — store zeros, skip signal
            ratio = 0.0
        else:
            ratio = round(indirect / total * 100, 1)

        # Non-destructive patch using the SQLAlchemy JSON mutation pattern
        rd = cu.regulatory_data or {}
        cu.regulatory_data = {
            **rd,
            "indirect_loans": indirect,
            "indirect_ratio": ratio,
        }
        flag_modified(cu, "regulatory_data")

        # Remove stale ncua_indirect signals before re-creating
        db.query(Signal).filter_by(company_id=cu.id, source="ncua_indirect").delete()

        if indirect > 0 and total > 0:
            sev, label = _severity_and_summary(cu.name, indirect, ratio)
            sig = Signal(
                company_id=cu.id,
                signal_type="indirect_lending",
                source="ncua_indirect",
                signal_label=label,
                severity=sev,
                is_active=True,
                source_file="call-report-data-2026-06.zip",
                source_label="NCUA 5300 Call Report Q2-2026",
                raw_evidence=(
                    f"Indirect loans: ${indirect:,}  |  "
                    f"Total loans: ${total:,}  |  "
                    f"Ratio: {ratio:.1f}%"
                ),
            )
            db.add(sig)

        updated += 1
        log.info("  ✓ %s — indirect %.1f%% ($%dM / $%dM)",
                 cu.name, ratio, indirect // 1_000_000, total // 1_000_000)

    db.commit()
    log.info("Done. Updated %d CUs, skipped %d (no charter match).", updated, skipped)


def main():
    z = download_5300()
    five300 = parse_5300(z)

    db = SessionLocal()
    try:
        enrich(db, five300)
    finally:
        db.close()


if __name__ == "__main__":
    main()
