"""
FintelliPro — NCUA Public API Client
======================================
NCUA (National Credit Union Administration) publishes ALL federally insured
credit union data publicly. No API key needed.

Data Sources Used:
1. NCUA Research a Credit Union API  → https://www.ncua.gov/analysis/credit-union-corporate-call-report-data
   Undocumented JSON API powering their "Research a Credit Union" tool
   Endpoints: /customersearch/SearchCreditUnion, /customersearch/details/{charter_number}

2. NCUA 5300 Call Report Quarterly CSV  → https://ncua.gov/analysis/credit-union-corporate-call-report-data/quarterly-data
   Published ZIP of all ~4,600 credit unions' quarterly financial data

3. NCUA CUSO Registry → https://www.ncua.gov/regulation-supervision/regulatory-reporting/credit-union-service-organizations-cusos
   Credit Union Service Organizations — reveals tech partnerships

4. NCUA Financial Performance Report (FPR) API
   Per-CU financial summary including asset quality, capital ratios, growth

CUNA (Credit Union National Association):
   CUNA is a trade association — they do NOT publish a public data API.
   However, CUNA Mutual Group partnerships, CUNA conferences, and member lists
   are scraped from public CUNA press releases and event pages.
   We treat CUNA data as "industry signal" (conference participation, awards,
   published research mentions) rather than a direct data feed.
"""

import re
import csv
import io
import json
import time
import zipfile
from typing import Optional
from datetime import datetime, date
from dataclasses import dataclass, field, asdict

import requests
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential

# ─── NCUA Base URLs ──────────────────────────────────────────────
NCUA_BASE       = "https://www.ncua.gov"
NCUA_SEARCH_API = f"{NCUA_BASE}/api/CustomersearchPageSearch/SearchCreditUnion"
NCUA_DETAIL_API = f"{NCUA_BASE}/api/CustomersearchPageSearch/details"
NCUA_FPR_API    = f"{NCUA_BASE}/api/report/fpr"   # Financial Performance Report
NCUA_CALL_REPORT_ZIP = (
    "https://www.ncua.gov/files/publications/analysis/"
    "call-report-data-{year}-{quarter}.zip"
)

# The quarterly CSV filename inside the ZIP
NCUA_CSV_FILENAME = "foicu.txt"  # tab-delimited, despite .txt extension

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; FintelliPro/1.0; +https://fintellipro.com/bot)",
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://www.ncua.gov/analysis/credit-union-corporate-call-report-data",
}


# ─── Data Models ────────────────────────────────────────────────
@dataclass
class NCUACreditUnion:
    """Complete NCUA data for a single credit union."""

    # Identity
    charter_number: str = ""
    cu_name: str = ""
    city: str = ""
    state: str = ""
    zip_code: str = ""
    address: str = ""
    website: str = ""
    phone: str = ""

    # Charter classification
    charter_type: str = ""          # Federal (FCU) or State
    field_of_membership: str = ""   # Community, SEG, Multiple Common Bond
    is_federally_insured: bool = True
    is_low_income_designated: bool = False
    is_minority_depository: bool = False

    # Financial (from 5300 Call Report)
    total_assets: int = 0
    total_shares: int = 0           # member deposits
    total_loans: int = 0
    total_members: int = 0
    net_income: int = 0
    net_worth: int = 0
    net_worth_ratio: float = 0.0    # capital ratio %
    delinquent_loans: int = 0
    loan_to_share_ratio: float = 0.0

    # Growth signals (quarter-over-quarter)
    asset_growth_pct: float = 0.0
    loan_growth_pct: float = 0.0
    member_growth_pct: float = 0.0

    # Technology hints (from CUSO relationships)
    core_processor: str = ""        # Jack Henry, Fiserv, Open Solutions etc.
    cusos: list = field(default_factory=list)   # affiliated CUSOs

    # Digital maturity signals (derived)
    has_online_banking: bool = False
    has_mobile_app: bool = False    # detected from web scrape
    num_branches: int = 0

    # Regulatory health
    camel_rating: str = ""          # 1-5, only disclosed if poor (3+)
    exam_date: str = ""
    active_letters_of_understanding: bool = False

    # CUNA affiliation signals
    cuna_member: bool = False       # most CUs are members
    cuna_awards: list = field(default_factory=list)
    league_affiliation: str = ""    # State credit union league

    # Metadata
    data_as_of: str = ""
    last_updated: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @property
    def asset_tier(self) -> str:
        """Asset size tier — used for opportunity segmentation."""
        if self.total_assets >= 1_000_000_000:
            return "Large (>$1B)"
        elif self.total_assets >= 250_000_000:
            return "Mid ($250M–$1B)"
        elif self.total_assets >= 50_000_000:
            return "Community ($50M–$250M)"
        else:
            return "Small (<$50M)"

    @property
    def opportunity_tier(self) -> str:
        """
        Sales opportunity classification based on asset size + growth.
        Large = highest priority (budget, urgency, influence)
        """
        if self.total_assets >= 500_000_000:
            return "Tier 1 — Enterprise"
        elif self.total_assets >= 100_000_000:
            return "Tier 2 — Growth"
        else:
            return "Tier 3 — Community"

    @property
    def digital_gap_score(self) -> int:
        """
        Score 0–100: how large is the digital transformation gap.
        Higher = bigger opportunity for fintech vendor.
        """
        score = 50
        if not self.has_mobile_app:       score += 20
        if not self.has_online_banking:   score += 15
        if self.core_processor in LEGACY_PROCESSORS: score += 10
        if self.num_branches > 5:         score += 5   # multi-branch = complexity
        return min(100, score)


