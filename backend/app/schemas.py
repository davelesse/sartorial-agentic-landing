"""
═══════════════════════════════════════════════════════════
SARTORIAL AGENTIC — Pydantic Schemas
Request/Response validation for the API layer.
═══════════════════════════════════════════════════════════
"""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


# ─────────────────────────────────────
# AUTH
# ─────────────────────────────────────

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str | None = Field(default=None, max_length=255)
    tenant_name: str = Field(min_length=2, max_length=255)
    affiliate_code: str | None = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: EmailStr
    full_name: str | None
    role: str
    is_active: bool
    is_verified: bool
    created_at: datetime


# ─────────────────────────────────────
# TENANT
# ─────────────────────────────────────

class TenantResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    slug: str
    plan: str
    sectors: list[str]
    subscription_status: str
    trial_ends_at: datetime | None
    executions_used: int
    created_at: datetime


class TenantUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=255)
    sectors: list[str] | None = None
    settings: dict | None = None


# ─────────────────────────────────────
# AGENT
# ─────────────────────────────────────

class AgentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    slug: str
    description: str | None
    sector: str
    category: str
    min_plan: str
    is_active: bool
    version: str


class TenantAgentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    agent: AgentResponse
    is_enabled: bool
    config: dict
    created_at: datetime


class TenantAgentActivateRequest(BaseModel):
    agent_id: UUID
    config: dict = Field(default_factory=dict)


class TenantAgentUpdateRequest(BaseModel):
    is_enabled: bool | None = None
    config: dict | None = None


# ─────────────────────────────────────
# TASK
# ─────────────────────────────────────

class TaskCreateRequest(BaseModel):
    agent_slug: str
    input_data: dict = Field(default_factory=dict)


class TaskResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    agent_id: UUID
    status: str
    input_data: dict
    output_data: dict
    error_message: str | None
    tokens_used: int
    cost_cents: int
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime


class TaskListResponse(BaseModel):
    items: list[TaskResponse]
    total: int
    page: int
    page_size: int


# ─────────────────────────────────────
# PARTNER
# ─────────────────────────────────────

class PartnerResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    plan: str
    commission_rate: Decimal
    affiliate_code: str
    total_earnings_cents: int
    is_active: bool
    created_at: datetime


# ─────────────────────────────────────
# WAITLIST
# ─────────────────────────────────────

class WaitlistRequest(BaseModel):
    email: EmailStr
    source: str = "landing"


class WaitlistResponse(BaseModel):
    success: bool
    message: str
