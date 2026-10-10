"""Tests de l'enregistrement de compte Mobile Money."""
from app.constants import WALLET_WITHDRAWABLE
from app.models import Card, Withdrawal
from app.services import finance

from tests.helpers import login, make_user


def test_register_mobile_account(app, client, db):
    user = make_user(db)
    db.session.commit()
    login(client, user.phone_number)
    resp = client.post(
        "/dashboard/cards",
        data={"operator": "MTN", "phone_number": "97000001", "name": "Thomas Waza"},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    card = Card.query.filter_by(user_id=user.id).first()
    assert card is not None
    assert card.operator == "MTN"
    assert card.phone_number == "97000001"
    assert card.name == "Thomas Waza"


def test_register_requires_operator(app, client, db):
    user = make_user(db)
    db.session.commit()
    login(client, user.phone_number)
    client.post(
        "/dashboard/cards",
        data={"operator": "", "phone_number": "97000001", "name": ""},
        follow_redirects=True,
    )
    assert Card.query.filter_by(user_id=user.id).count() == 0


def test_register_invalid_phone_rejected(app, client, db):
    user = make_user(db)
    db.session.commit()
    login(client, user.phone_number)
    client.post(
        "/dashboard/cards",
        data={"operator": "MTN", "phone_number": "12", "name": ""},  # trop court
        follow_redirects=True,
    )
    assert Card.query.filter_by(user_id=user.id).count() == 0


def test_withdrawal_to_mobile_account(app, client, db):
    user = make_user(db)
    finance.credit(user.id, "XOF", WALLET_WITHDRAWABLE, 5000, "test", "test")
    db.session.commit()
    login(client, user.phone_number)
    client.post(
        "/dashboard/cards",
        data={"operator": "MTN", "phone_number": "97000001", "name": "Thomas Waza"},
    )
    card = Card.query.filter_by(user_id=user.id).first()
    # Étape 1 : formulaire -> page de confirmation
    r = client.post("/dashboard/withdrawals", data={"amount": "2000", "card_id": str(card.id)})
    assert r.status_code == 200
    # Étape 2 : confirmation -> création du retrait
    client.post("/dashboard/withdrawals/confirm", data={"amount": "2000", "card_id": str(card.id)})
    withdrawal = Withdrawal.query.filter_by(user_id=user.id).first()
    assert withdrawal is not None
    assert withdrawal.operator == "MTN"
    assert withdrawal.wallet_number == "97000001"
    # Frais de 8 % : 2000 -> frais 160, net 1840
    assert withdrawal.amount == 2000
    assert withdrawal.fee == 160
    assert withdrawal.net_amount == 1840


