"""
═══════════════════════════════════════════════════════════
SARTORIAL AGENTIC — Backend i18n
Used for transactional emails, webhook notifications,
and server-side localized responses.
═══════════════════════════════════════════════════════════
"""

from typing import Any

SUPPORTED_LOCALES = {"fr", "en", "de", "nl", "es"}
DEFAULT_LOCALE = "fr"


# Email templates localized (body + subject)
EMAIL_TEMPLATES: dict[str, dict[str, dict[str, str]]] = {
    "welcome": {
        "fr": {
            "subject": "Bienvenue dans votre atelier Sartorial Agentic",
            "greeting": "Bienvenue {name},",
            "intro": "Votre atelier « {workshop} » est prêt. Votre période d'essai de 14 jours commence maintenant.",
            "cta": "Accéder à mon atelier",
            "signature": "À très bientôt,\n— Votre Tailleur",
        },
        "en": {
            "subject": "Welcome to your Sartorial Agentic atelier",
            "greeting": "Welcome {name},",
            "intro": "Your atelier \"{workshop}\" is ready. Your 14-day trial starts now.",
            "cta": "Access my atelier",
            "signature": "See you very soon,\n— Your Tailor",
        },
        "de": {
            "subject": "Willkommen in Ihrem Sartorial Agentic Atelier",
            "greeting": "Willkommen {name},",
            "intro": "Ihr Atelier „{workshop}“ ist bereit. Ihre 14-tägige Testphase beginnt jetzt.",
            "cta": "Zu meinem Atelier",
            "signature": "Bis bald,\n— Ihr Schneider",
        },
        "nl": {
            "subject": "Welkom in uw Sartorial Agentic atelier",
            "greeting": "Welkom {name},",
            "intro": "Uw atelier \"{workshop}\" is klaar. Uw proefperiode van 14 dagen begint nu.",
            "cta": "Naar mijn atelier",
            "signature": "Tot snel,\n— Uw Kleermaker",
        },
        "es": {
            "subject": "Bienvenido a su atelier Sartorial Agentic",
            "greeting": "Bienvenido {name},",
            "intro": "Su atelier «{workshop}» está listo. Su prueba de 14 días comienza ahora.",
            "cta": "Acceder a mi atelier",
            "signature": "Hasta muy pronto,\n— Su Sastre",
        },
    },

    "payment_failed": {
        "fr": {
            "subject": "Problème de paiement sur votre atelier",
            "greeting": "Bonjour,",
            "intro": "Nous n'avons pas pu traiter votre dernier paiement pour l'atelier « {workshop} ».",
            "cta": "Mettre à jour mon paiement",
            "signature": "— Votre Tailleur",
        },
        "en": {
            "subject": "Payment issue on your atelier",
            "greeting": "Hello,",
            "intro": "We couldn't process your latest payment for the \"{workshop}\" atelier.",
            "cta": "Update payment method",
            "signature": "— Your Tailor",
        },
        "de": {
            "subject": "Zahlungsproblem in Ihrem Atelier",
            "greeting": "Hallo,",
            "intro": "Wir konnten Ihre letzte Zahlung für das Atelier „{workshop}“ nicht verarbeiten.",
            "cta": "Zahlungsmethode aktualisieren",
            "signature": "— Ihr Schneider",
        },
        "nl": {
            "subject": "Betalingsprobleem in uw atelier",
            "greeting": "Hallo,",
            "intro": "We konden uw laatste betaling voor atelier \"{workshop}\" niet verwerken.",
            "cta": "Betalingsmethode bijwerken",
            "signature": "— Uw Kleermaker",
        },
        "es": {
            "subject": "Problema de pago en su atelier",
            "greeting": "Hola,",
            "intro": "No pudimos procesar su último pago para el atelier «{workshop}».",
            "cta": "Actualizar método de pago",
            "signature": "— Su Sastre",
        },
    },

    "trial_ending": {
        "fr": {
            "subject": "Votre essai se termine dans 3 jours",
            "greeting": "Bonjour,",
            "intro": "Il vous reste 3 jours d'essai sur votre atelier « {workshop} ». Choisissez votre formule pour continuer sans interruption.",
            "cta": "Choisir ma formule",
            "signature": "— Votre Tailleur",
        },
        "en": {
            "subject": "Your trial ends in 3 days",
            "greeting": "Hello,",
            "intro": "You have 3 trial days left on your \"{workshop}\" atelier. Choose your plan to continue without interruption.",
            "cta": "Choose my plan",
            "signature": "— Your Tailor",
        },
        "de": {
            "subject": "Ihr Test endet in 3 Tagen",
            "greeting": "Hallo,",
            "intro": "Sie haben noch 3 Testtage für Ihr Atelier „{workshop}“. Wählen Sie Ihren Tarif, um nahtlos fortzufahren.",
            "cta": "Meinen Tarif wählen",
            "signature": "— Ihr Schneider",
        },
        "nl": {
            "subject": "Uw proefperiode eindigt over 3 dagen",
            "greeting": "Hallo,",
            "intro": "U heeft nog 3 proefdagen voor uw atelier \"{workshop}\". Kies uw plan om ononderbroken door te gaan.",
            "cta": "Mijn plan kiezen",
            "signature": "— Uw Kleermaker",
        },
        "es": {
            "subject": "Su prueba termina en 3 días",
            "greeting": "Hola,",
            "intro": "Le quedan 3 días de prueba en su atelier «{workshop}». Elija su plan para continuar sin interrupción.",
            "cta": "Elegir mi plan",
            "signature": "— Su Sastre",
        },
    },
}


def normalize_locale(code: str | None) -> str:
    """Normalize a locale code (accepts 'fr-FR', 'FR', etc.)."""
    if not code:
        return DEFAULT_LOCALE
    base = code.lower().split("-")[0].split("_")[0].strip()
    return base if base in SUPPORTED_LOCALES else DEFAULT_LOCALE


def get_email_template(
    template_name: str,
    locale: str,
    **vars: Any,
) -> dict[str, str]:
    """
    Return a localized email template with interpolated variables.
    Returns dict with keys: subject, greeting, intro, cta, signature.
    """
    locale = normalize_locale(locale)
    templates = EMAIL_TEMPLATES.get(template_name, {})
    template = templates.get(locale) or templates.get(DEFAULT_LOCALE, {})

    return {
        key: value.format(**vars) if isinstance(value, str) else value
        for key, value in template.items()
    }
