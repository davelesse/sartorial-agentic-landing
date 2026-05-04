"""
═══════════════════════════════════════════════════════════
SARTORIAL AGENTIC — Database Models
SQLAlchemy 2.0 async ORM — Multi-tenant architecture
═══════════════════════════════════════════════════════════
"""

import secrets
from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import (
    String, Text, Integer, Boolean, ForeignKey, DateTime,
    ARRAY, UniqueConstraint, Numeric, func,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


def _uuid() -> UUID:
    return uuid4()


def _now():
    return datetime.now(timezone.utc)


def _api_key() -> str:
    return secrets.token_urlsafe(48)


# ─────────────────────────────────────
# USER
# ─────────────────────────────────────

class User(Base):
    __tablename__ = "users"

    id:              Mapped[UUID]     = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=_uuid)
    email:           Mapped[str]      = mapped_column(String(255), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str]      = mapped_column(String(255), nullable=False)
    full_name:       Mapped[str | None] = mapped_column(String(255))
    is_active:       Mapped[bool]     = mapped_column(Boolean, default=True)
    is_verified:     Mapped[bool]     = mapped_column(Boolean, default=False)
    role:            Mapped[str]      = mapped_column(String(50), default="client")  # client | partner | admin
    is_deleted:      Mapped[bool]     = mapped_column(Boolean, default=False, index=True)
    deleted_at:      Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at:      Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at:      Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)

    # Relationships
    tenants:  Mapped[list["Tenant"]]  = relationship(back_populates="owner", cascade="all, delete-orphan")
    partner:  Mapped["Partner | None"] = relationship(back_populates="user", uselist=False, cascade="all, delete-orphan")


# ─────────────────────────────────────
# TENANT (organization / workspace)
# ─────────────────────────────────────

class Tenant(Base):
    __tablename__ = "tenants"

    id:                     Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=_uuid)
    name:                   Mapped[str]  = mapped_column(String(255), nullable=False)
    slug:                   Mapped[str]  = mapped_column(String(100), unique=True, nullable=False, index=True)
    owner_id:               Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    # Clé publique pour le chatbot widget (cryptographiquement sûre, non-devinable)
    public_api_key:         Mapped[str]  = mapped_column(String(64), unique=True, nullable=False, index=True, default=_api_key)

    # Plan & Subscription
    plan:                   Mapped[str]  = mapped_column(String(50), default="atelier")  # atelier | manufacture | maison
    sectors:                Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    stripe_customer_id:     Mapped[str | None] = mapped_column(String(255), index=True)
    stripe_subscription_id: Mapped[str | None] = mapped_column(String(255), index=True)
    subscription_status:    Mapped[str]  = mapped_column(String(50), default="trialing")  # trialing | active | past_due | canceled
    trial_ends_at:          Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Usage counters (reset monthly by Celery Beat)
    executions_used:        Mapped[int]  = mapped_column(Integer, default=0)
    executions_reset_at:    Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    settings:               Mapped[dict] = mapped_column(JSONB, default=dict)
    is_deleted:             Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    deleted_at:             Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at:             Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at:             Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)

    # Relationships
    owner:         Mapped[User]              = relationship(back_populates="tenants")
    tenant_agents: Mapped[list["TenantAgent"]] = relationship(back_populates="tenant", cascade="all, delete-orphan")
    tasks:         Mapped[list["Task"]]       = relationship(back_populates="tenant", cascade="all, delete-orphan")
    leads:         Mapped[list["Lead"]]       = relationship(back_populates="tenant", cascade="all, delete-orphan")
    appointments:  Mapped[list["Appointment"]] = relationship(back_populates="tenant", cascade="all, delete-orphan")


# ─────────────────────────────────────
# AGENT (catalog — global, not tenant-specific)
# ─────────────────────────────────────

class Agent(Base):
    __tablename__ = "agents"

    id:            Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=_uuid)
    name:          Mapped[str]  = mapped_column(String(255), nullable=False)
    slug:          Mapped[str]  = mapped_column(String(100), nullable=False, index=True)
    description:   Mapped[str | None] = mapped_column(Text)
    sector:        Mapped[str]  = mapped_column(String(50), nullable=False, index=True)
    category:      Mapped[str]  = mapped_column(String(50), nullable=False)
    config_schema: Mapped[dict] = mapped_column(JSONB, default=dict)
    min_plan:      Mapped[str]  = mapped_column(String(50), default="atelier")
    is_active:     Mapped[bool] = mapped_column(Boolean, default=True)
    version:       Mapped[str]  = mapped_column(String(20), default="1.0.0")
    created_at:    Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


# ─────────────────────────────────────
# TENANT_AGENT (junction — which agents are enabled per tenant)
# ─────────────────────────────────────

class TenantAgent(Base):
    __tablename__ = "tenant_agents"
    __table_args__ = (UniqueConstraint("tenant_id", "agent_id", name="uq_tenant_agent"),)

    id:         Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=_uuid)
    tenant_id:  Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    agent_id:   Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("agents.id", ondelete="CASCADE"), nullable=False, index=True)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    config:     Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    # Relationships
    tenant: Mapped[Tenant] = relationship(back_populates="tenant_agents")
    agent:  Mapped[Agent]  = relationship()


