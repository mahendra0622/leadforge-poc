"""
FintelliPro — NCUA Bulk Download (production-grade, schema-resilient)
=======================================================================
Downloads real NCUA quarterly data and auto-detects column names.
Works even when NCUA changes their file structure each quarter.

Run:
    python ncua_bulk_download.py              # loads 100 CUs
    python ncua_bulk_download.py --target 200
    python ncua_bulk_download.py --target 500  # loads ~500 CUs ($50M+ assets)
"""
import sys, os, io, csv, time, uuid as _uuid, zipfile, urllib.request, argparse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.db.database import SessionLocal, init_db
from app.models import Company, Contact, Signal, AIMessage
from app.services.regulatory.cuna_ncua import CUNAIntelligenceClient, LEGACY_PROCESSORS
from app.services.regulatory.ncua_schema import (
    build_schema_map, validate_schema, NCUASchemaMap
)

DEFAULT_TARGET = 100
MIN_ASSETS     = 50_000_000

# Quarterly ZIP URLs — format: YYYY-MM (confirmed from ncua.gov)
NCUA_BULK_URLS = [
    ("2024-Q4", "https://ncua.gov/files/publications/analysis/call-report-data-2024-12.zip"),
    ("2024-Q3", "https://ncua.gov/files/publications/analysis/call-report-data-2024-09.zip"),
    ("2024-Q2", "https://ncua.gov/files/publications/analysis/call-report-data-2024-06.zip"),
    ("2024-Q1", "https://ncua.gov/files/publications/analysis/call-report-data-2024-03.zip"),
    ("2023-Q4", "https://ncua.gov/files/publications/analysis/call-report-data-2023-12.zip"),
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "*/*",
    "Referer": "https://ncua.gov/analysis/credit-union-corporate-call-report-data/quarterly-data",
}

G="\033[92m"; Y="\033[93m"; C="\033[96m"; R="\033[91m"; W="\033[0m"; B="\033[1m"
def ok(s):   print(f"  {G}✓{W} {s}")
def warn(s): print(f"  {Y}⚠{W}  {s}")
def err(s):  print(f"  {R}✗{W} {s}")
def hdr(s):  print(f"\n{B}{C}{s}{W}\n  {'─'*58}")
def info(s): print(f"  → {s}")

def gi(row, col):
    try: return int(float(str(row.get(col, "0") or "0").replace(",", "")))
    except: return 0

def gs(row, col):
    return str(row.get(col, "") or "").strip()


# ── Step 1: Download ────────────────────────────────────────────
def download_zip():
    for quarter, url in NCUA_BULK_URLS:
        info(f"Trying {quarter}  —  {url.split('/')[-1]}")
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=120) as resp:
                data = resp.read()
            ok(f"Downloaded {len(data)/1e6:.1f} MB  —  {quarter}")
            return data, quarter
        except Exception as e:
            warn(f"Failed: {str(e)[:80]}")
            time.sleep(1)
    return None, None


# ── Step 2: Load files from ZIP ─────────────────────────────────
def load_zip_files(zip_bytes: bytes) -> tuple:
    """
    Extract FOICU.txt, FS220.txt, and AcctDesc.txt from the ZIP.
    Returns (foicu_rows, fs220_rows, acct_desc_raw).
    File names are matched case-insensitively.
    """
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as z:
        names = z.namelist()
        name_map = {os.path.basename(n).upper(): n for n in names}

        ok(f"ZIP contains {len(names)} files")

        # Required files
        foicu_key  = next((k for k in name_map if k.startswith("FOICU") and k.endswith(".TXT")), None)
        fs220_key  = next((k for k in name_map if k == "FS220.TXT"), None)
        acct_key   = next((k for k in name_map if k.startswith("ACCTDESC") or k == "ACCTDESC.TXT"), None)

        if not foicu_key: raise ValueError(f"FOICU.TXT not found. Files: {list(name_map.keys())[:15]}")
        if not fs220_key: raise ValueError(f"FS220.TXT not found. Files: {list(name_map.keys())[:15]}")

        ok(f"Found: {foicu_key}, {fs220_key}, {acct_key or '(no AcctDesc)'}")

        foicu_raw   = z.read(name_map[foicu_key]).decode("utf-8", errors="replace")
        fs220_raw   = z.read(name_map[fs220_key]).decode("utf-8", errors="replace")
        acct_raw    = z.read(name_map[acct_key]).decode("utf-8", errors="replace") if acct_key else ""

    foicu_rows = list(csv.DictReader(io.StringIO(foicu_raw)))
    fs220_rows = list(csv.DictReader(io.StringIO(fs220_raw)))

    ok(f"FOICU: {len(foicu_rows):,} CUs   FS220: {len(fs220_rows):,} CUs")
    return foicu_rows, fs220_rows, acct_raw


