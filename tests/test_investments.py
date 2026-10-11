"""Tests du module d'investissement."""
import pytest

from app.constants import WALLET_DEPOSIT, WALLET_EARNINGS
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


def test_invest_insufficient_funds_raises_investment_error(app, db):
    user = make_user(db)
    # Aucun crédit : le portefeuille dépôt est vide.
    product = InvestmentProduct(
        name="Produit test", status="approved", duration_days=120,
        min_amount=1000, max_amount=1000000, currency="XOF",
    )
    db.session.add(product)
    db.session.flush()
    with pytest.raises(InvestmentError):
        investment.invest(user, product, 5000)


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


def test_payout_daily_income(app, db):
    user = make_user(db)
    finance.credit(user.id, "XOF", WALLET_DEPOSIT, 100000, "test", "test")
    product = InvestmentProduct(
        name="NAMARA 1", status="approved", duration_days=90,
        min_amount=3000, max_amount=3000, currency="XOF",
    )
    db.session.add(product)
    db.session.flush()
    inv = investment.invest(user, product, 3000)
    db.session.commit()

    # Revenu quotidien = 3000 * 0.08 = 240, versé sur 'earnings'.
    n = investment.payout_daily_income()
    db.session.commit()
    assert n == 1
    assert finance.get_balance(user.id, "XOF", WALLET_EARNINGS) == 240

    # Idempotent : relancer le même jour ne crée pas de double versement.
    n2 = investment.payout_daily_income()
    db.session.commit()
    assert n2 == 0
    assert finance.get_balance(user.id, "XOF", WALLET_EARNINGS) == 240


def test_investments_page_requires_login(app, client):
    """Un visiteur non connecté est redirigé vers la page de connexion."""
    response = client.get("/investments/", follow_redirects=False)
    assert response.status_code == 302
    assert "/auth/login" in response.headers["Location"]


def test_investments_page_shows_only_own_investments(app, db, client):
    """Un utilisateur connecté voit uniquement ses propres souscriptions."""
    from tests.helpers import make_user, login
    import time

    u1 = make_user(db, phone="+22997000101")
    u2 = make_user(db, phone="+22997000102")
    finance.credit(u1.id, "XOF", WALLET_DEPOSIT, 100000, "test", "test")
    finance.credit(u2.id, "XOF", WALLET_DEPOSIT, 100000, "test", "test")
    product = InvestmentProduct(
        name="P1", status="approved", duration_days=90,
        min_amount=3000, max_amount=3000, currency="XOF",
    )
    db.session.add(product)
    db.session.flush()
    inv1 = investment.invest(u1, product, 3000)
    db.session.flush()
    time.sleep(1.1)
    inv2 = investment.invest(u2, product, 3000)
    db.session.commit()

    login(client, phone=u1.phone_number)
    response = client.get("/investments/")
    html = response.data.decode()
    assert f"INV-{inv1.id}" in html
    assert f"INV-{inv2.id}" not in html


def test_investments_empty_state(app, db, client):
    """Un utilisateur sans souscription voit l'état vide."""
    from tests.helpers import make_user, login

    user = make_user(db, phone="+22997000201")
    db.session.commit()
    login(client, phone=user.phone_number)
    response = client.get("/investments/")
    html = response.data.decode()
    assert "Vous n'avez pas encore de produit" in html
    assert "Découvrir les produits" in html


def test_investments_filter_by_status(app, db, client):
    """Le filtre par statut fonctionne correctement."""
    from tests.helpers import make_user, login
    import time

    user = make_user(db, phone="+22997000301")
    finance.credit(user.id, "XOF", WALLET_DEPOSIT, 100000, "test", "test")
    product = InvestmentProduct(
        name="P1", status="approved", duration_days=90,
        min_amount=3000, max_amount=3000, currency="XOF",
    )
    db.session.add(product)
    db.session.flush()
    inv_active = investment.invest(user, product, 3000)
    db.session.flush()
    time.sleep(1.1)
    inv2 = investment.invest(user, product, 3000)
    inv2.status = "completed"
    db.session.commit()

    login(client, phone=user.phone_number)
    r = client.get("/investments/")
    assert f"INV-{inv_active.id}" in r.data.decode()
    assert f"INV-{inv2.id}" in r.data.decode()
    r = client.get("/investments/?status=active")
    html = r.data.decode()
    assert f"INV-{inv_active.id}" in html
    assert f"INV-{inv2.id}" not in html
    r = client.get("/investments/?status=completed")
    html = r.data.decode()
    assert f"INV-{inv_active.id}" not in html
    assert f"INV-{inv2.id}" in html
    r = client.get("/investments/?status=cancelled")
    assert "Aucun résultat" in r.data.decode()


