"""
FintelliPro — SQLAlchemy Models
Complete database schema for all entities
"""
import uuid
from datetime import datetime
from sqlalchemy import (
    Column, String, Integer, SmallInteger, BigInteger,
    Boolean, Text, DateTime, Float, ForeignKey, ARRAY, JSON
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.database import Base


def gen_uuid():
    return str(uuid.uuid4())


# ──────────────────────────────────────────
# USER
# ──────────────────────────────────────────
class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=True)  # nullable: Google-login users have no password
    full_name = Column(String(255))
    company_name = Column(String(255))
    product_description = Column(Text)
    key_strengths = Column(Text)
    differentiators = Column(Text)
    tone = Column(String(50), default="consultative")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Gmail OAuth integration
    gmail_email         = Column(String(255), nullable=True)
    gmail_refresh_token = Column(Text, nullable=True)
    gmail_connected_at  = Column(DateTime(timezone=True), nullable=True)
    auth_provider       = Column(String(50), default="password")

    # Extended company profile (scraped from vendor's website)
    tagline     = Column(String(500), nullable=True)
    products    = Column(JSON, nullable=True)
    case_studies = Column(JSON, nullable=True)
    integrations = Column(JSON, nullable=True)

    campaigns = relationship("Campaign", back_populates="owner")
    ai_messages = relationship("AIMessage", back_populates="owner")


# ──────────────────────────────────────────
# COMPANY
# ──────────────────────────────────────────
class Company(Base):
    __tablename__ = "companies"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    apollo_org_id = Column(String(100), unique=True, index=True)

    # Identity
    name = Column(String(255), nullable=False)
    website = Column(String(255))
    industry = Column(String(100), index=True)
    sub_industry = Column(String(100))
    description = Column(Text)

    # Location
    hq_city = Column(String(100))
    hq_state = Column(String(50))
    hq_country = Column(String(50), default="US")

    # Firmographics
    revenue_est = Column(BigInteger)
    employee_count = Column(Integer)
    founded_year = Column(Integer)
    tech_stack = Column(ARRAY(String))

    # Regulatory
    regulatory_id = Column(String(100))
    regulatory_src = Column(String(50))  # NCUA, FDIC, NAIC
    regulatory_data = Column(JSON)        # raw regulatory fields

    # Scoring
    digital_maturity = Column(SmallInteger, default=3)  # 1-5
    opportunity_score = Column(SmallInteger, default=0)  # 0-100
    outreach_status = Column(String(50), default="new", index=True)

    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    last_enriched_at = Column(DateTime(timezone=True))

    # Relationships
    contacts = relationship("Contact", back_populates="company", cascade="all, delete-orphan")
    signals = relationship("Signal", back_populates="company", cascade="all, delete-orphan")
    ai_messages = relationship("AIMessage", back_populates="company")


# ──────────────────────────────────────────
# CONTACT (Apollo-enriched)
# ──────────────────────────────────────────
class Contact(Base):
    __tablename__ = "contacts"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    company_id = Column(UUID(as_uuid=False), ForeignKey("companies.id", ondelete="CASCADE"), index=True)
    apollo_person_id = Column(String(100), unique=True, index=True)

    # Identity
    first_name = Column(String(100))
    last_name = Column(String(100))
    title = Column(String(255))

    # Contact details
    email = Column(String(255), index=True)
    email_status = Column(String(50))       # verified, probable, invalid
    email_confidence = Column(SmallInteger) # 0-100
    phone = Column(String(50))
    linkedin_url = Column(Text)

    # Classification
    is_decision_maker = Column(Boolean, default=False, index=True)
    seniority_level = Column(String(50))    # c_suite, vp, director, manager

    # Metadata
    last_verified = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    company = relationship("Company", back_populates="contacts")
    ai_messages = relationship("AIMessage", back_populates="contact")
    outreach_events = relationship("OutreachEvent", back_populates="contact")


