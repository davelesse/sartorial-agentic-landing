#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
╔════════════════════════════════════════════════════════════════════════╗
║  EMAIL TEMPLATE ENGINE — Emails brandés Digital Colosse               ║
║                                                                       ║
║  Système d'emails professionnels avec :                               ║
║  ✅ Design DC (fond sombre, or, turquoise)                            ║
║  ✅ Logo DC intégré                                                   ║
║  ✅ Boutons CTA stylés                                                ║
║  ✅ 5 langues via i18n_engine                                         ║
║  ✅ White-label (branding revendeur si sous-client)                   ║
║  ✅ Responsive (mobile + desktop)                                     ║
║  ✅ Templates par type de commande                                    ║
║  ✅ Templates rappels métier                                          ║
║  ✅ Templates onboarding                                              ║
║                                                                       ║
║  Usage :                                                              ║
║    from email_templates import email_engine                            ║
║    html = email_engine.render('order_confirm', tenant_id,             ║
║               customer_name='Sophie', product_name='Pack Fondation',  ║
║               amount='797€', delivery_days=7)                         ║
║                                                                       ║
║  Digital Colosse — Mars 2026                                         ║
╚════════════════════════════════════════════════════════════════════════╝
"""

import os
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger('EmailTemplates')



# ============================================================================
# LOGO DC EN BASE64 (48×48px, ~5KB)
# ============================================================================

DC_LOGO_BASE64 = "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"
DC_LOGO_DATA_URI = f"data:image/png;base64,{DC_LOGO_BASE64}"

# ============================================================================
# BRANDING PAR DÉFAUT
# ============================================================================

DEFAULT_BRAND = {
    'name': 'Digital Colosse',
    'tagline': "« l'automatisation comme un art »",
    'logo_url': 'https://digital-colosse.com/assets/logo-dc.png',
    'website': 'https://digital-colosse.com',
    'dashboard_url': 'https://digital-colosse.com/dashboard',
    'primary_color': '#D4AF37',     # Or
    'accent_color': '#48D1CC',      # Turquoise
    'bg_dark': '#09090b',           # Fond principal
    'bg_card': '#18181b',           # Fond carte
    'bg_header': '#0f0f12',         # Fond header
    'text_primary': '#fafafa',      # Texte principal
    'text_secondary': '#a1a1aa',    # Texte secondaire
    'text_muted': '#71717a',        # Texte discret
    'border_color': '#27272a',      # Bordures
    'sender_name': 'Le Colosse',
    'support_email': 'contact@digital-colosse.com',
}


# ============================================================================
# BASE LAYOUT HTML
# ============================================================================

def _base_layout(content: str, brand: dict, footer_extra: str = '') -> str:
    """Layout HTML commun à tous les emails"""
    return f"""<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{brand['name']}</title>
</head>
<body style="margin:0;padding:0;background-color:{brand['bg_dark']};font-family:'Helvetica Neue',Helvetica,Arial,sans-serif;">
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background-color:{brand['bg_dark']};">
        <tr><td align="center" style="padding:20px 10px;">
            <table role="presentation" width="600" cellspacing="0" cellpadding="0" style="max-width:600px;width:100%;">

                <!-- HEADER -->
                <tr><td style="background:{brand['bg_header']};padding:24px 32px;border-radius:12px 12px 0 0;border-bottom:2px solid {brand['primary_color']};">
                    <table role="presentation" width="100%" cellspacing="0" cellpadding="0">
                        <tr>
                            <td style="width:48px;">
                                <img src="{brand['logo_url']}" alt="{brand['name']}" width="42" height="42" style="border-radius:50%;border:2px solid {brand['primary_color']};">
                            </td>
                            <td style="padding-left:14px;">
                                <div style="font-size:18px;font-weight:700;color:{brand['primary_color']};font-family:Georgia,'Times New Roman',serif;letter-spacing:1px;">{brand['name'].upper()}</div>
                                <div style="font-size:11px;color:{brand['accent_color']};font-style:italic;letter-spacing:0.5px;margin-top:2px;">{brand['tagline']}</div>
                            </td>
                        </tr>
                    </table>
                </td></tr>

                <!-- CONTENT -->
                <tr><td style="background:{brand['bg_card']};padding:32px;border-left:1px solid {brand['border_color']};border-right:1px solid {brand['border_color']};">
                    {content}
                </td></tr>

                <!-- FOOTER -->
                <tr><td style="background:{brand['bg_header']};padding:24px 32px;border-radius:0 0 12px 12px;border-top:1px solid {brand['border_color']};">
                    {footer_extra}
                    <table role="presentation" width="100%" cellspacing="0" cellpadding="0">
                        <tr><td style="text-align:center;">
                            <div style="font-size:12px;color:{brand['text_muted']};margin-bottom:6px;">
                                {brand['name']} — {brand['tagline']}
                            </div>
                            <div style="font-size:11px;color:{brand['text_muted']};">
                                <a href="{brand['website']}" style="color:{brand['accent_color']};text-decoration:none;">{brand['website'].replace('https://', '')}</a>
                                &nbsp;·&nbsp;
                                <a href="mailto:{brand['support_email']}" style="color:{brand['accent_color']};text-decoration:none;">{brand['support_email']}</a>
                            </div>
                        </td></tr>
                    </table>
                </td></tr>

            </table>
        </td></tr>
    </table>
</body>
</html>"""


# ============================================================================
# COMPOSANTS RÉUTILISABLES
# ============================================================================

def _heading(text: str, brand: dict) -> str:
    return f'<h1 style="margin:0 0 16px 0;font-size:24px;font-weight:700;color:{brand["text_primary"]};font-family:Georgia,serif;">{text}</h1>'

def _subheading(text: str, brand: dict) -> str:
    return f'<h2 style="margin:20px 0 12px 0;font-size:18px;font-weight:600;color:{brand["primary_color"]};font-family:Georgia,serif;">{text}</h2>'

def _text(text: str, brand: dict) -> str:
    return f'<p style="margin:0 0 14px 0;font-size:15px;line-height:1.6;color:{brand["text_secondary"]};">{text}</p>'

def _text_small(text: str, brand: dict) -> str:
    return f'<p style="margin:0 0 10px 0;font-size:13px;line-height:1.5;color:{brand["text_muted"]};">{text}</p>'

def _button(text: str, url: str, brand: dict, color: str = None) -> str:
    bg = color or brand['primary_color']
    text_color = '#000000' if bg == brand['primary_color'] else '#000000'
    return f'''<table role="presentation" cellspacing="0" cellpadding="0" style="margin:24px 0;">
        <tr><td style="border-radius:8px;background:{bg};">
            <a href="{url}" target="_blank" style="display:inline-block;padding:14px 28px;font-size:15px;font-weight:700;color:{text_color};text-decoration:none;border-radius:8px;letter-spacing:0.5px;">{text}</a>
        </td></tr>
    </table>'''

def _divider(brand: dict) -> str:
    return f'<hr style="border:none;border-top:1px solid {brand["border_color"]};margin:24px 0;">'

def _info_row(label: str, value: str, brand: dict) -> str:
    return f'''<tr>
        <td style="padding:8px 12px;font-size:14px;color:{brand['text_muted']};border-bottom:1px solid {brand['border_color']};">{label}</td>
        <td style="padding:8px 12px;font-size:14px;color:{brand['text_primary']};font-weight:600;border-bottom:1px solid {brand['border_color']};text-align:right;">{value}</td>
    </tr>'''

def _info_table(rows: list, brand: dict) -> str:
    """Tableau d'informations (montant, délai, etc.)"""
    inner = ''.join(rows)
    return f'''<table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background:{brand['bg_dark']};border-radius:8px;border:1px solid {brand['border_color']};margin:16px 0;overflow:hidden;">
        {inner}
    </table>'''

