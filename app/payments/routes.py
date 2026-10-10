"""Routes de paiement (webhooks)."""
from flask import Blueprint, jsonify, request

from app.extensions import csrf, db
from app.payments import service
from app.payments.providers.base import ProviderError

payments_bp = Blueprint("payments", __name__)


@payments_bp.route("/webhook/<provider_name>", methods=["POST"])
@csrf.exempt
def webhook(provider_name):
    provider = service.get_provider()
    if provider.name != provider_name:
        return jsonify({"error": "provider_not_found"}), 404
    try:
        result = service.process_deposit_webhook(provider, request)
        db.session.commit()
        return jsonify({"status": "ok", "result": result}), 200
    except ProviderError as exc:
        db.session.rollback()
        return jsonify({"error": str(exc)}), 400
    except Exception:
        db.session.rollback()
        raise
