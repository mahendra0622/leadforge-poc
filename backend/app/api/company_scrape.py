"""
app/api/company_scrape.py
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from app.core.security import get_current_user
from app.services.company_scraper import scrape_company_url

router = APIRouter()


class ScrapeRequest(BaseModel):
    url: str


@router.post("/api/settings/scrape-company")
async def scrape_company(
    req: ScrapeRequest,
    current_user = Depends(get_current_user)
):
    """
    Scrapes the given company URL and returns extracted profile fields.
    Does NOT save anything — frontend shows results for user to review
    and confirm before saving via the normal PUT /api/auth/profile.
    """
    if not req.url or len(req.url) < 4:
        raise HTTPException(400, "Please provide a valid URL")

    try:
        result = await scrape_company_url(req.url)
    except ImportError:
        raise HTTPException(
            500,
            "Playwright not installed. Run: pip install playwright && "
            "playwright install chromium"
        )
    except Exception as e:
        raise HTTPException(500, f"Scrape failed: {str(e)}")

    if result.get("scrape_status") == "failed":
        raise HTTPException(422, result.get("error", "Could not extract data from this URL"))

    return result