def _signature(sender_name: str, brand: dict) -> str:
    return f'''<div style="margin-top:28px;padding-top:20px;border-top:1px solid {brand['border_color']};">
        <p style="margin:0;font-size:16px;font-weight:700;color:{brand['primary_color']};font-family:Georgia,serif;font-style:italic;">{sender_name}</p>
        <p style="margin:4px 0 0 0;font-size:13px;color:{brand['accent_color']};font-style:italic;">{brand['name']}</p>
    </div>'''

def _badge(text: str, brand: dict, color: str = None) -> str:
    bg = color or brand['primary_color']
    return f'<span style="display:inline-block;padding:4px 12px;font-size:12px;font-weight:700;color:#000;background:{bg};border-radius:20px;letter-spacing:0.5px;">{text}</span>'


# ============================================================================
# TEMPLATES PAR TYPE
# ============================================================================

# ── Textes multilingues pour chaque template ──

TEXTS = {
    # ════════ COMMANDES ════════

    'order_pack': {
        'subject': {
            'fr': 'Votre {product_name} est en route !',
            'en': 'Your {product_name} is on its way!',
            'nl': 'Uw {product_name} is onderweg!',
            'de': 'Ihr {product_name} ist unterwegs!',
            'es': '¡Su {product_name} está en camino!',
        },
        'greeting': {
            'fr': 'Merci {customer_name} !',
            'en': 'Thank you {customer_name}!',
            'nl': 'Bedankt {customer_name}!',
            'de': 'Danke {customer_name}!',
            'es': '¡Gracias {customer_name}!',
        },
        'body': {
            'fr': 'Votre <strong>{product_name}</strong> a bien été commandé. Notre équipe va vous contacter dans les prochaines heures pour démarrer votre projet.',
            'en': 'Your <strong>{product_name}</strong> has been ordered. Our team will contact you within the next few hours to start your project.',
            'nl': 'Uw <strong>{product_name}</strong> is besteld. Ons team neemt binnen enkele uren contact met u op om uw project te starten.',
            'de': 'Ihr <strong>{product_name}</strong> wurde bestellt. Unser Team wird sich in den nächsten Stunden bei Ihnen melden, um Ihr Projekt zu starten.',
            'es': 'Su <strong>{product_name}</strong> ha sido pedido. Nuestro equipo se pondrá en contacto con usted en las próximas horas para iniciar su proyecto.',
        },
        'label_amount': {'fr': 'Montant', 'en': 'Amount', 'nl': 'Bedrag', 'de': 'Betrag', 'es': 'Monto'},
        'label_delivery': {'fr': 'Livraison estimée', 'en': 'Estimated delivery', 'nl': 'Geschatte levertijd', 'de': 'Geschätzte Lieferzeit', 'es': 'Entrega estimada'},
        'label_order': {'fr': 'Commande', 'en': 'Order', 'nl': 'Bestelling', 'de': 'Bestellung', 'es': 'Pedido'},
        'days': {'fr': '{n} jours', 'en': '{n} days', 'nl': '{n} dagen', 'de': '{n} Tage', 'es': '{n} días'},
        'next_step': {
            'fr': 'Prochaine étape : vous recevrez un formulaire pour nous décrire vos besoins. Plus vous êtes précis, plus le résultat sera parfait.',
            'en': 'Next step: you will receive a form to describe your needs. The more precise you are, the better the result.',
            'nl': 'Volgende stap: u ontvangt een formulier om uw wensen te beschrijven. Hoe preciezer, hoe beter het resultaat.',
            'de': 'Nächster Schritt: Sie erhalten ein Formular zur Beschreibung Ihrer Anforderungen. Je genauer, desto besser das Ergebnis.',
            'es': 'Próximo paso: recibirá un formulario para describir sus necesidades. Cuanto más preciso sea, mejor será el resultado.',
        },
    },

    'order_auto': {
        'subject': {
            'fr': '{product_name} — activé !',
            'en': '{product_name} — activated!',
            'nl': '{product_name} — geactiveerd!',
            'de': '{product_name} — aktiviert!',
            'es': '¡{product_name} — activado!',
        },
        'greeting': {
            'fr': '{customer_name}, c\'est parti !',
            'en': '{customer_name}, you\'re all set!',
            'nl': '{customer_name}, u bent klaar!',
            'de': '{customer_name}, es geht los!',
            'es': '¡{customer_name}, todo listo!',
        },
        'body': {
            'fr': 'Votre <strong>{product_name}</strong> est actif. Les agents travaillent pour vous dès maintenant — 24h/24, 7j/7.',
            'en': 'Your <strong>{product_name}</strong> is active. The agents are working for you right now — 24/7.',
            'nl': 'Uw <strong>{product_name}</strong> is actief. De agents werken nu voor u — 24/7.',
            'de': 'Ihr <strong>{product_name}</strong> ist aktiv. Die Agenten arbeiten jetzt für Sie — rund um die Uhr.',
            'es': 'Su <strong>{product_name}</strong> está activo. Los agentes trabajan para usted ahora mismo — 24/7.',
        },
        'features_title': {
            'fr': 'Ce qui est actif', 'en': 'What\'s active', 'nl': 'Wat actief is', 'de': 'Was aktiv ist', 'es': 'Lo que está activo',
        },
        'features': {
            'fr': ['Rappels clients automatiques', 'Emails de suivi personnalisés', 'Dashboard KPIs en temps réel', 'Rapports hebdomadaires'],
            'en': ['Automatic client reminders', 'Personalized follow-up emails', 'Real-time KPI dashboard', 'Weekly reports'],
            'nl': ['Automatische klantreminders', 'Gepersonaliseerde follow-up e-mails', 'Realtime KPI-dashboard', 'Wekelijkse rapporten'],
            'de': ['Automatische Kundenerinnerungen', 'Personalisierte Follow-up-E-Mails', 'Echtzeit-KPI-Dashboard', 'Wöchentliche Berichte'],
            'es': ['Recordatorios automáticos', 'Emails de seguimiento personalizados', 'Dashboard KPIs en tiempo real', 'Informes semanales'],
        },
        'btn_dashboard': {
            'fr': 'Accéder à mon dashboard', 'en': 'Go to my dashboard', 'nl': 'Naar mijn dashboard', 'de': 'Zu meinem Dashboard', 'es': 'Ir a mi panel',
        },
    },

    'order_human': {
        'subject': {
            'fr': 'Commande confirmée — {product_name}',
            'en': 'Order confirmed — {product_name}',
            'nl': 'Bestelling bevestigd — {product_name}',
            'de': 'Bestellung bestätigt — {product_name}',
            'es': 'Pedido confirmado — {product_name}',
        },
        'greeting': {
            'fr': 'Merci {customer_name} !',
            'en': 'Thank you {customer_name}!',
            'nl': 'Bedankt {customer_name}!',
            'de': 'Danke {customer_name}!',
            'es': '¡Gracias {customer_name}!',
        },
        'body': {
            'fr': 'Votre commande <strong>{product_name}</strong> est confirmée. Nous démarrons le travail.',
            'en': 'Your order <strong>{product_name}</strong> is confirmed. We\'re getting started.',
            'nl': 'Uw bestelling <strong>{product_name}</strong> is bevestigd. We gaan aan de slag.',
            'de': 'Ihre Bestellung <strong>{product_name}</strong> ist bestätigt. Wir beginnen mit der Arbeit.',
            'es': 'Su pedido <strong>{product_name}</strong> está confirmado. Comenzamos a trabajar.',
        },
        'brief_needed': {
            'fr': 'Pour démarrer, nous avons besoin de quelques informations sur vos besoins. Remplissez le formulaire ci-dessous — ça prend 5 minutes.',
            'en': 'To get started, we need some information about your needs. Fill out the form below — it takes 5 minutes.',
            'nl': 'Om te beginnen hebben we wat informatie nodig over uw wensen. Vul het onderstaande formulier in — het duurt 5 minuten.',
            'de': 'Zum Start benötigen wir einige Informationen über Ihre Anforderungen. Füllen Sie das Formular aus — es dauert 5 Minuten.',
            'es': 'Para comenzar, necesitamos información sobre sus necesidades. Complete el formulario — toma 5 minutos.',
        },
        'btn_brief': {
            'fr': 'Remplir le brief (5 min)', 'en': 'Fill the brief (5 min)', 'nl': 'Vul de briefing in (5 min)', 'de': 'Briefing ausfüllen (5 Min)', 'es': 'Completar el brief (5 min)',
        },
    },

    'order_recurring': {
        'subject': {
            'fr': 'Bienvenue — {product_name} activé !',
            'en': 'Welcome — {product_name} activated!',
            'nl': 'Welkom — {product_name} geactiveerd!',
            'de': 'Willkommen — {product_name} aktiviert!',
            'es': '¡Bienvenido — {product_name} activado!',
        },
        'greeting': {
            'fr': 'Bienvenue {customer_name} !',
            'en': 'Welcome {customer_name}!',
            'nl': 'Welkom {customer_name}!',
            'de': 'Willkommen {customer_name}!',
            'es': '¡Bienvenido {customer_name}!',
        },
        'body': {
            'fr': 'Votre abonnement <strong>{product_name}</strong> ({amount}/mois) est actif.',
            'en': 'Your subscription <strong>{product_name}</strong> ({amount}/month) is active.',
            'nl': 'Uw abonnement <strong>{product_name}</strong> ({amount}/maand) is actief.',
            'de': 'Ihr Abonnement <strong>{product_name}</strong> ({amount}/Monat) ist aktiv.',
            'es': 'Su suscripción <strong>{product_name}</strong> ({amount}/mes) está activa.',
        },
        'whats_included': {
            'fr': 'Ce qui est inclus', 'en': 'What\'s included', 'nl': 'Wat inbegrepen is', 'de': 'Was enthalten ist', 'es': 'Lo que incluye',
        },
        'all_set': {
            'fr': 'Vos agents sont actifs. Votre site est surveillé. On s\'occupe de tout.',
            'en': 'Your agents are active. Your site is monitored. We handle everything.',
            'nl': 'Uw agents zijn actief. Uw site wordt gemonitord. Wij regelen alles.',
            'de': 'Ihre Agenten sind aktiv. Ihre Website wird überwacht. Wir kümmern uns um alles.',
            'es': 'Sus agentes están activos. Su sitio está monitoreado. Nos encargamos de todo.',
        },
    },

    'order_completed': {
        'subject': {
            'fr': 'Votre {product_name} est prêt !',
            'en': 'Your {product_name} is ready!',
            'nl': 'Uw {product_name} is klaar!',
            'de': 'Ihr {product_name} ist fertig!',
            'es': '¡Su {product_name} está listo!',
        },
        'greeting': {
            'fr': '{customer_name}, c\'est livré !',
            'en': '{customer_name}, it\'s delivered!',
            'nl': '{customer_name}, het is geleverd!',
            'de': '{customer_name}, es ist geliefert!',
            'es': '¡{customer_name}, está entregado!',
        },
        'body': {
            'fr': 'Votre <strong>{product_name}</strong> est terminé et prêt à l\'emploi.',
            'en': 'Your <strong>{product_name}</strong> is completed and ready to use.',
            'nl': 'Uw <strong>{product_name}</strong> is voltooid en klaar voor gebruik.',
            'de': 'Ihr <strong>{product_name}</strong> ist fertig und einsatzbereit.',
            'es': 'Su <strong>{product_name}</strong> está completado y listo para usar.',
        },
        'btn_dashboard': {
            'fr': 'Voir mon espace', 'en': 'View my dashboard', 'nl': 'Naar mijn dashboard', 'de': 'Zu meinem Dashboard', 'es': 'Ver mi panel',
        },
        'thanks': {
            'fr': 'Merci pour votre confiance. Si vous avez la moindre question, répondez simplement à cet email.',
            'en': 'Thank you for your trust. If you have any questions, simply reply to this email.',
            'nl': 'Bedankt voor uw vertrouwen. Heeft u vragen? Antwoord gewoon op deze e-mail.',
            'de': 'Danke für Ihr Vertrauen. Bei Fragen antworten Sie einfach auf diese E-Mail.',
            'es': 'Gracias por su confianza. Si tiene alguna pregunta, simplemente responda a este email.',
        },
    },

    'order_shipped': {
        'subject': {
            'fr': 'Votre commande est expédiée !',
            'en': 'Your order has been shipped!',
            'nl': 'Uw bestelling is verzonden!',
            'de': 'Ihre Bestellung wurde versandt!',
            'es': '¡Su pedido ha sido enviado!',
        },
        'body': {
            'fr': 'Votre <strong>{product_name}</strong> est en route !',
            'en': 'Your <strong>{product_name}</strong> is on its way!',
            'nl': 'Uw <strong>{product_name}</strong> is onderweg!',
            'de': 'Ihr <strong>{product_name}</strong> ist unterwegs!',
            'es': '¡Su <strong>{product_name}</strong> está en camino!',
        },
        'label_tracking': {'fr': 'Numéro de suivi', 'en': 'Tracking number', 'nl': 'Trackingnummer', 'de': 'Sendungsnummer', 'es': 'Número de seguimiento'},
    },

    'brief_request': {
        'subject': {
            'fr': 'Dernière étape — Votre brief {product_name}',
            'en': 'Last step — Your {product_name} brief',
            'nl': 'Laatste stap — Uw {product_name} briefing',
            'de': 'Letzter Schritt — Ihr {product_name} Briefing',
            'es': 'Último paso — Su brief {product_name}',
        },
        'body': {
            'fr': 'Pour démarrer votre <strong>{product_name}</strong>, nous avons besoin de quelques informations.',
            'en': 'To start your <strong>{product_name}</strong>, we need some information.',
            'nl': 'Om uw <strong>{product_name}</strong> te starten, hebben we wat informatie nodig.',
            'de': 'Um Ihr <strong>{product_name}</strong> zu starten, benötigen wir einige Informationen.',
            'es': 'Para iniciar su <strong>{product_name}</strong>, necesitamos información.',
        },
        'btn': {
            'fr': 'Remplir le brief (5 min)', 'en': 'Fill the brief (5 min)', 'nl': 'Briefing invullen (5 min)', 'de': 'Briefing ausfüllen (5 Min)', 'es': 'Completar el brief (5 min)',
        },
    },
    'welcome_oracle': {
        'subject': {
            'fr': '☉ Bienvenue dans la Forge — Votre Oracle est prêt',
            'en': '☉ Welcome to the Forge — Your Oracle is ready',
            'nl': '☉ Welkom in de Forge — Uw Oracle is klaar',
            'de': '☉ Willkommen in der Forge — Ihr Oracle ist bereit',
            'es': '☉ Bienvenido a la Forge — Su Oráculo está listo',
        },
        'greeting': {
            'fr': 'Bonjour {customer_name},',
            'en': 'Hello {customer_name},',
            'nl': 'Hallo {customer_name},',
            'de': 'Hallo {customer_name},',
            'es': 'Hola {customer_name},',
        },
        'intro': {
            'fr': 'Votre souscription au niveau <strong style="color:#D4AF37;">{plan_label}</strong> a été confirmée. <strong>L’Oracle est maintenant activé</strong> — votre conseiller solaire est disponible dès cet instant, 24h/24.',
            'en': 'Your subscription to <strong style="color:#D4AF37;">{plan_label}</strong> has been confirmed. <strong>The Oracle is now active</strong> — your Solar advisor is available right now, 24/7.',
            'nl': 'Uw abonnement op niveau <strong style="color:#D4AF37;">{plan_label}</strong> is bevestigd. <strong>De Oracle is nu actief</strong> — uw AI-adviseur staat 24/7 voor u klaar.',
            'de': 'Ihr Abonnement für Stufe <strong style="color:#D4AF37;">{plan_label}</strong> wurde bestätigt. <strong>Das Oracle ist jetzt aktiv</strong> — 24/7 für Sie verfügbar.',
            'es': 'Su suscripción al nivel <strong style="color:#D4AF37;">{plan_label}</strong> ha sido confirmada. <strong>El Oráculo está ahora activo</strong> — disponible 24h.',
        },
        'level_label': {
            'fr': 'Niveau Actif', 'en': 'Active Level',
            'nl': 'Actief Niveau', 'de': 'Aktive Stufe', 'es': 'Nivel Activo',
        },
        'members_label': {
            'fr': 'Membres Déployés', 'en': 'Deployed Members',
            'nl': 'Actieve Leden', 'de': 'Aktive Mitglieder', 'es': 'Miembros Activos',
        },
        'steps_title': {
            'fr': 'Vos prochaines étapes', 'en': 'Your next steps',
            'nl': 'Uw volgende stappen', 'de': 'Ihre nächsten Schritte', 'es': 'Sus próximos pasos',
        },
        'step1_title': {
            'fr': 'Consultez L’Oracle', 'en': 'Consult The Oracle',
            'nl': 'Raadpleeg De Oracle', 'de': 'Das Oracle konsultieren', 'es': 'Consulte El Oráculo',
        },
        'step1_body': {
            'fr': 'Accédez à votre conseiller solaire. Décrivez votre activité, vos systèmes, vos objectifs. Il conduit l’audit et formule le plan de déploiement optimal pour vos Agents Aurum.',
            'en': 'Access your Solar advisor. Describe your business, systems and goals. It conducts the audit and formulates the optimal deployment plan for your Aurum Agents.',
            'nl': 'Toegang tot uw AI-adviseur. Beschrijf uw activiteit, systemen en doelen. Hij voert de audit uit.',
            'de': 'Greifen Sie auf Ihren KI-Berater zu. Beschreiben Sie Ihr Unternehmen und Ziele. Er führt das Audit durch.',
            'es': 'Acceda a su asesor de IA. Describa su negocio, sistemas y objetivos. Realiza la auditoría.',
        },
        'step2_title': {
            'fr': 'Connexion de vos systèmes', 'en': 'Connect your systems',
            'nl': 'Verbind uw systemen', 'de': 'Ihre Systeme verbinden', 'es': 'Conecte sus sistemas',
        },
        'step2_body': {
            'fr': 'Notre équipe connecte vos outils (SaaS, IaaS, RaaS...) aux Agents Aurum assignés à votre niveau <strong style="color:#D4AF37;">{plan_label}</strong>. L’Oracle supervise chaque intégration.',
            'en': 'Our team connects your tools (SaaS, IaaS, RaaS...) to the Aurum Agents at your <strong style="color:#D4AF37;">{plan_label}</strong> level.',
            'nl': 'Ons team verbindt uw tools met de Aurum-agenten voor niveau <strong style="color:#D4AF37;">{plan_label}</strong>.',
            'de': 'Unser Team verbindet Ihre Tools mit den Aurum-Agenten für Stufe <strong style="color:#D4AF37;">{plan_label}</strong>.',
            'es': 'Nuestro equipo conecta sus herramientas a los Agentes Aurum de nivel <strong style="color:#D4AF37;">{plan_label}</strong>.',
        },
        'step3_title': {
            'fr': 'Les Agents Aurum entrent en action', 'en': 'The Aurum Agents take action',
            'nl': 'De Aurum-agenten gaan aan de slag', 'de': 'Die Aurum-Agenten werden aktiv',
            'es': 'Los Agentes Aurum entran en acción',
        },
        'step3_body': {
            'fr': 'Une fois connectés, vos Agents exécutent, automatisent et rapportent en continu. L’Oracle reste disponible pour reconfigurer à tout moment.',
            'en': 'Once connected, your Agents execute, automate and report continuously. The Oracle remains available at any time.',
            'nl': 'Eenmaal verbonden voeren uw agenten continu taken uit. De Oracle blijft beschikbaar.',
            'de': 'Nach der Verbindung führen Ihre Agenten Aufgaben aus. Das Oracle bleibt verfügbar.',
            'es': 'Una vez conectados, sus Agentes ejecutan continuamente. El Oráculo permanece disponible.',
        },
        'btn': {
            'fr': 'Activer L’Oracle →', 'en': 'Activate The Oracle →',
            'nl': 'De Oracle activeren →', 'de': 'Das Oracle aktivieren →',
            'es': 'Activar El Oráculo →',
        },
        'upsell_label': {
            'fr': 'Prochain Niveau de Conscience', 'en': 'Next Level of Consciousness',
            'nl': 'Volgend Bewustzijnsniveau', 'de': 'Nächste Bewusstseinsstufe',
            'es': 'Próximo Nivel de Conciencia',
        },
        'upsell_body': {
            'fr': 'Montez au niveau <strong style="color:#D4AF37;">{next_level}</strong> pour déployer davantage d’Agents Aurum.',
            'en': 'Upgrade to <strong style="color:#D4AF37;">{next_level}</strong> to deploy more Aurum Agents.',
            'nl': 'Upgrade naar niveau <strong style="color:#D4AF37;">{next_level}</strong> voor meer Aurum-agenten.',
            'de': 'Steigen Sie auf Stufe <strong style="color:#D4AF37;">{next_level}</strong> auf.',
            'es': 'Suba al nivel <strong style="color:#D4AF37;">{next_level}</strong> para más Agentes Aurum.',
        },
        'upsell_link': {
            'fr': 'Voir les offres', 'en': 'View offers',
            'nl': 'Bekijk aanbod', 'de': 'Angebote ansehen', 'es': 'Ver ofertas',
        },
        'footer': {
            'fr': 'Des questions ? Répondez directement à cet email.',
            'en': 'Any questions? Simply reply to this email.',
            'nl': 'Vragen? Antwoord gewoon op deze e-mail.',
            'de': 'Fragen? Antworten Sie einfach auf diese E-Mail.',
            'es': '¿Preguntas? Simplemente responda a este email.',
        },
    },
    'payment_failed': {'subject': {'fr': '⚠️ Action requise — Paiement échoué', 'en': '⚠️ Action required — Payment failed', 'nl': '⚠️ Actie vereist — Betaling mislukt', 'de': '⚠️ Handlung erforderlich — Zahlung fehlgeschlagen', 'es': '⚠️ Acción requerida — Pago fallido'}, 'greeting': {'fr': 'Bonjour {customer_name},', 'en': 'Hello {customer_name},', 'nl': 'Hallo {customer_name},', 'de': 'Hallo {customer_name},', 'es': 'Hola {customer_name},'}, 'body': {'fr': 'Nous n’avons pas pu traiter votre paiement de <strong style="color:#D4AF37;">{amount}</strong> pour votre abonnement <strong>{plan_label}</strong>. Veuillez mettre à jour votre moyen de paiement.', 'en': 'We were unable to process your payment of <strong style="color:#D4AF37;">{amount}</strong> for your <strong>{plan_label}</strong> subscription. Please update your payment method.', 'nl': 'We konden uw betaling van <strong style="color:#D4AF37;">{amount}</strong> niet verwerken. Werk uw betaalmethode bij.', 'de': 'Wir konnten Ihre Zahlung von <strong style="color:#D4AF37;">{amount}</strong> nicht verarbeiten. Bitte aktualisieren Sie Ihre Zahlungsmethode.', 'es': 'No pudimos procesar su pago de <strong style="color:#D4AF37;">{amount}</strong>. Por favor actualice su método de pago.'}, 'warning': {'fr': 'Sans mise à jour sous <strong>48h</strong>, votre accès sera suspendu.', 'en': 'Without an update within <strong>48h</strong>, your access will be suspended.', 'nl': 'Zonder update binnen <strong>48u</strong> wordt uw toegang opgeschort.', 'de': 'Ohne Aktualisierung innerhalb von <strong>48h</strong> wird Ihr Zugang gesperrt.', 'es': 'Sin actualización en <strong>48h</strong>, su acceso será suspendido.'}, 'btn': {'fr': 'Mettre à jour le paiement →', 'en': 'Update payment →', 'nl': 'Betaling bijwerken →', 'de': 'Zahlung aktualisieren →', 'es': 'Actualizar pago →'}, 'help': {'fr': 'Un problème ? Répondez à cet email, nous vous aidons immédiatement.', 'en': 'Any issue? Reply to this email, we help you right away.', 'nl': 'Problemen? Antwoord op deze e-mail, wij helpen u direct.', 'de': 'Probleme? Antworten Sie auf diese E-Mail, wir helfen sofort.', 'es': '¿Problemas? Responda a este email, le ayudamos de inmediato.'}},
    'invoice': {'subject': {'fr': 'Votre facture Digital Colosse — {invoice_number}', 'en': 'Your Digital Colosse invoice — {invoice_number}', 'nl': 'Uw Digital Colosse factuur — {invoice_number}', 'de': 'Ihre Digital Colosse Rechnung — {invoice_number}', 'es': 'Su factura Digital Colosse — {invoice_number}'}, 'greeting': {'fr': 'Bonjour {customer_name},', 'en': 'Hello {customer_name},', 'nl': 'Hallo {customer_name},', 'de': 'Hallo {customer_name},', 'es': 'Hola {customer_name},'}, 'body': {'fr': 'Veuillez trouver ci-joint votre facture <strong style="color:#D4AF37;">{invoice_number}</strong> d’un montant de <strong style="color:#D4AF37;">{amount}</strong> pour votre abonnement <strong>{plan_label}</strong>.', 'en': 'Please find attached your invoice <strong style="color:#D4AF37;">{invoice_number}</strong> for <strong style="color:#D4AF37;">{amount}</strong> for your <strong>{plan_label}</strong> subscription.', 'nl': 'Hierbij ontvangt u uw factuur <strong style="color:#D4AF37;">{invoice_number}</strong> voor <strong style="color:#D4AF37;">{amount}</strong>.', 'de': 'Anbei finden Sie Ihre Rechnung <strong style="color:#D4AF37;">{invoice_number}</strong> über <strong style="color:#D4AF37;">{amount}</strong>.', 'es': 'Adjunto encontrará su factura <strong style="color:#D4AF37;">{invoice_number}</strong> por <strong style="color:#D4AF37;">{amount}</strong>.'}, 'label_invoice': {'fr': 'N° Facture', 'en': 'Invoice No.', 'nl': 'Factuurnr.', 'de': 'Rechnungsnr.', 'es': 'Nº Factura'}, 'label_date': {'fr': 'Date', 'en': 'Date', 'nl': 'Datum', 'de': 'Datum', 'es': 'Fecha'}, 'label_plan': {'fr': 'Abonnement', 'en': 'Subscription', 'nl': 'Abonnement', 'de': 'Abonnement', 'es': 'Suscripción'}, 'label_ht': {'fr': 'Montant HT', 'en': 'Amount excl. VAT', 'nl': 'Bedrag excl. btw', 'de': 'Betrag netto', 'es': 'Importe excl. IVA'}, 'label_tva': {'fr': 'Tax/VAT (0%)', 'en': 'Tax/VAT (0%)', 'nl': 'Tax/VAT (0%)', 'de': 'Tax/VAT (0%)', 'es': 'Tax/VAT (0%)'}, 'label_ttc': {'fr': 'Total TTC', 'en': 'Total incl. VAT', 'nl': 'Totaal incl. btw', 'de': 'Gesamt brutto', 'es': 'Total incl. IVA'}, 'footer_note': {'fr': 'Facture émise par Digital Colosse LLC — Wyoming LLC — Tax/VAT not applicable — Conservez ce document pour votre comptabilité.', 'en': 'Invoice issued by Digital Colosse LLC — Wyoming LLC — Tax/VAT not applicable — Please keep for your records.', 'nl': 'Factuur uitgegeven door Digital Colosse LLC — Wyoming LLC — Tax/VAT not applicable.', 'de': 'Rechnung von Digital Colosse LLC — Wyoming LLC — Tax/VAT not applicable.', 'es': 'Factura emitida por Digital Colosse LLC — Wyoming LLC — Tax/VAT not applicable.'}, 'btn': {'fr': 'Accéder à L’Oracle →', 'en': 'Access The Oracle →', 'nl': 'Toegang tot De Oracle →', 'de': 'Zum Oracle →', 'es': 'Acceder al Oráculo →'}},
}


