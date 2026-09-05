#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
╔════════════════════════════════════════════════════════════════════════╗
║  I18N ENGINE — Système multilingue Digital Colosse                    ║
║                                                                       ║
║  5 langues : FR, EN, NL, DE, ES                                      ║
║                                                                       ║
║  Deux modes :                                                         ║
║  ✅ Templates multilingues — emails transactionnels (fiable, précis) ║
║  ✅ Traduction IA à la volée — contenu dynamique (flexible)          ║
║                                                                       ║
║  Chaque agent appelle i18n.get(tenant_id, 'clé') et reçoit le        ║
║  texte dans la langue du tenant. C'est tout.                          ║
║                                                                       ║
║  Usage :                                                              ║
║    from i18n_engine import i18n                                       ║
║    subject = i18n.get(tenant_id, 'email.payment_confirm.subject',    ║
║                       amount='285€', brand=name)                      ║
║    body = i18n.get(tenant_id, 'email.payment_confirm.body', ...)     ║
║                                                                       ║
║  Digital Colosse — Mars 2026                                         ║
╚════════════════════════════════════════════════════════════════════════╝
"""

import os
import json
import logging
import requests
from typing import Dict, Optional, Any

logger = logging.getLogger('I18nEngine')


# ============================================================================
# LANGUES SUPPORTÉES
# ============================================================================

SUPPORTED_LANGUAGES = {
    'fr': {'name': 'Français', 'flag': '🇫🇷', 'default': True},
    'en': {'name': 'English', 'flag': '🇬🇧'},
    'nl': {'name': 'Nederlands', 'flag': '🇳🇱'},
    'de': {'name': 'Deutsch', 'flag': '🇩🇪'},
    'es': {'name': 'Español', 'flag': '🇪🇸'},
}

DEFAULT_LANGUAGE = 'fr'


# ============================================================================
# TEMPLATES MULTILINGUES
# ============================================================================

TEMPLATES = {

    # ════════════════════════════════════════════════════════
    # EMAILS TRANSACTIONNELS — Paiement
    # ════════════════════════════════════════════════════════

    'email.payment_confirm.subject': {
        'fr': 'Paiement confirmé — {brand_name}',
        'en': 'Payment confirmed — {brand_name}',
        'nl': 'Betaling bevestigd — {brand_name}',
        'de': 'Zahlung bestätigt — {brand_name}',
        'es': 'Pago confirmado — {brand_name}',
    },
    'email.payment_confirm.body': {
        'fr': '<h2>Merci {customer_name} !</h2><p>Votre paiement de {amount} a bien été reçu.</p><p>{brand_name}</p>',
        'en': '<h2>Thank you {customer_name}!</h2><p>Your payment of {amount} has been received.</p><p>{brand_name}</p>',
        'nl': '<h2>Bedankt {customer_name}!</h2><p>Uw betaling van {amount} is ontvangen.</p><p>{brand_name}</p>',
        'de': '<h2>Danke {customer_name}!</h2><p>Ihre Zahlung von {amount} wurde empfangen.</p><p>{brand_name}</p>',
        'es': '<h2>¡Gracias {customer_name}!</h2><p>Su pago de {amount} ha sido recibido.</p><p>{brand_name}</p>',
    },

    # ════════════════════════════════════════════════════════
    # EMAILS — Rappels métier
    # ════════════════════════════════════════════════════════

    # Garage — rappel entretien
    'email.maintenance_reminder.subject': {
        'fr': 'Rappel entretien — {brand_name}',
        'en': 'Service reminder — {brand_name}',
        'nl': 'Onderhoudsherinnering — {brand_name}',
        'de': 'Wartungserinnerung — {brand_name}',
        'es': 'Recordatorio de mantenimiento — {brand_name}',
    },
    'email.maintenance_reminder.body': {
        'fr': '<h2>Bonjour {customer_name} !</h2><p>Il est temps de penser à l\'entretien de votre {vehicle_make} {vehicle_model}.</p><p>Contactez-nous pour prendre rendez-vous.</p><p>{brand_name}</p>',
        'en': '<h2>Hello {customer_name}!</h2><p>It\'s time for your {vehicle_make} {vehicle_model} service.</p><p>Contact us to book an appointment.</p><p>{brand_name}</p>',
        'nl': '<h2>Hallo {customer_name}!</h2><p>Het is tijd voor het onderhoud van uw {vehicle_make} {vehicle_model}.</p><p>Neem contact met ons op voor een afspraak.</p><p>{brand_name}</p>',
        'de': '<h2>Hallo {customer_name}!</h2><p>Es ist Zeit für die Wartung Ihres {vehicle_make} {vehicle_model}.</p><p>Kontaktieren Sie uns für einen Termin.</p><p>{brand_name}</p>',
        'es': '<h2>¡Hola {customer_name}!</h2><p>Es hora del mantenimiento de su {vehicle_make} {vehicle_model}.</p><p>Contáctenos para reservar una cita.</p><p>{brand_name}</p>',
    },

    # Salon — rebooking
    'email.rebooking_reminder.subject': {
        'fr': 'C\'est le moment de reprendre RDV — {brand_name}',
        'en': 'Time to rebook — {brand_name}',
        'nl': 'Tijd om opnieuw te boeken — {brand_name}',
        'de': 'Zeit für einen neuen Termin — {brand_name}',
        'es': 'Es hora de reservar de nuevo — {brand_name}',
    },
    'email.rebooking_reminder.body': {
        'fr': '<h2>{customer_name}, on vous attend !</h2><p>Votre dernière visite remonte à quelques semaines. Prenez rendez-vous pour garder votre style au top.</p><p><a href="{booking_url}">Prendre RDV</a></p><p>{brand_name}</p>',
        'en': '<h2>{customer_name}, we miss you!</h2><p>It\'s been a few weeks since your last visit. Book now to keep your style on point.</p><p><a href="{booking_url}">Book now</a></p><p>{brand_name}</p>',
        'nl': '<h2>{customer_name}, we missen u!</h2><p>Het is een paar weken geleden sinds uw laatste bezoek. Maak een afspraak.</p><p><a href="{booking_url}">Nu boeken</a></p><p>{brand_name}</p>',
        'de': '<h2>{customer_name}, wir vermissen Sie!</h2><p>Ihr letzter Besuch ist einige Wochen her. Buchen Sie jetzt einen Termin.</p><p><a href="{booking_url}">Jetzt buchen</a></p><p>{brand_name}</p>',
        'es': '<h2>¡{customer_name}, le echamos de menos!</h2><p>Han pasado unas semanas desde su última visita. Reserve ahora.</p><p><a href="{booking_url}">Reservar</a></p><p>{brand_name}</p>',
    },

    # Véto — vaccination
    'email.vaccination_reminder.subject': {
        'fr': 'Rappel vaccin pour {pet_name} — {brand_name}',
        'en': 'Vaccination reminder for {pet_name} — {brand_name}',
        'nl': 'Vaccinatieherinnering voor {pet_name} — {brand_name}',
        'de': 'Impferinnerung für {pet_name} — {brand_name}',
        'es': 'Recordatorio de vacuna para {pet_name} — {brand_name}',
    },
    'email.vaccination_reminder.body': {
        'fr': '<h2>Rappel pour {pet_name}</h2><p>Le vaccin de {pet_name} arrive à échéance. Prenez rendez-vous.</p><p><a href="{booking_url}">Prendre RDV</a></p><p>{brand_name}</p>',
        'en': '<h2>Reminder for {pet_name}</h2><p>{pet_name}\'s vaccination is due. Please book an appointment.</p><p><a href="{booking_url}">Book now</a></p><p>{brand_name}</p>',
        'nl': '<h2>Herinnering voor {pet_name}</h2><p>De vaccinatie van {pet_name} is aan de beurt. Maak een afspraak.</p><p><a href="{booking_url}">Nu boeken</a></p><p>{brand_name}</p>',
        'de': '<h2>Erinnerung für {pet_name}</h2><p>Die Impfung von {pet_name} steht an. Bitte vereinbaren Sie einen Termin.</p><p><a href="{booking_url}">Jetzt buchen</a></p><p>{brand_name}</p>',
        'es': '<h2>Recordatorio para {pet_name}</h2><p>La vacuna de {pet_name} está pendiente. Reserve una cita.</p><p><a href="{booking_url}">Reservar</a></p><p>{brand_name}</p>',
    },

    # Dentiste — contrôle annuel
    'email.checkup_reminder.subject': {
        'fr': 'Contrôle annuel — {brand_name}',
        'en': 'Annual checkup — {brand_name}',
        'nl': 'Jaarlijkse controle — {brand_name}',
        'de': 'Jährliche Kontrolle — {brand_name}',
        'es': 'Revisión anual — {brand_name}',
    },
    'email.checkup_reminder.body': {
        'fr': '<h2>Bonjour {customer_name}</h2><p>Votre contrôle annuel est dû. Prenez rendez-vous.</p><p><a href="{booking_url}">Prendre RDV</a></p><p>{brand_name}</p>',
        'en': '<h2>Hello {customer_name}</h2><p>Your annual checkup is due. Please book an appointment.</p><p><a href="{booking_url}">Book now</a></p><p>{brand_name}</p>',
        'nl': '<h2>Hallo {customer_name}</h2><p>Uw jaarlijkse controle is aan de beurt. Maak een afspraak.</p><p><a href="{booking_url}">Nu boeken</a></p><p>{brand_name}</p>',
        'de': '<h2>Hallo {customer_name}</h2><p>Ihre jährliche Kontrolle steht an. Bitte vereinbaren Sie einen Termin.</p><p><a href="{booking_url}">Jetzt buchen</a></p><p>{brand_name}</p>',
        'es': '<h2>Hola {customer_name}</h2><p>Su revisión anual está pendiente. Reserve una cita.</p><p><a href="{booking_url}">Reservar</a></p><p>{brand_name}</p>',
    },

    # RDV — rappel rendez-vous
    'email.appointment_reminder.subject': {
        'fr': 'Rappel RDV demain — {brand_name}',
        'en': 'Appointment reminder — {brand_name}',
        'nl': 'Afspraakherinnering — {brand_name}',
        'de': 'Terminerinnerung — {brand_name}',
        'es': 'Recordatorio de cita — {brand_name}',
    },
    'email.appointment_reminder.body': {
        'fr': '<h2>Rappel</h2><p>{customer_name}, vous avez rendez-vous demain chez {brand_name}.</p><p>À bientôt !</p>',
        'en': '<h2>Reminder</h2><p>{customer_name}, you have an appointment tomorrow at {brand_name}.</p><p>See you soon!</p>',
        'nl': '<h2>Herinnering</h2><p>{customer_name}, u heeft morgen een afspraak bij {brand_name}.</p><p>Tot dan!</p>',
        'de': '<h2>Erinnerung</h2><p>{customer_name}, Sie haben morgen einen Termin bei {brand_name}.</p><p>Bis dann!</p>',
        'es': '<h2>Recordatorio</h2><p>{customer_name}, tiene una cita mañana en {brand_name}.</p><p>¡Hasta pronto!</p>',
    },

    # ════════════════════════════════════════════════════════
    # EMAILS — Commandes / Packs
    # ════════════════════════════════════════════════════════

    'email.order_confirm.subject': {
        'fr': 'Commande confirmée — {product_name}',
        'en': 'Order confirmed — {product_name}',
        'nl': 'Bestelling bevestigd — {product_name}',
        'de': 'Bestellung bestätigt — {product_name}',
        'es': 'Pedido confirmado — {product_name}',
    },
    'email.order_confirm.body': {
        'fr': '<h2>Merci {customer_name} !</h2><p>Votre commande <strong>{product_name}</strong> est confirmée.</p><p>Montant : {amount}</p><p>Délai estimé : {delivery_days} jours</p><p>Digital Colosse</p>',
        'en': '<h2>Thank you {customer_name}!</h2><p>Your order <strong>{product_name}</strong> is confirmed.</p><p>Amount: {amount}</p><p>Estimated delivery: {delivery_days} days</p><p>Digital Colosse</p>',
        'nl': '<h2>Bedankt {customer_name}!</h2><p>Uw bestelling <strong>{product_name}</strong> is bevestigd.</p><p>Bedrag: {amount}</p><p>Geschatte levertijd: {delivery_days} dagen</p><p>Digital Colosse</p>',
        'de': '<h2>Danke {customer_name}!</h2><p>Ihre Bestellung <strong>{product_name}</strong> ist bestätigt.</p><p>Betrag: {amount}</p><p>Geschätzte Lieferzeit: {delivery_days} Tage</p><p>Digital Colosse</p>',
        'es': '<h2>¡Gracias {customer_name}!</h2><p>Su pedido <strong>{product_name}</strong> está confirmado.</p><p>Monto: {amount}</p><p>Plazo estimado: {delivery_days} días</p><p>Digital Colosse</p>',
    },

    'email.order_completed.subject': {
        'fr': 'Votre {product_name} est prêt !',
        'en': 'Your {product_name} is ready!',
        'nl': 'Uw {product_name} is klaar!',
        'de': 'Ihr {product_name} ist fertig!',
        'es': '¡Su {product_name} está listo!',
    },
    'email.order_completed.body': {
        'fr': '<h2>{customer_name} !</h2><p>Votre <strong>{product_name}</strong> est terminé et livré.</p><p><a href="{dashboard_url}">Accéder à votre espace</a></p><p>Merci pour votre confiance !</p><p>David — Digital Colosse</p>',
        'en': '<h2>{customer_name}!</h2><p>Your <strong>{product_name}</strong> is completed and delivered.</p><p><a href="{dashboard_url}">Access your dashboard</a></p><p>Thank you for your trust!</p><p>David — Digital Colosse</p>',
        'nl': '<h2>{customer_name}!</h2><p>Uw <strong>{product_name}</strong> is voltooid en geleverd.</p><p><a href="{dashboard_url}">Naar uw dashboard</a></p><p>Bedankt voor uw vertrouwen!</p><p>David — Digital Colosse</p>',
        'de': '<h2>{customer_name}!</h2><p>Ihr <strong>{product_name}</strong> ist fertig und geliefert.</p><p><a href="{dashboard_url}">Zu Ihrem Dashboard</a></p><p>Danke für Ihr Vertrauen!</p><p>David — Digital Colosse</p>',
        'es': '<h2>¡{customer_name}!</h2><p>Su <strong>{product_name}</strong> está completado y entregado.</p><p><a href="{dashboard_url}">Acceder a su panel</a></p><p>¡Gracias por su confianza!</p><p>David — Digital Colosse</p>',
    },

    'email.order_shipped.subject': {
        'fr': 'Votre commande est expédiée !',
        'en': 'Your order has been shipped!',
        'nl': 'Uw bestelling is verzonden!',
        'de': 'Ihre Bestellung wurde versandt!',
        'es': '¡Su pedido ha sido enviado!',
    },

    # ════════════════════════════════════════════════════════
    # EMAILS — Onboarding followup
    # ════════════════════════════════════════════════════════

    'email.stripe_reminder.subject': {
        'fr': 'Connectez votre Stripe en 2 minutes',
        'en': 'Connect your Stripe in 2 minutes',
        'nl': 'Verbind uw Stripe in 2 minuten',
        'de': 'Verbinden Sie Ihr Stripe in 2 Minuten',
        'es': 'Conecte su Stripe en 2 minutos',
    },
    'email.stripe_help.subject': {
        'fr': 'Besoin d\'aide pour Stripe ?',
        'en': 'Need help with Stripe?',
        'nl': 'Hulp nodig met Stripe?',
        'de': 'Brauchen Sie Hilfe mit Stripe?',
        'es': '¿Necesita ayuda con Stripe?',
    },
    'email.trial_3days.subject': {
        'fr': 'Plus que 3 jours d\'essai',
        'en': 'Only 3 days left in your trial',
        'nl': 'Nog 3 dagen proefperiode',
        'de': 'Nur noch 3 Tage Testphase',
        'es': 'Solo quedan 3 días de prueba',
    },
    'email.trial_expired.subject': {
        'fr': 'Votre essai est terminé',
        'en': 'Your trial has ended',
        'nl': 'Uw proefperiode is verlopen',
        'de': 'Ihre Testphase ist beendet',
        'es': 'Su periodo de prueba ha terminado',
    },

    # ════════════════════════════════════════════════════════
    # SMS — Courts, directs
    # ════════════════════════════════════════════════════════

    'sms.maintenance_reminder': {
        'fr': '{customer_name}, votre {vehicle_make} {vehicle_model} est dû pour un entretien. {brand_name} {phone}',
        'en': '{customer_name}, your {vehicle_make} {vehicle_model} is due for service. {brand_name} {phone}',
        'nl': '{customer_name}, uw {vehicle_make} {vehicle_model} is toe aan onderhoud. {brand_name} {phone}',
        'de': '{customer_name}, Ihr {vehicle_make} {vehicle_model} braucht Wartung. {brand_name} {phone}',
        'es': '{customer_name}, su {vehicle_make} {vehicle_model} necesita mantenimiento. {brand_name} {phone}',
    },
    'sms.rebooking_reminder': {
        'fr': '{customer_name}, ça fait un moment ! Reprenez RDV chez {brand_name}. {booking_url}',
        'en': '{customer_name}, it\'s been a while! Rebook at {brand_name}. {booking_url}',
        'nl': '{customer_name}, het is een tijdje geleden! Boek opnieuw bij {brand_name}. {booking_url}',
        'de': '{customer_name}, es ist eine Weile her! Buchen Sie neu bei {brand_name}. {booking_url}',
        'es': '{customer_name}, ¡hace tiempo! Reserve de nuevo en {brand_name}. {booking_url}',
    },
    'sms.appointment_reminder': {
        'fr': '{customer_name}, rappel RDV demain chez {brand_name}.',
        'en': '{customer_name}, reminder: appointment tomorrow at {brand_name}.',
        'nl': '{customer_name}, herinnering: afspraak morgen bij {brand_name}.',
        'de': '{customer_name}, Erinnerung: Termin morgen bei {brand_name}.',
        'es': '{customer_name}, recordatorio: cita mañana en {brand_name}.',
    },
    'sms.vaccination_reminder': {
        'fr': 'Rappel: vaccin de {pet_name} à renouveler. {brand_name} {phone}',
        'en': 'Reminder: {pet_name}\'s vaccination is due. {brand_name} {phone}',
        'nl': 'Herinnering: vaccinatie van {pet_name} is aan de beurt. {brand_name} {phone}',
        'de': 'Erinnerung: Impfung von {pet_name} steht an. {brand_name} {phone}',
        'es': 'Recordatorio: vacuna de {pet_name} pendiente. {brand_name} {phone}',
    },

    # ════════════════════════════════════════════════════════
    # UI — Labels du dashboard
    # ════════════════════════════════════════════════════════

    'ui.dashboard.overview': {
        'fr': 'Vue d\'ensemble', 'en': 'Overview', 'nl': 'Overzicht', 'de': 'Übersicht', 'es': 'Resumen',
    },
    'ui.dashboard.contacts': {
        'fr': 'Contacts', 'en': 'Contacts', 'nl': 'Contacten', 'de': 'Kontakte', 'es': 'Contactos',
    },
    'ui.dashboard.transactions': {
        'fr': 'Transactions', 'en': 'Transactions', 'nl': 'Transacties', 'de': 'Transaktionen', 'es': 'Transacciones',
    },
    'ui.dashboard.tasks': {
        'fr': 'Tâches', 'en': 'Tasks', 'nl': 'Taken', 'de': 'Aufgaben', 'es': 'Tareas',
    },
    'ui.dashboard.assistant': {
        'fr': 'Assistant', 'en': 'Assistant', 'nl': 'Assistent', 'de': 'Assistent', 'es': 'Asistente',
    },
    'ui.dashboard.revenue': {
        'fr': 'Revenus', 'en': 'Revenue', 'nl': 'Inkomsten', 'de': 'Einnahmen', 'es': 'Ingresos',
    },
    'ui.dashboard.new_this_month': {
        'fr': 'Nouveaux ce mois', 'en': 'New this month', 'nl': 'Nieuw deze maand', 'de': 'Neu diesen Monat', 'es': 'Nuevos este mes',
    },
    'ui.dashboard.pending_tasks': {
        'fr': 'Tâches en attente', 'en': 'Pending tasks', 'nl': 'Openstaande taken', 'de': 'Offene Aufgaben', 'es': 'Tareas pendientes',
    },
    'ui.dashboard.recent_activity': {
        'fr': 'Activité récente', 'en': 'Recent activity', 'nl': 'Recente activiteit', 'de': 'Letzte Aktivität', 'es': 'Actividad reciente',
    },

    # ════════════════════════════════════════════════════════
    # INSIGHTS — Learning engine
    # ════════════════════════════════════════════════════════

    'insight.vip_threshold_high': {
        'fr': 'Votre seuil VIP ({threshold}€) est trop haut par rapport à votre ticket moyen ({avg}€). Aucun client n\'atteint ce seuil. Suggestion : baisser à {suggested}€.',
        'en': 'Your VIP threshold ({threshold}€) is too high compared to your average ticket ({avg}€). No client reaches this threshold. Suggestion: lower to {suggested}€.',
        'nl': 'Uw VIP-drempel ({threshold}€) is te hoog in vergelijking met uw gemiddeld ticket ({avg}€). Suggestie: verlaag naar {suggested}€.',
        'de': 'Ihr VIP-Schwellenwert ({threshold}€) ist zu hoch im Vergleich zu Ihrem Durchschnittsticket ({avg}€). Vorschlag: senken auf {suggested}€.',
        'es': 'Su umbral VIP ({threshold}€) es demasiado alto respecto a su ticket medio ({avg}€). Sugerencia: bajar a {suggested}€.',
    },
    'insight.high_activity': {
        'fr': 'Votre activité ({actual}/jour) dépasse largement votre estimation ({expected}/jour). Ajustement recommandé.',
        'en': 'Your activity ({actual}/day) significantly exceeds your estimate ({expected}/day). Adjustment recommended.',
        'nl': 'Uw activiteit ({actual}/dag) overtreft uw schatting ({expected}/dag) aanzienlijk. Aanpassing aanbevolen.',
        'de': 'Ihre Aktivität ({actual}/Tag) übersteigt Ihre Schätzung ({expected}/Tag) deutlich. Anpassung empfohlen.',
        'es': 'Su actividad ({actual}/día) supera ampliamente su estimación ({expected}/día). Se recomienda ajustar.',
    },
    'insight.suggest_sms': {
        'fr': 'Le SMS a un taux d\'ouverture de 98% vs 20% pour l\'email. Avec {contacts} contacts, activer le SMS augmenterait significativement l\'efficacité de vos rappels.',
        'en': 'SMS has a 98% open rate vs 20% for email. With {contacts} contacts, enabling SMS would significantly increase your reminder effectiveness.',
        'nl': 'SMS heeft een openingspercentage van 98% vs 20% voor e-mail. Met {contacts} contacten zou SMS de effectiviteit van uw herinneringen aanzienlijk verhogen.',
        'de': 'SMS hat eine Öffnungsrate von 98% vs 20% bei E-Mail. Mit {contacts} Kontakten würde SMS die Wirksamkeit Ihrer Erinnerungen deutlich steigern.',
        'es': 'Los SMS tienen una tasa de apertura del 98% vs 20% del email. Con {contacts} contactos, activar SMS mejoraría significativamente la eficacia de sus recordatorios.',
    },
}


# ============================================================================
# I18N ENGINE
# ============================================================================

class I18nEngine:
    """
    Moteur de traduction pour Digital Colosse.
    
    Usage par les agents :
        # Récupérer un texte traduit
        subject = i18n.get(tenant_id, 'email.payment_confirm.subject', 
                           brand_name='Garage Martin', amount='285€')
        
        # Traduire du contenu dynamique (via IA)
        translated = i18n.translate(tenant_id, 
                                     "Votre activité est en hausse de 30%")
        
        # Récupérer la langue d'un tenant
        lang = i18n.get_language(tenant_id)  # 'fr', 'en', 'nl', 'de', 'es'
    """

    def __init__(self):
        self._tenant_languages: Dict[str, str] = {}
        self._custom_templates: Dict[str, dict] = {}
        self._load()
        logger.info(f"🌍 I18nEngine initialisé — {len(SUPPORTED_LANGUAGES)} langues, {len(TEMPLATES)} templates")

    def _config_path(self):
        return os.path.join(
            os.getenv('AUTOMATION_DIR', '/opt/digital-colosse/automation'),
            'tenant_languages.json'
        )

    def _load(self):
        try:
            path = self._config_path()
            if os.path.exists(path):
                with open(path, 'r') as f:
                    self._tenant_languages = json.load(f)
        except Exception:
            pass

    def _save(self):
        try:
            path = self._config_path()
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, 'w') as f:
                json.dump(self._tenant_languages, f, indent=2)
        except Exception as e:
            logger.error(f"Erreur sauvegarde langues: {e}")

    # ────────────────────────────────────────────
    # LANGUE DU TENANT
    # ────────────────────────────────────────────

    def set_language(self, tenant_id: str, language: str):
        """Définit la langue d'un tenant"""
        if language not in SUPPORTED_LANGUAGES:
            logger.warning(f"Langue non supportée: {language}, fallback fr")
            language = DEFAULT_LANGUAGE
        self._tenant_languages[tenant_id] = language
        self._save()
        logger.info(f"🌍 Langue {tenant_id} → {SUPPORTED_LANGUAGES[language]['flag']} {language}")

    def get_language(self, tenant_id: str) -> str:
        """Récupère la langue d'un tenant"""
        return self._tenant_languages.get(tenant_id, DEFAULT_LANGUAGE)

    # ────────────────────────────────────────────
    # TEMPLATES — Textes pré-traduits
    # ────────────────────────────────────────────

    def get(self, tenant_id: str, key: str, **kwargs) -> str:
        """
        Récupère un texte traduit avec les variables remplacées.
        
        i18n.get('garage_martin', 'email.payment_confirm.subject', 
                 brand_name='Garage Martin')
        → "Paiement confirmé — Garage Martin" (si tenant est fr)
        → "Payment confirmed — Garage Martin" (si tenant est en)
        """
        lang = self.get_language(tenant_id)

        # Chercher d'abord dans les templates custom du tenant
        custom_key = f"{tenant_id}:{key}"
        if custom_key in self._custom_templates:
            template = self._custom_templates[custom_key].get(lang)
            if template:
                return self._format_safe(template, kwargs)

        # Sinon dans les templates globaux
        template_set = TEMPLATES.get(key)
        if not template_set:
            logger.warning(f"Template inconnu: {key}")
            return key

        # Langue demandée → fallback FR → clé brute
        template = template_set.get(lang) or template_set.get(DEFAULT_LANGUAGE, key)
        return self._format_safe(template, kwargs)

    def get_sms(self, tenant_id: str, key: str, **kwargs) -> str:
        """Raccourci pour les templates SMS"""
        sms_key = f"sms.{key}" if not key.startswith('sms.') else key
        return self.get(tenant_id, sms_key, **kwargs)

    def get_email(self, tenant_id: str, template_name: str, **kwargs) -> tuple:
        """Récupère sujet + corps d'un email traduit"""
        subject = self.get(tenant_id, f'email.{template_name}.subject', **kwargs)
        body = self.get(tenant_id, f'email.{template_name}.body', **kwargs)
        return subject, body

    def get_ui(self, tenant_id: str, key: str) -> str:
        """Récupère un label UI traduit"""
        ui_key = f"ui.{key}" if not key.startswith('ui.') else key
        return self.get(tenant_id, ui_key)

    # ────────────────────────────────────────────
    # TRADUCTION IA — Contenu dynamique
    # ────────────────────────────────────────────

    def translate(self, tenant_id: str, text: str, source_lang: str = 'fr') -> str:
        """
        Traduit du texte dynamique via l'API Claude.
        Pour les insights, rapports, et messages générés.
        """
        target_lang = self.get_language(tenant_id)
        if target_lang == source_lang:
            return text

        lang_name = SUPPORTED_LANGUAGES.get(target_lang, {}).get('name', target_lang)
        api_key = os.getenv('ANTHROPIC_API_KEY', '')

        if not api_key:
            logger.warning("Pas de clé API Anthropic — traduction impossible")
            return text

        try:
            response = requests.post(
                'https://api.anthropic.com/v1/messages',
                headers={
                    'x-api-key': api_key,
                    'anthropic-version': '2023-06-01',
                    'content-type': 'application/json',
                },
                json={
                    'model': 'claude-sonnet-4-20250514',
                    'max_tokens': 1000,
                    'messages': [{
                        'role': 'user',
                        'content': (
                            f"Translate the following text to {lang_name}. "
                            f"Keep the same tone and formatting. "
                            f"Return ONLY the translated text, nothing else.\n\n"
                            f"{text}"
                        ),
                    }],
                },
                timeout=15,
            )

            if response.status_code == 200:
                data = response.json()
                translated = data.get('content', [{}])[0].get('text', text)
                return translated.strip()
            else:
                logger.error(f"Traduction API erreur {response.status_code}")
                return text

        except Exception as e:
            logger.error(f"Traduction erreur: {e}")
            return text

    def translate_insight(self, tenant_id: str, insight_key: str, **kwargs) -> str:
        """Traduit un insight du learning engine"""
        return self.get(tenant_id, f'insight.{insight_key}', **kwargs)

    # ────────────────────────────────────────────
    # TEMPLATES CUSTOM (par tenant)
    # ────────────────────────────────────────────

    def set_custom_template(self, tenant_id: str, key: str, translations: dict):
        """
        Permet à un tenant de personnaliser un template dans sa langue.
        Ex: un garagiste qui veut changer le texte du rappel entretien.
        """
        custom_key = f"{tenant_id}:{key}"
        self._custom_templates[custom_key] = translations
        logger.info(f"📝 Template custom: {tenant_id} → {key}")

    # ────────────────────────────────────────────
    # API
    # ────────────────────────────────────────────

    def get_supported_languages(self) -> dict:
        return SUPPORTED_LANGUAGES

    def get_all_templates(self, language: str = 'fr') -> dict:
        """Retourne tous les templates dans une langue"""
        result = {}
        for key, translations in TEMPLATES.items():
            result[key] = translations.get(language, translations.get(DEFAULT_LANGUAGE, ''))
        return result

    # ────────────────────────────────────────────
    # HELPERS
    # ────────────────────────────────────────────

    def _format_safe(self, template: str, kwargs: dict) -> str:
        """Format avec gestion des variables manquantes"""
        try:
            return template.format(**{k: v for k, v in kwargs.items() if isinstance(v, (str, int, float))})
        except KeyError as e:
            logger.warning(f"Variable manquante dans template: {e}")
            # Remplacer les variables manquantes par des placeholders
            import re
            for match in re.finditer(r'\{(\w+)\}', template):
                var = match.group(1)
                if var not in kwargs:
                    template = template.replace(f'{{{var}}}', f'[{var}]')
            try:
                return template.format(**{k: v for k, v in kwargs.items() if isinstance(v, (str, int, float))})
            except:
                return template


# ============================================================================
# INSTANCE GLOBALE
# ============================================================================

i18n = I18nEngine()
