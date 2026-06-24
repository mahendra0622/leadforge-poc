"""
Add this to your backend:

1. Copy this file to: backend/app/api/followup.py
2. In backend/app/main.py add:
   from app.api.followup import router as followup_router
   app.include_router(followup_router)
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from app.db.database import get_db
from app.models import Company, Signal, Contact, AIMessage
from app.core.security import get_current_user
import anthropic, os, json, uuid

router = APIRouter()
_client = None

def get_client():
    global _client
    if not _client and os.getenv("ANTHROPIC_API_KEY"):
        _client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    return _client

class FollowUpRequest(BaseModel):
    company_id: str
    original_message: str
    client_response: str
    use_rag: bool = True

FOLLOWUP_PROMPT = """You are an elite B2B sales writer generating a follow-up email.

The prospect just responded to our initial outreach. Write a reply that:
1. Opens by acknowledging a SPECIFIC thing they said — not generic thanks
2. If they mentioned a timeline — reference it explicitly
3. If they raised a constraint — address it directly with proof
4. Uses RETRIEVED CONTEXT below for proof points if relevant
5. Ends with ONE specific next step

CU CONTEXT:
{cu_context}

RETRIEVED CONTEXT (case studies, past threads, news — use the most relevant):
{rag_context}

ORIGINAL EMAIL WE SENT:
{original_message}

THEIR RESPONSE:
{client_response}

Return JSON only: {{ "subject": "Re: ...", "body": "..." }}
No preamble. No explanation. Just the JSON."""

@router.post("/api/ai/generate-followup")
async def generate_followup(
    req: FollowUpRequest,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    company = db.query(Company).filter_by(id=req.company_id).first()
    if not company:
        raise HTTPException(404, "Company not found")

    signals = db.query(Signal).filter_by(company_id=req.company_id, is_active=True).all()
    contact = db.query(Contact).filter_by(company_id=req.company_id).first()

    cu_context = (
        f"Name: {company.name}\n"
        f"Assets: ${round((company.revenue_est or 0)/1_000_000)}M\n"
        f"Members: {(company.regulatory_data or {}).get('total_members', 'N/A')}\n"
        f"NWR: {(company.regulatory_data or {}).get('net_worth_ratio', 'N/A')}%\n"
        f"LTS: {(company.regulatory_data or {}).get('loan_to_share_ratio', 'N/A')}%\n"
        f"Core: {((company.tech_stack or [''])[0])}\n"
        f"Contact: {contact.name if contact else ''}, {contact.title if contact else ''}\n"
        f"Signals: {' | '.join([s.signal_label for s in signals[:3]])}"
    )

    rag_context = "No additional context available."
    rag_chunks = []
    if req.use_rag:
        try:
            from rag_store import retrieve
            query = f"{company.name} {req.client_response[:200]}"
            chunks = retrieve(query, cu_name=company.name, n=3)
            if len(chunks) < 3:
                chunks += retrieve(query, n=5-len(chunks))
            if chunks:
                rag_context = "\n\n---\n".join([
                    f"[{c['type'].upper()} | score:{c['score']}]\n{c['text']}"
                    for c in chunks[:4]
                ])
                rag_chunks = [{"type": c["type"], "score": c["score"],
                               "source": c["source"]} for c in chunks[:4]]
        except Exception:
            pass

    # Fallback template (no API key)
    ai = get_client()
    if not ai:
        first_name = (contact.name.split()[0] if contact else "there")
        return {
            "subject": f"Re: Following up — {company.name}",
            "body": (
                f"Hi {first_name},\n\n"
                "Thank you for the context. The timeline and constraints you mentioned "
                "are exactly the situation we designed for — our approach doesn't require "
                "any core replacement.\n\n"
                "Would a 20-minute call next week work to walk through how we've solved "
                "this for similar-sized credit unions?\n\nBest,\n[Your name]"
            ),
            "rag_chunks_used": [],
            "note": "template_mode"
        }

    prompt = FOLLOWUP_PROMPT.format(
        cu_context=cu_context,
        rag_context=rag_context,
        original_message=req.original_message[:1500],
        client_response=req.client_response
    )

    resp = ai.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=800,
        messages=[{"role": "user", "content": prompt}]
    )

    raw = resp.content[0].text
    try:
        parsed = json.loads(raw.replace("```json","").replace("```","").strip())
    except Exception:
        parsed = {"subject": f"Re: {company.name}", "body": raw}

    db.add(AIMessage(
        id=str(uuid.uuid4()),
        company_id=company.id,
        contact_id=contact.id if contact else None,
        message_type="email_followup",
        subject_line=parsed.get("subject"),
        body=parsed.get("body"),
        tokens_used=resp.usage.output_tokens
    ))
    db.commit()

    return {**parsed, "rag_chunks_used": rag_chunks,
            "tokens_used": resp.usage.output_tokens}
