"""
FintelliPro — News Signal Fetcher
====================================
Pulls news articles about companies in your DB from:
  1. Google News RSS   — company-specific search (free, no key)
  2. CUToday RSS       — credit union industry press (free)
  3. CUInsight RSS     — credit union industry press (free)
  4. NCUA Press RSS    — enforcement actions, regulatory news (free)

For each article Claude classifies it as a signal type and severity.
Runs in ~2 minutes for 50 CUs.

Run:
    python news_signals.py                    # fetch news for all CUs in DB
    python news_signals.py --company "BECU"   # fetch for one CU by name
    python news_signals.py --dry-run          # print articles without saving

Requires: pip install feedparser
"""

import sys, os, time, uuid, urllib.request, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.services.source_refs import web_source

try:
    import feedparser
except ImportError:
    print("Installing feedparser...")
    os.system(f"{sys.executable} -m pip install feedparser -q")
    import feedparser

import argparse
from datetime import datetime, timedelta
from loguru import logger

from app.db.database import SessionLocal, init_db
from app.models import Company, Signal
from app.core.config import settings

G="\033[92m"; Y="\033[93m"; C="\033[96m"; W="\033[0m"; B="\033[1m"
def ok(s):   print(f"  {G}✓{W} {s}")
def warn(s): print(f"  {Y}⚠{W}  {s}")
def hdr(s):  print(f"\n{B}{C}{s}{W}\n  {'─'*52}")
def info(s): print(f"  → {s}")

# ── RSS feed URLs ───────────────────────────────────────────────

def google_news_url(query: str) -> str:
    """Google News RSS for a specific search query."""
    q = urllib.request.quote(query)
    return f"https://news.google.com/rss/search?q={q}+credit+union&hl=en-US&gl=US&ceid=US:en"

# Industry-wide feeds — catch news about any CU
INDUSTRY_FEEDS = [
    ("CUToday",   "https://www.cutoday.info/feed/"),
    ("CUInsight", "https://www.cuinsight.com/feed/"),
    ("NCUA News", "https://ncua.gov/rss.xml"),
    ("American Banker CU", "https://www.americanbanker.com/tag/credit-unions.rss"),
]

# Keywords that indicate a high-value signal event
SIGNAL_KEYWORDS = {
    "growth": [
        "raised", "funding", "raise", "capital", "investment", "acquired", "merger",
        "acquisition", "partnership", "expanded", "growing", "growth", "hired",
        "appoints", "new ceo", "new cto", "new cdo", "chief digital", "chief technology",
        "milestone", "record assets", "record members", "fastest growing",
    ],
    "operational_gap": [
        "core conversion", "core replacement", "core modernization", "legacy system",
        "digital transformation", "new platform", "technology upgrade", "system migration",
        "modernize", "digital banking platform", "mobile banking launch",
    ],
    "pain_point": [
        "outage", "breach", "hack", "cyberattack", "complaint", "lawsuit", "fine",
        "penalty", "regulatory action", "enforcement", "investigation", "failure",
        "downtime", "fraud losses", "member complaints", "rating drops",
    ],
    "regulatory_risk": [
        "ncua", "cfpb", "enforcement action", "cease and desist", "letter of understanding",
        "consent order", "regulatory", "compliance", "examination", "supervision",
        "fednow", "faster payments", "open banking", "section 1033",
    ],
}

# ── Fetch RSS feeds ─────────────────────────────────────────────
def fetch_rss(url: str, timeout: int = 10) -> list[dict]:
    """Fetch and parse an RSS feed. Returns list of article dicts."""
    try:
        feed = feedparser.parse(url)
        articles = []
        cutoff = datetime.now() - timedelta(days=90)  # only last 90 days

        for entry in feed.entries[:20]:  # max 20 articles per feed
            # Parse date
            published = None
            if hasattr(entry, "published_parsed") and entry.published_parsed:
                try:
                    published = datetime(*entry.published_parsed[:6])
                except:
                    published = datetime.now()
            else:
                published = datetime.now()

            if published < cutoff:
                continue

            articles.append({
                "title":     getattr(entry, "title", ""),
                "summary":   getattr(entry, "summary", "") or getattr(entry, "description", ""),
                "url":       getattr(entry, "link", ""),
                "published": published.isoformat(),
                "source":    feed.feed.get("title", url),
            })

        return articles
    except Exception as e:
        logger.warning(f"RSS fetch failed for {url[:60]}: {e}")
        return []


