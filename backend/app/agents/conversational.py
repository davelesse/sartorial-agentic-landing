"""
═══════════════════════════════════════════════════════════
SARTORIAL AGENTIC — Conversational Agent
Agent conversationnel agentique avec :
  - Mémoire persistante par visiteur (Redis + PostgreSQL)
  - Profiling dynamique (métier, expertise, intentions, ton)
  - Adaptation au secteur du tenant hôte
  - Multilingue natif (FR, EN, DE, NL, ES)
  - Tool use pour actions réelles (lead creation, RDV, email)
  - Streaming des réponses
═══════════════════════════════════════════════════════════
"""

import json
from datetime import datetime, timezone
from typing import AsyncGenerator
from uuid import UUID

import structlog
from anthropic import AsyncAnthropic

from app.agents.base import BaseAgent, CLAUDE_MODEL_BALANCED, CLAUDE_MODEL_FAST
from app.core.config import settings

logger = structlog.get_logger()

# ─────────────────────────────────────
# LANGUAGES SUPPORTED
# ─────────────────────────────────────

SUPPORTED_LANGUAGES = {"fr", "en", "de", "nl", "es"}
DEFAULT_LANGUAGE = "fr"

LANGUAGE_NAMES = {
    "fr": "français",
    "en": "English",
    "de": "Deutsch",
    "nl": "Nederlands",
    "es": "español",
}


# ─────────────────────────────────────
# SECTOR-SPECIFIC PERSONAS
# ─────────────────────────────────────

SECTOR_PERSONAS = {
    "automobile": {
        "name": "un conseiller automobile expérimenté",
        "tone_fr": "expert, passionné, précis sur les détails techniques",
        "tone_en": "expert, passionate, precise on technical details",
        "tone_de": "sachkundig, leidenschaftlich, technisch präzise",
        "tone_nl": "deskundig, gepassioneerd, technisch precies",
        "tone_es": "experto, apasionado, preciso en los detalles técnicos",
        "greeting_fr": "Je suis votre conseiller. Quel véhicule vous intéresse ?",
        "greeting_en": "I'm your advisor. Which vehicle interests you?",
        "greeting_de": "Ich bin Ihr Berater. Welches Fahrzeug interessiert Sie?",
        "greeting_nl": "Ik ben uw adviseur. Welk voertuig interesseert u?",
        "greeting_es": "Soy su asesor. ¿Qué vehículo le interesa?",
    },
    "immobilier": {
        "name": "un conseiller immobilier de confiance",
        "tone_fr": "rassurant, discret, à l'écoute des projets de vie",
        "tone_en": "reassuring, discreet, attentive to life projects",
        "tone_de": "vertrauenswürdig, diskret, aufmerksam",
        "tone_nl": "geruststellend, discreet, aandachtig",
        "tone_es": "tranquilizador, discreto, atento",
        "greeting_fr": "Bienvenue. Parlez-moi de votre projet immobilier.",
        "greeting_en": "Welcome. Tell me about your real estate project.",
        "greeting_de": "Willkommen. Erzählen Sie mir von Ihrem Immobilienprojekt.",
        "greeting_nl": "Welkom. Vertel me over uw vastgoedproject.",
        "greeting_es": "Bienvenido. Cuénteme sobre su proyecto inmobiliario.",
    },
    "ecommerce": {
        "name": "un assistant shopping attentif",
        "tone_fr": "dynamique, conseil orienté besoin, jamais pressant",
        "tone_en": "dynamic, needs-focused advice, never pushy",
        "tone_de": "dynamisch, bedürfnisorientiert, nie aufdringlich",
        "tone_nl": "dynamisch, behoefte-gericht, nooit opdringerig",
        "tone_es": "dinámico, centrado en las necesidades, nunca insistente",
        "greeting_fr": "Bonjour ! Que recherchez-vous aujourd'hui ?",
        "greeting_en": "Hello! What are you looking for today?",
        "greeting_de": "Hallo! Wonach suchen Sie heute?",
        "greeting_nl": "Hallo! Waar bent u vandaag naar op zoek?",
        "greeting_es": "¡Hola! ¿Qué está buscando hoy?",
    },
    "beaute": {
        "name": "une conseillère beauté raffinée",
        "tone_fr": "élégante, bienveillante, experte en rituels",
        "tone_en": "elegant, caring, expert in beauty rituals",
        "tone_de": "elegant, fürsorglich, Expertin für Rituale",
        "tone_nl": "elegant, zorgzaam, expert in rituelen",
        "tone_es": "elegante, atenta, experta en rituales",
        "greeting_fr": "Bienvenue dans notre atelier. Quel soin vous tente ?",
        "greeting_en": "Welcome to our atelier. Which treatment appeals to you?",
        "greeting_de": "Willkommen in unserem Atelier. Welche Behandlung spricht Sie an?",
        "greeting_nl": "Welkom in ons atelier. Welke behandeling spreekt u aan?",
        "greeting_es": "Bienvenida a nuestro atelier. ¿Qué tratamiento le apetece?",
    },
    "sante": {
        "name": "un assistant médical bienveillant",
        "tone_fr": "calme, rassurant, jamais de diagnostic — seulement orientation",
        "tone_en": "calm, reassuring, never diagnosing — only guidance",
        "tone_de": "ruhig, beruhigend, niemals Diagnose — nur Orientierung",
        "tone_nl": "kalm, geruststellend, nooit diagnose — alleen begeleiding",
        "tone_es": "tranquilo, tranquilizador, nunca diagnóstico — solo orientación",
        "greeting_fr": "Bonjour. Comment puis-je vous aider aujourd'hui ?",
        "greeting_en": "Hello. How can I help you today?",
        "greeting_de": "Guten Tag. Wie kann ich Ihnen heute helfen?",
        "greeting_nl": "Hallo. Hoe kan ik u vandaag helpen?",
        "greeting_es": "Buenos días. ¿Cómo puedo ayudarle hoy?",
    },
    "restauration": {
        "name": "un maître d'hôtel chaleureux",
        "tone_fr": "accueillant, gourmand, fier de la carte",
        "tone_en": "welcoming, gourmet, proud of the menu",
        "tone_de": "einladend, genussvoll, stolz auf die Karte",
        "tone_nl": "gastvrij, genietend, trots op de kaart",
        "tone_es": "acogedor, gourmet, orgulloso de la carta",
        "greeting_fr": "Bonsoir ! Souhaitez-vous réserver une table ?",
        "greeting_en": "Good evening! Would you like to book a table?",
        "greeting_de": "Guten Abend! Möchten Sie einen Tisch reservieren?",
        "greeting_nl": "Goedenavond! Wilt u een tafel reserveren?",
        "greeting_es": "¡Buenas noches! ¿Desea reservar una mesa?",
    },
}


