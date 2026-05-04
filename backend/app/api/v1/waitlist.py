"""
═══════════════════════════════════════════════════════════
SARTORIAL AGENTIC — Waitlist Router
Public endpoint for landing page email capture.
═══════════════════════════════════════════════════════════
"""

import structlog
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models import Waitlist
from app.schemas import WaitlistRequest, WaitlistResponse

logger = structlog.get_logger()
router = APIRouter()


@router.post("/", response_model=WaitlistResponse)
async def join_waitlist(
    request: WaitlistRequest,
    db: AsyncSession = Depends(get_db),
):
    """Register an email to the pre-launch waitlist."""
    # Idempotent — si déjà présent, on renvoie juste success
    existing = await db.execute(select(Waitlist).where(Waitlist.email == request.email))
    if existing.scalar_one_or_none():
        return WaitlistResponse(
            success=True,
            message="Vous êtes déjà sur la liste. Nous vous contacterons bientôt.",
        )

    entry = Waitlist(email=request.email, source=request.source)
    db.add(entry)
    await db.commit()

    logger.info("waitlist.joined", email=request.email, source=request.source)

    return WaitlistResponse(
        success=True,
        message="Bienvenue dans l'atelier. Nous vous contacterons très bientôt.",
    )
