"""
app/services/company_scraper.py
==================================
Scrapes a company's own website (the user's company, in Settings) to
auto-fill the product profile fields used for AI outreach personalisation.

Crawls: homepage + common pages (/about, /product(s), /solutions,
/services, /company) — same pattern as Alacriti's site structure
(products, value props, case studies/proof points, integrations).

Extracts 8 fields instead of the original 4:
  company_name, tagline, product_description, key_strengths,
  differentiators, products (list), case_studies (list), integrations (list)

If a field can't be confidently extracted, it's left blank — never
fabricated. The user fills gaps manually.

Usage:
    POST /api/settings/scrape-company
    { "url": "https://www.alacriti.com" }
"""

import re
import asyncio
from urllib.parse import urljoin, urlparse

COMMON_PATHS = [
    "", "/about", "/about-us", "/company",
    "/product", "/products", "/solutions", "/services",
]

MAX_PAGES   = 6      # cap total pages crawled per site
TIMEOUT_MS  = 10_000


async def scrape_company_url(base_url: str) -> dict:
    """
    Main entry point. Crawls the site and returns extracted fields.
    Any field that can't be confidently filled is returned as "" (blank) —
    never guessed or fabricated.
    """
    from playwright.async_api import async_playwright

    if not base_url.startswith("http"):
        base_url = "https://" + base_url
    parsed = urlparse(base_url)
    domain = parsed.netloc

    result = {
        "company_name":        "",
        "tagline":              "",
        "product_description":  "",
        "key_strengths":        "",
        "differentiators":      "",
        "products":             [],
        "case_studies":         [],
        "integrations":         [],
        "pages_crawled":        [],
        "scrape_status":        "success",
    }

    playwright = await async_playwright().start()
    browser = await playwright.chromium.launch(headless=True,
        args=["--no-sandbox", "--disable-dev-shm-usage"])
    page = await browser.new_page(
        user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"
    )

    all_text_blocks = []
    visited = set()

    try:
        for path in COMMON_PATHS:
            if len(visited) >= MAX_PAGES:
                break
            url = urljoin(base_url, path)
            if url in visited:
                continue
            try:
                resp = await page.goto(url, wait_until="domcontentloaded", timeout=TIMEOUT_MS)
                if not resp or resp.status >= 400:
                    continue
                visited.add(url)
                result["pages_crawled"].append(url)

                text = await page.evaluate("() => document.body.innerText")
                title = await page.title()
                all_text_blocks.append({"url": url, "title": title, "text": text})

            except Exception:
                continue  # page didn't exist or timed out — skip silently

        if not all_text_blocks:
            result["scrape_status"] = "failed"
            result["error"] = "Could not reach the website or no pages responded."
            return result

        # ── Extract company name ────────────────────────────────
        homepage = all_text_blocks[0]
        result["company_name"] = _extract_company_name(homepage["title"], domain)

        # ── Extract tagline (usually the largest heading on homepage) ──
        result["tagline"] = await _extract_tagline(page, base_url)

        # ── Combine all text for broader extraction ─────────────
        full_text = "\n\n".join(b["text"] for b in all_text_blocks)

        result["products"]      = _extract_products(full_text)
        result["case_studies"]  = _extract_case_studies(full_text)
        result["integrations"]  = _extract_integrations(full_text)

        result["product_description"] = _build_product_description(
            result["tagline"], result["products"], full_text)
        result["key_strengths"]       = _extract_strengths(full_text)
        result["differentiators"]     = _extract_differentiators(
            result["products"], result["case_studies"])

    finally:
        await browser.close()
        await playwright.stop()

    return result


# ── Extraction helpers ───────────────────────────────────────────

def _extract_company_name(title: str, domain: str) -> str:
    """Pull company name from page title, fall back to domain."""
    if title:
        # Strip common suffixes like " | Home" or " - Official Site"
        name = re.split(r"[\|\-–—]", title)[0].strip()
        if 2 < len(name) < 60:
            return name
    # Fallback: derive from domain (e.g. "alacriti.com" -> "Alacriti")
    base = domain.replace("www.", "").split(".")[0]
    return base.capitalize()


