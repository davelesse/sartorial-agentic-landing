"""
═══════════════════════════════════════════════════════════
SARTORIAL AGENTIC — Agent Registry & Celery Tasks
Map agent slugs → classes, async execution via Celery.
═══════════════════════════════════════════════════════════
"""

import asyncio
from datetime import datetime, timezone
from uuid import UUID

import structlog
from anthropic import RateLimitError, APIConnectionError, APITimeoutError
from celery import shared_task

from app.agents.base import BaseAgent
from app.agents.content_creator import ContentCreatorAgent
from app.agents.conversational import ConversationalAgent
from app.agents.email_outreach import EmailOutreachAgent
from app.agents.lead_qualifier import LeadQualifierAgent
from app.agents.appointment_scheduler import AppointmentSchedulerAgent
from app.agents.customer_success import CustomerSuccessAgent
from app.agents.reputation_manager import ReputationManagerAgent
from app.agents.invoice_quote import InvoiceQuoteAgent
from app.agents.social_media import SocialMediaAgent

logger = structlog.get_logger()


# ─────────────────────────────────────
# AGENT REGISTRY
# ─────────────────────────────────────

AGENT_REGISTRY: dict[str, type[BaseAgent]] = {
    # Transversaux — disponibles pour tous les secteurs
    "email-outreach":        EmailOutreachAgent,
    "content-creator":       ContentCreatorAgent,
    "lead-qualifier":        LeadQualifierAgent,
    "appointment-scheduler": AppointmentSchedulerAgent,
    "customer-success":      CustomerSuccessAgent,
    "reputation-manager":    ReputationManagerAgent,
    "invoice-quote":         InvoiceQuoteAgent,
    "social-media-manager":  SocialMediaAgent,
    "conversational":        ConversationalAgent,
    # Sectoriels — à implémenter au fur et à mesure
    # "catalogue-vehicules":  CatalogueVehiculesAgent,
    # "matching-acheteur":    MatchingAcheteurAgent,
    # "fiche-produit-seo":    FicheProduitSEOAgent,
    # "gestion-agenda":       GestionAgendaAgent,
    # "menu-dynamique":       MenuDynamiqueAgent,
    # "suivi-patient":        SuiviPatientAgent,
}


def get_agent_class(slug: str) -> type[BaseAgent]:
    """Return the agent class for a given slug."""
    if slug not in AGENT_REGISTRY:
        raise ValueError(f"Agent '{slug}' non implémenté")
    return AGENT_REGISTRY[slug]


# ─────────────────────────────────────
# CELERY TASKS
# ─────────────────────────────────────

@shared_task(name="app.agents.tasks.execute_agent_task", bind=True, max_retries=3)
def execute_agent_task(self, task_id: str):
    """
    Execute an agent task asynchronously.
    Loads task from DB, runs the corresponding agent, saves result.
    """
    async def _run():
        from sqlalchemy import select
        from app.core.database import async_session
        from app.models import Agent, Task

        async with async_session() as db:
            # Charger la task
            result = await db.execute(select(Task).where(Task.id == UUID(task_id)))
            task = result.scalar_one_or_none()
            if not task:
                logger.error("agent.task_not_found", task_id=task_id)
                return

            # Charger l'agent
            agent_result = await db.execute(select(Agent).where(Agent.id == task.agent_id))
            agent_def = agent_result.scalar_one_or_none()
            if not agent_def:
                task.status = "failed"
                task.error_message = "Agent introuvable"
                task.completed_at = datetime.now(timezone.utc)
                await db.commit()
                return

            # Marquer running
            task.status = "running"
            task.started_at = datetime.now(timezone.utc)
            await db.commit()

            # Exécuter
            try:
                from sqlalchemy import func
                AgentCls = get_agent_class(agent_def.slug)
                agent = AgentCls(tenant_id=str(task.tenant_id))

                # Pour invoice-quote : injecter un numéro de document séquentiel
                input_data = dict(task.input_data)
                if agent_def.slug == "invoice-quote" and "document_number" not in input_data:
                    seq = (await db.execute(
                        select(func.count()).select_from(Task)
                        .where(Task.tenant_id == task.tenant_id, Task.agent_id == task.agent_id)
                    )).scalar_one()
                    year = datetime.now(timezone.utc).year
                    action = input_data.get("action", "generate_quote")
                    prefix = "FAC" if action == "convert_to_invoice" else "DEVIS"
                    input_data["document_number"] = f"{prefix}-{year}-{seq + 1:04d}"

                result = await agent.execute(input_data)

                # Sauver résultat
                task.status = "completed" if result.success else "failed"
                task.output_data = result.output
                task.error_message = result.error
                task.tokens_used = result.tokens_used
                task.cost_cents = result.cost_cents
                task.completed_at = datetime.now(timezone.utc)
                await db.commit()

                logger.info(
                    "agent.task.completed",
                    task_id=task_id,
                    status=task.status,
                    tokens=task.tokens_used,
                    cost_cents=task.cost_cents,
                )
            except Exception as e:
                logger.exception("agent.task.crashed", task_id=task_id, error=str(e))
                task.status = "failed"
                task.error_message = str(e)
                task.completed_at = datetime.now(timezone.utc)
                await db.commit()
                raise

    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(_run())
    except (RateLimitError, APIConnectionError, APITimeoutError) as exc:
        delay = 2 ** self.request.retries  # 1s, 2s, 4s
        logger.warning(
            "agent.task.retrying",
            task_id=task_id,
            attempt=self.request.retries + 1,
            retry_in=delay,
            error=str(exc),
        )
        raise self.retry(exc=exc, countdown=delay)
    finally:
        loop.close()


@shared_task(name="app.agents.tasks.health_check_all")
def health_check_all():
    """
    Periodic health check — scheduled every 15 min by Celery Beat.
    Verifies agent registry is loadable.
    """
    count = len(AGENT_REGISTRY)
    logger.info("agent.health_check", agents_registered=count)
    return {"status": "ok", "agents_count": count}
