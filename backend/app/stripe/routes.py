"""
═══════════════════════════════════════════════════════════
SARTORIAL AGENTIC — Stripe API Routes
Checkout sessions, customer portal, plan info.
═══════════════════════════════════════════════════════════
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.stripe import (
    create_checkout_session,
    create_customer_portal_session,
    PLANS,
)

router = APIRouter()


# ── Schemas ──

class CheckoutRequest(BaseModel):
    plan_id: str
    email: EmailStr
    tenant_id: str
    locale: str = "fr"
    affiliate_code: str | None = None


class CheckoutResponse(BaseModel):
    checkout_url: str


class PortalRequest(BaseModel):
    stripe_customer_id: str


class PlanInfo(BaseModel):
    plan_id: str
    name: str
    description: str
    price_eur: int
    price_display: str
    features: dict


# ── Routes ──

@router.get("/plans")
async def list_plans():
    """List all available plans with pricing."""
    plans = []
    for plan_id, plan in PLANS.items():
        plans.append({
            "plan_id": plan_id,
            "name": plan["name"],
            "description": plan["description"],
            "price_eur_cents": plan["price_eur"],
            "price_display": f"{plan['price_eur'] / 100:.0f}€/mois",
            "features": plan["metadata"],
        })
    return {"plans": plans}


@router.post("/checkout", response_model=CheckoutResponse)
async def create_checkout(
    request: CheckoutRequest,
    db: AsyncSession = Depends(get_db),
):
    """Create a Stripe Checkout Session for a plan."""
    if request.plan_id not in PLANS:
        raise HTTPException(
            status_code=400,
            detail=f"Plan inconnu: {request.plan_id}. Plans disponibles: {list(PLANS.keys())}",
        )

    try:
        url = await create_checkout_session(
            plan_id=request.plan_id,
            customer_email=request.email,
            tenant_id=request.tenant_id,
            locale=request.locale,
            affiliate_code=request.affiliate_code,
        )
        return CheckoutResponse(checkout_url=url)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/portal")
async def create_portal(request: PortalRequest):
    """Create a Stripe Customer Portal session."""
    try:
        url = await create_customer_portal_session(request.stripe_customer_id)
        return {"portal_url": url}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
