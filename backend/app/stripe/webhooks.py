"""
═══════════════════════════════════════════════════════════
SARTORIAL AGENTIC — Stripe Webhook Handler
Receives and processes all Stripe events.
═══════════════════════════════════════════════════════════
"""

from decimal import Decimal
from uuid import UUID

import stripe
import structlog
from fastapi import APIRouter, Request, HTTPException, Depends
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db

logger = structlog.get_logger()
router = APIRouter()

stripe.api_key = settings.STRIPE_SECRET_KEY

# Mapping statuts Stripe → statuts internes
STRIPE_STATUS_MAP = {
    "active":    "active",
    "trialing":  "trialing",
    "past_due":  "past_due",
    "canceled":  "canceled",
    "unpaid":    "canceled",
    "incomplete": "past_due",
    "incomplete_expired": "canceled",
    "paused":    "past_due",
}

# Plans Stripe ID → plan name (à configurer dans .env au besoin)
STRIPE_PLAN_MAP = {
    "atelier":     "atelier",
    "manufacture": "manufacture",
    "maison":      "maison",
}


@router.post("/stripe")
async def stripe_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    """
    Main Stripe webhook endpoint.
    Validates signature, dispatches to handlers.
    """
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    if not sig_header:
        raise HTTPException(status_code=400, detail="Missing stripe-signature header")

    try:
        event = stripe.Webhook.construct_event(
            payload,
            sig_header,
            settings.STRIPE_WEBHOOK_SECRET,
        )
    except ValueError:
        logger.error("stripe.webhook.invalid_payload")
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe.error.SignatureVerificationError:
        logger.error("stripe.webhook.invalid_signature")
        raise HTTPException(status_code=400, detail="Invalid signature")

    event_type = event["type"]
    data = event["data"]["object"]

    logger.info("stripe.webhook.received", event_type=event_type, event_id=event["id"])

    handlers = {
        "checkout.session.completed":    handle_checkout_completed,
        "customer.subscription.created": handle_subscription_updated,  # même logique
        "customer.subscription.updated": handle_subscription_updated,
        "customer.subscription.deleted": handle_subscription_deleted,
        "invoice.paid":                  handle_invoice_paid,
        "invoice.payment_failed":        handle_invoice_payment_failed,
        "customer.created":              handle_customer_created,
    }

    handler = handlers.get(event_type)
    if handler:
        await handler(data, db)
    else:
        logger.debug("stripe.webhook.unhandled", event_type=event_type)

    return {"status": "ok"}


# ─────────────────────────────────────
# EVENT HANDLERS
# ─────────────────────────────────────

async def handle_checkout_completed(data: dict, db: AsyncSession):
    """
    Checkout completed — lie Stripe customer au tenant,
    active la subscription, enregistre le referral affilié si présent.
    """
    from app.models import Partner, Referral, Tenant

    metadata = data.get("metadata", {})
    tenant_id = metadata.get("tenant_id")
    plan_id = metadata.get("plan_id", "atelier")
    affiliate_code = metadata.get("affiliate_code")
    customer_id = data.get("customer")
    subscription_id = data.get("subscription")

    logger.info(
        "stripe.checkout_completed",
        tenant_id=tenant_id,
        plan=plan_id,
        customer=customer_id,
        subscription=subscription_id,
    )

    if not tenant_id:
        logger.warning("stripe.checkout_completed.no_tenant_id", customer=customer_id)
        return

    # 1. Mettre à jour le tenant avec les IDs Stripe et le plan
    result = await db.execute(select(Tenant).where(Tenant.id == UUID(tenant_id)))
    tenant = result.scalar_one_or_none()
    if not tenant:
        logger.error("stripe.checkout_completed.tenant_not_found", tenant_id=tenant_id)
        return

    tenant.stripe_customer_id = customer_id
    if subscription_id:
        tenant.stripe_subscription_id = subscription_id
    tenant.subscription_status = "active"
    plan_name = STRIPE_PLAN_MAP.get(plan_id, plan_id)
    if plan_name in ("atelier", "manufacture", "maison"):
        tenant.plan = plan_name

    await db.commit()
    logger.info("stripe.checkout_completed.tenant_updated", tenant_id=tenant_id, plan=plan_name)

    # 2. Enregistrer le referral affilié (idempotent via ON CONFLICT DO NOTHING)
    if affiliate_code:
        partner_result = await db.execute(
            select(Partner).where(Partner.affiliate_code == affiliate_code, Partner.is_active == True)
        )
        partner = partner_result.scalar_one_or_none()
        if partner:
            stmt = pg_insert(Referral).values(
                partner_id=partner.id,
                tenant_id=UUID(tenant_id),
                commission_rate=partner.commission_rate,
            ).on_conflict_do_nothing(constraint="uq_partner_tenant")
            await db.execute(stmt)
            await db.commit()
            logger.info(
                "stripe.referral_created",
                partner_id=str(partner.id),
                tenant_id=tenant_id,
                commission_rate=str(partner.commission_rate),
            )


