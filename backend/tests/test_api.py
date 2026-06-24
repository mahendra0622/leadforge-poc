"""
FintelliPro POC — Backend Tests
Run: pytest tests/ -v
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.db.database import Base, get_db
from app.core.security import hash_password
from app.models import User

# Use in-memory SQLite for tests
TEST_DB_URL = "sqlite:///./test_fintellipro.db"
engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(autouse=True, scope="session")
def setup_db():
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    # Seed test user
    user = User(
        id="test-user-001",
        email="test@fintellipro.com",
        hashed_password=hash_password("testpass123"),
        full_name="Test User",
        company_name="TestCo",
        tone="consultative",
    )
    db.add(user)
    db.commit()
    db.close()
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def auth_headers(client):
    resp = client.post("/api/auth/login", json={"email": "test@fintellipro.com", "password": "testpass123"})
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


# ── Auth Tests ────────────────────────────────────────────────
class TestAuth:
    def test_health(self, client):
        r = client.get("/health")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"

    def test_register(self, client):
        r = client.post("/api/auth/register", json={
            "email": "newuser@test.com",
            "password": "password123",
            "full_name": "New User",
        })
        assert r.status_code == 200
        assert "access_token" in r.json()

    def test_login_success(self, client):
        r = client.post("/api/auth/login", json={
            "email": "test@fintellipro.com",
            "password": "testpass123",
        })
        assert r.status_code == 200
        data = r.json()
        assert "access_token" in data
        assert data["user"]["email"] == "test@fintellipro.com"

    def test_login_wrong_password(self, client):
        r = client.post("/api/auth/login", json={
            "email": "test@fintellipro.com",
            "password": "wrongpassword",
        })
        assert r.status_code == 401

    def test_me_authenticated(self, client, auth_headers):
        r = client.get("/api/auth/me", headers=auth_headers)
        assert r.status_code == 200
        assert r.json()["email"] == "test@fintellipro.com"

    def test_me_unauthenticated(self, client):
        r = client.get("/api/auth/me")
        assert r.status_code == 403  # No bearer token


# ── Companies Tests ───────────────────────────────────────────
class TestCompanies:
    def test_list_companies_empty(self, client, auth_headers):
        r = client.get("/api/companies/", headers=auth_headers)
        assert r.status_code == 200
        data = r.json()
        assert "data" in data
        assert "total" in data

    def test_list_requires_auth(self, client):
        r = client.get("/api/companies/")
        assert r.status_code == 403

    def test_company_not_found(self, client, auth_headers):
        r = client.get("/api/companies/nonexistent-id", headers=auth_headers)
        assert r.status_code == 404


# ── Scoring Tests ─────────────────────────────────────────────
class TestScoring:
    def test_opportunity_score_high_gap(self):
        from app.services.ai_service import calculate_opportunity_score
        score = calculate_opportunity_score(
            digital_maturity=1,       # legacy
            pain_severity_avg=85.0,
            growth_strength_avg=70.0,
            apollo_confidence=95.0,
            industry="credit_unions",
            has_regulatory_data=True,
        )
        assert score >= 80

    def test_opportunity_score_modern_company(self):
        from app.services.ai_service import calculate_opportunity_score
        score = calculate_opportunity_score(
            digital_maturity=5,       # fully digital
            pain_severity_avg=20.0,
            growth_strength_avg=30.0,
            apollo_confidence=80.0,
            industry="retail",
            has_regulatory_data=False,
        )
        assert score < 60

    def test_regulatory_multiplier_applied(self):
        from app.services.ai_service import calculate_opportunity_score
        with_reg = calculate_opportunity_score(1, 70, 60, 90, "credit_unions", True)
        without_reg = calculate_opportunity_score(1, 70, 60, 90, "credit_unions", False)
        assert with_reg > without_reg

    def test_score_capped_at_100(self):
        from app.services.ai_service import calculate_opportunity_score
        score = calculate_opportunity_score(1, 100, 100, 100, "credit_unions", True)
        assert score <= 100

    def test_digital_maturity_classification(self):
        from app.services.ai_service import classify_digital_maturity
        # Fully legacy → low maturity
        m = classify_digital_maturity(
            has_mobile_app=False, has_api_docs=False, has_digital_portal=False,
            app_store_rating=None, tech_stack=["Jack Henry", "Symitar"]
        )
        assert m <= 2

        # Modern → high maturity
        m = classify_digital_maturity(
            has_mobile_app=True, has_api_docs=True, has_digital_portal=True,
            app_store_rating=4.8, tech_stack=["AWS", "Stripe", "React"]
        )
        assert m >= 4


# ── AI Service Tests ──────────────────────────────────────────
class TestAIService:
    def test_mock_signal_detection(self):
        from app.services.ai_service import _mock_signal_detection
        result = _mock_signal_detection({"name": "Test CU", "industry": "credit_unions"})
        assert "operational_gaps" in result
        assert "pain_points" in result
        assert "growth_signals" in result
        assert "digital_maturity" in result
        assert "opportunity_score" in result
        assert 0 <= result["opportunity_score"] <= 100
        assert 1 <= result["digital_maturity"] <= 5

    def test_mock_email_generation(self):
        from app.services.ai_service import _mock_outreach_message
        result = _mock_outreach_message(
            "email",
            {"name": "Coastal CU", "industry": "credit_unions", "hq_city": "San Diego"},
            {"first_name": "Jennifer", "last_name": "Walsh", "title": "VP Technology"},
            {"company_name": "FintelliPay", "product_description": "Real-time payments"},
        )
        assert "body" in result
        assert "subject_line" in result
        assert len(result["body"]) > 100  # non-trivial content
        assert "Jennifer" in result["body"]

    def test_mock_linkedin_generation(self):
        from app.services.ai_service import _mock_outreach_message
        result = _mock_outreach_message(
            "linkedin",
            {"name": "SunBridge", "industry": "insurance"},
            {"first_name": "David", "last_name": "Ruiz"},
            {"company_name": "FintelliPay"},
        )
        assert result["body"] is not None
        assert result["subject_line"] is None
        assert len(result["body"]) <= 400  # LinkedIn should be concise


# ── Pipeline Tests ────────────────────────────────────────────
class TestPipeline:
    def test_pipeline_status(self, client, auth_headers):
        r = client.get("/api/pipeline/status", headers=auth_headers)
        assert r.status_code == 200
        data = r.json()
        assert "companies_total" in data

    def test_pipeline_run_trigger(self, client, auth_headers):
        r = client.post("/api/pipeline/run", json={"industry": "credit_unions"}, headers=auth_headers)
        assert r.status_code == 200
        assert r.json()["status"] == "started"


# ── Dashboard Tests ───────────────────────────────────────────
class TestDashboard:
    def test_stats(self, client, auth_headers):
        r = client.get("/api/dashboard/stats", headers=auth_headers)
        assert r.status_code == 200
        data = r.json()
        assert "total_leads" in data
        assert "apollo_enriched" in data
        assert "high_score_leads" in data
