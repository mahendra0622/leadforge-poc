"""
FintelliPro — Web Scraper
===========================
Visits each CU's website + job postings to extract:
  1. Core processor name (from job postings — most reliable method)
  2. Mobile app existence + App Store rating
  3. API / developer portal presence
  4. Digital maturity score (updated from real evidence)

Uses Playwright (headless Chrome) so JavaScript-heavy sites work fine.

Run:
    python web_scraper.py                    # scrape all CUs missing core data
    python web_scraper.py --limit 10         # scrape first 10 only
    python web_scraper.py --company "BECU"   # scrape one specific CU
    python web_scraper.py --dry-run          # print findings without saving

Setup (first time only):
    playwright install chromium
"""

import sys, os, re, time, asyncio, argparse, uuid
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.services.source_refs import web_source

from loguru import logger
from app.db.database import SessionLocal, init_db
from app.models import Company, Signal

G="\033[92m"; Y="\033[93m"; C="\033[96m"; W="\033[0m"; B="\033[1m"; R="\033[91m"
def ok(s):   print(f"  {G}✓{W} {s}")
def warn(s): print(f"  {Y}⚠{W}  {s}")
def info(s): print(f"  → {s}")
def err(s):  print(f"  {R}✗{W} {s}")
def hdr(s):  print(f"\n{B}{C}{s}{W}\n  {'─'*54}")


# ── Core processor keyword dictionary ──────────────────────────
# Maps keywords found in job postings → core processor name + maturity score
CORE_KEYWORDS = {
    # Legacy cores — maturity 2
    "symitar":       ("Symitar (Jack Henry)", 2),
    "episys":        ("Episys (Symitar)",     2),
    "cu*base":       ("Jack Henry CU*BASE",   2),
    "cubase":        ("Jack Henry CU*BASE",   2),
    "jack henry":    ("Jack Henry",           2),
    "sharetec":      ("Sharetec",             2),
    "open solutions":("Open Solutions",       2),
    "oss":           ("Open Solutions",       2),
    "data center":   ("DataCenter Inc",       2),
    "dpcu":          ("DPCU",                 2),

    # Mid-tier cores — maturity 3
    "fiserv dna":    ("Fiserv DNA",           3),
    "fiserv":        ("Fiserv",               3),
    "dna core":      ("Fiserv DNA",           3),
    "portico":       ("Fiserv Portico",       3),
    "gold":          ("Fiserv GOLD",          3),
    "spectrum":      ("Fiserv Spectrum",      3),

    # Modern cores — maturity 4
    "corelation":    ("Corelation Keystone",  4),
    "keystone":      ("Corelation Keystone",  4),
    "nymbus":        ("Nymbus",               4),
    "symxchange":    ("Symitar SymXchange",   4),

    # Cloud-native — maturity 5
    "alkami":        ("Alkami",               5),
    "q2":            ("Q2",                   5),
    "narmi":         ("Narmi",                5),
    "mambu":         ("Mambu",                5),
    "nc suite":      ("NCR NC Suite",         4),
}

# Keywords indicating FedNow / real-time payments interest
FEDNOW_KEYWORDS = [
    "fednow", "fed now", "real-time payments", "real time payments",
    "rtp", "instant payments", "faster payments", "zelle",
]

# Keywords indicating digital transformation initiative
DIGITAL_KEYWORDS = [
    "digital transformation", "digital banking", "mobile-first",
    "api-first", "fintech", "digital strategy", "core modernization",
    "core migration", "technology modernization",
]

# App store rating thresholds
RATING_PAIN_THRESHOLD = 3.5   # below this = pain_point signal
RATING_GOOD_THRESHOLD = 4.2   # above this = growth signal (competitive differentiator)


# ── Scraping functions ──────────────────────────────────────────

async def setup_browser():
    """Launch headless Chromium browser."""
    from playwright.async_api import async_playwright
    playwright = await async_playwright().start()
    browser = await playwright.chromium.launch(
        headless=True,
        args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"]
    )
    context = await browser.new_context(
        user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        viewport={"width": 1280, "height": 800},
        java_script_enabled=True,
    )
    return playwright, browser, context


