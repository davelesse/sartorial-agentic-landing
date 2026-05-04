"""
═══════════════════════════════════════════════════════════
SARTORIAL AGENTIC — Partners Router
Dashboard partenaire : inscription, commissions, clients référés,
lien d'affiliation, rapports.
═══════════════════════════════════════════════════════════
"""

import secrets
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models import Partner, Referral, Tenant, User
from app.schemas import PartnerResponse

from pydantic import BaseModel

logger = structlog.get_logger()
router = APIRouter()


# ─── Schemas ───

class PartnerRegisterRequest(BaseModel):
    plan: str = "associe"  # associe | maison_partenaire


class PartnerDashboardResponse(BaseModel):
    partner: PartnerResponse
    stats: dict
    referrals: list[dict]


class CommissionReportResponse(BaseModel):
    total_earned_cents: int
    total_earned_eur: float
    pending_cents: int
    paid_cents: int
    referral_count: int
    monthly_breakdown: list[dict]


# ─── Routes ───

@router.post("/register", response_model=PartnerResponse, status_code=status.HTTP_201_CREATED)
async def register_as_partner(
    request: PartnerRegisterRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    S'inscrire comme partenaire/revendeur.
    Génère un code d'affiliation unique.
    """
    # Vérifier si déjà partenaire
    existing = await db.execute(select(Partner).where(Partner.user_id == user.id))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Vous êtes déjà partenaire")

    valid_plans = {"associe", "maison_partenaire"}
    if request.plan not in valid_plans:
        raise HTTPException(status_code=400, detail=f"Plan invalide. Options : {valid_plans}")

    commission_rates = {"associe": 20.00, "maison_partenaire": 30.00}

    # Générer un code unique mémorable
    code = f"SA-{user.email.split('@')[0][:6].upper()}-{secrets.token_hex(3).upper()}"

    partner = Partner(
        user_id=user.id,
        plan=request.plan,
        commission_rate=commission_rates[request.plan],
        affiliate_code=code,
        is_active=True,
    )
    db.add(partner)

    # Upgrade role
    user.role = "partner"

    await db.commit()
    await db.refresh(partner)

    logger.info("partner.registered", user_id=str(user.id), plan=request.plan, code=code)

    return partner


@router.get("/me", response_model=PartnerDashboardResponse)
async def partner_dashboard(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Dashboard complet du partenaire avec stats et liste des clients référés."""
    result = await db.execute(
        select(Partner)
        .where(Partner.user_id == user.id)
        .options(
            selectinload(Partner.referrals).selectinload(Referral.tenant)
        )
    )
    partner = result.scalar_one_or_none()
    if not partner:
        raise HTTPException(status_code=404, detail="Compte partenaire introuvable")

    # Construire les détails referrals — eager loaded, 0 requêtes supplémentaires
    referral_details = []
    for ref in partner.referrals:
        tenant = ref.tenant
        if tenant:
            referral_details.append({
                "tenant_name": tenant.name,
                "tenant_plan": tenant.plan,
                "subscription_status": tenant.subscription_status,
                "commission_rate": float(ref.commission_rate),
                "total_paid_cents": ref.total_paid_cents,
                "total_paid_eur": round(ref.total_paid_cents / 100, 2),
                "created_at": ref.created_at.isoformat(),
            })

    # Calcul des stats
    total_referrals = len(partner.referrals)
    active_referrals = sum(
        1 for r in referral_details if r["subscription_status"] in ("active", "trialing")
    )
    total_earned = partner.total_earnings_cents

    stats = {
        "total_referrals": total_referrals,
        "active_referrals": active_referrals,
        "total_earned_cents": total_earned,
        "total_earned_eur": round(total_earned / 100, 2),
        "affiliate_code": partner.affiliate_code,
        "affiliate_url": f"https://sartorial-agentic.ai/register?ref={partner.affiliate_code}",
        "commission_rate": float(partner.commission_rate),
        "plan": partner.plan,
    }

    return PartnerDashboardResponse(
        partner=partner,
        stats=stats,
        referrals=referral_details,
    )


@router.get("/commissions", response_model=CommissionReportResponse)
async def commission_report(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Rapport détaillé des commissions."""
    result = await db.execute(select(Partner).where(Partner.user_id == user.id))
    partner = result.scalar_one_or_none()
    if not partner:
        raise HTTPException(status_code=404, detail="Compte partenaire introuvable")

    referrals = await db.execute(
        select(Referral).where(Referral.partner_id == partner.id)
    )
    refs = referrals.scalars().all()

    total_earned = partner.total_earnings_cents
    total_paid = sum(r.total_paid_cents for r in refs)
    pending = total_earned - total_paid

    # Breakdown mensuel simplifié (à enrichir avec dates réelles)
    monthly = []

    return CommissionReportResponse(
        total_earned_cents=total_earned,
        total_earned_eur=round(total_earned / 100, 2),
        pending_cents=max(0, pending),
        paid_cents=total_paid,
        referral_count=len(refs),
        monthly_breakdown=monthly,
    )


@router.get("/link")
async def get_affiliate_link(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Récupère le lien d'affiliation du partenaire."""
    result = await db.execute(select(Partner).where(Partner.user_id == user.id))
    partner = result.scalar_one_or_none()
    if not partner:
        raise HTTPException(status_code=404, detail="Compte partenaire introuvable")

    return {
        "affiliate_code": partner.affiliate_code,
        "affiliate_url": f"https://sartorial-agentic.ai/register?ref={partner.affiliate_code}",
        "commission_rate": float(partner.commission_rate),
    }
