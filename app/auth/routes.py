"""Routes d'authentification : inscription, connexion, OTP, mot de passe oublié."""
import secrets
from datetime import timedelta

import phonenumbers
from flask import (
    Blueprint,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import current_user, login_required, login_user, logout_user
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from app.auth.forms import (
    ForgotPasswordForm,
    LoginForm,
    RegistrationForm,
    ResetPasswordForm,
)
from app.constants import COUNTRIES, WALLET_TYPES
from app.extensions import db, limiter
from app.models import LedgerEntry, User
from app.models.base import utcnow
from app.models.user import new_unique_referral_code
from app.services import finance, referral, settings
from app.utils import currency_for_country

auth_bp = Blueprint("auth", __name__)


def _reset_serializer():
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"], salt="namara-reset")


def _apply_welcome_bonus(user: User) -> None:
    """Bonus de bienvenue : crédité une seule fois, sur un portefeuille distinct,
    explicitement promotionnel et non retirable."""
    if not settings.get_bool("BONUS_ENABLED", False):
        return
    amount = settings.get_int("BONUS_INSCRIPTION", 0)
    if amount <= 0:
        return
    if LedgerEntry.query.filter_by(user_id=user.id, transaction_type="welcome_bonus").first():
        return
    finance.credit(
        user.id,
        user.currency,
        "bonus",
        amount,
        "welcome_bonus",
        "system",
        reference=f"BONUS-{user.id}",
        description="Bonus de bienvenue (promotionnel, non retirable)",
    )


@auth_bp.route("/register", methods=["GET", "POST"])
@limiter.limit("5 per hour")
def register():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.index"))

    form = RegistrationForm()
    if request.method == "GET" and not form.referral_code.data:
        form.referral_code.data = request.args.get("ref", "")
    if form.validate_on_submit():
        phone = form.normalized_phone
        if User.query.filter_by(phone_number=phone).first():
            form.phone_number.errors.append("Ce numéro de téléphone est déjà utilisé.")
            return render_template("auth/register.html", form=form)

        user = User(
            full_name=form.full_name.data.strip(),
            phone_number=phone,
            country=form.country.data,
            currency=currency_for_country(form.country.data),
            referral_code=new_unique_referral_code(),
        )
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.flush()

        finance.ensure_wallets(user.id, user.currency, WALLET_TYPES)

        if form.referral_code.data:
            try:
                referral.attach_referrals(user, form.referral_code.data)
            except referral.ReferralError as exc:
                db.session.rollback()
                form.referral_code.errors.append(str(exc))
                return render_template("auth/register.html", form=form)

        user.is_phone_verified = True
        db.session.commit()

        login_user(user)
        flash("Inscription réussie. Bienvenue sur NAMARA !", "success")
        return redirect(url_for("dashboard.index"))

    return render_template("auth/register.html", form=form)


def _is_safe_next_url(target):
    """N'autorise que les chemins relatifs commençant par '/' (pas d'URL absolue)."""
    if not target:
        return False
    return target.startswith("/") and not target.startswith("//")


@auth_bp.route("/login", methods=["GET", "POST"])
@limiter.limit("10 per minute")
def login():
    next_page = request.values.get("next")
    if not _is_safe_next_url(next_page):
        next_page = None

    if current_user.is_authenticated:
        return redirect(next_page or url_for("dashboard.index"))

    form = LoginForm()
    if form.validate_on_submit():
        raw_phone = (form.phone_number.data or "").strip()
        # Si le numéro est complet (commence par "+"), on l'utilise tel quel ;
        # sinon on combine l'indicatif du pays sélectionné avec le numéro local.
        if not raw_phone.startswith("+") and form.country.data:
            info = COUNTRIES.get(form.country.data)
            if info:
                raw_phone = info["phone_code"] + raw_phone
        phone = _normalize_login_phone(raw_phone)
        user = User.query.filter_by(phone_number=phone).first()
        # Message générique : ne révèle pas si le numéro existe.
        if user is None or not user.check_password(form.password.data):
            flash("Identifiants incorrects.", "danger")
            return render_template("auth/login.html", form=form, next_page=next_page)
        if user.status != "active":
            flash("Compte suspendu. Contactez l'assistance.", "danger")
            return render_template("auth/login.html", form=form, next_page=next_page)

        login_user(user)
        return redirect(next_page or url_for("dashboard.index"))

    return render_template("auth/login.html", form=form, next_page=next_page)


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Vous êtes déconnecté.", "info")
    return redirect(url_for("auth.login"))


def _normalize_login_phone(raw: str) -> str:
    raw = (raw or "").strip()
    if not raw.startswith("+"):
        raw = "+" + raw
    try:
        parsed = phonenumbers.parse(raw, None)
        if phonenumbers.is_valid_number(parsed):
            return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
    except phonenumbers.NumberParseException:
        pass
    return raw



@auth_bp.route("/verify")
@login_required
def verify():
    return redirect(url_for("dashboard.index"))


@auth_bp.route("/forgot-password", methods=["GET", "POST"])
@limiter.limit("5 per hour")
def forgot_password():
    form = ForgotPasswordForm()
    if form.validate_on_submit():
        phone = _normalize_login_phone(form.phone_number.data)
        user = User.query.filter_by(phone_number=phone).first()
        # Message générique même si le numéro n'existe pas.
        if user is not None:
            token = _reset_serializer().dumps(user.id)
            reset_url = url_for("auth.reset_password", token=token, _external=True)
            if current_app.config.get("FLASK_ENV") != "production":
                flash(
                    f"Mode développement : lien de réinitialisation — {reset_url}",
                    "info",
                )
        flash("Si ce numéro existe, un lien de réinitialisation a été généré.", "success")
        return redirect(url_for("auth.login"))
    return render_template("auth/forgot_password.html", form=form)


@auth_bp.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token):
    try:
        user_id = _reset_serializer().loads(token, max_age=1800)
    except (SignatureExpired, BadSignature):
        flash("Lien invalide ou expiré.", "danger")
        return redirect(url_for("auth.forgot_password"))

    user = db.session.get(User, int(user_id))
    if user is None:
        flash("Utilisateur introuvable.", "danger")
        return redirect(url_for("auth.forgot_password"))

    form = ResetPasswordForm()
    if form.validate_on_submit():
        user.set_password(form.password.data)
        db.session.commit()
        flash("Mot de passe mis à jour. Connectez-vous.", "success")
        return redirect(url_for("auth.login"))
    return render_template("auth/reset_password.html", form=form)
