"""
═══════════════════════════════════════════════════════════
SARTORIAL AGENTIC — Auth Router
Register, login, current user.
═══════════════════════════════════════════════════════════
"""

import re
from datetime import datetime, timedelta, timezone

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.security import create_access_token, hash_password, verify_password
from app.models import Partner, Tenant, User
from app.schemas import (
    LoginRequest, RegisterRequest, TokenResponse, UserResponse,
)

logger = structlog.get_logger()
router = APIRouter()


def _slugify(text: str) -> str:
    """Simple slug generator — lowercase, alphanumeric, dashes."""
    slug = re.sub(r"[^\w\s-]", "", text.lower())
    slug = re.sub(r"[\s_-]+", "-", slug).strip("-")
    return slug[:80]


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(
    request: RegisterRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Register a new user + create their default tenant.
    Starts a 14-day trial by default.
    """
    # Vérifier unicité email (message générique — évite l'énumération d'emails)
    existing = await db.execute(select(User).where(User.email == request.email))
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Inscription impossible. Veuillez réessayer.",
        )

    # Créer user
    user = User(
        email=request.email,
        hashed_password=hash_password(request.password),
        full_name=request.full_name,
        role="client",
        is_active=True,
    )
    db.add(user)
    await db.flush()

    # Slug unique pour tenant — avec protection contre la race condition
    base_slug = _slugify(request.tenant_name) or "atelier"
    slug = base_slug
    counter = 1
    while True:
        existing_slug = await db.execute(select(Tenant).where(Tenant.slug == slug))
        if not existing_slug.scalar_one_or_none():
            break
        counter += 1
        slug = f"{base_slug}-{counter}"
        if counter > 999:  # safety net
            import secrets
            slug = f"{base_slug}-{secrets.token_hex(4)}"
            break

    # Créer tenant avec trial 14j
    tenant = Tenant(
        name=request.tenant_name,
        slug=slug,
        owner_id=user.id,
        plan="atelier",
        subscription_status="trialing",
        trial_ends_at=datetime.now(timezone.utc) + timedelta(days=14),
        executions_reset_at=datetime.now(timezone.utc) + timedelta(days=30),
    )
    db.add(tenant)

    # Tracker affiliate si présent
    if request.affiliate_code:
        partner_result = await db.execute(
            select(Partner).where(Partner.affiliate_code == request.affiliate_code)
        )
        partner = partner_result.scalar_one_or_none()
        if partner and partner.is_active:
            from app.models import Referral
            referral = Referral(
                partner_id=partner.id,
                tenant_id=tenant.id,
                commission_rate=partner.commission_rate,
            )
            db.add(referral)
            logger.info("auth.referral_tracked", partner=str(partner.id), tenant=str(tenant.id))

    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Inscription impossible. Veuillez réessayer.",
        )

    logger.info("auth.registered", user_id=str(user.id), tenant_id=str(tenant.id), email=request.email)

    token, expires_in = create_access_token(user_id=user.id, tenant_id=tenant.id, role=user.role)
    return TokenResponse(access_token=token, expires_in=expires_in)


@router.post("/login", response_model=TokenResponse)
async def login(
    request: LoginRequest,
    db: AsyncSession = Depends(get_db),
):
    """Authenticate with email + password."""
    result = await db.execute(select(User).where(User.email == request.email))
    user = result.scalar_one_or_none()

    if not user or not verify_password(request.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email ou mot de passe incorrect",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Compte désactivé",
        )

    # Récupère le tenant par défaut
    tenant_result = await db.execute(
        select(Tenant).where(Tenant.owner_id == user.id).limit(1)
    )
    tenant = tenant_result.scalar_one_or_none()

    logger.info("auth.login", user_id=str(user.id), email=user.email)

    token, expires_in = create_access_token(
        user_id=user.id,
        tenant_id=tenant.id if tenant else None,
        role=user.role,
    )
    return TokenResponse(access_token=token, expires_in=expires_in)


@router.get("/me", response_model=UserResponse)
async def me(user: User = Depends(get_current_user)):
    """Return the current authenticated user's profile."""
    return user
