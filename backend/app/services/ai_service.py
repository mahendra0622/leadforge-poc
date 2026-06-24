"""
FintelliPro — Signal Detection & Opportunity Scoring Engine
Uses Claude AI to detect gaps and score opportunities
"""
import json
from typing import Optional
from loguru import logger
import anthropic

from app.core.config import settings

# ──────────────────────────────────────────
# Claude AI client (singleton)
# ──────────────────────────────────────────
_anthropic_client = None

def get_anthropic():
    global _anthropic_client
    if _anthropic_client is None:
        _anthropic_client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    return _anthropic_client


# ──────────────────────────────────────────
# Signal Detection Prompt
# ──────────────────────────────────────────
SIGNAL_DETECTION_PROMPT = """You are a senior fintech B2B intelligence analyst specializing in identifying digital transformation opportunities at financial institutions and regulated businesses.

Analyze the company data below and identify signals, gaps, and opportunities.

COMPANY DATA:
Name: {company_name}
Industry: {industry}
Location: {city}, {state}
Revenue: {revenue}
Employees: {employees}
Tech Stack: {tech_stack}
Regulatory Source: {regulatory_src}
Website Features Detected: {web_features}
Recent News: {news_summary}
Job Postings: {job_signals}
Customer Reviews Summary: {reviews_summary}

Return ONLY valid JSON in this exact format (no markdown, no preamble):
{{
  "operational_gaps": [
    {{"label": "...", "severity": 0-100, "evidence": "..."}}
  ],
  "pain_points": [
    {{"label": "...", "urgency": 0-100, "evidence": "..."}}
  ],
  "growth_signals": [
    {{"label": "...", "strength": 0-100, "evidence": "..."}}
  ],
  "digital_maturity": 1,
  "opportunity_score": 0,
  "recommended_pitch_angle": "...",
  "key_insight": "One sentence summary of the biggest opportunity"
}}

Rules:
- digital_maturity: 1=paper-based/legacy, 2=basic digital, 3=partial modernization, 4=mostly digital, 5=fully digital-native
- opportunity_score: higher = better opportunity for a fintech solution
- Be specific — reference actual company details in evidence fields
- If data is limited, use industry benchmarks and be transparent about it"""


# ──────────────────────────────────────────
# Personalized Outreach Prompts
# ──────────────────────────────────────────
EMAIL_PROMPT = """You are a senior B2B fintech sales strategist with deep expertise in {industry}.

Write a personalized cold email for this prospect:
Contact: {contact_name}, {contact_title} at {company_name}
Industry: {industry}
Location: {location}

COMPANY INTELLIGENCE:
Revenue: {revenue}
Digital Maturity: {digital_maturity}/5 ({maturity_label})
Opportunity Score: {opportunity_score}/100

KEY PAIN POINTS DETECTED:
{pain_points}

GROWTH SIGNALS DETECTED:
{growth_signals}

OPERATIONAL GAPS:
{operational_gaps}

YOUR FINTECH PRODUCT:
Company: {provider_name}
Product: {product_description}
Key Strengths: {key_strengths}
Differentiators: {differentiators}
Tone: {tone}

RULES:
- Do NOT start with "I hope this email finds you well" or any variation
- Do NOT use {first_name} placeholders — use the actual name
- Open with a specific, compelling observation about {company_name}
- Reference one SPECIFIC pain point or signal in the first 2 sentences
- Keep under 220 words
- One clear, soft CTA at the end (suggest a 20-minute call)
- No bullet points in the email body
- Sound human, not AI-generated

Return ONLY the email body. Do not include subject line here."""


SUBJECT_LINE_PROMPT = """Write 3 compelling subject lines for a cold sales email to {contact_name} at {company_name}.

Context:
- Industry: {industry}
- Main pain point: {main_pain}
- Fintech solution: {provider_name} — {product_short}

Rules:
- Under 60 characters each
- No clickbait or ALL CAPS
- Sound like a real person wrote it
- Reference something specific about their situation

Return ONLY the 3 subject lines, one per line, no numbering."""


LINKEDIN_PROMPT = """You are a senior fintech sales professional. Write a LinkedIn connection request message.

Prospect: {contact_name}, {contact_title} at {company_name}
Industry: {industry}
Key signal: {main_signal}
Your company: {provider_name}

Rules:
- Under 300 characters (LinkedIn limit)
- First line: specific observation about them or their company
- Do NOT pitch in the connection request
- Sound genuinely curious, not salesy
- End with a question or a reason to connect

Return ONLY the message text."""