def classify_signal_local(article: dict, cu_name: str) -> dict | None:
    """
    Classify an article as a signal using keyword matching.
    Returns signal dict or None if not relevant.

    In production: replace this with a Claude API call for
    much higher accuracy and nuanced classification.
    """
    text = f"{article['title']} {article['summary']}".lower()
    cu_lower = cu_name.lower()

    # Check if article mentions this specific CU
    cu_words = cu_lower.replace(" credit union", "").replace(" federal credit union", "").strip()
    is_company_specific = (
        cu_lower in text or
        cu_words in text or
        cu_name.split()[0].lower() in text  # first word of CU name
    )

    # Find matching signal type
    best_type = None
    best_count = 0
    matched_keywords = []

    for sig_type, keywords in SIGNAL_KEYWORDS.items():
        matches = [kw for kw in keywords if kw in text]
        if len(matches) > best_count:
            best_count = len(matches)
            best_type = sig_type
            matched_keywords = matches

    if not best_type or best_count == 0:
        return None

    # Calculate severity based on signal type and keyword strength
    severity_map = {
        "growth":           70 + min(20, best_count * 5),
        "operational_gap":  75 + min(15, best_count * 5),
        "pain_point":       78 + min(14, best_count * 4),
        "regulatory_risk":  72 + min(18, best_count * 6),
    }
    severity = severity_map.get(best_type, 70)

    # Boost severity if company-specific
    if is_company_specific:
        severity = min(95, severity + 10)

    label = f"News: {article['title'][:80]}" if len(article['title']) > 80 else f"News: {article['title']}"

    return {
        "signal_type":  best_type,
        "signal_label": label,
        "severity":     severity,
        "source":       f"news_{article['source'].lower().replace(' ','_')[:20]}",
        "url":          article["url"],
        "company_specific": is_company_specific,
        "matched_keywords": matched_keywords[:3],
    }


def classify_signal_claude(article: dict, cu_name: str) -> dict | None:
    """
    Use Claude AI to classify an article as a signal.
    More accurate than keyword matching — understands context and nuance.
    Falls back to local classification if no API key.
    """
    if not settings.ANTHROPIC_API_KEY:
        return classify_signal_local(article, cu_name)

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)

        prompt = f"""Analyze this news article about the credit union industry.

Credit Union we are tracking: {cu_name}
Article title: {article['title']}
Article summary: {article['summary'][:500]}
Published: {article['published']}

Classify this article and respond with ONLY valid JSON:
{{
  "is_relevant": true/false,
  "mentions_cu_directly": true/false,
  "signal_type": "growth" | "operational_gap" | "pain_point" | "regulatory_risk" | "none",
  "severity": 0-100,
  "reason": "one sentence why",
  "pitch_hook": "one sentence sales hook based on this news"
}}

Signal type guide:
- growth: funding, hiring, acquisition, new leadership, asset growth
- operational_gap: core migration, technology upgrade, digital transformation
- pain_point: outage, breach, complaint, fine, penalty, fraud
- regulatory_risk: ncua action, cfpb, compliance mandate, fednow
- none: not relevant to fintech sales

Only mark is_relevant=true if this article represents a genuine sales opportunity signal.
Severity 80+ = immediate outreach trigger. 60-79 = worth noting. Below 60 = skip."""

        resp = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=300,
            messages=[{"role": "user", "content": prompt}]
        )

        import json
        result = json.loads(resp.content[0].text.strip())

        if not result.get("is_relevant") or result.get("signal_type") == "none":
            return None

        return {
            "signal_type":  result["signal_type"],
            "signal_label": f"News: {article['title'][:100]}",
            "severity":     result["severity"],
            "source":       "news_ai_classified",
            "url":          article["url"],
            "company_specific": result.get("mentions_cu_directly", False),
            "pitch_hook":   result.get("pitch_hook", ""),
        }

    except Exception as e:
        logger.warning(f"Claude classification failed: {e} — falling back to keyword match")
        return classify_signal_local(article, cu_name)


