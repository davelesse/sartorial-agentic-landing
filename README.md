# Sartorial Agentic

> Plateforme SaaS agentique premium — L'IA sur mesure qui travaille pendant que vous dormez.

## Architecture

```
┌───────────────────────────────────────────────────────────┐
│  Nginx (ports 80/443)                                     │
│  ├── /api/*  → FastAPI (port 8000)                        │
│  └── /      → Next.js (port 3000)                         │
└───────────────────────────────────────────────────────────┘
           │                          │
┌──────────▼─────────┐    ┌───────────▼──────────┐
│  FastAPI Backend   │    │  Next.js Frontend    │
│  - Auth (JWT)      │    │  - Landing           │
│  - Tenants         │    │  - Login/Register    │
│  - Agents          │    │  - Dashboard         │
│  - Tasks           │    │  - Billing           │
│  - Stripe          │    │  - Settings          │
└────────┬───────────┘    └──────────────────────┘
         │
    ┌────┴────┐
    │         │
┌───▼───┐ ┌──▼────┐ ┌──────────┐
│Postgres│ │ Redis │ │  Celery  │
│  16   │ │   7   │ │ Workers  │
└───────┘ └───────┘ └──────────┘
```

## Stack technique

| Couche | Technologie |
|---|---|
| Frontend | Next.js 15 + React 19 + TypeScript |
| Backend | Python 3.12 + FastAPI + SQLAlchemy 2.0 async |
| Database | PostgreSQL 16 |
| Cache & Queue | Redis 7 + Celery |
| AI/Agents | Claude API (Anthropic) + LangGraph |
| Paiements | Stripe (Checkout Sessions dynamiques) |
| Emails | Resend |
| Reverse Proxy | Nginx + Let's Encrypt |
| Conteneurs | Docker Compose |
| Hébergement | Hetzner Cloud CPX31 (Falkenstein, UE) |

## Structure du projet

```
sartorial-agentic/
├── backend/                    # FastAPI application
│   ├── app/
│   │   ├── agents/            # Agent Engine + implémentations
│   │   ├── api/v1/            # Routes REST API
│   │   ├── core/              # Config, DB, Security, Deps, Celery
│   │   ├── stripe/            # Module Stripe complet
│   │   ├── main.py            # Entry point FastAPI
│   │   ├── models.py          # SQLAlchemy ORM models
│   │   └── schemas.py         # Pydantic request/response schemas
│   ├── Dockerfile
│   └── requirements.txt
│
├── frontend/                   # Next.js application
│   ├── src/
│   │   ├── app/
│   │   │   ├── dashboard/     # Dashboard pages (overview, agents, tasks, billing, settings)
│   │   │   ├── login/
│   │   │   ├── register/
│   │   │   ├── layout.tsx
│   │   │   └── page.tsx       # Redirection intelligente
│   │   └── lib/
│   │       └── api.ts         # Typed API client
│   ├── Dockerfile
│   ├── next.config.js
│   ├── package.json
│   └── tsconfig.json
│
├── database/
│   └── init/
│       └── 01-schema.sql      # Schema + seed du catalog agents
│
├── nginx/
│   ├── nginx.conf             # Production (SSL)
│   └── nginx.dev.conf         # Development (HTTP only)
│
├── scripts/
│   ├── bootstrap.sh           # Setup serveur Ubuntu vierge
│   └── deploy-init.sh         # Déploiement initial de la stack
│
├── docker-compose.yml         # Production stack
├── docker-compose.dev.yml     # Development overrides
├── Makefile                   # Commandes utilitaires
├── .env.example               # Template variables env
├── .gitignore
├── DEPLOYMENT.md              # Guide de déploiement pas-à-pas
└── README.md                  # Ce fichier
```

## Démarrage rapide

### Prérequis

- Serveur Hetzner Cloud CPX31 (Ubuntu 24.04)
- Domaine `sartorial-agentic.ai` (DNS pointé vers le serveur)
- Clés API : Stripe, Anthropic (Claude), Resend

### Déploiement

Voir [DEPLOYMENT.md](./DEPLOYMENT.md) pour le guide complet pas-à-pas.

Version courte :

```bash
# 1. Sur ton ordinateur : upload des fichiers
scp -i ~/.ssh/sartorial_ed25519 \
    scripts/bootstrap.sh scripts/deploy-init.sh \
    sartorial-agentic-stack.tar.gz \
    root@<IP_HETZNER>:/tmp/

# 2. Sur le serveur (en root) : bootstrap
sudo bash /tmp/bootstrap.sh

# 3. Reconnexion en user sartorial
ssh -p 2242 sartorial@<IP_HETZNER>

# 4. Déploiement
bash /tmp/deploy-init.sh
```

### Développement local

```bash
# Clone & config
cp .env.example .env
# Remplir les clés dans .env

# Démarrer la stack en mode dev (hot reload)
docker compose -f docker-compose.yml -f docker-compose.dev.yml up

# Accès
# Frontend : http://localhost:3000
# Backend  : http://localhost:8000
# Docs API : http://localhost:8000/api/docs
```

## Commandes Makefile

```bash
make up              # Lancer la stack
make down            # Arrêter
make restart         # Redémarrer
make logs            # Logs en temps réel
make status          # État des conteneurs
make health          # Health check complet
make db-backup       # Backup PostgreSQL
make db-shell        # Shell PostgreSQL
make ssl-init        # Obtenir SSL Let's Encrypt
make ssl-renew       # Renouveler SSL
```

## Plans tarifaires

| Plan | Prix | Agents | Exécutions/mois |
|---|---|---|---|
| **Atelier** | 79€/mois | 3 transversaux | 500 |
| **Manufacture** | 199€/mois | 6 (trans. + sectoriels) | 2 500 |
| **Maison** | 499€/mois | Tous + custom | Illimité |

Plans partenaires : Associé (0€, 20% commission) · Maison Partenaire (497€, 30%).

## 6 secteurs cibles

Automobile · Immobilier · E-Commerce · Beauté · Santé · Restauration

## Palette de marque

| Token | Valeur |
|---|---|
| Abyss | `#030810` |
| Midnight | `#060E1A` |
| Purple | `#4A0E2E` |
| Gold | `#C9A84C` |
| Ivory | `#F5F0EB` |

Typographies : **Cormorant Garamond** (titres) · **DM Sans** (corps).

Signature : **— Votre Tailleur**

---

© 2026 Sartorial Agentic. L'IA sur mesure qui travaille pendant que vous dormez.
