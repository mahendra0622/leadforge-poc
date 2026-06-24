"""
FintelliPro — Apollo.ai API Client (Free Plan Optimised)
=========================================================
Apollo Free Plan limits (2025/2026):
  - 100 data credits/month  (1 credit = 1 email reveal or export)
  - 5 mobile credits/month  (1 mobile number = 8 credits — skip on free)
  - 10 export credits/month
  - Email search: unlimited for verified corporate domains
  - API access: basic (people search + org enrich included)
  - Rate limit: ~10 req/min on free plan

Strategy for free plan:
  1. Use /people/search for bulk discovery (no credit cost to SEARCH)
  2. Only REVEAL/EXPORT the top 10 contacts per month (costs credits)
  3. Use org enrich sparingly — match by domain not by export
  4. Cache all results in DB so we never re-fetch the same contact twice
  5. Fall back to mock data when credits exhausted
"""
import time
from typing import Optional
import requests
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import settings

APOLLO_BASE = "https://api.apollo.io/v1"

# Titles that matter for FintelliPro's ICP — decision-makers in fintech buying
FINTECH_DECISION_MAKER_TITLES = [
    "Chief Technology Officer",
    "Chief Digital Officer",
    "Chief Information Officer",
    "VP of Technology",
    "VP of Digital Banking",
    "VP of Payments",
    "VP of Information Technology",
    "Head of Payments",
    "Director of Digital Transformation",
    "Director of IT",
    "Chief Operating Officer",
    "Chief Revenue Officer",
]

INDUSTRY_MAP = {
    "credit_unions": "Banking",
    "insurance":     "Insurance",
    "utilities":     "Utilities",
    "lending":       "Financial Services",
    "retail":        "Retail",
    "logistics":     "Transportation/Trucking/Railroad",
    "healthcare":    "Hospital & Health Care",
    "government":    "Government Administration",
    "wealth":        "Investment Management",
}


