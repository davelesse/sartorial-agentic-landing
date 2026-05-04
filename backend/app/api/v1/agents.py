"""
═══════════════════════════════════════════════════════════
SARTORIAL AGENTIC — Agents Router
Catalog listing, tenant-level activation.
═══════════════════════════════════════════════════════════
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.deps import get_current_tenant
from app.models import Agent, Tenant, TenantAgent
from app.schemas import (
    AgentResponse, TenantAgentActivateRequest, TenantAgentResponse,
    TenantAgentUpdateRequest,
)

router = APIRouter()

# Plan hierarchy for min_plan check
PLAN_LEVEL = {"atelier": 1, "manufacture": 2, "maison": 3}


@router.get("/catalog", response_model=list[AgentResponse])
async def list_catalog(
    sector: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """List all available agents in the catalog (filterable by sector)."""
    query = select(Agent).where(Agent.is_active == True)  # noqa: E712
    if sector:
        query = query.where(Agent.sector == sector)
    query = query.order_by(Agent.sector, Agent.name)

    result = await db.execute(query)
    return result.scalars().all()


@router.get("/mine", response_model=list[TenantAgentResponse])
async def list_my_agents(
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """List agents activated for the current tenant."""
    result = await db.execute(
        select(TenantAgent)
        .where(TenantAgent.tenant_id == tenant.id)
        .options(selectinload(TenantAgent.agent))
        .order_by(TenantAgent.created_at.desc())
    )
    return result.scalars().all()


@router.post("/activate", response_model=TenantAgentResponse, status_code=status.HTTP_201_CREATED)
async def activate_agent(
    request: TenantAgentActivateRequest,
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Activate an agent for the current tenant."""
    # Vérifier l'agent existe
    agent_result = await db.execute(select(Agent).where(Agent.id == request.agent_id))
    agent = agent_result.scalar_one_or_none()
    if not agent or not agent.is_active:
        raise HTTPException(status_code=404, detail="Agent introuvable")

    # Vérifier plan suffisant
    if PLAN_LEVEL.get(tenant.plan, 0) < PLAN_LEVEL.get(agent.min_plan, 1):
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=f"Cet agent requiert le plan '{agent.min_plan}' ou supérieur",
        )

    # Vérifier pas déjà activé
    existing = await db.execute(
        select(TenantAgent)
        .where(TenantAgent.tenant_id == tenant.id, TenantAgent.agent_id == request.agent_id)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Agent déjà activé")

    # Création
    tenant_agent = TenantAgent(
        tenant_id=tenant.id,
        agent_id=request.agent_id,
        is_enabled=True,
        config=request.config,
    )
    db.add(tenant_agent)
    await db.commit()

    # Recharger avec relation
    result = await db.execute(
        select(TenantAgent)
        .where(TenantAgent.id == tenant_agent.id)
        .options(selectinload(TenantAgent.agent))
    )
    return result.scalar_one()


@router.patch("/{tenant_agent_id}", response_model=TenantAgentResponse)
async def update_tenant_agent(
    tenant_agent_id: UUID,
    request: TenantAgentUpdateRequest,
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Update config or toggle agent for a tenant."""
    result = await db.execute(
        select(TenantAgent)
        .where(TenantAgent.id == tenant_agent_id, TenantAgent.tenant_id == tenant.id)
        .options(selectinload(TenantAgent.agent))
    )
    tenant_agent = result.scalar_one_or_none()
    if not tenant_agent:
        raise HTTPException(status_code=404, detail="Agent non activé pour ce tenant")

    if request.is_enabled is not None:
        tenant_agent.is_enabled = request.is_enabled
    if request.config is not None:
        tenant_agent.config = {**tenant_agent.config, **request.config}

    await db.commit()
    await db.refresh(tenant_agent)
    return tenant_agent


@router.delete("/{tenant_agent_id}", status_code=status.HTTP_204_NO_CONTENT)
async def deactivate_agent(
    tenant_agent_id: UUID,
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Deactivate (remove) an agent from the tenant's workspace."""
    result = await db.execute(
        select(TenantAgent)
        .where(TenantAgent.id == tenant_agent_id, TenantAgent.tenant_id == tenant.id)
    )
    tenant_agent = result.scalar_one_or_none()
    if not tenant_agent:
        raise HTTPException(status_code=404, detail="Agent non trouvé")

    await db.delete(tenant_agent)
    await db.commit()