def test_investments_search_by_name(app, db, client):
    """La recherche par nom de produit fonctionne."""
    from tests.helpers import make_user, login
    import time

    user = make_user(db, phone="+22997000401")
    finance.credit(user.id, "XOF", WALLET_DEPOSIT, 100000, "test", "test")
    p1 = InvestmentProduct(
        name="NAMARA 1", status="approved", duration_days=90,
        min_amount=3000, max_amount=3000, currency="XOF",
    )
    p2 = InvestmentProduct(
        name="NAMARA 2", status="approved", duration_days=90,
        min_amount=5000, max_amount=5000, currency="XOF",
    )
    db.session.add_all([p1, p2])
    db.session.flush()
    inv1 = investment.invest(user, p1, 3000)
    db.session.flush()
    time.sleep(1.1)
    inv2 = investment.invest(user, p2, 5000)
    db.session.commit()

    login(client, phone=user.phone_number)
    r = client.get("/investments/?q=NAMARA+1")
    html = r.data.decode()
    assert f"INV-{inv1.id}" in html
    assert f"INV-{inv2.id}" not in html


def test_investments_progression_within_bounds(app, db, client):
    """La progression reste toujours entre 0% et 100%."""
    from tests.helpers import make_user, login
    import re

    user = make_user(db, phone="+22997000501")
    finance.credit(user.id, "XOF", WALLET_DEPOSIT, 100000, "test", "test")
    product = InvestmentProduct(
        name="P1", status="approved", duration_days=90,
        min_amount=3000, max_amount=3000, currency="XOF",
    )
    db.session.add(product)
    db.session.flush()
    investment.invest(user, product, 3000)
    db.session.commit()

    login(client, phone=user.phone_number)
    r = client.get("/investments/")
    html = r.data.decode()
    widths = re.findall(r'width:(\d+)%', html)
    assert len(widths) > 0
    for w in widths:
        pct = int(w)
        assert 0 <= pct <= 100, f"Progression {pct}% hors bornes [0,100]"


def test_investments_completed_shows_100(app, db, client):
    """Une souscription terminée affiche 100%."""
    from tests.helpers import make_user, login

    user = make_user(db, phone="+22997000601")
    finance.credit(user.id, "XOF", WALLET_DEPOSIT, 100000, "test", "test")
    product = InvestmentProduct(
        name="P1", status="approved", duration_days=90,
        min_amount=3000, max_amount=3000, currency="XOF",
    )
    db.session.add(product)
    db.session.flush()
    inv = investment.invest(user, product, 3000)
    inv.status = "completed"
    db.session.commit()

    login(client, phone=user.phone_number)
    r = client.get("/investments/")
    assert 'width:100%' in r.data.decode()


def test_investments_no_balance_change_on_get(app, db, client):
    """Un simple GET ne modifie aucun solde."""
    from tests.helpers import make_user

    user = make_user(db)
    finance.credit(user.id, "XOF", WALLET_DEPOSIT, 100000, "test", "test")
    product = InvestmentProduct(
        name="P1", status="approved", duration_days=90,
        min_amount=3000, max_amount=3000, currency="XOF",
    )
    db.session.add(product)
    db.session.flush()
    investment.invest(user, product, 3000)
    db.session.commit()

    balance_before = finance.get_balance(user.id, "XOF", WALLET_DEPOSIT)

    with client:
        client.post("/auth/login", data={"phone": user.phone_number, "password": "password123"}, follow_redirects=True)
        client.get("/investments/")

    balance_after = finance.get_balance(user.id, "XOF", WALLET_DEPOSIT)
    assert balance_before == balance_after
