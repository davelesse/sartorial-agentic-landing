"""
═══════════════════════════════════════════════════════════
SARTORIAL AGENTIC — Agent Social Media Manager
Gestion autonome des réseaux sociaux du client :
  - Création de posts adaptés par plateforme
  - Calendrier éditorial automatique
  - Analyse d'engagement et suggestions
  - Hashtags optimisés par secteur

CHAÎNE : Content Creator → [CE MODULE] → Reputation Manager
═══════════════════════════════════════════════════════════
"""

import json

from app.agents.base import BaseAgent, CLAUDE_MODEL_BALANCED

SYSTEM_PROMPT = """Tu es l'Agent Social Media Manager de Sartorial Agentic. Tu crées et planifies du contenu pour les réseaux sociaux.

Tes capacités :
1. Créer des posts adaptés à chaque plateforme (LinkedIn, Instagram, Facebook, X)
2. Adapter le ton au secteur et à la plateforme
3. Générer des hashtags pertinents
4. Proposer un calendrier éditorial hebdomadaire ou mensuel
5. Analyser les métriques d'engagement et recommander des ajustements

Règles :
- LinkedIn : ton professionnel, insights sectoriels, 1300 caractères max
- Instagram : visuel d'abord, caption engageante, 30 hashtags max
- Facebook : conversationnel, questions ouvertes, liens vers le site
- X (Twitter) : concis, percutant, 280 caractères, 3-5 hashtags max
- Jamais de contenu polarisant, politique ou controversé
- Toujours inclure un CTA subtil

Format de sortie : JSON strict.
"""


class SocialMediaAgent(BaseAgent):
    slug = "social-media-manager"
    name = "Agent Réseaux Sociaux"
    default_model = CLAUDE_MODEL_BALANCED

    async def run(self, input_data: dict) -> dict:
        """
        Input:
            {
                "action": "create_post" | "editorial_calendar" | "engagement_analysis",
                "business": {
                    "name": "Garage Central",
                    "sector": "automobile",
                    "tone": "expert et accessible",
                    "website": "https://garage-central.fr"
                },
                "post_config": {
                    "platform": "linkedin" | "instagram" | "facebook" | "x",
                    "topic": "Lancement de notre service de diagnostic IA",
                    "goal": "awareness" | "engagement" | "traffic" | "leads",
                    "include_cta": true,
                    "cta_url": "https://garage-central.fr/diagnostic"
                },
                "calendar_config": {
                    "duration": "week" | "month",
                    "platforms": ["linkedin", "instagram"],
                    "posts_per_week": 3,
                    "themes": ["innovation", "coulisses", "témoignages"]
                },
                "locale": "fr"
            }
        """
        action = input_data.get("action", "create_post")
        business = input_data.get("business", {})
        locale = input_data.get("locale", "fr")

        if action == "create_post":
            return await self._create_post(input_data, business, locale)
        elif action == "editorial_calendar":
            return await self._editorial_calendar(input_data, business, locale)
        elif action == "engagement_analysis":
            return await self._engagement_analysis(input_data, business, locale)
        else:
            raise ValueError(f"Action inconnue : {action}")

    async def _create_post(self, input_data: dict, business: dict, locale: str) -> dict:
        config = input_data.get("post_config", {})
        platform = config.get("platform", "linkedin")

        prompt = f"""Crée un post pour {platform}.

ENTREPRISE :
{json.dumps(business, ensure_ascii=False, indent=2)}

CONFIGURATION :
{json.dumps(config, ensure_ascii=False, indent=2)}

LANGUE : {locale}

Retourne :
{{
  "platform": "{platform}",
  "post_text": "<texte complet du post>",
  "hashtags": ["#hashtag1", "#hashtag2"],
  "image_suggestion": "<description de l'image idéale à accompagner>",
  "best_time_to_post": "<jour et heure optimaux>",
  "estimated_reach": "low" | "medium" | "high",
  "cta_included": true | false,
  "variations": [
    "<version alternative 1 du post>",
    "<version alternative 2>"
  ]
}}
"""
        response_text = await self.call_claude(prompt=prompt, system=SYSTEM_PROMPT, max_tokens=1536, temperature=0.8)
        data = self._parse_json(response_text)
        data["action_performed"] = "create_post"
        return data

    async def _editorial_calendar(self, input_data: dict, business: dict, locale: str) -> dict:
        config = input_data.get("calendar_config", {})

        prompt = f"""Crée un calendrier éditorial.

ENTREPRISE :
{json.dumps(business, ensure_ascii=False, indent=2)}

CONFIG :
{json.dumps(config, ensure_ascii=False, indent=2)}

LANGUE : {locale}

Retourne :
{{
  "duration": "{config.get('duration', 'week')}",
  "posts": [
    {{
      "day": "lundi",
      "date_relative": "Jour 1",
      "platform": "linkedin",
      "theme": "innovation",
      "post_idea": "<idée de post en 1 ligne>",
      "post_text": "<texte complet>",
      "hashtags": ["#tag"],
      "time": "09:00"
    }}
  ],
  "strategy_notes": "<notes stratégiques sur le calendrier>"
}}
"""
        response_text = await self.call_claude(prompt=prompt, system=SYSTEM_PROMPT, max_tokens=3000, temperature=0.75)
        data = self._parse_json(response_text)
        data["action_performed"] = "editorial_calendar"
        return data

    async def _engagement_analysis(self, input_data: dict, business: dict, locale: str) -> dict:
        metrics = input_data.get("metrics", {})

        prompt = f"""Analyse ces métriques d'engagement et recommande des ajustements.

ENTREPRISE :
{json.dumps(business, ensure_ascii=False, indent=2)}

MÉTRIQUES :
{json.dumps(metrics, ensure_ascii=False, indent=2)}

LANGUE : {locale}

Retourne :
{{
  "overall_score": <0-100>,
  "best_performing": {{"platform": "...", "post_type": "...", "why": "..."}},
  "worst_performing": {{"platform": "...", "post_type": "...", "why": "..."}},
  "recommendations": [
    {{"action": "...", "expected_impact": "...", "priority": "high" | "medium"}}
  ],
  "content_gaps": ["type de contenu manquant"],
  "competitor_insights": "<observation générale sur le secteur>"
}}
"""
        response_text = await self.call_claude(prompt=prompt, system=SYSTEM_PROMPT, max_tokens=1536, temperature=0.6)
        data = self._parse_json(response_text)
        data["action_performed"] = "engagement_analysis"
        return data