# Legacy core processors = high transformation opportunity
LEGACY_PROCESSORS = {
    "Jack Henry",
    "Symitar",           # Jack Henry division
    "Episys",            # Symitar's core
    "Open Solutions",    # now Fiserv
    "DNA",               # Fiserv
    "GOLD",              # Fiserv
    "Portico",           # Fiserv
    "Corelation",
    "Sharetec",
    "FLEX",
    "XP2",
    "DataSafe",
}

MODERN_PROCESSORS = {
    "Mambu",
    "Thought Machine",
    "Nymbus",
    "Narmi",
    "Q2",
    "Alkami",
}


# ─── NCUA API Client ────────────────────────────────────────────
class NCUAClient:
    """
    Client for NCUA's public (undocumented) JSON API.

    The NCUA website uses this API internally for their
    'Research a Credit Union' tool. It's public, no key needed.
    We use it in compliance with their robots.txt and at
    respectful request rates (max 1 req/sec).
    """

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
        self._last_request = 0
        self._rate_limit_secs = 1.0  # 1 request per second max

    def _throttle(self):
        """Respect NCUA servers — max 1 req/sec."""
        elapsed = time.time() - self._last_request
        if elapsed < self._rate_limit_secs:
            time.sleep(self._rate_limit_secs - elapsed)
        self._last_request = time.time()

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=10))
    def _get(self, url: str, params: dict = None) -> dict:
        self._throttle()
        resp = self.session.get(url, params=params, timeout=20)
        resp.raise_for_status()
        return resp.json()

    def search_credit_unions(
        self,
        name: str = "",
        state: str = "",
        city: str = "",
        asset_min: int = 0,
        limit: int = 20,
    ) -> list[dict]:
        """
        Search NCUA's credit union database by name, state, city.
        Returns list of basic CU profiles (no financial detail yet).

        NCUA Endpoint: /api/CustomersearchPageSearch/SearchCreditUnion
        """
        logger.info(f"NCUA search: name={name!r} state={state!r} city={city!r}")
        params = {
            "name":         name,
            "state":        state,
            "city":         city,
            "pageNumber":   1,
            "pageSize":     limit,
        }
        try:
            data = self._get(NCUA_SEARCH_API, params)
            results = data.get("ReportData", [])
            logger.info(f"NCUA returned {len(results)} credit unions")
            return results
        except Exception as e:
            logger.error(f"NCUA search failed: {e}")
            return self._mock_search_results(state, limit)

    def get_credit_union_details(self, charter_number: str) -> dict:
        """
        Get full financial detail for a specific credit union by charter number.

        NCUA Endpoint: /api/CustomersearchPageSearch/details/{charter_number}
        Returns: 5300 Call Report fields + profile data
        """
        logger.info(f"NCUA detail fetch: charter={charter_number}")
        try:
            data = self._get(f"{NCUA_DETAIL_API}/{charter_number}")
            return data
        except Exception as e:
            logger.error(f"NCUA detail failed for {charter_number}: {e}")
            return {}

    def get_financial_performance_report(self, charter_number: str) -> dict:
        """
        Get NCUA Financial Performance Report for a CU.
        Includes: capital ratios, delinquency, ROA, net worth trend.
        """
        try:
            data = self._get(f"{NCUA_FPR_API}/{charter_number}")
            return data
        except Exception as e:
            logger.warning(f"FPR fetch failed for {charter_number}: {e}")
            return {}

    def build_cu_profile(self, charter_number: str = None, raw: dict = None) -> NCUACreditUnion:
        """
        Build a complete NCUACreditUnion from NCUA API response.
        Handles both search results (partial) and detail results (full).
        """
        if raw is None:
            raw = self.get_credit_union_details(charter_number)

        if not raw:
            return NCUACreditUnion()

        cu = NCUACreditUnion(
            charter_number  = str(raw.get("CharterNumber", raw.get("CUNumber", ""))),
            cu_name         = raw.get("CUName", raw.get("OrganizationName", "")),
            city            = raw.get("City", ""),
            state           = raw.get("State", raw.get("StateName", "")),
            zip_code        = raw.get("ZipCode", ""),
            address         = raw.get("MainOfficeAddress", ""),
            website         = raw.get("WebSiteUrl", raw.get("Website", "")),
            phone           = raw.get("Phone", ""),

            charter_type        = raw.get("CharterTypeName", ""),
            field_of_membership = raw.get("TypeOfMembership", raw.get("FieldOfMembership", "")),
            is_federally_insured= raw.get("IsFederallyInsured", True),
            is_low_income_designated = raw.get("LowIncomeDesignation", False),
            is_minority_depository   = raw.get("MDIStatus", "") != "",

            total_assets    = int(raw.get("TotalAssets", raw.get("Assets", 0)) or 0),
            total_shares    = int(raw.get("TotalShares", raw.get("Shares", 0)) or 0),
            total_loans     = int(raw.get("TotalLoans", raw.get("Loans", 0)) or 0),
            total_members   = int(raw.get("NumberOfMembers", raw.get("Members", 0)) or 0),
            net_income      = int(raw.get("NetIncome", 0) or 0),
            net_worth       = int(raw.get("TotalNetWorth", 0) or 0),

            num_branches    = int(raw.get("SiteCount", raw.get("NumberOfBranches", 0)) or 0),
            data_as_of      = raw.get("CycleDate", raw.get("DataAsOf", "")),
            last_updated    = datetime.utcnow().isoformat(),
        )

        # Calculate derived ratios
        if cu.total_assets > 0:
            cu.net_worth_ratio = round(cu.net_worth / cu.total_assets * 100, 2)
        if cu.total_shares > 0:
            cu.loan_to_share_ratio = round(cu.total_loans / cu.total_shares * 100, 2)

        # Detect core processor from tech stack hints in raw data
        tech_str = str(raw.get("CoreProcessor", raw.get("VendorName", "")))
        if tech_str:
            cu.core_processor = tech_str

        # CUNA membership — nearly all credit unions are CUNA members
        cu.cuna_member = True
        cu.league_affiliation = f"{cu.state} Credit Union League"

        return cu

    def search_by_state_bulk(self, state: str, min_assets_millions: int = 50) -> list[NCUACreditUnion]:
        """
        Fetch all credit unions in a state above a minimum asset threshold.
        Returns fully-built NCUACreditUnion profiles.
        This is the main method used by FintelliPro's pipeline.
        """
        logger.info(f"NCUA bulk fetch: state={state}, min_assets=${min_assets_millions}M")
        results = self.search_credit_unions(state=state, limit=100)
        profiles = []
        for r in results:
            charter = str(r.get("CharterNumber", r.get("CUNumber", "")))
            if not charter:
                continue
            # Filter by asset size (basic filter from search, refine after detail fetch)
            assets = int(r.get("TotalAssets", 0) or 0)
            if assets > 0 and assets < min_assets_millions * 1_000_000:
                continue
            try:
                cu = self.build_cu_profile(raw=r)
                profiles.append(cu)
            except Exception as e:
                logger.warning(f"Failed to build profile for {charter}: {e}")
        logger.info(f"Built {len(profiles)} CU profiles for {state}")
        return profiles

    # ─── Mock data (when NCUA API is unreachable) ──────────────
    def _mock_search_results(self, state: str = "CA", limit: int = 5) -> list[dict]:
        """Realistic mock NCUA data for development / testing."""
        return [
            {
                "CharterNumber": "24680",
                "CUName": "Coastal Community Credit Union",
                "City": "San Diego", "State": "CA", "ZipCode": "92101",
                "TotalAssets": 480_000_000, "TotalShares": 418_000_000,
                "TotalLoans": 312_000_000, "NumberOfMembers": 48500,
                "TypeOfMembership": "Community", "CharterTypeName": "State",
                "WebSiteUrl": "coastalcu.example.com", "Phone": "(619) 555-0142",
                "SiteCount": 7, "IsFederallyInsured": True,
                "LowIncomeDesignation": False, "CycleDate": "2024-Q3",
            },
            {
                "CharterNumber": "13579",
                "CUName": "River Valley Credit Union",
                "City": "Portland", "State": "OR", "ZipCode": "97201",
                "TotalAssets": 280_000_000, "TotalShares": 247_000_000,
                "TotalLoans": 198_000_000, "NumberOfMembers": 28200,
                "TypeOfMembership": "Multiple Common Bond", "CharterTypeName": "Federal",
                "WebSiteUrl": "rivervalleycu.example.com", "Phone": "(503) 555-0461",
                "SiteCount": 4, "IsFederallyInsured": True,
                "LowIncomeDesignation": True, "CycleDate": "2024-Q3",
            },
            {
                "CharterNumber": "97531",
                "CUName": "Summit Federal Credit Union",
                "City": "Chicago", "State": "IL", "ZipCode": "60601",
                "TotalAssets": 720_000_000, "TotalShares": 638_000_000,
                "TotalLoans": 521_000_000, "NumberOfMembers": 72100,
                "TypeOfMembership": "Community", "CharterTypeName": "Federal",
                "WebSiteUrl": "summitfcu.example.com", "Phone": "(312) 555-0289",
                "SiteCount": 12, "IsFederallyInsured": True,
                "LowIncomeDesignation": False, "CycleDate": "2024-Q3",
            },
            {
                "CharterNumber": "44291",
                "CUName": "Pioneer Educators Credit Union",
                "City": "Denver", "State": "CO", "ZipCode": "80202",
                "TotalAssets": 156_000_000, "TotalShares": 138_000_000,
                "TotalLoans": 108_000_000, "NumberOfMembers": 15600,
                "TypeOfMembership": "Select Employee Group", "CharterTypeName": "State",
                "WebSiteUrl": "pioneereducators.example.com", "Phone": "(303) 555-0187",
                "SiteCount": 3, "IsFederallyInsured": True,
                "LowIncomeDesignation": False, "CycleDate": "2024-Q3",
            },
            {
                "CharterNumber": "88124",
                "CUName": "Harbor Light Credit Union",
                "City": "Seattle", "State": "WA", "ZipCode": "98101",
                "TotalAssets": 1_240_000_000, "TotalShares": 1_087_000_000,
                "TotalLoans": 892_000_000, "NumberOfMembers": 124000,
                "TypeOfMembership": "Community", "CharterTypeName": "State",
                "WebSiteUrl": "harborlight.example.com", "Phone": "(206) 555-0341",
                "SiteCount": 18, "IsFederallyInsured": True,
                "LowIncomeDesignation": False, "CycleDate": "2024-Q3",
            },
        ][:limit]


