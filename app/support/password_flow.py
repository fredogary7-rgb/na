"""Flux de modification du mot de passe via le support (vérification d'identité).

Le bot (chat web + Telegram) peut modifier le mot de passe d'un compte, mais
uniquement après vérification de l'identité : le numéro de téléphone identifie
le compte, et le mot de passe actuel prouve que la personne en est propriétaire.

L'état du flux est conservé dans `SupportConversation.last_intent` (préfixe
"pwd_"). Aucun mot de passe n'est jamais stocké dans cet état, ni dans
l'historique des messages (les saisies sensibles sont remplacées par "••••••••").
"""
import phonenumbers

from app.extensions import db
from app.models import User

# États du flux (préfixe stocké dans last_intent).
PWD_PHONE = "pwd_phone"
PWD_VERIFY = "pwd_verify:"   # "pwd_verify:<user_id>:<tentatives>"
PWD_NEW = "pwd_new:"         # "pwd_new:<user_id>"

MAX_ATTEMPTS = 5
MIN_LENGTH = 8
MAX_LENGTH = 128

PROMPT_PHONE = (
    "Pour modifier votre mot de passe, je dois d'abord vérifier votre identité.\n\n"
    "Veuillez saisir le numéro de téléphone associé à votre compte NAMARA "
    "(au format international, ex. +22997000001)."
)
PROMPT_VERIFY = (
    "Compte identifié ✅\n\n"
    "Pour confirmer votre identité, saisissez votre mot de passe actuel."
)
PROMPT_NEW = (
    "Identité vérifiée ✅\n\n"
    f"Saisissez votre nouveau mot de passe (entre {MIN_LENGTH} et {MAX_LENGTH} caractères)."
)

REDACTED = "••••••••"


def is_active(conv) -> bool:
    """True si la conversation est en cours de modification de mot de passe."""
    state = conv.last_intent or ""
    return state.startswith("pwd_")


def is_sensitive_step(conv) -> bool:
    """True si l'étape en cours attend un mot de passe (à ne jamais journaliser)."""
    state = conv.last_intent or ""
    return state.startswith(PWD_VERIFY) or state.startswith(PWD_NEW)


def start(conv) -> str:
    """Démarre le flux : demande le numéro de téléphone."""
    conv.last_intent = PWD_PHONE
    return PROMPT_PHONE


def handle(conv, text: str):
    """Traite une saisie dans le flux. Retourne la réponse du bot, ou None si hors flux."""
    state = conv.last_intent or ""
    text = (text or "").strip()
    if state == PWD_PHONE:
        return _handle_phone(conv, text)
    if state.startswith(PWD_VERIFY):
        return _handle_verify(conv, state, text)
    if state.startswith(PWD_NEW):
        return _handle_new(conv, state, text)
    return None


def _normalize_phone(raw: str) -> str:
    raw = (raw or "").strip()
    if raw and not raw.startswith("+"):
        raw = "+" + raw
    try:
        parsed = phonenumbers.parse(raw, None)
        if phonenumbers.is_valid_number(parsed):
            return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
    except phonenumbers.NumberParseException:
        pass
    return raw


def _handle_phone(conv, text) -> str:
    phone = _normalize_phone(text)
    user = User.query.filter_by(phone_number=phone).first()
    if user is None:
        # Message générique : ne révèle pas si le numéro existe.
        return (
            "Aucun compte correspondant n'a été trouvé. Vérifiez votre numéro "
            "(format +22997000001) et réessayez."
        )
    conv.last_intent = f"{PWD_VERIFY}{user.id}:0"
    return PROMPT_VERIFY


def _handle_verify(conv, state, text) -> str:
    parts = state.split(":")
    if len(parts) != 3:
        conv.last_intent = None
        return "Session expirée. Veuillez recommencer."
    user = db.session.get(User, int(parts[1]))
    attempts = int(parts[2])
    if user is None:
        conv.last_intent = None
        return "Compte introuvable. Veuillez recommencer."
    if not user.check_password(text):
        attempts += 1
        if attempts >= MAX_ATTEMPTS:
            conv.last_intent = None
            return (
                "Trop de tentatives incorrectes. Pour votre sécurité, la demande "
                "a été annulée. Réessayez plus tard."
            )
        conv.last_intent = f"{PWD_VERIFY}{user.id}:{attempts}"
        return "Mot de passe incorrect. Veuillez réessayer."
    conv.last_intent = f"{PWD_NEW}{user.id}"
    return PROMPT_NEW


def _handle_new(conv, state, text) -> str:
    parts = state.split(":", 1)
    if len(parts) != 2:
        conv.last_intent = None
        return "Session expirée. Veuillez recommencer."
    user = db.session.get(User, int(parts[1]))
    if user is None:
        conv.last_intent = None
        return "Compte introuvable. Veuillez recommencer."
    if len(text) < MIN_LENGTH or len(text) > MAX_LENGTH:
        return (
            f"Le mot de passe doit contenir entre {MIN_LENGTH} et {MAX_LENGTH} "
            "caractères. Réessayez."
        )
    user.set_password(text)
    conv.last_intent = None
    return (
        "Votre mot de passe a été modifié avec succès ✅\n\n"
        "Vous pouvez désormais vous connecter avec votre nouveau mot de passe. "
        "Ne le partagez jamais."
    )
