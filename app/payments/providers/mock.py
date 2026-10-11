"""Fournisseur simulé, explicitement identifié comme tel.

Utilisé uniquement en développement et dans les tests automatisés. Aucun fonds
réel n'est manipulé et aucune simulation n'est présentée comme une transaction
réelle dans l'interface.
"""
import hashlib
import hmac

from flask import current_app, request

from app.payments.providers.base import BaseProvider, ProviderError


class MockProvider(BaseProvider):
    name = "mock"

    # Statuts bruts de la simulation -> statuts normalisés.
    STATUS_MAP = {
        "pending": "pending",
        "processing": "processing",
        "success": "successful",
        "failed": "failed",
        "rejected": "rejected",
        "cancelled": "cancelled",
    }

    def initiate_deposit(self, deposit, otp=None):
        # Aucun paiement réel : la demande reste en attente d'une confirmation
        # webhook authentifiée (fournie par les tests ou un outil de dev).
        return {"status": "pending", "external_ref": None}

    def verify_status(self, external_ref: str):
        return "pending"

    def normalize_status(self, raw) -> str:
        return self.STATUS_MAP.get(str(raw).lower(), "unknown")

    def process_webhook(self, payload: dict) -> dict:
        reference = payload.get("reference")
        if not reference:
            raise ProviderError("Référence manquante dans l'événement.")
        return {
            "reference": reference,
            "amount": payload.get("amount"),
            "currency": payload.get("currency"),
            "status": self.normalize_status(payload.get("status")),
            "external_ref": payload.get("external_ref"),
        }

    def _signature(self, body: bytes) -> str:
        # Clé HMAC dérivée de SECRET_KEY (aucun secret matériel codé en dur).
        secret = current_app.config.get("SOLEASPAY_WEBHOOK_SECRET") or current_app.config["SECRET_KEY"]
        return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()

    def verify_signature(self, req) -> bool:
        supplied = req.headers.get("X-Namara-Signature")
        if not supplied:
            return False
        expected = self._signature(req.get_data())
        return hmac.compare_digest(supplied, expected)