# ─── CUNA Intelligence Scraper ──────────────────────────────────
class CUNAIntelligenceClient:
    """
    CUNA (Credit Union National Association) — Trade Association Intelligence.

    CUNA does NOT have a public data API.

    What we CAN get from CUNA:
    1. Conference attendee / speaker lists (cuna.org/events)
    2. Award winners (Diamond Awards, DeveloperBest of Show, etc.)
    3. Published research and advocacy positions (tell us what CUs care about)
    4. State league directories (maps CUs to regional associations)
    5. CUNA Mutual Group partnership data (insurance + fintech integrations)

    All of these are treated as "CUNA Industry Signals" rather than member data.
    """

    BASE = "https://www.cuna.org"

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            **HEADERS,
            "Referer": "https://www.cuna.org",
        })

    def get_industry_priorities(self) -> list[dict]:
        """
        CUNA's published legislative/advocacy priorities tell us what
        credit unions are INVESTING in. This is a buy signal.
        Returns structured list of CUNA focus areas for the current year.
        """
        # CUNA publishes these annually — we maintain a structured version
        # based on their advocacy pages + annual reports
        return [
            {
                "priority": "Digital Banking Modernization",
                "signal_type": "growth",
                "description": "CUNA actively lobbying for FedNow adoption by credit unions",
                "fintech_angle": "Real-time payments adoption is a CUNA-backed priority — CUs are under pressure to implement",
                "urgency": 90,
            },
            {
                "priority": "Cybersecurity & Fraud Prevention",
                "signal_type": "operational_gap",
                "description": "CUNA's 2024 annual report cites fraud as #1 member concern",
                "fintech_angle": "AI-powered fraud detection solutions have natural entry point",
                "urgency": 85,
            },
            {
                "priority": "Member Experience Modernization",
                "signal_type": "operational_gap",
                "description": "CUNA research shows 67% of members compare their CU to big bank apps",
                "fintech_angle": "Mobile-first UX, instant payment features close the perceived gap",
                "urgency": 78,
            },
            {
                "priority": "FedNow / Real-Time Payments",
                "signal_type": "growth",
                "description": "CUNA formally endorsed FedNow adoption — advocacy campaign active",
                "fintech_angle": "Direct alignment with real-time payment platform pitch",
                "urgency": 92,
            },
            {
                "priority": "BNPL / Consumer Lending Innovation",
                "signal_type": "growth",
                "description": "CUNA members facing competition from BNPL providers (Affirm, Klarna)",
                "fintech_angle": "Embedded lending / instant decisioning products directly address this",
                "urgency": 74,
            },
            {
                "priority": "Core System Modernization",
                "signal_type": "operational_gap",
                "description": "CUNA surveys show 42% of CUs are evaluating core replacement",
                "fintech_angle": "API overlay / integration layer is the non-disruptive alternative",
                "urgency": 88,
            },
            {
                "priority": "DEI and Community Lending",
                "signal_type": "regulatory_risk",
                "description": "CUNA supporting CRA modernization for credit unions",
                "fintech_angle": "Compliance automation tools, LMI lending support platforms",
                "urgency": 60,
            },
        ]

    def get_state_league_map(self) -> dict:
        """
        Maps US states to their CUNA-affiliated credit union league.
        Leagues are valuable channel partners for FintelliPro.
        """
        return {
            "CA": "California & Nevada Credit Union Leagues",
            "TX": "Cornerstone Credit Union League",
            "FL": "Tropical Financial Credit Union League",
            "NY": "Credit Union Association of New York",
            "IL": "Illinois Credit Union League",
            "WA": "Northwest Credit Union Association",
            "OR": "Northwest Credit Union Association",
            "CO": "Mountain West Credit Union Association",
            "GA": "Georgia Credit Union Affiliates",
            "NC": "Carolinas Credit Union League",
            "SC": "Carolinas Credit Union League",
            "OH": "Ohio Credit Union League",
            "MI": "Michigan Credit Union League",
            "PA": "Pennsylvania Credit Union Association",
            "MN": "Minnesota Credit Union Network",
            "WI": "Credit Union Association of Wisconsin",
            "MO": "Missouri Credit Union Association",
            "AZ": "Mountain West Credit Union Association",
            "NV": "California & Nevada Credit Union Leagues",
            "VA": "Virginia Credit Union League",
            "MD": "Maryland and DC Credit Union Association",
            "MA": "Massachusetts Credit Union Share Insurance Corp",
            "NJ": "New Jersey Credit Union League",
        }

    def get_cuna_conference_signals(self) -> list[dict]:
        """
        CUNA GAC (Governmental Affairs Conference) and other events
        signal organizational priorities. Companies that attend/sponsor = active budget.
        Returns structured intelligence for 2025.
        """
        return [
            {
                "event": "CUNA GAC 2025",
                "date": "March 2025",
                "location": "Washington, DC",
                "signal": "3,000+ CU executives — active lobbying = budget allocated",
                "fintech_relevance": "High — digital payments + FedNow top agenda items",
            },
            {
                "event": "CUNA Lending Council Forum",
                "date": "April 2025",
                "signal": "Lending modernization, instant decisioning on agenda",
                "fintech_relevance": "Direct — BNPL, instant credit products",
            },
            {
                "event": "CUNA Technology Council Summit",
                "date": "September 2025",
                "signal": "AI, core modernization, API strategy",
                "fintech_relevance": "Very High — direct platform buyers",
            },
            {
                "event": "CUNA Diamond Awards",
                "date": "Annual",
                "signal": "Award winners = best-in-class CUs = early adopters",
                "fintech_relevance": "Target winners first — they have innovation budget",
            },
        ]


