#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
╔════════════════════════════════════════════════════════════════════════╗
║  WEBHOOK HANDLER AGENT — Version Agentique                           ║
║                                                                       ║
║  Agent autonome qui:                                                  ║
║  ✅ Reçoit et valide les webhooks Stripe (signature HMAC)            ║
║  ✅ Crée/met à jour contacts dans EspoCRM                            ║
║  ✅ Crée des opportunités (commandes)                                ║
║  ✅ Envoie des emails de confirmation                                ║
║  ✅ Self-healing: retry automatique en cas d'échec                   ║
║  ✅ Multi-tenant: gère N clients avec leurs propres configs          ║
║  ✅ Observabilité: métriques, logs structurés, alertes               ║
║  ✅ File d'attente interne pour les événements en échec              ║
║                                                                       ║
║  Remplace: stripe_to_espocrm_webhook.py + webhook_handler_cron.py   ║
║  Appelé par: api_server.py (route /api/webhooks/stripe)              ║
║                                                                       ║
║  Digital Colosse — Mars 2026                                         ║
╚════════════════════════════════════════════════════════════════════════╝
"""

import os
import json
import time
import hmac
import hashlib
import logging
import smtplib
import threading
import requests
from datetime import datetime, timedelta
from typing import Dict, Tuple, Optional, List
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dataclasses import dataclass, field
from enum import Enum

# ============================================================================
# CONFIGURATION & LOGGING
# ============================================================================

LOG_DIR = os.getenv('LOG_DIR', '/var/log/digital-colosse')
os.makedirs(LOG_DIR, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f'{LOG_DIR}/webhook_agent.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('WebhookHandlerAgent')


class EventType(Enum):
    """Types d'événements Stripe gérés"""
    PAYMENT_SUCCEEDED = 'payment_intent.succeeded'
    PAYMENT_FAILED = 'payment_intent.payment_failed'
    PAYMENT_CANCELED = 'payment_intent.canceled'
    CHECKOUT_COMPLETED = 'checkout.session.completed'
    INVOICE_PAID = 'invoice.paid'
    INVOICE_FAILED = 'invoice.payment_failed'
    SUBSCRIPTION_CREATED = 'customer.subscription.created'
    SUBSCRIPTION_DELETED = 'customer.subscription.deleted'
    DISPUTE_CREATED = 'charge.dispute.created'
    CHARGE_REFUNDED = 'charge.refunded'


@dataclass
class TenantConfig:
    """Configuration d'un tenant (toi ou un de tes clients SaaS)"""
    tenant_id: str
    name: str
    # Stripe
    stripe_webhook_secret: str
    # EspoCRM
    espocrm_url: str
    espocrm_api_key: str
    # Email
    smtp_host: str = 'smtp.hostinger.com'
    smtp_port: int = 587
    smtp_user: str = ''
    smtp_password: str = ''
    from_email: str = ''
    # État
    active: bool = True


@dataclass
class AgentMetrics:
    """Métriques de l'agent — observabilité complète"""
    events_received: int = 0
    events_processed: int = 0
    events_failed: int = 0
    events_retried: int = 0
    contacts_created: int = 0
    contacts_updated: int = 0
    opportunities_created: int = 0
    emails_sent: int = 0
    emails_failed: int = 0
    signature_failures: int = 0
    last_event_at: Optional[str] = None
    last_error: Optional[str] = None
    started_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict:
        return {
            'events_received': self.events_received,
            'events_processed': self.events_processed,
            'events_failed': self.events_failed,
            'events_retried': self.events_retried,
            'contacts_created': self.contacts_created,
            'contacts_updated': self.contacts_updated,
            'opportunities_created': self.opportunities_created,
            'emails_sent': self.emails_sent,
            'emails_failed': self.emails_failed,
            'signature_failures': self.signature_failures,
            'last_event_at': self.last_event_at,
            'last_error': self.last_error,
            'started_at': self.started_at,
            'success_rate': (
                f"{(self.events_processed / self.events_received * 100):.1f}%"
                if self.events_received > 0 else 'N/A'
            )
        }


# ============================================================================
# ESPOCRM CLIENT — Interaction bi-directionnelle avec le CRM
# ============================================================================