async def safe_goto(page, url: str, timeout: int = 12000) -> bool:
    """Navigate to URL, return True if successful."""
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=timeout)
        return True
    except Exception as e:
        logger.debug(f"Navigation failed for {url}: {str(e)[:60]}")
        return False


async def get_page_text(page) -> str:
    """Extract all visible text from current page."""
    try:
        text = await page.evaluate("() => document.body.innerText")
        return text.lower() if text else ""
    except:
        return ""


async def scrape_cu_website(page, domain: str) -> dict:
    """
    Visit the CU's website. Look for:
    - Mobile app links (iOS/Android)
    - API / developer portal
    - Digital banking page
    - Any core processor mentions
    """
    result = {
        "has_mobile_app": False,
        "has_api_docs": False,
        "has_digital_banking": False,
        "core_from_website": None,
        "maturity_from_website": None,
        "website_text": "",
    }

    if not domain or "example" in domain:
        return result

    url = f"https://{domain}" if not domain.startswith("http") else domain
    success = await safe_goto(page, url)
    if not success:
        url = f"http://{domain}"
        success = await safe_goto(page, url)
    if not success:
        return result

    text = await get_page_text(page)
    result["website_text"] = text[:2000]  # save first 2000 chars

    # Check for mobile app
    result["has_mobile_app"] = any(kw in text for kw in [
        "app store", "google play", "download our app", "mobile app",
        "ios app", "android app", "download the app",
    ])

    # Check for API/developer portal
    result["has_api_docs"] = any(kw in text for kw in [
        "api", "developer portal", "developer docs", "open banking",
        "developer.cu", "sandbox", "api documentation",
    ])

    # Check for digital banking
    result["has_digital_banking"] = any(kw in text for kw in [
        "online banking", "digital banking", "mobile banking", "e-banking",
    ])

    # Check for core processor mentions on website
    for keyword, (core_name, maturity) in CORE_KEYWORDS.items():
        if keyword in text:
            result["core_from_website"] = core_name
            result["maturity_from_website"] = maturity
            break

    return result


async def scrape_job_postings(page, cu_name: str, state: str) -> dict:
    """
    Search Indeed for job postings by this CU.
    Job postings are the MOST RELIABLE source for core processor data.
    "3+ years Symitar/Episys experience required" = confirmed core.
    """
    result = {
        "core_from_jobs": None,
        "maturity_from_jobs": None,
        "has_digital_hiring": False,
        "has_payments_hiring": False,
        "has_fednow_hiring": False,
        "job_text": "",
    }

    # Clean up CU name for search
    search_name = cu_name.replace(" Federal Credit Union", "").replace(" Credit Union", "")
    search_name = search_name.replace(" FCU", "").replace(" CU", "").strip()

    # Search Indeed
    search_url = (
        f"https://www.indeed.com/jobs?q={search_name.replace(' ', '+')}"
        f"+credit+union&l={state}&sort=date"
    )

    success = await safe_goto(page, search_url, timeout=15000)
    if not success:
        return result

    await page.wait_for_timeout(2000)  # let JS render
    text = await get_page_text(page)
    result["job_text"] = text[:3000]

    # Look for core processor in job descriptions
    for keyword, (core_name, maturity) in CORE_KEYWORDS.items():
        if keyword in text:
            result["core_from_jobs"] = core_name
            result["maturity_from_jobs"] = maturity
            logger.info(f"  Found core '{core_name}' in job posting for {cu_name}")
            break

    # Check for digital/payments hiring signals
    result["has_digital_hiring"] = any(kw in text for kw in DIGITAL_KEYWORDS)
    result["has_payments_hiring"] = any(kw in text for kw in [
        "payments", "payment", "payment processing", "payment systems",
    ])
    result["has_fednow_hiring"] = any(kw in text for kw in FEDNOW_KEYWORDS)

    return result


