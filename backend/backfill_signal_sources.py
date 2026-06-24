"""
backfill_signal_sources.py
=============================
One-time script to backfill source_url / source_file / source_page /
source_label on every EXISTING signal already in the database that
doesn't have them yet.

Since old signals don't store which specific article/page they came
from, we backfill at the best available granularity:

  - signals with source == "ncua_5300" or similar      → NCUA bulk file (no page, it's CSV/TXT data)
  - signals with source == "cuna_intelligence"          → CUNA advocacy page URL
  - signals with source == "google_news" / "news_signals" → best-effort: re-search
    Google News for the CU name to find the most likely matching article URL
  - signals with source == "web_scraper"                → the CU's own website URL
  - anything else / unknown                              → labelled "Source not recorded"
    (we never fabricate a fake citation)

Run:
    python backfill_signal_sources.py             # all signals missing source refs
    python backfill_signal_sources.py --dry-run    # preview without writing
    python backfill_signal_sources.py --limit 50   # test on a small batch first
"""

import os
import sys
import argparse
import urllib.request
import urllib.parse
import re

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.db.database import SessionLocal
from app.models import Signal, Company
from app.services.source_refs import (
    web_source, file_source, ncua_source, cuna_source, format_hover_text
)

G = "\033[92m"; Y = "\033[93m"; W = "\033[0m"; R = "\033[91m"


def guess_news_url(cu_name: str, signal_label: str) -> dict:
    """
    Best-effort: re-search Google News RSS for this CU and try to find
    an article whose title overlaps with the signal label. If nothing
    matches well, fall back to a generic search-results link (still
    useful — clicking it shows relevant articles) rather than no link.
    """
    query = urllib.parse.quote(f"{cu_name} credit union")
    search_url = f"https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en"

    try:
        req = urllib.request.Request(search_url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=6) as resp:
            content = resp.read().decode("utf-8", errors="ignore")

        items = re.findall(r"<item>(.*?)</item>", content, re.DOTALL)[:10]
        label_words = set(re.findall(r"\w+", signal_label.lower())) - {
            "the", "a", "an", "and", "or", "for", "with", "on", "in", "of", "to"
        }

        best_match, best_score = None, 0
        for item in items:
            title_m = re.search(r"<title><!\[CDATA\[(.*?)\]\]></title>", item)
            link_m  = re.search(r"<link>(.*?)</link>", item)
            if not (title_m and link_m):
                continue
            title = title_m.group(1)
            title_words = set(re.findall(r"\w+", title.lower()))
            score = len(label_words & title_words)
            if score > best_score:
                best_score, best_match = score, (title, link_m.group(1))

        if best_match and best_score >= 2:
            title, link = best_match
            return web_source(link, label=title[:80])

        # Fallback: generic search results link, clearly labelled as such
        return web_source(
            f"https://news.google.com/search?q={query}",
            label="Google News search (exact article not recorded)"
        )

    except Exception:
        return {
            "source_url": None, "source_file": None,
            "source_page": None, "source_label": "Source not recorded"
        }


def backfill(dry_run: bool = False, limit: int = None):
    db = SessionLocal()

    signals = db.query(Signal).filter(
        Signal.source_url.is_(None),
        Signal.source_file.is_(None),
    ).all()

    if limit:
        signals = signals[:limit]

    print(f"\nFound {len(signals)} signals missing source references.")
    print(f"Dry run: {dry_run}\n")

    company_cache = {}
    updated, skipped = 0, 0

    for sig in signals:
        if sig.company_id not in company_cache:
            company_cache[sig.company_id] = db.query(Company).filter_by(
                id=sig.company_id).first()
        company = company_cache[sig.company_id]
        cu_name = company.name if company else "Unknown CU"

        src = (sig.source or "").lower()
        refs = None

        if "ncua" in src or "5300" in src or "regulatory" in src:
            refs = ncua_source()

        elif "cuna" in src:
            refs = cuna_source()

        elif "news" in src or "rss" in src:
            refs = guess_news_url(cu_name, sig.signal_label or "")

        elif "scraper" in src or "web" in src:
            website = company.website if company and company.website else None
            refs = web_source(website, label=f"{cu_name} website") if website else None

        if not refs:
            refs = {
                "source_url": None, "source_file": None,
                "source_page": None, "source_label": "Source not recorded"
            }
            skipped += 1
        else:
            updated += 1

        print(f"  [{sig.signal_type:18s}] {cu_name[:30]:30s} → {refs['source_label']}")

        if not dry_run:
            sig.source_url   = refs["source_url"]
            sig.source_file  = refs["source_file"]
            sig.source_page  = refs["source_page"]
            sig.source_label = refs["source_label"]

    if not dry_run:
        db.commit()

    print(f"\n{'─'*50}")
    print(f"Updated with a real source: {updated}")
    print(f"Marked 'Source not recorded': {skipped}")
    if dry_run:
        print(f"\n(dry run — nothing was written. Re-run without --dry-run to save)")
    db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()
    backfill(dry_run=args.dry_run, limit=args.limit)
