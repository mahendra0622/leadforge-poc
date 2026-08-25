"""
Fix news signal source_urls — replaces fake article URLs with
real Google News search URLs so every link works.

Run:
    python fix_news_signal_urls.py
"""
import sys, os, urllib.parse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.db.database import SessionLocal, init_db
from app.models import Company, Signal
from sqlalchemy.orm import joinedload

G="\033[92m"; W="\033[0m"; B="\033[1m"; C="\033[96m"

# Map signal_type -> fallback search topic when we can't parse the label
TOPIC_FALLBACK = {
    "growth":           "growth technology digital banking",
    "operational_gap":  "core conversion digital transformation fintech",
    "regulatory_risk":  "NCUA FedNow compliance regulatory",
    "pain_point":       "outage fraud security incident",
}


def gnews(cu_name: str, topic: str) -> str:
    q = urllib.parse.quote(f'"{cu_name}" {topic}')
    return f"https://news.google.com/search?q={q}&hl=en-US&gl=US&ceid=US%3Aen"


def is_fake_url(url: str) -> bool:
    """Returns True if this looks like a templated fake URL."""
    if not url:
        return True
    fake_domains = [
        "cuinsight.com/press-release/",
        "cutoday.info/Fresh-Today/",
        "americanbanker.com/creditunions/",
        "cutimes.com/2025/",
        "finovate.com/fintech/2025/",
        "paymentsdive.com/news/",
        "bai.org/banking-strategies/",
        "ncua.gov/press-releases/2025/",
        "ncua.gov/regulation-supervision/regulatory-alerts/",
        "consumerfinance.gov/complaint-database/",
        "databreaches.net/2025/",
    ]
    return any(p in url for p in fake_domains)


def extract_topic(label: str, sig_type: str) -> str:
    """Pull useful search keywords from a signal label."""
    # Strip "News: " prefix
    text = label.removeprefix("News: ").strip()

    # Pick the most informative fragment (after em-dash if present)
    if " — " in text:
        text = text.split(" — ")[1]

    # Remove the CU name (often the first several words before a verb)
    # Just use the last ~6 words as topic keywords
    words = text.split()
    topic = " ".join(words[-6:]) if len(words) > 6 else text
    return topic or TOPIC_FALLBACK.get(sig_type, "credit union technology")


def main():
    print(f"\n{B}{C}Fix news signal source_urls → Google News search URLs{W}\n")

    init_db()
    db = SessionLocal()

    # Load all news signals with their company
    sigs = (
        db.query(Signal)
          .options(joinedload(Signal.company))
          .filter(Signal.source.like("news_%"))
          .all()
    )

    print(f"  Found {len(sigs)} news signals total")

    fixed = 0
    for s in sigs:
        if not is_fake_url(s.source_url):
            continue  # already a real or Google News URL

        cu_name = s.company.name if s.company else "credit union"
        topic   = extract_topic(s.signal_label or "", s.signal_type or "growth")
        new_url = gnews(cu_name, topic)
        s.source_url = new_url
        fixed += 1

    db.commit()
    print(f"  {G}✓{W} Fixed {fixed} fake URLs → Google News search URLs")
    print(f"  Skipped {len(sigs) - fixed} signals (already valid URLs)\n")
    db.close()


if __name__ == "__main__":
    main()