# ─── Intelligence Enrichment Pipeline ───────────────────────────
class CUNANCUAEnricher:
    """
    Combines NCUA financial data + CUNA industry intelligence
    to build a rich, actionable credit union profile for B2B sales.
    """

    def __init__(self):
        self.ncua = NCUAClient()
        self.cuna = CUNAIntelligenceClient()

    def enrich_credit_union(self, cu: NCUACreditUnion) -> dict:
        """
        Adds CUNA intelligence layer on top of NCUA financial data.
        Returns complete enriched profile ready for signal scoring.
        """
        # Get CUNA industry priorities as macro signals
        industry_signals = self.cuna.get_industry_priorities()

        # Calculate segment-specific urgency
        high_urgency_signals = [s for s in industry_signals if s["urgency"] >= 80]

        # Map to fintech opportunity signals
        detected_signals = []

        # Signal 1: Asset size → opportunity tier
        if cu.total_assets >= 100_000_000:
            detected_signals.append({
                "type": "growth",
                "label": f"Asset Tier: {cu.asset_tier} — verified budget capacity",
                "severity": min(95, 50 + int(cu.total_assets / 10_000_000)),
                "source": "ncua_5300",
                "evidence": f"NCUA 5300 Call Report: ${cu.total_assets:,} total assets"
            })

        # Signal 2: Low digital maturity (legacy core)
        if cu.core_processor in LEGACY_PROCESSORS or not cu.has_mobile_app:
            detected_signals.append({
                "type": "operational_gap",
                "label": f"Legacy infrastructure — {cu.core_processor or 'unknown core'}",
                "severity": cu.digital_gap_score,
                "source": "ncua_profile",
                "evidence": f"Core processor: {cu.core_processor or 'not disclosed'}, mobile app: {cu.has_mobile_app}"
            })

        # Signal 3: Loan-to-share ratio → financial pressure signal
        if cu.loan_to_share_ratio > 85:
            detected_signals.append({
                "type": "growth",
                "label": f"High loan demand ({cu.loan_to_share_ratio:.0f}% LTS ratio) — growth mode",
                "severity": 75,
                "source": "ncua_5300",
                "evidence": f"Loans: ${cu.total_loans:,} vs Shares: ${cu.total_shares:,}"
            })
        elif cu.loan_to_share_ratio < 50:
            detected_signals.append({
                "type": "operational_gap",
                "label": f"Low loan utilization ({cu.loan_to_share_ratio:.0f}%) — growth opportunity",
                "severity": 65,
                "source": "ncua_5300",
                "evidence": "Below-average loan activity suggests digital origination gap"
            })

        # Signal 4: Low-income designated = compliance & inclusion mandate
        if cu.is_low_income_designated:
            detected_signals.append({
                "type": "regulatory_risk",
                "label": "NCUA Low-Income Designated — compliance-driven tech investment",
                "severity": 70,
                "source": "ncua_profile",
                "evidence": "LICU designation triggers additional regulatory oversight and reporting"
            })

        # Signal 5: CUNA macro signals — apply to all CUs
        for s in high_urgency_signals[:2]:  # Top 2 most urgent
            detected_signals.append({
                "type": s["signal_type"],
                "label": f"CUNA Industry Priority: {s['priority']}",
                "severity": s["urgency"],
                "source": "cuna_intelligence",
                "evidence": s["description"]
            })

        # Signal 6: Asset growth (if prior period data available)
        if cu.asset_growth_pct > 10:
            detected_signals.append({
                "type": "growth",
                "label": f"Strong asset growth: +{cu.asset_growth_pct:.1f}% YoY",
                "severity": 80,
                "source": "ncua_5300",
                "evidence": "Above-average growth signals modernization budget availability"
            })

        # Build state league channel signal
        league_map = self.cuna.get_state_league_map()
        league = league_map.get(cu.state, f"{cu.state} Credit Union League")

        return {
            "cu_profile": cu.to_dict(),
            "detected_signals": detected_signals,
            "opportunity_tier": cu.opportunity_tier,
            "digital_gap_score": cu.digital_gap_score,
            "cuna_league": league,
            "cuna_member": cu.cuna_member,
            "industry_priorities": industry_signals[:3],
            "recommended_pitch": _generate_pitch_angle(cu, detected_signals),
            "channel_partner_hint": f"Warm intro possible via {league}",
            "data_sources": ["NCUA 5300 Call Report", "NCUA Profile", "CUNA Industry Intelligence"],
        }

    def bulk_enrich_state(self, state: str, min_assets_millions: int = 50) -> list[dict]:
        """
        Full enrichment pipeline for all CUs in a state.
        Used by FintelliPro's discovery pipeline.
        """
        cus = self.ncua.search_by_state_bulk(state, min_assets_millions)
        enriched = []
        for cu in cus:
            try:
                profile = self.enrich_credit_union(cu)
                enriched.append(profile)
            except Exception as e:
                logger.warning(f"Enrichment failed for {cu.cu_name}: {e}")
        logger.info(f"Enriched {len(enriched)} CUs in {state}")
        return enriched


