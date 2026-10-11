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
    status_filter = request.args.get("status", "").strip().lower()
    search_query = request.args.get("q", "").strip()

    # Base query: own investments only.
    query = Investment.query.filter_by(user_id=current_user.id)

    # Apply status filter.
    if status_filter in ("active", "completed", "cancelled", "interrupted"):
        query = query.filter_by(status=status_filter)

    # Apply search by product name.
    if search_query:
        from app.models import InvestmentProduct
        matching_product_ids = (
            db.session.query(InvestmentProduct.id)
            .filter(InvestmentProduct.name.ilike(f"%{search_query}%"))
        )
        query = query.filter(Investment.product_id.in_(matching_product_ids))

    investments = query.order_by(Investment.created_at.desc()).all()

    # Statistics (all investments, unfiltered).
    all_user_investments = Investment.query.filter_by(user_id=current_user.id).all()
    total_count = len(all_user_investments)
    total_capital = sum(inv.capital for inv in all_user_investments)
    active_count = sum(1 for inv in all_user_investments if inv.status == "active")
    completed_count = sum(1 for inv in all_user_investments if inv.status == "completed")

    created_investment = None
    created_sim = None
    created_id = request.args.get("created", type=int)
    if created_id:
        inv = db.session.get(Investment, created_id)
        if inv is not None and inv.user_id == current_user.id:
            created_investment = inv
            created_sim = investment_service.simulation_for(inv.product)

    # Progression for each investment.
    now = utcnow()
    positions = []
    for inv in investments:
        total_secs = (inv.end_date - inv.start_date).total_seconds()
        days_total = max(1, (inv.end_date - inv.start_date).days)

        if inv.status == "completed":
            pct = 100
            reference_point = inv.end_date
        elif inv.status in ("cancelled", "interrupted"):
            # Freeze at the moment the status was last updated.
            reference_point = inv.updated_at or now
            if total_secs > 0:
                elapsed = max(0, (reference_point - inv.start_date).total_seconds())
                pct = max(0, min(100, int(elapsed / total_secs * 100)))
            else:
                pct = 0
        elif total_secs > 0:
            reference_point = now
            elapsed = max(0, (now - inv.start_date).total_seconds())
            pct = max(0, min(100, int(elapsed / total_secs * 100)))
        else:
            pct = 0
            reference_point = now

        days_elapsed = min(days_total, max(0, (reference_point - inv.start_date).days))
        days_remaining = max(0, days_total - days_elapsed)

        income_earned = (
            db.session.query(
                db.func.coalesce(db.func.sum(InvestmentAccrual.paid_amount), 0)
            )
            .filter_by(investment_id=inv.id)
            .scalar()
        ) or 0

        positions.append({
            "inv": inv,
            "pct": pct,
            "days_elapsed": days_elapsed,
            "days_total": days_total,
            "days_remaining": days_remaining,
            "income_earned": income_earned,
        })

    return render_template(
        "dashboard/investments.html",
        positions=positions,
        total_count=total_count,
        total_capital=total_capital,
        active_count=active_count,
        completed_count=completed_count,
        created_investment=created_investment,
        created_sim=created_sim,
        status_filter=status_filter,
        search_query=search_query,
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

