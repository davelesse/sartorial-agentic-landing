"""
═══════════════════════════════════════════════════════════
SARTORIAL AGENTIC — Stripe Integration
Products, Prices, Checkout Sessions, Webhooks, Customer Portal
═══════════════════════════════════════════════════════════
"""

import stripe
import structlog
from app.core.config import settings

logger = structlog.get_logger()

stripe.api_key = settings.STRIPE_SECRET_KEY

# ─────────────────────────────────────
# PRODUCT & PRICE CATALOG
# ─────────────────────────────────────

PLANS = {
    "atelier": {
        "name": "Atelier",
        "description": "L'essentiel pour démarrer avec l'IA agentique — 3 agents transversaux, 1 secteur, 500 exécutions/mois.",
        "price_eur": 7900,       # centimes
        "metadata": {
            "plan_id": "atelier",
            "agents_limit": "3",
            "sectors_limit": "1",
            "executions_limit": "500",
            "support_level": "email_48h",
            "chatbot": "false",
        },
    },
    "manufacture": {
        "name": "Manufacture",
        "description": "La puissance complète — 6 agents, 2 secteurs, 2500 exécutions/mois, chatbot white-label.",
        "price_eur": 19900,
        "metadata": {
            "plan_id": "manufacture",
            "agents_limit": "6",
            "sectors_limit": "2",
            "executions_limit": "2500",
            "support_level": "email_24h",
            "chatbot": "true",
        },
    },
    "maison": {
        "name": "Maison",
        "description": "L'excellence sur mesure — tous les agents, secteurs illimités, exécutions illimitées, support dédié.",
        "price_eur": 49900,
        "metadata": {
            "plan_id": "maison",
            "agents_limit": "unlimited",
            "sectors_limit": "unlimited",
            "executions_limit": "unlimited",
            "support_level": "dedicated_slack",
            "chatbot": "true",
        },
    },
}

PARTNER_PLANS = {
    "associe": {
        "name": "Associé (Partenaire)",
        "description": "Programme partenaire gratuit — 20% de commission récurrente.",
        "price_eur": 0,
        "metadata": {
            "partner_plan_id": "associe",
            "commission_rate": "20",
        },
    },
    "maison_partenaire": {
        "name": "Maison Partenaire",
        "description": "Programme partenaire premium — 30% de commission, marque blanche, formation.",
        "price_eur": 49700,
        "metadata": {
            "partner_plan_id": "maison_partenaire",
            "commission_rate": "30",
        },
    },
}


async def ensure_products_and_prices() -> dict:
    """
    Create or update all Stripe Products and Prices.
    Idempotent — safe to run multiple times.
    Returns a mapping of plan_id → {product_id, price_id}.
    """
    catalog = {}

    for plan_id, plan in PLANS.items():
        product = await _ensure_product(plan_id, plan)
        price = await _ensure_price(product.id, plan_id, plan)
        catalog[plan_id] = {
            "product_id": product.id,
            "price_id": price.id,
        }
        logger.info(
            "stripe.plan_synced",
            plan=plan_id,
            product_id=product.id,
            price_id=price.id,
        )

    for plan_id, plan in PARTNER_PLANS.items():
        if plan["price_eur"] > 0:
            product = await _ensure_product(f"partner_{plan_id}", plan)
            price = await _ensure_price(product.id, f"partner_{plan_id}", plan)
            catalog[f"partner_{plan_id}"] = {
                "product_id": product.id,
                "price_id": price.id,
            }

    return catalog


async def _ensure_product(plan_id: str, plan: dict) -> stripe.Product:
    """Find existing product by metadata or create new one."""
    existing = stripe.Product.search(
        query=f"metadata['plan_id']:'{plan_id}'"
    )
    if existing.data:
        product = existing.data[0]
        # Update if needed
        stripe.Product.modify(
            product.id,
            name=f"Sartorial Agentic — {plan['name']}",
            description=plan["description"],
            metadata={**plan.get("metadata", {}), "plan_id": plan_id},
        )
        return product

    return stripe.Product.create(
        name=f"Sartorial Agentic — {plan['name']}",
        description=plan["description"],
        metadata={**plan.get("metadata", {}), "plan_id": plan_id},
    )


