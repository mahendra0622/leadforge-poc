"""
fix_cu_charters.py
==================
Fixes wrong regulatory_id (NCUA charter numbers) for credit unions by
matching against NCUA 5300 FOICU.txt using name search + asset-size validation.

A match is accepted only if the NCUA asset size is within 4x of the
total_assets stored in our regulatory_data — this filters out false positives
where different CUs share a common name prefix.

Safe to re-run: only updates regulatory_id, nothing else.
"""

import os, sys, io, csv, urllib.request, zipfile, logging
sys.path.insert(0, os.path.dirname(__file__))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

NCUA_URL = "https://ncua.gov/files/publications/analysis/call-report-data-2026-06.zip"

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql://leadforge_db_utkx_user:Ydw9AloKOqyYBhbLWTxSf4uY3Q0eESzB"
    "@dpg-dag9v0jl550s73aeqba0-a.oregon-postgres.render.com/leadforge_db_utkx",
)

from app.db.database import SessionLocal
from app.models import Company


def download_5300() -> zipfile.ZipFile:
    log.info("Downloading NCUA 5300...")
    req = urllib.request.Request(NCUA_URL, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=120) as r:
        data = r.read()
    return zipfile.ZipFile(io.BytesIO(data))


def build_lookup(z: zipfile.ZipFile):
    """Returns (name_upper → list[{charter, state}], charter → total_assets_dollars)"""
    name_map = {}
    with z.open("FOICU.txt") as f:
        for row in csv.DictReader(io.TextIOWrapper(f, encoding="latin-1")):
            cid = row["CU_NUMBER"]
            name = row["CU_NAME"].strip()
            state = row.get("CU_STATE", "").strip().upper()
            name_map.setdefault(name.upper(), []).append({"charter": cid, "state": state, "name": name})

    asset_map = {}
    with z.open("FS220.txt") as f:
        for row in csv.DictReader(io.TextIOWrapper(f, encoding="latin-1")):
            v = (row.get("ACCT_010") or "").strip()
            asset_map[row["CU_NUMBER"]] = int(v) if v else 0

    return name_map, asset_map


def find_charter(cu_name: str, cu_state: str, db_assets: int,
                 name_map: dict, asset_map: dict):
    """
    Returns (charter, ncua_name) or (None, None).
    Validates that NCUA total assets are within 4x of our DB total assets.
    """
    cu_name_upper = cu_name.upper()
    cu_state = cu_state.upper() if cu_state else ""

    def _best_candidate(candidates):
        """Pick state-matching candidate if available, else first."""
        state_match = [c for c in candidates if c["state"] == cu_state]
        return (state_match or candidates)[0]

    def _asset_ok(charter):
        if db_assets <= 0:
            return True  # no data to validate against
        ncua = asset_map.get(charter, 0)
        if ncua <= 0:
            return False
        ratio = max(db_assets, ncua) / min(db_assets, ncua)
        return ratio <= 4.0

    # 1. Exact match
    if cu_name_upper in name_map:
        c = _best_candidate(name_map[cu_name_upper])
        if _asset_ok(c["charter"]):
            return c["charter"], c["name"]

    # 2. Strip common suffixes and try prefix match
    stripped = cu_name_upper
    for suffix in [" FEDERAL CREDIT UNION", " CREDIT UNION", " FEDERAL CU", " FCU", " CU"]:
        if stripped.endswith(suffix):
            stripped = stripped[: -len(suffix)].strip()
            break

    if stripped and stripped != cu_name_upper:
        # Look for NCUA entries whose name starts with the stripped token
        matches = [
            (ncua_name, cands)
            for ncua_name, cands in name_map.items()
            if ncua_name.startswith(stripped)
        ]
        for ncua_name, cands in matches:
            c = _best_candidate(cands)
            if _asset_ok(c["charter"]):
                return c["charter"], c["name"]

    return None, None


def run():
    z = download_5300()
    name_map, asset_map = build_lookup(z)

    db = SessionLocal()
    cus = db.query(Company).filter_by(industry="credit_unions").all()
    valid_charters = set(asset_map.keys())

    updated = 0
    skipped = 0

    for cu in cus:
        if str(cu.regulatory_id) in valid_charters:
            continue  # already correct

        db_assets = (cu.regulatory_data or {}).get("total_assets", 0)
        new_charter, ncua_name = find_charter(
            cu.name, cu.hq_state or "", db_assets, name_map, asset_map
        )

        if new_charter:
            old = cu.regulatory_id
            cu.regulatory_id = new_charter
            ncua_assets_m = asset_map.get(new_charter, 0) // 1_000_000
            log.info("✓ '%s' — %s → %s (NCUA: '%s', $%dM)",
                     cu.name, old, new_charter, ncua_name, ncua_assets_m)
            updated += 1
        else:
            log.warning("✗ '%s' — no validated match (db_assets=$%dM)",
                        cu.name, db_assets // 1_000_000 if db_assets else 0)
            skipped += 1

    db.commit()
    log.info("Done. Fixed %d charters, skipped %d.", updated, skipped)
    db.close()


if __name__ == "__main__":
    run()
