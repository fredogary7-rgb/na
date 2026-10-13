"""Gestion des mises à jour Telegram : commandes, boutons, messages, FAQ."""
from flask import current_app

from app.extensions import db
from app.models import SupportConversation, SupportMessage
from app.services import support
from app.services.telegram import TelegramError, send_message
from app.support import knowledge_base as kb
from app.support import password_flow

WELCOME = (
    "Bonjour et bienvenue chez NAMARA ! 🌿\n\n"
    "Comment pouvons-nous vous aider aujourd'hui ? Choisissez une catégorie "
    "ou écrivez directement votre question.\n\n"
    "Commandes : /start /help /contact /status /cancel /privacy /password"
)

HELP_TEXT = (
    "Catégories d'assistance :\n"
    "• Problème de compte\n• Dépôt\n• Retrait\n• Produits\n• Parrainage\n"
    "• Problème technique\n• Parler à un conseiller\n\n"
    "Utilisez /contact pour parler à un conseiller, /status pour suivre une demande,\n"
    "ou /password pour modifier votre mot de passe (avec vérification d'identité)."
)

PRIVACY_TEXT = (
    "Confidentialité NAMARA : nous ne vous demanderons jamais votre mot de passe, "
    "votre code OTP, votre code PIN Mobile Money, votre CVV ou votre token d'accès. "
    "Vos échanges sont enregistrés de façon sécurisée pour le suivi de votre demande."
)

CATEGORY_KEYBOARD = {
    "inline_keyboard": [
        [{"text": "Problème de compte", "callback_data": "cat:account"}],
        [{"text": "Dépôt", "callback_data": "cat:deposit"},
         {"text": "Retrait", "callback_data": "cat:withdrawal"}],
        [{"text": "Produits", "callback_data": "cat:products"},
         {"text": "Parrainage", "callback_data": "cat:referral"}],
        [{"text": "Problème technique", "callback_data": "cat:technical"}],
        [{"text": "🔒 Modifier mon mot de passe", "callback_data": "pw:start"}],
        [{"text": "Parler à un conseiller", "callback_data": "cat:human"}],
    ]
}

STATUS_LABELS = {"open": "ouverte", "pending": "en attente", "answered": "répondue", "closed": "fermée"}


def _notify_support(conversation):
    admin_chat_id = current_app.config.get("TELEGRAM_ADMIN_CHAT_ID")
    if not admin_chat_id:
        return
    try:
        send_message(
            admin_chat_id,
            f"🆘 Nouvelle demande (réf. {conversation.public_reference}, "
            f"catégorie {support.category_label(conversation.category)}).",
        )
    except TelegramError:
        pass


def handle_update(update: dict) -> bool:
    """Traite un update Telegram. False = événement déjà traité (idempotence)."""
    update_id = str(update.get("update_id", ""))
    if update_id and SupportMessage.query.filter_by(telegram_update_id=update_id).first() is not None:
        return False
    if "message" in update:
        _handle_message(update["message"], update_id)
        return True
    if "callback_query" in update:
        _handle_callback(update["callback_query"], update_id)
        return True
    return False


def _handle_message(message, update_id):
    chat_id = message.get("chat", {}).get("id")
    text = (message.get("text") or "").strip()
    if text.startswith("/"):
        _handle_command(chat_id, text)
        return
    if text:
        _route_text(chat_id, text, update_id)
        return
    if message.get("photo"):
        _route_text(chat_id, "[Capture d'écran reçue]", update_id)
        return
    try:
        send_message(chat_id, "Je n'ai pas compris. Utilisez /help pour voir les catégories.")
    except TelegramError:
        pass


def _handle_command(chat_id, text):
    parts = text.split(maxsplit=1)
    command = parts[0].split("@")[0].lower()
    arg = parts[1] if len(parts) > 1 else None
    if command == "/start":
        try:
            send_message(chat_id, WELCOME, reply_markup=CATEGORY_KEYBOARD)
        except TelegramError:
            pass
    elif command == "/help":
        try:
            send_message(chat_id, HELP_TEXT, reply_markup=CATEGORY_KEYBOARD)
        except TelegramError:
            pass
    elif command == "/contact":
        _request_human(chat_id)
    elif command == "/password":
        _start_password_change(chat_id)
    elif command == "/status":
        _status(chat_id, arg)
    elif command == "/cancel":
        conv = support.get_or_create_telegram_conversation(chat_id)
        conv.last_intent = None
        try:
            send_message(chat_id, "Saisie annulée. Comment puis-je vous aider ?")
        except TelegramError:
            pass
    elif command == "/privacy":
        try:
            send_message(chat_id, PRIVACY_TEXT)
        except TelegramError:
            pass
    else:
        try:
            send_message(chat_id, "Commande inconnue. Utilisez /help.")
        except TelegramError:
            pass



