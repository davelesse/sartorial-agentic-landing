"""
═══════════════════════════════════════════════════════════
SARTORIAL AGENTIC — Agent Reputation Manager
Surveille la réputation en ligne du client et agit :
  - Analyse de sentiment des avis
  - Génération de réponses personnalisées aux avis
  - Alertes sur avis négatifs (temps réel)
  - Rapport hebdomadaire de e-réputation
  - Suggestions d'amélioration basées sur les avis

CHAÎNE : SAV → [CE MODULE] → Fidélisation
═══════════════════════════════════════════════════════════
"""

import json

from app.agents.base import BaseAgent, CLAUDE_MODEL_BALANCED

SYSTEM_PROMPT = """Tu es l'Agent Reputation Manager de Sartorial Agentic. Tu gères la e-réputation des clients.

Ton rôle :
1. Analyser le sentiment des avis reçus (Google, TripAdvisor, Trustpilot, etc.)
2. Rédiger des réponses professionnelles et personnalisées à chaque avis
3. Pour les avis négatifs : réponse empathique + proposition de résolution
4. Pour les avis positifs : remerciement chaleureux + invitation à revenir
5. Identifier les tendances et suggérer des améliorations opérationnelles

Règles absolues :
- Ne jamais être défensif face à un avis négatif
- Toujours proposer une solution concrète
- Ne jamais inventer de faits ou promettre sans vérifier
- Adapter le ton au secteur (restaurant = chaleureux, santé = professionnel, auto = expert)

Format de sortie : JSON strict.
"""


class ReputationManagerAgent(BaseAgent):
    slug = "reputation-manager"
    name = "Agent Réputation Online"
    default_model = CLAUDE_MODEL_BALANCED

    async def run(self, input_data: dict) -> dict:
        """
        Input:
            {
                "action": "analyze_review" | "generate_response" | "weekly_report",
                "business": {
                    "name": "Restaurant Le Tailleur",
                    "sector": "restauration",
                    "owner_name": "David"
                },
                "review": {
                    "platform": "google",
                    "rating": 2,
                    "author": "Sophie L.",
                    "text": "Service lent, le plat était tiède. Déçue car on m'avait recommandé l'endroit.",
                    "date": "2026-04-14"
                },
                "reviews_batch": [...],  // Pour weekly_report
                "locale": "fr"
            }
        """
        action = input_data.get("action", "analyze_review")
        business = input_data.get("business", {})
        review = input_data.get("review", {})
        locale = input_data.get("locale", "fr")

        if action == "weekly_report":
            return await self._weekly_report(input_data, business, locale)

        if not review.get("text"):
            raise ValueError("'review.text' requis")

        prompt = f"""Action : {action}

ENTREPRISE :
{json.dumps(business, ensure_ascii=False, indent=2)}

AVIS À TRAITER :
{json.dumps(review, ensure_ascii=False, indent=2)}

LANGUE DE RÉPONSE : {locale}

Pour "analyze_review" :
{{
  "sentiment": "positif" | "neutre" | "négatif" | "très_négatif",
  "score": <1-10>,
  "themes": ["service", "qualité", "prix", "ambiance", "propreté"],
  "urgency": "low" | "medium" | "high",
  "key_issues": ["problème identifié"],
  "requires_escalation": false,
  "escalation_reason": null
}}

Pour "generate_response" :
{{
  "response_text": "<réponse complète à publier>",
  "tone": "empathique" | "reconnaissant" | "professionnel",
  "internal_action": {{
    "type": "none" | "contact_client" | "process_improvement" | "compensation",
    "details": "<action interne suggérée>"
  }},
  "follow_up_needed": false
}}
"""

        response_text = await self.call_claude(
            prompt=prompt,
            system=SYSTEM_PROMPT,
            max_tokens=1024,
            temperature=0.6,
        )


        data = self._parse_json(response_text)
        data["action_performed"] = action
        data["review_platform"] = review.get("platform", "unknown")

        return data

    async def _weekly_report(self, input_data: dict, business: dict, locale: str) -> dict:
        reviews = input_data.get("reviews_batch", [])
        if not reviews:
            return {
                "action_performed": "weekly_report",
                "report": {"message": "Aucun avis cette semaine", "review_count": 0},
            }

        prompt = f"""Génère un rapport hebdomadaire de e-réputation.

ENTREPRISE :
{json.dumps(business, ensure_ascii=False, indent=2)}

AVIS DE LA SEMAINE ({len(reviews)} avis) :
{json.dumps(reviews[:20], ensure_ascii=False, indent=2)}

LANGUE : {locale}

Retourne un JSON :
{{
  "summary": "<résumé exécutif en 3 lignes>",
  "review_count": {len(reviews)},
  "average_rating": <moyenne>,
  "sentiment_distribution": {{"positif": <n>, "neutre": <n>, "négatif": <n>}},
  "top_compliments": ["ce qui plaît le plus"],
  "top_complaints": ["ce qui revient le plus en négatif"],
  "trend": "improving" | "stable" | "declining",
  "actionable_insights": [
    {{"insight": "...", "priority": "high" | "medium", "suggested_action": "..."}}
  ],
  "comparison_note": "<comparaison avec la semaine précédente si possible>"
}}
"""

        response_text = await self.call_claude(
            prompt=prompt,
            system=SYSTEM_PROMPT,
            max_tokens=1536,
            temperature=0.5,
        )


        data = self._parse_json(response_text)
        data["action_performed"] = "weekly_report"

        return data
