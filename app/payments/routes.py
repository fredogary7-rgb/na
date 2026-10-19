"""Routes de paiement (webhooks)."""
import requests

from flask import Blueprint, current_app, jsonify, request

from app.extensions import csrf, db
from app.payments import service
from app.payments.providers.base import ProviderError

payments_bp = Blueprint("payments", __name__)


def _forward_webhook(req):
    """Transmet le webhook reçu à un second site (ex. transafrik.org).

    Le corps brut et l'en-tête x-private-key sont renvoyés tels quels, afin
    que le second site puisse vérifier la signature SoleasPay lui-même.
    """
    target = current_app.config.get("TRANSFRIK_WEBHOOK_URL")
    if not target:
        return
    try:
        requests.post(
            target,
            data=req.get_data(),
            headers={
                "Content-Type": "application/json",
                "x-private-key": req.headers.get("x-private-key", ""),
            },
            timeout=10,
        )
    except requests.RequestException:
        current_app.logger.exception("Échec de la transmission du webhook vers le second site.")


@payments_bp.route("/webhook/<provider_name>", methods=["POST"])
@csrf.exempt
def webhook(provider_name):
    provider = service.get_provider()
    if provider.name != provider_name:
        return jsonify({"error": "provider_not_found"}), 404
    try:
        result = service.process_deposit_webhook(provider, request)
        db.session.commit()
        _forward_webhook(request)
        return jsonify({"status": "ok", "result": result}), 200
    except ProviderError as exc:
        db.session.rollback()
        return jsonify({"error": str(exc)}), 400
    except Exception:
        db.session.rollback()
        raise
