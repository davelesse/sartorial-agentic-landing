"""
═══════════════════════════════════════════════════════════
SARTORIAL AGENTIC — Agent Customer Success
Gestion du cycle de vie client post-conversion :
  - Onboarding automatisé (séquence J+1 à J+30)
  - Suivi satisfaction (NPS, enquêtes)
  - Détection de churn (signaux faibles)
  - Upsell intelligent (upgrade au bon moment)
  - Réactivation des clients inactifs

CHAÎNE : Conversion → [CE MODULE] → Rétention long terme
═══════════════════════════════════════════════════════════
"""

import json

from app.agents.base import BaseAgent, CLAUDE_MODEL_BALANCED

SYSTEM_PROMPT = """Tu es l'Agent Customer Success de Sartorial Agentic. Ton rôle est de maximiser la rétention et la satisfaction des clients après leur conversion.

Tes missions :
1. ONBOARDING : guider le nouveau client dans ses premières actions
2. SATISFACTION : mesurer le NPS, détecter les problèmes tôt
3. ANTI-CHURN : identifier les signaux faibles de départ et agir
4. UPSELL : proposer un upgrade quand le client atteint ses limites
5. RÉACTIVATION : ramener les clients inactifs

Tu es proactif mais jamais intrusif. Tu apportes de la valeur avant de demander quoi que ce soit.

Format de sortie : JSON strict.
"""


class CustomerSuccessAgent(BaseAgent):
    slug = "customer-success"
    name = "Agent Customer Success"
    default_model = CLAUDE_MODEL_BALANCED

    async def run(self, input_data: dict) -> dict:
        """
        Input:
            {
                "action": "onboarding_sequence" | "health_check" | "churn_detection" | "upsell_analysis" | "reactivation",
                "client": {
                    "name": "Garage Central",
                    "email": "contact@garage-central.fr",
                    "plan": "atelier",
                    "sector": "automobile",
                    "signup_date": "2026-03-15",
                    "last_login": "2026-04-10",
                    "executions_used": 340,
                    "executions_limit": 500,
                    "agents_active": 3,
                    "subscription_status": "active"
                },
                "usage_data": {
                    "logins_last_30d": 12,
                    "executions_last_7d": 45,
                    "trend": "declining" | "stable" | "growing",
                    "most_used_agent": "email-outreach",
                    "least_used_agent": "content-creator",
                    "support_tickets": 0,
                    "nps_score": null
                },
                "locale": "fr"
            }
        """
        action = input_data.get("action", "health_check")
        client = input_data.get("client", {})
        usage = input_data.get("usage_data", {})
        locale = input_data.get("locale", "fr")

        if not client.get("email"):
            raise ValueError("'client.email' requis")

        prompt = f"""Action : {action}

CLIENT :
{json.dumps(client, ensure_ascii=False, indent=2)}

DONNÉES D'USAGE :
{json.dumps(usage, ensure_ascii=False, indent=2)}

LANGUE : {locale}

Selon l'action demandée :

Pour "onboarding_sequence" :
{{
  "emails": [
    {{"day": 1, "subject": "...", "body": "...", "cta": "..."}},
    {{"day": 3, "subject": "...", "body": "...", "cta": "..."}},
    {{"day": 7, "subject": "...", "body": "...", "cta": "..."}},
    {{"day": 14, "subject": "...", "body": "...", "cta": "..."}},
    {{"day": 30, "subject": "...", "body": "...", "cta": "..."}}
  ],
  "milestones": ["première exécution", "premier lead généré", "3 agents configurés"]
}}

Pour "health_check" :
{{
  "health_score": <0-100>,
  "status": "healthy" | "at_risk" | "critical",
  "signals": ["signal positif/négatif"],
  "recommended_actions": [
    {{"action": "...", "priority": "high" | "medium" | "low", "channel": "email" | "in_app", "message": "..."}}
  ]
}}

Pour "churn_detection" :
{{
  "churn_risk": <0-100>,
  "risk_level": "low" | "medium" | "high" | "critical",
  "warning_signals": ["signal 1", "signal 2"],
  "intervention": {{
    "type": "personal_email" | "phone_call" | "offer_extension" | "feature_highlight" | "upgrade_offer",
    "message": "<message personnalisé>",
    "urgency_hours": <délai recommandé>
  }}
}}

Pour "upsell_analysis" :
{{
  "ready_for_upgrade": true | false,
  "recommended_plan": "manufacture" | "maison",
  "triggers": ["raison 1", "raison 2"],
  "pitch": "<argumentaire personnalisé 3-5 lignes>",
  "email": {{"subject": "...", "body": "..."}},
  "best_timing": "<quand envoyer>"
}}

Pour "reactivation" :
{{
  "inactive_days": <nombre>,
  "reactivation_email": {{"subject": "...", "body": "..."}},
  "offer": {{
    "type": "free_extension" | "feature_unlock" | "personal_demo" | "discount",
    "details": "<détails de l'offre>"
  }},
  "fallback_if_no_response": "<action alternative>"
}}
"""

        response_text = await self.call_claude(
            prompt=prompt,
            system=SYSTEM_PROMPT,
            max_tokens=2048,
            temperature=0.65,
        )


        data = self._parse_json(response_text)
        data["action_performed"] = action
        data["client_email"] = client.get("email")

        return data
