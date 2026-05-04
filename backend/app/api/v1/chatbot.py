"""
═══════════════════════════════════════════════════════════
SARTORIAL AGENTIC — Chatbot API
Public endpoints pour le widget embarqué.
Authentification par clé publique du tenant (pas JWT).
═══════════════════════════════════════════════════════════
"""

import json
from uuid import UUID, uuid4

import structlog
from fastapi import APIRouter, Depends, Header, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents import conversation_store as store
from app.agents.conversational import (
    ConversationalAgent,
    SUPPORTED_LANGUAGES,
    DEFAULT_LANGUAGE,
)
from app.core.database import get_db
from app.models import Tenant

logger = structlog.get_logger()
router = APIRouter()


# ─────────────────────────────────────
# AUTH PAR PUBLIC KEY
# ─────────────────────────────────────

async def get_tenant_by_public_key(
    x_public_key: str = Header(..., alias="X-Public-Key"),
    db: AsyncSession = Depends(get_db),
) -> Tenant:
    """
    Authentifie une requête widget via la clé publique du tenant.
    La clé publique est un token aléatoire 64-char (tenant.public_api_key),
    beaucoup plus sûre que le slug qui est prédictible.
    """
    if not x_public_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Clé publique manquante (X-Public-Key header)",
        )

    result = await db.execute(select(Tenant).where(Tenant.public_api_key == x_public_key))
    tenant = result.scalar_one_or_none()

    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant introuvable")

    # Vérif abonnement
    if tenant.subscription_status not in ("active", "trialing"):
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="Abonnement inactif",
        )

    return tenant


# ─────────────────────────────────────
# SCHEMAS
# ─────────────────────────────────────

class ChatInitRequest(BaseModel):
    visitor_id: str | None = Field(default=None, description="Si null, un nouveau sera généré")
    language_hint: str | None = Field(default=None, description="Langue détectée côté navigateur")


class ChatInitResponse(BaseModel):
    visitor_id: str
    language: str
    greeting: str
    tenant_name: str


class ChatMessageRequest(BaseModel):
    visitor_id: str
    message: str = Field(min_length=1, max_length=2000)


# ─────────────────────────────────────
# ROUTES
# ─────────────────────────────────────

@router.post("/init", response_model=ChatInitResponse)
async def init_chat(
    request: ChatInitRequest,
    tenant: Tenant = Depends(get_tenant_by_public_key),
):
    """
    Initialise une session de chat.
    Retourne le visitor_id (nouveau ou existant) et le greeting dans la bonne langue.
    """
    visitor_id = request.visitor_id or str(uuid4())
    profile = await store.get_visitor_profile(visitor_id, str(tenant.id))

    # Langue : priorité au hint navigateur si première visite, sinon profil existant
    if request.language_hint and request.language_hint in SUPPORTED_LANGUAGES:
        if profile.message_count == 0:
            profile.language = request.language_hint

    lang = profile.language if profile.language in SUPPORTED_LANGUAGES else DEFAULT_LANGUAGE

    agent = ConversationalAgent(
        tenant_id=str(tenant.id),
        tenant_name=tenant.name,
        tenant_sector=tenant.sectors[0] if tenant.sectors else "ecommerce",
    )

    greeting_key = f"greeting_{lang}"
    greeting = agent.persona.get(greeting_key, agent.persona["greeting_fr"])

    await store.save_visitor_profile(profile)

    return ChatInitResponse(
        visitor_id=visitor_id,
        language=lang,
        greeting=greeting,
        tenant_name=tenant.name,
    )


@router.post("/message")
async def send_message(
    request: ChatMessageRequest,
    tenant: Tenant = Depends(get_tenant_by_public_key),
    db: AsyncSession = Depends(get_db),
):
    """
    Envoie un message et stream la réponse en Server-Sent Events.
    """
    tenant_id = str(tenant.id)
    visitor_id = request.visitor_id

    profile = await store.get_visitor_profile(visitor_id, tenant_id)

    # Détection de langue en live — permet le switch mid-conversation
    agent = ConversationalAgent(
        tenant_id=tenant_id,
        tenant_name=tenant.name,
        tenant_sector=tenant.sectors[0] if tenant.sectors else "ecommerce",
    )

    # Détection langue si le message est suffisamment long
    if len(request.message) >= 10:
        detected = await agent.detect_language(request.message)
        if detected != profile.language:
            logger.info("conv.lang_switch", visitor=visitor_id, from_=profile.language, to=detected)
            profile.language = detected

    history = await store.get_history(visitor_id, tenant_id)
    summary = await store.get_summary(visitor_id, tenant_id)

    # Persist le message user dès maintenant
    await store.append_message(visitor_id, tenant_id, "user", request.message)

    async def event_stream():
        assistant_text = ""
        tool_calls = []

        try:
            async for event in agent.chat_stream(
                profile=profile,
                message_history=history,
                user_message=request.message,
                conversation_summary=summary,
            ):
                event_type = event["type"]

                if event_type == "text_delta":
                    assistant_text += event["delta"]
                    yield f"data: {json.dumps(event)}\n\n"

                elif event_type == "tool_use":
                    tool_calls.append(event)

                    # Action côté serveur pour les tools non-informatifs
                    if event["tool"] == "update_visitor_profile":
                        await store.update_profile_from_tool(profile, event["input"])
                    elif event["tool"] == "capture_lead":
                        await store.persist_lead_capture(db, tenant_id, visitor_id, event["input"])
                    elif event["tool"] == "book_appointment":
                        await store.persist_appointment(db, tenant_id, visitor_id, event["input"])

                    yield f"data: {json.dumps(event)}\n\n"

                elif event_type == "done":
                    # Sauvegarde conversation
                    if assistant_text:
                        await store.append_message(visitor_id, tenant_id, "assistant", assistant_text)
                    await store.save_visitor_profile(profile)

                    # Si conversation très longue → résumé
                    if len(history) >= 30 and len(history) % 20 == 0:
                        new_summary = await agent.summarize_conversation(history)
                        await store.save_summary(visitor_id, tenant_id, new_summary)

                    yield f"data: {json.dumps(event)}\n\n"
                    yield "data: [DONE]\n\n"

        except Exception as e:
            logger.exception("conv.stream.error", visitor=visitor_id, error=str(e))
            error_event = {"type": "error", "message": "Une erreur est survenue."}
            yield f"data: {json.dumps(error_event)}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable Nginx buffering
        },
    )


@router.get("/history/{visitor_id}")
async def get_conversation_history(
    visitor_id: str,
    tenant: Tenant = Depends(get_tenant_by_public_key),
):
    """Récupère l'historique visible côté widget (pour reprise de conversation)."""
    history = await store.get_history(visitor_id, str(tenant.id))
    profile = await store.get_visitor_profile(visitor_id, str(tenant.id))

    return {
        "visitor_id": visitor_id,
        "language":   profile.language,
        "messages":   history,
    }


@router.delete("/history/{visitor_id}")
async def clear_conversation(
    visitor_id: str,
    tenant: Tenant = Depends(get_tenant_by_public_key),
):
    """Efface la conversation d'un visiteur (bouton 'nouvelle conversation')."""
    r = store._get_redis()
    tenant_id = str(tenant.id)
    await r.delete(
        store._history_key(visitor_id, tenant_id),
        store._summary_key(visitor_id, tenant_id),
    )
    logger.info("conv.cleared", visitor=visitor_id, tenant=tenant_id)
    return {"ok": True}