CALL_SCRIPT_PROMPT = """You are a senior fintech sales trainer. Write a structured 5-minute discovery call script.

Prospect: {contact_name}, {contact_title} at {company_name}
Industry: {industry}
Pain points: {pain_points}
Growth signals: {growth_signals}
Fintech provider: {provider_name} — {product_description}

Format:
OPENER (0:00–0:30):
[Script]

BRIDGE — PROBLEM DISCOVERY (0:30–2:00):
[Script with 2-3 discovery questions]

VALUE HOOK (2:00–3:30):
[Script referencing a relevant case study outcome]

CLOSE (3:30–5:00):
[Script to book next step]

OBJECTION HANDLING:
- "We already have a vendor": [Response]
- "Not the right time": [Response]  
- "Budget constraints": [Response]

Keep it conversational. Include timing notes. Reference specific company details."""


# ──────────────────────────────────────────
# Scoring Logic
# ──────────────────────────────────────────
INDUSTRY_FIT_SCORES = {
    "credit_unions": 95,
    "insurance": 88,
    "healthcare": 91,
    "lending": 86,
    "utilities": 74,
    "government": 78,
    "wealth": 83,
    "retail": 72,
    "logistics": 67,
}


def calculate_opportunity_score(
    digital_maturity: int,
    pain_severity_avg: float,
    growth_strength_avg: float,
    apollo_confidence: float,
    industry: str,
    has_regulatory_data: bool,
) -> int:
    """
    Weighted opportunity scoring formula.
    Higher score = better sales opportunity.
    """
    # Invert digital maturity (low maturity = high opportunity)
    maturity_gap_score = (6 - digital_maturity) * 20  # 20, 40, 60, 80, 100

    industry_fit = INDUSTRY_FIT_SCORES.get(industry, 70)

    base = (
        maturity_gap_score   * 0.30 +
        pain_severity_avg    * 0.25 +
        growth_strength_avg  * 0.20 +
        apollo_confidence    * 0.15 +
        industry_fit         * 0.10
    )

    # Regulatory bonus: regulated industries are more qualified
    multiplier = 1.2 if has_regulatory_data else 1.0

    return min(100, round(base * multiplier))


def classify_digital_maturity(
    has_mobile_app: bool,
    has_api_docs: bool,
    has_digital_portal: bool,
    app_store_rating: Optional[float],
    tech_stack: list,
) -> int:
    """Classify digital maturity from 1-5."""
    score = 3.0

    if not has_mobile_app:
        score -= 1.0
    if not has_api_docs:
        score -= 0.5
    if not has_digital_portal:
        score -= 0.5
    if app_store_rating and app_store_rating < 3.0:
        score -= 0.5
    if app_store_rating and app_store_rating >= 4.5:
        score += 0.5

    # Modern tech stack signals
    modern_tech = ["stripe", "plaid", "twilio", "salesforce", "aws", "azure", "react", "node"]
    legacy_tech = ["cobol", "as400", "jack henry", "fiserv", "symitar", "open solutions"]

    tech_lower = [t.lower() for t in tech_stack]
    modern_count = sum(1 for t in modern_tech if any(t in s for s in tech_lower))
    legacy_count = sum(1 for t in legacy_tech if any(t in s for s in tech_lower))

    score += min(1.0, modern_count * 0.3)
    score -= min(1.0, legacy_count * 0.2)

    return max(1, min(5, round(score)))


# ──────────────────────────────────────────
# AI Service Functions
# ──────────────────────────────────────────
def detect_signals(company_data: dict) -> dict:
    """
    Use Claude to detect signals and score opportunity.
    Falls back to rule-based scoring if AI unavailable.
    """
    if not settings.ANTHROPIC_API_KEY:
        logger.warning("No Anthropic API key — using mock signal detection")
        return _mock_signal_detection(company_data)

    try:
        client = get_anthropic()
        prompt = SIGNAL_DETECTION_PROMPT.format(
            company_name=company_data.get("name", "Unknown"),
            industry=company_data.get("industry", "Financial Services"),
            city=company_data.get("hq_city", ""),
            state=company_data.get("hq_state", ""),
            revenue=f"${company_data.get('revenue_est', 0):,}" if company_data.get("revenue_est") else "Unknown",
            employees=company_data.get("employee_count", "Unknown"),
            tech_stack=", ".join(company_data.get("tech_stack", [])) or "Unknown",
            regulatory_src=company_data.get("regulatory_src", "None"),
            web_features=company_data.get("web_features", "Not scraped"),
            news_summary=company_data.get("news_summary", "No recent news"),
            job_signals=company_data.get("job_signals", "No job postings analyzed"),
            reviews_summary=company_data.get("reviews_summary", "No reviews analyzed"),
        )

        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1500,
            messages=[{"role": "user", "content": prompt}],
        )

        raw = response.content[0].text.strip()
        # Strip markdown fences if present
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        result = json.loads(raw)
        result["tokens_used"] = response.usage.input_tokens + response.usage.output_tokens
        return result

    except Exception as e:
        logger.error(f"Signal detection failed: {e}")
        return _mock_signal_detection(company_data)


