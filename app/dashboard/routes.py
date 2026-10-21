"""Routes du tableau de bord utilisateur."""
import re
from functools import wraps

from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.constants import ALL_OPERATORS, WALLET_TYPES
from app.dashboard.forms import CardForm, ClaimForm, DepositForm, WithdrawalForm
from app.extensions import db
from app.models import (
    Card,
    Deposit,
    Investment,
    LedgerEntry,
    Notification,
    ReferralCommission,
    ReferralRelationship,
    Withdrawal,
)
from app.payments import service as payments
from app.payments.providers.base import ProviderError
from app.notifications.service import notify
from app.services import finance, referral as referral_service, settings
from app.utils import currency_for_country, operators_for_country, parse_amount

dashboard_bp = Blueprint("dashboard", __name__)


def verified_required(view):
    """Bloque les opérations financières tant que le téléphone n'est pas vérifié."""

    @wraps(view)
    def wrapped(*args, **kwargs):
        if not current_user.is_phone_verified:
            flash("Vérifiez votre numéro de téléphone avant toute opération financière.", "warning")
            return redirect(url_for("auth.verify"))
        return view(*args, **kwargs)

    return wrapped


def _transfer_to_withdrawable(user) -> int:
    """Transfère les revenus/commissions vers le solde retirable (atomique)."""
    total = 0
    for wtype in ("earnings", "referral"):
        balance = finance.get_balance(user.id, user.currency, wtype)
        if balance > 0:
            finance.transfer(
                user.id,
                user.currency,
                wtype,
                "withdrawable",
                balance,
                "claim",
                "dashboard",
                description=f"Transfert {wtype} vers solde retirable",
            )
            total += balance
    return total


@dashboard_bp.route("/")
@login_required
def index():
    user = current_user
    currency = user.currency
    balances = finance.get_balances(user.id, currency)
    balances.setdefault("deposit", 0)
    balances.setdefault("bonus", 0)
    balances.setdefault("earnings", 0)
    balances.setdefault("referral", 0)
    balances.setdefault("withdrawable", 0)

    # Solde total = fonds réels (dépôts + revenus + commissions + retirable).
    # Le bonus promotionnel est EXCLU : non retirable, il n'est pas un fonds réel.
    total_balance = (
        balances["withdrawable"]
        + balances["deposit"]
        + balances["earnings"]
        + balances["referral"]
    )
    first_name = user.full_name.split()[0] if user.full_name else user.full_name

    total_deposits = db.session.query(db.func.coalesce(db.func.sum(Deposit.amount), 0)).filter_by(
        user_id=user.id, status="successful"
    ).scalar()
    total_withdrawals = db.session.query(
        db.func.coalesce(db.func.sum(Withdrawal.amount), 0)
    ).filter_by(user_id=user.id, status="successful").scalar()
    referral_count = ReferralRelationship.query.filter_by(
        referrer_id=user.id, level=1
    ).count()
    recent = (
        LedgerEntry.query.filter_by(user_id=user.id)
        .order_by(LedgerEntry.created_at.desc())
        .limit(8)
        .all()
    )
    cards = (
        Card.query.filter_by(user_id=user.id, is_active=True)
        .order_by(Card.created_at.desc())
        .limit(2)
        .all()
    )
    return render_template(
        "dashboard/index.html",
        balances=balances,
        total_balance=total_balance,
        first_name=first_name,
        total_deposits=total_deposits,
        total_withdrawals=total_withdrawals,
        referral_count=referral_count,
        recent=recent,
        cards=cards,
    )



@dashboard_bp.route("/transactions")
@login_required
def transactions():
    entries = (
        LedgerEntry.query.filter_by(user_id=current_user.id)
        .order_by(LedgerEntry.created_at.desc())
        .limit(200)
        .all()
    )
    return render_template("dashboard/transactions.html", entries=entries)


