"""
backend/app/services/gmail_service.py
========================================
Handles Gmail OAuth (alongside existing email/password login), per-user
token storage, searching sent/received threads matched to a CU, and
sending emails directly from the logged-in user's own Gmail account.

SETUP REQUIRED (one-time, you don't have OAuth creds yet):
  1. Go to console.cloud.google.com → create a project (or use existing)
  2. APIs & Services → Library → enable "Gmail API"
  3. APIs & Services → Credentials → Create OAuth client ID
     - Application type: Web application
     - Authorized redirect URI: http://localhost:8000/api/auth/gmail/callback
       (and your production URL when you deploy)
  4. Download the client_id and client_secret
  5. Add to backend/.env:
       GOOGLE_CLIENT_ID=xxxx.apps.googleusercontent.com
       GOOGLE_CLIENT_SECRET=xxxx
       GOOGLE_REDIRECT_URI=http://localhost:8000/api/auth/gmail/callback
  6. pip install google-auth google-auth-oauthlib google-api-python-client

SCOPES requested:
  gmail.readonly  → search and read threads for linking to CUs
  gmail.send      → send emails as the logged-in user
  userinfo.email  → get their email address to create/match the account
"""

import os
import re
import base64
import json
from datetime import datetime
from email.mime.text import MIMEText
from typing import Optional

from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from google.auth.transport.requests import Request as GoogleRequest

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/userinfo.email",
    "openid",
]

CLIENT_CONFIG = {
    "web": {
        "client_id":     os.getenv("GOOGLE_CLIENT_ID", ""),
        "client_secret": os.getenv("GOOGLE_CLIENT_SECRET", ""),
        "redirect_uris": [os.getenv("GOOGLE_REDIRECT_URI",
                          "http://localhost:8000/api/auth/gmail/callback")],
        "auth_uri":  "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
    }
}


# ══════════════════════════════════════════════════════════════
# OAUTH FLOW
# ══════════════════════════════════════════════════════════════

def get_auth_url(state: str) -> str:
    """
    Step 1: Build the Google consent screen URL.
    `state` should encode something you can verify on callback —
    e.g. a signed random nonce stored in the user's session.
    """
    flow = Flow.from_client_config(CLIENT_CONFIG, scopes=SCOPES)
    flow.redirect_uri = CLIENT_CONFIG["web"]["redirect_uris"][0]
    auth_url, _ = flow.authorization_url(
        access_type="offline",        # ← needed to get a refresh_token
        include_granted_scopes="true",
        prompt="consent",             # forces refresh_token on every login
        state=state,
    )
    return auth_url


def exchange_code_for_tokens(code: str) -> dict:
    """
    Step 2: Exchange the authorization code (from Google's redirect)
    for access_token + refresh_token + the user's Gmail address.
    """
    flow = Flow.from_client_config(CLIENT_CONFIG, scopes=SCOPES)
    flow.redirect_uri = CLIENT_CONFIG["web"]["redirect_uris"][0]
    flow.fetch_token(code=code)
    creds = flow.credentials

    # Get the user's email address
    service = build("oauth2", "v2", credentials=creds)
    user_info = service.userinfo().get().execute()

    return {
        "email":         user_info["email"],
        "access_token":  creds.token,
        "refresh_token": creds.refresh_token,
        "token_expiry":  creds.expiry.isoformat() if creds.expiry else None,
    }


def build_credentials(refresh_token: str) -> Credentials:
    """Rebuild a Credentials object from a stored refresh_token."""
    creds = Credentials(
        token=None,
        refresh_token=refresh_token,
        client_id=CLIENT_CONFIG["web"]["client_id"],
        client_secret=CLIENT_CONFIG["web"]["client_secret"],
        token_uri=CLIENT_CONFIG["web"]["token_uri"],
        scopes=SCOPES,
    )
    creds.refresh(GoogleRequest())  # gets a fresh access_token
    return creds


def get_gmail_service(refresh_token: str):
    """Build an authenticated Gmail API client for this user."""
    creds = build_credentials(refresh_token)
    return build("gmail", "v1", credentials=creds)


# ══════════════════════════════════════════════════════════════
# MATCHING — domain + subject + business name search
# ══════════════════════════════════════════════════════════════