class EspoCRMClient:
    """
    Client EspoCRM agentique.
    Gère les contacts et opportunités avec retry automatique.
    """

    def __init__(self, url: str, api_key: str):
        self.url = url.rstrip('/')
        self.headers = {
            'X-Api-Key': api_key,
            'X-Requested-With': 'XMLHttpRequest',
            'Content-Type': 'application/json'
        }
        self.max_retries = 3
        self.retry_delay = 2  # secondes

    def _request(self, method: str, endpoint: str, data: dict = None) -> Optional[dict]:
        """Requête HTTP avec retry automatique"""
        url = f"{self.url}/api/v1/{endpoint}"

        for attempt in range(1, self.max_retries + 1):
            try:
                if method == 'GET':
                    resp = requests.get(url, headers=self.headers, timeout=15)
                elif method == 'POST':
                    resp = requests.post(url, json=data, headers=self.headers, timeout=15)
                elif method == 'PUT':
                    resp = requests.put(url, json=data, headers=self.headers, timeout=15)
                else:
                    return None

                if resp.status_code in (200, 201):
                    return resp.json()
                elif resp.status_code == 409:
                    logger.warning(f"Conflit EspoCRM sur {endpoint}, donnée existante")
                    return None
                else:
                    logger.warning(
                        f"EspoCRM {method} {endpoint} → {resp.status_code} "
                        f"(tentative {attempt}/{self.max_retries})"
                    )

            except requests.exceptions.Timeout:
                logger.warning(f"Timeout EspoCRM (tentative {attempt}/{self.max_retries})")
            except requests.exceptions.ConnectionError:
                logger.error(f"EspoCRM injoignable (tentative {attempt}/{self.max_retries})")
            except Exception as e:
                logger.error(f"Erreur EspoCRM inattendue: {e}")
                return None

            if attempt < self.max_retries:
                time.sleep(self.retry_delay * attempt)

        logger.error(f"EspoCRM {method} {endpoint} — échec après {self.max_retries} tentatives")
        return None

    def find_contact_by_email(self, email: str) -> Optional[dict]:
        """Cherche un contact par email"""
        endpoint = (
            f"Contact?where[0][type]=equals"
            f"&where[0][attribute]=emailAddress"
            f"&where[0][value]={email}"
        )
        result = self._request('GET', endpoint)
        if result and result.get('list'):
            return result['list'][0]
        return None

    def create_contact(self, first_name: str, last_name: str,
                       email: str, phone: str = None,
                       extra_fields: dict = None) -> Optional[str]:
        """Crée un contact et retourne son ID"""
        data = {
            'firstName': first_name,
            'lastName': last_name,
            'emailAddress': email,
        }
        if phone:
            data['phoneNumber'] = phone
        if extra_fields:
            data.update(extra_fields)

        result = self._request('POST', 'Contact', data)
        if result:
            logger.info(f"✅ Contact créé: {first_name} {last_name} ({email})")
            return result.get('id')
        return None

    def update_contact(self, contact_id: str, data: dict) -> bool:
        """Met à jour un contact existant"""
        result = self._request('PUT', f'Contact/{contact_id}', data)
        if result:
            logger.info(f"✅ Contact mis à jour: {contact_id}")
            return True
        return False

    def create_or_update_contact(self, email: str, first_name: str,
                                  last_name: str, phone: str = None,
                                  extra_fields: dict = None) -> Optional[str]:
        """Crée ou met à jour un contact — logique idempotente"""
        existing = self.find_contact_by_email(email)

        if existing:
            contact_id = existing['id']
            update_data = {'firstName': first_name, 'lastName': last_name}
            if phone:
                update_data['phoneNumber'] = phone
            if extra_fields:
                update_data.update(extra_fields)
            self.update_contact(contact_id, update_data)
            return contact_id
        else:
            return self.create_contact(first_name, last_name, email, phone, extra_fields)

    def create_opportunity(self, contact_id: str, amount: float,
                           name: str, stage: str = 'Closed Won',
                           extra_fields: dict = None) -> Optional[str]:
        """Crée une opportunité liée à un contact"""
        data = {
            'name': name,
            'contactId': contact_id,
            'amount': amount,
            'amountCurrency': 'EUR',
            'stage': stage,
            'probability': 100,
            'closeDate': datetime.now().strftime('%Y-%m-%d'),
        }
        if extra_fields:
            data.update(extra_fields)

        result = self._request('POST', 'Opportunity', data)
        if result:
            logger.info(f"✅ Opportunité créée: {name} ({amount}€)")
            return result.get('id')
        return None


# ============================================================================
# EMAIL SENDER — Envoi d'emails transactionnels
# ============================================================================

