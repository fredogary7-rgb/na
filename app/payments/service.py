"""Service de paiement : dépôts, retraits et traitement des webhooks."""
import json

from flask import current_app

from app.extensions import db
from app.models import Deposit, PaymentEvent, User, Withdrawal
from app.models.base import utcnow
from app.payments.providers.base import ProviderError
from app.services import finance, referral, settings
from app.utils import new_reference


def get_provider():
    mode = current_app.config.get("PAYMENT_MODE", "mock")
    if mode == "soleaspay":
        from app.payments.providers.soleaspay import SoleasPayProvider

        return SoleasPayProvider()
    from app.payments.providers.mock import MockProvider

    return MockProvider()


def initiate_deposit(user, amount, currency, country, operator, phone) -> Deposit:
    if amount < settings.get_int("MIN_DEPOSIT", current_app.config["MIN_DEPOSIT"]):
        raise ValueError(f"Le dépôt minimum est de {settings.get_int('MIN_DEPOSIT', 3000)} FCFA.")
    if currency != user.currency:
        raise ValueError("Devise incompatible avec le compte.")

    provider = get_provider()
    deposit = Deposit(
        user_id=user.id,
        amount=amount,
        currency=currency,
        country=country,
        operator=operator,
        phone_number=phone,
        provider=provider.name,
        reference=new_reference("DEP"),
        status="pending",
    )
    db.session.add(deposit)
    db.session.flush()
    provider.initiate_deposit(deposit)
    return deposit



def process_deposit_webhook(provider, req):
    """Traite un événement webhook de dépôt (atomique et idempotent).

    Vérifie l'authenticité, la référence, le montant, la devise et le statut,
    et empêche le traitement multiple d'un même événement.
    """
    if not provider.verify_signature(req):
        raise ProviderError("Signature de webhook invalide.")

    raw = req.get_json(silent=True) or {}
    event = provider.process_webhook(raw)
    reference = event["reference"]

    deposit = Deposit.query.filter_by(reference=reference).first()
    if deposit is None:
        raise ProviderError("Référence de dépôt inconnue.")

    if event.get("amount") is not None and int(event["amount"]) != deposit.amount:
        raise ProviderError("Montant incohérent avec la référence.")
    if event.get("currency") and event["currency"] != deposit.currency:
        raise ProviderError("Devise incohérente avec la référence.")

    pe = PaymentEvent(
        provider=provider.name,
        event_type="deposit",
        external_reference=event.get("external_ref") or reference,
        payload=json.dumps(raw),
        status="received",
    )
    db.session.add(pe)
    db.session.flush()

    status = event["status"]
    if status == "successful":
        if deposit.status == "successful":
            pe.status = "duplicate"
            db.session.flush()
            return "duplicate"
        _confirm_deposit(deposit, event.get("external_ref"))
        pe.status = "processed"
        pe.processed_at = utcnow()
    elif status in ("failed", "rejected", "cancelled"):
        deposit.status = status
        pe.status = "processed"
        pe.processed_at = utcnow()
    else:
        deposit.status = "processing" if status == "processing" else deposit.status

    db.session.flush()
    return deposit.status


def _confirm_deposit(deposit: Deposit, external_ref) -> None:
    """Crédite le dépôt uniquement après confirmation authentifiée du prestataire."""
    user = db.session.get(User, deposit.user_id)
    finance.credit(
        deposit.user_id,
        deposit.currency,
        "deposit",
        deposit.amount,
        "deposit",
        "payments",
        reference=f"DEP-CREDIT-{deposit.reference}",
        description="Dépôt confirmé",
        external_ref=external_ref,
        operator=deposit.operator,
    )
    deposit.status = "successful"
    deposit.external_ref = external_ref
    deposit.confirmed_at = utcnow()

    from app.notifications.service import notify

    notify(deposit.user_id, "deposit_confirmed", "Dépôt confirmé",
           f"Votre dépôt de {deposit.amount} {deposit.currency} a été confirmé.")

    commissions = referral.compute_commissions(
        user, "deposit", deposit.reference, deposit.amount, deposit.currency
    )
    for commission in commissions:
        referral.confirm_commission(commission)


def create_withdrawal(user, amount, currency, country, operator, wallet_number) -> Withdrawal:
    min_amount = settings.get_int("MIN_WITHDRAWAL", current_app.config["MIN_WITHDRAWAL"])
    if amount < min_amount:
        raise ValueError(f"Le retrait minimum est de {min_amount} FCFA.")
    if currency != user.currency:
        raise ValueError("Devise incompatible avec le compte.")

    fee_bps = current_app.config.get("WITHDRAWAL_FEE_BPS", 800)
    fee = amount * fee_bps // 10000
    net_amount = amount - fee

    reference = new_reference("WDR")
    finance.debit(
        user.id,
        currency,
        "withdrawable",
        amount,
        "withdrawal",
        "withdrawals",
        reference=f"{reference}-RES",
        description="Réservation pour retrait",
        operator=operator,
    )
    withdrawal = Withdrawal(
        user_id=user.id,
        amount=amount,
        fee=fee,
        net_amount=net_amount,
        currency=currency,
        country=country,
        operator=operator,
        wallet_number=wallet_number,
        reference=reference,
        status="pending",
    )
    db.session.add(withdrawal)
    db.session.flush()
    return withdrawal


def refund_withdrawal(withdrawal: Withdrawal, new_status: str) -> None:
    """Rembourse les fonds réservés en cas de rejet/échec."""
    if withdrawal.status in ("rejected", "failed"):
        return
    finance.credit(
        withdrawal.user_id,
        withdrawal.currency,
        "withdrawable",
        withdrawal.amount,
        "withdrawal_refund",
        "withdrawals",
        reference=f"{withdrawal.reference}-REFUND",
        description=f"Remboursement retrait {withdrawal.reference}",
    )
    withdrawal.status = new_status
    withdrawal.processed_at = utcnow()
    db.session.flush()


def complete_withdrawal(withdrawal: Withdrawal, external_ref=None) -> None:
    """Marque un retrait comme réussi (fonds déjà réservés à la création)."""
    withdrawal.status = "successful"
    withdrawal.external_ref = external_ref
    withdrawal.processed_at = utcnow()
    db.session.flush()
