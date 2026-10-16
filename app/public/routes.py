"""Pages publiques de NAMARA."""
from flask import Blueprint, jsonify, redirect, render_template, url_for
from flask_login import current_user, login_required

from app.extensions import db
from app.services.investment import (
    catalog_products,
    simulation_daily_rate,
    simulation_enabled,
    simulation_for,
    subscriptions_enabled,
)

public_bp = Blueprint("public", __name__)


@public_bp.route("/health")
def health():
    """Endpoint de santé (utilisé par Railway pour le healthcheck)."""
    try:
        db.session.execute(db.text("SELECT 1"))
        return jsonify({"status": "ok"}), 200
    except Exception:
        db.session.rollback()
        return jsonify({"status": "error"}), 500


@public_bp.route("/")
def index():
    """Racine du site : redirige vers le tableau de bord ou la connexion."""
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.index"))
    return redirect(url_for("auth.login"))


@public_bp.route("/about")
def about():
    """Page « À propos » présentant NAMARA."""
    return render_template("public/about.html")


@public_bp.route("/how-it-works")
def how_it_works():
    return render_template("public/how_it_works.html")


@public_bp.route("/products")
@login_required
def products():
    show_sim = simulation_enabled()
    rate_percent = simulation_daily_rate() * 100
    entries = []
    for p in catalog_products():
        entries.append({"product": p, "sim": simulation_for(p) if show_sim else None})

    approved_entries = [e for e in entries if e["product"].status == "approved"]
    approved_count = len(approved_entries)
    starting_price = min((e["product"].min_amount for e in approved_entries), default=None)
    standard_duration = entries[0]["product"].duration_days if entries else 90
    catalog_currency = entries[0]["product"].currency if entries else "XOF"

    return render_template(
        "public/products.html",
        entries=entries,
        show_sim=show_sim,
        rate_percent=rate_percent,
        subs_enabled=subscriptions_enabled(),
        approved_count=approved_count,
        starting_price=starting_price,
        standard_duration=standard_duration,
        catalog_currency=catalog_currency,
    )


@public_bp.route("/terms")
def terms():
    return render_template("public/terms.html")


@public_bp.route("/privacy")
def privacy():
    return render_template("public/privacy.html")


@public_bp.route("/risk-policy")
def risk_policy():
    return render_template("public/risk_policy.html")


@public_bp.route("/withdrawal-policy")
def withdrawal_policy():
    return render_template("public/withdrawal_policy.html")


@public_bp.route("/bonus-terms")
def bonus_terms():
    return render_template("public/bonus_terms.html")


@public_bp.route("/referral-terms")
@login_required
def referral_terms():
    return render_template("public/referral_terms.html")


@public_bp.route("/faq")
def faq():
    return render_template("public/faq.html")


@public_bp.route("/contact")
def contact():
    return render_template("public/contact.html")
