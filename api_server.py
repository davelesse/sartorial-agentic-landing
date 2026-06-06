#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
═══════════════════════════════════════════════════════════════
   API SERVER — LE NOYAU DIGITAL COLOSSE (FRÉQUENCE 1M%)

   Fusion de la Matrice Aurum (Agents) et de l'Infrastructure Stripe.
   L'Agent 24 (PHP) transmet les ondes de choc ici.
═══════════════════════════════════════════════════════════════
"""

import os
import json
import logging
import stripe
import requests
import subprocess
from datetime import datetime
from flask import Flask, request, jsonify, redirect
from dotenv import load_dotenv

# ═══════════════════════════════════════════════════════════════
# 1. CONFIGURATION ET CHARGEMENT DE L'ÉNERGIE (.ENV)
# ═══════════════════════════════════════════════════════════════

env_path = os.path.join(os.path.dirname(__file__), '..', '.env')
load_dotenv(env_path)

app = Flask(__name__)
app.config['JSON_AS_ASCII'] = False

# Clés Souveraines
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "CLE_INTROUVABLE")
stripe.api_key = os.getenv('STRIPE_SECRET_KEY', '')
STRIPE_WEBHOOK_SECRET = os.getenv('STRIPE_WEBHOOK_SECRET', '')
STRIPE_APPLICATION_FEE_PERCENT = float(os.getenv('STRIPE_APPLICATION_FEE_PERCENT', '1.5'))
DOMAIN = os.getenv('DOMAIN', 'https://digital-colosse.com')

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(name)s] %(message)s')
logger = logging.getLogger('NoyauColosse')

# ═══════════════════════════════════════════════════════════════
# 2. LE PONT DE BIFRÖST (CONNEXION AGENT 21)
# ═══════════════════════════════════════════════════════════════

def ordonner_creation_produit_stripe(nom_produit, prix_euros):
    """L'Agent 21 forge un produit instantanément."""
    chemin_agent_21 = "/var/www/digital-colosse.com/public_html/agents/agent21.py"
    commande = ["python3", chemin_agent_21, "--forge", str(nom_produit), str(prix_euros)]
    try:
        subprocess.Popen(commande, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except Exception as e:
        logger.error(f"ANOMALIE BIFRÖST : {e}")
        return False

# ═══════════════════════════════════════════════════════════════
# 3. LA MATRICE AURUM (LES 44 AGENTS)
# ═══════════════════════════════════════════════════════════════

AGENTS_REGISTRY = {
    "04": {"name": "Le Sismographe de Tension", "role": "Analyser les réseaux pour détecter les frustrations."},
    "06": {"name": "L'Intercepteur d'Intention", "role": "Capturer les coordonnées des prospects."},
    "01": {"name": "L'Architecte de Flux", "role": "Définir la structure web (Tom Hopkins)."},
    "10": {"name": "L'Architecte Noyau", "role": "Coder physiquement les modules."},
    "24": {"name": "Le Héraut Rouge", "role": "Alerter Charles et David. (Frontend PHP)"},
    "25": {"name": "L'Orchestrateur Symphonique", "role": "Assembler site et paiements."},
    "32": {"name": "L'Archonte de Ma'at", "role": "Bouclier juridique et conformité."},
    "37": {"name": "Le Sphinx de Ma'at", "role": "Protéger contre les hackers."},
    "38": {"name": "Garde Impériale", "role": "Gérer le SAV et la sécurité."},
    "strategie": {"name": "Le Haut Stratège", "role": "Maximiser le ROI."}
    # La liste complète a été condensée pour la clarté du Cerveau,
    # mais l'architecture peut accueillir les 44 sans friction.
}

def call_neural_engine(system_prompt, user_message):
    """Moteur Neuronal : Connexion directe à la Source (Gemini)."""
    if GEMINI_API_KEY == "CLE_INTROUVABLE":
        return "Erreur Solaire : Clé API absente du .env."
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}"
    payload = {"contents": [{"role": "user", "parts": [{"text": f"{system_prompt}\n\nORDRE : {user_message}"}]}]}
    try:
        response = requests.post(url, json=payload, headers={'Content-Type': 'application/json'}, timeout=30)
        if response.status_code == 200:
            return response.json()['candidates'][0]['content']['parts'][0]['text']
        return f"Erreur {response.status_code}."
    except Exception as e:
        return f"Erreur Noyau : {str(e)}"