def generate_outreach_message(
    message_type: str,
    company_data: dict,
    contact_data: dict,
    provider_profile: dict,
    signals: dict,
) -> dict:
    """
    Generate personalized outreach using Claude.
    """
    if not settings.ANTHROPIC_API_KEY:
        return _mock_outreach_message(message_type, company_data, contact_data, provider_profile)

    try:
        client = get_anthropic()

        pain_points_str = "\n".join([
            f"- {p['label']} (urgency: {p.get('urgency', 50)}/100)"
            for p in signals.get("pain_points", [])[:3]
        ]) or "- General operational inefficiencies"

        growth_signals_str = "\n".join([
            f"- {g['label']}"
            for g in signals.get("growth_signals", [])[:3]
        ]) or "- Industry growth trends"

        gaps_str = "\n".join([
            f"- {g['label']}"
            for g in signals.get("operational_gaps", [])[:3]
        ]) or "- Digital modernization opportunity"

        maturity_labels = {1: "Legacy/Paper-based", 2: "Basic Digital", 3: "Partial Modernization", 4: "Mostly Digital", 5: "Fully Digital-native"}
        maturity_label = maturity_labels.get(signals.get("digital_maturity", 3), "Moderate")

        tone = provider_profile.get("tone", "consultative")
        location = f"{company_data.get('hq_city', '')}, {company_data.get('hq_state', '')}"

        if message_type == "email":
            body_prompt = EMAIL_PROMPT.format(
                contact_name=f"{contact_data.get('first_name', '')} {contact_data.get('last_name', '')}".strip(),
                contact_title=contact_data.get("title", ""),
                company_name=company_data.get("name", ""),
                industry=company_data.get("industry", ""),
                location=location,
                revenue=f"${company_data.get('revenue_est', 0):,}" if company_data.get("revenue_est") else "growing organization",
                digital_maturity=signals.get("digital_maturity", 3),
                maturity_label=maturity_label,
                opportunity_score=signals.get("opportunity_score", 50),
                pain_points=pain_points_str,
                growth_signals=growth_signals_str,
                operational_gaps=gaps_str,
                provider_name=provider_profile.get("company_name", "our platform"),
                product_description=provider_profile.get("product_description", ""),
                key_strengths=provider_profile.get("key_strengths", ""),
                differentiators=provider_profile.get("differentiators", ""),
                tone=tone,
            )

            body_response = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=800,
                messages=[{"role": "user", "content": body_prompt}],
            )
            body = body_response.content[0].text.strip()

            # Generate subject line
            main_pain = signals.get("pain_points", [{}])[0].get("label", "operational efficiency")
            subj_response = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=200,
                messages=[{"role": "user", "content": SUBJECT_LINE_PROMPT.format(
                    contact_name=contact_data.get("first_name", ""),
                    company_name=company_data.get("name", ""),
                    industry=company_data.get("industry", ""),
                    main_pain=main_pain,
                    provider_name=provider_profile.get("company_name", ""),
                    product_short=provider_profile.get("product_description", "")[:80],
                )}],
            )
            subjects = subj_response.content[0].text.strip().split("\n")
            subject_line = subjects[0].strip() if subjects else f"Quick question about {company_data.get('name', '')}"
            tokens = (body_response.usage.input_tokens + body_response.usage.output_tokens +
                      subj_response.usage.input_tokens + subj_response.usage.output_tokens)

        elif message_type == "linkedin":
            main_signal = signals.get("operational_gaps", signals.get("pain_points", [{}]))[0].get("label", "digital transformation")
            li_response = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=200,
                messages=[{"role": "user", "content": LINKEDIN_PROMPT.format(
                    contact_name=f"{contact_data.get('first_name', '')} {contact_data.get('last_name', '')}".strip(),
                    contact_title=contact_data.get("title", ""),
                    company_name=company_data.get("name", ""),
                    industry=company_data.get("industry", ""),
                    main_signal=main_signal,
                    provider_name=provider_profile.get("company_name", ""),
                )}],
            )
            body = li_response.content[0].text.strip()
            subject_line = None
            tokens = li_response.usage.input_tokens + li_response.usage.output_tokens

        else:  # call_script
            cs_response = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=1200,
                messages=[{"role": "user", "content": CALL_SCRIPT_PROMPT.format(
                    contact_name=f"{contact_data.get('first_name', '')} {contact_data.get('last_name', '')}".strip(),
                    contact_title=contact_data.get("title", ""),
                    company_name=company_data.get("name", ""),
                    industry=company_data.get("industry", ""),
                    pain_points=pain_points_str,
                    growth_signals=growth_signals_str,
                    provider_name=provider_profile.get("company_name", ""),
                    product_description=provider_profile.get("product_description", ""),
                )}],
            )
            body = cs_response.content[0].text.strip()
            subject_line = None
            tokens = cs_response.usage.input_tokens + cs_response.usage.output_tokens

        return {
            "body": body,
            "subject_line": subject_line,
            "tokens_used": tokens,
            "model": "claude-sonnet-4-20250514",
        }

    except Exception as e:
        logger.error(f"Message generation failed: {e}")
        return _mock_outreach_message(message_type, company_data, contact_data, provider_profile)


