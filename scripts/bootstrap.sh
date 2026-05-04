#!/bin/bash
# ═══════════════════════════════════════════════════════════
# SARTORIAL AGENTIC — Server Bootstrap Script
# Ubuntu 24.04 LTS · Hetzner Cloud CPX31
# Usage: sudo bash bootstrap.sh
# ═══════════════════════════════════════════════════════════

set -euo pipefail

# ─────────────────────────────────────
# CONFIGURATION — À ADAPTER
# ─────────────────────────────────────
DEPLOY_USER="sartorial"
DEPLOY_USER_PASSWORD=""              # Sera généré si vide
SSH_PORT="2242"                      # Port SSH custom (défaut 22 évité pour moins de bots)
DOMAIN="sartorial-agentic.ai"
ADMIN_EMAIL="admin@sartorial-agentic.ai"
TIMEZONE="Europe/Paris"
GITHUB_SSH_KEY=""                    # Ta clé publique SSH — OBLIGATOIRE (ssh-rsa AAAA... ou ssh-ed25519 AAAA...)

# ─────────────────────────────────────
# COULEURS & LOGS
# ─────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
GOLD='\033[0;33m'
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

# ─────────────────────────────────────
# VÉRIFICATIONS PRÉALABLES
# ─────────────────────────────────────
header "SARTORIAL AGENTIC — Bootstrap du serveur"

if [[ $EUID -ne 0 ]]; then
   warn "Ce script doit être lancé en root (sudo bash bootstrap.sh)"
   exit 1
fi

if [[ -z "$GITHUB_SSH_KEY" ]]; then
   warn "GITHUB_SSH_KEY est vide !"
   warn "Édite ce script et ajoute ta clé publique SSH (ligne GITHUB_SSH_KEY)"
   warn "Tu peux l'obtenir avec : cat ~/.ssh/id_ed25519.pub"
   exit 1
fi

# Validation du format de la clé SSH
if ! [[ "$GITHUB_SSH_KEY" =~ ^ssh-(rsa|ed25519|ecdsa)[[:space:]] ]]; then
   warn "GITHUB_SSH_KEY ne semble pas être une clé publique SSH valide."
   warn "Format attendu : ssh-ed25519 AAAA... ou ssh-rsa AAAA..."
   exit 1
fi

# Génération mot de passe si vide
if [[ -z "$DEPLOY_USER_PASSWORD" ]]; then
  DEPLOY_USER_PASSWORD=$(openssl rand -base64 24)
  log "Mot de passe généré pour $DEPLOY_USER"
fi

# ─────────────────────────────────────
# 1. SYSTEM UPDATE
# ─────────────────────────────────────
header "1/10 · Mise à jour du système"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get upgrade -y -qq
apt-get install -y -qq \
  curl wget git vim htop \
  ufw fail2ban \
  ca-certificates gnupg lsb-release \
  unattended-upgrades apt-listchanges \
  software-properties-common \
  jq tree ncdu
ok "Système à jour"

# Timezone
timedatectl set-timezone "$TIMEZONE"
ok "Timezone : $TIMEZONE"

# ─────────────────────────────────────
# 2. USER NON-ROOT
# ─────────────────────────────────────
header "2/10 · Création du user $DEPLOY_USER"

if id "$DEPLOY_USER" &>/dev/null; then
  log "User $DEPLOY_USER existe déjà"
else
  useradd -m -s /bin/bash "$DEPLOY_USER"
  echo "$DEPLOY_USER:$DEPLOY_USER_PASSWORD" | chpasswd
  usermod -aG sudo "$DEPLOY_USER"
  ok "User $DEPLOY_USER créé avec sudo"
fi

# SSH key setup
mkdir -p /home/$DEPLOY_USER/.ssh
echo "$GITHUB_SSH_KEY" > /home/$DEPLOY_USER/.ssh/authorized_keys
chown -R $DEPLOY_USER:$DEPLOY_USER /home/$DEPLOY_USER/.ssh
chmod 700 /home/$DEPLOY_USER/.ssh
chmod 600 /home/$DEPLOY_USER/.ssh/authorized_keys
ok "Clé SSH installée pour $DEPLOY_USER"

# Sudo sans mot de passe (pour automatisation CI/CD — facultatif mais pratique)
echo "$DEPLOY_USER ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/$DEPLOY_USER
chmod 440 /etc/sudoers.d/$DEPLOY_USER
ok "Sudo sans mot de passe configuré"

# ─────────────────────────────────────
# 3. SSH HARDENING
# ─────────────────────────────────────
header "3/10 · Durcissement SSH (port $SSH_PORT)"

SSHD_CONFIG="/etc/ssh/sshd_config"
cp "$SSHD_CONFIG" "${SSHD_CONFIG}.backup.$(date +%s)"

