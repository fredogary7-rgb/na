"""Service de notifications extensible (in-app + interfaces SMS/e-mail).

Ne prétend jamais qu'un SMS ou e-mail a été envoyé si aucun fournisseur n'est
configuré : les interfaces externes sont des no-op explicites par défaut.
"""
from app.extensions import db
from app.models import Notification


def notify(user_id: int, event: str, title: str, message: str) -> Notification:
    notification = Notification(user_id=user_id, event=event, title=title, message=message)
    db.session.add(notification)
    return notification


def send_sms(phone_number: str, message: str) -> None:
    """No-op tant qu'aucun fournisseur SMS n'est configuré."""
    # Intégration future : brancher un fournisseur SMS ici.
    return None


def send_email(address: str, subject: str, body: str) -> None:
    """No-op tant qu'aucun fournisseur e-mail n'est configuré."""
    # Intégration future : brancher un fournisseur e-mail ici.
    return None
