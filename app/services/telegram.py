"""Client Telegram Bot API (via requests). Le token est lu depuis l'environnement."""
import os

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


def send_channel_message(text, reply_markup=None):
    """Envoie un message texte vers la chaîne Telegram configurée (TELEGRAM_CHANNEL_ID)."""
    chat_id = current_app.config.get("TELEGRAM_CHANNEL_ID")
    if not chat_id:
        raise TelegramError("TELEGRAM_CHANNEL_ID non configuré.")
    return send_message(chat_id, text, reply_markup=reply_markup)


def send_photo(chat_id, photo_path, caption=None):
    """Envoie une photo (fichier local) avec une légende optionnelle."""
    payload = {"chat_id": chat_id}
    if caption is not None:
        payload["caption"] = caption
    url = f"https://api.telegram.org/bot{_token()}/sendPhoto"
    try:
        with open(photo_path, "rb") as fh:
            resp = requests.post(url, data=payload, files={"photo": fh}, timeout=20)
        data = resp.json()
    except (requests.RequestException, OSError) as exc:
        raise TelegramError(f"Erreur réseau Telegram : {exc}")
    if not data.get("ok"):
        raise TelegramError(f"Erreur Telegram : {data}")
    return data.get("result")


def logo_path():
    """Chemin du logo NAMARA (fichier image local)."""
    return os.path.join(current_app.static_folder, "images", "namara.jpeg")


def send_channel_photo(photo_path, caption=None):
    """Envoie une photo vers la chaîne Telegram configurée (TELEGRAM_CHANNEL_ID)."""
    chat_id = current_app.config.get("TELEGRAM_CHANNEL_ID")
    if not chat_id:
        raise TelegramError("TELEGRAM_CHANNEL_ID non configuré.")
    return send_photo(chat_id, photo_path, caption=caption)


def send_channel_info(app_name="NAMARA", app_slogan="Votre capital, une vision d'avenir."):
    """Envoie le logo NAMARA + le message « fonctionnement » à la chaîne."""
    return send_channel_photo(logo_path(), caption=platform_info_text(app_name, app_slogan))


def _fmt_amount(amount):
    return f"{int(amount):,}".replace(",", " ")


def platform_info_text(app_name="NAMARA", app_slogan="Votre capital, une vision d'avenir."):
    """Message d'information : montants minimaux, produits disponibles et fonctionnement."""
    from app.services import settings
    from app.services.investment import available_products

    min_deposit = settings.get_int("MIN_DEPOSIT", 3000)
    min_withdrawal = settings.get_int("MIN_WITHDRAWAL", 1500)
    fee_bps = settings.get_int("WITHDRAWAL_FEE_BPS", 800)

    lines = [
        f"🌿 {app_name} — {app_slogan}",
        "",
        f"💳 Dépôt minimum : {_fmt_amount(min_deposit)} FCFA",
        f"🏦 Retrait minimum : {_fmt_amount(min_withdrawal)} FCFA (frais {fee_bps / 100:.2f} %)",
        "",
        "📦 Produits disponibles :",
    ]
    products = available_products()
    if products:
        for p in products:
            lines.append(
                f"• {p.name} — {_fmt_amount(p.min_amount)} FCFA — {p.duration_days} jours"
            )
    else:
        lines.append("• Aucun produit disponible pour le moment.")
    lines += [
        "",
        "Comment ça marche :",
        "1. Créez votre compte (nom, téléphone, pays).",
        "2. Vérifiez votre téléphone.",
        "3. Effectuez un dépôt via Mobile Money.",
        "4. Gérez vos soldes (dépôts, bonus, revenus, commissions, solde retirable).",
        "",
        "Assistance : Telegram @narama_bot ou le chat du site.",
    ]
    return "\n".join(lines)


def set_webhook(url, secret_token=None):
    payload = {"url": url}
    if secret_token:
        payload["secret_token"] = secret_token
    return _call("setWebhook", payload)


def delete_webhook():
    return _call("deleteWebhook", {})
