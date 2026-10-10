"""Espace administrateur : accès restreint au rôle admin, journalisé."""
from functools import wraps

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from flask_wtf import FlaskForm
from wtforms import BooleanField, IntegerField, SelectField, StringField, TextAreaField
from wtforms.validators import DataRequired, Optional

from app.extensions import db
from app.models import (
    AuditLog,
    Deposit,
    InvestmentProduct,
    PaymentEvent,
    SupportConversation,
    SupportMessage,
    User,
    Withdrawal,
)
from app.payments import service as payments
from app.models.base import utcnow
from app.services import support as support_service
from app.services.telegram import TelegramError, send_message

admin_bp = Blueprint("admin", __name__)


def admin_required(view):
    """Vérification côté serveur sur chaque route : le rôle admin est requis."""

    @wraps(view)
    def wrapped(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for("auth.login"))
        if not current_user.is_admin:
            abort(403)
        return view(*args, **kwargs)

    return wrapped


def _audit(action, target_type=None, target_id=None, details=None):
    db.session.add(
        AuditLog(
            admin_id=current_user.id,
            action=action,
            target_type=target_type,
            target_id=str(target_id) if target_id is not None else None,
            details=details,
            ip_address=request.remote_addr,
        )
    )


@admin_bp.route("/")
@login_required
@admin_required
def index():
    stats = {
        "users": User.query.count(),
        "deposits": Deposit.query.count(),
        "withdrawals": Withdrawal.query.count(),
        "pending_withdrawals": Withdrawal.query.filter_by(status="pending").count(),
        "pending_deposits": Deposit.query.filter_by(status="pending").count(),
        "products": InvestmentProduct.query.count(),
    }
    return render_template("admin/index.html", stats=stats)


@admin_bp.route("/users")
@login_required
@admin_required
def users():
    q = request.args.get("q", "").strip()
    country = request.args.get("country", "").strip()
    query = User.query
    if q:
        query = query.filter(User.phone_number.ilike(f"%{q}%"))
    if country:
        query = query.filter_by(country=country)
    users_list = query.order_by(User.created_at.desc()).limit(200).all()
    return render_template("admin/users.html", users=users_list, q=q, country=country)


@admin_bp.route("/deposits")
@login_required
@admin_required
def deposits():
    deposits_list = Deposit.query.order_by(Deposit.created_at.desc()).limit(200).all()
    return render_template("admin/deposits.html", deposits=deposits_list)


@admin_bp.route("/withdrawals")
@login_required
@admin_required
def withdrawals():
    withdrawals_list = Withdrawal.query.order_by(Withdrawal.created_at.desc()).limit(200).all()
    return render_template("admin/withdrawals.html", withdrawals=withdrawals_list)


@admin_bp.route("/withdrawals/<int:wid>/<action>", methods=["POST"])
@login_required
@admin_required
def withdrawal_action(wid, action):
    withdrawal = db.session.get(Withdrawal, wid)
    if withdrawal is None:
        abort(404)
    if action == "approve":
        withdrawal.status = "approved"
        withdrawal.processed_at = utcnow()
        _audit("withdrawal_approve", "withdrawal", wid)
    elif action == "reject":
        payments.refund_withdrawal(withdrawal, "rejected")
        _audit("withdrawal_reject", "withdrawal", wid)
    elif action == "complete":
        payments.complete_withdrawal(withdrawal)
        _audit("withdrawal_complete", "withdrawal", wid)
    else:
        abort(404)
    db.session.commit()
    flash("Statut du retrait mis à jour.", "success")
    return redirect(url_for("admin.withdrawals"))


@admin_bp.route("/webhooks")
@login_required
@admin_required
def webhooks():
    events = PaymentEvent.query.order_by(PaymentEvent.created_at.desc()).limit(200).all()
    return render_template("admin/webhooks.html", events=events)


@admin_bp.route("/audit")
@login_required
@admin_required
def audit():
    logs = AuditLog.query.order_by(AuditLog.created_at.desc()).limit(200).all()
    return render_template("admin/audit.html", logs=logs)


class ProductForm(FlaskForm):
    name = StringField("Nom", validators=[DataRequired()])
    description = TextAreaField("Description")
    duration_days = IntegerField("Durée (jours)", default=120)
    min_amount = IntegerField("Montant minimum", default=3000)
    max_amount = IntegerField("Montant maximum", default=1000000)
    currency = SelectField("Devise", choices=[("XOF", "XOF"), ("XAF", "XAF")])
    annual_rate_bps = IntegerField("Taux annuel (points de base)", default=0)
    terms = TextAreaField("Conditions")


@admin_bp.route("/products", methods=["GET", "POST"])
@login_required
@admin_required
def products():
    form = ProductForm()
    if form.validate_on_submit():
        product = InvestmentProduct(
            name=form.name.data,
            description=form.description.data,
            duration_days=form.duration_days.data or 120,
            min_amount=form.min_amount.data or 0,
            max_amount=form.max_amount.data or 0,
            currency=form.currency.data,
            annual_rate_bps=form.annual_rate_bps.data or 0,
            terms=form.terms.data,
            status="draft",
        )
        db.session.add(product)
        db.session.flush()
        _audit("product_create", "product", product.id)
        db.session.commit()
        flash("Produit créé (statut brouillon).", "success")
        return redirect(url_for("admin.products"))

    products_list = InvestmentProduct.query.order_by(InvestmentProduct.id.desc()).all()
    return render_template("admin/products.html", form=form, products=products_list)


