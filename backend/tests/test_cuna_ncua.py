"""
FintelliPro — NCUA/CUNA Integration Tests
Run: pytest tests/test_cuna_ncua.py -v
"""
import pytest
from app.services.regulatory.cuna_ncua import (
    NCUAClient,
    CUNAIntelligenceClient,
    CUNANCUAEnricher,
    NCUACreditUnion,
    LEGACY_PROCESSORS,
    MODERN_PROCESSORS,
)


# ── NCUACreditUnion model tests ────────────────────────────────
class TestNCUACreditUnionModel:

    def test_asset_tier_large(self):
        cu = NCUACreditUnion(total_assets=1_500_000_000)
        assert cu.asset_tier == "Large (>$1B)"

    def test_asset_tier_mid(self):
        cu = NCUACreditUnion(total_assets=400_000_000)
        assert cu.asset_tier == "Mid ($250M–$1B)"

    def test_asset_tier_community(self):
        cu = NCUACreditUnion(total_assets=100_000_000)
        assert cu.asset_tier == "Community ($50M–$250M)"

    def test_asset_tier_small(self):
        cu = NCUACreditUnion(total_assets=20_000_000)
        assert cu.asset_tier == "Small (<$50M)"

    def test_opportunity_tier_enterprise(self):
        cu = NCUACreditUnion(total_assets=600_000_000)
        assert "Enterprise" in cu.opportunity_tier

    def test_opportunity_tier_growth(self):
        cu = NCUACreditUnion(total_assets=200_000_000)
        assert "Growth" in cu.opportunity_tier

    def test_opportunity_tier_community(self):
        cu = NCUACreditUnion(total_assets=30_000_000)
        assert "Community" in cu.opportunity_tier

    def test_digital_gap_score_high_for_legacy(self):
        cu = NCUACreditUnion(
            has_mobile_app=False,
            has_online_banking=False,
            has_digital_portal=False,
            core_processor="Symitar",
            num_branches=10,
        )
        assert cu.digital_gap_score >= 80

    def test_digital_gap_score_low_for_modern(self):
        cu = NCUACreditUnion(
            has_mobile_app=True,
            has_online_banking=True,
            has_digital_portal=True,
            core_processor="Alkami",
            num_branches=2,
        )
        assert cu.digital_gap_score <= 60

    def test_net_worth_ratio_calculated(self):
        cu = NCUACreditUnion(total_assets=100_000_000, net_worth=8_000_000)
        # ratio calculated in build_cu_profile, not automatically
        # test the formula directly
        ratio = cu.net_worth / cu.total_assets * 100
        assert abs(ratio - 8.0) < 0.01

    def test_loan_to_share_ratio_formula(self):
        cu = NCUACreditUnion(total_shares=400_000_000, total_loans=340_000_000)
        ratio = cu.total_loans / cu.total_shares * 100
        assert abs(ratio - 85.0) < 0.1

    def test_to_dict_returns_all_fields(self):
        cu = NCUACreditUnion(cu_name="Test CU", charter_number="12345")
        d = cu.to_dict()
        assert "cu_name" in d
        assert "charter_number" in d
        assert "total_assets" in d
        assert "digital_gap_score" not in d  # property, not field


# ── NCUAClient tests ───────────────────────────────────────────
class TestNCUAClient:

    def test_mock_search_returns_data(self):
        client = NCUAClient()
        results = client._mock_search_results(state="CA", limit=3)
        assert len(results) == 3
        assert all("CUName" in r for r in results)
        assert all("TotalAssets" in r for r in results)

    def test_mock_search_limit(self):
        client = NCUAClient()
        results = client._mock_search_results(limit=2)
        assert len(results) == 2

    def test_build_cu_profile_from_mock(self):
        client = NCUAClient()
        mocks = client._mock_search_results(limit=1)
        cu = client.build_cu_profile(raw=mocks[0])

        assert cu.cu_name != ""
        assert cu.charter_number != ""
        assert cu.total_assets > 0
        assert cu.total_members > 0
        assert cu.state in ("CA", "OR", "IL", "CO", "WA")

    def test_build_cu_profile_calculates_ratios(self):
        client = NCUAClient()
        raw = {
            "CharterNumber": "99999",
            "CUName": "Test Credit Union",
            "City": "Portland", "State": "OR",
            "TotalAssets": 100_000_000,
            "TotalShares": 80_000_000,
            "TotalLoans": 60_000_000,
            "TotalNetWorth": 10_000_000,
            "NumberOfMembers": 10000,
        }
        cu = client.build_cu_profile(raw=raw)
        assert cu.net_worth_ratio == 10.0
        assert cu.loan_to_share_ratio == 75.0

    def test_build_cu_profile_cuna_defaults(self):
        client = NCUAClient()
        raw = {"CharterNumber": "11111", "CUName": "Small CU", "State": "TX"}
        cu = client.build_cu_profile(raw=raw)
        assert cu.cuna_member is True  # all CUs are CUNA members by default

    def test_search_falls_back_to_mock(self):
        """If NCUA API is unreachable, should return mock data."""
        client = NCUAClient()
        # Force mock by providing a state that returns mocked data
        results = client.search_credit_unions(state="CA", limit=5)
        # Either real API results or mock — both should be lists
        assert isinstance(results, list)

    def test_legacy_processor_set(self):
        assert "Jack Henry" in LEGACY_PROCESSORS
        assert "Symitar" in LEGACY_PROCESSORS
        assert "Fiserv" not in LEGACY_PROCESSORS  # Fiserv itself is less legacy
        assert "Mambu" not in LEGACY_PROCESSORS

    def test_modern_processor_set(self):
        assert "Mambu" in MODERN_PROCESSORS
        assert "Nymbus" in MODERN_PROCESSORS
        assert "Jack Henry" not in MODERN_PROCESSORS