class ApolloClient:
    """
    Apollo.ai API wrapper — optimised for free plan usage.

    Credit cost per operation:
      - Search (people/org search)  : FREE — no credits used
      - Email reveal                : 1 credit
      - Mobile reveal               : 8 credits (skip on free plan)
      - Export to CSV/CRM           : 1 credit

    On free plan: search freely, reveal sparingly (max 10/month).
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.APOLLO_API_KEY
        self.headers = {
            "Content-Type": "application/json",
            "Cache-Control": "no-cache",
            "X-Api-Key": self.api_key or "",
        }
        self._last_call = 0
        self._min_interval = 6.5   # ~9 req/min — safe for free plan limit

    def _is_configured(self) -> bool:
        return bool(self.api_key) and self.api_key != "your_apollo_api_key_here"

    def _rate_limit(self):
        elapsed = time.time() - self._last_call
        if elapsed < self._min_interval:
            time.sleep(self._min_interval - elapsed)
        self._last_call = time.time()

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=3, max=15))
    def _post(self, endpoint: str, payload: dict) -> dict:
        self._rate_limit()
        resp = requests.post(
            f"{APOLLO_BASE}{endpoint}",
            json=payload,
            headers=self.headers,
            timeout=30,
        )
        if resp.status_code == 429:
            logger.warning("Apollo rate limit hit — backing off 30s")
            time.sleep(30)
            raise Exception("Rate limited")
        if resp.status_code == 401:
            logger.error("Apollo 401 — check your API key in .env")
            raise Exception("Invalid Apollo API key")
        if resp.status_code == 402:
            logger.warning("Apollo 402 — credits exhausted for this month")
            raise Exception("Credits exhausted")
        resp.raise_for_status()
        return resp.json()

    # ── FREE: Search (no credits used) ────────────────────────

    def search_people_at_company(
        self,
        company_name: str,
        domain: str = "",
        titles: list = None,
    ) -> dict:
        """
        Search for people at a specific company.
        DOES NOT consume credits — only reveals consume credits.
        Perfect for free plan: search all you want.
        """
        if not self._is_configured():
            return self._mock_people(company_name)

        payload = {
            "page": 1,
            "per_page": 5,
            "q_organization_name": company_name,
            "person_titles": titles or FINTECH_DECISION_MAKER_TITLES[:6],
            "person_seniority": ["c_suite", "vp", "director"],
        }
        if domain:
            payload["q_organization_domains"] = [domain]

        try:
            result = self._post("/mixed_people/search", payload)
            people = result.get("people", [])
            logger.info(f"Apollo search '{company_name}': {len(people)} people found")
            return result
        except Exception as e:
            logger.error(f"Apollo search failed for {company_name}: {e}")
            return self._mock_people(company_name)

    def people_search(
        self,
        industry_key: str,
        page: int = 1,
        per_page: int = 10,
    ) -> dict:
        """
        Search people by industry — used by the pipeline.
        Returns people + their org data. No credits consumed.
        Free plan: per_page <= 25, max ~10 req/min.
        """
        if not self._is_configured():
            logger.info(f"Apollo not configured — using mock data for {industry_key}")
            return self._get_mock_response(industry_key)

        industry_label = INDUSTRY_MAP.get(industry_key, industry_key)
        logger.info(f"Apollo people_search: {industry_label}, page={page}")

        payload = {
            "page": page,
            "per_page": per_page,
            "person_titles": FINTECH_DECISION_MAKER_TITLES[:8],
            "q_organization_keyword_tags": [industry_label],
            "organization_num_employees_ranges": ["50,10000"],
            "person_seniority": ["c_suite", "vp", "director"],
            # Note: contact_email_status filter may require paid plan
            # Remove it if you get 0 results on free plan
        }

        try:
            return self._post("/mixed_people/search", payload)
        except Exception as e:
            logger.error(f"Apollo people_search failed: {e}")
            return self._get_mock_response(industry_key)

    # ── COSTS 1 CREDIT: Reveal email ──────────────────────────

    def reveal_email(self, person_id: str) -> dict:
        """
        Reveal a contact's verified email address.
        COSTS 1 CREDIT — use sparingly on free plan (100/month).
        Only call this for your highest-priority contacts.
        """
        if not self._is_configured():
            return {}
        try:
            return self._post("/people/match", {
                "id": person_id,
                "reveal_personal_emails": False,  # personal emails cost more
            })
        except Exception as e:
            logger.error(f"Apollo reveal_email failed: {e}")
            return {}

    # ── COSTS 1 CREDIT: Org enrich ────────────────────────────

    def enrich_organization(self, domain: str) -> dict:
        """
        Enrich a company by domain — gets tech stack, revenue, headcount.
        COSTS 1 CREDIT — use sparingly.
        """
        if not self._is_configured():
            return {}
        try:
            return self._post("/organizations/enrich", {"domain": domain})
        except Exception as e:
            logger.error(f"Apollo org enrich failed for {domain}: {e}")
            return {}

    # ── FREE: Check your credit balance ───────────────────────

    def get_credit_balance(self) -> dict:
        """Check remaining credits — free to call."""
        if not self._is_configured():
            return {"error": "not configured"}
        try:
            resp = requests.get(
                f"{APOLLO_BASE}/auth/health",
                headers=self.headers,
                timeout=10,
            )
            if resp.status_code == 200:
                return resp.json()
            return {"status": resp.status_code}
        except Exception as e:
            return {"error": str(e)}

    # ── Mock fallback ──────────────────────────────────────────

    def _mock_people(self, company_name: str) -> dict:
        """Return a mock person for a specific company (no API needed)."""
        return {
            "people": [{
                "id": f"mock_{company_name[:8].replace(' ','_').lower()}",
                "first_name": "Alex",
                "last_name": "Morgan",
                "title": "VP of Technology",
                "email": f"a.morgan@{company_name[:10].replace(' ','').lower()}.org",
                "email_status": "guessed",
                "phone_numbers": [],
                "linkedin_url": "",
                "seniority": "vp",
                "organization": {
                    "id": f"mock_org_{company_name[:8].replace(' ','_').lower()}",
                    "name": company_name,
                    "website_url": "",
                    "industry": "Banking",
                    "estimated_num_employees": 200,
                },
                "confidence_score": 60,
            }],
            "pagination": {"page":1,"per_page":5,"total_entries":1},
        }

    def _get_mock_response(self, industry_key: str) -> dict:
        """Full mock response for pipeline runs without a real API key."""
        people = [
            {
                "id": "mock_person_1",
                "first_name": "Jennifer", "last_name": "Walsh",
                "title": "VP of Technology",
                "email": "j.walsh@coastalcu.example.com",
                "email_status": "verified",
                "phone_numbers": [{"raw_number": "+1-619-555-0142"}],
                "linkedin_url": "linkedin.com/in/jennifer-walsh-tech",
                "seniority": "vp",
                "organization": {
                    "id": "mock_org_1",
                    "name": "Coastal Community Credit Union",
                    "website_url": "coastalcu.example.com",
                    "industry": "Banking",
                    "estimated_num_employees": 220,
                    "annual_revenue": 480_000_000,
                    "city": "San Diego", "state": "CA",
                    "technology_names": ["Jack Henry", "Symitar"],
                },
                "confidence_score": 98,
            },
            {
                "id": "mock_person_2",
                "first_name": "Marcus", "last_name": "Chen",
                "title": "Chief Digital Officer",
                "email": "m.chen@rivervalleycu.example.com",
                "email_status": "verified",
                "phone_numbers": [],
                "linkedin_url": "linkedin.com/in/marcus-chen-cdo",
                "seniority": "c_suite",
                "organization": {
                    "id": "mock_org_2",
                    "name": "River Valley Credit Union",
                    "website_url": "rivervalleycu.example.com",
                    "industry": "Banking",
                    "estimated_num_employees": 145,
                    "annual_revenue": 280_000_000,
                    "city": "Portland", "state": "OR",
                    "technology_names": ["Fiserv", "DNA Core"],
                },
                "confidence_score": 95,
            },
        ]
        return {
            "people": people,
            "pagination": {"page":1,"per_page":10,"total_entries":len(people)},
        }


apollo_client = ApolloClient()
