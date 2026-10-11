"""Module d'investissement (produits approuvés uniquement)."""
from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.extensions import db
from app.models import Investment, InvestmentProduct
from app.services import investment as investment_service


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

    return render_template(
        "dashboard/investments.html",
        products=products,
        investments=investments,
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

    return render_template("dashboard/investments_confirm.html", product=product, sim=sim)