# ── Step 3: Join and filter ─────────────────────────────────────
def join_and_filter(foicu_rows, fs220_rows, schema: NCUASchemaMap, min_assets: int) -> list[dict]:
    """
    Join FOICU (identity) + FS220 (financials) on CU_NUMBER.
    Uses schema map for column names — works even if NCUA renames columns.
    """
    # Index FOICU by CU_NUMBER
    foicu_idx = {gs(r, schema.col_cu_number): r for r in foicu_rows}

    TOM_MAP = {
        "1":"Community","3":"Community","5":"Community","10":"Community",
        "14":"Community","20":"Community","36":"Community","37":"Community",
        "2":"Multiple Common Bond","4":"Select Employee Group",
        "40":"Select Employee Group",
    }

    combined = []
    for fin in fs220_rows:
        cu_num = gs(fin, schema.col_cu_number)
        assets = gi(fin, schema.col_assets)
        if assets < min_assets:
            continue

        ident    = foicu_idx.get(cu_num, {})
        cu_type  = gs(ident, schema.col_cu_type)
        tom      = gs(ident, schema.col_tom_code).strip()
        licu_raw = gs(ident, schema.col_licu)
        branches = gi(fin, schema.col_branches_a) + gi(fin, schema.col_branches_b)

        combined.append({
            "CU_NUMBER":    cu_num,
            "CU_NAME":      gs(ident, schema.col_cu_name),
            "CITY":         gs(ident, schema.col_city),
            "STATE":        gs(ident, schema.col_state),
            "ZIP_CODE":     gs(ident, schema.col_zip),
            "CHARTER_TYPE": "Federal" if cu_type in ("1","F","FCU") else "State",
            "FOM":          TOM_MAP.get(tom, "Community"),
            "LICU":         licu_raw in ("1","Y","Yes","True","TRUE"),

            "ASSETS":    assets,
            "LOANS":     gi(fin, schema.col_loans),
            "SHARES":    gi(fin, schema.col_shares),
            "MEMBERS":   gi(fin, schema.col_members),
            "NET_WORTH": gi(fin, schema.col_net_worth),
            "NET_INCOME":gi(fin, schema.col_net_income),
            "BRANCHES":  branches,
        })

    combined.sort(key=lambda r: r["ASSETS"], reverse=True)
    ok(f"After join + filter (≥${min_assets/1e6:.0f}M): {len(combined):,} CUs")
    return combined