# Config SSH sécurisée
cat > /etc/ssh/sshd_config.d/99-sartorial.conf << EOF
# ═══ Sartorial Agentic — SSH Hardening ═══
Port $SSH_PORT
PermitRootLogin no
PasswordAuthentication no
PubkeyAuthentication yes
PermitEmptyPasswords no
ChallengeResponseAuthentication no
UsePAM yes
X11Forwarding no
PrintMotd no
ClientAliveInterval 300
ClientAliveCountMax 2
MaxAuthTries 3
MaxSessions 5
AllowUsers $DEPLOY_USER
Protocol 2
EOF

# Test avant restart
sshd -t && ok "Config SSH valide" || (warn "Config SSH invalide !" && exit 1)

systemctl restart ssh
ok "SSH durci et relancé sur le port $SSH_PORT"

# ─────────────────────────────────────
# 4. FIREWALL UFW
# ─────────────────────────────────────
header "4/10 · Configuration du firewall UFW"

ufw --force reset > /dev/null
ufw default deny incoming
ufw default allow outgoing

# SSH sur le nouveau port
ufw allow $SSH_PORT/tcp comment 'SSH'

# HTTP/HTTPS
ufw allow 80/tcp comment 'HTTP'
ufw allow 443/tcp comment 'HTTPS'

# Enable
ufw --force enable
ok "Firewall actif : SSH($SSH_PORT), HTTP(80), HTTPS(443)"

# ─────────────────────────────────────
# 5. FAIL2BAN
# ─────────────────────────────────────
header "5/10 · Configuration de fail2ban"

cat > /etc/fail2ban/jail.local << EOF
[DEFAULT]
bantime = 3600
findtime = 600
maxretry = 5
destemail = $ADMIN_EMAIL
sender = fail2ban@$DOMAIN
action = %(action_mwl)s

[sshd]
enabled = true
port = $SSH_PORT
filter = sshd
logpath = /var/log/auth.log
maxretry = 3
bantime = 86400

[nginx-http-auth]
enabled = true
filter = nginx-http-auth
port = http,https
logpath = /var/log/nginx/error.log

[nginx-botsearch]
enabled = true
filter = nginx-botsearch
port = http,https
logpath = /var/log/nginx/error.log
maxretry = 2
EOF

systemctl enable fail2ban > /dev/null 2>&1
systemctl restart fail2ban
ok "fail2ban actif (3 tentatives SSH → ban 24h)"

# ─────────────────────────────────────
# 6. MISES À JOUR AUTOMATIQUES
# ─────────────────────────────────────
header "6/10 · Activation des mises à jour de sécurité automatiques"

cat > /etc/apt/apt.conf.d/20auto-upgrades << 'EOF'
APT::Periodic::Update-Package-Lists "1";
APT::Periodic::Download-Upgradeable-Packages "1";
APT::Periodic::AutocleanInterval "7";
APT::Periodic::Unattended-Upgrade "1";
EOF

cat > /etc/apt/apt.conf.d/50unattended-upgrades << EOF
Unattended-Upgrade::Allowed-Origins {
    "\${distro_id}:\${distro_codename}";
    "\${distro_id}:\${distro_codename}-security";
    "\${distro_id}ESMApps:\${distro_codename}-apps-security";
    "\${distro_id}ESM:\${distro_codename}-infra-security";
};
Unattended-Upgrade::Automatic-Reboot "true";
Unattended-Upgrade::Automatic-Reboot-Time "04:00";
Unattended-Upgrade::Mail "$ADMIN_EMAIL";
Unattended-Upgrade::MailReport "on-change";
EOF

systemctl enable unattended-upgrades > /dev/null 2>&1
ok "Auto-updates sécurité actives (reboot 4h si nécessaire)"

# ─────────────────────────────────────
# 7. DOCKER + COMPOSE
# ─────────────────────────────────────
header "7/10 · Installation Docker + Docker Compose"

if ! command -v docker &> /dev/null; then
  install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg | \
    gpg --dearmor -o /etc/apt/keyrings/docker.gpg
  chmod a+r /etc/apt/keyrings/docker.gpg

  echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
    https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
    tee /etc/apt/sources.list.d/docker.list > /dev/null

  apt-get update -qq
  apt-get install -y -qq \
    docker-ce docker-ce-cli containerd.io \
    docker-buildx-plugin docker-compose-plugin

  ok "Docker installé"
else
  ok "Docker déjà installé"
fi

# Add deploy user to docker group
usermod -aG docker $DEPLOY_USER

# Configuration daemon Docker — logs rotés
cat > /etc/docker/daemon.json << 'EOF'
{
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "10m",
    "max-file": "3"
  },
  "live-restore": true,
  "default-address-pools": [
    { "base": "172.28.0.0/16", "size": 24 }
  ]
}
EOF

systemctl restart docker
systemctl enable docker > /dev/null 2>&1
ok "Docker daemon configuré (log rotation 10Mo × 3)"