@admin_bp.route("/products/<int:pid>/<action>", methods=["POST"])
@login_required
@admin_required
def product_action(pid, action):
    product = db.session.get(InvestmentProduct, pid)
    if product is None:
        abort(404)
    if action == "approve":
        product.status = "approved"
        _audit("product_approve", "product", pid)
    elif action == "pause":
        product.status = "paused"
        _audit("product_pause", "product", pid)
    elif action == "close":
        product.status = "closed"
        _audit("product_close", "product", pid)
    else:
        abort(404)
    db.session.commit()
    flash("Statut du produit mis à jour.", "success")
    return redirect(url_for("admin.products"))


class SettingsForm(FlaskForm):
    bonus_enabled = BooleanField("Bonus de bienvenue activé")
    bonus_amount = IntegerField("Montant du bonus (FCFA)", validators=[Optional()])
    min_deposit = IntegerField("Dépôt minimum (FCFA)", validators=[Optional()])
    min_withdrawal = IntegerField("Retrait minimum (FCFA)", validators=[Optional()])
    referral_enabled = BooleanField("Parrainage activé")


@admin_bp.route("/settings", methods=["GET", "POST"])
@login_required
@admin_required
def settings():
    from app.services import settings as settings_service

    form = SettingsForm()
    if form.validate_on_submit():
        settings_service.set_setting("BONUS_ENABLED", "true" if form.bonus_enabled.data else "false", "Bonus de bienvenue")
        settings_service.set_setting("BONUS_INSCRIPTION", form.bonus_amount.data or 0, "Montant du bonus")
        settings_service.set_setting("MIN_DEPOSIT", form.min_deposit.data or 3000, "Dépôt minimum")
        settings_service.set_setting("MIN_WITHDRAWAL", form.min_withdrawal.data or 1500, "Retrait minimum")
        settings_service.set_setting("REFERRAL_ENABLED", "true" if form.referral_enabled.data else "false", "Parrainage")
        _audit("settings_update", "settings", None)
        db.session.commit()
        flash("Paramètres enregistrés.", "success")
        return redirect(url_for("admin.settings"))

    form.bonus_enabled.data = settings_service.get_bool("BONUS_ENABLED", False)
    form.bonus_amount.data = settings_service.get_int("BONUS_INSCRIPTION", 0)
    form.min_deposit.data = settings_service.get_int("MIN_DEPOSIT", 3000)
    form.min_withdrawal.data = settings_service.get_int("MIN_WITHDRAWAL", 1500)
    form.referral_enabled.data = settings_service.get_bool("REFERRAL_ENABLED", False)
    return render_template("admin/settings.html", form=form)


# ---------------------------------------------------------------------------
# Service client (support)
# ---------------------------------------------------------------------------
@admin_bp.route("/support")
@login_required
@admin_required
def support():
    status = request.args.get("status", "").strip()
    channel = request.args.get("channel", "").strip()
    category = request.args.get("category", "").strip()
    q = request.args.get("q", "").strip()

    query = SupportConversation.query
    if status:
        query = query.filter_by(status=status)
    if channel:
        query = query.filter_by(channel=channel)
    if category:
        query = query.filter_by(category=category)
    if q:
        query = query.filter(SupportConversation.public_reference.ilike(f"%{q}%"))

    conversations = (
        query.order_by(SupportConversation.last_message_at.desc())
        .limit(200)
        .all()
    )
    stats = {
        "open": SupportConversation.query.filter_by(status="open").count(),
        "pending": SupportConversation.query.filter_by(status="pending").count(),
        "unread": SupportMessage.query.filter_by(is_read=False).count(),
        "closed": SupportConversation.query.filter_by(status="closed").count(),
    }
    return render_template(
        "admin/support.html",
        conversations=conversations,
        stats=stats,
        status=status,
        channel=channel,
        category=category,
        q=q,
    )


@admin_bp.route("/support/<int:conv_id>", methods=["GET", "POST"])
@login_required
@admin_required
def support_detail(conv_id):
    conv = db.session.get(SupportConversation, conv_id)
    if conv is None:
        abort(404)

    if request.method == "POST":
        action = request.form.get("action")
        if action == "reply":
            text = (request.form.get("message") or "").strip()
            if text:
                msg = support_service.add_message(conv, "admin", text)
                if conv.channel == "telegram" and conv.telegram_chat_id:
                    try:
                        send_message(conv.telegram_chat_id, text)
                        msg.delivery_status = "sent"
                    except TelegramError:
                        msg.delivery_status = "failed"
                conv.status = "answered"
                _audit("support_reply", "conversation", conv.id)
        elif action == "note":
            text = (request.form.get("note") or "").strip()
            if text:
                support_service.add_message(conv, "admin", text, internal_note=True)
                _audit("support_note", "conversation", conv.id)
        elif action == "assign":
            admin_id = request.form.get("admin_id", type=int) or None
            conv.assigned_admin_id = admin_id
            _audit("support_assign", "conversation", conv.id)
        elif action == "status":
            new_status = request.form.get("status")
            if new_status in ("open", "pending", "answered", "closed"):
                conv.status = new_status
                _audit("support_status", "conversation", conv.id)
        db.session.commit()
        return redirect(url_for("admin.support_detail", conv_id=conv.id))

    support_service.mark_read(conv)
    db.session.commit()
    admins = User.query.filter_by(role="admin").all()
    return render_template("admin/support_detail.html", conv=conv, admins=admins)