# ============================================================================
# EMAIL ENGINE
# ============================================================================

class EmailTemplateEngine:
    """
    Moteur de templates d'emails brandés Digital Colosse.
    
    Usage :
        subject, html = email_engine.render('order_pack', tenant_id,
            customer_name='Sophie', product_name='Pack Fondation',
            amount='797€', delivery_days=7)
    """

    def __init__(self):
        self.i18n = None
        self.reseller_manager = None
        self.logger = logging.getLogger('EmailTemplates')

    def set_dependencies(self, i18n=None, reseller_manager=None):
        self.i18n = i18n
        self.reseller_manager = reseller_manager

    def _get_lang(self, tenant_id: str) -> str:
        if self.i18n:
            return self.i18n.get_language(tenant_id)
        return 'fr'

    def _get_brand(self, tenant_id: str) -> dict:
        """Récupère le branding (white-label si revendeur, sinon DC)"""
        brand = DEFAULT_BRAND.copy()
        if self.reseller_manager:
            custom = self.reseller_manager.get_branding(tenant_id)
            if custom and custom.get('brand_name') != 'Digital Colosse':
                brand['name'] = custom.get('brand_name', brand['name'])
                brand['logo_url'] = custom.get('logo_url') or brand['logo_url']
                brand['primary_color'] = custom.get('primary_color') or brand['primary_color']
                brand['accent_color'] = custom.get('accent_color') or brand['accent_color']
                if custom.get('hide_powered_by'):
                    brand['tagline'] = ''
        return brand

    def _t(self, template_key: str, field: str, lang: str, **kwargs) -> str:
        """Récupère un texte traduit"""
        texts = TEXTS.get(template_key, {})
        field_texts = texts.get(field, {})
        text = field_texts.get(lang) or field_texts.get('fr', '')
        if isinstance(text, str):
            try:
                return text.format(**{k: v for k, v in kwargs.items() if isinstance(v, (str, int, float))})
            except KeyError:
                return text
        return text  # Pour les listes

    # ────────────────────────────────────────────
    # RENDER PRINCIPAL
    # ────────────────────────────────────────────

    def render(self, template_name: str, tenant_id: str, **kwargs) -> tuple:
        """
        Rendu d'un email. Retourne (subject, html_body).
        
        Templates disponibles :
        - order_pack, order_auto, order_human, order_recurring
        - order_completed, order_shipped
        - brief_request
        """
        lang = self._get_lang(tenant_id)
        brand = self._get_brand(tenant_id)

        renderer = getattr(self, f'_render_{template_name}', None)
        if not renderer:
            self.logger.warning(f"Template inconnu: {template_name}")
            return f"Notification — {brand['name']}", _base_layout(
                _heading('Notification', brand) + _text(str(kwargs), brand), brand
            )

        return renderer(lang, brand, tenant_id, **kwargs)

    # ────────────────────────────────────────────
    # COMMANDE PACK
    # ────────────────────────────────────────────

    def _render_order_pack(self, lang, brand, tenant_id, **kw):
        subject = self._t('order_pack', 'subject', lang, **kw)
        days_text = self._t('order_pack', 'days', lang, n=kw.get('delivery_days', 7))

        content = ''.join([
            _heading(self._t('order_pack', 'greeting', lang, **kw), brand),
            _text(self._t('order_pack', 'body', lang, **kw), brand),
            _info_table([
                _info_row(self._t('order_pack', 'label_order', lang), kw.get('order_id', ''), brand),
                _info_row(self._t('order_pack', 'label_amount', lang), str(kw.get('amount', '')), brand),
                _info_row(self._t('order_pack', 'label_delivery', lang), days_text, brand),
            ], brand),
            _divider(brand),
            _subheading('📋', brand),
            _text(self._t('order_pack', 'next_step', lang, **kw), brand),
            _signature(brand['sender_name'], brand),
        ])
        return subject, _base_layout(content, brand)

    # ────────────────────────────────────────────
    # COMMANDE DIGITAL AUTO (Agents IA, Audit, Oracle)
    # ────────────────────────────────────────────

    def _render_order_auto(self, lang, brand, tenant_id, **kw):
        subject = self._t('order_auto', 'subject', lang, **kw)
        features = self._t('order_auto', 'features', lang)
        features_html = ''
        if isinstance(features, list):
            for f in features:
                features_html += f'<tr><td style="padding:6px 0;font-size:14px;color:{brand["text_secondary"]};">✅ {f}</td></tr>'

        content = ''.join([
            _badge('ACTIVÉ', brand, brand['accent_color']),
            '<br><br>',
            _heading(self._t('order_auto', 'greeting', lang, **kw), brand),
            _text(self._t('order_auto', 'body', lang, **kw), brand),
            _subheading(self._t('order_auto', 'features_title', lang), brand),
            f'<table role="presentation" cellspacing="0" cellpadding="0" style="margin:12px 0;">{features_html}</table>',
            _button(self._t('order_auto', 'btn_dashboard', lang), brand['dashboard_url'], brand, brand['accent_color']),
            _signature(brand['sender_name'], brand),
        ])
        return subject, _base_layout(content, brand)

    # ────────────────────────────────────────────
    # COMMANDE DIGITAL HUMAN (Site, Tunnel, Logo)
    # ────────────────────────────────────────────

    def _render_order_human(self, lang, brand, tenant_id, **kw):
        subject = self._t('order_human', 'subject', lang, **kw)
        brief_url = kw.get('brief_url', f"{brand['website']}/brief/{kw.get('order_id', '')}")

        content = ''.join([
            _heading(self._t('order_human', 'greeting', lang, **kw), brand),
            _text(self._t('order_human', 'body', lang, **kw), brand),
            _info_table([
                _info_row(self._t('order_pack', 'label_amount', lang), str(kw.get('amount', '')), brand),
                _info_row(self._t('order_pack', 'label_delivery', lang),
                          self._t('order_pack', 'days', lang, n=kw.get('delivery_days', 7)), brand),
            ], brand),
            _divider(brand),
            _text(self._t('order_human', 'brief_needed', lang, **kw), brand),
            _button(self._t('order_human', 'btn_brief', lang), brief_url, brand),
            _signature(brand['sender_name'], brand),
        ])
        return subject, _base_layout(content, brand)

    # ────────────────────────────────────────────
    # ABONNEMENT RÉCURRENT (Maintenance, Plans SaaS)
    # ────────────────────────────────────────────

    def _render_order_recurring(self, lang, brand, tenant_id, **kw):
        subject = self._t('order_recurring', 'subject', lang, **kw)

        content = ''.join([
            _badge('ABONNEMENT ACTIF', brand, brand['primary_color']),
            '<br><br>',
            _heading(self._t('order_recurring', 'greeting', lang, **kw), brand),
            _text(self._t('order_recurring', 'body', lang, **kw), brand),
            _divider(brand),
            _text(self._t('order_recurring', 'all_set', lang, **kw), brand),
            _button(self._t('order_auto', 'btn_dashboard', lang), brand['dashboard_url'], brand, brand['accent_color']),
            _signature(brand['sender_name'], brand),
        ])
        return subject, _base_layout(content, brand)

    # ────────────────────────────────────────────
    # COMMANDE TERMINÉE
    # ────────────────────────────────────────────

    def _render_order_completed(self, lang, brand, tenant_id, **kw):
        subject = self._t('order_completed', 'subject', lang, **kw)

        content = ''.join([
            _badge('LIVRÉ', brand, brand['accent_color']),
            '<br><br>',
            _heading(self._t('order_completed', 'greeting', lang, **kw), brand),
            _text(self._t('order_completed', 'body', lang, **kw), brand),
            _button(self._t('order_completed', 'btn_dashboard', lang), brand['dashboard_url'], brand),
            _divider(brand),
            _text(self._t('order_completed', 'thanks', lang, **kw), brand),
            _signature(brand['sender_name'], brand),
        ])
        return subject, _base_layout(content, brand)

    # ────────────────────────────────────────────
    # COMMANDE EXPÉDIÉE
    # ────────────────────────────────────────────

    def _render_order_shipped(self, lang, brand, tenant_id, **kw):
        subject = self._t('order_shipped', 'subject', lang, **kw)
        tracking = kw.get('tracking_number', '')

        rows = [_info_row(self._t('order_pack', 'label_order', lang), kw.get('order_id', ''), brand)]
        if tracking:
            rows.append(_info_row(self._t('order_shipped', 'label_tracking', lang), tracking, brand))

        content = ''.join([
            _badge('EXPÉDIÉ', brand, brand['accent_color']),
            '<br><br>',
            _heading(self._t('order_human', 'greeting', lang, **kw), brand),
            _text(self._t('order_shipped', 'body', lang, **kw), brand),
            _info_table(rows, brand),
            _signature(brand['sender_name'], brand),
        ])
        return subject, _base_layout(content, brand)

    # ────────────────────────────────────────────
    # DEMANDE DE BRIEF
    # ────────────────────────────────────────────

    def _render_brief_request(self, lang, brand, tenant_id, **kw):
        subject = self._t('brief_request', 'subject', lang, **kw)
        brief_url = kw.get('brief_url', f"{brand['website']}/brief/{kw.get('order_id', '')}")

        content = ''.join([
            _heading(self._t('order_human', 'greeting', lang, **kw), brand),
            _text(self._t('brief_request', 'body', lang, **kw), brand),
            _button(self._t('brief_request', 'btn', lang), brief_url, brand),
            _text_small(
                {'fr': 'Dès que c\'est fait, on démarre !', 'en': 'Once done, we start!',
                 'nl': 'Zodra het klaar is, beginnen we!', 'de': 'Sobald Sie fertig sind, legen wir los!',
                 'es': '¡En cuanto esté listo, empezamos!'}.get(lang, 'Dès que c\'est fait, on démarre !'), brand),
            _signature(brand['sender_name'], brand),
        ])
        return subject, _base_layout(content, brand)


    # ────────────────────────────────────────────
    # BIENVENUE ORACLE + AGENTS AURUM
    # ────────────────────────────────────────────

    def _render_welcome_oracle(self, lang, brand, tenant_id, **kw):
        oracle_url   = 'https://digital-colosse.com/solaris.php'
        site_url     = brand.get('website', 'https://digital-colosse.com')
        plan_label   = kw.get('plan_label', 'ESSENCE')
        plan_members = kw.get('plan_members', '')
        next_level   = kw.get('next_level', '')
        ac = brand['accent_color']
        pc = brand['primary_color']
        tp = brand['text_primary']
        tm = brand['text_muted']
        bd = brand['border_color']
        bg = brand['bg_dark']

        sn_style = (
            'display:inline-block;width:28px;height:28px;'
            'background:#000;border:1px solid ' + ac + ';'
            'border-radius:50%;text-align:center;line-height:26px;'
            'font-size:11px;color:' + ac + ';font-weight:700;'
        )

        def step(n, title, body):
            return (
                '<table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="margin-bottom:20px;">'
                '<tr><td width="36" valign="top"><div style="' + sn_style + '">' + n + '</div></td>'
                '<td valign="top" style="padding-left:14px;">'
                '<p style="margin:0 0 5px;font-size:13px;font-weight:600;color:' + tp + ';">' + title + '</p>'
                '<p style="margin:0;font-size:12px;color:' + tm + ';line-height:1.8;">' + body + '</p>'
                '</td></tr></table>'
            )

        upsell = ''
        if next_level:
            upsell = (
                '<div style="margin:0 0 28px;background:' + bg + ';'
                'border:1px solid ' + bd + ';'
                'border-left:2px solid ' + ac + ';'
                'border-radius:4px;padding:16px 20px;">'
                '<p style="margin:0 0 6px;font-size:10px;letter-spacing:2px;color:' + ac + ';text-transform:uppercase;opacity:.8;">'
                + self._t('welcome_oracle', 'upsell_label', lang) + '</p>'
                '<p style="margin:0;font-size:12px;color:' + tm + ';line-height:1.8;">'
                + self._t('welcome_oracle', 'upsell_body', lang, next_level=next_level)
                + ' <a href="' + site_url + '" style="color:' + ac + ';text-decoration:none;">'
                + self._t('welcome_oracle', 'upsell_link', lang) + '</a>'
                '</p></div>'
            )

        badge = (
            '<div style="background:#050500;border:1px solid #2a2200;border-radius:8px;padding:22px 26px;margin-bottom:24px;">'
            '<table role="presentation" width="100%" cellspacing="0" cellpadding="0"><tr>'
            '<td><p style="margin:0 0 6px;font-size:10px;letter-spacing:3px;color:' + tm + ';text-transform:uppercase;">'
            + self._t('welcome_oracle', 'level_label', lang) + '</p>'
            '<p style="margin:0;font-size:24px;font-weight:700;letter-spacing:3px;color:' + pc + ';font-family:Georgia,serif;">' + plan_label + '</p></td>'
            '<td style="text-align:right;">'
            '<p style="margin:0 0 6px;font-size:10px;letter-spacing:3px;color:' + tm + ';text-transform:uppercase;">'
            + self._t('welcome_oracle', 'members_label', lang) + '</p>'
            '<p style="margin:0;font-size:13px;color:' + tp + ';">' + plan_members + '</p>'
            '</td></tr></table></div>'
        )

        content = ''.join([
            badge,
            _heading(self._t('welcome_oracle', 'greeting', lang, **kw), brand),
            _text(self._t('welcome_oracle', 'intro', lang, plan_label=plan_label), brand),
            _divider(brand),
            '<p style="margin:0 0 20px;font-size:10px;letter-spacing:3px;color:' + tm + ';text-transform:uppercase;">'
            + self._t('welcome_oracle', 'steps_title', lang) + '</p>',
            step('1', self._t('welcome_oracle', 'step1_title', lang),
                      self._t('welcome_oracle', 'step1_body', lang)),
            step('2', self._t('welcome_oracle', 'step2_title', lang),
                      self._t('welcome_oracle', 'step2_body', lang, plan_label=plan_label)),
            step('3', self._t('welcome_oracle', 'step3_title', lang),
                      self._t('welcome_oracle', 'step3_body', lang)),
            _button(self._t('welcome_oracle', 'btn', lang), oracle_url, brand),
            upsell,
            _text_small(self._t('welcome_oracle', 'footer', lang), brand),
            _signature(brand['sender_name'], brand),
        ])

        subject = self._t('welcome_oracle', 'subject', lang)
        return subject, _base_layout(content, brand)


    def _render_payment_failed(self, lang, brand, tenant_id, **kw):
        payment_url = kw.get('payment_url', 'https://digital-colosse.com/billing')
        ac = brand['accent_color']
        tm = brand['text_muted']
        warning_box = (
            '<div style="margin:20px 0;background:#1a0000;border:1px solid #4a0000;'
            'border-left:3px solid #ff4444;border-radius:6px;padding:16px 20px;">'
            '<p style="margin:0;font-size:13px;color:#ff6666;line-height:1.7;">'
            + self._t('payment_failed','warning',lang,**kw) + '</p></div>'
        )
        content = ''.join([
            _badge('⚠️ PAIEMENT ÉCHOUÉ', brand, '#ff4444'),
            '<br><br>',
            _heading(self._t('payment_failed','greeting',lang,**kw), brand),
            _text(self._t('payment_failed','body',lang,**kw), brand),
            warning_box,
            _button(self._t('payment_failed','btn',lang), payment_url, brand, '#ff4444'),
            _divider(brand),
            _text_small(self._t('payment_failed','help',lang), brand),
            _signature(brand['sender_name'], brand),
        ])
        subject = self._t('payment_failed','subject',lang,**kw)
        return subject, _base_layout(content, brand)

    def _render_invoice(self, lang, brand, tenant_id, **kw):
        oracle_url = 'https://digital-colosse.com/solaris.php'
        amount     = kw.get('amount','')
        plan_label = kw.get('plan_label','')
        inv_number = kw.get('invoice_number','')
        inv_date   = kw.get('invoice_date','')
        amount_ht  = kw.get('amount_ht','')
        amount_tva = kw.get('amount_tva','')
        rows = [
            _info_row(self._t('invoice','label_invoice',lang), inv_number, brand),
            _info_row(self._t('invoice','label_date',lang),    inv_date,   brand),
            _info_row(self._t('invoice','label_plan',lang),    plan_label, brand),
            _info_row(self._t('invoice','label_ht',lang),      amount_ht,  brand),
            _info_row(self._t('invoice','label_tva',lang),     amount_tva, brand),
            _info_row(self._t('invoice','label_ttc',lang),     amount,     brand),
        ]
        content = ''.join([
            _badge('FACTURE', brand, brand['primary_color']),
            '<br><br>',
            _heading(self._t('invoice','greeting',lang,**kw), brand),
            _text(self._t('invoice','body',lang,**kw), brand),
            _info_table(rows, brand),
            _button(self._t('invoice','btn',lang), oracle_url, brand),
            _divider(brand),
            _text_small(self._t('invoice','footer_note',lang), brand),
            _signature(brand['sender_name'], brand),
        ])
        subject = self._t('invoice','subject',lang,**kw)
        return subject, _base_layout(content, brand)

# ============================================================================
# INSTANCE GLOBALE
# ============================================================================

email_engine = EmailTemplateEngine()