def fetch_news_for_company(cu_name: str, use_claude: bool = True) -> list[dict]:
    """
    Fetch all relevant news signals for one credit union.
    1. Search Google News for the specific CU name
    2. Pull industry feeds and filter for mentions
    """
    signals = []
    seen_titles = set()

    # Search 1: Company-specific Google News
    url = google_news_url(f'"{cu_name}"')
    articles = fetch_rss(url)
    info(f"  Google News '{cu_name}': {len(articles)} articles")

    for article in articles:
        if article["title"] in seen_titles:
            continue
        seen_titles.add(article["title"])

        sig = (classify_signal_claude if use_claude else classify_signal_local)(article, cu_name)
        if sig:
            signals.append(sig)

    # Search 2: Industry feeds filtered by CU name
    for feed_name, feed_url in INDUSTRY_FEEDS[:2]:  # CUToday + CUInsight only
        articles = fetch_rss(feed_url)
        for article in articles:
            if article["title"] in seen_titles:
                continue

            # Only keep articles that mention this CU
            text = f"{article['title']} {article['summary']}".lower()
            cu_words = cu_name.lower().replace("credit union","").replace("federal","").strip()
            if cu_words not in text and cu_name.lower() not in text:
                continue

            seen_titles.add(article["title"])
            sig = (classify_signal_claude if use_claude else classify_signal_local)(article, cu_name)
            if sig:
                signals.append(sig)

    return signals


def save_signals(db, company_id: str, signals: list[dict], dry_run: bool = False):
    """Save news signals to the signals table, skipping duplicates."""
    saved = 0
    for sig in signals:
        # Check for duplicate (same label)
        existing = db.query(Signal).filter_by(
            company_id=company_id, signal_label=sig["signal_label"]
        ).first()
        if existing:
            continue

        if not dry_run:
            refs = web_source(sig.get("url") or "", label=sig.get("signal_label", "")[:80]) if sig.get("url") else {}
            db.add(Signal(
                id=str(uuid.uuid4()),
                company_id=company_id,
                signal_type=sig["signal_type"],
                signal_label=sig["signal_label"],
                severity=sig["severity"],
                source=sig["source"],
                is_active=True,
                **refs,
            ))
            saved += 1

    if not dry_run:
        db.commit()

    return saved


def main():
    parser = argparse.ArgumentParser(description="Fetch news signals for CUs in DB")
    parser.add_argument("--company", type=str, help="Filter to one company by name")
    parser.add_argument("--dry-run", action="store_true", help="Print signals without saving")
    parser.add_argument("--no-claude", action="store_true", help="Use keyword matching instead of Claude")
    args = parser.parse_args()

    use_claude = not args.no_claude and bool(settings.ANTHROPIC_API_KEY)
    if use_claude:
        info("Using Claude AI for signal classification (more accurate)")
    else:
        info("Using keyword matching for classification (add ANTHROPIC_API_KEY for better results)")

    init_db()
    db = SessionLocal()

    q = db.query(Company).filter_by(industry="credit_unions")
    if args.company:
        q = q.filter(Company.name.ilike(f"%{args.company}%"))
    companies = q.order_by(Company.opportunity_score.desc()).all()

    if not companies:
        print("No companies found. Run ncua_bulk_download.py first.")
        return

    print(f"\n{B}{C}FintelliPro — News Signal Fetcher{W}")
    print(f"  Companies: {len(companies)} · Claude: {use_claude} · Dry run: {args.dry_run}\n")

    total_new = 0
    for co in companies:
        hdr(f"{co.name}  (score: {co.opportunity_score})")
        signals = fetch_news_for_company(co.name, use_claude=use_claude)

        if not signals:
            info("No news signals found")
            continue

        for sig in signals:
            flag = "🎯" if sig.get("company_specific") else "📰"
            print(f"  {flag} [{sig['signal_type']:15s} | sev:{sig['severity']:3d}] {sig['signal_label'][:70]}")
            if sig.get("pitch_hook"):
                print(f"     Hook: {sig['pitch_hook'][:80]}")

        saved = save_signals(db, co.id, signals, dry_run=args.dry_run)
        ok(f"Saved {saved} new signals")
        total_new += saved

        # Rate limit — be polite to Google News RSS
        time.sleep(1.5)

    print(f"\n{G}✅ Done — {total_new} new signals added across {len(companies)} CUs{W}\n")
    db.close()


if __name__ == "__main__":
    main()
