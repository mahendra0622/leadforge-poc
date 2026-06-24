"""
FintelliPro — Pydantic Schemas
Request/Response validation models
"""
from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List, Any
from datetime import datetime
from enum import Enum


# ─── Enums ─────────────────────────────────────────────
class OutreachStatus(str, Enum):
    new = "new"
    contacted = "contacted"
    replied = "replied"
    qualified = "qualified"
    lost = "lost"

class MessageType(str, Enum):
    email = "email"
    linkedin = "linkedin"
    call_script = "call_script"

class SignalType(str, Enum):
    operational_gap = "operational_gap"
    pain_point = "pain_point"
    growth = "growth"
    digital_gap = "digital_gap"
    regulatory_risk = "regulatory_risk"


# ─── Auth ───────────────────────────────────────────────
class UserRegister(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    full_name: str
    company_name: Optional[str] = None

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict

class UserProfile(BaseModel):
    company_name: Optional[str]
    product_description: Optional[str]
    key_strengths: Optional[str]
    differentiators: Optional[str]
    tone: str = "consultative"
    tagline: Optional[str] = None
    products: Optional[List[str]] = None
    case_studies: Optional[List[Any]] = None
    integrations: Optional[List[str]] = None


# ─── Company ────────────────────────────────────────────
class CompanyBase(BaseModel):
    name: str
    industry: Optional[str]
    website: Optional[str]
    hq_city: Optional[str]
    hq_state: Optional[str]
    revenue_est: Optional[int]
    employee_count: Optional[int]

class CompanyCreate(CompanyBase):
    pass

class CompanyResponse(CompanyBase):
    id: str
    opportunity_score: int
    digital_maturity: int
    outreach_status: str
    regulatory_src: Optional[str]
    created_at: datetime
    signal_count: Optional[int] = 0
    top_contact: Optional[dict] = None

    class Config:
        from_attributes = True


# ─── Contact ────────────────────────────────────────────
class ContactResponse(BaseModel):
    id: str
    company_id: str
    first_name: Optional[str]
    last_name: Optional[str]
    title: Optional[str]
    email: Optional[str]
    email_status: Optional[str]
    email_confidence: Optional[int]
    phone: Optional[str]
    linkedin_url: Optional[str]
    is_decision_maker: bool
    seniority_level: Optional[str]

    class Config:
        from_attributes = True


# ─── Signal ─────────────────────────────────────────────
class SignalResponse(BaseModel):
    id: str
    signal_type: str
    signal_label: str
    severity: int
    source: Optional[str]
    detected_at: datetime

    class Config:
        from_attributes = True


# ─── AI Message ─────────────────────────────────────────
class GenerateMessageRequest(BaseModel):
    company_id: str
    contact_id: str
    message_type: MessageType
    tone: Optional[str] = None  # override user profile tone

class GenerateMessageResponse(BaseModel):
    id: str
    message_type: str
    subject_line: Optional[str]
    body: str
    tone: Optional[str]
    variant: Optional[str]
    tokens_used: Optional[int]
    created_at: datetime

    class Config:
        from_attributes = True


# ─── Campaign ───────────────────────────────────────────
class CampaignCreate(BaseModel):
    name: str
    industry: Optional[str]
    channel: str = "email"
    min_score: int = 60
    from_email: Optional[str]
    from_name: Optional[str]

class CampaignResponse(BaseModel):
    id: str
    name: str
    industry: Optional[str]
    status: str
    channel: str
    total_sent: int
    total_opens: int
    total_replies: int
    created_at: datetime

    @property
    def open_rate(self) -> float:
        return round(self.total_opens / self.total_sent * 100, 1) if self.total_sent > 0 else 0.0

    @property
    def reply_rate(self) -> float:
        return round(self.total_replies / self.total_sent * 100, 1) if self.total_sent > 0 else 0.0

    class Config:
        from_attributes = True


# ─── Dashboard ──────────────────────────────────────────
class DashboardStats(BaseModel):
    total_leads: int
    apollo_enriched: int
    high_score_leads: int
    active_campaigns: int
    emails_sent_today: int
    open_rate_avg: float
    reply_rate_avg: float
