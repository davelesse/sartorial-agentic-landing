"""
═══════════════════════════════════════════════════════════
SARTORIAL AGENTIC — Stripe Celery Tasks
Autonomous Stripe management agent tasks.
═══════════════════════════════════════════════════════════
"""

import structlog
from celery import shared_task

logger = structlog.get_logger()


@shared_task(name="app.stripe.tasks.send_payment_failed_email", bind=True, max_retries=3)
def send_payment_failed_email(self, customer_id: str, tenant_id: str, attempt_count: int):
    """Envoie un email de paiement échoué au client via Resend."""
    import asyncio

    async def _send():
        from sqlalchemy import select
        from app.core.database import async_session
        from app.core.config import settings
        from app.models import Tenant

        async with async_session() as db:
            from uuid import UUID
            result = await db.execute(select(Tenant).where(Tenant.id == UUID(tenant_id)))
            tenant = result.scalar_one_or_none()
            if not tenant:
                return

            owner_result = await db.execute(
                select(__import__("app.models", fromlist=["User"]).User)
                .where(__import__("app.models", fromlist=["User"]).User.id == tenant.owner_id)
            )
            owner = owner_result.scalar_one_or_none()
            if not owner:
                return

            try:
                import resend
                resend.api_key = settings.RESEND_API_KEY
                resend.Emails.send({
                    "from": "Sartorial Agentic <no-reply@sartorial-agentic.ai>",
                    "to": [owner.email],
                    "subject": "Action requise — Problème de paiement",
                    "html": f"""
                    <p>Bonjour {owner.full_name or ''},</p>
                    <p>Nous n'avons pas pu traiter votre paiement pour Sartorial Agentic
                    (tentative {attempt_count}/3).</p>
                    <p>Veuillez mettre à jour votre moyen de paiement pour éviter
                    toute interruption de service.</p>
                    <p>— Votre Tailleur</p>
                    """,
                })
                logger.info("email.payment_failed_sent", tenant_id=tenant_id, attempt=attempt_count)
            except Exception as exc:
                logger.error("email.payment_failed_error", error=str(exc))
                raise self.retry(exc=exc, countdown=60)

    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(_send())
    finally:
        loop.close()


@shared_task(name="app.stripe.tasks.commission_only_email_sequence", bind=True, max_retries=3)
def commission_only_email_sequence(self, tenant_id: str, email: str, full_name: str):
    """Planifie la séquence d'emails Commission Only (J+1, J+7, J+14, J+21, J+27, J+30)."""
    import asyncio
    from datetime import datetime, timedelta, timezone

    EMAIL_SEQUENCE = [
        {"day": 1,  "subject": "Bienvenue — votre essai de 30 jours commence"},
        {"day": 7,  "subject": "Vos premiers résultats sont là"},
        {"day": 14, "subject": "Mi-parcours — vos agents performent"},
        {"day": 21, "subject": "Plus que 9 jours d'essai gratuit"},
        {"day": 27, "subject": "3 jours restants — ne perdez pas vos agents"},
        {"day": 30, "subject": "Votre essai est terminé — choisissez votre plan"},
    ]

    async def _schedule():
        from app.core.config import settings
        import resend
        resend.api_key = settings.RESEND_API_KEY

        now = datetime.now(timezone.utc)
        for step in EMAIL_SEQUENCE:
            send_at = now + timedelta(days=step["day"])
            try:
                resend.Emails.send({
                    "from": "Sartorial Agentic <no-reply@sartorial-agentic.ai>",
                    "to": [email],
                    "subject": step["subject"],
                    "scheduled_at": send_at.strftime("%Y-%m-%dT%H:%M:%S+00:00"),
                    "html": f"<p>Bonjour {full_name},</p><p>{step['subject']}</p><p>— Votre Tailleur</p>",
                })
                logger.info(
                    "commission_only.email_scheduled",
                    tenant_id=tenant_id,
                    day=step["day"],
                    send_at=send_at.isoformat(),
                )
            except Exception as exc:
                logger.warning("commission_only.email_schedule_failed", day=step["day"], error=str(exc))

    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(_schedule())
    except Exception as exc:
        logger.error("commission_only.email_sequence_failed", error=str(exc))
        raise self.retry(exc=exc, countdown=300)
    finally:
        loop.close()


@shared_task(name="app.stripe.tasks.sync_products")
def sync_products():
    """
    Sync all products and prices with Stripe.
    Runs every 6 hours via Celery Beat.
    Ensures our catalog is always in sync.
    """
    import asyncio
    from app.stripe import ensure_products_and_prices

    async def _sync():
        catalog = await ensure_products_and_prices()
        logger.info("stripe.sync_completed", products=len(catalog))
        return catalog

    loop = asyncio.new_event_loop()
    try:
        result = loop.run_until_complete(_sync())
        return {"status": "synced", "products": len(result)}
    finally:
        loop.close()


@shared_task(name="app.stripe.tasks.archive_stale_products")
def archive_stale_products():
    """
    Archive products that are no longer in our catalog.
    Safety measure to keep Stripe dashboard clean.
    """
    import stripe
    from app.core.config import settings
    from app.stripe import PLANS, PARTNER_PLANS

    stripe.api_key = settings.STRIPE_SECRET_KEY

    valid_plan_ids = set(PLANS.keys()) | {f"partner_{k}" for k in PARTNER_PLANS.keys()}

    products = stripe.Product.list(active=True, limit=100)
    archived = 0

    for product in products.auto_paging_iter():
        plan_id = product.metadata.get("plan_id", "")
        if plan_id and plan_id not in valid_plan_ids:
            stripe.Product.modify(product.id, active=False)
            logger.info("stripe.product_archived", product_id=product.id, plan_id=plan_id)
            archived += 1

    return {"status": "completed", "archived": archived}


@shared_task(name="app.stripe.tasks.generate_revenue_report")
def generate_revenue_report():
    """
    Generate MRR and churn report from Stripe data.
    Used by the Analytics Reporter agent.
    """
    import stripe
    from app.core.config import settings
    from datetime import datetime, timedelta

    stripe.api_key = settings.STRIPE_SECRET_KEY

    # Active subscriptions
    subscriptions = stripe.Subscription.list(status="active", limit=100)
    mrr = sum(
        sub["items"]["data"][0]["price"]["unit_amount"]
        for sub in subscriptions.auto_paging_iter()
    )

    # Churned in last 30 days
    thirty_days_ago = int((datetime.now() - timedelta(days=30)).timestamp())
    cancelled = stripe.Subscription.list(
        status="canceled",
        created={"gte": thirty_days_ago},
        limit=100,
    )
    churn_count = len(list(cancelled.auto_paging_iter()))

    total_active = len(list(
        stripe.Subscription.list(status="active", limit=100).auto_paging_iter()
    ))

    report = {
        "mrr_cents": mrr,
        "mrr_eur": mrr / 100,
        "active_subscriptions": total_active,
        "churned_30d": churn_count,
        "churn_rate": round(churn_count / max(total_active, 1) * 100, 2),
        "generated_at": datetime.now().isoformat(),
    }

    logger.info("stripe.revenue_report", **report)
    return report
