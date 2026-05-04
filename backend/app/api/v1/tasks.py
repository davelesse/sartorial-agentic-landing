"""
═══════════════════════════════════════════════════════════
SARTORIAL AGENTIC — Tasks Router
Trigger agent executions, view task history.
═══════════════════════════════════════════════════════════
"""

from datetime import datetime, timezone
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger()

VALID_STATUSES = frozenset({"pending", "running", "completed", "failed", "cancelled"})

from app.core.database import get_db
from app.core.deps import get_current_tenant, require_active_subscription
from app.models import Agent, Task, Tenant, TenantAgent
from app.schemas import TaskCreateRequest, TaskListResponse, TaskResponse

router = APIRouter()

# Execution limits per plan
PLAN_LIMITS = {
    "atelier": 500,
    "manufacture": 2500,
    "maison": -1,  # unlimited
}


@router.post("/", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
async def create_task(
    request: TaskCreateRequest,
    tenant: Tenant = Depends(require_active_subscription()),
    db: AsyncSession = Depends(get_db),
):
    """
    Trigger a new agent execution.
    Checks plan limits before queueing.
    """
    # Vérifier l'expiration du trial
    if (
        tenant.subscription_status == "trialing"
        and tenant.trial_ends_at
        and tenant.trial_ends_at < datetime.now(timezone.utc)
    ):
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="Votre période d'essai est expirée. Veuillez choisir un plan pour continuer.",
        )

    # Vérifier la limite mensuelle
    limit = PLAN_LIMITS.get(tenant.plan, 0)
    if limit > 0 and tenant.executions_used >= limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Limite mensuelle atteinte ({limit} exécutions). Upgrade vers un plan supérieur pour continuer.",
        )

    # Trouver l'agent
    agent_result = await db.execute(select(Agent).where(Agent.slug == request.agent_slug))
    agent = agent_result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent '{request.agent_slug}' introuvable")

    # Vérifier que l'agent est activé pour ce tenant
    ta_result = await db.execute(
        select(TenantAgent).where(
            TenantAgent.tenant_id == tenant.id,
            TenantAgent.agent_id == agent.id,
            TenantAgent.is_enabled == True,  # noqa: E712
        )
    )
    if not ta_result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Agent '{agent.slug}' non activé pour votre atelier",
        )

    # Créer la task en pending
    task = Task(
        tenant_id=tenant.id,
        agent_id=agent.id,
        status="pending",
        input_data=request.input_data,
    )
    db.add(task)

    # Incrémenter le compteur
    tenant.executions_used += 1

    await db.commit()
    await db.refresh(task)

    # Queuer l'exécution Celery
    try:
        from app.agents.tasks import execute_agent_task
        execute_agent_task.delay(str(task.id))
    except Exception as exc:
        logger.exception("task.queue_failed", task_id=str(task.id), error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service d'exécution temporairement indisponible. Réessayez dans quelques instants.",
        )

    return task


@router.get("/", response_model=TaskListResponse)
async def list_tasks(
    status_filter: str | None = Query(default=None, alias="status"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """List tasks for the current tenant (paginated)."""
    query = select(Task).where(Task.tenant_id == tenant.id)
    count_query = select(func.count()).select_from(Task).where(Task.tenant_id == tenant.id)

    if status_filter:
        if status_filter not in VALID_STATUSES:
            raise HTTPException(status_code=400, detail=f"Statut invalide. Options : {', '.join(sorted(VALID_STATUSES))}")
        query = query.where(Task.status == status_filter)
        count_query = count_query.where(Task.status == status_filter)

    query = query.order_by(Task.created_at.desc()).offset((page - 1) * page_size).limit(page_size)

    total = (await db.execute(count_query)).scalar_one()
    items = (await db.execute(query)).scalars().all()

    return TaskListResponse(items=items, total=total, page=page, page_size=page_size)


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(
    task_id: UUID,
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Get a single task with full details."""
    result = await db.execute(
        select(Task).where(Task.id == task_id, Task.tenant_id == tenant.id)
    )
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task introuvable")
    return task
