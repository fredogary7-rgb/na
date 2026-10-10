"""Tests du service client (Telegram + chat web)."""
import pytest

from app.models import SupportConversation, SupportMessage, User
from app.services import support
from app.services.telegram import TelegramError
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
