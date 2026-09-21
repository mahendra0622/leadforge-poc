"""
seed_bank_payments.py
=====================
Cross-references community banks against the live RTP and FedNow
participant lists and sets is_rtp_participant / is_fednow_participant
in regulatory_data.

Uses the same data sources as seed_payments.py (which only ran for CUs).
Safe to re-run. Only touches community_banks rows.
"""
import os, sys, re, urllib.request, io, logging
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql://leadforge_db_utkx_user:Ydw9AloKOqyYBhbLWTxSf4uY3Q0eESzB"
    "@dpg-dag9v0jl550s73aeqba0-a.oregon-postgres.render.com/leadforge_db_utkx",
)

from app.db.database import SessionLocal
from app.models import Company, Signal
from sqlalchemy.orm.attributes import flag_modified


def fetch_rtp_names() -> set:
    """Scrape The Clearing House RTP participant list."""
    url = "https://www.theclearinghouse.org/payment-systems/rtp/rtp-participating-financial-institutions"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=30) as r:
            html = r.read().decode("utf-8", errors="ignore")
        # Extract institution names from the page
        names = set(re.findall(r'class="fi-company"[^>]*>([^<]+)<', html))
        if not names:
            # Fallback: grab any text that looks like a bank name
            names = set(re.findall(r'>([A-Z][A-Za-z\s&,\'.]+(?:Bank|Bancorp|Financial|Credit Union|Savings|Trust|NA|N\.A\.))<', html))
        log.info("RTP list: %d institutions scraped", len(names))
        return {n.strip().upper() for n in names if n.strip()}
    except Exception as e:
        log.warning("RTP fetch failed: %s", e)
        return set()


def fetch_fednow_names() -> set:
    """Download FedNow participant XLSX and extract institution names."""
    try:
        # FedNow resource API returns JSON with embedded XLSX URL
        api_url = "https://www.frbservices.org/resourceapi/financial-services/fednow/organizations"
        req = urllib.request.Request(api_url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=30) as r:
            import json
            data = json.loads(r.read())

        xlsx_url = None
        for item in data.get("items", []):
            for link in item.get("links", []):
                if ".xlsx" in link.get("href", ""):
                    xlsx_url = link["href"]
                    break
            if xlsx_url:
                break

        if not xlsx_url:
            log.warning("FedNow XLSX URL not found in resource API")
            return set()

        if not xlsx_url.startswith("http"):
            xlsx_url = "https://www.frbservices.org" + xlsx_url

        req2 = urllib.request.Request(xlsx_url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req2, timeout=30) as r:
            xlsx_data = r.read()

        import zipfile, xml.etree.ElementTree as ET
        zf = zipfile.ZipFile(io.BytesIO(xlsx_data))
        names = set()
        for fname in zf.namelist():
            if "sharedStrings" in fname:
                root = ET.parse(zf.open(fname)).getroot()
                ns = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
                for si in root.findall("x:si", ns):
                    t = si.find("x:t", ns)
                    if t is not None and t.text:
                        names.add(t.text.strip().upper())
        log.info("FedNow list: %d strings extracted", len(names))
        return names
    except Exception as e:
        log.warning("FedNow fetch failed: %s — using empty set", e)
        return set()


def _name_match(bank_name: str, participant_names: set) -> bool:
    """Fuzzy match: check if any significant word sequence from bank_name appears in the participant list."""
    bn = bank_name.upper()
    # Direct check
    if bn in participant_names:
        return True
    # Check if any participant name contains our bank name (or vice versa)
    # Strip common suffixes for comparison
    stripped = re.sub(r'\b(NATIONAL BANK|NATIONAL ASSOCIATION|N\.?A\.?|BANK|BANCORP|SAVINGS BANK|FINANCIAL|FSB|AND TRUST|& TRUST)\b', '', bn).strip()
    if len(stripped) < 4:
        return False
    for pname in participant_names:
        if stripped in pname or pname.startswith(stripped[:15]):
            return True
    return False


def run():
    log.info("Fetching RTP and FedNow participant lists...")
    rtp_names = fetch_rtp_names()
    fednow_names = fetch_fednow_names()

    db = SessionLocal()
    banks = db.query(Company).filter_by(industry="community_banks").all()
    rtp_count = fednow_count = 0

    for bank in banks:
        on_rtp    = _name_match(bank.name, rtp_names)
        on_fednow = _name_match(bank.name, fednow_names)

        rd = bank.regulatory_data or {}
        bank.regulatory_data = {
            **rd,
            "is_rtp_participant":    on_rtp,
            "is_fednow_participant": on_fednow,
        }
        flag_modified(bank, "regulatory_data")

        if on_rtp:    rtp_count += 1
        if on_fednow: fednow_count += 1

        if on_rtp or on_fednow:
            rails = []
            if on_rtp:    rails.append("RTP")
            if on_fednow: rails.append("FedNow")
            db.query(Signal).filter_by(company_id=bank.id, source="payment_rails").delete()
            db.add(Signal(
                company_id=bank.id,
                signal_type="growth",
                source="payment_rails",
                signal_label=f"{bank.name} is a live participant on {' + '.join(rails)}",
                severity=72,
                is_active=True,
                source_label="TCH RTP / FedNow participant lists",
            ))

    db.commit()
    log.info("Done. RTP: %d/%d banks  FedNow: %d/%d banks", rtp_count, len(banks), fednow_count, len(banks))
    db.close()


if __name__ == "__main__":
    run()