class EmailSender:
    """Envoi d'emails avec retry et templates"""

    def __init__(self, smtp_host: str, smtp_port: int,
                 smtp_user: str, smtp_password: str, from_email: str):
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.smtp_user = smtp_user
        self.smtp_password = smtp_password
        self.from_email = from_email

    def send(self, to_email: str, subject: str, body_html: str) -> bool:
        """Envoie un email avec retry"""
        for attempt in range(1, 4):
            try:
                msg = MIMEMultipart('alternative')
                msg['From'] = self.from_email
                msg['To'] = to_email
                msg['Subject'] = subject
                msg.attach(MIMEText(body_html, 'html', 'utf-8'))

                with smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=15) as server:
                    server.starttls()
                    server.login(self.smtp_user, self.smtp_password)
                    server.send_message(msg)

                logger.info(f"✅ Email envoyé à {to_email}")
                return True

            except Exception as e:
                logger.warning(f"Email échec tentative {attempt}/3: {e}")
                if attempt < 3:
                    time.sleep(2 * attempt)

        logger.error(f"❌ Email non envoyé à {to_email} après 3 tentatives")
        return False

    def send_order_confirmation(self, to_email: str, customer_name: str,
                                 amount: float, order_id: str,
                                 brand_name: str = "Digital Colosse") -> bool:
        """Email de confirmation de commande"""
        subject = f"Commande confirmée — {brand_name}"
        body = f"""
        <html>
        <body style="font-family: Arial, sans-serif; color: #333; max-width: 600px;">
            <div style="background: #0a0a0a; color: #D4AF37; padding: 20px; text-align: center;">
                <h1>{brand_name}</h1>
            </div>
            <div style="padding: 30px;">
                <h2>Merci {customer_name} !</h2>
                <p>Votre commande a bien été confirmée.</p>
                <table style="width: 100%; border-collapse: collapse; margin: 20px 0;">
                    <tr style="background: #f5f5f5;">
                        <td style="padding: 10px; border: 1px solid #ddd;"><strong>Référence</strong></td>
                        <td style="padding: 10px; border: 1px solid #ddd;">{order_id}</td>
                    </tr>
                    <tr>
                        <td style="padding: 10px; border: 1px solid #ddd;"><strong>Montant</strong></td>
                        <td style="padding: 10px; border: 1px solid #ddd;">{amount:.2f} €</td>
                    </tr>
                    <tr style="background: #f5f5f5;">
                        <td style="padding: 10px; border: 1px solid #ddd;"><strong>Date</strong></td>
                        <td style="padding: 10px; border: 1px solid #ddd;">{datetime.now().strftime('%d/%m/%Y %H:%M')}</td>
                    </tr>
                </table>
                <p>Nous vous recontacterons très bientôt.</p>
                <p>Cordialement,<br><strong>{brand_name}</strong></p>
            </div>
        </body>
        </html>
        """
        return self.send(to_email, subject, body)

    def send_payment_failed_notice(self, to_email: str, customer_name: str,
                                    brand_name: str = "Digital Colosse") -> bool:
        """Email de notification d'échec de paiement"""
        subject = f"Problème avec votre paiement — {brand_name}"
        body = f"""
        <html>
        <body style="font-family: Arial, sans-serif; color: #333; max-width: 600px;">
            <div style="padding: 30px;">
                <h2>Bonjour {customer_name},</h2>
                <p>Nous n'avons pas pu traiter votre paiement.</p>
                <p>Veuillez vérifier vos informations de paiement et réessayer.</p>
                <p>Si le problème persiste, contactez-nous.</p>
                <p>Cordialement,<br><strong>{brand_name}</strong></p>
            </div>
        </body>
        </html>
        """
        return self.send(to_email, subject, body)


# ============================================================================
# RETRY QUEUE — File d'attente pour événements en échec
# ============================================================================

class RetryQueue:
    """
    File d'attente en mémoire pour les événements en échec.
    L'agent retente automatiquement les événements échoués.
    """

    def __init__(self, max_retries: int = 5, base_delay: int = 60):
        self.queue: List[dict] = []
        self.max_retries = max_retries
        self.base_delay = base_delay  # secondes entre les retries
        self._lock = threading.Lock()

    def add(self, event: dict, tenant_id: str, error: str):
        """Ajoute un événement en échec à la file"""
        with self._lock:
            entry = {
                'event': event,
                'tenant_id': tenant_id,
                'error': error,
                'attempts': 1,
                'first_failed_at': datetime.now().isoformat(),
                'next_retry_at': (
                    datetime.now() + timedelta(seconds=self.base_delay)
                ).isoformat(),
            }
            self.queue.append(entry)
            logger.warning(
                f"🔄 Événement ajouté à la retry queue: "
                f"{event.get('type')} (tenant: {tenant_id})"
            )

    def get_ready(self) -> List[dict]:
        """Retourne les événements prêts à être retentés"""
        now = datetime.now()
        ready = []
        with self._lock:
            for entry in self.queue:
                retry_at = datetime.fromisoformat(entry['next_retry_at'])
                if now >= retry_at and entry['attempts'] < self.max_retries:
                    ready.append(entry)
        return ready

    def mark_success(self, entry: dict):
        """Retire un événement traité avec succès"""
        with self._lock:
            if entry in self.queue:
                self.queue.remove(entry)
                logger.info("✅ Événement retiré de la retry queue (succès)")

    def mark_retry(self, entry: dict, error: str):
        """Incrémente le compteur de retry"""
        with self._lock:
            entry['attempts'] += 1
            entry['error'] = error
            delay = self.base_delay * (2 ** entry['attempts'])  # backoff exponentiel
            entry['next_retry_at'] = (
                datetime.now() + timedelta(seconds=delay)
            ).isoformat()
            logger.warning(
                f"🔄 Retry {entry['attempts']}/{self.max_retries} "
                f"dans {delay}s — {error}"
            )

    def remove_dead(self) -> List[dict]:
        """Retire les événements qui ont dépassé le max de retries"""
        dead = []
        with self._lock:
            for entry in list(self.queue):
                if entry['attempts'] >= self.max_retries:
                    self.queue.remove(entry)
                    dead.append(entry)
                    logger.error(
                        f"💀 Événement abandonné après {self.max_retries} tentatives: "
                        f"{entry['event'].get('type')}"
                    )
        return dead

    @property
    def size(self) -> int:
        return len(self.queue)