async def scrape_app_store(page, cu_name: str) -> dict:
    """
    Search Apple App Store for this CU's mobile app.
    Returns rating and review count.
    """
    result = {
        "ios_rating": None,
        "ios_review_count": None,
        "has_ios_app": False,
    }

    search_name = cu_name.replace(" Federal Credit Union", "").replace(" Credit Union", "")
    search_name = search_name.replace(" FCU", "").replace(" CU", "").strip()

    url = f"https://itunes.apple.com/search?term={search_name.replace(' ', '+')}" \
          f"+credit+union&entity=software&country=us&limit=3"

    try:
        import urllib.request, json
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read())
            results = data.get("results", [])
            if results:
                app = results[0]
                result["ios_rating"] = app.get("averageUserRating")
                result["ios_review_count"] = app.get("userRatingCount")
                result["has_ios_app"] = True
                logger.info(f"  App Store: {app.get('trackName')} — {result['ios_rating']}★ ({result['ios_review_count']} reviews)")
    except Exception as e:
        logger.debug(f"App Store search failed for {cu_name}: {e}")

    return result


def determine_core_and_maturity(website_result: dict, job_result: dict) -> tuple:
    """
    Pick the best core + maturity from all sources.
    Priority: job postings > website > asset-size estimate.
    """
    # Job postings are most reliable
    if job_result.get("core_from_jobs"):
        return job_result["core_from_jobs"], job_result["maturity_from_jobs"]

    # Website mentions are second best
    if website_result.get("core_from_website"):
        return website_result["core_from_website"], website_result["maturity_from_website"]

    return None, None


def build_signals_from_scrape(
    co: Company,
    website: dict,
    jobs: dict,
    app: dict,
) -> list:
    """Build signal records from scraping findings."""
    signals = []
    domain = co.website or ""
    if domain:
        domain = domain.replace("https://","").replace("http://","").replace("www.","").split("/")[0]
    site_url = f"https://{domain}" if domain else None
    _web = web_source(site_url, label=f"{co.name} website") if site_url else {}

    search_name = co.name.replace(" Federal Credit Union", "").replace(" Credit Union", "").strip()
    indeed_url = f"https://www.indeed.com/jobs?q={search_name.replace(' ', '+')}+credit+union"
    _jobs = web_source(indeed_url, label=f"{co.name} — Indeed job posting")

    # No mobile app
    if not website.get("has_mobile_app") and not app.get("has_ios_app"):
        signals.append({
            "type":     "operational_gap",
            "label":    f"No mobile banking app detected on {co.website or co.name + ' website'}",
            "severity": 74,
            "source":   "web_scraper",
            **_web,
        })
    elif app.get("has_ios_app"):
        rating = app.get("ios_rating")
        reviews = app.get("ios_review_count", 0)
        if rating and rating < RATING_PAIN_THRESHOLD:
            signals.append({
                "type":     "pain_point",
                "label":    f"Mobile app rating {rating:.1f}★ ({reviews:,} reviews) — member friction",
                "severity": int(90 - (rating * 10)),
                "source":   "web_scraper",
                **_web,
            })
        elif rating and rating >= RATING_GOOD_THRESHOLD:
            signals.append({
                "type":     "growth",
                "label":    f"Strong mobile app: {rating:.1f}★ ({reviews:,} reviews) — digital momentum",
                "severity": 65,
                "source":   "web_scraper",
                **_web,
            })

    # No API docs
    if not website.get("has_api_docs"):
        signals.append({
            "type":     "operational_gap",
            "label":    "No API/developer documentation found — open banking gap",
            "severity": 68,
            "source":   "web_scraper",
            **_web,
        })

    # Digital hiring = budget signal
    if jobs.get("has_digital_hiring"):
        signals.append({
            "type":     "growth",
            "label":    "Actively hiring for digital transformation roles — budget allocated",
            "severity": 76,
            "source":   "web_scraper",
            **_jobs,
        })

    # FedNow hiring = very hot signal
    if jobs.get("has_fednow_hiring"):
        signals.append({
            "type":     "growth",
            "label":    "Job posting mentions FedNow — actively evaluating real-time payments",
            "severity": 90,
            "source":   "web_scraper",
            **_jobs,
        })

    # Payments hiring
    if jobs.get("has_payments_hiring") and not jobs.get("has_fednow_hiring"):
        signals.append({
            "type":     "growth",
            "label":    "Hiring for payments roles — payments infrastructure investment",
            "severity": 72,
            "source":   "web_scraper",
            **_jobs,
        })

    return signals


