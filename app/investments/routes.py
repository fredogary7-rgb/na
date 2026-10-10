"""Module d'investissement (produits approuvés uniquement)."""
from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from flask_wtf import FlaskForm
from wtforms import IntegerField, SelectField
from wtforms.validators import DataRequired

from app.extensions import db
from app.models import Investment
from app.services import investment as investment_service


class InvestForm(FlaskForm):
    product_id = SelectField("Produit", coerce=int, validators=[DataRequired()])
    amount = IntegerField("Montant (FCFA)", validators=[DataRequired()])


investments_bp = Blueprint("investments", __name__)


@investments_bp.route("/", methods=["GET", "POST"])
@login_required
def index():
    products = investment_service.available_products(currency=current_user.currency)
    form = InvestForm()
    form.product_id.choices = [(p.id, p.name) for p in products]

    if form.validate_on_submit() and products:
        try:
            product = next(p for p in products if p.id == form.product_id.data)
            investment_service.invest(current_user, product, form.amount.data)
            db.session.commit()
            flash("Investissement enregistré.", "success")
            return redirect(url_for("investments.index"))
        except (StopIteration, investment_service.InvestmentError, ValueError) as exc:
            db.session.rollback()
            flash(str(exc), "danger")

    investments = (
        Investment.query.filter_by(user_id=current_user.id)
        .order_by(Investment.created_at.desc())
        .all()
    )
    return render_template(
        "dashboard/investments.html",
        form=form,
        products=products,
        investments=investments,
    )
