"""
app/api/gmail_auth.py
Gmail OAuth login (alongside password) + email thread linking + send-from-app
"""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
from datetime import datetime
import secrets

from app.db.database import get_db
from app.models import User, Company, Contact, EmailThreadLink
from app.core.security import get_current_user, create_access_token
from app.services.gmail_service import (
    get_auth_url, exchange_code_for_tokens,
    find_threads_for_company, link_thread_manually, send_email
)

router = APIRouter()

# In-memory state store for OAuth CSRF protection (use Redis in production)
_pending_states = {}


# ══════════════════════════════════════════════════════════════
# 1. LOGIN WITH GOOGLE (alongside existing email/password)
# ══════════════════════════════════════════════════════════════

@router.get("/api/auth/gmail/login")
async def gmail_login_start():
    """
    Frontend redirects here when "Continue with Google" is clicked on the
    login page (shown ALONGSIDE the existing email/password form).
    """
    state = secrets.token_urlsafe(24)
    _pending_states[state] = {"created_at": datetime.utcnow()}
    auth_url = get_auth_url(state)
    return RedirectResponse(auth_url)


@router.get("/api/auth/gmail/callback")
async def gmail_login_callback(code: str, state: str, db: Session = Depends(get_db)):
    """
    Google redirects here after consent. Exchange code for tokens, find-or-create
    the user, store refresh_token, issue our own JWT.
    """
    if state not in _pending_states:
        raise HTTPException(400, "Invalid or expired OAuth state")
    _pending_states.pop(state)

    tokens = exchange_code_for_tokens(code)

    user = db.query(User).filter_by(email=tokens["email"]).first()
    if not user:
        user = User(
            email=tokens["email"],
            full_name=tokens["email"].split("@")[0].replace(".", " ").title(),
            auth_provider="google",
            hashed_password=None,
        )
        db.add(user)

    user.gmail_email         = tokens["email"]
    user.gmail_refresh_token = tokens["refresh_token"]
    user.gmail_connected_at  = datetime.utcnow()
    db.commit()

    jwt_token = create_access_token({"sub": user.id})

    import os
    frontend_url = os.getenv("FRONTEND_URL", "http://localhost:3000")
    return RedirectResponse(f"{frontend_url}/auth/callback?token={jwt_token}")


# ══════════════════════════════════════════════════════════════
# 2. CONNECT GMAIL (for password-login users who want to link Gmail)
# ══════════════════════════════════════════════════════════════

@router.get("/api/auth/gmail/connect")
async def gmail_connect_start(current_user: User = Depends(get_current_user)):
    """Returns the Google consent URL so the frontend can redirect the user."""
    state = secrets.token_urlsafe(24)
    _pending_states[state] = {"user_id": current_user.id, "created_at": datetime.utcnow()}
    return {"auth_url": get_auth_url(state, connect=True)}


@router.get("/api/auth/gmail/connect-callback")
async def gmail_connect_callback(code: str, state: str, db: Session = Depends(get_db)):
    pending = _pending_states.pop(state, None)
    if not pending or "user_id" not in pending:
        raise HTTPException(400, "Invalid OAuth state")

    tokens = exchange_code_for_tokens(code, connect=True)
    user = db.query(User).filter_by(id=pending["user_id"]).first()
    user.gmail_email         = tokens["email"]
    user.gmail_refresh_token = tokens["refresh_token"]
    user.gmail_connected_at  = datetime.utcnow()
    db.commit()

    import os
    frontend_url = os.getenv("FRONTEND_URL", "http://localhost:3000")
    return RedirectResponse(f"{frontend_url}/settings?gmail_connected=true")


# ══════════════════════════════════════════════════════════════
# 3. EMAIL THREAD HISTORY FOR A COMPANY
# ══════════════════════════════════════════════════════════════

@router.get("/api/companies/{company_id}/email-threads")
async def get_company_email_threads(
    company_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Used by the Outreach tab — shows email conversation history with this CU."""
    if not current_user.gmail_refresh_token:
        raise HTTPException(428, "Gmail not connected. Connect it in Settings first.")

    company = db.query(Company).filter_by(id=company_id).first()
    if not company:
        raise HTTPException(404, "Company not found")

    domain = None
    if company.website:
        domain = company.website.replace("https://", "").replace("http://", "") \
                                 .replace("www.", "").split("/")[0]

    threads = find_threads_for_company(
        current_user.gmail_refresh_token,
        company_name=company.name,
        company_domain=domain,
    )
    return {"company_id": company_id, "threads": threads, "matched_domain": domain}


class ManualLinkRequest(BaseModel):
    thread_id: str

@router.post("/api/companies/{company_id}/email-threads/link")
async def manually_link_thread(
    company_id: str,
    req: ManualLinkRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Manual link fallback — user pastes a Gmail thread ID."""
    if not current_user.gmail_refresh_token:
        raise HTTPException(428, "Gmail not connected")

    thread = link_thread_manually(current_user.gmail_refresh_token, req.thread_id)

    link = EmailThreadLink(
        company_id=company_id,
        user_id=current_user.id,
        gmail_thread_id=req.thread_id,
    )
    db.add(link)
    db.commit()

    return {"linked": True, "thread": thread}


# ══════════════════════════════════════════════════════════════
# 4. SEND EMAIL FROM THE APP
# ══════════════════════════════════════════════════════════════

class SendEmailRequest(BaseModel):
    company_id: str
    contact_id: str
    subject: str
    body: str
    thread_id: str | None = None

@router.post("/api/outreach/send-email")
async def send_outreach_email(
    req: SendEmailRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Sends the AI-generated email as the logged-in user's own Gmail account."""
    if not current_user.gmail_refresh_token:
        raise HTTPException(428, "Gmail not connected. Connect it in Settings first.")

    contact = db.query(Contact).filter_by(id=req.contact_id).first()
    if not contact or not contact.email:
        raise HTTPException(400, "Contact has no email on file")

    from app.models import AIMessage
    result = send_email(
        current_user.gmail_refresh_token,
        to=contact.email,
        subject=req.subject,
        body=req.body,
        thread_id=req.thread_id,
    )

    db.add(AIMessage(
        company_id=req.company_id, contact_id=req.contact_id,
        message_type="email", subject_line=req.subject, body=req.body,
        sent_at=datetime.utcnow(), gmail_message_id=result["message_id"],
    ))
    db.add(EmailThreadLink(
        company_id=req.company_id, user_id=current_user.id,
        gmail_thread_id=result["thread_id"],
    ))
    db.commit()

    return result