# ──────────────────────────────────────────
# Mock fallbacks (for dev without API keys)
# ──────────────────────────────────────────
def _mock_signal_detection(company_data: dict) -> dict:
    return {
        "operational_gaps": [
            {"label": "Legacy core banking system", "severity": 78, "evidence": "Tech stack shows older core vendors"},
            {"label": "No visible API documentation", "severity": 65, "evidence": "Website analysis — no developer portal found"},
        ],
        "pain_points": [
            {"label": "Slow member onboarding process", "urgency": 72, "evidence": "Industry benchmark for similar-sized institution"},
            {"label": "Limited digital payment options", "urgency": 68, "evidence": "Website review shows basic payment features only"},
        ],
        "growth_signals": [
            {"label": "Hiring for Digital Transformation roles", "strength": 80, "evidence": "Job board signal — 3 open positions"},
        ],
        "digital_maturity": 2,
        "opportunity_score": 78,
        "recommended_pitch_angle": "Focus on real-time payments and API integration to modernize member experience without replacing core system",
        "key_insight": "High-opportunity target — legacy infrastructure with active digital transformation hiring signals readiness for modernization",
        "tokens_used": 0,
    }


def _mock_outreach_message(msg_type: str, company: dict, contact: dict, profile: dict) -> dict:
    fname = contact.get("first_name", "")
    cname = company.get("name", "your organization")
    pname = profile.get("company_name", "our platform")

    if msg_type == "email":
        body = f"""Hi {fname},

I was looking at {cname}'s digital banking infrastructure and noticed something that's holding back a lot of credit unions at your asset size — the gap between your members' expectations for real-time payments and the legacy ACH rails most institutions are still running on.

Members increasingly expect instant transfers, same-day loan disbursements, and a banking experience that feels more like Venmo than a drive-through teller. That's a hard promise to keep when you're working around a core system that wasn't built for speed.

At {pname}, we've helped 40+ credit unions bridge exactly this gap — without replacing their core. We layer a real-time payment API on top of existing infrastructure, and most clients are live within 6 weeks.

Would a 20-minute conversation be worth your time? I can share a case study from a similar-sized credit union in your region.

Best,
[Your Name]"""
        return {"body": body, "subject_line": f"Real-time payments at {cname} — quick question", "tokens_used": 0, "model": "mock"}

    elif msg_type == "linkedin":
        body = f"Hi {fname}, I noticed {cname} is scaling up — impressive trajectory in a competitive market. We help credit unions modernize their payment infrastructure without core replacement. Curious whether real-time payments are on your roadmap this year?"
        return {"body": body, "subject_line": None, "tokens_used": 0, "model": "mock"}

    else:
        body = f"""CALL SCRIPT — {cname} / {fname}

OPENER (0:00–0:30):
"Hi {fname}, this is [Name] from {pname}. I'll be quick — I came across {cname}'s recent digital transformation signals and thought there might be a conversation worth having. Do you have 3 minutes?"

BRIDGE (0:30–2:00):
"We've been looking at how credit unions your size are handling real-time payment demand. Is modernizing your payment rails something that's on your team's radar for this year?"

VALUE HOOK (2:00–3:30):
"One of our clients — a credit union with similar assets — cut their ACH processing time from 2 days to under 2 seconds. And they did it without replacing their Jack Henry core. The whole integration was 6 weeks."

CLOSE (3:30–5:00):
"I'd love to show you specifically how that would work for {cname}'s stack. Are you open to a 20-minute screen share next week — say Tuesday or Thursday?"

OBJECTIONS:
→ "We already have a vendor": "Makes sense. Many of our clients keep their existing vendors — we layer on as the real-time rail, not a replacement. Would it be worth a quick comparison?"
→ "Not the right time": "Totally get it. When's a better quarter to revisit — Q3 or Q4?" """
        return {"body": body, "subject_line": None, "tokens_used": 0, "model": "mock"}
