"""
═══════════════════════════════════════════════════════════
SARTORIAL AGENTIC — Agent Email Outreach
Génère des séquences d'emails personnalisés pour la prospection.
═══════════════════════════════════════════════════════════
"""

import json

from app.agents.base import BaseAgent, CLAUDE_MODEL_BALANCED

SYSTEM_PROMPT = """Tu es l'Agent Email Outreach de Sartorial Agentic — un stratège en prospection email d'élite.

Tu génères des séquences d'emails premium, personnalisés, qui obtiennent des taux de réponse supérieurs à la moyenne du marché. Tu évites absolument le spam, les formules creuses, les accroches génériques.

Règles de rédaction :
- Ton : direct, confiant, respectueux. Tu parles d'humain à humain.
- Longueur : court (80-150 mots par email).
- Personnalisation : utilise le contexte fourni (secteur, nom, entreprise, pain point).
- Call-to-action : unique, clair, sans pression.
- Signature : toujours "— Votre Tailleur" ou personnalisée selon config.
- Langue : celle demandée dans input_data.locale (défaut: fr).

Format de sortie : JSON strict, sans markdown ni texte autour.
"""


class EmailOutreachAgent(BaseAgent):
    slug = "email-outreach"
    name = "Agent Email Outreach"
    default_model = CLAUDE_MODEL_BALANCED

    async def run(self, input_data: dict) -> dict:
        """
        Input:
            {
                "prospect": {
                    "name": "Jean Dupont",
                    "company": "Garage Central",
                    "sector": "automobile",
                    "role": "Directeur"
                },
                "goal": "prendre_rdv" | "presenter_produit" | "relance",
                "context": "Rencontré au salon XYZ, intéressé par...",
                "sequence_length": 3,
                "locale": "fr"
            }
        Output:
            {
                "emails": [
                    {"subject": "...", "body": "...", "day_offset": 0},
                    {"subject": "...", "body": "...", "day_offset": 3},
                    {"subject": "...", "body": "...", "day_offset": 7}
                ]
            }
        """
        prospect = input_data.get("prospect", {})
        goal = input_data.get("goal", "presenter_produit")
        context = input_data.get("context", "")
        sequence_length = int(input_data.get("sequence_length", 3))
        locale = input_data.get("locale", "fr")

        if not prospect.get("name") and not prospect.get("company"):
            raise ValueError("'prospect.name' ou 'prospect.company' requis")

        if sequence_length < 1 or sequence_length > 7:
            raise ValueError("sequence_length doit être entre 1 et 7")

        prompt = f"""Génère une séquence de {sequence_length} emails de prospection.

PROSPECT :
{json.dumps(prospect, ensure_ascii=False, indent=2)}

OBJECTIF : {goal}

CONTEXTE : {context if context else "(aucun contexte fourni — adapte-toi au profil)"}

LANGUE : {locale}

Contraintes :
- Email 1 : premier contact, accroche sur un pain point probable de son secteur/rôle.
- Emails suivants : relances avec angle différent à chaque fois (ne jamais répéter).
- Espacement : day_offset commence à 0 pour le 1er, puis +3, +7, +14, +21...
- Objets percutants (max 50 caractères, sans emoji, sans "Re:", sans caps lock).

Retourne UNIQUEMENT un JSON valide au format :
{{
  "emails": [
    {{"subject": "...", "body": "...", "day_offset": 0}}
  ]
}}
"""

        response_text = await self.call_claude(
            prompt=prompt,
            system=SYSTEM_PROMPT,
            max_tokens=2048,
            temperature=0.8,
        )

        # Parse JSON response (handle eventual markdown code fences)

        try:
            data = self._parse_json(response_text)
        except json.JSONDecodeError as e:
            raise ValueError(f"Claude a retourné un JSON invalide : {e}") from e

        if "emails" not in data or not isinstance(data["emails"], list):
            raise ValueError("Réponse invalide : 'emails' doit être une liste")

        # Validation minimale
        for idx, email in enumerate(data["emails"]):
            if "subject" not in email or "body" not in email:
                raise ValueError(f"Email {idx} : 'subject' et 'body' requis")
            email.setdefault("day_offset", idx * 3)

        return {
            "emails": data["emails"],
            "prospect_name": prospect.get("name", ""),
            "prospect_company": prospect.get("company", ""),
            "generated_count": len(data["emails"]),
        }
