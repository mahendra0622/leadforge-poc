"""
FintelliPro — Payment Rails Seed
=================================
Fetches the live RTP participant list from The Clearing House,
cross-references with our 100 CUs, stores is_rtp_participant /
is_fednow_participant in regulatory_data, and generates signals.

Run:
    python seed_payments.py
"""
import sys, os, re, uuid
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import urllib.request
from sqlalchemy.orm.attributes import flag_modified
from app.db.database import SessionLocal, init_db
from app.models import Company, Signal

G="\033[92m"; Y="\033[93m"; C="\033[96m"; R="\033[91m"; W="\033[0m"; B="\033[1m"

# ── Fetch live RTP participant list ──────────────────────────────────────────

def fetch_rtp_names() -> set[str]:
    url = "https://www.theclearinghouse.org/payment-systems/rtp/rtp-participating-financial-institutions"
    headers = {"User-Agent": "Mozilla/5.0 (compatible; FintelliPro/1.0)"}
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as r:
        body = r.read().decode("utf-8", errors="ignore")
    entries = re.findall(r'<div class="fi-company">([^<]+)<br', body)
    # Strip trailing state code (e.g. " - TX")
    names = {re.sub(r'\s*-\s*[A-Z]{2}$', '', e.strip()).strip() for e in entries}
    return names


def normalize(name: str) -> str:
    name = name.lower().strip()
    # Expand common abbreviations before removing words
    name = re.sub(r'\bfcu\b', 'federal credit union', name)
    # Remove noise words
    for w in ['the', 'federal', 'inc', 'corp', ',', '.']:
        name = re.sub(r'\b' + re.escape(w) + r'\b', ' ', name)
    name = re.sub(r'[^a-z0-9 ]', ' ', name)
    return re.sub(r'\s+', ' ', name).strip()


def find_rtp_match(cu_name: str, rtp_norm: dict[str, str]) -> str | None:
    """Return canonical RTP name if cu_name is a confident match, else None."""
    norm = normalize(cu_name)
    # Exact normalized match
    if norm in rtp_norm:
        return rtp_norm[norm]
    # Token-based: require ≥3 meaningful tokens to overlap
    tokens = set(t for t in norm.split() if len(t) > 3
                 and t not in ('credit', 'union', 'employees', 'community', 'financial'))
    if len(tokens) < 2:
        return None
    for rk, rv in rtp_norm.items():
        rk_tokens = set(t for t in rk.split() if len(t) > 3
                        and t not in ('credit', 'union', 'employees', 'community', 'financial'))
        overlap = tokens & rk_tokens
        if len(overlap) >= 2 and len(overlap) >= len(tokens) * 0.7:
            return rv
    return None


def build_payment_signals(cu_name: str, is_rtp: bool, is_fednow: bool | None) -> list[dict]:
    signals = []

    if is_rtp and is_fednow:
        signals.append({
            "type": "growth", "sev": 72,
            "label": "On both RTP and FedNow networks — mature payment stack, target for value-added services",
            "source": "payment_rails",
        })
    elif is_rtp and not is_fednow:
        signals.append({
            "type": "growth", "sev": 76,
            "label": "Already on RTP real-time payments — strong candidate for FedNow adoption",
            "source": "payment_rails",
        })
    elif is_fednow and not is_rtp:
        signals.append({
            "type": "growth", "sev": 74,
            "label": "FedNow early adopter — open to payment innovation and instant payment expansion",
            "source": "payment_rails",
        })
    else:
        # Not on either network — best prospect for payment modernization
        signals.append({
            "type": "operational_gap", "sev": 82,
            "label": "Not yet on real-time payment rails — FedNow/RTP adoption is an active priority",
            "source": "payment_rails",
        })

    return signals


def main():
    print(f"\n{B}{C}FintelliPro — Payment Rails Seed{W}")

    print(f"\n  {Y}Fetching RTP participant list from The Clearing House...{W}")
    rtp_raw = fetch_rtp_names()
    rtp_norm = {normalize(n): n for n in rtp_raw}
    rtp_cus = {n for n in rtp_raw if "Credit Union" in n}
    print(f"  RTP participants fetched: {len(rtp_raw)} total, {len(rtp_cus)} credit unions")

    init_db()
    db = SessionLocal()
    companies = db.query(Company).filter_by(industry="credit_unions").all()
    print(f"  Processing {len(companies)} credit unions\n")

    rtp_yes = rtp_no = 0
    sig_added = 0

    for co in companies:
        rtp_match = find_rtp_match(co.name, rtp_norm)
        is_rtp = rtp_match is not None
        is_fednow = None  # FedNow list not yet machine-readable

        # Patch regulatory_data — assign new dict to force SQLAlchemy to detect change
        rd = dict(co.regulatory_data or {})
        rd["is_rtp_participant"]    = is_rtp
        rd["is_fednow_participant"] = is_fednow  # None = unknown
        co.regulatory_data = rd
        flag_modified(co, "regulatory_data")

        # Replace existing payment_rails signals
        db.query(Signal).filter(
            Signal.company_id == co.id,
            Signal.source == "payment_rails",
        ).delete(synchronize_session=False)

        new_sigs = build_payment_signals(co.name, is_rtp, is_fednow)
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
        sig_added += len(new_sigs)

        icon = f"{G}✓ RTP{W}" if is_rtp else f"{Y}✗{W}"
        match_str = f"  ({rtp_match[:35]})" if rtp_match else ""
        print(f"  {icon}  {co.name[:48]:<48}{match_str}")

        if is_rtp: rtp_yes += 1
        else:       rtp_no  += 1

    db.commit()

    print(f"\n{B}{C}Summary{W}")
    print(f"  ─────────────────────────────────────────────")
    print(f"  On RTP:         {rtp_yes:3d} CUs")
    print(f"  Not on RTP:     {rtp_no:3d} CUs")
    print(f"  Signals added:  {sig_added}")
    total = db.query(Signal).count()
    print(f"  Total signals:  {total}")
    print(f"\n  {G}✅ Payment rails data seeded.{W}\n")
    db.close()


if __name__ == "__main__":
    main()
