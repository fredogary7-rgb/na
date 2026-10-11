"""Tests du service client (Telegram + chat web)."""
import pytest

from app.models import SupportConversation, SupportMessage, User
from app.services import support
from app.services.telegram import TelegramError
from app.support import knowledge_base as kb
from app.support import telegram_handler

from tests.helpers import login, make_user


def _webhook(app, client, payload, secret=None):
    headers = {}
    if secret:
        headers["X-Telegram-Bot-Api-Secret-Token"] = secret
    return client.post("/support/telegram/webhook", json=payload, headers=headers)


def test_webhook_rejected_when_not_configured(app, client):
    app.config["TELEGRAM_WEBHOOK_SECRET"] = None
    resp = _webhook(app, client, {"update_id": 1, "message": {"text": "hi"}}, secret="x")
    assert resp.status_code == 503


def test_webhook_rejected_wrong_secret(app, client):
    app.config["TELEGRAM_WEBHOOK_SECRET"] = "bon-secret"
    resp = _webhook(app, client, {"update_id": 1}, secret="mauvais")
    assert resp.status_code == 403


def test_webhook_valid_update_creates_conversation(app, client, db):
    app.config["TELEGRAM_WEBHOOK_SECRET"] = "bon-secret"
    update = {
        "update_id": 100,
        "message": {"chat": {"id": "555"}, "text": "bonjour"},
    }
    resp = _webhook(app, client, update, secret="bon-secret")
    assert resp.status_code == 200
    conv = SupportConversation.query.filter_by(channel="telegram", telegram_chat_id="555").first()
    assert conv is not None


def test_telegram_dedup(app, client, db):
    app.config["TELEGRAM_WEBHOOK_SECRET"] = "bon-secret"
    update = {"update_id": 777, "message": {"chat": {"id": "555"}, "text": "bonjour"}}
    _webhook(app, client, update, secret="bon-secret")
    count_before = SupportMessage.query.filter_by(telegram_update_id="777").count()
    # Deuxième envoi du même update_id → ignoré.
    _webhook(app, client, update, secret="bon-secret")
    count_after = SupportMessage.query.filter_by(telegram_update_id="777").count()
    assert count_before == 1
    assert count_after == 1


def test_web_conversation_and_message(app, client):
    session_hash = "a" * 32
    resp = client.post("/support/api/conversation", json={"session_hash": session_hash})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["reference"].startswith("SC-")

    resp = client.post("/support/api/message", json={"session_hash": session_hash, "text": "Bonjour"})
    assert resp.status_code == 200

    resp = client.get("/support/api/messages", query_string={"session_hash": session_hash})
    data = resp.get_json()
    assert len(data["messages"]) >= 1


def test_cannot_access_other_conversation(app, client):
    client.post("/support/api/conversation", json={"session_hash": "a" * 32})
    client.post("/support/api/message", json={"session_hash": "a" * 32, "text": "secret"})
    # Un autre visiteur (autre session_hash) ne voit rien.
    resp = client.get("/support/api/messages", query_string={"session_hash": "b" * 32})
    data = resp.get_json()
    assert data["messages"] == []


def test_admin_support_requires_admin(app, client, db):
    user = make_user(db, role="user")
    db.session.commit()
    login(client, user.phone_number)
    resp = client.get("/admin/support")
    assert resp.status_code == 403


def test_telegram_send_message_requires_token(app):
    app.config["TELEGRAM_BOT_TOKEN"] = None
    with app.app_context():
        with pytest.raises(TelegramError):
            from app.services.telegram import send_message

            send_message("123", "coucou")


def test_faq_lookup(app, db):
    support.seed_default_faq()
    db.session.commit()
    faq = support.find_faq("comment créer un compte ?")
    assert faq is not None
    assert "inscription" in (faq.answer or "").lower() or "page d'inscription" in (faq.answer or "")


# ---------------------------------------------------------------------------
# Moteur d'intentions (questions en langage naturel)
# ---------------------------------------------------------------------------
def test_intent_detection_common_messages(app):
    cases = [
        ("Je veux effectuer un dépôt.", "deposit_how"),
        ("Comment déposer de l'argent ?", "deposit_how"),
        ("Mon dépôt n'est pas arrivé.", "deposit_not_credited"),
        ("Comment retirer mes gains ?", "withdrawal_how"),
        ("Mon retrait est bloqué.", "withdrawal_pending"),
        ("Quels sont vos produits ?", "products"),
        ("Comment fonctionne le parrainage ?", "referral_how"),
        ("J'ai oublié mon mot de passe.", "account_password"),
        ("Je veux parler à un conseiller.", "human"),
        ("Bonjour, j'ai une question.", "greeting"),
    ]
    with app.app_context():
        for text, expected in cases:
            result = kb.resolve(text)
            assert result["intent"] == expected, f"{text!r} -> {result['intent']}"
            assert result["reply"], f"réponse vide pour {text!r}"