# ──────────────────────────────────────────
# SIGNAL
# ──────────────────────────────────────────
class Signal(Base):
    __tablename__ = "signals"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    company_id = Column(UUID(as_uuid=False), ForeignKey("companies.id", ondelete="CASCADE"), index=True)

    signal_type = Column(String(50), nullable=False, index=True)
    # operational_gap | pain_point | growth | digital_gap | regulatory_risk

    signal_label = Column(String(255), nullable=False)
    severity = Column(SmallInteger, default=50)   # 0-100
    source = Column(String(100))                   # apollo, web_scrape, news, jobs, regulatory
    raw_evidence = Column(Text)
    is_active = Column(Boolean, default=True)
    detected_at = Column(DateTime(timezone=True), server_default=func.now())

    # Source reference (traceable citation for the signal)
    source_url   = Column(Text, nullable=True)           # web URL (news article, scraped page)
    source_file  = Column(String(255), nullable=True)   # filename (NCUA bulk zip/CSV)
    source_page  = Column(Integer, nullable=True)       # page number for PDFs only
    source_label = Column(String(120), nullable=True)   # human-readable hover label

    company = relationship("Company", back_populates="signals")


# ──────────────────────────────────────────
# AI MESSAGE
# ──────────────────────────────────────────
class AIMessage(Base):
    __tablename__ = "ai_messages"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    company_id = Column(UUID(as_uuid=False), ForeignKey("companies.id"), index=True)
    contact_id = Column(UUID(as_uuid=False), ForeignKey("contacts.id"), index=True)
    owner_id = Column(UUID(as_uuid=False), ForeignKey("users.id"), index=True)

    message_type = Column(String(50))   # email, linkedin, call_script
    subject_line = Column(Text)
    body = Column(Text, nullable=False)
    tone = Column(String(50))
    angle = Column(String(50))          # pain_first, growth_first
    variant = Column(String(10))        # A or B

    model_used = Column(String(100))
    tokens_used = Column(Integer)
    approved = Column(Boolean, default=False)
    sent = Column(Boolean, default=False)

    sent_at          = Column(DateTime(timezone=True), nullable=True)
    gmail_message_id = Column(String(255), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    company = relationship("Company", back_populates="ai_messages")
    contact = relationship("Contact", back_populates="ai_messages")
    owner = relationship("User", back_populates="ai_messages")


# ──────────────────────────────────────────
# CAMPAIGN
# ──────────────────────────────────────────
class Campaign(Base):
    __tablename__ = "campaigns"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    owner_id = Column(UUID(as_uuid=False), ForeignKey("users.id"), index=True)

    name = Column(String(255), nullable=False)
    industry = Column(String(100))
    status = Column(String(50), default="draft", index=True)
    # draft | active | paused | completed

    channel = Column(String(50), default="email")  # email, linkedin, multi
    min_score = Column(SmallInteger, default=60)
    from_email = Column(String(255))
    from_name = Column(String(255))

    # Stats (denormalized for performance)
    total_sent = Column(Integer, default=0)
    total_opens = Column(Integer, default=0)
    total_replies = Column(Integer, default=0)
    total_bounces = Column(Integer, default=0)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    launched_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))

    owner = relationship("User", back_populates="campaigns")
    events = relationship("OutreachEvent", back_populates="campaign")


# ──────────────────────────────────────────
# OUTREACH EVENT
# ──────────────────────────────────────────
class OutreachEvent(Base):
    __tablename__ = "outreach_events"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    campaign_id = Column(UUID(as_uuid=False), ForeignKey("campaigns.id"), index=True)
    contact_id = Column(UUID(as_uuid=False), ForeignKey("contacts.id"), index=True)
    message_id = Column(UUID(as_uuid=False), ForeignKey("ai_messages.id"))

    event_type = Column(String(50), index=True)
    # sent | delivered | opened | clicked | replied | bounced | unsubscribed

    event_data = Column(JSON, default={})
    occurred_at = Column(DateTime(timezone=True), server_default=func.now())

    campaign = relationship("Campaign", back_populates="events")
    contact = relationship("Contact", back_populates="outreach_events")


# ──────────────────────────────────────────
# EMAIL THREAD LINK
# ──────────────────────────────────────────
class EmailThreadLink(Base):
    __tablename__ = "email_thread_links"

    id              = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    company_id      = Column(UUID(as_uuid=False), ForeignKey("companies.id"), nullable=False, index=True)
    user_id         = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=False, index=True)
    gmail_thread_id = Column(String(255), nullable=False)
    match_method    = Column(String(50), default="auto")   # "auto" | "manual"
    linked_at       = Column(DateTime(timezone=True), server_default=func.now())

    company = relationship("Company")
    user    = relationship("User")