async def scrape_company(page, co: Company, dry_run: bool = False) -> dict:
    """Full scrape pipeline for one company."""
    domain = co.website or ""
    if domain:
        domain = domain.replace("https://","").replace("http://","").replace("www.","").split("/")[0]

    state = co.hq_state or ""

    info(f"Website: {domain or '(none)'}")

    # 1. Visit website
    website = await scrape_cu_website(page, domain)
    if website.get("has_mobile_app"):    info("Has mobile app link")
    if website.get("has_api_docs"):       info("Has API/developer docs")
    if website.get("core_from_website"): info(f"Core on website: {website['core_from_website']}")

    # 2. Search job postings
    await page.wait_for_timeout(1000)
    info("Searching job postings (Indeed)...")
    jobs = await scrape_job_postings(page, co.name, state)
    if jobs.get("core_from_jobs"):        info(f"Core in jobs: {jobs['core_from_jobs']}")
    if jobs.get("has_fednow_hiring"):     info("FedNow mentioned in job posting!")
    if jobs.get("has_digital_hiring"):    info("Digital transformation hiring detected")

    # 3. Check App Store
    info("Checking App Store...")
    app = await scrape_app_store(page, co.name)
    if app.get("has_ios_app"):
        info(f"iOS app found: {app.get('ios_rating')}★")

    # 4. Determine core + maturity
    core, maturity = determine_core_and_maturity(website, jobs)

    # 5. Build signals
    signals = build_signals_from_scrape(co, website, jobs, app)

    return {
        "core":     core,
        "maturity": maturity,
        "signals":  signals,
        "website":  website,
        "jobs":     jobs,
        "app":      app,
    }


def save_results(db, co: Company, results: dict):
    """Persist scraping results to DB."""
    changed = False

    # Update core processor
    if results["core"] and not (co.tech_stack and co.tech_stack[0]):
        co.tech_stack = [results["core"]]
        rd = co.regulatory_data or {}
        rd["core_processor"] = results["core"]
        co.regulatory_data = rd
        changed = True
        ok(f"Core: {results['core']}")

    # Update maturity
    if results["maturity"] and results["maturity"] != co.digital_maturity:
        old = co.digital_maturity
        co.digital_maturity = results["maturity"]
        changed = True
        ok(f"Maturity: {old} → {results['maturity']}")

    # Update opportunity score if maturity changed
    if changed and results["maturity"]:
        from app.models import Signal as Sig
        sigs = db.query(Sig).filter_by(company_id=co.id, is_active=True).all()
        pain   = [s.severity for s in sigs if s.signal_type in ("pain_point","operational_gap")]
        growth = [s.severity for s in sigs if s.signal_type == "growth"]
        pa = sum(pain)/len(pain) if pain else 40
        ga = sum(growth)/len(growth) if growth else 30
        mat = results["maturity"] or co.digital_maturity or 2
        gap  = (6 - mat) * 18
        base = gap*0.30 + pa*0.25 + ga*0.20 + 85*0.15 + 80*0.10
        co.opportunity_score = min(100, int(base * 1.15))
        ok(f"Score updated: {co.opportunity_score}")

    # Save new signals (skip duplicates)
    sig_count = 0
    for sig in results["signals"]:
        exists = db.query(Signal).filter_by(
            company_id=co.id, signal_label=sig["label"]
        ).first()
        if not exists:
            db.add(Signal(
                id=str(uuid.uuid4()),
                company_id=co.id,
                signal_type=sig["type"],
                signal_label=sig["label"],
                severity=sig["severity"],
                source=sig["source"],
                source_url=sig.get("source_url"),
                source_file=sig.get("source_file"),
                source_page=sig.get("source_page"),
                source_label=sig.get("source_label"),
                is_active=True,
            ))
            sig_count += 1

    if sig_count:
        ok(f"Added {sig_count} new signals")

    if changed or sig_count:
        db.commit()

    return changed