async def _extract_tagline(page, base_url: str) -> str:
    """
    The tagline is usually the first large heading (h1) on the homepage.
    Example: Alacriti's "One Platform. Payments Modernization. Delivered."
    """
    try:
        await page.goto(base_url, wait_until="domcontentloaded", timeout=TIMEOUT_MS)
        h1_text = await page.evaluate("""
            () => {
                const h1 = document.querySelector('h1');
                return h1 ? h1.innerText.trim() : '';
            }
        """)
        if h1_text and 5 < len(h1_text) < 200:
            return h1_text.replace("\n", " ").strip()
    except Exception:
        pass
    return ""


def _extract_products(text: str) -> list:
    """
    Look for a "Products" section and pull out product names.
    Pattern-matches headings followed by short product-name-like lines.
    """
    products = []
    # Look for lines that appear right after a "Products" heading
    matches = re.findall(
        r"Products?\s*\n+([A-Z][\w &\-/]{3,60})\n",
        text, re.MULTILINE
    )
    for m in matches[:8]:
        clean = m.strip()
        if clean and clean not in products and len(clean.split()) <= 8:
            products.append(clean)
    return products


def _extract_case_studies(text: str) -> list:
    """
    Look for case study patterns — customer name + outcome.
    Matches lines like "Customer\\nRoyal Credit Union" followed by
    a results-style headline nearby.
    """
    case_studies = []
    # Pattern: a results headline followed by "Customer" label and a name
    blocks = re.split(r"\n(?=[A-Z])", text)
    for i, block in enumerate(blocks):
        if "Customer" in block and i > 0:
            headline = blocks[i-1].strip().split("\n")[-1]
            customer_match = re.search(r"Customer\s*\n?([A-Z][\w &]{2,40})", block)
            if customer_match and len(headline) > 15 and len(headline) < 200:
                case_studies.append({
                    "customer": customer_match.group(1).strip(),
                    "outcome":  headline.strip()
                })
    return case_studies[:6]


def _extract_integrations(text: str) -> list:
    """Look for an 'Integrations' or 'Partners' section."""
    integrations = []
    section_match = re.search(
        r"(Integrations|Partners|Technology Partners)[\s:]*\n(.*?)(?:\n\n|\Z)",
        text, re.DOTALL
    )
    if section_match:
        block = section_match.group(2)
        names = re.findall(r"[A-Z][\w\.]{2,30}", block)
        integrations = list(dict.fromkeys(names))[:10]  # dedupe, preserve order
    return integrations


def _build_product_description(tagline: str, products: list, full_text: str) -> str:
    """
    Build a concise product description from the tagline + product list.
    Prefers the site's own "Why [Company]" / "What we do" style paragraph
    if one exists, otherwise composes from tagline + products.
    """
    why_match = re.search(
        r"(?:Why [\w\s]+\?|What we do|About us)\s*\n+(.{50,400}?)(?:\n\n|\.\s*\n)",
        full_text, re.DOTALL
    )
    if why_match:
        return why_match.group(1).strip().replace("\n", " ")

    if tagline and products:
        return f"{tagline} Core offerings include: {', '.join(products[:4])}."
    if tagline:
        return tagline
    return ""


def _extract_strengths(full_text: str) -> str:
    """
    Look for a value-proposition section (e.g. Alacriti's "Why Alacriti?"
    block: Flexibility, Strength of Technology, Single Source of Truth...).
    Returns them as a comma-separated summary.
    """
    strengths = []
    section_match = re.search(
        r"Why [\w\s]+\?\s*\n(.*?)(?:\n\n[A-Z]{2,}|\Z)",
        full_text, re.DOTALL
    )
    block = section_match.group(1) if section_match else full_text

    headings = re.findall(r"\n([A-Z][\w]+(?:\s[A-Z][\w]+){0,4})\n", block)
    for h in headings[:6]:
        if 8 < len(h) < 50 and h not in strengths:
            strengths.append(h.strip())

    return "; ".join(strengths) if strengths else ""


def _extract_differentiators(products: list, case_studies: list) -> str:
    """
    Compose differentiators from concrete proof points (case study
    outcomes) since these are the most credible differentiators —
    real numbers, not marketing claims.
    """
    if case_studies:
        outcomes = [cs["outcome"] for cs in case_studies[:3]]
        return " / ".join(outcomes)
    if products:
        return f"Specialised in: {', '.join(products[:3])}"
    return ""
