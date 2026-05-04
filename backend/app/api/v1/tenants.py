"""
═══════════════════════════════════════════════════════════
SARTORIAL AGENTIC — Tenants Router
Workspace management.
═══════════════════════════════════════════════════════════
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_tenant
from app.models import Tenant
from app.schemas import TenantResponse, TenantUpdateRequest

router = APIRouter()


@router.get("/me", response_model=TenantResponse)
async def get_my_tenant(tenant: Tenant = Depends(get_current_tenant)):
    """Get current user's tenant."""
    return tenant


@router.patch("/me", response_model=TenantResponse)
async def update_my_tenant(
    request: TenantUpdateRequest,
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Update tenant settings (name, sectors, settings dict)."""
    if request.name is not None:
        tenant.name = request.name
    if request.sectors is not None:
        tenant.sectors = request.sectors
    if request.settings is not None:
        # Merge dict au lieu de remplacer
        tenant.settings = {**tenant.settings, **request.settings}

    await db.commit()
    await db.refresh(tenant)
    return tenant
