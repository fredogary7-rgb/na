"""Module d'investissement (produits approuvés uniquement)."""
from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.extensions import db
from app.models import Investment, InvestmentAccrual, InvestmentProduct
from app.models.base import utcnow
from app.services import finance, investment as investment_service


investments_bp = Blueprint("investments", __name__)


@investments_bp.route("/")
@login_required
def index():
    products = investment_service.available_products(currency=current_user.currency)
    investments = (
        Investment.query.filter_by(user_id=current_user.id)
        .order_by(Investment.created_at.desc())
        .all()
    )

    created_investment = None
    created_sim = None
    created_id = request.args.get("created", type=int)
    if created_id:
        inv = db.session.get(Investment, created_id)
        if inv is not None and inv.user_id == current_user.id:
            created_investment = inv
            created_sim = investment_service.simulation_for(inv.product)

    # Progression de chaque position + statistiques d'ensemble.
    now = utcnow()
    positions = []
    total_invested = 0
    total_income = 0
    for inv in investments:
        total_secs = (inv.end_date - inv.start_date).total_seconds()
        days_total = max(1, (inv.end_date - inv.start_date).days)
        days_elapsed = min(days_total, max(0, (now - inv.start_date).days))
        days_remaining = max(0, days_total - days_elapsed)
        if inv.status == "completed":
            pct = 100
        elif inv.status in ("cancelled", "interrupted"):
            pct = 100
        elif total_secs > 0:
            pct = max(0, min(100, int((now - inv.start_date).total_seconds() / total_secs * 100)))
        else:
            pct = 0
        income_earned = (
            db.session.query(
                db.func.coalesce(db.func.sum(InvestmentAccrual.paid_amount), 0)
            )
            .filter_by(investment_id=inv.id)
            .scalar()
        ) or 0
        total_invested += inv.capital
        total_income += income_earned
        positions.append({
            "inv": inv,
            "pct": pct,
            "days_elapsed": days_elapsed,
            "days_total": days_total,
            "days_remaining": days_remaining,
            "income_earned": income_earned,
        })

    active_count = sum(1 for inv in investments if inv.status == "active")

    return render_template(
        "dashboard/investments.html",
        products=products,
        positions=positions,
        total_invested=total_invested,
        total_income=total_income,
        active_count=active_count,
        created_investment=created_investment,
        created_sim=created_sim,
        rate_percent=investment_service.simulation_daily_rate() * 100,
    )


@investments_bp.route("/confirm/<int:product_id>", methods=["GET", "POST"])
@login_required
def confirm(product_id):
    product = db.session.get(InvestmentProduct, product_id)
    if (
        product is None
        or product.status != "approved"
        or product.currency != current_user.currency
    ):
        abort(404)

    sim = investment_service.simulation_for(product)

    if request.method == "POST":
        try:
            inv = investment_service.invest(current_user, product, product.min_amount)
            db.session.commit()
            return redirect(url_for("investments.index", created=inv.id))
        except investment_service.InvestmentError as exc:
            db.session.rollback()
            flash(str(exc), "danger")
            return redirect(url_for("investments.index"))

    return render_template(
        "dashboard/investments_confirm.html",
        product=product,
        sim=sim,
        deposit_balance=finance.get_balance(current_user.id, current_user.currency, "deposit"),
    )