def test_intent_fault_tolerant(app):
    with app.app_context():
        # Sans accents, fautes d'orthographe légères.
        assert kb.resolve("coment depose de l argent")["intent"] == "deposit_how"
        assert kb.resolve("je veux fair un depot")["intent"] == "deposit_how"
        assert kb.resolve("comen retirer mes gain")["intent"] == "withdrawal_how"
        assert kb.resolve("jai oublie mon mot de passe")["intent"] == "account_password"


def test_unknown_question_triggers_handoff(app):
    with app.app_context():
        result = kb.resolve("azertyuiop qsdfghjklm wxcvbn")
        assert result["handoff"] is True
        assert result["buttons"] == ["human"]
        assert "conseiller" in result["reply"]


def test_ai_unavailable_falls_back_to_handoff(app, monkeypatch):
    from app.services import ai

    def boom(*args, **kwargs):
        raise ai.AIUnavailable("service indisponible")

    monkeypatch.setattr(ai, "ask", boom)
    with app.app_context():
        result = kb.resolve("question totalement inédite xyz123")
        assert result["handoff"] is True


def test_ai_used_when_configured(app, monkeypatch):
    from app.services import ai

    monkeypatch.setattr(ai, "ask", lambda question, context: "Réponse IA de test")
    with app.app_context():
        result = kb.resolve("question jamais vue auparavant")
        assert result["reply"] == "Réponse IA de test"
        assert result["handoff"] is False


def test_conversation_memory_followup(app):
    with app.app_context():
        assert kb.resolve("Je veux faire un dépôt")["intent"] == "deposit_how"
        followup = kb.resolve("Et si l'argent n'arrive pas ?", context="deposit_how")
        assert followup["intent"] == "deposit_not_credited"


def test_deposit_answer_uses_real_minimum(app):
    with app.app_context():
        app.config["MIN_DEPOSIT"] = 5000
        result = kb.resolve("Comment faire un dépôt ?")
        assert "5 000" in result["reply"]


def test_withdrawal_answer_uses_real_fee(app):
    with app.app_context():
        app.config["WITHDRAWAL_FEE_BPS"] = 800
        result = kb.resolve("Comment retirer mes gains ?")
        assert "8.00" in result["reply"]


def test_telegram_human_handoff_creates_ticket(app, client, db):
    app.config["TELEGRAM_WEBHOOK_SECRET"] = "bon-secret"
    app.config["TELEGRAM_BOT_TOKEN"] = None  # éviter tout appel réseau
    update = {"update_id": 900, "message": {"chat": {"id": "700"}, "text": "Je veux parler à un conseiller"}}
    resp = client.post(
        "/support/telegram/webhook", json=update,
        headers={"X-Telegram-Bot-Api-Secret-Token": "bon-secret"},
    )
    assert resp.status_code == 200
    conv = SupportConversation.query.filter_by(channel="telegram", telegram_chat_id="700").first()
    assert conv is not None
    assert conv.category == "human"
    assert conv.last_intent == "human"
    assert conv.messages.filter_by(sender_type="bot").count() >= 1


def test_telegram_free_text_deposit_resolves(app, client, db):
    app.config["TELEGRAM_WEBHOOK_SECRET"] = "bon-secret"
    app.config["TELEGRAM_BOT_TOKEN"] = None
    update = {"update_id": 901, "message": {"chat": {"id": "701"}, "text": "Je veux effectuer un dépôt"}}
    resp = client.post(
        "/support/telegram/webhook", json=update,
        headers={"X-Telegram-Bot-Api-Secret-Token": "bon-secret"},
    )
    assert resp.status_code == 200
    conv = SupportConversation.query.filter_by(channel="telegram", telegram_chat_id="701").first()
    assert conv is not None
    assert conv.last_intent == "deposit_how"
    bot_messages = [m.message_text for m in conv.messages.filter_by(sender_type="bot").all()]
    assert any("Recharger" in (m or "") for m in bot_messages)