@dashboard_bp.route("/deposits", methods=["GET", "POST"])
@login_required
@verified_required
def deposits():
    from app.payments.services import service_by_name, services_for_country

    services = services_for_country(current_user.country)
    is_redirect_flow = current_user.country == "Niger"  # RobotPay (page hébergée)
    form = DepositForm()
    form.operator.choices = [(s["name"], s["name"]) for s in services]
    if form.validate_on_submit():
        try:
            amount = form.clean_amount()
            if is_redirect_flow:
                # RobotPay : seul le montant est utilisé (numéro/opérateur saisis sur WestPay).
                operator = ""
                phone = ""
                service_id = None
            else:
                if not form.operator.data:
                    raise ValueError("Veuillez sélectionner un opérateur Mobile Money.")
                if not (form.phone_number.data or "").strip():
                    raise ValueError("Veuillez saisir votre numéro de téléphone.")
                service = service_by_name(current_user.country, form.operator.data)
                operator = service["operator"] if service else form.operator.data
                service_id = service["id"] if service else None
                phone = form.phone_number.data.strip()
            deposit = payments.initiate_deposit(
                current_user,
                amount,
                current_user.currency,
                current_user.country,
                operator,
                phone,
                service_id=service_id,
                otp=(form.otp.data or "").strip() or None,
            )
            db.session.commit()
            checkout_url = getattr(deposit, "checkout_url", None)
            if checkout_url:
                return redirect(checkout_url)
            flash("Demande de dépôt enregistrée. En attente de confirmation du prestataire.", "info")
            return redirect(url_for("dashboard.deposits"))
        except (ValueError, ProviderError) as exc:
            db.session.rollback()
            current_app.logger.warning("DÉPÔT ÉCHOUÉ | reason=%s", exc)
            flash(str(exc), "danger")

    history = (
        Deposit.query.filter_by(user_id=current_user.id)
        .order_by(Deposit.created_at.desc())
        .limit(50)
        .all()
    )
    return render_template(
        "dashboard/deposits.html",
        form=form,
        history=history,
        services=services,
        is_redirect_flow=is_redirect_flow,
    )


@dashboard_bp.route("/withdrawals", methods=["GET", "POST"])
@login_required
@verified_required
def withdrawals():
    form = WithdrawalForm()
    user_cards = (
        Card.query.filter_by(user_id=current_user.id, is_active=True)
        .order_by(Card.created_at.desc())
        .all()
    )
    form.card_id.choices = [("", "Sélectionner un compte")] + [
        (c.id, f"{c.operator} •••• {c.last4}") for c in user_cards
    ]
    if form.validate_on_submit():
        amount = form.clean_amount()
        min_amount = settings.get_int("MIN_WITHDRAWAL", current_app.config["MIN_WITHDRAWAL"])
        if amount < min_amount:
            form.amount.errors.append(f"Le retrait minimum est de {min_amount} FCFA.")
        else:
            card = db.session.get(Card, form.card_id.data) if form.card_id.data else None
            if card is None or card.user_id != current_user.id:
                form.card_id.errors.append("Sélectionnez un compte mobile valide.")
            else:
                fee_bps = current_app.config.get("WITHDRAWAL_FEE_BPS", 800)
                fee = amount * fee_bps // 10000
                net = amount - fee
                return render_template(
                    "dashboard/withdrawals_confirm.html",
                    card=card,
                    amount=amount,
                    fee=fee,
                    net=net,
                )

    history = (
        Withdrawal.query.filter_by(user_id=current_user.id)
        .order_by(Withdrawal.created_at.desc())
        .limit(50)
        .all()
    )
    created_withdrawal = None
    created_id = request.args.get("created", type=int)
    if created_id:
        w = db.session.get(Withdrawal, created_id)
        if w is not None and w.user_id == current_user.id:
            created_withdrawal = w
    return render_template(
        "dashboard/withdrawals.html",
        form=form,
        history=history,
        cards=user_cards,
        created_withdrawal=created_withdrawal,
    )


