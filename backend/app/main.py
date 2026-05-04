"""
═══════════════════════════════════════════════════════════
SARTORIAL AGENTIC — FastAPI Application
Main entry point
═══════════════════════════════════════════════════════════
"""

from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware

from app.core.config import settings
from app.core.database import engine, Base

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup & shutdown events."""
    logger.info("sartorial_agentic.starting", env=settings.APP_ENV, version=settings.APP_VERSION)

    # Validation des variables d'environnement critiques
    if settings.APP_ENV == "production":
        if not settings.ANTHROPIC_API_KEY:
            raise RuntimeError("ANTHROPIC_API_KEY manquant en production")
        if not settings.STRIPE_SECRET_KEY:
            raise RuntimeError("STRIPE_SECRET_KEY manquant en production")
        logger.info("sartorial_agentic.production_config_ok")

    # Dev uniquement : créer les tables depuis les modèles ORM.
    # En production : utiliser `alembic upgrade head`.
    if settings.APP_ENV == "development":
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    yield

    logger.info("sartorial_agentic.shutdown")
    await engine.dispose()


app = FastAPI(
    title="Sartorial Agentic API",
    description="Plateforme SaaS Agentique Premium — API Backend",
    version="1.0.0",
    docs_url="/api/docs" if settings.APP_ENV == "development" else None,
    redoc_url="/api/redoc" if settings.APP_ENV == "development" else None,
    lifespan=lifespan,
)

# ─────────────────────────────────────
# MIDDLEWARE
# ─────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-Requested-With"],
)

if settings.APP_ENV == "production":
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=["sartorial-agentic.ai", "*.sartorial-agentic.ai"],
    )


# ─────────────────────────────────────
# SYSTEM ROUTES
# ─────────────────────────────────────

@app.get("/health", tags=["system"])
async def health_check():
    return {
        "status": "healthy",
        "service": "sartorial-agentic",
        "version": settings.APP_VERSION,
        "env": settings.APP_ENV,
    }


@app.get("/api/v1", tags=["system"])
async def api_root():
    return {
        "message": "Bienvenue dans l'atelier — Sartorial Agentic API v1",
        "signature": "Votre Tailleur",
    }


# ─────────────────────────────────────
# ROUTER REGISTRATION
# ─────────────────────────────────────

# Phase 1 — Stripe
from app.stripe.routes import router as stripe_routes
from app.stripe.webhooks import router as stripe_webhooks

app.include_router(stripe_routes,   prefix="/api/v1/stripe",   tags=["stripe"])
app.include_router(stripe_webhooks, prefix="/api/v1/webhooks", tags=["webhooks"])

# Phase 2 — Auth, Tenants, Agents, Tasks, Waitlist
from app.api.v1 import agents, analytics, auth, chatbot, commission_only, partners, tasks, tenants, waitlist

app.include_router(auth.router,            prefix="/api/v1/auth",            tags=["auth"])
app.include_router(tenants.router,         prefix="/api/v1/tenants",         tags=["tenants"])
app.include_router(agents.router,          prefix="/api/v1/agents",          tags=["agents"])
app.include_router(tasks.router,           prefix="/api/v1/tasks",           tags=["tasks"])
app.include_router(waitlist.router,        prefix="/api/v1/waitlist",        tags=["waitlist"])

# Phase 4 — Conversational Agent (chatbot public)
app.include_router(chatbot.router,         prefix="/api/v1/chatbot",         tags=["chatbot"])

# Phase 5 — Partners, Analytics, Commission Only
app.include_router(partners.router,        prefix="/api/v1/partners",        tags=["partners"])
app.include_router(analytics.router,       prefix="/api/v1/analytics",       tags=["analytics"])
app.include_router(commission_only.router, prefix="/api/v1/commission-only", tags=["commission-only"])
