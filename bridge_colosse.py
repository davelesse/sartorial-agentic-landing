#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Emplacement serveur : /var/www/digital-colosse.com/agents_aurum/bridge_colosse.py
# Pont appelé par webhook_colosse.php (Stripe -> PHP -> ce script).
import sys, os, json, logging
sys.path.append('/var/www/digital-colosse.com/agents_aurum')

# Charger le .env (SMTP + secret) — le bridge tournait sans, c'etait un bug latent
def _load_env(path):
    if os.path.exists(path):
        for line in open(path, encoding="utf-8", errors="replace"):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
for _p in ("/var/www/digital-colosse.com/public_html/api/.env",
           "/var/www/digital-colosse.com/.env"):
    _load_env(_p)

logging.basicConfig(level=logging.INFO,
                    filename='/var/log/digital-colosse/webhook_bridge.log')

try:
    from webhook_handler_agent import webhook_agent
except ImportError as e:
    logging.error(f"Erreur d'importation de l'Agent 21: {e}")
    sys.exit(1)

webhook_agent.register_default_tenant()


def _send_branded_emails(event):
    """Bienvenue Oracle + facture PDF sur checkout.session.completed."""
    if event.get('type') != 'checkout.session.completed':
        return
    obj = event.get('data', {}).get('object', {})
    details = obj.get('customer_details', {}) or {}
    to_email = obj.get('customer_email') or details.get('email') or ''
    name = details.get('name') or 'Client'
    meta = obj.get('metadata', {}) or {}
    plan = meta.get('plan_name') or meta.get('product_id') or 'ESSENCE'
    amount = (obj.get('amount_total') or 0) / 100.0
    currency = (obj.get('currency') or 'eur').upper()
    if not to_email:
        logging.info("Pas d'email client -> emails ignores")
        return

    # 1) Email de bienvenue brande (Oracle)
    try:
        import smtplib, ssl
        from email.mime.text import MIMEText
        from email_templates import email_engine
        subject, html = email_engine.render('welcome_oracle', 'digital-colosse',
                                            customer_name=name, plan_label=plan)
        host = os.getenv("SMTP_HOST", ""); port = int(os.getenv("SMTP_PORT", 587))
        user = os.getenv("SMTP_USER", ""); pwd = os.getenv("SMTP_PASSWORD", "")
        sender = os.getenv("FROM_EMAIL", os.getenv("EMAIL_FROM", user))
        if host and user and pwd:
            msg = MIMEText(html, "html", "utf-8")
            msg["Subject"] = subject
            msg["From"] = f"Digital Colosse <{sender}>"
            msg["To"] = to_email
            if port == 465:
                with smtplib.SMTP_SSL(host, port, context=ssl.create_default_context()) as s:
                    s.login(user, pwd); s.sendmail(sender, to_email, msg.as_string())
            else:
                with smtplib.SMTP(host, port) as s:
                    s.ehlo(); s.starttls(); s.login(user, pwd)
                    s.sendmail(sender, to_email, msg.as_string())
            logging.info(f"Email bienvenue envoye -> {to_email}")
        else:
            logging.warning("SMTP non configure -> bienvenue ignore")
    except Exception as e:
        logging.error(f"Email bienvenue: {e}")

    # 2) Facture PDF
    # NOTE: Hostinger/MailChannels rejette les pieces jointes PDF -> a migrer
    #       vers un lien de telechargement (PDF heberge sur le site).
    try:
        from invoice_generator import send_invoice_email
        send_invoice_email(to_email=to_email, customer_name=name,
                           plan_name=plan, amount=amount,
                           tenant_id='digital-colosse', currency=currency)
    except Exception as e:
        logging.error(f"Facture: {e}")


if len(sys.argv) > 2:
    payload_file = sys.argv[1]
    sig_header = sys.argv[2]
    try:
        with open(payload_file, 'rb') as f:
            payload_bytes = f.read()
        status, response = webhook_agent.handle_webhook(
            payload=payload_bytes, sig_header=sig_header, tenant_id='digital-colosse')
        print(f"SUCCESS: Status {status}")
        if isinstance(status, int) and 200 <= status < 300:
            try:
                _send_branded_emails(json.loads(payload_bytes))
            except Exception as e:
                logging.error(f"Parsing/emails: {e}")
    except Exception as e:
        logging.error(f"Erreur de traitement: {str(e)}")
        print(f"ERROR: {str(e)}")
