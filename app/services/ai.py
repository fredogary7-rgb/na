"""Fournisseur d'IA optionnel (compatible OpenAI), configurable par variable d'environnement.

L'IA n'est utilisée qu'en dernier recours (niveau 3). Elle reçoit uniquement le
contexte factuel du site et ne doit jamais inventer de règle, de montant ni de
délai. Elle ne peut exécuter aucune opération financière.
"""
import requests
from flask import current_app


class AIUnavailable(Exception):
    """L'IA n'est pas configurée ou a échoué."""


def is_configured():
    return bool(current_app.config.get("AI_API_KEY"))


def ask(question, context):
    """Interroge le fournisseur d'IA avec un contexte restreint.

    Lève AIUnavailable si non configuré ou en cas d'erreur / délai dépassé.
    """
    key = current_app.config.get("AI_API_KEY")
    if not key:
        raise AIUnavailable("IA non configurée")

    base_url = current_app.config.get("AI_BASE_URL", "https://api.openai.com/v1")
    model = current_app.config.get("AI_MODEL", "gpt-4o-mini")
    timeout = current_app.config.get("AI_TIMEOUT", 10)

    system = (
        "Tu es le service client de NAMARA, une plateforme financière en francs CFA. "
        "Réponds uniquement à partir du CONTEXTE fourni. N'invente jamais de règle, de montant, "
        "de délai ni de gain. Ne demande jamais de mot de passe ni de code OTP. "
        "Si le contexte ne permet pas de répondre, dis-le clairement et propose de parler à un conseiller."
    )
    try:
        resp = requests.post(
            f"{base_url}/chat/completions",
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": f"CONTEXTE :\n{context}\n\nQUESTION : {question}"},
                ],
            },
            headers={"Authorization": f"Bearer {key}"},
            timeout=timeout,
        )
        data = resp.json()
        content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        return content.strip() if content else None
    except requests.RequestException as exc:
        raise AIUnavailable(f"Erreur réseau IA : {exc}")
    except (ValueError, KeyError, IndexError, TypeError) as exc:
        raise AIUnavailable(f"Réponse IA invalide : {exc}")
