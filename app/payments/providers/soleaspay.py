"""Fournisseur SoleasPay v3 (intégration réelle).

Documentation : https://doc.mysoleas.com/soleaspay-v3/
API de base : https://soleaspay.com

- Collecte (Pay-In) : POST /api/agent/bills/v3
  Headers : x-api-key (clé publique), operation=2, service=<service_id>
  Body JSON : wallet, amount, currency, order_id, description, payer, ...
- Vérification : GET /api/agent/verif-pay?orderId=...&payId=...
- Callback (webhook) : header x-private-key = SHA-512(secret)
"""
import hashlib
import hmac

import requests
from flask import current_app

from app.payments.providers.base import BaseProvider, ProviderError


class SoleasPayProvider(BaseProvider):
    name = "soleaspay"

    STATUS_MAP = {
        "SUCCESS": "successful",
        "RECEIVED": "processing",
        "PROCESSING": "processing",
        "REFUND": "failed",
        "FAILURE": "failed",
        "FAILED": "failed",
        "CANCELLED": "cancelled",
    }

    @property
    def base_url(self):
        return current_app.config.get("SOLEASPAY_BASE_URL") or "https://soleaspay.com"

    @property
    def api_key(self):
        key = current_app.config.get("SOLEASPAY_API_KEY")
        if not key:
            raise ProviderError("SOLEASPAY_API_KEY non configuré.")
        return key

    def normalize_status(self, raw):
        return self.STATUS_MAP.get(str(raw).upper(), "pending")

    def initiate_deposit(self, deposit, otp=None):
        """Collecte (Pay-In) d'un dépôt Mobile Money."""
        headers = {
            "Content-Type": "application/json",
            "x-api-key": self.api_key,
            "operation": "2",
            "service": str(deposit.service_id),
        }
        if otp:
            headers["otp"] = str(otp)  # requis pour Orange Money
        payload = {
            "wallet": deposit.phone_number,
            "amount": deposit.amount,
            "currency": deposit.currency,
            "order_id": deposit.reference,
            "description": "Dépôt NAMARA",
            "payer": "Client NAMARA",
        }
        data = self._post("/api/agent/bills/v3", json=payload, headers=headers)
        info = data.get("data") or {}
        deposit.external_ref = info.get("reference")  # payId SoleasPay
        deposit.status = "processing"
        return {"status": "processing", "external_ref": deposit.external_ref}

    def verify_status(self, external_ref, order_id=None):
        headers = {
            "x-api-key": self.api_key,
            "operation": "2",
        }
        params = {}
        if order_id:
            params["orderId"] = order_id
        if external_ref:
            params["payId"] = external_ref
        data = self._get("/api/agent/verif-pay", headers=headers, params=params)
        return self.normalize_status(data.get("status"))

    def process_webhook(self, payload):
        """Normalise le callback SoleasPay en structure standard."""
        data = payload.get("data") or {}
        return {
            "reference": data.get("external_reference"),
            "external_ref": data.get("reference"),
            "amount": data.get("amount"),
            "currency": data.get("currency"),
            "status": self.normalize_status(payload.get("status")),
        }

    def verify_signature(self, request):
        """Vérifie l'en-tête x-private-key = SHA-512(secret)."""
        supplied = request.headers.get("x-private-key")
        if not supplied:
            return False
        secret = (
            current_app.config.get("SOLEASPAY_WEBHOOK_SECRET")
            or current_app.config.get("SOLEASPAY_API_SECRET")
        )
        if not secret:
            return False
        expected = hashlib.sha512(secret.encode()).hexdigest()
        return hmac.compare_digest(supplied.lower(), expected.lower())

    # --- helpers HTTP ---
    def _post(self, path, json=None, headers=None):
        try:
            resp = requests.post(self.base_url + path, json=json, headers=headers, timeout=15)
        except requests.RequestException as exc:
            raise ProviderError(f"Erreur réseau SoleasPay : {exc}")
        return self._parse(resp)

    def _get(self, path, headers=None, params=None):
        try:
            resp = requests.get(self.base_url + path, headers=headers, params=params, timeout=15)
        except requests.RequestException as exc:
            raise ProviderError(f"Erreur réseau SoleasPay : {exc}")
        return self._parse(resp)

    def _parse(self, resp):
        try:
            data = resp.json()
        except ValueError:
            raise ProviderError(f"Réponse SoleasPay invalide (HTTP {resp.status_code}).")
        if not data.get("success"):
            raise ProviderError(f"SoleasPay : {data.get('message', 'opération refusée')}")
        return data

