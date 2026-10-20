"""Fournisseur DrimPay v2 (intégration réelle Mobile Money).

Documentation : https://drimpay.com/fr/docs/payin
Base URL live : https://drimpay.com/api/v2 (le préfixe /v2 est déjà inclus).
- Collecte (Pay-In) : POST /payin/initiate
  Headers : Authorization: Bearer <dp_live_sk_...>
- Vérification : GET /payin/{reference}
- Webhook : header X-DrimPay-Signature = t=<ts>,v1=<HMAC-SHA256>
  HMAC_SHA256(key=DRIMPAY_WEBHOOK_SECRET, data="{timestamp}.{raw_body}")
"""
import hashlib
import hmac
import time

import requests
from flask import current_app

from app.constants import COUNTRIES
from app.payments.providers.base import BaseProvider, ProviderError


class DrimPayProvider(BaseProvider):
    name = "drimpay"

    # Statuts DrimPay -> statuts normalisés NAMARA.
    STATUS_MAP = {
        "queued": "processing",
        "pending": "processing",
        "processing": "processing",
        "success": "successful",
        "failed": "failed",
        "expired": "failed",
        "cancelled": "cancelled",
        "reversed": "failed",
    }

    # Marques NAMARA -> slug opérateur DrimPay.
    OPERATOR_SLUG = {
        "MTN": "mtn",
        "Moov": "moov",
        "Orange": "orange",
        "Wave": "wave",
        "Airtel": "airtel",
        "Vodacom": "vodacom",
        "Mix": "tmoney",   # T-Money Togo
        "Mov": "moov",
    }

    @property
    def base_url(self):
        key = current_app.config.get("DRIMPAY_API_KEY") or ""
        if key.startswith("dp_sandbox_sk_"):
            return current_app.config.get("DRIMPAY_SANDBOX_BASE_URL") or "https://drimpay.com/sandbox-api/v2"
        return current_app.config.get("DRIMPAY_BASE_URL") or "https://drimpay.com/api/v2"

    @property
    def api_key(self):
        key = current_app.config.get("DRIMPAY_API_KEY")
        if not key:
            raise ProviderError("DRIMPAY_API_KEY non configuré.")
        return key

    def normalize_status(self, raw):
        return self.STATUS_MAP.get(str(raw).lower(), "pending")

    def initiate_deposit(self, deposit, otp=None):
        """Collecte (Pay-In) d'un dépôt Mobile Money via DrimPay."""
        payload = {
            "amount": deposit.amount,
            "currency": deposit.currency,
            "country_code": self._country_code(deposit.country),
            "operator": self._operator_slug(deposit.operator),
            "phone": self._phone(deposit.phone_number),
            "order_id": deposit.reference,
            "description": "Dépôt NAMARA",
        }
        webhook_url = current_app.config.get("DRIMPAY_WEBHOOK_URL")
        if webhook_url:
            payload["webhook_url"] = webhook_url
        if otp:
            payload["operator_otp"] = str(otp)

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        current_app.logger.info(
            "DRIMPAY PAY IN | url=%s | body=%s",
            self.base_url + "/payin/initiate",
            payload,
        )
        data = self._post("/payin/initiate", json=payload, headers=headers)
        current_app.logger.info("DRIMPAY PAY IN RESPONSE | %s", data)

        deposit.external_ref = data.get("reference")
        deposit.status = "processing"
        return {"status": "processing", "external_ref": deposit.external_ref}

    def verify_status(self, external_ref, order_id=None):
        headers = {"Authorization": f"Bearer {self.api_key}"}
        data = self._get(f"/payin/{external_ref}", headers=headers)
        return self.normalize_status(data.get("status"))

    def process_webhook(self, payload):
        """Normalise le callback DrimPay en structure standard."""
        return {
            "reference": payload.get("order_id"),
            "external_ref": payload.get("reference"),
            "amount": payload.get("amount"),
            "currency": payload.get("currency"),
            "status": self.normalize_status(payload.get("status")),
        }

    def verify_signature(self, request):
        """Vérifie l'en-tête X-DrimPay-Signature (HMAC-SHA256)."""
        supplied = request.headers.get("X-DrimPay-Signature", "")
        timestamp = None
        signature = None
        for part in supplied.split(","):
            if "=" in part:
                key, value = part.split("=", 1)
                key = key.strip()
                value = value.strip()
                if key == "t":
                    timestamp = value
                elif key == "v1":
                    signature = value
        if not timestamp or not signature:
            return False
        try:
            ts = int(timestamp)
        except (TypeError, ValueError):
            return False
        # Protection anti-rejeu : tolérance ±5 minutes.
        if abs(int(time.time()) - ts) > 300:
            return False

        secret = current_app.config.get("DRIMPAY_WEBHOOK_SECRET")
        if not secret:
            return False

        raw_body = request.get_data()
        signed = f"{timestamp}.".encode() + raw_body
        expected = hmac.new(secret.encode(), signed, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, signature)

    # --- helpers ---
    @staticmethod
    def _country_code(country):
        return COUNTRIES.get(country, {}).get("code") or country

    @classmethod
    def _operator_slug(cls, operator):
        return cls.OPERATOR_SLUG.get(str(operator), str(operator).lower())

    @staticmethod
    def _phone(phone):
        # DrimPay attend le numéro local sans indicatif (ex. 71339325 au Togo).
        return str(phone or "").strip()

    def _post(self, path, json=None, headers=None):
        try:
            resp = requests.post(self.base_url + path, json=json, headers=headers, timeout=30)
        except requests.RequestException as exc:
            raise ProviderError(f"Erreur réseau DrimPay : {exc}")
        return self._parse(resp)

    def _get(self, path, headers=None):
        try:
            resp = requests.get(self.base_url + path, headers=headers, timeout=30)
        except requests.RequestException as exc:
            raise ProviderError(f"Erreur réseau DrimPay : {exc}")
        return self._parse(resp)

    def _parse(self, resp):
        try:
            data = resp.json()
        except ValueError:
            raise ProviderError(f"Réponse DrimPay invalide (HTTP {resp.status_code}).")
        if not (200 <= resp.status_code < 300):
            current_app.logger.warning("DRIMPAY ERROR | http=%s | body=%s", resp.status_code, data)
            raise ProviderError(f"DrimPay : {data.get('message') or data.get('error') or 'opération refusée'}")
        return data

