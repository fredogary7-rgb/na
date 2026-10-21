"""Routes de paiement (webhooks)."""
import requests

from flask import Blueprint, current_app, jsonify, redirect, request, url_for

from app.extensions import csrf, db
from app.models import Deposit
from app.payments import service
from app.payments.providers.base import ProviderError

payments_bp = Blueprint("payments", __name__)


def _forward_webhook(req):
    """Transmet le webhook reçu à un second site (ex. transafrik.org).

    Le corps brut et l'en-tête x-private-key sont renvoyés tels quels, afin
    que le second site puisse vérifier la signature SoleasPay lui-même.
    Retourne un libellé de statut pour les logs.
    """
    target = current_app.config.get("TRANSFRIK_WEBHOOK_URL")
    if not target:
        current_app.logger.info("WEBHOOK FORWARD skipped : TRANSFRIK_WEBHOOK_URL non défini")
        return "skipped"
    try:
        resp = requests.post(
            target,
            data=req.get_data(),
            headers={
                "Content-Type": "application/json",
                "x-private-key": req.headers.get("x-private-key", ""),
            },
            timeout=10,
        )
        current_app.logger.info(
            "WEBHOOK FORWARDED | target=%s | http=%s", target, resp.status_code
        )
        return f"ok({resp.status_code})"
    except requests.RequestException:
        current_app.logger.exception("WEBHOOK FORWARD FAILED | target=%s", target)
        return "failed"


@payments_bp.route("/robotpay/return/<deposit_ref>")
def robotpay_return(deposit_ref):
    """URL de retour après paiement RobotPay (page hébergée).

    Stocke le txId WestPay (paramètre `ref`) comme external_ref du dépôt afin
    de pouvoir le rapprocher au webhook payment.confirmed.
    """
    tx_ref = request.args.get("ref", "")
    if deposit_ref and tx_ref:
        deposit = Deposit.query.filter_by(reference=deposit_ref).first()
        if deposit and not deposit.external_ref:
            deposit.external_ref = tx_ref
            db.session.commit()
    return redirect(url_for("dashboard.deposits"))


@payments_bp.route("/webhook/<provider_name>", methods=["POST"])
@csrf.exempt
def webhook(provider_name):
    provider = service.get_provider(name=provider_name)
    if provider.name != provider_name:
        current_app.logger.warning("WEBHOOK PROVIDER INCONNU : %s", provider_name)
        return jsonify({"error": "provider_not_found"}), 404

    raw = request.get_data()
    current_app.logger.info(
        "WEBHOOK RECEIVED | provider=%s | x-private-key=%s | body=%s",
        provider_name,
        request.headers.get("x-private-key", ""),
        raw.decode("utf-8", errors="replace")[:2000],
    )

    try:
        result = service.process_deposit_webhook(provider, request)
        db.session.commit()
        # Le transfert vers un second site ne concerne que l'ancien provider SoleasPay.
        forward = _forward_webhook(request) if provider.name == "soleaspay" else "skipped"
        current_app.logger.info(
            "WEBHOOK PROCESSED | provider=%s | result=%s | forward=%s",
            provider_name,
            result,
            forward,
        )
        return jsonify({"status": "ok", "result": result}), 200
    except ProviderError as exc:
        db.session.rollback()
        current_app.logger.warning("WEBHOOK REJECTED | provider=%s | reason=%s", provider_name, exc)
        return jsonify({"error": str(exc)}), 400
    except Exception:
        db.session.rollback()
        current_app.logger.exception("WEBHOOK ERROR | provider=%s", provider_name)
        raise
