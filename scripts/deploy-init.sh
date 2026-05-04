#!/bin/bash
# ═══════════════════════════════════════════════════════════
# SARTORIAL AGENTIC — Initial Deployment Script
# À lancer APRÈS bootstrap.sh, en tant que user sartorial
# Usage: bash deploy-init.sh
# ═══════════════════════════════════════════════════════════

set -euo pipefail

GOLD='\033[0;33m'
GREEN='\033[0;32m'
RED='\033[0;31m'
PURPLE='\033[0;35m'
NC='\033[0m'

log()    { echo -e "${GOLD}◆${NC} $1"; }
ok()     { echo -e "${GREEN}✓${NC} $1"; }
warn()   { echo -e "${RED}⚠${NC} $1"; }
header() {
  echo ""
  echo -e "${PURPLE}═══════════════════════════════════════════════════${NC}"
  echo -e "${PURPLE}  $1${NC}"
  echo -e "${PURPLE}═══════════════════════════════════════════════════${NC}"
}

PROJECT_DIR="$HOME/sartorial-agentic"
REPO_URL="${REPO_URL:-git@github.com:yourusername/sartorial-agentic.git}"

# ─────────────────────────────────────
# 1. CLONE PROJET
# ─────────────────────────────────────
header "1/5 · Récupération du projet"

if [[ -d "$PROJECT_DIR/.git" ]]; then
  log "Repo déjà cloné, pull des derniers changements"
  cd "$PROJECT_DIR"
  git pull
else
  log "Clone du repo $REPO_URL"
  # Si pas de repo git encore, on crée la structure depuis l'archive locale
  if [[ -f "/tmp/sartorial-agentic-stack.tar.gz" ]]; then
    tar xzf /tmp/sartorial-agentic-stack.tar.gz -C "$HOME"
    ok "Archive extraite"
  else
    warn "Place l'archive sartorial-agentic-stack.tar.gz dans /tmp/ ou configure REPO_URL"
    warn "Upload via : scp -P 2242 sartorial-agentic-stack.tar.gz sartorial@<IP>:/tmp/"
    exit 1
  fi
fi

cd "$PROJECT_DIR"
ok "Projet dans $PROJECT_DIR"

# ─────────────────────────────────────
# 2. CONFIGURATION .env
# ─────────────────────────────────────
header "2/5 · Configuration des variables d'environnement"

if [[ ! -f ".env" ]]; then
  cp .env.example .env

  # Génération automatique des secrets
  APP_SECRET=$(openssl rand -hex 32)
  JWT_SECRET=$(openssl rand -hex 32)
  POSTGRES_PASS=$(openssl rand -base64 24 | tr -d '/+=' | head -c 24)
  REDIS_PASS=$(openssl rand -base64 24 | tr -d '/+=' | head -c 24)

  sed -i "s|APP_SECRET_KEY=.*|APP_SECRET_KEY=$APP_SECRET|" .env
  sed -i "s|JWT_SECRET=.*|JWT_SECRET=$JWT_SECRET|" .env
  sed -i "s|POSTGRES_PASSWORD=.*|POSTGRES_PASSWORD=$POSTGRES_PASS|" .env
  sed -i "s|REDIS_PASSWORD=.*|REDIS_PASSWORD=$REDIS_PASS|" .env
  sed -i "s|APP_ENV=.*|APP_ENV=production|" .env

  ok ".env créé avec secrets générés automatiquement"
  warn "⚠  COMPLÈTE MANUELLEMENT :"
  warn "     STRIPE_PUBLIC_KEY, STRIPE_SECRET_KEY, STRIPE_WEBHOOK_SECRET"
  warn "     ANTHROPIC_API_KEY, RESEND_API_KEY"
  warn ""
  warn "Édite avec : nano .env"
  warn ""
  read -p "Appuie sur Entrée une fois le .env complété..."
else
  ok ".env déjà configuré"
fi