# ─────────────────────────────────────
# TASK (agent execution log)
# ─────────────────────────────────────

class Task(Base):
    __tablename__ = "tasks"

    id:            Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=_uuid)
    tenant_id:     Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    agent_id:      Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("agents.id"), nullable=False, index=True)

    status:        Mapped[str]  = mapped_column(String(50), default="pending", index=True)  # pending | running | completed | failed | cancelled
    input_data:    Mapped[dict] = mapped_column(JSONB, default=dict)
    output_data:   Mapped[dict] = mapped_column(JSONB, default=dict)
    error_message: Mapped[str | None] = mapped_column(Text)

    tokens_used:   Mapped[int]  = mapped_column(Integer, default=0)
    cost_cents:    Mapped[int]  = mapped_column(Integer, default=0)

    started_at:    Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at:  Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at:    Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, index=True)

    # Relationships
    tenant: Mapped[Tenant] = relationship(back_populates="tasks")
    agent:  Mapped[Agent]  = relationship()


# ─────────────────────────────────────
# LEAD (captures chatbot)
# ─────────────────────────────────────

class Lead(Base):
    __tablename__ = "leads"

    id:           Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=_uuid)
    tenant_id:    Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    visitor_id:   Mapped[str]  = mapped_column(String(255), nullable=False, index=True)
    email:        Mapped[str]  = mapped_column(String(255), nullable=False)
    name:         Mapped[str | None] = mapped_column(String(255))
    phone:        Mapped[str | None] = mapped_column(String(50))
    need_summary: Mapped[str | None] = mapped_column(Text)
    urgency:      Mapped[str]  = mapped_column(String(20), default="medium")  # low | medium | high | urgent
    created_at:   Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, index=True)

    # Relationships
    tenant: Mapped[Tenant] = relationship(back_populates="leads")


# ─────────────────────────────────────
# APPOINTMENT (réservations chatbot)
# ─────────────────────────────────────

class Appointment(Base):
    __tablename__ = "appointments"

    id:             Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=_uuid)
    tenant_id:      Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    visitor_id:     Mapped[str]  = mapped_column(String(255), nullable=False, index=True)
    email:          Mapped[str | None] = mapped_column(String(255))
    service_type:   Mapped[str | None] = mapped_column(String(255))
    proposed_slots: Mapped[list]  = mapped_column(JSONB, default=list)  # [{"date": "...", "time": "..."}]
    confirmed_slot: Mapped[dict | None] = mapped_column(JSONB)
    status:         Mapped[str]   = mapped_column(String(20), default="proposed")  # proposed | confirmed | cancelled
    notes:          Mapped[str | None] = mapped_column(Text)
    created_at:     Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, index=True)

    # Relationships
    tenant: Mapped[Tenant] = relationship(back_populates="appointments")


# ─────────────────────────────────────
# PARTNER (reseller)
# ─────────────────────────────────────

class Partner(Base):
    __tablename__ = "partners"

    id:                   Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=_uuid)
    user_id:              Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)
    plan:                 Mapped[str]  = mapped_column(String(50), default="associe")  # associe | maison_partenaire
    commission_rate:      Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal("20.00"))
    affiliate_code:       Mapped[str]  = mapped_column(String(50), unique=True, nullable=False, index=True)
    stripe_connect_id:    Mapped[str | None] = mapped_column(String(255))
    total_earnings_cents: Mapped[int]  = mapped_column(Integer, default=0)
    is_active:            Mapped[bool] = mapped_column(Boolean, default=True)
    created_at:           Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    # Relationships
    user:      Mapped[User]              = relationship(back_populates="partner")
    referrals: Mapped[list["Referral"]]  = relationship(back_populates="partner", cascade="all, delete-orphan")


# ─────────────────────────────────────
# REFERRAL (commission tracking)
# ─────────────────────────────────────

class Referral(Base):
    __tablename__ = "referrals"
    __table_args__ = (UniqueConstraint("partner_id", "tenant_id", name="uq_partner_tenant"),)

    id:               Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=_uuid)
    partner_id:       Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("partners.id"), nullable=False, index=True)
    tenant_id:        Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True)
    commission_rate:  Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    total_paid_cents: Mapped[int]  = mapped_column(Integer, default=0)
    created_at:       Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    # Relationships
    partner: Mapped[Partner] = relationship(back_populates="referrals")
    tenant:  Mapped[Tenant]  = relationship()


# ─────────────────────────────────────
# WAITLIST (pre-launch emails)
# ─────────────────────────────────────

class Waitlist(Base):
    __tablename__ = "waitlist"

    id:         Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=_uuid)
    email:      Mapped[str]  = mapped_column(String(255), unique=True, nullable=False, index=True)
    source:     Mapped[str]  = mapped_column(String(100), default="landing")
    metadata_:  Mapped[dict] = mapped_column("metadata", JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