# ─────────────────────────────────────
# VISITOR PROFILE
# ─────────────────────────────────────

class VisitorProfile:
    """
    Profil dynamique d'un visiteur, enrichi à chaque message.
    Stocké en Redis (TTL 30 jours) + synchronisé en PostgreSQL.
    """
    def __init__(self, visitor_id: str, tenant_id: str):
        self.visitor_id = visitor_id
        self.tenant_id = tenant_id
        self.language: str = DEFAULT_LANGUAGE
        self.detected_profession: str | None = None
        self.expertise_level: str = "unknown"   # novice | intermediate | expert
        self.preferred_tone: str = "neutral"    # formal | casual | premium
        self.intentions: list[str] = []         # ["buy", "research", "compare", "book_appointment"]
        self.products_viewed: list[str] = []
        self.pain_points: list[str] = []
        self.first_seen: str = datetime.now(timezone.utc).isoformat()
        self.last_seen: str = datetime.now(timezone.utc).isoformat()
        self.message_count: int = 0
        self.custom_facts: dict = {}            # Faits mémorables mentionnés

    def to_dict(self) -> dict:
        return {
            "visitor_id":          self.visitor_id,
            "tenant_id":           self.tenant_id,
            "language":            self.language,
            "detected_profession": self.detected_profession,
            "expertise_level":     self.expertise_level,
            "preferred_tone":      self.preferred_tone,
            "intentions":          self.intentions,
            "products_viewed":     self.products_viewed,
            "pain_points":         self.pain_points,
            "first_seen":          self.first_seen,
            "last_seen":           self.last_seen,
            "message_count":       self.message_count,
            "custom_facts":        self.custom_facts,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "VisitorProfile":
        p = cls(data["visitor_id"], data["tenant_id"])
        for key, value in data.items():
            if hasattr(p, key):
                setattr(p, key, value)
        return p

    def summarize_for_prompt(self) -> str:
        """Génère un résumé textuel du profil pour injection dans le system prompt."""
        lines = []
        if self.detected_profession:
            lines.append(f"- Métier probable : {self.detected_profession}")
        if self.expertise_level != "unknown":
            lines.append(f"- Niveau d'expertise : {self.expertise_level}")
        if self.preferred_tone != "neutral":
            lines.append(f"- Ton préféré : {self.preferred_tone}")
        if self.intentions:
            lines.append(f"- Intentions détectées : {', '.join(self.intentions)}")
        if self.products_viewed:
            lines.append(f"- Produits/sujets consultés : {', '.join(self.products_viewed[-5:])}")
        if self.pain_points:
            lines.append(f"- Préoccupations exprimées : {', '.join(self.pain_points[-3:])}")
        if self.custom_facts:
            facts = [f"{k}={v}" for k, v in list(self.custom_facts.items())[:5]]
            lines.append(f"- Faits mémorisés : {', '.join(facts)}")
        lines.append(f"- Nombre de messages échangés : {self.message_count}")
        return "\n".join(lines) if lines else "(Premier contact — aucune info préalable)"


# ─────────────────────────────────────
# CONVERSATIONAL AGENT
# ─────────────────────────────────────

class ConversationalAgent(BaseAgent):
    """
    Agent conversationnel agentique.
    Contrairement à un chatbot classique :
      - Profile le visiteur en continu
      - Adapte dynamiquement son ton et son vocabulaire
      - Utilise des tools pour AGIR (pas juste répondre)
      - Se souvient entre les sessions
      - Multilingue avec détection automatique
    """

    slug = "conversational"
    name = "Agent Conversationnel"
    default_model = CLAUDE_MODEL_BALANCED

    def __init__(
        self,
        tenant_id: str,
        tenant_name: str = "",
        tenant_sector: str = "ecommerce",
        tenant_config: dict | None = None,
    ):
        super().__init__(tenant_id=tenant_id, config=tenant_config)
        self.tenant_name = tenant_name
        self.tenant_sector = tenant_sector
        self.persona = SECTOR_PERSONAS.get(tenant_sector, SECTOR_PERSONAS["ecommerce"])

    async def run(self, input_data: dict) -> dict:
        """Implémentation BaseAgent — délègue à chat_stream pour les appels Celery."""
        return {
            "message": "ConversationalAgent s'utilise via chat_stream() pour le streaming temps réel.",
            "tenant_id": self.tenant_id,
            "sector": self.tenant_sector,
        }

    def _build_system_prompt(
        self,
        profile: VisitorProfile,
        conversation_summary: str | None = None,
    ) -> str:
        """Construit un system prompt adaptatif basé sur le profil du visiteur."""
        lang = profile.language if profile.language in SUPPORTED_LANGUAGES else DEFAULT_LANGUAGE
        tone_key = f"tone_{lang}"
        tone = self.persona.get(tone_key, self.persona["tone_fr"])

        language_instruction = {
            "fr": "Tu réponds systématiquement en français.",
            "en": "You always respond in English.",
            "de": "Du antwortest ausschließlich auf Deutsch.",
            "nl": "Je antwoordt altijd in het Nederlands.",
            "es": "Respondes siempre en español.",
        }[lang]

        base = f"""Tu es l'assistant conversationnel officiel de "{self.tenant_name}".

IDENTITÉ : {self.persona['name']}
SECTEUR : {self.tenant_sector}
TON : {tone}

LANGUE : {language_instruction} Si le visiteur change de langue en cours de conversation, adapte-toi immédiatement à sa nouvelle langue.

PROFIL DU VISITEUR (mis à jour à chaque message) :
{profile.summarize_for_prompt()}

{"RÉSUMÉ DES ÉCHANGES PRÉCÉDENTS : " + conversation_summary if conversation_summary else ""}

RÈGLES STRICTES :
1. Tu ADAPTES ton vocabulaire au profil détecté. Avec un expert : technique. Avec un novice : pédagogique. Avec un prospect premium : raffiné.
2. Tu POSES DES QUESTIONS pour qualifier l'interlocuteur quand utile — mais jamais plus d'une question par message.
3. Tu AGIS via tes tools quand c'est pertinent (prise de RDV, création de lead, envoi d'info, recherche produit). Tu ne te contentes pas de répondre.
4. Tu RESTES dans le périmètre du secteur "{self.tenant_sector}" de "{self.tenant_name}". Si on te demande autre chose, tu rediriges poliment.
5. Tu NE DONNES JAMAIS d'informations que tu n'as pas. Si tu ne sais pas, tu utilises un tool ou tu dis que tu vas te renseigner.
6. Tu NE MENS JAMAIS sur tes capacités. Tu es une IA, et tu l'assumes si on te le demande directement.
7. Tu RESTES BREF : 2-4 phrases par message sauf si on te demande un détail long.
8. Tu TERMINES chaque message par une ouverture naturelle (question, proposition d'action).

INTERDITS ABSOLUS :
- Ne promets jamais de prix, délais ou disponibilités que tu n'as pas vérifiés via un tool.
- Ne diagnostique jamais (santé), n'estime jamais (immobilier), ne conseille jamais légalement (finance). Redirige vers un humain.
- Ne fais pas de scripts de vente agressifs. Tu es conseiller, pas vendeur à la criée.
"""
        return base

    def _get_tools(self) -> list[dict]:
        """
        Outils disponibles pour l'agent (tool use Anthropic API).
        Chaque secteur peut avoir ses tools spécifiques — pour l'instant on définit les transversaux.
        """
        return [
            {
                "name": "capture_lead",
                "description": "Capture un lead qualifié (nom, email, téléphone, besoin). À utiliser dès qu'un visiteur exprime un intérêt concret et partage ses coordonnées.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "name":        {"type": "string", "description": "Nom complet du visiteur"},
                        "email":       {"type": "string", "description": "Email du visiteur"},
                        "phone":       {"type": "string", "description": "Téléphone (optionnel)"},
                        "need_summary":{"type": "string", "description": "Résumé en 1-2 phrases du besoin exprimé"},
                        "urgency":     {"type": "string", "enum": ["low", "medium", "high"]},
                    },
                    "required": ["email", "need_summary"],
                },
            },
            {
                "name": "book_appointment",
                "description": "Réserve un rendez-vous dans l'agenda du tenant.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "visitor_name":  {"type": "string"},
                        "visitor_email": {"type": "string"},
                        "preferred_date":{"type": "string", "description": "Format ISO 8601"},
                        "duration_minutes": {"type": "integer"},
                        "topic":         {"type": "string"},
                    },
                    "required": ["visitor_email", "preferred_date", "topic"],
                },
            },
            {
                "name": "search_catalog",
                "description": "Recherche dans le catalogue du tenant (produits, services, biens immobiliers, véhicules, etc.).",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "query":  {"type": "string"},
                        "filters":{"type": "object", "description": "Filtres optionnels (prix, catégorie, etc.)"},
                        "limit":  {"type": "integer", "default": 5},
                    },
                    "required": ["query"],
                },
            },
            {
                "name": "escalate_to_human",
                "description": "Transfère la conversation à un humain. À utiliser quand le visiteur est insatisfait, que la demande dépasse les compétences de l'agent, ou qu'il le demande explicitement.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "reason":          {"type": "string"},
                        "urgency":         {"type": "string", "enum": ["low", "medium", "high"]},
                        "conversation_summary": {"type": "string"},
                    },
                    "required": ["reason", "conversation_summary"],
                },
            },
            {
                "name": "update_visitor_profile",
                "description": "Met à jour le profil du visiteur avec des informations apprises en conversation (métier, expertise, intentions, faits). À utiliser fréquemment pour enrichir la mémoire.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "detected_profession": {"type": "string"},
                        "expertise_level":     {"type": "string", "enum": ["novice", "intermediate", "expert"]},
                        "preferred_tone":      {"type": "string", "enum": ["formal", "casual", "premium"]},
                        "intentions":          {"type": "array", "items": {"type": "string"}},
                        "pain_points":         {"type": "array", "items": {"type": "string"}},
                        "custom_facts":        {"type": "object", "description": "Dict clé-valeur de faits à mémoriser"},
                    },
                },
            },
        ]

    async def chat_stream(
        self,
        profile: VisitorProfile,
        message_history: list[dict],
        user_message: str,
        conversation_summary: str | None = None,
    ) -> AsyncGenerator[dict, None]:
        """
        Stream la réponse de l'agent token par token.
        Yield des events typés :
          {"type": "text_delta", "delta": "..."}
          {"type": "tool_use", "tool": "...", "input": {...}}
          {"type": "done", "usage": {...}}
        """
        # Update metadata profile
        profile.message_count += 1
        profile.last_seen = datetime.now(timezone.utc).isoformat()

        system = self._build_system_prompt(profile, conversation_summary)

        messages = message_history + [{"role": "user", "content": user_message}]

        try:
            async with self.client.messages.stream(
                model=self.default_model,
                max_tokens=1024,
                system=system,
                tools=self._get_tools(),
                messages=messages,
            ) as stream:
                current_tool: dict | None = None

                async for event in stream:
                    event_type = event.type

                    if event_type == "content_block_start":
                        block = event.content_block
                        if block.type == "tool_use":
                            current_tool = {
                                "id":    block.id,
                                "name":  block.name,
                                "input": "",
                            }

                    elif event_type == "content_block_delta":
                        delta = event.delta
                        if delta.type == "text_delta":
                            yield {"type": "text_delta", "delta": delta.text}
                        elif delta.type == "input_json_delta" and current_tool:
                            current_tool["input"] += delta.partial_json

                    elif event_type == "content_block_stop":
                        if current_tool:
                            try:
                                parsed_input = json.loads(current_tool["input"]) if current_tool["input"] else {}
                            except json.JSONDecodeError:
                                parsed_input = {}
                            yield {
                                "type": "tool_use",
                                "id":    current_tool["id"],
                                "tool":  current_tool["name"],
                                "input": parsed_input,
                            }
                            current_tool = None

                # Final message → usage stats
                final_message = await stream.get_final_message()
                yield {
                    "type": "done",
                    "usage": {
                        "input_tokens":  final_message.usage.input_tokens,
                        "output_tokens": final_message.usage.output_tokens,
                    },
                }
        except Exception as exc:
            logger.exception("conv.stream_error", tenant=self.tenant_id, error=str(exc))
            yield {"type": "error", "message": str(exc)}

    async def detect_language(self, text: str) -> str:
        """
        Détecte rapidement la langue d'un message via Haiku (fast & cheap).
        Retourne un code ISO parmi fr/en/de/nl/es.
        """
        if len(text.strip()) < 3:
            return DEFAULT_LANGUAGE

        prompt = f"""Identify the language of this text. Respond with ONLY the ISO code: "fr", "en", "de", "nl", or "es". No other text.

Text: {text[:200]}"""

        try:
            response = await self.client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=5,
                messages=[{"role": "user", "content": prompt}],
            )
            code = "".join(block.text for block in response.content if hasattr(block, "text")).strip().lower()
            return code if code in SUPPORTED_LANGUAGES else DEFAULT_LANGUAGE
        except Exception as e:
            logger.warning("lang_detection.failed", error=str(e))
            return DEFAULT_LANGUAGE

    async def summarize_conversation(self, message_history: list[dict]) -> str:
        """
        Résume une conversation longue pour économiser des tokens.
        Utilisé quand l'historique dépasse ~20 messages.
        """
        if len(message_history) < 10:
            return ""

        conversation_text = "\n".join([
            f"{msg['role']}: {msg['content']}"
            for msg in message_history
        ])

        prompt = f"""Résume cette conversation en 3-5 phrases, en conservant :
- L'objectif principal du visiteur
- Les informations clés partagées
- Les engagements ou questions en suspens
- Le ton de l'échange

Conversation :
{conversation_text}

Résumé :"""

        try:
            response = await self.client.messages.create(
                model=CLAUDE_MODEL_FAST,
                max_tokens=256,
                messages=[{"role": "user", "content": prompt}],
            )
            return "".join(block.text for block in response.content if hasattr(block, "text")).strip()
        except Exception as exc:
            logger.warning("conv.summarize_failed", error=str(exc))
            return ""