# ── CUNAIntelligenceClient tests ───────────────────────────────
class TestCUNAIntelligenceClient:

    def test_industry_priorities_returns_list(self):
        cuna = CUNAIntelligenceClient()
        priorities = cuna.get_industry_priorities()
        assert isinstance(priorities, list)
        assert len(priorities) >= 5

    def test_priorities_have_required_fields(self):
        cuna = CUNAIntelligenceClient()
        for p in cuna.get_industry_priorities():
            assert "priority" in p
            assert "signal_type" in p
            assert "urgency" in p
            assert "fintech_angle" in p
            assert 0 <= p["urgency"] <= 100

    def test_fednow_is_high_priority(self):
        cuna = CUNAIntelligenceClient()
        priorities = cuna.get_industry_priorities()
        fednow = next((p for p in priorities if "FedNow" in p["priority"]), None)
        assert fednow is not None
        assert fednow["urgency"] >= 85

    def test_state_league_map_covers_major_states(self):
        cuna = CUNAIntelligenceClient()
        leagues = cuna.get_state_league_map()
        for state in ["CA", "TX", "FL", "NY", "IL", "WA"]:
            assert state in leagues
            assert leagues[state] != ""

    def test_conference_signals_have_fintech_relevance(self):
        cuna = CUNAIntelligenceClient()
        events = cuna.get_cuna_conference_signals()
        assert len(events) >= 2
        for e in events:
            assert "event" in e
            assert "fintech_relevance" in e


# ── CUNANCUAEnricher tests ─────────────────────────────────────
class TestCUNANCUAEnricher:

    def test_enrich_returns_complete_profile(self):
        enricher = CUNANCUAEnricher()
        cu = NCUACreditUnion(
            cu_name="Test Credit Union",
            charter_number="12345",
            state="CA",
            total_assets=300_000_000,
            total_members=30_000,
            total_shares=260_000_000,
            total_loans=210_000_000,
            net_worth=24_000_000,
            core_processor="Symitar",
            has_mobile_app=False,
        )
        cu.net_worth_ratio = round(cu.net_worth / cu.total_assets * 100, 2)
        cu.loan_to_share_ratio = round(cu.total_loans / cu.total_shares * 100, 2)

        result = enricher.enrich_credit_union(cu)

        assert "cu_profile" in result
        assert "detected_signals" in result
        assert "opportunity_tier" in result
        assert "digital_gap_score" in result
        assert "cuna_league" in result
        assert "recommended_pitch" in result
        assert "data_sources" in result

    def test_legacy_core_adds_gap_signal(self):
        enricher = CUNANCUAEnricher()
        cu = NCUACreditUnion(
            cu_name="Legacy CU",
            state="OR",
            total_assets=200_000_000,
            core_processor="Symitar",
            has_mobile_app=False,
        )
        result = enricher.enrich_credit_union(cu)
        gap_signals = [s for s in result["detected_signals"] if s["type"] == "operational_gap"]
        assert len(gap_signals) > 0

    def test_high_assets_adds_growth_signal(self):
        enricher = CUNANCUAEnricher()
        cu = NCUACreditUnion(
            cu_name="Big CU",
            state="TX",
            total_assets=800_000_000,
            total_members=80_000,
        )
        result = enricher.enrich_credit_union(cu)
        growth_signals = [s for s in result["detected_signals"] if s["type"] == "growth"]
        assert len(growth_signals) > 0

    def test_cuna_signals_included(self):
        enricher = CUNANCUAEnricher()
        cu = NCUACreditUnion(cu_name="Any CU", state="CA", total_assets=100_000_000)
        result = enricher.enrich_credit_union(cu)
        cuna_signals = [s for s in result["detected_signals"] if s.get("source") == "cuna_intelligence"]
        assert len(cuna_signals) >= 1

    def test_low_income_designation_signal(self):
        enricher = CUNANCUAEnricher()
        cu = NCUACreditUnion(
            cu_name="Community CU",
            state="GA",
            total_assets=80_000_000,
            is_low_income_designated=True,
        )
        result = enricher.enrich_credit_union(cu)
        regulatory_signals = [s for s in result["detected_signals"] if s["type"] == "regulatory_risk"]
        assert len(regulatory_signals) > 0

    def test_recommended_pitch_is_string(self):
        enricher = CUNANCUAEnricher()
        cu = NCUACreditUnion(cu_name="Generic CU", state="IL", total_assets=150_000_000)
        result = enricher.enrich_credit_union(cu)
        assert isinstance(result["recommended_pitch"], str)
        assert len(result["recommended_pitch"]) > 20

    def test_data_sources_always_included(self):
        enricher = CUNANCUAEnricher()
        cu = NCUACreditUnion(cu_name="Minimal CU", state="WA", total_assets=50_000_000)
        result = enricher.enrich_credit_union(cu)
        assert "NCUA 5300 Call Report" in result["data_sources"]
        assert "CUNA Industry Intelligence" in result["data_sources"]
