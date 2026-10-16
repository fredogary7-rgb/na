"""Tests des actions admin sur les utilisateurs (crédit / débit / suppression)."""
from app.constants import WALLET_DEPOSIT
from app.extensions import db
from app.models import User
from app.services import finance

from tests.helpers import login, make_user


def _admin_login(client, db):
    admin = make_user(db, phone="+22997000099", role="admin")
    db.session.commit()
    login(client, admin.phone_number)
    return admin


def test_admin_can_credit_user(app, client, db):
    admin = _admin_login(client, db)
    user = make_user(db)
    db.session.commit()

    resp = client.post(
        f"/admin/users/{user.id}/credit",
        data={"amount": "5000"},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert finance.get_balance(user.id, "XOF", WALLET_DEPOSIT) == 5000
    assert admin is not None


def test_admin_can_debit_user(app, client, db):
    _admin_login(client, db)
    user = make_user(db)
    finance.credit(user.id, "XOF", WALLET_DEPOSIT, 10000, "test", "test")
    db.session.commit()

    client.post(f"/admin/users/{user.id}/debit", data={"amount": "3000"}, follow_redirects=True)
    assert finance.get_balance(user.id, "XOF", WALLET_DEPOSIT) == 7000


def test_admin_debit_refuses_insufficient_funds(app, client, db):
    _admin_login(client, db)
    user = make_user(db)
    db.session.commit()

    client.post(f"/admin/users/{user.id}/debit", data={"amount": "99999"}, follow_redirects=True)
    assert finance.get_balance(user.id, "XOF", WALLET_DEPOSIT) == 0


def test_admin_can_delete_user(app, client, db):
    _admin_login(client, db)
    user = make_user(db)
    db.session.commit()

    client.post(f"/admin/users/{user.id}/delete", follow_redirects=True)
    assert db.session.get(User, user.id) is None


def test_non_admin_cannot_credit(app, client, db):
    user = make_user(db)
    db.session.commit()
    login(client, user.phone_number)

    resp = client.post(f"/admin/users/{user.id}/credit", data={"amount": "5000"})
    assert resp.status_code == 403
    assert finance.get_balance(user.id, "XOF", WALLET_DEPOSIT) == 0
