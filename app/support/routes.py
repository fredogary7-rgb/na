"""Routes du support client : API chat web + webhook Telegram."""
import hmac

from flask import Blueprint, current_app, jsonify, render_template, request
from flask_login import current_user
from werkzeug.exceptions import abort

from app.extensions import csrf, db, limiter
from app.models import SupportConversation
from app.services import support
from app.support import knowledge_base as kb
from app.support import password_flow
from app.support import telegram_handler

support_bp = Blueprint("support", __name__)


@support_bp.route("/chat")
def chat_page():
    """Page de chat dédiée (service client)."""
    return render_template("support/chat.html")


def _serialize_message(msg):
    return {
        "id": msg.id,
        "sender_type": msg.sender_type,
        "text": msg.message_text,
        "created_at": msg.created_at.strftime("%H:%M") if msg.created_at else "",
    }


def _serialize_conversation(conv):
    return {
        "reference": conv.public_reference,
        "status": conv.status,
        "category": support.category_label(conv.category),
    }


# ---------------------------------------------------------------------------
# Chat web (widget)
# ---------------------------------------------------------------------------
@support_bp.route("/api/conversation", methods=["POST"])
@csrf.exempt
@limiter.limit("20 per minute")
def api_create_conversation():
    data = request.get_json(silent=True) or {}
    session_hash = (data.get("session_hash") or "").strip()
    if len(session_hash) < 16 or len(session_hash) > 128:
        return jsonify({"error": "session_hash invalide"}), 400

    user_id = current_user.id if current_user.is_authenticated else None
    category = data.get("category") or None
    conv = support.get_or_create_web_conversation(session_hash, user_id=user_id, category=category)
    db.session.commit()
    return jsonify(_serialize_conversation(conv))


@support_bp.route("/api/message", methods=["POST"])
@csrf.exempt
@limiter.limit("30 per minute")
def api_send_message():
    data = request.get_json(silent=True) or {}
    session_hash = (data.get("session_hash") or "").strip()
    text = (data.get("text") or "").strip()
    action = (data.get("action") or "").strip()

    if not text and not action:
        return jsonify({"error": "message vide"}), 400

    conv = support.get_web_conversation(session_hash)
    if conv is None:
        return jsonify({"error": "conversation introuvable"}), 404

    buttons = []

    # Option « modifier mon mot de passe » (flux de vérification d'identité).
    if action == "password_change":
        support.add_message(conv, "visitor", "Modifier mon mot de passe")
        conv.category = "account"
        reply = password_flow.start(conv)
        bot_msg = support.add_message(conv, "bot", reply)
        db.session.commit()
        return jsonify({
            "ok": True,
            "reply": reply,
            "buttons": [],
            "reference": conv.public_reference,
            "last_id": bot_msg.id,
        })

    if action:
        result = kb.resolve_intent(action)
        if result is None:
            return jsonify({"error": "action inconnue"}), 400
        support.add_message(conv, "visitor", kb.BUTTON_LABELS.get(action, action))
        reply = result["reply"]
        if result["intent"] == "human":
            reply += f"\n\nRéférence de votre demande : {conv.public_reference}"
        conv.last_intent = result["intent"]
        if result["category"]:
            conv.category = result["category"]
        buttons = result["buttons"]
    else:
        if len(text) > current_app.config.get("SUPPORT_MESSAGE_MAX_LENGTH", 2000):
            return jsonify({"error": "message trop long"}), 400
        if password_flow.is_active(conv):
            # Les mots de passe saisis ne sont jamais journalisés.
            support.add_message(
                conv, "visitor",
                password_flow.REDACTED if password_flow.is_sensitive_step(conv) else text,
            )
            reply = password_flow.handle(conv, text)
        else:
            support.add_message(conv, "visitor", text)
            result = kb.resolve(text, context=conv.last_intent)
            reply = result["reply"]
            if result["intent"] == "human":
                reply += f"\n\nRéférence de votre demande : {conv.public_reference}"
            conv.last_intent = result["intent"]
            if result["category"]:
                conv.category = result["category"]
            buttons = result["buttons"]

    bot_msg = support.add_message(conv, "bot", reply)
    db.session.commit()

    return jsonify({
        "ok": True,
        "reply": reply,
        "buttons": kb.button_payload(buttons),
        "reference": conv.public_reference,
        "last_id": bot_msg.id,
    })


@support_bp.route("/api/messages", methods=["GET"])
@csrf.exempt
@limiter.limit("60 per minute")
def api_get_messages():
    session_hash = (request.args.get("session_hash") or "").strip()
    conv = support.get_web_conversation(session_hash)
    if conv is None:
        return jsonify({"messages": [], "status": None, "reference": None})
    after_id = request.args.get("after_id", type=int) or 0
    messages = [m for m in conv.messages.all() if m.id > after_id and not m.internal_note]
    return jsonify({
        "messages": [_serialize_message(m) for m in messages],
        "status": conv.status,
        "reference": conv.public_reference,
    })


# ---------------------------------------------------------------------------
# Webhook Telegram
# ---------------------------------------------------------------------------
@support_bp.route("/telegram/webhook", methods=["POST"])
@csrf.exempt
def telegram_webhook():
    secret = current_app.config.get("TELEGRAM_WEBHOOK_SECRET")
    if not secret:
        return jsonify({"error": "webhook non configuré"}), 503
    header = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
    if not hmac.compare_digest(header, secret):
        return jsonify({"error": "non autorisé"}), 403

    update = request.get_json(silent=True)
    if not isinstance(update, dict):
        return jsonify({"error": "données invalides"}), 400

    try:
        telegram_handler.handle_update(update)
        db.session.commit()
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Erreur webhook Telegram")
        return jsonify({"error": "erreur interne"}), 500

    return jsonify({"ok": True})
