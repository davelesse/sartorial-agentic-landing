"""
═══════════════════════════════════════════════════════════
SARTORIAL AGENTIC — Analytics Router
Métriques temps réel : MRR, usage agents, coûts, tendances.
═══════════════════════════════════════════════════════════
"""

from datetime import datetime, timedelta, timezone

import structlog
from fastapi import APIRouter, Depends
from sqlalchemy import cast, Date, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_tenant, require_role
from app.models import Agent, Partner, Referral, Task, Tenant, User

logger = structlog.get_logger()
router = APIRouter()


@router.get("/tenant")
async def tenant_analytics(
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Métriques du tenant courant — usage, coûts, tendances."""
    now = datetime.now(timezone.utc)
    month_ago = now - timedelta(days=30)
    week_ago = now - timedelta(days=7)

    # Tasks ce mois
    tasks_month = await db.execute(
        select(func.count())
        .select_from(Task)
        .where(Task.tenant_id == tenant.id, Task.created_at >= month_ago)
    )
    total_tasks_month = tasks_month.scalar_one()

    # Tasks cette semaine
    tasks_week = await db.execute(
        select(func.count())
        .select_from(Task)
        .where(Task.tenant_id == tenant.id, Task.created_at >= week_ago)
    )
    total_tasks_week = tasks_week.scalar_one()

    # Coût total ce mois
    cost_month = await db.execute(
        select(func.coalesce(func.sum(Task.cost_cents), 0))
        .where(Task.tenant_id == tenant.id, Task.created_at >= month_ago)
    )
    total_cost_month = cost_month.scalar_one()

    # Tokens totaux ce mois
    tokens_month = await db.execute(
        select(func.coalesce(func.sum(Task.tokens_used), 0))
        .where(Task.tenant_id == tenant.id, Task.created_at >= month_ago)
    )
    total_tokens_month = tokens_month.scalar_one()

    # Taux de succès
    success_count = await db.execute(
        select(func.count())
        .select_from(Task)
        .where(
            Task.tenant_id == tenant.id,
            Task.created_at >= month_ago,
            Task.status == "completed",
        )
    )
    successes = success_count.scalar_one()
    success_rate = round(successes / max(total_tasks_month, 1) * 100, 1)

    # Répartition par status — GROUP BY (1 requête au lieu de 4)
    status_rows = await db.execute(
        select(Task.status, func.count())
        .where(Task.tenant_id == tenant.id, Task.created_at >= month_ago)
        .group_by(Task.status)
    )
    status_breakdown = {s: 0 for s in ("pending", "running", "completed", "failed")}
    for row_status, row_count in status_rows.all():
        if row_status in status_breakdown:
            status_breakdown[row_status] = row_count

    # Activité quotidienne (7 derniers jours) — GROUP BY date (1 requête au lieu de 7)
    daily_rows = await db.execute(
        select(cast(Task.created_at, Date), func.count())
        .where(Task.tenant_id == tenant.id, Task.created_at >= week_ago)
        .group_by(cast(Task.created_at, Date))
    )
    daily_map = {str(row_date): row_count for row_date, row_count in daily_rows.all()}

    daily_activity = []
    for i in range(7):
        day = now - timedelta(days=6 - i)
        day_str = day.strftime("%Y-%m-%d")
        daily_activity.append({"date": day_str, "count": daily_map.get(day_str, 0)})

    return {
        "period": "30d",
        "executions_month": total_tasks_month,
        "executions_week": total_tasks_week,
        "executions_used": tenant.executions_used,
        "cost_month_cents": total_cost_month,
        "cost_month_eur": round(total_cost_month / 100, 2),
        "tokens_month": total_tokens_month,
        "success_rate": success_rate,
        "status_breakdown": status_breakdown,
        "daily_activity": daily_activity,
    }


@router.get("/admin")
async def admin_analytics(
    user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    """Métriques globales — réservé admin (toi David)."""
    now = datetime.now(timezone.utc)
    month_ago = now - timedelta(days=30)

    # Total tenants
    total_tenants = (await db.execute(select(func.count()).select_from(Tenant))).scalar_one()

    # Tenants actifs (trialing ou active)
    active_tenants = (await db.execute(
        select(func.count())
        .select_from(Tenant)
        .where(Tenant.subscription_status.in_(["active", "trialing"]))
    )).scalar_one()

    # Répartition par plan — GROUP BY (1 requête au lieu de 3)
    plan_rows = await db.execute(
        select(Tenant.plan, func.count()).group_by(Tenant.plan)
    )
    plan_breakdown = {p: 0 for p in ("atelier", "manufacture", "maison")}
    for row_plan, row_count in plan_rows.all():
        plan_breakdown[row_plan] = row_count

    # Total tasks ce mois
    total_tasks = (await db.execute(
        select(func.count()).select_from(Task).where(Task.created_at >= month_ago)
    )).scalar_one()

    # Coût API total
    total_cost = (await db.execute(
        select(func.coalesce(func.sum(Task.cost_cents), 0))
        .where(Task.created_at >= month_ago)
    )).scalar_one()

    # MRR estimé depuis les plans
    mrr_map = {"atelier": 7900, "manufacture": 19900, "maison": 49900}
    mrr_cents = sum(
        mrr_map.get(plan, 0) * count
        for plan, count in plan_breakdown.items()
    )

    # Partenaires
    total_partners = (await db.execute(
        select(func.count()).select_from(Partner).where(Partner.is_active == True)
    )).scalar_one()

    total_referrals = (await db.execute(
        select(func.count()).select_from(Referral)
    )).scalar_one()

    # Waitlist
    from app.models import Waitlist
    waitlist_count = (await db.execute(
        select(func.count()).select_from(Waitlist)
    )).scalar_one()

    return {
        "period": "30d",
        "tenants_total": total_tenants,
        "tenants_active": active_tenants,
        "plan_breakdown": plan_breakdown,
        "mrr_cents": mrr_cents,
        "mrr_eur": round(mrr_cents / 100, 2),
        "tasks_month": total_tasks,
        "api_cost_month_cents": total_cost,
        "api_cost_month_eur": round(total_cost / 100, 2),
        "partners_active": total_partners,
        "referrals_total": total_referrals,
        "waitlist_count": waitlist_count,
    }
