"""
═══════════════════════════════════════════════════════════
SARTORIAL AGENTIC — Commission Only Funnel v2
Argument massif de conversion / closing.

STRATÉGIE :
  1. Le prospect hésite → on lui propose 30 jours gratuits
  2. Pendant 30 jours : accès complet plan Atelier, agents actifs,
     résultats réels (leads, RDV, contenu généré)
  3. À J+30 : choix automatique
     a) Le prospect est convaincu → conversion vers un plan payant
     b) Le prospect ne convertit pas → suspension douce (lecture seule)
  4. Séquence email automatisée :
     - J+1   : bienvenue + onboarding
     - J+7   : premiers résultats (rapport auto)
     - J+14  : mi-parcours, suggestion d'upgrade
     - J+21  : rappel fin d'essai dans 9 jours
     - J+27  : dernière chance, 3 jours restants
     - J+30  : fin d'essai, proposition de plan

  Ce n'est PAS un plan permanent. C'est un funnel de conversion
  déguisé en "offre sans risque" — le closing parfait.

  Point d'entrée : /api/v1/commission-only/apply
  N'apparaît nulle part sur le site public.
  Déclenché uniquement par un commercial ou un lien privé.
═══════════════════════════════════════════════════════════
"""

import re
import secrets
from datetime import datetime, timedelta, timezone

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import create_access_token, hash_password
from app.models import Partner, Referral, Tenant, User
from app.stripe.tasks import commission_only_email_sequence

logger = structlog.get_logger()
router = APIRouter()

# ─── Configuration ───

COMMISSION_TRIAL_DAYS = 30
COMMISSION_PLAN_ACCESS = "atelier"  # Accès au plan Atelier complet pendant l'essai

# Séquence email automatisée (jours après inscription)
EMAIL_SEQUENCE = [
    {"day": 1,  "template": "commission_only_welcome",     "subject_key": "Bienvenue — votre essai de 30 jours commence"},
    {"day": 7,  "template": "commission_only_first_results","subject_key": "Vos premiers résultats sont là"},
    {"day": 14, "template": "commission_only_midpoint",     "subject_key": "Mi-parcours — vos agents performent"},
    {"day": 21, "template": "commission_only_reminder",     "subject_key": "Plus que 9 jours d'essai gratuit"},
    {"day": 27, "template": "commission_only_last_chance",  "subject_key": "3 jours restants — ne perdez pas vos agents"},
    {"day": 30, "template": "commission_only_expired",      "subject_key": "Votre essai est terminé — choisissez votre plan"},
]


# ─── Schemas ───

class CommissionOnlyRequest(BaseModel):
    """
    Formulaire simplifié pour le prospect.
    Le message qu'il voit :
      "30 jours gratuits. Accès complet. Zéro risque.
       Si vous êtes convaincu, vous choisissez votre plan.
       Sinon, on se quitte bons amis."
    """
    email: EmailStr
    full_name: str = Field(min_length=2, max_length=255)
    company_name: str = Field(min_length=2, max_length=255)
    sector: str = Field(min_length=2, max_length=50)
    phone: str | None = None
    referred_by: str | None = Field(default=None, description="Code partenaire si présent")


class CommissionOnlyResponse(BaseModel):
    success: bool
    message: str
    access_token: str | None = None
    tenant_slug: str | None = None
    trial_ends_at: str | None = None
    days_remaining: int | None = None


class CommissionOnlyStatusResponse(BaseModel):
    is_commission_only: bool
    days_remaining: int
    trial_ends_at: str
    can_convert: bool
    results_summary: dict


# ─── Routes ───

