"""Client Telegram Bot API (via requests). Le token est lu depuis l'environnement."""
import requests
from flask import current_app


class TelegramError(Exception):
    pass


def _token():
    token = current_app.config.get("TELEGRAM_BOT_TOKEN")
    if not token:
        raise TelegramError("TELEGRAM_BOT_TOKEN non configuré.")
    return token


def _call(method, payload, timeout=10):
    url = f"https://api.telegram.org/bot{_token()}/{method}"
    try:
        resp = requests.post(url, json=payload, timeout=timeout)
        data = resp.json()
    except requests.RequestException as exc:
        raise TelegramError(f"Erreur réseau Telegram : {exc}")
    if not data.get("ok"):
        raise TelegramError(f"Erreur Telegram : {data}")
    return data.get("result")


def send_message(chat_id, text, reply_markup=None):
    payload = {"chat_id": chat_id, "text": text}
    if reply_markup is not None:
        payload["reply_markup"] = reply_markup
    return _call("sendMessage", payload)


def set_webhook(url, secret_token=None):
    payload = {"url": url}
    if secret_token:
        payload["secret_token"] = secret_token
    return _call("setWebhook", payload)


def delete_webhook():
    return _call("deleteWebhook", {})
