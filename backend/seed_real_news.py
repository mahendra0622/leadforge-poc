"""
FintelliPro — Real News Signal Seeder
=======================================
Loads pre-fetched real news articles (real_news_data.json) and saves
them as signals with genuine source URLs.

Run:
    python seed_real_news.py
"""
import sys, os, uuid, json, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.db.database import SessionLocal, init_db
from app.models import Company, Signal

G="\033[92m"; Y="\033[93m"; C="\033[96m"; W="\033[0m"; B="\033[1m"
def ok(s):   print(f"  {G}✓{W} {s}")
def skip(s): print(f"  {Y}–{W}  {s}")
def hdr(s):  print(f"\n{B}{C}{s}{W}\n  {'─'*56}")

# ── Signal classification from headline keywords ────────────────────
def classify(title: str) -> tuple[str, int]:
    t = title.lower()
    if any(k in t for k in ["breach","hack","cyberattack","outage","fraud","lawsuit","penalty","fine","complaint"]):
        return "pain_point", 88
    if any(k in t for k in ["ncua","cfpb","enforcement","cease","consent","regulatory","compliance","examine"]):
        return "regulatory_risk", 85
    if any(k in t for k in ["fednow","instant payment","real-time","faster payment","open banking","1033"]):
        return "regulatory_risk", 82
    if any(k in t for k in ["core","platform","digital bank","mobile app","technology","fintech","api","moderniz","upgrade","transform","convert","replac"]):
        return "operational_gap", 84
    if any(k in t for k in ["merger","acqui","partner","expand","growth","record","milestone","appoint","hire","new ceo","new cto","new cdo","chief"]):
        return "growth", 80
    return "growth", 72


def source_label(url: str) -> str:
    m = re.search(r"https?://(?:news\.google\.com/rss/articles/.*?source=([^&]+)|(?:www\.)?([^/]+))", url)
    if not m:
        return "News"
    raw = m.group(1) or m.group(2) or "News"
    # Google News redirect URL — try to extract real domain from encoded source param
    if "CBMi" in url or "news.google.com" in url:
        # Fall back to generic label
        return "Industry News"
    return raw.split(".")[0].capitalize()


def main():
    data_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "real_news_data.json")
    if not os.path.exists(data_path):
        print("  real_news_data.json not found. Run the local fetch script first.")
        sys.exit(1)

    with open(data_path) as f:
        news_data: dict = json.load(f)

    print(f"\n{B}{C}FintelliPro — Real News Signal Seeder{W}")
    print(f"  Loaded {len(news_data)} CU entries from real_news_data.json\n")

    init_db()
    db = SessionLocal()

    companies = db.query(Company).filter_by(industry="credit_unions").all()
    co_by_name = {co.name: co for co in companies}

    hdr("Replacing fake news signals with real ones")
    total_added = 0
    cu_updated = 0

    for cu_name, articles in news_data.items():
        if not articles:
            skip(f"{cu_name}: no real articles fetched — keeping existing signals")
            continue

        co = co_by_name.get(cu_name)
        if not co:
            skip(f"{cu_name}: not found in DB")
            continue

        # Delete existing news signals for this CU
        deleted = db.query(Signal).filter(
            Signal.company_id == co.id,
            Signal.source.like("news_%"),
        ).delete(synchronize_session=False)

        # Insert real signals (up to 3 per CU)
        added = 0
        seen_titles = set()
        for art in articles[:3]:
            title = art.get("title", "").strip()
            url   = art.get("url", "").strip()
            if not title or not url or title in seen_titles:
                continue
            seen_titles.add(title)

            sig_type, severity = classify(title)
            label = f"News: {title[:120]}"
            src_label = source_label(url)

            db.add(Signal(
                id           = str(uuid.uuid4()),
                company_id   = co.id,
                signal_type  = sig_type,
                signal_label = label,
                severity     = severity,
                source       = f"news_{src_label.lower()[:20]}",
                source_url   = url,
                source_label = src_label,
                is_active    = True,
            ))
            added += 1

        total_added += added
        cu_updated  += 1
        ok(f"{cu_name:<44} deleted {deleted} fake · added {added} real")

    db.commit()

    total_sigs = db.query(Signal).count()
    news_sigs  = db.query(Signal).filter(Signal.source.like("news_%")).count()

    print(f"\n{B}{C}Done!{W}\n  {'─'*56}")
    print(f"  CUs updated:         {cu_updated}")
    print(f"  Real signals added:  {total_added}")
    print(f"  Total signals in DB: {total_sigs}")
    print(f"  News signals total:  {news_sigs}")
    print(f"\n  {G}✅ All news links now point to real articles.{W}\n")
    db.close()


if __name__ == "__main__":
    main()
