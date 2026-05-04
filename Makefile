# ═══════════════════════════════════════════════════════════
# SARTORIAL AGENTIC — Makefile
# Commandes utilitaires pour le développement et le déploiement
# ═══════════════════════════════════════════════════════════

.PHONY: help up down build logs restart db-shell redis-shell backup ssl migrate migration deploy backup-s3

help: ## Afficher l'aide
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# ── Stack ──
up: ## Lancer toute la stack
	docker compose up -d

down: ## Arrêter toute la stack
	docker compose down

build: ## Rebuild tous les conteneurs
	docker compose build --no-cache

restart: ## Redémarrer la stack
	docker compose down && docker compose up -d

logs: ## Voir les logs en temps réel
	docker compose logs -f --tail=100

logs-backend: ## Logs du backend uniquement
	docker compose logs -f backend celery-worker

logs-frontend: ## Logs du frontend uniquement
	docker compose logs -f frontend

# ── Database ──
db-shell: ## Ouvrir un shell PostgreSQL
	docker compose exec postgres psql -U $${POSTGRES_USER:-sartorial} -d $${POSTGRES_DB:-sartorial_agentic}

db-backup: ## Sauvegarder la base de données
	@mkdir -p backups
	docker compose exec -T postgres pg_dump -U $${POSTGRES_USER:-sartorial} $${POSTGRES_DB:-sartorial_agentic} \
		| gzip > backups/sa-backup-$$(date +%Y%m%d-%H%M%S).sql.gz
	@echo "✓ Backup créé dans backups/"

db-restore: ## Restaurer depuis le dernier backup (usage: make db-restore FILE=backups/sa-backup-xxx.sql.gz)
	@test -f $(FILE) || (echo "Erreur: spécifiez FILE=backups/xxx.sql.gz" && exit 1)
	gunzip -c $(FILE) | docker compose exec -T postgres psql -U $${POSTGRES_USER:-sartorial} $${POSTGRES_DB:-sartorial_agentic}

# ── Redis ──
redis-shell: ## Ouvrir un shell Redis
	docker compose exec redis redis-cli -a $${REDIS_PASSWORD}

# ── SSL ──
ssl-init: ## Obtenir le certificat SSL initial
	docker compose run --rm certbot certonly \
		--webroot --webroot-path=/var/www/certbot \
		-d sartorial-agentic.ai -d www.sartorial-agentic.ai \
		--email admin@sartorial-agentic.ai --agree-tos --no-eff-email

ssl-renew: ## Renouveler le certificat SSL
	docker compose run --rm certbot renew
	docker compose exec nginx nginx -s reload

# ── Monitoring ──
status: ## Voir l'état de tous les conteneurs
	docker compose ps

health: ## Vérifier la santé des services
	@echo "── Backend ──"
	@curl -sf http://localhost:8000/health | python3 -m json.tool 2>/dev/null || echo "✗ Backend down"
	@echo "\n── Frontend ──"
	@curl -sf http://localhost:3000 > /dev/null && echo "✓ Frontend OK" || echo "✗ Frontend down"
	@echo "\n── PostgreSQL ──"
	@docker compose exec -T postgres pg_isready -U $${POSTGRES_USER:-sartorial} > /dev/null 2>&1 && echo "✓ PostgreSQL OK" || echo "✗ PostgreSQL down"
	@echo "\n── Redis ──"
	@docker compose exec -T redis redis-cli -a $${REDIS_PASSWORD} ping 2>/dev/null | grep -q PONG && echo "✓ Redis OK" || echo "✗ Redis down"

# ── Development ──
dev: ## Lancer en mode développement (avec volumes montés)
	docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d

test: ## Lancer les tests backend
	docker compose exec backend pytest -v --cov=app

lint: ## Linter le code backend
	docker compose exec backend ruff check app/

# ── Migrations ──
migrate: ## Appliquer les migrations Alembic
	docker compose exec backend alembic upgrade head

migration: ## Créer une nouvelle migration (usage: make migration MSG="description")
	docker compose exec backend alembic revision --autogenerate -m "$(MSG)"

# ── Déploiement ──
deploy: ## Déployer (pull + build + migrate + restart)
	git pull && $(MAKE) build && $(MAKE) migrate && $(MAKE) restart

# ── Backups S3 ──
backup-s3: ## Sauvegarder la DB et uploader sur S3
	@mkdir -p backups
	@BACKUP_FILE=backups/sa-backup-$$(date +%Y%m%d-%H%M%S).sql.gz; \
	docker compose exec -T postgres pg_dump -U $${POSTGRES_USER:-sartorial} $${POSTGRES_DB:-sartorial_agentic} \
		| gzip > $$BACKUP_FILE && echo "✓ Backup: $$BACKUP_FILE"; \
	if [ -n "$${S3_BACKUP_BUCKET}" ]; then \
		aws s3 cp $$BACKUP_FILE s3://$${S3_BACKUP_BUCKET}/$$(basename $$BACKUP_FILE) && echo "✓ Uploaded to S3"; \
		find backups/ -name "*.sql.gz" -mtime +$${BACKUP_RETENTION_DAYS:-30} -delete && echo "✓ Old backups pruned"; \
	fi