@app.route('/dc-api/agent/command', methods=['POST'])
def execute_agent_command():
    data = request.json
    agent_id = data.get('agent', '01')
    message = data.get('message', '')
    source = data.get('source', 'chat')

    if source == 'terminal':
        system_prompt = "Tu es l'Architecte Noyau (10). Fréquence Solaire 1M%. Génère UNIQUEMENT du HTML/CSS pur."
        return jsonify({"status": "success", "reply": call_neural_engine(system_prompt, message)})

    agent_profile = AGENTS_REGISTRY.get(agent_id, {"name": "Oracle", "role": "Souverain"})
    system_prompt = f"Tu es {agent_profile['name']}. Mission : {agent_profile['role']}. Fréquence Solaire 1 Million %."
    return jsonify({"status": "success", "agent_name": agent_profile['name'], "reply": call_neural_engine(system_prompt, message)})

# ═══════════════════════════════════════════════════════════════
# 4. INFRASTRUCTURE FINANCIÈRE (CATALOGUE ET CHECKOUT)
# ═══════════════════════════════════════════════════════════════

_catalog = None
_mapping = None

def get_catalog():
    global _catalog
    if not _catalog:
        try:
            from product_catalog import build_catalog
            _catalog = build_catalog()
        except ImportError:
            _catalog = {}
    return _catalog

def get_price_id(product_id):
    global _mapping
    if not _mapping:
        try:
            from stripe_price_mapping import STRIPE_PRICE_MAP
            _mapping = STRIPE_PRICE_MAP
        except ImportError:
            _mapping = {}
    return _mapping.get(product_id, '')

@app.route('/dc-api/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok', 'service': 'Digital Colosse API', 'timestamp': datetime.now().isoformat()})

@app.route('/dc-api/checkout', methods=['POST'])
def create_checkout():
    """Génère la foudre financière (Lien Stripe)."""
    data = request.json or {}
    product_id = data.get('product_id', '')
    lang = data.get("lang", "fr")
    locale_map = {"fr": "fr", "en": "en", "nl": "nl", "de": "de", "es": "es"}
    stripe_locale = locale_map.get(lang, "fr")
    email = data.get('email', '')
    quantity = int(data.get('quantity', 1))
    stripe_account = data.get('stripe_account', '')  # Stripe Connect (optionnel)

    if not product_id:
        return jsonify({'error': 'product_id requis'}), 400

    price_id = get_price_id(product_id)
    if not price_id:
        return jsonify({'error': f'Prix Stripe non configuré'}), 500

    catalog = get_catalog()
    product = catalog.get(product_id)
    if not product:
        return jsonify({'error': 'Produit inconnu'}), 404

    mode = 'subscription' if product.price_type == 'recurring' else 'payment'

    session_params = {
        'locale': stripe_locale,
        'line_items': [{'price': price_id, 'quantity': quantity}],
        'mode': mode,
        'metadata': {'product_id': product_id, 'source': 'digital-colosse'},
        'success_url': f'{DOMAIN}/merci?session_id={{CHECKOUT_SESSION_ID}}',
        'cancel_url': f'{DOMAIN}/annule',
    }
    if email:
        session_params['customer_email'] = email

    # Metadata aussi portée par l'abonnement (pour les récurrents)
    if mode == 'subscription':
        session_params['subscription_data'] = {
            'metadata': {'product_id': product_id, 'source': 'digital-colosse'}
        }

    # ── Stripe Connect : paiement sur le compte du tenant + commission ──
    stripe_options = {}
    if stripe_account:
        stripe_options['stripe_account'] = stripe_account
        amount_cents = int(product.price * 100 * quantity)
        fee_cents = int(amount_cents * STRIPE_APPLICATION_FEE_PERCENT / 100)
        if mode == 'payment':
            session_params['payment_intent_data'] = {'application_fee_amount': fee_cents}
        elif mode == 'subscription':
            session_params['subscription_data']['application_fee_percent'] = STRIPE_APPLICATION_FEE_PERCENT

    try:
        session = stripe.checkout.Session.create(**session_params, **stripe_options)
        logger.info(f"✅ Checkout créé : {product_id} → {session.id}")
        return jsonify({'url': session.url, 'session_id': session.id})
    except stripe.error.StripeError as e:
        return jsonify({'error': str(e)}), 500