# ============================================================================
# WEBHOOK HANDLER AGENT — Le cœur agentique
# ============================================================================



# ============================================================
# SMTP — Email de bienvenue Oracle + Agents Aurum
# Utilise email_engine.render('welcome_oracle', ...)
# ============================================================
import smtplib, os
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

_PLAN_DB = {
    'niveau essence':   {'label': 'ESSENCE',   'members': '1 Bras Actif',             'next': 'ÉTHER'},
    'niveau éther':     {'label': 'ÉTHER',     'members': '2 Bras Actifs',            'next': 'PARADISE'},
    'niveau paradise':  {'label': 'PARADISE',  'members': '2 Bras + 1 Jambe',         'next': 'SOUVERAIN'},
    'niveau souverain': {'label': 'SOUVERAIN', 'members': 'Déploiement Total + Auto',  'next': None},
}

def send_welcome_email(to_email: str, customer_name: str,
                       espocrm_url: str = '', temp_password: str = '',
                       plan_name: str = '', tenant_id: str = 'default') -> bool:
    smtp_host     = os.getenv('SMTP_HOST', '')
    smtp_port     = int(os.getenv('SMTP_PORT', 587))
    smtp_user     = os.getenv('SMTP_USER', '')
    smtp_password = os.getenv('SMTP_PASSWORD', '')
    from_email    = os.getenv('FROM_EMAIL', os.getenv('EMAIL_FROM', smtp_user))

    if not all([smtp_host, smtp_user, smtp_password]):
        logger.warning("⚠️  SMTP non configuré — email ignoré")
        return False

    plan = _PLAN_DB.get(plan_name.lower().strip(),
           {'label': plan_name.upper() or 'ESSENCE', 'members': '', 'next': None})

    try:
        from email_templates import email_engine
        subject, html = email_engine.render(
            'welcome_oracle', tenant_id,
            customer_name=customer_name,
            plan_label=plan['label'],
            plan_members=plan['members'],
            next_level=plan['next'] or '',
        )
    except Exception as e:
        logger.error(f"❌ Erreur rendu template : {e}")
        return False

    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From']    = f"Digital Colosse — L'Oracle <{from_email}>"
        msg['To']      = to_email
        msg.attach(MIMEText(html, 'html', 'utf-8'))

        if smtp_port == 465:
            import ssl
            with smtplib.SMTP_SSL(smtp_host, smtp_port, context=ssl.create_default_context()) as s:
                s.login(smtp_user, smtp_password)
                s.sendmail(from_email, to_email, msg.as_string())
        else:
            with smtplib.SMTP(smtp_host, smtp_port) as s:
                s.ehlo(); s.starttls()
                s.login(smtp_user, smtp_password)
                s.sendmail(from_email, to_email, msg.as_string())

        logger.info(f"✉️  Email Oracle → {to_email} [{plan['label']}]")
        return True

    except Exception as e:
        logger.error(f"❌ Erreur SMTP : {e}")
        return False