# ── Step 4: Build signals ───────────────────────────────────────
def build_signals(r: dict, cuna) -> list:
    a=r["ASSETS"]; sh=r["SHARES"]; lo=r["LOANS"]
    m=r["MEMBERS"]; nw=r["NET_WORTH"]; br=r["BRANCHES"]
    nwr = round(nw/a*100, 1) if a else 0
    lts = round(lo/sh*100, 1) if sh else 0
    sigs = []

    if   a >= 1_000_000_000: sigs.append(("growth", f"Enterprise CU — ${a/1e9:.1f}B assets (Tier 1)", 90, "ncua_5300"))
    elif a >= 500_000_000:   sigs.append(("growth", f"Large CU — ${a/1e6:.0f}M assets (Tier 1)", 82, "ncua_5300"))
    elif a >= 100_000_000:   sigs.append(("growth", f"Mid-market CU — ${a/1e6:.0f}M assets (Tier 2)", 72, "ncua_5300"))

    if   m >= 500_000: sigs.append(("growth", f"Massive member base: {m:,} members", 88, "ncua_5300"))
    elif m >= 100_000: sigs.append(("growth", f"Large member base: {m:,} members", 78, "ncua_5300"))
    elif m >= 20_000:  sigs.append(("growth", f"Growing membership: {m:,} members", 62, "ncua_5300"))

    if   nwr >= 10: sigs.append(("growth",      f"Strongly capitalised: {nwr}% NWR — budget available", 76, "ncua_5300"))
    elif nwr >= 7:  sigs.append(("growth",      f"Well-capitalised: {nwr}% NWR", 62, "ncua_5300"))
    elif 0 < nwr < 6: sigs.append(("pain_point", f"Capital pressure: {nwr}% NWR — pitch cost reduction", 68, "ncua_5300"))

    if   lts >= 85:   sigs.append(("growth",          f"High loan demand: {lts}% LTS — digital origination needed", 78, "ncua_5300"))
    elif 0 < lts < 50: sigs.append(("operational_gap", f"Low loan utilisation: {lts}% LTS — origination gap", 70, "ncua_5300"))

    sigs.append(("operational_gap", "Core processor requires Apollo enrichment — likely legacy", 62, "ncua_profile"))

    if r["LICU"]:
        sigs.append(("regulatory_risk", "NCUA Low-Income Designated (LICU) — compliance investment mandate", 72, "ncua_profile"))
    if br >= 15:
        sigs.append(("operational_gap", f"Multi-branch: {br} locations — payments orchestration needed", 65, "ncua_profile"))

    for p in sorted(cuna.get_industry_priorities(), key=lambda x: x["urgency"], reverse=True)[:2]:
        sigs.append((p["signal_type"], f"CUNA Industry Signal: {p['priority']}", p["urgency"], "cuna_intelligence"))

    return sigs


def calc_score(r, maturity, sigs):
    pain   = [s[2] for s in sigs if s[0] in ("pain_point","operational_gap")]
    growth = [s[2] for s in sigs if s[0] == "growth"]
    pa = sum(pain)/len(pain)     if pain   else 40
    ga = sum(growth)/len(growth) if growth else 30
    base = (6-maturity)*18*0.30 + pa*0.25 + ga*0.20 + 85*0.15 + 80*0.10
    return min(100, int(base * 1.15))


