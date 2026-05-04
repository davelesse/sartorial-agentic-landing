"""
═══════════════════════════════════════════════════════════
SARTORIAL AGENTIC — Agent Content Creator
SEO content, product pages, social posts.
═══════════════════════════════════════════════════════════
"""

import json

from app.agents.base import BaseAgent, CLAUDE_MODEL_BALANCED

SYSTEM_PROMPT = """Tu es l'Agent Content Creator de Sartorial Agentic — un rédacteur copywriter d'exception.

Tu produis du contenu premium qui convertit : fiches produits, articles SEO, posts réseaux sociaux.

Règles :
- Ton adapté au secteur : luxe pour beauté/automobile, chaleureux pour restauration, rassurant pour santé, dynamique pour e-commerce.
- SEO natif : mots-clés intégrés naturellement, jamais forcés.
- Structure claire : titres H2/H3 pour contenu long, accroches pour posts courts.
- Appel à l'action discret mais présent.
- Langue : celle demandée dans input_data.locale (défaut: fr).
- Pas de superlatifs gratuits ("incroyable", "révolutionnaire", "le meilleur").

Format de sortie : JSON strict, sans markdown ni texte autour.
"""


class ContentCreatorAgent(BaseAgent):
    slug = "content-creator"
    name = "Agent Content Creator"
    default_model = CLAUDE_MODEL_BALANCED

    async def run(self, input_data: dict) -> dict:
        """
        Input:
            {
                "content_type": "product_page" | "blog_post" | "social_post",
                "topic": "Voiture Mercedes Classe E 2024",
                "sector": "automobile",
                "keywords": ["voiture occasion", "mercedes classe e"],
                "target_length_words": 500,
                "tone": "premium" | "casual" | "expert",
                "locale": "fr"
            }
        Output:
            {
                "title": "...",
                "meta_description": "...",
                "content": "...",   # markdown
                "keywords_used": [...],
                "word_count": 523
            }
        """
        content_type = input_data.get("content_type", "product_page")
        topic = input_data.get("topic")
        sector = input_data.get("sector", "general")
        keywords = input_data.get("keywords", [])
        target_length = int(input_data.get("target_length_words", 500))
        tone = input_data.get("tone", "premium")
        locale = input_data.get("locale", "fr")

        if not topic:
            raise ValueError("'topic' requis")

        valid_types = {"product_page", "blog_post", "social_post"}
        if content_type not in valid_types:
            raise ValueError(f"content_type invalide. Valides : {valid_types}")

        # Length adjustment
        if content_type == "social_post":
            target_length = min(target_length, 280)
        elif content_type == "blog_post":
            target_length = max(target_length, 400)

        prompt = f"""Génère un contenu de type "{content_type}".

SUJET : {topic}
SECTEUR : {sector}
MOTS-CLÉS À INTÉGRER : {', '.join(keywords) if keywords else '(libre)'}
LONGUEUR CIBLE : {target_length} mots
TON : {tone}
LANGUE : {locale}

Retourne UNIQUEMENT un JSON valide au format :
{{
  "title": "Titre optimisé SEO (max 60 caractères)",
  "meta_description": "Meta description (max 155 caractères)",
  "content": "Contenu complet en markdown",
  "keywords_used": ["liste", "des", "mots-clés", "effectivement", "intégrés"]
}}
"""

        response_text = await self.call_claude(
            prompt=prompt,
            system=SYSTEM_PROMPT,
            max_tokens=4096,
            temperature=0.75,
        )


        try:
            data = self._parse_json(response_text)
        except json.JSONDecodeError as e:
            raise ValueError(f"Claude a retourné un JSON invalide : {e}") from e

        for required in ("title", "content"):
            if required not in data:
                raise ValueError(f"Champ '{required}' manquant dans la réponse")

        data.setdefault("meta_description", "")
        data.setdefault("keywords_used", keywords)
        data["word_count"] = len(data["content"].split())

        return data
