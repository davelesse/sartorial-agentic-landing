#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
═══════════════════════════════════════════════════════════════
   I18N ENGINE — Digital Colosse
   Gestion des langues par tenant pour les emails brandés.
═══════════════════════════════════════════════════════════════
"""

import os
import logging

logger = logging.getLogger('I18nEngine')

SUPPORTED_LANGS = {'fr', 'en', 'nl', 'de', 'es'}
DEFAULT_LANG = 'fr'

# Mapping des codes locaux courants vers les langues supportées
_LOCALE_MAP = {
    'fr': 'fr', 'fr-fr': 'fr', 'fr-be': 'fr', 'fr-ch': 'fr', 'fr-ca': 'fr',
    'en': 'en', 'en-us': 'en', 'en-gb': 'en', 'en-au': 'en', 'en-ca': 'en',
    'nl': 'nl', 'nl-nl': 'nl', 'nl-be': 'nl',
    'de': 'de', 'de-de': 'de', 'de-at': 'de', 'de-ch': 'de',
    'es': 'es', 'es-es': 'es', 'es-mx': 'es', 'es-ar': 'es',
}


def normalize_lang(code: str | None) -> str:
    """Normalise un code langue/locale vers l'une des 5 langues supportées."""
    if not code:
        return DEFAULT_LANG
    normalized = _LOCALE_MAP.get(code.lower().strip())
    if normalized:
        return normalized
    base = code.lower().split('-')[0].split('_')[0]
    return base if base in SUPPORTED_LANGS else DEFAULT_LANG


class I18nEngine:
    """
    Moteur i18n pour Digital Colosse.

    Stocke la langue préférée par tenant et fournit une interface
    unifiée utilisée par EmailTemplateEngine.set_dependencies(i18n=...).

    Usage :
        from i18n_engine import i18n_engine
        i18n_engine.set_language('digital-colosse', 'fr')
        lang = i18n_engine.get_language('digital-colosse')
    """

    def __init__(self):
        # tenant_id -> lang
        self._registry: dict[str, str] = {}
        # Langue par défaut issue de l'env (LANG_DEFAULT=en, etc.)
        self._default = normalize_lang(os.getenv('LANG_DEFAULT', DEFAULT_LANG))

    def set_language(self, tenant_id: str, lang: str) -> None:
        """Enregistre la langue préférée d'un tenant."""
        normalized = normalize_lang(lang)
        self._registry[tenant_id] = normalized
        logger.debug(f"i18n: tenant={tenant_id} lang={normalized}")

    def get_language(self, tenant_id: str) -> str:
        """Retourne la langue du tenant (défaut si inconnu)."""
        return self._registry.get(tenant_id, self._default)

    def detect_and_set(self, tenant_id: str, accept_language: str) -> str:
        """
        Détecte la langue depuis un header Accept-Language HTTP
        et l'enregistre pour le tenant.
        Ex : 'fr-FR,fr;q=0.9,en;q=0.8' → 'fr'
        """
        lang = DEFAULT_LANG
        if accept_language:
            for part in accept_language.split(','):
                code = part.split(';')[0].strip()
                candidate = normalize_lang(code)
                if candidate != DEFAULT_LANG or code.lower().startswith('fr'):
                    lang = candidate
                    break
        self.set_language(tenant_id, lang)
        return lang

    def supported_langs(self) -> list[str]:
        return sorted(SUPPORTED_LANGS)


# Instance globale partagée par api_server.py et email_templates.py
i18n_engine = I18nEngine()