async def handle_subscription_updated(data: dict, db: AsyncSession):
    """
    Subscription créée/mise à jour — synchronise le statut et le plan.
    """
    from app.models import Tenant

    subscription_id = data["id"]
    stripe_status = data["status"]
    internal_status = STRIPE_STATUS_MAP.get(stripe_status, "past_due")
    metadata = data.get("metadata", {})
    plan_id = metadata.get("plan_id")
    cancel_at_period_end = data.get("cancel_at_period_end", False)

    logger.info(
        "stripe.subscription_updated",
        subscription_id=subscription_id,
        stripe_status=stripe_status,
        internal_status=internal_status,
        plan=plan_id,
        cancelling=cancel_at_period_end,
    )

    result = await db.execute(
        select(Tenant).where(Tenant.stripe_subscription_id == subscription_id)
    )
    tenant = result.scalar_one_or_none()
    if not tenant:
        logger.warning("stripe.subscription_updated.tenant_not_found", sub=subscription_id)
        return

    tenant.subscription_status = internal_status

    # Mise à jour du plan si spécifié dans les métadonnées
    if plan_id:
        plan_name = STRIPE_PLAN_MAP.get(plan_id, plan_id)
        if plan_name in ("atelier", "manufacture", "maison"):
            tenant.plan = plan_name

    await db.commit()
    logger.info(
        "stripe.subscription_synced",
        tenant_id=str(tenant.id),
        status=internal_status,
    )


async def handle_subscription_deleted(data: dict, db: AsyncSession):
    """Subscription annulée — passe le tenant en statut canceled."""
    from app.models import Tenant

    subscription_id = data["id"]

    logger.info("stripe.subscription_deleted", subscription_id=subscription_id)

    result = await db.execute(
        select(Tenant).where(Tenant.stripe_subscription_id == subscription_id)
    )
    tenant = result.scalar_one_or_none()
    if not tenant:
        return

    tenant.subscription_status = "canceled"
    await db.commit()
    logger.info("stripe.subscription_cancelled", tenant_id=str(tenant.id))


async def handle_invoice_paid(data: dict, db: AsyncSession):
    """
    Invoice payée — confirme l'accès actif et crédite les commissions affilié.
    """
    from app.models import Partner, Referral, Tenant

    customer_id = data.get("customer")
    amount_paid = data.get("amount_paid", 0)  # en centimes
    subscription_id = data.get("subscription")

    logger.info(
        "stripe.invoice_paid",
        customer=customer_id,
        amount_cents=amount_paid,
        subscription=subscription_id,
    )

    if not customer_id:
        return

    # Retrouver le tenant via customer_id
    result = await db.execute(
        select(Tenant).where(Tenant.stripe_customer_id == customer_id)
    )
    tenant = result.scalar_one_or_none()
    if not tenant:
        logger.warning("stripe.invoice_paid.tenant_not_found", customer=customer_id)
        return

    # S'assurer que le statut est bien active
    if tenant.subscription_status not in ("active", "trialing"):
        tenant.subscription_status = "active"

    # Chercher un referral actif pour ce tenant
    ref_result = await db.execute(
        select(Referral).where(Referral.tenant_id == tenant.id)
    )
    referral = ref_result.scalar_one_or_none()

    if referral:
        # Calculer et créditer la commission
        commission_cents = int(
            Decimal(amount_paid) * referral.commission_rate / Decimal("100")
        )
        partner_result = await db.execute(
            select(Partner).where(Partner.id == referral.partner_id)
        )
        partner = partner_result.scalar_one_or_none()
        if partner and partner.is_active:
            partner.total_earnings_cents += commission_cents
            referral.total_paid_cents += commission_cents
            logger.info(
                "stripe.commission_credited",
                partner_id=str(partner.id),
                tenant_id=str(tenant.id),
                commission_cents=commission_cents,
                invoice_cents=amount_paid,
            )

    await db.commit()


async def handle_invoice_payment_failed(data: dict, db: AsyncSession):
    """
    Paiement échoué — passe le tenant en past_due et notifie par email.
    Après 3 tentatives, Stripe annule automatiquement.
    """
    from app.models import Tenant

    customer_id = data.get("customer")
    attempt_count = data.get("attempt_count", 1)

    logger.warning(
        "stripe.payment_failed",
        customer=customer_id,
        attempt=attempt_count,
    )

    if not customer_id:
        return

    result = await db.execute(
        select(Tenant).where(Tenant.stripe_customer_id == customer_id)
    )
    tenant = result.scalar_one_or_none()
    if not tenant:
        return

    tenant.subscription_status = "past_due"
    await db.commit()

    # Envoyer un email de notification (Celery task)
    try:
        from app.stripe.tasks import send_payment_failed_email
        send_payment_failed_email.delay(customer_id, str(tenant.id), attempt_count)
    except Exception as exc:
        logger.warning("stripe.payment_failed_email_error", error=str(exc))


async def handle_customer_created(data: dict, db: AsyncSession):
    """New Stripe customer created — log for tracking."""
    logger.info(
        "stripe.customer_created",
        customer_id=data["id"],
        email=data.get("email"),
    )
