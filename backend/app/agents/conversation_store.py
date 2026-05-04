"""
═══════════════════════════════════════════════════════════
SARTORIAL AGENTIC — Conversation Persistence
Redis pour la session active (chaud, TTL 30j)
PostgreSQL pour l'historique long terme
═══════════════════════════════════════════════════════════
"""

import json
from uuid import UUID

import redis.asyncio as redis
import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.conversational import VisitorProfile
from app.core.config import settings

logger = structlog.get_logger()

# TTL = 30 jours
PROFILE_TTL = 60 * 60 * 24 * 30
HISTORY_TTL = 60 * 60 * 24 * 30

# Max messages gardés en Redis — au-delà, on résume
MAX_HISTORY_IN_REDIS = 40


_redis_client: redis.Redis | None = None


def _get_redis() -> redis.Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
        )
    return _redis_client


def _profile_key(visitor_id: str, tenant_id: str) -> str:
    return f"conv:profile:{tenant_id}:{visitor_id}"


def _history_key(visitor_id: str, tenant_id: str) -> str:
    return f"conv:history:{tenant_id}:{visitor_id}"


def _summary_key(visitor_id: str, tenant_id: str) -> str:
    return f"conv:summary:{tenant_id}:{visitor_id}"


# ─────────────────────────────────────
# VISITOR PROFILE
# ─────────────────────────────────────

async def get_visitor_profile(visitor_id: str, tenant_id: str) -> VisitorProfile:
    """Récupère le profil depuis Redis, ou en crée un nouveau."""
    r = _get_redis()
    data = await r.get(_profile_key(visitor_id, tenant_id))

    if data:
        try:
            return VisitorProfile.from_dict(json.loads(data))
        except (json.JSONDecodeError, KeyError) as e:
            logger.warning("profile.corrupt", visitor=visitor_id, error=str(e))

    return VisitorProfile(visitor_id=visitor_id, tenant_id=tenant_id)


async def save_visitor_profile(profile: VisitorProfile) -> None:
    """Sauvegarde le profil dans Redis avec TTL."""
    r = _get_redis()
    await r.setex(
        _profile_key(profile.visitor_id, profile.tenant_id),
        PROFILE_TTL,
        json.dumps(profile.to_dict()),
    )


async def update_profile_from_tool(
    profile: VisitorProfile,
    tool_input: dict,
) -> VisitorProfile:
    """Met à jour le profil à partir d'un tool_use update_visitor_profile."""
    if "detected_profession" in tool_input and tool_input["detected_profession"]:
        profile.detected_profession = tool_input["detected_profession"]

    if "expertise_level" in tool_input and tool_input["expertise_level"]:
        profile.expertise_level = tool_input["expertise_level"]

    if "preferred_tone" in tool_input and tool_input["preferred_tone"]:
        profile.preferred_tone = tool_input["preferred_tone"]

    if "intentions" in tool_input:
        # Merge sans duplicate
        profile.intentions = list(set(profile.intentions + tool_input["intentions"]))

    if "pain_points" in tool_input:
        profile.pain_points = list(set(profile.pain_points + tool_input["pain_points"]))[-10:]

    if "custom_facts" in tool_input and isinstance(tool_input["custom_facts"], dict):
        profile.custom_facts.update(tool_input["custom_facts"])

    await save_visitor_profile(profile)
    return profile


# ─────────────────────────────────────
# MESSAGE HISTORY
# ─────────────────────────────────────

async def get_history(visitor_id: str, tenant_id: str) -> list[dict]:
    """Récupère l'historique des messages (les plus récents)."""
    r = _get_redis()
    raw = await r.lrange(_history_key(visitor_id, tenant_id), 0, -1)
    return [json.loads(msg) for msg in raw]


async def append_message(
    visitor_id: str,
    tenant_id: str,
    role: str,
    content: str,
) -> None:
    """Ajoute un message à l'historique. Trim si trop long."""
    r = _get_redis()
    key = _history_key(visitor_id, tenant_id)

    msg = json.dumps({"role": role, "content": content})
    await r.rpush(key, msg)
    await r.expire(key, HISTORY_TTL)

    # Trim : si trop long, on garde les derniers MAX_HISTORY messages
    length = await r.llen(key)
    if length > MAX_HISTORY_IN_REDIS:
        await r.ltrim(key, -MAX_HISTORY_IN_REDIS, -1)


async def get_summary(visitor_id: str, tenant_id: str) -> str | None:
    """Récupère le résumé des conversations passées (peut être None)."""
    r = _get_redis()
    return await r.get(_summary_key(visitor_id, tenant_id))


async def save_summary(visitor_id: str, tenant_id: str, summary: str) -> None:
    """Sauvegarde un résumé de conversation."""
    r = _get_redis()
    await r.setex(
        _summary_key(visitor_id, tenant_id),
        HISTORY_TTL,
        summary,
    )


# ─────────────────────────────────────
# PERSISTENCE POSTGRESQL (cold storage)
# ─────────────────────────────────────

async def persist_lead_capture(
    db: AsyncSession,
    tenant_id: str,
    visitor_id: str,
    lead_data: dict,
) -> None:
    """Persiste un lead capturé par l'agent dans PostgreSQL."""
    from app.models import Lead
    from uuid import UUID

    lead = Lead(
        tenant_id=UUID(tenant_id),
        visitor_id=visitor_id,
        email=lead_data.get("email", ""),
        name=lead_data.get("name"),
        phone=lead_data.get("phone"),
        need_summary=lead_data.get("need_summary"),
        urgency=lead_data.get("urgency", "medium"),
    )
    db.add(lead)
    try:
        await db.commit()
        logger.info(
            "conv.lead_persisted",
            tenant=tenant_id,
            visitor=visitor_id,
            email=lead.email,
            urgency=lead.urgency,
        )
    except Exception as exc:
        await db.rollback()
        logger.error("conv.lead_persist_failed", error=str(exc))


async def persist_appointment(
    db: AsyncSession,
    tenant_id: str,
    visitor_id: str,
    appointment_data: dict,
) -> None:
    """Persiste un RDV pris via l'agent dans PostgreSQL."""
    from app.models import Appointment
    from uuid import UUID

    appointment = Appointment(
        tenant_id=UUID(tenant_id),
        visitor_id=visitor_id,
        email=appointment_data.get("visitor_email"),
        service_type=appointment_data.get("topic"),
        proposed_slots=[{"date": appointment_data.get("preferred_date")}],
        notes=appointment_data.get("notes"),
        status="proposed",
    )
    db.add(appointment)
    try:
        await db.commit()
        logger.info(
            "conv.appointment_persisted",
            tenant=tenant_id,
            visitor=visitor_id,
            date=appointment_data.get("preferred_date"),
        )
    except Exception as exc:
        await db.rollback()
        logger.error("conv.appointment_persist_failed", error=str(exc))
