"""
═══════════════════════════════════════════════════════════
SARTORIAL AGENTIC — Agent Invoice & Quote Generator
Génère automatiquement devis et factures à partir
d'une conversation ou d'une demande structurée.

CHAÎNE : RDV / Chatbot → [CE MODULE] → Paiement / Suivi
═══════════════════════════════════════════════════════════
"""

import json

from app.agents.base import BaseAgent, CLAUDE_MODEL_BALANCED

SYSTEM_PROMPT = """Tu es l'Agent Devis & Factures de Sartorial Agentic. Tu génères des documents commerciaux professionnels.

Ton rôle :
1. Générer des devis détaillés à partir d'une description de besoin
2. Convertir un devis accepté en facture
3. Adapter le format au secteur (automobile, immobilier, beauté, etc.)
4. Inclure les conditions générales pertinentes
5. Calculer TVA, remises, totaux

Règles :
- Toujours demander confirmation avant d'envoyer au client
- TVA standard 20% sauf indication contraire
- Numérotation séquentielle (DEVIS-2026-XXXX / FAC-2026-XXXX)
- Validité devis : 30 jours par défaut

Format de sortie : JSON strict.
"""


class InvoiceQuoteAgent(BaseAgent):
    slug = "invoice-quote"
    name = "Agent Devis & Factures"
    default_model = CLAUDE_MODEL_BALANCED

    async def run(self, input_data: dict) -> dict:
        """
        Input:
            {
                "action": "generate_quote" | "convert_to_invoice" | "credit_note",
                "client_info": {
                    "name": "Marie Martin",
                    "company": "Salon Élégance",
                    "email": "marie@salon-elegance.fr",
                    "address": "12 rue de la Paix, 75002 Paris",
                    "siret": "12345678900012"
                },
                "business_info": {
                    "name": "Garage Central",
                    "siret": "98765432100098",
                    "address": "45 avenue des Champs, 75008 Paris",
                    "tva_number": "FR12345678901"
                },
                "items": [
                    {"description": "Révision complète véhicule", "quantity": 1, "unit_price_ht": 250.00},
                    {"description": "Changement plaquettes frein", "quantity": 4, "unit_price_ht": 45.00}
                ],
                "discount_percent": 10,
                "notes": "Suite à notre conversation du 14 avril",
                "payment_terms": "30 jours",
                "locale": "fr"
            }
        """
        import uuid as _uuid
        from datetime import datetime as _dt
        action = input_data.get("action", "generate_quote")
        client = input_data.get("client_info", {})
        business = input_data.get("business_info", {})
        items = input_data.get("items", [])
        locale = input_data.get("locale", "fr")

        # Numéro séquentiel injecté par tasks.py, sinon fallback sur un identifiant unique
        if "document_number" not in input_data:
            year = _dt.now().year
            prefix = "FAC" if action == "convert_to_invoice" else "DEVIS"
            input_data["document_number"] = f"{prefix}-{year}-{_uuid.uuid4().hex[:6].upper()}"
        document_number = input_data["document_number"]

        if not items:
            raise ValueError("'items' requis (au moins une ligne)")

        # Calculs
        subtotal_ht = sum(i["quantity"] * i["unit_price_ht"] for i in items)
        discount_pct = input_data.get("discount_percent", 0)
        discount_amount = subtotal_ht * discount_pct / 100
        total_ht = subtotal_ht - discount_amount
        tva = total_ht * 0.20
        total_ttc = total_ht + tva

        prompt = f"""Génère un document commercial.

ACTION : {action}
LANGUE : {locale}
NUMÉRO DE DOCUMENT : {document_number} (utilise ce numéro exact dans le champ "document_number")

ÉMETTEUR :
{json.dumps(business, ensure_ascii=False, indent=2)}

CLIENT :
{json.dumps(client, ensure_ascii=False, indent=2)}

LIGNES :
{json.dumps(items, ensure_ascii=False, indent=2)}

CALCULS :
- Sous-total HT : {subtotal_ht:.2f}€
- Remise ({discount_pct}%) : -{discount_amount:.2f}€
- Total HT : {total_ht:.2f}€
- TVA (20%) : {tva:.2f}€
- Total TTC : {total_ttc:.2f}€

NOTES : {input_data.get('notes', '')}
CONDITIONS DE PAIEMENT : {input_data.get('payment_terms', '30 jours')}

Retourne un JSON :
{{
  "document_type": "devis" | "facture" | "avoir",
  "document_number": "<numéro séquentiel>",
  "date": "<date du jour>",
  "validity_date": "<date + 30j pour devis>",
  "emitter": {{...}},
  "client": {{...}},
  "lines": [
    {{"description": "...", "quantity": <n>, "unit_price_ht": <prix>, "total_ht": <total>}}
  ],
  "subtotal_ht": {subtotal_ht:.2f},
  "discount": {{"percent": {discount_pct}, "amount": {discount_amount:.2f}}},
  "total_ht": {total_ht:.2f},
  "tva_rate": 20,
  "tva_amount": {tva:.2f},
  "total_ttc": {total_ttc:.2f},
  "payment_terms": "...",
  "notes": "...",
  "legal_mentions": "<mentions légales adaptées>",
  "cover_email": {{"subject": "...", "body": "<email d'accompagnement>"}}
}}
"""

        response_text = await self.call_claude(
            prompt=prompt,
            system=SYSTEM_PROMPT,
            max_tokens=2048,
            temperature=0.3,  # Précision maximale pour les docs financiers
        )


        data = self._parse_json(response_text)
        data["action_performed"] = action
        data["computed_totals"] = {
            "subtotal_ht": subtotal_ht,
            "discount_amount": discount_amount,
            "total_ht": total_ht,
            "tva": tva,
            "total_ttc": total_ttc,
        }

        return data
