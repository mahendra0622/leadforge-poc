"""
FintelliPro — Payment Rails Seed
=================================
Fetches live RTP (The Clearing House) and FedNow (Federal Reserve XLSX)
participant lists, cross-references with our 100 CUs, stores flags in
regulatory_data, and generates payment_rails signals.

Run:
    python seed_payments.py
"""
import sys, os, re, uuid, zipfile, io
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import urllib.request
import xml.etree.ElementTree as ET
from sqlalchemy.orm.attributes import flag_modified
from app.db.database import SessionLocal, init_db
from app.models import Company, Signal

G="\033[92m"; Y="\033[93m"; C="\033[96m"; R="\033[91m"; W="\033[0m"; B="\033[1m"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Accept": "*/*",
}

# ── RTP: scrape The Clearing House ───────────────────────────────────────────

def fetch_rtp_names() -> set[str]:
    url = "https://www.theclearinghouse.org/payment-systems/rtp/rtp-participating-financial-institutions"
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=30) as r:
        body = r.read().decode("utf-8", errors="ignore")
    entries = re.findall(r'<div class="fi-company">([^<]+)<br', body)
    return {re.sub(r'\s*-\s*[A-Z]{2}$', '', e.strip()).strip() for e in entries}


# ── FedNow: download XLSX from frbservices.org, parse without openpyxl ───────

def fetch_fednow_names() -> set[str]:
    """Download FedNow live-participants XLSX and return set of org names (uppercase)."""
    # URL discovered via Bloomreach CMS resourceapi endpoint
    xlsx_url = (
        "https://www.frbservices.org/binaries/content/assets/crsocms/"
        "financial-services/fednow/fednow-live-participants.xlsx"
    )
    req = urllib.request.Request(xlsx_url, headers={
        **HEADERS,
        "Referer": "https://www.frbservices.org/financial-services/fednow/organizations",
    })
    with urllib.request.urlopen(req, timeout=30) as r:
        xlsx_bytes = r.read()

    # XLSX is a ZIP; shared strings are in xl/sharedStrings.xml
    names = set()
    with zipfile.ZipFile(io.BytesIO(xlsx_bytes)) as zf:
        # Read shared strings table
        shared_strings = []
        if "xl/sharedStrings.xml" in zf.namelist():
            tree = ET.parse(zf.open("xl/sharedStrings.xml"))
            root = tree.getroot()
            ns = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
            for si in root.findall(".//x:si", ns):
                texts = [t.text or "" for t in si.findall(".//x:t", ns)]
                shared_strings.append("".join(texts))

        # Read sheet1 cells — column A (organization name)
        sheet_file = "xl/worksheets/sheet1.xml"
        if sheet_file in zf.namelist():
            tree = ET.parse(zf.open(sheet_file))
            root = tree.getroot()
            ns = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
            for row in root.findall(".//x:row", ns):
                for cell in row.findall("x:c", ns):
                    ref = cell.get("r", "")
                    if not ref.startswith("A"):
                        continue
                    cell_type = cell.get("t", "")
                    v = cell.find("x:v", ns)
                    if v is None or v.text is None:
                        continue
                    if cell_type == "s":
                        # shared string index
                        idx = int(v.text)
                        if idx < len(shared_strings):
                            names.add(shared_strings[idx].strip().upper())
                    else:
                        names.add(v.text.strip().upper())

    # Remove header rows
    names.discard("ORGANIZATION NAME")
    names = {n for n in names if len(n) > 3}
    return names


# ── Name matching ─────────────────────────────────────────────────────────────

_NOISE = {'the', 'federal', 'inc', 'corp', 'and', 'of', 'a'}
_SKIP_TOKENS = {'credit', 'union', 'employees', 'community', 'financial', 'bank', 'services'}

def normalize(name: str) -> str:
    name = name.lower().strip()
    name = re.sub(r'\bfcu\b', 'federal credit union', name)
    name = re.sub(r'\bcu\b(?!\w)', 'credit union', name)
    for w in _NOISE:
        name = re.sub(r'\b' + w + r'\b', ' ', name)
    name = re.sub(r'[^a-z0-9 ]', ' ', name)
    return re.sub(r'\s+', ' ', name).strip()


def meaningful_tokens(norm: str) -> set[str]:
    return {t for t in norm.split() if len(t) > 3 and t not in _SKIP_TOKENS}


def find_match(cu_name: str, name_norm: dict[str, str], require_cu: bool = False) -> str | None:
    """Return canonical name if confident match found, else None.
    If require_cu=True, only match entries that contain 'credit union'.
    """
    norm = normalize(cu_name)
    if norm in name_norm:
        match = name_norm[norm]
        if require_cu and "credit union" not in match.lower():
            return None
        return match

    tokens = meaningful_tokens(norm)
    if len(tokens) < 2:
        return None
    for rk, rv in name_norm.items():
        if require_cu and "credit union" not in rv.lower():
            continue
        rk_tokens = meaningful_tokens(rk)
        overlap = tokens & rk_tokens
        if len(overlap) >= 2 and len(overlap) >= len(tokens) * 0.75:
            return rv
    return None


# ── Signals ───────────────────────────────────────────────────────────────────

def build_payment_signals(is_rtp: bool, is_fednow: bool) -> list[dict]:
    if is_rtp and is_fednow:
        return [{"type": "growth", "sev": 72,
                 "label": "On both RTP and FedNow — mature payment stack; evaluate value-added instant payment services",
                 "source": "payment_rails"}]
    if is_rtp and not is_fednow:
        return [{"type": "growth", "sev": 76,
                 "label": "On RTP but not FedNow — strong candidate to add FedNow send/receive capability",
                 "source": "payment_rails"}]
    if is_fednow and not is_rtp:
        return [{"type": "growth", "sev": 74,
                 "label": "FedNow early adopter (not yet on RTP) — open to expanding real-time payment rails",
                 "source": "payment_rails"}]
    # Neither
    return [{"type": "operational_gap", "sev": 84,
             "label": "Not yet on real-time payment rails (FedNow or RTP) — payment modernization is an active priority",
             "source": "payment_rails"}]


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print(f"\n{B}{C}FintelliPro — Payment Rails Seed{W}")

    print(f"\n  {Y}Fetching RTP list from The Clearing House...{W}")
    rtp_raw = fetch_rtp_names()
    rtp_norm = {normalize(n): n for n in rtp_raw}
    print(f"  RTP: {len(rtp_raw)} total, {sum(1 for n in rtp_raw if 'Credit Union' in n)} credit unions")

    print(f"  {Y}Fetching FedNow participant XLSX from frbservices.org...{W}")
    fednow_raw = fetch_fednow_names()
    fednow_norm = {normalize(n): n for n in fednow_raw}
    print(f"  FedNow: {len(fednow_raw)} total, {sum(1 for n in fednow_raw if 'CREDIT UNION' in n)} credit unions")

    init_db()
    db = SessionLocal()
    companies = db.query(Company).filter_by(industry="credit_unions").all()
    print(f"\n  Processing {len(companies)} credit unions\n")

    rtp_yes = fednow_yes = both = neither = 0
    sig_added = 0

    for co in companies:
        rtp_match    = find_match(co.name, rtp_norm,    require_cu=False)
        fednow_match = find_match(co.name, fednow_norm, require_cu=True)

        is_rtp    = rtp_match    is not None
        is_fednow = fednow_match is not None

        rd = dict(co.regulatory_data or {})
        rd["is_rtp_participant"]    = is_rtp
        rd["is_fednow_participant"] = is_fednow
        co.regulatory_data = rd
        flag_modified(co, "regulatory_data")

        db.query(Signal).filter(
            Signal.company_id == co.id,
            Signal.source == "payment_rails",
        ).delete(synchronize_session=False)

        for s in build_payment_signals(is_rtp, is_fednow):
            db.add(Signal(
                id=str(uuid.uuid4()), company_id=co.id,
                signal_type=s["type"], signal_label=s["label"],
                severity=s["sev"], source=s["source"], is_active=True,
            ))
        sig_added += 1

        rtp_icon    = f"{G}RTP{W}"    if is_rtp    else f"   "
        fednow_icon = f"{C}FedNow{W}" if is_fednow else f"      "
        print(f"  [{rtp_icon}][{fednow_icon}]  {co.name}")

        if is_rtp and is_fednow: both    += 1
        elif is_rtp:             rtp_yes += 1
        elif is_fednow:          fednow_yes += 1
        else:                    neither += 1

    db.commit()

    print(f"\n{B}{C}Summary{W}")
    print(f"  ───────────────────────────────")
    print(f"  Both RTP + FedNow:   {both:3d}")
    print(f"  RTP only:            {rtp_yes:3d}")
    print(f"  FedNow only:         {fednow_yes:3d}")
    print(f"  Neither:             {neither:3d}")
    print(f"  Signals written:     {sig_added}")
    print(f"\n  {G}✅ Payment rails data seeded.{W}\n")
    db.close()


if __name__ == "__main__":
    main()
