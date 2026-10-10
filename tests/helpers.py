"""Aides partagées pour les tests."""
import hashlib
import hmac
import json

from app.constants import WALLET_TYPES
from app.models import User
from app.models.user import new_unique_referral_code
from app.services import finance


def make_user(db, phone="+22997000001", name="Test User", country="Benin",
              currency="XOF", verified=True, role="user"):
    user = User(
        full_name=name,
        phone_number=phone,
        country=country,
        currency=currency,
        role=role,
        is_phone_verified=verified,
        referral_code=new_unique_referral_code(),
    )
    user.set_password("password123")
    db.session.add(user)
    db.session.flush()
    finance.ensure_wallets(user.id, currency, WALLET_TYPES)
    db.session.flush()
    return user


def register(client, phone="+22997000002", country="Benin", referral_code=""):
    return client.post(
        "/auth/register",
        data={
            "full_name": "New User",
            "country": country,
            "phone_number": phone.replace("+229", ""),
            "password": "password123",
            "confirm_password": "password123",
            "referral_code": referral_code,
            "accept_terms": "y",
            "accept_privacy": "y",
        },
        follow_redirects=True,
    )


def login(client, phone="+22997000001", password="password123"):
    return client.post(
        "/auth/login",
        data={"phone_number": phone, "password": password},
        follow_redirects=True,
    )


def signed_webhook(app, data):
    """Construit le corps et la signature HMAC d'un webhook de test."""
    body = json.dumps(data).encode()
    secret = app.config.get("SOLEASPAY_WEBHOOK_SECRET") or app.config["SECRET_KEY"]
    signature = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return body, signature