@router.post("/apply", response_model=CommissionOnlyResponse)
async def apply_commission_only(
    request: CommissionOnlyRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Point d'entrée du funnel Commission Only.

    Flow :
    1. Crée un compte user + tenant avec trial 30 jours
    2. Accès complet plan Atelier (3 agents transversaux)
    3. Pas de CB requise — zéro friction
    4. Séquence email automatisée planifiée
    5. À J+30 : notification + suspension si pas de conversion
    """
    # Email unique ?
    existing = await db.execute(select(User).where(User.email == request.email))
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=409,
            detail="Un compte existe déjà avec cet email. Connectez-vous ou choisissez un plan.",
        )

    # Mot de passe temporaire (envoyé par email)
    temp_password = secrets.token_urlsafe(12)

    user = User(
        email=request.email,
        hashed_password=hash_password(temp_password),
        full_name=request.full_name,
        role="client",
        is_active=True,
    )
    db.add(user)
    await db.flush()

    # Slug tenant
    base_slug = re.sub(r"[^\w\s-]", "", request.company_name.lower())
    base_slug = re.sub(r"[\s_-]+", "-", base_slug).strip("-")[:60]
    slug = f"{base_slug}-co"
    counter = 1
    while True:
        exists = await db.execute(select(Tenant).where(Tenant.slug == slug))
        if not exists.scalar_one_or_none():
            break
        counter += 1
        if counter > 999:
            slug = f"{base_slug}-co-{secrets.token_hex(4)}"
            break
        slug = f"{base_slug}-co-{counter}"

    trial_end = datetime.now(timezone.utc) + timedelta(days=COMMISSION_TRIAL_DAYS)

    tenant = Tenant(
        name=request.company_name,
        slug=slug,
        owner_id=user.id,
        plan=COMMISSION_PLAN_ACCESS,
        sectors=[request.sector],
        subscription_status="trialing",  # Même statut que les trials normaux
        trial_ends_at=trial_end,         # Mais 30 jours au lieu de 14
        executions_reset_at=datetime.now(timezone.utc) + timedelta(days=30),
        settings={
            "billing_model": "commission_only",
            "commission_trial_days": COMMISSION_TRIAL_DAYS,
            "phone": request.phone,
            "source": "commission_only_funnel",
            "applied_at": datetime.now(timezone.utc).isoformat(),
            "email_sequence": [
                {"day": e["day"], "template": e["template"], "sent": False}
                for e in EMAIL_SEQUENCE
            ],
            "conversion_status": "in_trial",  # in_trial | converted | expired | extended
        },
    )
    db.add(tenant)

    # Tracking partenaire
    if request.referred_by:
        partner_result = await db.execute(
            select(Partner).where(Partner.affiliate_code == request.referred_by)
        )
        partner = partner_result.scalar_one_or_none()
        if partner and partner.is_active:
            referral = Referral(
                partner_id=partner.id,
                tenant_id=tenant.id,
                commission_rate=partner.commission_rate,
            )
            db.add(referral)
            logger.info("commission_only.referral_tracked", partner=str(partner.id))

    await db.commit()

    logger.info(
        "commission_only.applied",
        user_id=str(user.id),
        tenant_id=str(tenant.id),
        sector=request.sector,
        trial_ends=trial_end.isoformat(),
    )

    # Token d'accès
    token, _ = create_access_token(user_id=user.id, tenant_id=tenant.id, role=user.role)

    # Planifier la séquence email
    commission_only_email_sequence.delay(str(tenant.id), request.email, request.full_name)

    return CommissionOnlyResponse(
        success=True,
        message=f"Votre essai de {COMMISSION_TRIAL_DAYS} jours est activé. Bienvenue dans l'atelier.",
        access_token=token,
        tenant_slug=slug,
        trial_ends_at=trial_end.isoformat(),
        days_remaining=COMMISSION_TRIAL_DAYS,
    )


@router.get("/status/{tenant_id}", response_model=CommissionOnlyStatusResponse)
async def commission_only_status(
    tenant_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Vérifie le status d'un essai Commission Only.
    Utilisé par le dashboard pour afficher la barre de progression
    et le CTA de conversion.
    """
    from uuid import UUID

    result = await db.execute(select(Tenant).where(Tenant.id == UUID(tenant_id)))
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant introuvable")

    settings = tenant.settings or {}
    if settings.get("billing_model") != "commission_only":
        raise HTTPException(status_code=400, detail="Ce tenant n'est pas en Commission Only")

    now = datetime.now(timezone.utc)
    trial_end = tenant.trial_ends_at
    days_remaining = max(0, (trial_end - now).days) if trial_end else 0
    can_convert = days_remaining > 0

    # Résumé des résultats générés pendant l'essai
    from app.models import Task
    from sqlalchemy import func

    tasks_count = (await db.execute(
        select(func.count()).select_from(Task).where(Task.tenant_id == tenant.id)
    )).scalar_one()

    completed_count = (await db.execute(
        select(func.count()).select_from(Task)
        .where(Task.tenant_id == tenant.id, Task.status == "completed")
    )).scalar_one()

    return CommissionOnlyStatusResponse(
        is_commission_only=True,
        days_remaining=days_remaining,
        trial_ends_at=trial_end.isoformat() if trial_end else "",
        can_convert=can_convert,
        results_summary={
            "total_executions": tasks_count,
            "completed_executions": completed_count,
            "conversion_status": settings.get("conversion_status", "in_trial"),
            "trial_days_total": settings.get("commission_trial_days", 30),
            "trial_days_used": settings.get("commission_trial_days", 30) - days_remaining,
        },
    )


@router.post("/convert/{tenant_id}")
async def convert_to_paid(
    tenant_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Convertit un essai Commission Only en abonnement payant.
    Redirige vers Stripe Checkout.
    """
    from uuid import UUID
    from app.stripe.routes import router as stripe_router

    result = await db.execute(select(Tenant).where(Tenant.id == UUID(tenant_id)))
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant introuvable")

    settings = tenant.settings or {}
    if settings.get("billing_model") != "commission_only":
        raise HTTPException(status_code=400, detail="Ce tenant n'est pas en Commission Only")

    # Marquer comme converti
    settings["conversion_status"] = "converted"
    settings["converted_at"] = datetime.now(timezone.utc).isoformat()
    tenant.settings = settings
    await db.commit()

    logger.info("commission_only.converted", tenant_id=tenant_id)

    # Retourne l'info pour que le frontend redirige vers Stripe Checkout
    user_result = await db.execute(select(User).where(User.id == tenant.owner_id))
    user = user_result.scalar_one()

    return {
        "status": "ready_to_checkout",
        "message": "Choisissez votre plan pour continuer sans interruption.",
        "email": user.email,
        "tenant_id": str(tenant.id),
        "suggested_plan": "manufacture",  # On pousse vers Manufacture — meilleur pour eux
        "current_results": settings.get("conversion_status"),
    }