# Vérification des clés critiques
source .env
MISSING=""
for var in STRIPE_SECRET_KEY ANTHROPIC_API_KEY RESEND_API_KEY; do
  if [[ -z "${!var}" ]] || [[ "${!var}" == "sk_test_..." ]] || [[ "${!var}" == "re_..." ]]; then
    MISSING="$MISSING $var"
  fi
done

if [[ -n "$MISSING" ]]; then
  warn "Variables manquantes :$MISSING"
  warn "Complète .env avant de continuer"
  exit 1
fi
ok "Toutes les variables critiques sont définies"

# ─────────────────────────────────────
# 3. BUILD DES IMAGES DOCKER
# ─────────────────────────────────────
header "3/5 · Build des images Docker"

docker compose build --no-cache
ok "Images buildées"

# ─────────────────────────────────────
# 4. OBTENTION SSL (Let's Encrypt)
# ─────────────────────────────────────
header "4/5 · Obtention du certificat SSL"

DOMAIN=$(grep "^DOMAIN=" .env | cut -d '=' -f2)
if [[ -z "$DOMAIN" ]]; then
  DOMAIN="sartorial-agentic.ai"
fi

# Vérification DNS
log "Vérification que $DOMAIN pointe vers ce serveur..."
PUBLIC_IP=$(curl -s -4 icanhazip.com)
DNS_IP=$(dig +short $DOMAIN | tail -n1)

if [[ "$DNS_IP" != "$PUBLIC_IP" ]]; then
  warn "DNS $DOMAIN → $DNS_IP (attendu : $PUBLIC_IP)"
  warn "Configure le DNS avant de continuer, ou SSL va échouer."
  read -p "Continuer quand même ? (o/N) " -n 1 -r
  echo
  [[ ! $REPLY =~ ^[Oo]$ ]] && exit 1
else
  ok "DNS configuré correctement"
fi

# Lance Nginx seul d'abord (pour le challenge HTTP)
docker compose up -d nginx

# Obtention certificat
docker compose run --rm certbot certonly \
  --webroot --webroot-path=/var/www/certbot \
  -d $DOMAIN -d www.$DOMAIN \
  --email admin@$DOMAIN --agree-tos --no-eff-email \
  --non-interactive

if [[ $? -eq 0 ]]; then
  ok "Certificat SSL obtenu pour $DOMAIN"
  docker compose exec nginx nginx -s reload
else
  warn "Échec SSL — tu peux retry avec : make ssl-init"
fi

# ─────────────────────────────────────
# 5. LANCEMENT STACK COMPLÈTE
# ─────────────────────────────────────
header "5/5 · Lancement de la stack complète"

docker compose up -d

sleep 8

# Health checks
log "Vérification des services..."

services=("postgres" "redis" "backend" "frontend" "nginx" "celery-worker" "celery-beat")
all_ok=true

for svc in "${services[@]}"; do
  if docker compose ps --status running | grep -q "$svc"; then
    ok "$svc is running"
  else
    warn "$svc is NOT running"
    all_ok=false
  fi
done

echo ""
if [[ "$all_ok" == true ]]; then
  echo -e "${GREEN}═══════════════════════════════════════════════════${NC}"
  echo -e "${GREEN}  DÉPLOIEMENT RÉUSSI${NC}"
  echo -e "${GREEN}═══════════════════════════════════════════════════${NC}"
  echo ""
  echo -e "${GOLD}Ta plateforme est live :${NC}"
  echo "  https://$DOMAIN"
  echo ""
  echo -e "${GOLD}Commandes utiles :${NC}"
  echo "  make status       # État des services"
  echo "  make logs         # Voir les logs"
  echo "  make health       # Health check complet"
  echo "  make db-backup    # Sauvegarder la DB"
  echo ""
  echo -e "${PURPLE}— Votre Tailleur${NC}"
else
  warn "Certains services ne sont pas démarrés"
  warn "Diagnostique avec : docker compose logs"
fi