def find_threads_for_company(refresh_token: str, company_name: str,
                              company_domain: Optional[str] = None,
                              max_results: int = 20) -> list:
    """
    Searches the logged-in user's Gmail for threads related to a CU,
    using THREE matching strategies combined (per approved spec):
      1. Domain match  — to:/from: @company_domain
      2. Subject match — subject contains the company name
      3. Business name — body/subject mentions the company name

    Returns threads sorted newest first, each with messages, so the
    outreach panel can render a full conversation timeline.
    """
    service = get_gmail_service(refresh_token)

    query_parts = []
    if company_domain:
        query_parts.append(f"(to:@{company_domain} OR from:@{company_domain})")
    # Always include name-based search too — domain alone misses cases
    # where their reply comes from a personal/different address
    safe_name = company_name.replace('"', '')
    query_parts.append(f'"{safe_name}"')

    query = " OR ".join(query_parts) if len(query_parts) > 1 else query_parts[0]

    results = service.users().threads().list(
        userId="me", q=query, maxResults=max_results
    ).execute()

    threads = []
    for stub in results.get("threads", []):
        thread = service.users().threads().get(
            userId="me", id=stub["id"], format="full"
        ).execute()
        threads.append(_parse_thread(thread))

    threads.sort(key=lambda t: t["last_message_date"], reverse=True)
    return threads


def link_thread_manually(refresh_token: str, thread_id: str) -> dict:
    """
    Manual link fallback — when a user finds a relevant thread that
    didn't match automatically (e.g. domain mismatch), they paste the
    Gmail thread ID or URL and we fetch + return it directly so the
    frontend can confirm + save the company_id association.
    """
    service = get_gmail_service(refresh_token)
    thread = service.users().threads().get(
        userId="me", id=thread_id, format="full"
    ).execute()
    return _parse_thread(thread)


def _parse_thread(thread: dict) -> dict:
    """Convert raw Gmail API thread response into clean message list."""
    messages = []
    for msg in thread.get("messages", []):
        headers = {h["name"]: h["value"] for h in msg["payload"]["headers"]}
        body = _extract_body(msg["payload"])
        messages.append({
            "id":      msg["id"],
            "from":    headers.get("From", ""),
            "to":      headers.get("To", ""),
            "subject": headers.get("Subject", "(no subject)"),
            "date":    headers.get("Date", ""),
            "snippet": msg.get("snippet", ""),
            "body":    body,
        })

    last_date = messages[-1]["date"] if messages else ""
    return {
        "thread_id":         thread["id"],
        "subject":           messages[0]["subject"] if messages else "",
        "messages":          messages,
        "message_count":     len(messages),
        "last_message_date": last_date,
    }


def _extract_body(payload: dict) -> str:
    """Pull plain-text body out of a Gmail message payload."""
    if "parts" in payload:
        for part in payload["parts"]:
            if part["mimeType"] == "text/plain":
                data = part["body"].get("data", "")
                return base64.urlsafe_b64decode(data).decode("utf-8", errors="ignore")
    elif payload.get("body", {}).get("data"):
        return base64.urlsafe_b64decode(
            payload["body"]["data"]
        ).decode("utf-8", errors="ignore")
    return ""


# ══════════════════════════════════════════════════════════════
# SEND — directly from the logged-in user's Gmail
# ══════════════════════════════════════════════════════════════

def send_email(refresh_token: str, to: str, subject: str, body: str,
               thread_id: Optional[str] = None) -> dict:
    """
    Sends an email AS the logged-in user — appears in their own Sent
    folder, replies land in their own inbox (per approved spec: "use
    the logged in user", not a shared system sender).

    If thread_id is provided, the email is sent as a reply within that
    existing Gmail thread (proper threading, not a new conversation).
    """
    service = get_gmail_service(refresh_token)

    message = MIMEText(body)
    message["to"] = to
    message["subject"] = subject

    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
    body_payload = {"raw": raw}
    if thread_id:
        body_payload["threadId"] = thread_id

    sent = service.users().messages().send(
        userId="me", body=body_payload
    ).execute()

    return {
        "message_id": sent["id"],
        "thread_id":  sent.get("threadId"),
        "sent_at":    datetime.utcnow().isoformat(),
    }