def _status(chat_id, reference):
    if not reference:
        try:
            send_message(chat_id, "Utilisez /status suivi de votre référence, ex : /status SC-ABCD1234")
        except TelegramError:
            pass
        return
    target = SupportConversation.query.filter_by(public_reference=reference.strip().upper()).first()
    if target is None or target.channel != "telegram" or target.telegram_chat_id != str(chat_id):
        try:
            send_message(chat_id, "Aucune demande trouvée avec cette référence.")
        except TelegramError:
            pass
        return
    try:
        send_message(
            chat_id,
            f"Demande {target.public_reference} — statut : {STATUS_LABELS.get(target.status, target.status)}.",
        )
    except TelegramError:
        pass


def _request_human(chat_id):
    conv = support.get_or_create_telegram_conversation(chat_id, category="human", subject="Demande de conseiller")
    support.add_message(conv, "visitor", "Demande de conseiller")
    conv.last_intent = "human"
    _notify_support(conv)
    try:
        send_message(
            chat_id,
            "Votre demande a été transmise au service client NAMARA. Un conseiller vous "
            f"répondra dès que possible. Référence : {conv.public_reference}",
        )
    except TelegramError:
        pass


def _start_password_change(chat_id):
    conv = support.get_or_create_telegram_conversation(
        chat_id, category="account", subject="Modification du mot de passe"
    )
    support.add_message(conv, "visitor", "Modifier mon mot de passe")
    reply = password_flow.start(conv)
    support.add_message(conv, "bot", reply)
    try:
        send_message(chat_id, reply)
    except TelegramError:
        pass


def _route_text(chat_id, text, update_id):
    conv = support.get_or_create_telegram_conversation(chat_id)

    # Flux de modification du mot de passe (les mots de passe ne sont jamais journalisés).
    if password_flow.is_active(conv):
        support.add_message(
            conv, "visitor",
            password_flow.REDACTED if password_flow.is_sensitive_step(conv) else text,
            telegram_update_id=update_id,
        )
        reply = password_flow.handle(conv, text)
        support.add_message(conv, "bot", reply)
        try:
            send_message(chat_id, reply)
        except TelegramError:
            pass
        return

    support.add_message(conv, "visitor", text, telegram_update_id=update_id)

    result = kb.resolve(text, context=conv.last_intent)
    reply = result["reply"]

    if result["intent"] == "human":
        reply += f"\n\nRéférence de votre demande : {conv.public_reference}"
        conv.category = "human"
        conv.last_intent = "human"
        _notify_support(conv)
    else:
        conv.last_intent = result["intent"]
        if result["category"]:
            conv.category = result["category"]
        if result["handoff"]:
            _notify_support(conv)

    support.add_message(conv, "bot", reply)
    try:
        send_message(chat_id, reply, reply_markup=kb.build_keyboard(result["buttons"]))
    except TelegramError:
        pass


def _answer_intent(chat_id, key, update_id=None):
    intent = kb.INTENTS_BY_KEY.get(key)
    if intent is None:
        return
    conv = support.get_or_create_telegram_conversation(chat_id, category=intent["category"])
    reply = intent["answer"]()
    conv.last_intent = key
    conv.category = intent["category"]
    if key == "human":
        reply += f"\n\nRéférence de votre demande : {conv.public_reference}"
        _notify_support(conv)
    support.add_message(conv, "bot", reply)
    try:
        send_message(chat_id, reply, reply_markup=kb.build_keyboard(intent.get("buttons", [])))
    except TelegramError:
        pass


def _handle_callback(callback, update_id):
    chat_id = callback.get("message", {}).get("chat", {}).get("id")
    data = callback.get("data", "")
    if not data:
        return
    if data in ("pw:start", "intent:password_change"):
        _start_password_change(chat_id)
    elif data.startswith("intent:"):
        _answer_intent(chat_id, data[7:], update_id)
    elif data.startswith("cat:"):
        category = data[4:]
        _answer_intent(chat_id, kb.CATEGORY_TO_INTENT.get(category, category), update_id)