# ── Step 5: Wipe + insert ───────────────────────────────────────
def wipe_and_insert(db, rows, cuna, quarter):
    hdr(f"Step 4 — Wipe old data + insert {len(rows)} real CUs")

    db.query(Signal).delete(); db.query(AIMessage).delete()
    db.query(Contact).delete(); db.query(Company).delete()
    db.commit()
    ok("Deleted old data · Demo user preserved")
    print()

    inserted = 0
    for r in rows:
        a=r["ASSETS"]; m=r["MEMBERS"]; sh=r["SHARES"]; lo=r["LOANS"]; nw=r["NET_WORTH"]
        nwr = round(nw/a*100, 2) if a else 0
        lts = round(lo/sh*100, 2) if sh else 0
        tier = ("Large (>$1B)" if a>=1_000_000_000 else
                "Mid ($250M–$1B)" if a>=250_000_000 else "Community ($50M–$250M)")
        mat  = 3 if a >= 1_000_000_000 else 2
        sigs = build_signals(r, cuna)
        opp  = calc_score(r, mat, sigs)

        co_id = str(_uuid.uuid4())
        db.add(Company(
            id=co_id, apollo_org_id=f"ncua_{r['CU_NUMBER']}",
            name=r["CU_NAME"], website="",
            industry="credit_unions",
            hq_city=r["CITY"], hq_state=r["STATE"], hq_country="US",
            revenue_est=a,
            employee_count=max(10, m//80) if m else None,
            tech_stack=[],
            regulatory_src="NCUA", regulatory_id=r["CU_NUMBER"],
            regulatory_data={
                "charter_number":       r["CU_NUMBER"],
                "charter_type":         r["CHARTER_TYPE"],
                "field_of_membership":  r["FOM"],
                "total_assets":         a,
                "total_shares":         sh,
                "total_loans":          lo,
                "total_members":        m,
                "net_worth":            nw,
                "net_worth_ratio":      nwr,
                "loan_to_share_ratio":  lts,
                "num_branches":         r["BRANCHES"],
                "core_processor":       "",
                "asset_tier":           tier,
                "is_licu":              r["LICU"],
                "data_as_of":           quarter,
            },
            digital_maturity=mat, opportunity_score=opp, outreach_status="new",
        ))
        db.flush()

        for (st, lb, sv, src) in sigs:
            db.add(Signal(id=str(_uuid.uuid4()), company_id=co_id,
                          signal_type=st, signal_label=lb, severity=sv, source=src, is_active=True))

        inserted += 1
        print(f"  {G}✓{W} [{inserted:03d}] {r['CU_NAME']:<46} ${a/1e6:>9,.0f}M  score:{opp}")
        if inserted % 25 == 0:
            db.commit()

    db.commit()
    return inserted


# ── Main ────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", type=int, default=DEFAULT_TARGET)
    args = parser.parse_args()

    print(f"\n{B}{C}FintelliPro — NCUA Bulk Download (schema-resilient){W}")
    print(f"  Target: top {args.target} CUs · NCUA 5300 Call Report\n")

    init_db()
    db   = SessionLocal()
    cuna = CUNAIntelligenceClient()

    # 1. Download
    hdr("Step 1 — Download NCUA quarterly ZIP")
    zip_bytes, quarter = download_zip()
    if not zip_bytes:
        err("Download failed. Run  python ncua_live_seed.py  for embedded data.")
        sys.exit(1)

    # 2. Load files
    hdr("Step 2 — Extract + parse FOICU.txt and FS220.txt")
    foicu_rows, fs220_rows, acct_raw = load_zip_files(zip_bytes)

    # 3. Auto-detect schema (handles column renames each quarter)
    hdr("Step 3 — Auto-detect column schema")
    schema = build_schema_map(foicu_rows, fs220_rows, acct_raw, quarter)
    ok(f"Assets col: {schema.col_assets}  |  Members: {schema.col_members}  |  "
       f"Shares: {schema.col_shares}  |  NetWorth: {schema.col_net_worth}")

    # Validate — sanity-check the mapping
    warnings = validate_schema(schema, foicu_rows, fs220_rows)
    if warnings:
        for w in warnings:
            warn(w)
    else:
        ok("Schema validation passed")

    # Join + filter
    rows = join_and_filter(foicu_rows, fs220_rows, schema, MIN_ASSETS)
    top  = rows[:args.target]

    # 4. Wipe + insert
    inserted = wipe_and_insert(db, top, cuna, quarter)

    # Summary
    cos  = db.query(Company).all()
    ta   = sum(c.revenue_est or 0 for c in cos)
    mem  = sum((c.regulatory_data or {}).get("total_members", 0) for c in cos)
    avg  = sum(c.opportunity_score or 0 for c in cos) / len(cos) if cos else 0
    sigs = db.query(Signal).count()
    licu = sum(1 for c in cos if (c.regulatory_data or {}).get("is_licu"))

    print(f"\n{B}{C}Summary — NCUA {quarter}{W}\n  {'─'*58}")
    print(f"  {B}CUs loaded:        {inserted}{W}")
    print(f"  Combined assets:   ${ta/1e9:.1f}B")
    print(f"  Total members:     {mem:,}")
    print(f"  Total signals:     {sigs}")
    print(f"  Avg opp. score:    {avg:.0f}/100")
    print(f"  LICU designated:   {licu} CUs")
    print(f"\n  {G}Login: demo@fintellipro.com / demo1234{W}")
    print(f"  Open:  http://localhost:3000")
    print(f"\n  {G}✅ Done — {inserted} real CUs from NCUA {quarter}.{W}\n")
    db.close()


if __name__ == "__main__":
    main()
