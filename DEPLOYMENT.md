# ═══════════════════════════════════════════════════════════
# SARTORIAL AGENTIC — Guide de Déploiement Hetzner
# Ubuntu 24.04 LTS · CPX31 · Falkenstein
# ═══════════════════════════════════════════════════════════

## 🎯 Objectif

Te guider étape par étape, de la commande du VPS Hetzner jusqu'à
ta plateforme live sur `https://sartorial-agentic.ai`.

Temps estimé : **45 minutes**.

---

## PHASE 1 — Commander le serveur Hetzner

### 1.1 Créer un compte Hetzner Cloud

1. Va sur https://console.hetzner.cloud/
2. Crée un compte (vérification email + pièce d'identité)
3. Ajoute un moyen de paiement (CB ou SEPA)

### 1.2 Créer un projet

1. Clique **New Project**
2. Nom : `sartorial-agentic`
3. Entre dans le projet

### 1.3 Générer une clé SSH

**Sur ton ordinateur** (Mac/Linux/WSL) :

```bash
# Si tu n'as pas encore de clé SSH
ssh-keygen -t ed25519 -C "david@sartorial-agentic" -f ~/.ssh/sartorial_ed25519

# Afficher la clé publique (à copier)
cat ~/.ssh/sartorial_ed25519.pub
```

Sur Hetzner Cloud :
1. **Security** → **SSH Keys** → **Add SSH Key**
2. Colle le contenu de `sartorial_ed25519.pub`
3. Nom : `david-laptop`

### 1.4 Créer le serveur

1. **Servers** → **Add Server**
2. **Location** : Falkenstein (Allemagne) — meilleur pour clients FR
3. **Image** : Ubuntu 24.04
4. **Type** : Shared vCPU → **CPX31** (4 vCPU AMD, 8 Go RAM, 160 Go NVMe)
5. **Networking** : IPv4 + IPv6
6. **SSH Keys** : coche `david-laptop`
7. **Name** : `sartorial-prod-01`
8. **Create & Buy now** (16,49€/mois)

⏱ Serveur provisionné en ~30 secondes.

### 1.5 Récupérer l'IP publique

Note l'adresse IPv4 affichée (ex: `94.130.X.X`).

---

## PHASE 2 — Configuration DNS

Chez ton registrar de domaine (OVH, Gandi, Namecheap, etc.) :

Ajoute ces enregistrements A :

```
sartorial-agentic.ai       A    <IP_HETZNER>    (TTL 3600)
www.sartorial-agentic.ai   A    <IP_HETZNER>    (TTL 3600)
```

⏱ La propagation prend 5 minutes à quelques heures. Vérifie avec :

```bash
dig +short sartorial-agentic.ai
```

Tu dois voir ton IP Hetzner.

---

## PHASE 3 — Bootstrap du serveur

### 3.1 Premier accès SSH (en root)

```bash
ssh -i ~/.ssh/sartorial_ed25519 root@<IP_HETZNER>
```

Accepte le fingerprint.

### 3.2 Uploader le script bootstrap

**Depuis ton ordinateur**, dans un nouveau terminal :

```bash
# Upload du script et de l'archive projet
scp -i ~/.ssh/sartorial_ed25519 \
    scripts/bootstrap.sh \
    scripts/deploy-init.sh \
    sartorial-agentic-stack.tar.gz \
    root@<IP_HETZNER>:/tmp/
```

### 3.3 Éditer le script bootstrap

**Sur le serveur** (connecté en SSH) :

```bash
cd /tmp
nano bootstrap.sh
```

Modifie les variables en haut du fichier :

```bash
GITHUB_SSH_KEY="ssh-ed25519 AAAA... david@sartorial-agentic"
# ↑ Ta clé publique SSH (cat ~/.ssh/sartorial_ed25519.pub)
```

Sauvegarde (`Ctrl+O`, `Enter`, `Ctrl+X`).

### 3.4 Lancer le bootstrap

```bash
sudo bash /tmp/bootstrap.sh
```

⏱ ~5 minutes. À la fin, tu verras :

```
◆ Connexion SSH :
  ssh -p 2242 sartorial@<IP_HETZNER>

◆ Mot de passe user sartorial : <PASSWORD_GÉNÉRÉ>
  ⚠  NOTE CE MOT DE PASSE DANS 1PASSWORD/BITWARDEN
```

**IMPORTANT** : sauvegarde ce mot de passe. On passe ensuite par SSH key uniquement.

### 3.5 Tester la nouvelle connexion

**Ouvre un NOUVEAU terminal** (garde l'ancien au cas où) :

```bash
ssh -p 2242 -i ~/.ssh/sartorial_ed25519 sartorial@<IP_HETZNER>
```

Si ça marche, tu peux fermer l'ancienne session root. Tu es maintenant sur le user `sartorial` sécurisé.

---

## PHASE 4 — Déploiement de la plateforme

### 4.1 Déplacer l'archive et le script deploy

```bash
sudo mv /tmp/sartorial-agentic-stack.tar.gz /tmp/
sudo cp /tmp/deploy-init.sh ~/
chmod +x ~/deploy-init.sh
```

### 4.2 Lancer le déploiement

```bash
cd ~
bash deploy-init.sh
```

Le script va :
1. Extraire le projet dans `~/sartorial-agentic/`
2. Générer les secrets (.env)
3. Te demander de compléter les clés Stripe/Anthropic/Resend
4. Builder les images Docker
5. Obtenir le certificat SSL Let's Encrypt
6. Lancer toute la stack

### 4.3 Compléter le .env

Quand le script te le demande :

```bash
nano ~/sartorial-agentic/.env
```

Remplis ces clés (tu les récupères sur leurs dashboards respectifs) :

```env
STRIPE_PUBLIC_KEY=pk_live_...
STRIPE_SECRET_KEY=sk_live_...
STRIPE_WEBHOOK_SECRET=whsec_...
ANTHROPIC_API_KEY=sk-ant-...
RESEND_API_KEY=re_...
```

Où les obtenir :
- **Stripe** : https://dashboard.stripe.com/apikeys
- **Anthropic** : https://console.anthropic.com/settings/keys
- **Resend** : https://resend.com/api-keys

Sauvegarde et reprends le script (Enter).

---

## PHASE 5 — Vérification & Go-Live

### 5.1 Vérifier les services

```bash
cd ~/sartorial-agentic
make health
```

Tu dois voir :
```
✓ Backend OK
✓ Frontend OK
✓ PostgreSQL OK
✓ Redis OK
```

### 5.2 Tester l'URL publique

Dans ton navigateur : https://sartorial-agentic.ai

Tu dois voir ta landing page avec :
- ✓ Cadenas vert (SSL actif)
- ✓ Animations fluides
- ✓ Formulaire waitlist fonctionnel

### 5.3 Configurer le webhook Stripe

Sur https://dashboard.stripe.com/webhooks :
1. **Add endpoint**
2. URL : `https://sartorial-agentic.ai/api/v1/webhooks/stripe`
3. Événements à écouter :
   - `checkout.session.completed`
   - `customer.subscription.created`
   - `customer.subscription.updated`
   - `customer.subscription.deleted`
   - `invoice.paid`
   - `invoice.payment_failed`
4. Copie le **signing secret** (whsec_...) dans `.env` :
   ```bash
   nano ~/sartorial-agentic/.env
   # Met à jour STRIPE_WEBHOOK_SECRET
   make restart
   ```

---

## 🛠 Commandes utiles au quotidien

```bash
cd ~/sartorial-agentic

make up                 # Lancer la stack
make down               # Arrêter
make restart            # Redémarrer
make logs               # Voir les logs en temps réel
make status             # État des conteneurs
make health             # Health check complet
make db-backup          # Backup PostgreSQL
make db-shell           # Shell PostgreSQL
make ssl-renew          # Renouveler SSL (auto tous les 60j)
```

---

## 🚨 En cas de problème

### Le site n'est pas accessible

```bash
make logs-backend       # Logs backend
make logs-frontend      # Logs frontend
docker compose logs nginx --tail=50
```

### Erreur SSL

```bash
# Vérifier que le DNS pointe bien vers le serveur
dig +short sartorial-agentic.ai

# Retry SSL
cd ~/sartorial-agentic
make ssl-init
```

### Connexion SSH refusée

Si jamais tu es lock out :
1. Va sur Hetzner Console
2. Ouvre la console web du serveur
3. Connecte-toi en root (mot de passe envoyé par email à la création)
4. Debug depuis là

---

## 📊 Monitoring (à configurer plus tard)

Quand tu auras du trafic, on ajoutera :
- **Uptime Kuma** (monitoring gratuit auto-hébergé)
- **Sentry** (error tracking, free tier généreux)
- **Grafana Cloud** (metrics, free tier)

---

— **Votre Tailleur**
