"""
FintelliPro — Community Bank News Signals
==========================================
Fetches Google News RSS for each community bank and creates news signals.
Same pattern as seed_real_news.py for credit unions.

Run:
    python seed_bank_news.py
"""
import sys, os, uuid, re, time, urllib.request, urllib.parse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    import feedparser
except ImportError:
    os.system("pip install feedparser -q")
    import feedparser

from app.db.database import SessionLocal, init_db
from app.models import Company, Signal

G="\033[92m"; Y="\033[93m"; C="\033[96m"; W="\033[0m"; B="\033[1m"

RELEVANT_KEYWORDS = [
    "digital", "fintech", "technology", "core", "banking", "mobile", "app",
    "acquisition", "merger", "partnership", "platform", "cloud", "fraud",
    "loan", "deposit", "growth", "expansion", "branch", "layoff", "hiring",
]

SIGNAL_KEYWORDS = {
    "acquisition":    ("growth",        82),
    "merger":         ("growth",        80),
    "partnership":    ("growth",        75),
    "digital":        ("growth",        70),
    "fintech":        ("growth",        72),
    "core banking":   ("operational_gap", 80),
    "system upgrade": ("operational_gap", 78),
    "new platform":   ("growth",        74),
    "fraud":          ("pain_point",    76),
    "layoff":         ("pain_point",    70),
    "cybersecurity":  ("pain_point",    74),
    "data breach":    ("pain_point",    85),
    "regulatory":     ("pain_point",    72),
    "fine":           ("pain_point",    78),
}

def classify_article(title: str, summary: str) -> tuple[str, int] | None:
    text = (title + " " + summary).lower()
    for kw, (sig_type, sev) in SIGNAL_KEYWORDS.items():
        if kw in text:
            return sig_type, sev
    # Generic news signal if relevant
    if any(kw in text for kw in RELEVANT_KEYWORDS):
        return "growth", 60
    return None


def fetch_news(bank_name: str, max_articles: int = 4) -> list[dict]:
    query = urllib.parse.quote(f'"{bank_name}" bank')
    url = f"https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en"
    try:
        feed = feedparser.parse(url)
        articles = []
        for entry in feed.entries[:max_articles]:
            title = entry.get("title", "")
            summary = re.sub(r"<[^>]+>", "", entry.get("summary", ""))
            link = entry.get("link", "")
            # Convert Google redirect to direct article URL
            if "/articles/" in link:
                link = link.replace("/rss/articles/", "/articles/")
            articles.append({"title": title, "summary": summary, "url": link})
        return articles
    except Exception as e:
        print(f"    {Y}RSS error for {bank_name}: {e}{W}")
        return []


def main():
    print(f"\n{B}{C}FintelliPro — Community Bank News Seed{W}")

    init_db()
    db = SessionLocal()
    banks = db.query(Company).filter_by(industry="community_banks").all()
    print(f"  Found {len(banks)} community banks\n")

    if not banks:
        print(f"  {Y}No community banks found. Run seed_community_banks.py first.{W}")
        db.close()
        return

    total_signals = 0

    for bank in banks:
        # Remove existing bank news signals
        db.query(Signal).filter(
            Signal.company_id == bank.id,
            Signal.source == "news",
        ).delete(synchronize_session=False)

        articles = fetch_news(bank.name)
        added = 0

        for art in articles:
            result = classify_article(art["title"], art["summary"])
            if not result:
                continue
            sig_type, sev = result
            db.add(Signal(
                id           = str(uuid.uuid4()),
                company_id   = bank.id,
                signal_type  = sig_type,
                signal_label = art["title"][:250],
                severity     = sev,
                source       = "news",
                source_url   = art["url"],
                is_active    = True,
            ))
            added += 1

        total_signals += added
        icon = f"{G}✓{W}" if added > 0 else f"{Y}—{W}"
        print(f"  {icon} {bank.name[:45]:<45} {added} news signals")
        time.sleep(0.5)  # polite rate limit for Google News

    db.commit()

    print(f"\n{B}{C}Summary{W}")
    print(f"  News signals added: {total_signals}")
    print(f"\n  {G}✅ Bank news signals seeded.{W}\n")
    db.close()


if __name__ == "__main__":
    main()