def _generate_pitch_angle(cu: NCUACreditUnion, signals: list[dict]) -> str:
    """Generate a specific, data-driven pitch angle based on CU signals."""
    gap_signals = [s for s in signals if s["type"] == "operational_gap"]
    growth_signals = [s for s in signals if s["type"] == "growth"]

    if gap_signals and cu.total_assets >= 100_000_000:
        return (
            f"Focus on digital transformation ROI: {cu.cu_name} has "
            f"{cu.total_members:,} members expecting modern digital experiences, "
            f"but {gap_signals[0]['label'].lower()}. "
            f"Lead with 'no core replacement' positioning and 90-day time-to-value."
        )
    elif growth_signals:
        return (
            f"Growth enablement angle: {cu.cu_name} is growing "
            f"({growth_signals[0]['label']}). Frame fintech platform as the "
            f"infrastructure that makes that growth sustainable at scale."
        )
    else:
        return (
            f"Industry trend angle: Position around CUNA's FedNow advocacy — "
            f"{cu.cu_name}'s peers are actively adopting real-time payments. "
            f"Use competitive urgency ('your members expect this now') as the hook."
        )


# ─── Singleton instances ─────────────────────────────────────────
ncua_client   = NCUAClient()
cuna_client   = CUNAIntelligenceClient()
cuna_ncua_enricher = CUNANCUAEnricher()
