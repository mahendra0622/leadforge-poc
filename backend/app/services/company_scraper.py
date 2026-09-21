"""
app/services/company_scraper.py
==================================
Scrapes a company's own website (the user's company, in Settings) to
auto-fill the product profile fields used for AI outreach personalisation.

Uses httpx + BeautifulSoup (no Playwright / browser binary needed).
Crawls: homepage + /about, /products, /solutions, /services, /company.

Extracts: company_name, tagline, product_description, key_strengths,
differentiators, products (list), case_studies (list), integrations (list).
"""

import re
import asyncio
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

COMMON_PATHS = [
    "", "/about", "/about-us", "/company",
    "/product", "/products", "/solutions", "/services",
]

MAX_PAGES = 6
TIMEOUT   = 15.0
HEADERS   = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


async def scrape_company_url(base_url: str) -> dict:
    if not base_url.startswith("http"):
        base_url = "https://" + base_url
    parsed = urlparse(base_url)
    domain = parsed.netloc

    result = {
        "company_name":       "",
        "tagline":            "",
        "product_description": "",
        "key_strengths":      "",
        "differentiators":    "",
        "products":           [],
        "case_studies":       [],
        "integrations":       [],
        "pages_crawled":      [],
        "scrape_status":      "success",
    }

    all_pages = []
    visited   = set()

    async with httpx.AsyncClient(headers=HEADERS, timeout=TIMEOUT,
                                  follow_redirects=True) as client:
        for path in COMMON_PATHS:
            if len(visited) >= MAX_PAGES:
                break
            url = urljoin(base_url, path)
            if url in visited:
                continue
            try:
                resp = await client.get(url)
                if resp.status_code >= 400:
                    continue
                visited.add(url)
                result["pages_crawled"].append(url)
                soup = BeautifulSoup(resp.text, "lxml")
                # strip script/style noise
                for tag in soup(["script", "style", "nav", "footer", "header"]):
                    tag.decompose()
                text  = soup.get_text(separator="\n", strip=True)
                title = soup.title.string.strip() if soup.title else ""
                all_pages.append({"url": url, "soup": soup, "text": text, "title": title})
            except Exception:
                continue

    if not all_pages:
        result["scrape_status"] = "failed"
        result["error"] = "Could not reach the website or no pages responded."
        return result

    homepage = all_pages[0]
    full_text = "\n\n".join(p["text"] for p in all_pages)

    result["company_name"]        = _extract_company_name(homepage["title"], domain)
    result["tagline"]             = _extract_tagline(homepage["soup"])
    result["products"]            = _extract_products(full_text)
    result["case_studies"]        = _extract_case_studies(full_text)
    result["integrations"]        = _extract_integrations(full_text)
    result["product_description"] = _build_product_description(
        result["tagline"], result["products"], full_text)
    result["key_strengths"]       = _extract_strengths(full_text)
    result["differentiators"]     = _extract_differentiators(
        result["products"], result["case_studies"])

    return result


# ── Helpers ────────────────────────────────────────────────────────────────

def _extract_company_name(title: str, domain: str) -> str:
    if title:
        name = re.split(r"[\|\-–—]", title)[0].strip()
        if 2 < len(name) < 60:
            return name
    base = domain.replace("www.", "").split(".")[0]
    return base.capitalize()


def _extract_tagline(soup: "BeautifulSoup") -> str:
    # Try h1 first
    for tag in soup.find_all(["h1", "h2"]):
        text = tag.get_text(" ", strip=True)
        if 8 < len(text) < 200:
            return text.replace("\n", " ").strip()
    return ""


def _extract_products(text: str) -> list:
    products = []
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
    case_studies = []
    blocks = re.split(r"\n(?=[A-Z])", text)
    for i, block in enumerate(blocks):
        if "Customer" in block and i > 0:
            headline = blocks[i - 1].strip().split("\n")[-1]
            customer_match = re.search(r"Customer\s*\n?([A-Z][\w &]{2,40})", block)
            if customer_match and 15 < len(headline) < 200:
                case_studies.append({
                    "customer": customer_match.group(1).strip(),
                    "outcome":  headline.strip(),
                })
    return case_studies[:6]


def _extract_integrations(text: str) -> list:
    integrations = []
    section_match = re.search(
        r"(Integrations|Partners|Technology Partners)[\s:]*\n(.*?)(?:\n\n|\Z)",
        text, re.DOTALL
    )
    if section_match:
        block = section_match.group(2)
        names = re.findall(r"[A-Z][\w\.]{2,30}", block)
        integrations = list(dict.fromkeys(names))[:10]
    return integrations


def _build_product_description(tagline: str, products: list, full_text: str) -> str:
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
    if case_studies:
        outcomes = [cs["outcome"] for cs in case_studies[:3]]
        return " / ".join(outcomes)
    if products:
        return f"Specialised in: {', '.join(products[:3])}"
    return ""
