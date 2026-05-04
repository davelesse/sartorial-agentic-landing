"""
═══════════════════════════════════════════════════════════
SARTORIAL AGENTIC — Agent Appointment Scheduler
Gère le cycle complet des rendez-vous :
  - Proposition de créneaux
  - Confirmation automatique
  - Rappels J-1 et H-1
  - Gestion des reports/annulations
  - Résumé pré-RDV pour le commercial

CHAÎNE : Lead Qualifier → [CE MODULE] → Follow-up SAV
═══════════════════════════════════════════════════════════
"""

import json

from app.agents.base import BaseAgent, CLAUDE_MODEL_BALANCED

SYSTEM_PROMPT = """Tu es l'Agent Appointment Scheduler de Sartorial Agentic. Tu gères la prise de rendez-vous de A à Z.

Tes capacités :
- Proposer des créneaux adaptés au profil du prospect
- Rédiger les messages de confirmation, rappel, report
- Préparer un briefing pré-RDV pour le commercial
- Adapter le ton au secteur (formel pour santé, chaleureux pour restauration)

Format de sortie : JSON strict.
"""


class AppointmentSchedulerAgent(BaseAgent):
    slug = "appointment-scheduler"
    name = "Agent Prise de RDV"
    default_model = CLAUDE_MODEL_BALANCED

    async def run(self, input_data: dict) -> dict:
        """
        Input:
            {
                "action": "propose_slots" | "confirm" | "remind" | "reschedule" | "prepare_brief",
                "prospect": {
                    "name": "Marie Martin",
                    "email": "marie@example.com",
                    "phone": "+33612345678",
                    "company": "Salon Élégance",
                    "sector": "beaute"
                },
                "appointment": {
                    "date": "2026-04-20T10:00:00",
                    "duration_minutes": 30,
                    "type": "demo" | "consultation" | "visite" | "devis",
                    "location": "visioconférence" | "sur place" | "téléphone"
                },
                "available_slots": ["2026-04-20T10:00", "2026-04-20T14:00", "2026-04-21T09:00"],
                "conversation_history": "Résumé de l'échange avec le prospect",
                "locale": "fr"
            }
        """
        action = input_data.get("action", "propose_slots")
        prospect = input_data.get("prospect", {})
        appointment = input_data.get("appointment", {})
        locale = input_data.get("locale", "fr")

        if not prospect.get("email"):
            raise ValueError("'prospect.email' requis")

        prompt = f"""Action demandée : {action}

PROSPECT :
{json.dumps(prospect, ensure_ascii=False, indent=2)}

RENDEZ-VOUS :
{json.dumps(appointment, ensure_ascii=False, indent=2)}

CRÉNEAUX DISPONIBLES : {json.dumps(input_data.get('available_slots', []))}

HISTORIQUE CONVERSATION : {input_data.get('conversation_history', '(aucun)')}

LANGUE : {locale}

Selon l'action demandée, retourne un JSON avec :

Pour "propose_slots" :
{{
  "message_to_prospect": "<message proposant les créneaux>",
  "subject": "<objet email>",
  "recommended_slot": "<le créneau le plus adapté et pourquoi>"
}}

Pour "confirm" :
{{
  "confirmation_email": {{"subject": "...", "body": "..."}},
  "confirmation_sms": "<texte SMS court>",
  "calendar_event": {{"title": "...", "description": "...", "start": "...", "end": "...", "location": "..."}}
}}

Pour "remind" :
{{
  "reminder_email": {{"subject": "...", "body": "..."}},
  "reminder_sms": "<texte SMS rappel>",
  "timing": "j-1" | "h-1"
}}

Pour "reschedule" :
{{
  "reschedule_email": {{"subject": "...", "body": "..."}},
  "new_slots_proposed": ["<3 nouveaux créneaux>"]
}}

Pour "prepare_brief" :
{{
  "brief": {{
    "prospect_summary": "<résumé du prospect en 3 lignes>",
    "key_interests": ["<ce qui l'intéresse>"],
    "pain_points": ["<ses problèmes>"],
    "recommended_approach": "<comment aborder le RDV>",
    "questions_to_ask": ["<questions pertinentes>"],
    "materials_to_prepare": ["<documents/démos à préparer>"]
  }}
}}
"""

        response_text = await self.call_claude(
            prompt=prompt,
            system=SYSTEM_PROMPT,
            max_tokens=1536,
            temperature=0.6,
        )


        data = self._parse_json(response_text)
        data["action_performed"] = action
        data["prospect_email"] = prospect.get("email")

        return data
