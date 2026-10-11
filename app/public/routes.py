"""Pages publiques de NAMARA."""
from flask import Blueprint, jsonify, render_template

from app.extensions import db
from app.services.investment import available_products

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
    return render_template("index.html")


@public_bp.route("/how-it-works")
def how_it_works():
    return render_template("public/how_it_works.html")


@public_bp.route("/products")
def products():
    return render_template("public/products.html", products=available_products())


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
def referral_terms():
    return render_template("public/referral_terms.html")


@public_bp.route("/faq")
def faq():
    return render_template("public/faq.html")


@public_bp.route("/contact")
def contact():
    return render_template("public/contact.html")