# ─────────────────────────────────────
# 8. OPTIMISATIONS SYSTÈME
# ─────────────────────────────────────
header "8/10 · Optimisations kernel & système"

cat > /etc/sysctl.d/99-sartorial.conf << 'EOF'
# ═══ Sartorial Agentic — Kernel Tuning ═══
# Network
net.core.somaxconn = 1024
net.ipv4.tcp_max_syn_backlog = 2048
net.ipv4.ip_local_port_range = 10000 65535
net.ipv4.tcp_fin_timeout = 15
net.ipv4.tcp_keepalive_time = 300
net.ipv4.tcp_tw_reuse = 1

# File descriptors (pour FastAPI + Celery)
fs.file-max = 2097152

# Swappiness (VPS avec SSD NVMe)
vm.swappiness = 10
vm.overcommit_memory = 1
EOF

sysctl -p /etc/sysctl.d/99-sartorial.conf > /dev/null

# Limites user (pour Celery workers)
cat > /etc/security/limits.d/99-sartorial.conf << EOF
$DEPLOY_USER soft nofile 65536
$DEPLOY_USER hard nofile 65536
$DEPLOY_USER soft nproc 4096
$DEPLOY_USER hard nproc 4096
EOF

ok "Kernel optimisé pour workload web + agents"

# ─────────────────────────────────────
# 9. RÉPERTOIRE PROJET
# ─────────────────────────────────────
header "9/10 · Préparation du répertoire projet"

PROJECT_DIR="/home/$DEPLOY_USER/sartorial-agentic"
mkdir -p "$PROJECT_DIR"/{backups,logs,ssl}
chown -R $DEPLOY_USER:$DEPLOY_USER "/home/$DEPLOY_USER"

# Cron backup quotidien
BACKUP_SCRIPT="/opt/sartorial/scripts/backup.sh"
mkdir -p /opt/sartorial/scripts
cat > "$BACKUP_SCRIPT" << 'BACKUP_EOF'
#!/bin/bash
set -euo pipefail
cd /home/sartorial/sartorial-agentic
make backup-s3 >> /home/sartorial/sartorial-agentic/logs/backup.log 2>&1
BACKUP_EOF
chmod +x "$BACKUP_SCRIPT"
(crontab -l 2>/dev/null || true; echo "0 3 * * * $BACKUP_SCRIPT") | crontab -
ok "Cron backup quotidien configuré (3h00 chaque nuit)"

# Swap file de 2Go (sécurité si pic RAM)
if [[ ! -f /swapfile ]]; then
  fallocate -l 2G /swapfile
  chmod 600 /swapfile
  mkswap /swapfile > /dev/null
  swapon /swapfile
  echo '/swapfile none swap sw 0 0' >> /etc/fstab
  ok "Swap de 2Go créé"
else
  ok "Swap déjà présent"
fi

# ─────────────────────────────────────
# 10. RÉCAPITULATIF
# ─────────────────────────────────────
header "10/10 · Bootstrap terminé ✓"

# Public IP
PUBLIC_IP=$(curl -s -4 icanhazip.com)

echo ""
echo -e "${GREEN}═══════════════════════════════════════════════════${NC}"
echo -e "${GREEN}  SERVEUR PRÊT POUR SARTORIAL AGENTIC${NC}"
echo -e "${GREEN}═══════════════════════════════════════════════════${NC}"
echo ""
echo -e "${GOLD}Connexion SSH :${NC}"
echo "  ssh -p $SSH_PORT $DEPLOY_USER@$PUBLIC_IP"
echo ""
echo -e "${GOLD}Informations serveur :${NC}"
echo "  IP publique    : $PUBLIC_IP"
echo "  User deploy    : $DEPLOY_USER"
echo "  Port SSH       : $SSH_PORT"
echo "  Domaine cible  : $DOMAIN"
echo "  Timezone       : $TIMEZONE"
echo ""
echo -e "${GOLD}Mot de passe user $DEPLOY_USER :${NC}"
echo "  $DEPLOY_USER_PASSWORD"
echo -e "${RED}⚠  NOTE CE MOT DE PASSE DANS UN GESTIONNAIRE (1Password, Bitwarden).${NC}"
echo ""
echo -e "${GOLD}Prochaines étapes :${NC}"
echo "  1. Pointe le DNS de $DOMAIN vers $PUBLIC_IP (A record)"
echo "  2. Connecte-toi avec la commande SSH ci-dessus"
echo "  3. Clone le repo du projet dans ~/sartorial-agentic/"
echo "  4. Copie .env.example → .env et remplis les clés"
echo "  5. Lance : cd ~/sartorial-agentic && make ssl-init"
echo "  6. Lance : make up"
echo ""
echo -e "${PURPLE}— Votre Tailleur${NC}"
echo ""