async def _ensure_price(product_id: str, plan_id: str, plan: dict) -> stripe.Price:
    """Find existing active price or create new one."""
    prices = stripe.Price.list(product=product_id, active=True)
    for price in prices.data:
        if price.unit_amount == plan["price_eur"] and price.currency == "eur":
            return price

    return stripe.Price.create(
        product=product_id,
        unit_amount=plan["price_eur"],
        currency="eur",
        recurring={"interval": "month"},
        metadata={"plan_id": plan_id},
    )


# ─────────────────────────────────────
# CHECKOUT SESSIONS
# ─────────────────────────────────────

async def create_checkout_session(
    plan_id: str,
    customer_email: str,
    tenant_id: str,
    locale: str = "fr",
    affiliate_code: str | None = None,
) -> str:
    """
    Create a dynamic Stripe Checkout Session.
    Returns the checkout URL.
    """
    catalog = await ensure_products_and_prices()

    if plan_id not in catalog:
        raise ValueError(f"Plan inconnu: {plan_id}")

    metadata = {
        "plan_id": plan_id,
        "tenant_id": tenant_id,
        "locale": locale,
    }
    if affiliate_code:
        metadata["affiliate_code"] = affiliate_code

    session = stripe.checkout.Session.create(
        mode="subscription",
        payment_method_types=["card"],
        line_items=[{
            "price": catalog[plan_id]["price_id"],
            "quantity": 1,
        }],
        customer_email=customer_email,
        metadata=metadata,
        subscription_data={
            "trial_period_days": 14,
            "metadata": metadata,
        },
        success_url=f"https://sartorial-agentic.ai/dashboard?session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=f"https://sartorial-agentic.ai/tarifs?cancelled=true",
        locale=locale,
        allow_promotion_codes=True,
    )

    logger.info(
        "stripe.checkout_created",
        plan=plan_id,
        tenant=tenant_id,
        session_id=session.id,
    )

    return session.url


async def create_customer_portal_session(
    stripe_customer_id: str,
) -> str:
    """Create a Stripe Customer Portal session for plan management."""
    session = stripe.billing_portal.Session.create(
        customer=stripe_customer_id,
        return_url="https://sartorial-agentic.ai/dashboard/settings",
    )
    return session.url


# ─────────────────────────────────────
# SUBSCRIPTION MANAGEMENT
# ─────────────────────────────────────

async def get_subscription(subscription_id: str) -> stripe.Subscription:
    """Retrieve a subscription with its details."""
    return stripe.Subscription.retrieve(
        subscription_id,
        expand=["latest_invoice", "default_payment_method"],
    )


async def cancel_subscription(subscription_id: str, at_period_end: bool = True):
    """Cancel a subscription (default: at end of billing period)."""
    stripe.Subscription.modify(
        subscription_id,
        cancel_at_period_end=at_period_end,
    )
    logger.info("stripe.subscription_cancelled", subscription_id=subscription_id)


async def update_subscription_plan(
    subscription_id: str,
    new_plan_id: str,
) -> stripe.Subscription:
    """Upgrade or downgrade a subscription."""
    catalog = await ensure_products_and_prices()
    if new_plan_id not in catalog:
        raise ValueError(f"Plan inconnu: {new_plan_id}")

    subscription = stripe.Subscription.retrieve(subscription_id)

    updated = stripe.Subscription.modify(
        subscription_id,
        items=[{
            "id": subscription["items"]["data"][0].id,
            "price": catalog[new_plan_id]["price_id"],
        }],
        metadata={"plan_id": new_plan_id},
        proration_behavior="create_prorations",
    )

    logger.info(
        "stripe.subscription_updated",
        subscription_id=subscription_id,
        new_plan=new_plan_id,
    )

    return updated
