"""Tests de la page Produits et du catalogue NAMARA."""
import pytest

from app.constants import WALLET_DEPOSIT, WALLET_EARNINGS
from app.models import InvestmentProduct
from app.services import finance, investment
from app.services.investment import InvestmentError

from tests.helpers import login, make_user


def _seed(app, db):
    with app.app_context():
        investment.seed_catalog_products()
        db.session.commit()


# ---------------------------------------------------------------------------
# Catalogue
# ---------------------------------------------------------------------------
def test_catalog_seed_idempotent(app, db):
    with app.app_context():
        first = investment.seed_catalog_products()
        db.session.commit()
        second = investment.seed_catalog_products()
        db.session.commit()
        assert first == 9
        assert second == 0
        assert InvestmentProduct.query.count() == 9


def test_catalog_names_prices_durations(app, db):
    _seed(app, db)
    with app.app_context():
        expected = {
            "NAMARA 1": 3000, "NAMARA 2": 5000, "NAMARA 3": 10000,
            "NAMARA 4": 25000, "NAMARA 5": 50000, "NAMARA 6": 100000,
            "NAMARA 7": 150000, "NAMARA 8": 200000, "NAMARA 9": 250000,
        }
        for name, price in expected.items():
            p = InvestmentProduct.query.filter_by(name=name).first()
            assert p is not None, name
            assert p.min_amount == price
            assert p.max_amount == price
            assert p.duration_days == 90


def test_catalog_disabled_products(app, db):
    _seed(app, db)
    with app.app_context():
        for name in ["NAMARA 7", "NAMARA 8", "NAMARA 9"]:
            p = InvestmentProduct.query.filter_by(name=name).first()
            assert p.status == "disabled"
        approved = InvestmentProduct.query.filter_by(status="approved").count()
        assert approved == 6
        # Le catalogue public montre tout ; la souscription ne voit que les actifs.
        assert len(investment.catalog_products()) == 9
        assert len(investment.available_products("XOF")) == 6


# ---------------------------------------------------------------------------
# Simulation
# ---------------------------------------------------------------------------
def test_simulation_calculations(app, db):
    _seed(app, db)
    with app.app_context():
        expected = {
            "NAMARA 1": (240, 21600, 24600),
            "NAMARA 2": (400, 36000, 41000),
            "NAMARA 3": (800, 72000, 82000),
            "NAMARA 4": (2000, 180000, 205000),
            "NAMARA 5": (4000, 360000, 410000),
            "NAMARA 6": (8000, 720000, 820000),
            "NAMARA 7": (12000, 1080000, 1230000),
            "NAMARA 8": (16000, 1440000, 1640000),
            "NAMARA 9": (20000, 1800000, 2050000),
        }
        for name, (daily, revenue, total) in expected.items():
            p = InvestmentProduct.query.filter_by(name=name).first()
            sim = investment.simulation_for(p)
            assert round(sim["daily"]) == daily, name
            assert round(sim["revenue"]) == revenue, name
            assert round(sim["total"]) == total, name


def test_format_amount_fcfa(app):
    with app.app_context():
        from app.utils import format_amount

        assert format_amount(3000, "XOF") == "3\u00a0000 FCFA"
        assert format_amount(250000, "XAF") == "250\u00a0000 FCFA"



# ---------------------------------------------------------------------------
# Sécurité des souscriptions
# ---------------------------------------------------------------------------
def test_subscription_to_disabled_product_rejected(app, db):
    _seed(app, db)
    user = make_user(db)
    finance.credit(user.id, "XOF", WALLET_DEPOSIT, 1000000, "test", "test")
    db.session.commit()
    with app.app_context():
        p = InvestmentProduct.query.filter_by(name="NAMARA 7").first()
        with pytest.raises(InvestmentError):
            investment.invest(user, p, p.min_amount)


def test_subscription_blocked_when_not_enabled(app, db):
    app.config["SUBSCRIPTIONS_ENABLED"] = False
    _seed(app, db)
    user = make_user(db)
    finance.credit(user.id, "XOF", WALLET_DEPOSIT, 1000000, "test", "test")
    db.session.commit()
    with app.app_context():
        p = InvestmentProduct.query.filter_by(name="NAMARA 1").first()
        with pytest.raises(InvestmentError):
            investment.invest(user, p, p.min_amount)


def test_no_simulated_income_credited(app, db):
    _seed(app, db)
    user = make_user(db)
    finance.credit(user.id, "XOF", WALLET_DEPOSIT, 100000, "test", "test")
    db.session.commit()
    with app.app_context():
        p = InvestmentProduct.query.filter_by(name="NAMARA 1").first()
        investment.invest(user, p, p.min_amount)
        db.session.commit()
        assert finance.get_balance(user.id, "XOF", WALLET_EARNINGS) == 0
        assert finance.get_balance(user.id, "XOF", WALLET_DEPOSIT) == 97000


# ---------------------------------------------------------------------------
# Page publique
# ---------------------------------------------------------------------------
def test_products_page_renders(app, client, db):
    _seed(app, db)
    resp = client.get("/products")
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert "Nos produits" in html
    for name in ["NAMARA 1", "NAMARA 6", "NAMARA 9"]:
        assert name in html
    assert "90 jours" in html
    assert "Bientôt disponible" in html
    assert "Simulation indicative" in html


def test_products_page_no_footer(app, client, db):
    _seed(app, db)
    html = client.get("/products").get_data(as_text=True)
    assert "Informations légales" not in html
    assert "ne prétend pas être agréée" not in html


def test_simulation_display_can_be_disabled(app, client, db):
    app.config["SIMULATION_SHOW_AMOUNTS"] = False
    _seed(app, db)
    html = client.get("/products").get_data(as_text=True)
    assert "240 FCFA" not in html


def test_admin_products_requires_admin(app, client, db):
    user = make_user(db, role="user")
    db.session.commit()
    login(client, user.phone_number)
    resp = client.get("/admin/products")
    assert resp.status_code == 403
