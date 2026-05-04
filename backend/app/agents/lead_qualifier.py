"""
═══════════════════════════════════════════════════════════
SARTORIAL AGENTIC — Agent Lead Qualifier
Analyse chaque lead entrant, le score, le qualifie,
et décide de l'action suivante automatiquement.

CHAÎNE : Prospection → [CE MODULE] → Email Outreach / RDV
═══════════════════════════════════════════════════════════
"""

import json

from app.agents.base import BaseAgent, CLAUDE_MODEL_BALANCED

SYSTEM_PROMPT = """Tu es l'Agent Lead Qualifier de Sartorial Agentic. Tu analyses les leads entrants pour déterminer leur potentiel de conversion et décider de l'action optimale.

Tu reçois les données d'un lead (source, comportement, messages, secteur) et tu produis :
1. Un score de 0 à 100
2. Une qualification (froid / tiède / chaud / brûlant)
3. Les signaux d'achat détectés
4. L'action recommandée immédiate
5. La séquence de nurturing recommandée

Tu es analytique, factuel, jamais optimiste sans raison. Un lead mal qualifié fait perdre du temps au commercial.

Barème de scoring :
- 0-25 : FROID — curieux, pas de besoin identifié
- 26-50 : TIÈDE — besoin latent, pas encore prêt
- 51-75 : CHAUD — besoin exprimé, en phase de recherche
- 76-100 : BRÛLANT — urgence, budget identifié, décideur

Format de sortie : JSON strict.
"""


class LeadQualifierAgent(BaseAgent):
    slug = "lead-qualifier"
    name = "Agent Lead Qualifier"
    default_model = CLAUDE_MODEL_BALANCED

    async def run(self, input_data: dict) -> dict:
        """
        Input:
            {
                "lead": {
                    "name": "Jean Dupont",
                    "email": "jean@example.com",
                    "company": "Garage Central",
                    "role": "Gérant",
                    "phone": "+33612345678",
                    "source": "chatbot" | "landing" | "referral" | "linkedin" | "cold",
                    "sector": "automobile"
                },
                "context": {
                    "messages": ["Je cherche une solution pour gérer mes leads"],
                    "pages_viewed": ["/pricing", "/automobile"],
                    "time_on_site_seconds": 240,
                    "returning_visitor": true,
                    "referral_code": null
                }
            }
        Output:
            {
                "score": 72,
                "qualification": "chaud",
                "signals": ["a consulté les prix", "revient pour la 2e fois", "besoin exprimé"],
                "recommended_action": "email_sequence_warm",
                "action_details": {
                    "type": "email_outreach",
                    "delay_hours": 2,
                    "template": "warm_lead_first_contact",
                    "personalization_notes": "Mentionner son secteur auto, rebondir sur sa question leads"
                },
                "nurturing_plan": [
                    {"day": 0, "action": "email_first_contact", "channel": "email"},
                    {"day": 2, "action": "follow_up_value", "channel": "email"},
                    {"day": 5, "action": "case_study_sector", "channel": "email"},
                    {"day": 7, "action": "book_demo_cta", "channel": "email"}
                ],
                "enrichment": {
                    "estimated_company_size": "PME",
                    "estimated_budget": "moyen",
                    "decision_timeline": "1-3 mois",
                    "key_pain_points": ["gestion leads", "suivi prospects"]
                }
            }
        """
        lead = input_data.get("lead", {})
        context = input_data.get("context", {})

        if not lead.get("email"):
            raise ValueError("'lead.email' requis")

        prompt = f"""Analyse ce lead et qualifie-le.

LEAD :
{json.dumps(lead, ensure_ascii=False, indent=2)}

CONTEXTE COMPORTEMENTAL :
{json.dumps(context, ensure_ascii=False, indent=2)}

Retourne UNIQUEMENT un JSON valide au format :
{{
  "score": <0-100>,
  "qualification": "froid" | "tiède" | "chaud" | "brûlant",
  "signals": ["signal 1", "signal 2"],
  "recommended_action": "<action_key>",
  "action_details": {{
    "type": "email_outreach" | "phone_call" | "book_demo" | "nurture_sequence" | "disqualify",
    "delay_hours": <0-72>,
    "template": "<template_name>",
    "personalization_notes": "<notes pour personnaliser l'approche>"
  }},
  "nurturing_plan": [
    {{"day": 0, "action": "<action>", "channel": "email" | "sms" | "phone"}}
  ],
  "enrichment": {{
    "estimated_company_size": "micro" | "PME" | "ETI" | "grand_compte",
    "estimated_budget": "faible" | "moyen" | "élevé",
    "decision_timeline": "<estimation>",
    "key_pain_points": ["point 1", "point 2"]
  }}
}}"""

        response_text = await self.call_claude(
            prompt=prompt,
            system=SYSTEM_PROMPT,
            max_tokens=1024,
            temperature=0.4,  # Peu de créativité, beaucoup de rigueur
        )


        data = self._parse_json(response_text)

        # Validation
        if "score" not in data or not isinstance(data["score"], (int, float)):
            raise ValueError("Score manquant ou invalide")
        data["score"] = max(0, min(100, int(data["score"])))

        valid_quals = {"froid", "tiède", "chaud", "brûlant"}
        if data.get("qualification") not in valid_quals:
            data["qualification"] = (
                "froid" if data["score"] <= 25
                else "tiède" if data["score"] <= 50
                else "chaud" if data["score"] <= 75
                else "brûlant"
            )

        data["lead_email"] = lead.get("email")
        data["lead_name"] = lead.get("name", "")

        return data
