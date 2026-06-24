"""
app/services/source_refs.py
=============================
Central helper for building consistent source-reference metadata on signals.
Import this wherever a signal is created (cuna_ncua.py, news_signals.py,
web_scraper.py, ai_service.py) so every signal gets a traceable source.

Usage:
    from app.services.source_refs import web_source, file_source, pdf_source

    signal_dict["source_url"]   = web_source("https://...")["source_url"]

    # or build the whole dict in one call:
    refs = web_source("https://cutoday.us/article-123", label="CUToday.us")
    signal = Signal(..., **refs)
"""

import os
import re


def web_source(url: str, label: str = None) -> dict:
    """
    Build source reference dict for a signal that came from a web page
    (news article, scraped CU website, job posting page).
    """
    if not label:
        # Derive a clean label from the domain
        m = re.search(r"https?://(?:www\.)?([^/]+)", url or "")
        label = m.group(1) if m else "Web source"

    return {
        "source_url":   url,
        "source_file":  None,
        "source_page":  None,
        "source_label": label,
    }


def file_source(filename: str, label: str = None) -> dict:
    """
    Build source reference dict for a signal that came from a flat data
    file — NCUA bulk ZIP/TXT/CSV. No page number since these aren't
    paginated documents.
    """
    return {
        "source_url":   None,
        "source_file":  filename,
        "source_page":  None,
        "source_label": label or filename,
    }


def pdf_source(filename: str, page: int, label: str = None) -> dict:
    """
    Build source reference dict for a signal that came from a PDF
    (annual report, board minutes, CUNA conference deck).
    Page number IS tracked here since PDFs are paginated.
    """
    auto_label = f"{filename} p.{page}" if page else filename
    return {
        "source_url":   None,
        "source_file":  filename,
        "source_page":  page,
        "source_label": label or auto_label,
    }


def ncua_source(quarter: str = "2024Q4") -> dict:
    """Shortcut for the standard NCUA bulk-download source."""
    return file_source(
        filename=f"call-report-data-{quarter.lower()}.zip",
        label=f"NCUA {quarter} Call Report"
    )


def cuna_source() -> dict:
    """Shortcut for CUNA advocacy intelligence (structured, no single doc)."""
    return web_source(
        url="https://www.cuna.org/advocacy.html",
        label="CUNA Advocacy Priorities"
    )


def format_hover_text(signal) -> str:
    """
    Build the hover tooltip text shown in the UI for a signal's source.
    Used by the /api/signals/ endpoint when serializing signals.
    """
    if signal.source_url:
        return signal.source_label or signal.source_url
    if signal.source_file:
        if signal.source_page:
            return signal.source_label or f"{signal.source_file} (page {signal.source_page})"
        return signal.source_label or signal.source_file
    return "Source not recorded"
