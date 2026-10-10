"""Tests du module d'investissement."""
import pytest

from app.constants import WALLET_DEPOSIT
from app.models import InvestmentAccrual, InvestmentProduct
from app.services import finance, investment
from app.services.investment import InvestmentError

from tests.helpers import make_user


def test_no_approved_product_available(app, db):
    user = make_user(db)
    db.session.commit()
    assert investment.available_products(currency="XOF") == []


def test_invest_requires_approved_product(app, db):
    user = make_user(db)
    finance.credit(user.id, "XOF", WALLET_DEPOSIT, 100000, "test", "test")
    product = InvestmentProduct(
        name="Produit test", status="draft", duration_days=120,
        min_amount=1000, max_amount=1000000, currency="XOF",
    )
    db.session.add(product)
    db.session.commit()
    with pytest.raises(InvestmentError):
        investment.invest(user, product, 5000)


def test_invest_debits_deposit_wallet(app, db):
    user = make_user(db)
    finance.credit(user.id, "XOF", WALLET_DEPOSIT, 100000, "test", "test")
    product = InvestmentProduct(
        name="Produit test", status="approved", duration_days=120,
        min_amount=1000, max_amount=1000000, currency="XOF", annual_rate_bps=1000,
    )
    db.session.add(product)
    db.session.flush()
    inv = investment.invest(user, product, 5000)
    db.session.commit()
    assert finance.get_balance(user.id, "XOF", WALLET_DEPOSIT) == 95000
    assert inv.status == "active"


def test_daily_accrue_idempotent(app, db):
    user = make_user(db)
    finance.credit(user.id, "XOF", WALLET_DEPOSIT, 100000, "test", "test")
    product = InvestmentProduct(
        name="Produit test", status="approved", duration_days=120,
        min_amount=1000, max_amount=1000000, currency="XOF", annual_rate_bps=3650,
    )
    db.session.add(product)
    db.session.flush()
    inv = investment.invest(user, product, 10000)
    db.session.commit()

    investment.daily_accrue(inv)
    investment.daily_accrue(inv)
    db.session.commit()
    count = InvestmentAccrual.query.filter_by(investment_id=inv.id).count()
    assert count == 1