# ═══════════════════════════════════════════════════════════════
# 4bis. EMAILS TRANSACTIONNELS BRANDÉS (Oracle / Facture / Échec)
#       Modules : email_templates.py (rendu) + invoice_generator.py (facture PDF)
# ═══════════════════════════════════════════════════════════════

def _send_html_email(to_email, subject, html):
    """Envoi SMTP générique d'un email HTML brandé (welcome, payment_failed…).
    Les factures passent par invoice_generator.send_invoice_email (PDF joint)."""
    import smtplib
    import ssl
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText

    smtp_host = os.getenv("SMTP_HOST", "")
    smtp_port = int(os.getenv("SMTP_PORT", 587))
    smtp_user = os.getenv("SMTP_USER", "")
    smtp_password = os.getenv("SMTP_PASSWORD", "")
    from_email = os.getenv("FROM_EMAIL", os.getenv("EMAIL_FROM", smtp_user))

    if not all([smtp_host, smtp_user, smtp_password]):
        logger.warning("✉️ SMTP non configuré — email ignoré.")
        return False
    if not to_email:
        logger.warning("✉️ Aucun destinataire — email ignoré.")
        return False

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"Digital Colosse <{from_email}>"
        msg["To"] = to_email
        msg.attach(MIMEText(html, "html", "utf-8"))

        if smtp_port == 465:
            with smtplib.SMTP_SSL(smtp_host, smtp_port,
                                   context=ssl.create_default_context()) as s:
                s.login(smtp_user, smtp_password)
                s.sendmail(from_email, to_email, msg.as_string())
        else:
            with smtplib.SMTP(smtp_host, smtp_port) as s:
                s.ehlo(); s.starttls()
                s.login(smtp_user, smtp_password)
                s.sendmail(from_email, to_email, msg.as_string())

        logger.info(f"✉️ Email envoyé → {to_email} ({subject})")
        return True
    except Exception as e:
        logger.error(f"❌ Erreur SMTP : {e}")
        return False


def dispatch_transactional_email(event_type, obj):
    """Déclenche l'email brandé adapté à l'événement Stripe.
    Tolérant aux pannes : si un module/SMTP manque, on log et on continue."""
    try:
        from email_templates import email_engine
    except ImportError:
        logger.info("ℹ️ Module email_templates absent — emails désactivés.")
        return

    # ── Extraction des infos client (Checkout Session ou Invoice) ──
    details = obj.get('customer_details', {}) or {}
    to_email = obj.get('customer_email') or details.get('email') or ''
    customer_name = details.get('name') or obj.get('customer_name') or 'Client'
    metadata = obj.get('metadata', {}) or {}
    product_id = metadata.get('product_id', '')
    tenant_id = metadata.get('tenant_id', 'default')

    currency = (obj.get('currency') or 'eur').upper()
    amount_cents = obj.get('amount_total')
    if amount_cents is None:
        amount_cents = obj.get('amount_paid', 0)
    amount = (amount_cents or 0) / 100.0
    sym = "€" if currency == "EUR" else ("$" if currency == "USD" else currency)

    # Libellé du plan via le catalogue (sinon product_id, sinon défaut)
    catalog = get_catalog()
    product = catalog.get(product_id) if product_id else None
    plan_label = (getattr(product, 'name', None) or product_id or 'ESSENCE')

    try:
        if event_type == 'checkout.session.completed':
            # 1) Email de bienvenue (Oracle + Agents Aurum)
            subject, html = email_engine.render(
                'welcome_oracle', tenant_id,
                customer_name=customer_name, plan_label=plan_label,
            )
            _send_html_email(to_email, subject, html)

            # 2) Facture PDF (gère son propre rendu + SMTP)
            try:
                from invoice_generator import send_invoice_email
                send_invoice_email(
                    to_email=to_email, customer_name=customer_name,
                    plan_name=plan_label, amount=amount,
                    tenant_id=tenant_id, currency=currency,
                )
            except ImportError:
                logger.info("ℹ️ invoice_generator absent — facture non envoyée.")

        elif event_type in ('invoice.payment_failed',
                            'invoice.payment_action_required'):
            subject, html = email_engine.render(
                'payment_failed', tenant_id,
                customer_name=customer_name, plan_label=plan_label,
                amount=f"{amount:.2f} {sym}",
            )
            _send_html_email(to_email, subject, html)
    except Exception as e:
        logger.error(f"❌ Erreur dispatch email ({event_type}) : {e}")

