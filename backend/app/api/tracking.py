"""
app/api/tracking.py
Email open and click tracking endpoints — no auth required (hit by email clients).
"""
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, BackgroundTasks
from fastapi.responses import Response, RedirectResponse
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.db.database import get_db
from app.models import AIMessage, OutreachEvent, Signal, Company

router = APIRouter()

# Standard transparent 1×1 GIF
_PIXEL = bytes([
    0x47, 0x49, 0x46, 0x38, 0x39, 0x61, 0x01, 0x00,
    0x01, 0x00, 0x80, 0x00, 0x00, 0xff, 0xff, 0xff,
    0x00, 0x00, 0x00, 0x21, 0xf9, 0x04, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x2c, 0x00, 0x00, 0x00, 0x00,
    0x01, 0x00, 0x01, 0x00, 0x00, 0x02, 0x02, 0x44,
    0x01, 0x00, 0x3b,
])


def _record_open(message_id: str, db: Session):
    msg = db.query(AIMessage).filter_by(id=message_id).first()
    if not msg:
        return

    msg.open_count = (msg.open_count or 0) + 1
    db.add(OutreachEvent(
        id=str(uuid.uuid4()),
        message_id=message_id,
        contact_id=msg.contact_id,
        event_type="opened",
        event_data={"open_number": msg.open_count},
        occurred_at=datetime.utcnow(),
    ))

    # Engagement signals on 1st and 3rd open
    if msg.open_count == 1:
        _add_signal(db, msg, "growth", 65,
                    "Contact opened outreach email — initial engagement confirmed")
    elif msg.open_count == 3:
        _add_signal(db, msg, "growth", 80,
                    "Contact re-reading outreach (3+ opens) — strong buying interest")
        _bump_score(db, msg, 10)

    db.commit()


def _record_click(message_id: str, url: str, db: Session):
    msg = db.query(AIMessage).filter_by(id=message_id).first()
    if not msg:
        return

    msg.click_count = (msg.click_count or 0) + 1
    db.add(OutreachEvent(
        id=str(uuid.uuid4()),
        message_id=message_id,
        contact_id=msg.contact_id,
        event_type="clicked",
        event_data={"url": url, "click_number": msg.click_count},
        occurred_at=datetime.utcnow(),
    ))

    # Signal on every click (deduplicated by checking existing)
    already = db.query(Signal).filter(
        Signal.company_id == msg.company_id,
        Signal.source == "email_tracking",
        Signal.signal_type == "growth",
        Signal.signal_label.like("Contact clicked%"),
    ).first()
    if not already:
        _add_signal(db, msg, "growth", 85,
                    "Contact clicked link in outreach email — active interest confirmed")
        _bump_score(db, msg, 10)

    db.commit()


def _add_signal(db: Session, msg: AIMessage, sig_type: str, sev: int, label: str):
    db.add(Signal(
        id=str(uuid.uuid4()),
        company_id=msg.company_id,
        signal_type=sig_type,
        signal_label=label,
        severity=sev,
        source="email_tracking",
        is_active=True,
    ))


def _bump_score(db: Session, msg: AIMessage, delta: int):
    co = db.query(Company).filter_by(id=msg.company_id).first()
    if co:
        co.opportunity_score = min(100, (co.opportunity_score or 50) + delta)


# ── Public endpoints (no auth — hit by email clients) ────────────────────────

@router.get("/api/track/open/{message_id}", include_in_schema=False)
async def track_open(
    message_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    background_tasks.add_task(_record_open, message_id, db)
    return Response(content=_PIXEL, media_type="image/gif",
                    headers={"Cache-Control": "no-store, no-cache"})


@router.get("/api/track/click/{message_id}", include_in_schema=False)
async def track_click(
    message_id: str,
    url: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    background_tasks.add_task(_record_click, message_id, url, db)
    return RedirectResponse(url=url, status_code=302,
                            headers={"Cache-Control": "no-store"})
