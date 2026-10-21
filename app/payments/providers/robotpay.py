"""Fournisseur RobotPay / WestPay (Niger) — paiement par page hébergée.

Documentation : https://westpay.cfd
- Dépôt (collecte) : redirection vers une page de paiement hébergée
  https://checkout1.westpay.cfd/pay?merchant=<slug>&amount=X&country=Niger&redirect=<url>
- Webhook : header X-RobotPay-Signature = HMAC-SHA256(secret, JSON.stringify(body))
  Événement : payment.confirmed
"""
import hashlib
import hmac
import json

from flask import current_app
from urllib.parse import urlencode

from app.payments.providers.base import BaseProvider, ProviderError


class RobotPayProvider(BaseProvider):
    name = "robotpay"

    def normalize_status(self, raw):
        if raw == "payment.confirmed":
            return "successful"
        if raw in ("payment.failed", "payment.expired"):
            return "failed"
        return "processing"

    def checkout_url(self, amount, country, reference):
        """Construit l'URL de la page de paiement hébergée RobotPay."""
        slug = current_app.config.get("ROBOTPAY_MERCHANT_SLUG")
        if not slug:
            raise ProviderError("ROBOTPAY_MERCHANT_SLUG non configuré.")
        base = current_app.config.get("ROBOTPAY_CHECKOUT_URL") or "https://checkout1.westpay.cfd/pay"
        return_url = current_app.config.get("ROBOTPAY_RETURN_URL") or "https://namara.win/payments/robotpay/return"
        params = urlencode({
            "merchant": slug,
            "amount": int(amount),
            "country": country,
            "redirect": f"{return_url}/{reference}",
        })
        return f"{base}?{params}"

    def initiate_deposit(self, deposit, otp=None):
        """Génère l'URL de redirection (aucun appel API direct pour la collecte)."""
        url = self.checkout_url(deposit.amount, deposit.country, deposit.reference)
        deposit.status = "pending"
        return {"status": "pending", "external_ref": None, "checkout_url": url}

    def process_webhook(self, payload):
        """Normalise le callback RobotPay en structure standard.

        Le payload ne contient pas de référence NAMARA : on utilise txId
        comme identifiant (rapproché via external_ref stocké au retour).
        """
        return {
            "reference": payload.get("txId"),
            "external_ref": payload.get("txId"),
            "amount": payload.get("amount"),
            "currency": payload.get("currency"),
            "status": self.normalize_status(payload.get("event")),
        }

    def verify_signature(self, request):
        """Vérifie l'en-tête X-RobotPay-Signature (HMAC-SHA256).

        La signature couvre JSON.stringify(body) (JSON compact) — on accepte
        aussi le corps brut reçu tel quel.
        """
        supplied = request.headers.get("X-RobotPay-Signature", "")
        if not supplied:
            return False
        secret = current_app.config.get("ROBOTPAY_WEBHOOK_SECRET")
        if not secret:
            return False
        raw_body = request.get_data()
        candidates = [raw_body]
        try:
            parsed = json.loads(raw_body)
            candidates.append(
                json.dumps(parsed, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
            )
        except (ValueError, TypeError):
            pass
        for candidate in candidates:
            expected = hmac.new(secret.encode(), candidate, hashlib.sha256).hexdigest()
            if hmac.compare_digest(expected, supplied):
                return True
        return False