@dashboard_bp.route("/withdrawals/confirm", methods=["POST"])
@login_required
@verified_required
def withdrawals_confirm():
    card_id = request.form.get("card_id", type=int)
    amount = parse_amount(request.form.get("amount"))
    min_amount = settings.get_int("MIN_WITHDRAWAL", current_app.config["MIN_WITHDRAWAL"])

    card = db.session.get(Card, card_id) if card_id else None
    if card is None or card.user_id != current_user.id:
        flash("Compte mobile invalide.", "danger")
        return redirect(url_for("dashboard.withdrawals"))
    if amount < min_amount:
        flash(f"Le retrait minimum est de {min_amount} FCFA.", "danger")
        return redirect(url_for("dashboard.withdrawals"))

    try:
        withdrawal = payments.create_withdrawal(
            current_user,
            amount,
            current_user.currency,
            current_user.country,
            card.operator,
            card.phone_number,
        )
        notify(
            current_user.id,
            "withdrawal_requested",
            "Retrait demandé",
            f"Votre demande de retrait de {amount} {current_user.currency} a été enregistrée.",
        )
        db.session.commit()
        return redirect(url_for("dashboard.withdrawals", created=withdrawal.id))
    except (ValueError, finance.FinancialError) as exc:
        db.session.rollback()
        flash(str(exc), "danger")
    return redirect(url_for("dashboard.withdrawals"))


@dashboard_bp.route("/claim", methods=["POST"])
@login_required
@verified_required
def claim():
    form = ClaimForm()
    if form.validate_on_submit():
        total = _transfer_to_withdrawable(current_user)
        db.session.commit()
        if total > 0:
            flash("Fonds transférés vers le solde retirable.", "success")
        else:
            flash("Aucun fonds à transférer.", "info")
    return redirect(url_for("dashboard.index"))


@dashboard_bp.route("/notifications")
@login_required
def notifications():
    notifications_list = (
        Notification.query.filter_by(user_id=current_user.id)
        .order_by(Notification.created_at.desc())
        .limit(100)
        .all()
    )
    return render_template("dashboard/notifications.html", notifications=notifications_list)


@dashboard_bp.route("/notifications/read", methods=["POST"])
@login_required
def notifications_read():
    Notification.query.filter_by(user_id=current_user.id, is_read=False).update(
        {"is_read": True}, synchronize_session=False
    )
    db.session.commit()
    return redirect(url_for("dashboard.notifications"))


@dashboard_bp.route("/wallet")
@login_required
def wallet():
    user = current_user
    balances = finance.get_balances(user.id, user.currency)
    for key in ("deposit", "bonus", "earnings", "referral", "withdrawable"):
        balances.setdefault(key, 0)
    return render_template("dashboard/wallet.html", balances=balances)


@dashboard_bp.route("/cards", methods=["GET", "POST"])
@login_required
def cards():
    form = CardForm()
    form.operator.choices = [(o, o) for o in ALL_OPERATORS]
    if form.validate_on_submit():
        phone = re.sub(r"\D", "", form.phone_number.data or "")
        if len(phone) < 8 or len(phone) > 15:
            form.phone_number.errors.append("Numéro de téléphone invalide.")
        else:
            card = Card(
                user_id=current_user.id,
                operator=form.operator.data,
                phone_number=phone,
                name=(form.name.data or "").strip() or None,
            )
            db.session.add(card)
            db.session.commit()
            flash("Compte Mobile Money enregistré avec succès.", "success")
            return redirect(url_for("dashboard.cards"))

    cards_list = (
        Card.query.filter_by(user_id=current_user.id)
        .order_by(Card.created_at.desc())
        .all()
    )
    return render_template("dashboard/cards.html", form=form, cards=cards_list)


@dashboard_bp.route("/profile")
@login_required
def profile():
    return render_template("dashboard/profile.html")