# ── Main ────────────────────────────────────────────────────────

async def main_async(args):
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        err("Playwright not installed. Run: pip install playwright && playwright install chromium")
        return

    init_db()
    db = SessionLocal()

    # Get companies to scrape
    q = db.query(Company).filter_by(industry="credit_unions")
    if args.company:
        q = q.filter(Company.name.ilike(f"%{args.company}%"))
    else:
        # Prioritise: highest score AND missing core processor
        q = q.order_by(Company.opportunity_score.desc())

    companies = q.all()

    if not args.company:
        # Filter to those missing core processor data (most need it)
        missing_core = [c for c in companies if not (c.tech_stack and c.tech_stack[0])]
        has_core     = [c for c in companies if c.tech_stack and c.tech_stack[0]]
        # Scrape missing-core first, then refresh existing
        companies = missing_core + has_core

    if args.limit:
        companies = companies[:args.limit]

    print(f"\n{B}{C}FintelliPro — Web Scraper{W}")
    print(f"  Companies to scrape: {len(companies)}")
    print(f"  Dry run: {args.dry_run}\n")

    if not companies:
        print("  No companies found.")
        return

    # Launch browser
    hdr("Launching headless Chromium")
    playwright, browser, context = await setup_browser()
    page = await context.new_page()
    ok("Browser ready")

    scraped = 0
    updated = 0
    errors  = 0

    for i, co in enumerate(companies):
        hdr(f"[{i+1}/{len(companies)}] {co.name}  (score: {co.opportunity_score})")

        try:
            results = await scrape_company(page, co, dry_run=args.dry_run)

            if not args.dry_run:
                changed = save_results(db, co, results)
                if changed: updated += 1
            else:
                # Dry run — just print findings
                print(f"  Core found:  {results['core'] or '—'}")
                print(f"  Maturity:    {results['maturity'] or '—'}")
                print(f"  Signals:     {len(results['signals'])}")
                for s in results["signals"]:
                    print(f"    [{s['type']:15s}|{s['severity']:3d}] {s['label'][:65]}")

            scraped += 1

        except Exception as e:
            err(f"Scrape failed: {str(e)[:80]}")
            errors += 1

        # Polite delay between requests
        await asyncio.sleep(2.5)

    # Cleanup
    await browser.close()
    await playwright.stop()

    # Summary
    print(f"\n{B}{C}Summary{W}\n  {'─'*54}")
    print(f"  Companies scraped: {scraped}")
    print(f"  Records updated:   {updated}")
    print(f"  Errors:            {errors}")

    # Show core processor coverage
    all_cos = db.query(Company).filter_by(industry="credit_unions").all()
    with_core = sum(1 for c in all_cos if c.tech_stack and c.tech_stack[0])
    print(f"  Core data now:     {with_core}/{len(all_cos)} CUs ({with_core/len(all_cos)*100:.0f}%)")

    if not args.dry_run:
        print(f"\n  {G}Refresh http://localhost:3000 to see updated scores{W}\n")

    db.close()


def main():
    parser = argparse.ArgumentParser(description="Scrape CU websites for core processor and digital maturity data")
    parser.add_argument("--company", type=str, help="Scrape one company by name")
    parser.add_argument("--limit", type=int, help="Max number of companies to scrape")
    parser.add_argument("--dry-run", action="store_true", help="Print findings without saving to DB")
    args = parser.parse_args()

    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