# ═══════════════════════════════════════════════════════════════
# 5. LE POINT D'IMPACT WEBHOOK (CURL DEPUIS L'AGENT 24 PHP)
# ═══════════════════════════════════════════════════════════════

@app.route('/dc-api/webhooks/stripe', methods=['POST'])
def stripe_webhook():
    """Reçoit le flux de l'Agent 24 (PHP) et le confie au Webhook Agent.

    L'Agent (WebhookHandlerAgent) gère LUI-MÊME : vérification de la signature
    (secret du tenant), parsing, dispatch vers les handlers _on_* et l'envoi
    des emails (EmailSender). On lui passe donc le payload BRUT (bytes) et on
    relaie son tuple de retour (code_http, corps).
    """
    payload = request.get_data()  # bytes bruts — requis pour la vérif HMAC
    sig_header = request.headers.get('Stripe-Signature', '')
    # Slug du tenant : par défaut le tenant souverain 'digital-colosse'
    tenant_slug = request.headers.get('X-Tenant-Slug', 'digital-colosse')

    # ── Voie normale : délégation au Webhook Agent ──
    try:
        from webhook_handler_agent import webhook_agent
    except ImportError:
        webhook_agent = None

    if webhook_agent is not None:
        try:
            status, body = webhook_agent.handle_webhook(payload, sig_header, tenant_slug)
            logger.info(f"✅ Webhook Agent → {status}")
            return jsonify(body), status
        except Exception as e:
            logger.error(f"❌ Webhook Agent en échec : {e}")
            return jsonify({'error': 'Erreur interne webhook'}), 500

    # ── Secours natif (Agent absent) : vérif + emails brandés de repli ──
    logger.info("ℹ️ Webhook Agent non connecté. Traitement natif de secours.")
    payload_text = payload.decode('utf-8', errors='replace')
    if STRIPE_WEBHOOK_SECRET:
        try:
            event = stripe.Webhook.construct_event(payload_text, sig_header, STRIPE_WEBHOOK_SECRET)
        except Exception as e:
            logger.error(f"❌ Webhook rejeté : {e}")
            return jsonify({'error': 'Signature invalide'}), 400
    else:
        try:
            event = json.loads(payload_text)
        except Exception:
            return jsonify({'error': 'JSON invalide'}), 400

    event_type = event.get('type', '')
    event_data = event.get('data', {}).get('object', {})
    logger.info(f"📨 (secours natif) Onde de choc : {event_type}")
    dispatch_transactional_email(event_type, event_data)

    return jsonify({'status': 'ok'}), 200

# ═══════════════════════════════════════════════════════════════
# DÉMARRAGE DU CŒUR
# ═══════════════════════════════════════════════════════════════

if __name__ == '__main__':
    logger.info("🚀 DIGITAL COLOSSE - NOYAU SOUVERAIN ACTIVÉ")
    app.run(host='0.0.0.0', port=5000, debug=False)