class WebhookHandlerAgent:
    """
    Agent agentique principal.

    Responsabilités:
    - Réception et validation des webhooks Stripe
    - Traitement intelligent selon le type d'événement
    - Création/MAJ contacts et opportunités dans EspoCRM
    - Envoi d'emails transactionnels
    - Self-healing via retry queue
    - Observabilité via métriques
    - Multi-tenant: un agent, N clients

    Intégration:
    - Appelé par api_server.py sur POST /api/webhooks/stripe/<tenant_slug>
    - Ou sur POST /api/webhooks/stripe (tenant par défaut = toi)
    """

    def __init__(self):
        self.name = "WebhookHandlerAgent"
        self.tenants: Dict[str, TenantConfig] = {}
        self.espo_clients: Dict[str, EspoCRMClient] = {}
        self.email_senders: Dict[str, EmailSender] = {}
        self.metrics = AgentMetrics()
        self.retry_queue = RetryQueue(max_retries=5, base_delay=60)
        self._retry_thread = None
        self._running = False

        logger.info(f"🤖 {self.name} initialisé")

    # ────────────────────────────────────────────
    # GESTION DES TENANTS
    # ────────────────────────────────────────────

    def register_tenant(self, config: TenantConfig):
        """Enregistre un nouveau tenant (client SaaS)"""
        self.tenants[config.tenant_id] = config

        # Initialiser le client EspoCRM pour ce tenant
        self.espo_clients[config.tenant_id] = EspoCRMClient(
            url=config.espocrm_url,
            api_key=config.espocrm_api_key
        )

        # Initialiser l'email sender si configuré
        if config.smtp_user and config.smtp_password:
            self.email_senders[config.tenant_id] = EmailSender(
                smtp_host=config.smtp_host,
                smtp_port=config.smtp_port,
                smtp_user=config.smtp_user,
                smtp_password=config.smtp_password,
                from_email=config.from_email or config.smtp_user
            )

        logger.info(f"✅ Tenant enregistré: {config.name} ({config.tenant_id})")

    def register_default_tenant(self):
        """
        Enregistre Digital Colosse comme tenant par défaut.
        Lit la config depuis les variables d'environnement.
        """
        config = TenantConfig(
            tenant_id='digital-colosse',
            name='Digital Colosse',
            stripe_webhook_secret=os.getenv('STRIPE_WEBHOOK_SECRET', ''),
            espocrm_url=os.getenv('ESPOCRM_URL') or os.getenv('ESPO_URL', 'https://digital-colosse.com/crm'),
            espocrm_api_key=os.getenv('ESPOCRM_API_KEY') or os.getenv('ESPO_API_KEY', ''),
            smtp_host=os.getenv('SMTP_HOST', 'smtp.hostinger.com'),
            smtp_port=int(os.getenv('SMTP_PORT', '587')),
            smtp_user=os.getenv('SMTP_USER', ''),
            smtp_password=os.getenv('SMTP_PASSWORD', ''),
            from_email=os.getenv('FROM_EMAIL', 'ventes@digital-colosse.com'),
        )
        self.register_tenant(config)
        return config

    # ────────────────────────────────────────────
    # VALIDATION SIGNATURE STRIPE
    # ────────────────────────────────────────────

    def _verify_signature(self, payload: bytes, sig_header: str,
                          webhook_secret: str) -> bool:
        """
        Vérifie la signature Stripe (méthode officielle).
        Stripe envoie un header Stripe-Signature avec format:
        t=timestamp,v1=signature
        """
        try:
            if not sig_header or 't=' not in sig_header:
                logger.error("Header Stripe-Signature absent ou invalide")
                return False

            # Parser le header
            elements = {}
            for item in sig_header.split(','):
                key, value = item.split('=', 1)
                elements[key.strip()] = value.strip()

            timestamp = elements.get('t', '')
            signature = elements.get('v1', '')

            if not timestamp or not signature:
                logger.error("Timestamp ou signature manquant")
                return False

            # Vérifier que le timestamp n'est pas trop vieux (5 min max)
            event_time = int(timestamp)
            current_time = int(time.time())
            if abs(current_time - event_time) > 300:
                logger.warning("Webhook trop ancien (>5 min) — possible replay attack")
                return False

            # Calculer la signature attendue
            signed_payload = f"{timestamp}.{payload.decode('utf-8')}"
            expected_sig = hmac.new(
                webhook_secret.encode('utf-8'),
                signed_payload.encode('utf-8'),
                hashlib.sha256
            ).hexdigest()

            is_valid = hmac.compare_digest(expected_sig, signature)

            if not is_valid:
                logger.warning("❌ Signature Stripe invalide")
                self.metrics.signature_failures += 1

            return is_valid

        except Exception as e:
            logger.error(f"Erreur vérification signature: {e}")
            self.metrics.signature_failures += 1
            return False

    # ────────────────────────────────────────────
    # POINT D'ENTRÉE PRINCIPAL — appelé par api_server.py
    # ────────────────────────────────────────────

    def handle_webhook(self, payload: bytes, sig_header: str,
                       tenant_id: str = 'digital-colosse') -> Tuple[int, dict]:
        """
        Point d'entrée principal — appelé par api_server.py.

        Usage dans api_server.py:
            @app.route('/api/webhooks/stripe', methods=['POST'])
            def stripe_webhook():
                status, response = webhook_agent.handle_webhook(
                    payload=request.data,
                    sig_header=request.headers.get('Stripe-Signature', ''),
                    tenant_id='digital-colosse'
                )
                return jsonify(response), status

            @app.route('/api/webhooks/stripe/<tenant_slug>', methods=['POST'])
            def stripe_webhook_tenant(tenant_slug):
                status, response = webhook_agent.handle_webhook(
                    payload=request.data,
                    sig_header=request.headers.get('Stripe-Signature', ''),
                    tenant_id=tenant_slug
                )
                return jsonify(response), status
        """
        self.metrics.events_received += 1
        self.metrics.last_event_at = datetime.now().isoformat()

        # Vérifier que le tenant existe
        tenant = self.tenants.get(tenant_id)
        if not tenant:
            logger.error(f"Tenant inconnu: {tenant_id}")
            return 404, {'error': f'Tenant inconnu: {tenant_id}'}

        if not tenant.active:
            logger.warning(f"Tenant désactivé: {tenant_id}")
            return 403, {'error': 'Tenant désactivé'}

        # Vérifier la signature Stripe
        if not self._verify_signature(payload, sig_header, tenant.stripe_webhook_secret):
            return 401, {'error': 'Signature invalide'}

        # Parser l'événement
        try:
            event = json.loads(payload)
        except json.JSONDecodeError:
            logger.error("Payload JSON invalide")
            return 400, {'error': 'JSON invalide'}

        event_type = event.get('type', 'unknown')
        event_id = event.get('id', 'unknown')
        logger.info(f"📨 Événement reçu: {event_type} (id: {event_id}, tenant: {tenant_id})")

        # Traiter l'événement
        success, message = self._process_event(event, tenant_id)

        if success:
            self.metrics.events_processed += 1
            logger.info(f"✅ {event_type} traité avec succès: {message}")
            return 200, {
                'success': True,
                'event_type': event_type,
                'message': message
            }
        else:
            self.metrics.events_failed += 1
            self.metrics.last_error = message
            # Ajouter à la retry queue
            self.retry_queue.add(event, tenant_id, message)
            logger.error(f"❌ {event_type} en échec: {message}")
            # On retourne 200 à Stripe quand même pour éviter les re-envois
            # L'agent gère ses propres retries via la queue
            return 200, {
                'success': False,
                'event_type': event_type,
                'message': 'Reçu — traitement en retry',
                'queued': True
            }

    # ────────────────────────────────────────────
    # TRAITEMENT DES ÉVÉNEMENTS
    # ────────────────────────────────────────────

    def _process_event(self, event: dict,
                       tenant_id: str) -> Tuple[bool, str]:
        """Dispatch l'événement vers le bon handler"""
        event_type = event.get('type')

        handlers = {
            EventType.PAYMENT_SUCCEEDED.value: self._on_payment_succeeded,
            EventType.PAYMENT_FAILED.value: self._on_payment_failed,
            EventType.PAYMENT_CANCELED.value: self._on_payment_canceled,
            EventType.CHECKOUT_COMPLETED.value: self._on_checkout_completed,
            EventType.INVOICE_PAID.value: self._on_invoice_paid,
            EventType.INVOICE_FAILED.value: self._on_invoice_failed,
            EventType.SUBSCRIPTION_CREATED.value: self._on_subscription_created,
            EventType.SUBSCRIPTION_DELETED.value: self._on_subscription_deleted,
            EventType.DISPUTE_CREATED.value: self._on_dispute_created,
            EventType.CHARGE_REFUNDED.value: self._on_charge_refunded,
        }

        handler = handlers.get(event_type)
        if handler:
            return handler(event, tenant_id)
        else:
            logger.info(f"Événement non géré: {event_type} — ignoré")
            return True, f"Événement {event_type} ignoré (non géré)"

    def _extract_customer_data(self, stripe_object: dict) -> dict:
        """Extrait les données client d'un objet Stripe"""
        billing = stripe_object.get('billing_details', {})
        customer_details = stripe_object.get('customer_details', {})
        metadata = stripe_object.get('metadata', {})

        email = (
            stripe_object.get('receipt_email')
            or billing.get('email')
            or customer_details.get('email')
            or metadata.get('email')
        )

        name = (
            billing.get('name')
            or customer_details.get('name')
            or metadata.get('name')
            or 'Client'
        )

        phone = (
            billing.get('phone')
            or customer_details.get('phone')
        )

        name_parts = name.split(' ', 1)
        first_name = name_parts[0]
        last_name = name_parts[1] if len(name_parts) > 1 else ''

        return {
            'email': email,
            'first_name': first_name,
            'last_name': last_name,
            'phone': phone,
            'metadata': metadata,
        }

    # ── Handlers par type d'événement ──

    def _on_payment_succeeded(self, event: dict,
                               tenant_id: str) -> Tuple[bool, str]:
        """Paiement réussi → contact + opportunité + email"""
        obj = event['data']['object']
        customer = self._extract_customer_data(obj)
        amount = obj.get('amount', 0) / 100
        payment_id = obj.get('id', 'unknown')

        if not customer['email']:
            return False, "Pas d'email client dans l'événement"

        espo = self.espo_clients.get(tenant_id)
        if not espo:
            return False, f"Pas de client EspoCRM pour le tenant {tenant_id}"

        # 1. Créer/MAJ contact
        contact_id = espo.create_or_update_contact(
            email=customer['email'],
            first_name=customer['first_name'],
            last_name=customer['last_name'],
            phone=customer['phone'],
            extra_fields=customer.get('metadata')
        )

        if not contact_id:
            return False, "Échec création/MAJ contact EspoCRM"

        if customer.get('_was_created', True):
            self.metrics.contacts_created += 1
        else:
            self.metrics.contacts_updated += 1

        # 2. Créer opportunité
        opp_id = espo.create_opportunity(
            contact_id=contact_id,
            amount=amount,
            name=f"Paiement {payment_id[-8:]} — {amount}€",
            stage='Closed Won'
        )

        if opp_id:
            self.metrics.opportunities_created += 1

        # 3. Envoyer email de confirmation
        email_sender = self.email_senders.get(tenant_id)
        if email_sender:
            tenant = self.tenants[tenant_id]
            sent = email_sender.send_order_confirmation(
                to_email=customer['email'],
                customer_name=customer['first_name'],
                amount=amount,
                order_id=payment_id[-8:],
                brand_name=tenant.name
            )
            if sent:
                self.metrics.emails_sent += 1
            else:
                self.metrics.emails_failed += 1

        return True, f"Paiement {amount}€ de {customer['email']} traité"

    def _on_payment_failed(self, event: dict,
                            tenant_id: str) -> Tuple[bool, str]:
        """Paiement échoué → notification client + log"""
        obj = event['data']['object']
        customer = self._extract_customer_data(obj)
        amount = obj.get('amount', 0) / 100

        # Notifier le client par email
        email_sender = self.email_senders.get(tenant_id)
        if email_sender and customer['email']:
            tenant = self.tenants[tenant_id]
            email_sender.send_payment_failed_notice(
                to_email=customer['email'],
                customer_name=customer['first_name'],
                brand_name=tenant.name
            )

        return True, f"Échec paiement {amount}€ de {customer.get('email', 'inconnu')} enregistré"

    def _on_payment_canceled(self, event: dict,
                              tenant_id: str) -> Tuple[bool, str]:
        """Paiement annulé → log"""
        obj = event['data']['object']
        payment_id = obj.get('id', 'unknown')
        logger.warning(f"Paiement annulé: {payment_id}")
        return True, f"Annulation {payment_id} enregistrée"

    def _on_checkout_completed(self, event: dict,
                                tenant_id: str) -> Tuple[bool, str]:
        """Session checkout complétée — traitement similaire au paiement"""
        obj = event['data']['object']
        customer = self._extract_customer_data(obj)
        amount = obj.get('amount_total', 0) / 100
        session_id = obj.get('id', 'unknown')

        if not customer['email']:
            return False, "Pas d'email dans la session checkout"

        espo = self.espo_clients.get(tenant_id)
        if not espo:
            return False, f"Pas de client EspoCRM pour {tenant_id}"

        contact_id = espo.create_or_update_contact(
            email=customer['email'],
            first_name=customer['first_name'],
            last_name=customer['last_name'],
            phone=customer['phone']
        )

        if contact_id:
            espo.create_opportunity(
                contact_id=contact_id,
                amount=amount,
                name=f"Checkout {session_id[-8:]} — {amount}€",
                stage='Closed Won'
            )
            self.metrics.opportunities_created += 1

        # ── Onboarding + Email de bienvenue ──────────────────────────
        customer_email_val = customer.get('email', '')
        customer_name_val  = customer.get('name', customer_email_val)

        if customer_email_val and getattr(self, '_onboarding_agent', None):
            try:
                # 1) Enregistrer le tenant si pas encore fait
                ok, reg_result = self._onboarding_agent.register_tenant(
                    name=customer_name_val,
                    contact_email=customer_email_val
                )
                if ok and isinstance(reg_result, dict):
                    tenant_id_new = reg_result.get('tenant_id', '')
                    if tenant_id_new:
                        # 2) Provisionner (DB + EspoCRM user)
                        prov_ok, prov_result = self._onboarding_agent.provision_tenant(
                            tenant_id=tenant_id_new,
                            tenant_slug=reg_result.get('slug', tenant_id_new)
                        )
                        # 3) Email de bienvenue
                        espo_url = prov_result.get('espocrm_url', os.getenv('ESPOCRM_URL', '')) if prov_ok else ''
                        temp_pwd = prov_result.get('temp_password', '') if prov_ok else ''
                        send_welcome_email(
                            to_email=customer_email_val,
                            customer_name=customer_name_val,
                            espocrm_url=espo_url,
                            temp_password=temp_pwd,
                            plan_name=obj.get('metadata', {}).get('plan_name', '')
                        )
                        logger.info(f"🎉 Onboarding complet pour {customer_email_val}")
                elif not ok:
                    # Tenant existe déjà → envoyer juste l'email de bienvenue
                    logger.info(f"ℹ️  Tenant existant pour {customer_email_val} — email de bienvenue ignoré")
            except Exception as e_onb:
                logger.error(f"❌ Erreur onboarding checkout : {e_onb}")

        return True, f"Checkout {amount}€ de {customer['email']} traité"

    def _on_invoice_paid(self, event: dict,
                          tenant_id: str) -> Tuple[bool, str]:
        """Facture payée (abonnement) → opportunité récurrente"""
        obj = event['data']['object']
        customer_email = obj.get('customer_email')
        amount = obj.get('amount_paid', 0) / 100
        invoice_id = obj.get('id', 'unknown')

        if not customer_email:
            return True, "Invoice sans email — ignorée"

        espo = self.espo_clients.get(tenant_id)
        if espo:
            contact = espo.find_contact_by_email(customer_email)
            if contact:
                espo.create_opportunity(
                    contact_id=contact['id'],
                    amount=amount,
                    name=f"Facture {invoice_id[-8:]} — {amount}€",
                    stage='Closed Won'
                )
                self.metrics.opportunities_created += 1

        return True, f"Facture {amount}€ ({customer_email}) enregistrée"

    def _on_invoice_failed(self, event: dict,
                            tenant_id: str) -> Tuple[bool, str]:
        """Facture non payée → alerte"""
        obj = event['data']['object']
        customer_email = obj.get('customer_email', 'inconnu')
        amount = obj.get('amount_due', 0) / 100
        logger.warning(f"⚠️ Facture non payée: {amount}€ ({customer_email})")
        return True, f"Échec facture {amount}€ enregistré"

    def _on_subscription_created(self, event: dict,
                                  tenant_id: str) -> Tuple[bool, str]:
        """Nouvel abonnement → créer contact + opportunité ouverte"""
        obj = event['data']['object']
        customer_id = obj.get('customer', 'unknown')
        logger.info(f"Nouvel abonnement: customer {customer_id}")
        return True, f"Abonnement créé pour {customer_id}"

    def _on_subscription_deleted(self, event: dict,
                                  tenant_id: str) -> Tuple[bool, str]:
        """Abonnement annulé → mettre à jour opportunité"""
        obj = event['data']['object']
        customer_id = obj.get('customer', 'unknown')
        logger.warning(f"Abonnement annulé: customer {customer_id}")
        return True, f"Abonnement annulé pour {customer_id}"

    def _on_dispute_created(self, event: dict,
                             tenant_id: str) -> Tuple[bool, str]:
        """Litige créé → ALERTE URGENTE"""
        obj = event['data']['object']
        amount = obj.get('amount', 0) / 100
        logger.error(f"🚨 LITIGE CRÉÉ: {amount}€ — Action requise!")
        return True, f"Litige {amount}€ enregistré — alerte admin"

    def _on_charge_refunded(self, event: dict,
                             tenant_id: str) -> Tuple[bool, str]:
        """Remboursement → log + MAJ opportunité"""
        obj = event['data']['object']
        amount_refunded = obj.get('amount_refunded', 0) / 100
        logger.info(f"Remboursement: {amount_refunded}€")
        return True, f"Remboursement {amount_refunded}€ enregistré"

    # ────────────────────────────────────────────
    # SELF-HEALING — Retry automatique en arrière-plan
    # ────────────────────────────────────────────

    def start_retry_loop(self):
        """Démarre la boucle de retry en arrière-plan"""
        if self._running:
            return

        self._running = True
        self._retry_thread = threading.Thread(
            target=self._retry_loop,
            daemon=True,
            name='webhook-retry-loop'
        )
        self._retry_thread.start()
        logger.info("🔄 Boucle de retry démarrée")

    def stop_retry_loop(self):
        """Arrête la boucle de retry"""
        self._running = False
        logger.info("🔄 Boucle de retry arrêtée")

    def _retry_loop(self):
        """Boucle qui retente les événements en échec"""
        while self._running:
            try:
                # Retirer les événements morts
                dead = self.retry_queue.remove_dead()
                for entry in dead:
                    logger.error(
                        f"💀 Événement définitivement abandonné: "
                        f"{entry['event'].get('type')} — {entry['error']}"
                    )

                # Retenter les événements prêts
                ready = self.retry_queue.get_ready()
                for entry in ready:
                    self.metrics.events_retried += 1
                    event = entry['event']
                    tenant_id = entry['tenant_id']

                    logger.info(
                        f"🔄 Retry {entry['attempts']}: "
                        f"{event.get('type')} (tenant: {tenant_id})"
                    )

                    success, message = self._process_event(event, tenant_id)

                    if success:
                        self.retry_queue.mark_success(entry)
                        self.metrics.events_processed += 1
                    else:
                        self.retry_queue.mark_retry(entry, message)

            except Exception as e:
                logger.error(f"Erreur dans la boucle de retry: {e}")

            # Vérifier toutes les 30 secondes
            time.sleep(30)

    # ────────────────────────────────────────────
    # OBSERVABILITÉ
    # ────────────────────────────────────────────

    def get_status(self) -> dict:
        """Retourne l'état complet de l'agent"""
        return {
            'agent': self.name,
            'status': 'running' if self._running else 'idle',
            'tenants': {
                tid: {
                    'name': t.name,
                    'active': t.active
                }
                for tid, t in self.tenants.items()
            },
            'metrics': self.metrics.to_dict(),
            'retry_queue_size': self.retry_queue.size,
            'timestamp': datetime.now().isoformat()
        }


# ============================================================================
# INSTANCE GLOBALE — importée par api_server.py
# ============================================================================

webhook_agent = WebhookHandlerAgent()
