"""Service d'investissement (moteur de calcul quotidien, idempotent)."""
from datetime import date, timedelta

from flask import current_app

from app.extensions import db
from app.models import Investment, InvestmentAccrual, InvestmentProduct
from app.models.base import utcnow


class InvestmentError(Exception):
    pass


def available_products(currency=None):
    query = InvestmentProduct.query.filter_by(status="approved")
    if currency:
        query = query.filter_by(currency=currency)
    return query.order_by(InvestmentProduct.id.asc()).all()


def catalog_products(currency=None):
    """Produits visibles dans le catalogue public (actifs + désactivés)."""
    query = InvestmentProduct.query.filter(
        InvestmentProduct.status.in_(["approved", "disabled"])
    )
    if currency:
        query = query.filter_by(currency=currency)
    return query.order_by(InvestmentProduct.id.asc()).all()


# ---------------------------------------------------------------------------
# Simulation hypothétique (NON validée — aucune promesse de rendement)
# ---------------------------------------------------------------------------
def subscriptions_enabled() -> bool:
    """Les souscriptions réelles sont autorisées uniquement après validation."""
    from app.services import settings

    return settings.get_bool("SUBSCRIPTIONS_ENABLED", current_app.config.get("SUBSCRIPTIONS_ENABLED", False))


def simulation_enabled() -> bool:
    """L'affichage des montants simulés peut être désactivé globalement."""
    from app.services import settings

    return settings.get_bool("SIMULATION_SHOW_AMOUNTS", current_app.config.get("SIMULATION_SHOW_AMOUNTS", True))


def simulation_daily_rate() -> float:
    """Taux quotidien hypothétique (fraction, ex. 0.08 = 8 %/jour)."""
    from app.services import settings

    return settings.get_float("SIMULATION_DAILY_RATE", current_app.config.get("SIMULATION_DAILY_RATE", 0.08))


def simulation_for(product: InvestmentProduct) -> dict:
    """Calcule les montants de simulation (sans capitalisation, non arrondis).

    quotidien = prix * taux
    revenu_90j = quotidien * durée
    total = prix + revenu_90j
    """
    rate = simulation_daily_rate()
    price = product.min_amount  # catalogue : prix unique (min == max)
    daily = price * rate
    revenue = daily * product.duration_days
    total = price + revenue
    return {
        "price": price,
        "daily": daily,
        "revenue": revenue,
        "total": total,
        "duration_days": product.duration_days,
    }


# Catalogue officiel NAMARA (prix en FCFA, durée 90 jours).
# Les trois derniers produits sont désactivés par défaut.
CATALOG = [
    ("NAMARA 1", 3000, "approved"),
    ("NAMARA 2", 5000, "approved"),
    ("NAMARA 3", 10000, "approved"),
    ("NAMARA 4", 25000, "approved"),
    ("NAMARA 5", 50000, "approved"),
    ("NAMARA 6", 100000, "approved"),
    ("NAMARA 7", 150000, "disabled"),
    ("NAMARA 8", 200000, "disabled"),
    ("NAMARA 9", 250000, "disabled"),
]


def seed_catalog_products(currency="XOF", duration_days=90) -> int:
    """Initialisation idempotente du catalogue (n'ajoute pas les doublons)."""
    created = 0
    for name, price, status in CATALOG:
        if InvestmentProduct.query.filter_by(name=name).first() is not None:
            continue
        db.session.add(
            InvestmentProduct(
                name=name,
                description=f"{name} — produit NAMARA (simulation indicative).",
                duration_days=duration_days,
                min_amount=price,
                max_amount=price,
                currency=currency,
                annual_rate_bps=0,
                status=status,
            )
        )
        created += 1
    db.session.flush()
    return created


def invest(user, product: InvestmentProduct, amount: int) -> Investment:
    """Crée un investissement en débitant le portefeuille 'deposit'."""
    from app.services import finance

    if not subscriptions_enabled():
        raise InvestmentError("Les souscriptions ne sont pas encore ouvertes (validation en attente).")
    if product.status != "approved":
        raise InvestmentError("Ce produit n'est pas actif à la souscription.")
    if amount < product.min_amount or amount > product.max_amount:
        raise InvestmentError("Montant hors des limites du produit.")
    if product.currency != user.currency:
        raise InvestmentError("Devise incompatible.")

    reference = f"INV-{utcnow().strftime('%Y%m%d%H%M%S')}"
    finance.debit(
        user.id, user.currency, "deposit", amount,
        "investment_capital", "investments",
        reference=f"{reference}-CAP",
        description=f"Capital investi : {product.name}",
    )
    start = utcnow()
    end = start + timedelta(days=product.duration_days)
    investment = Investment(
        user_id=user.id,
        product_id=product.id,
        capital=amount,
        currency=product.currency,
        start_date=start,
        end_date=end,
        status="active",
    )
    db.session.add(investment)
    db.session.flush()
    return investment


def daily_accrue(investment: Investment, as_of=None) -> None:
    """Régularisation quotidienne idempotente.

    N'invente aucun rendement : utilise uniquement le taux annuel approuvé du
    produit. Une relance ne crédite jamais deux fois la même journée.
    """
    product = investment.product
    if product.annual_rate_bps <= 0 or investment.status != "active":
        return

    day = (as_of or utcnow()).date()
    accrual_date = day
    existing = InvestmentAccrual.query.filter_by(
        investment_id=investment.id, accrual_date=accrual_date
    ).first()
    if existing is not None:
        return  # déjà traité : idempotent

    # Estimation quotidienne = capital * taux_annuel_bps / 10_000 / 365 (arrondi entier)
    daily_estimate = (investment.capital * product.annual_rate_bps) // (10000 * 365)
    accrual = InvestmentAccrual(
        investment_id=investment.id,
        accrual_date=accrual_date,
        estimated_amount=daily_estimate,
        accrued_amount=0,
        confirmed_amount=0,
        paid_amount=0,
        status="estimated",
    )
    db.session.add(accrual)
    db.session.flush()


def complete_investment(investment: Investment) -> None:
    """Clôture l'investissement au 120e jour : rembourse le capital (portefeuille
    'deposit') et comptabilise les revenus réellement validés (portefeuille
    'earnings'). Aucun gain n'est payé s'il n'est pas validé économiquement."""
    from app.services import finance

    if investment.status != "active":
        return
    product = investment.product
    accruals = InvestmentAccrual.query.filter_by(investment_id=investment.id).all()
    total_estimated = sum(a.estimated_amount for a in accruals)

    # Remboursement du capital sur le portefeuille dépôt.
    finance.credit(
        investment.user_id, investment.currency, "deposit", investment.capital,
        "investment_repayment", "investments",
        reference=f"INV-REP-{investment.id}",
        description=f"Remboursement capital {product.name}",
    )
    # Les revenus estimés ne sont PAS des gains confirmés : ils restent estimés
    # tant qu'un processus de validation ne les a pas comptabilisés.
    investment.capital_repaid = investment.capital
    investment.status = "completed"
    db.session.flush()
