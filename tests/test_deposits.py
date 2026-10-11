"""Tests des dépôts et des webhooks."""
from app.constants import WALLET_DEPOSIT
from app.extensions import db
from app.models import Deposit
from app.payments import service as payments
from app.services import finance

from tests.helpers import login, make_user, signed_webhook


def test_services_catalog(app):
    from app.payments.services import service_by_name, services_for_country

    benin = services_for_country("Benin")
    assert len(benin) == 2
    assert benin[0]["operator"] == "MTN"

    ci = services_for_country("Cote d'Ivoire")
    assert len(ci) == 4

    s = service_by_name("Benin", "MOMO BJ")
    assert s is not None
    assert s["id"] == 35


def test_deposit_minimum_rejected(app, client, db):
    user = make_user(db)
    db.session.commit()
    login(client, user.phone_number)
    resp = client.post(
        "/dashboard/deposits",
        data={"amount": "1000", "operator": "MTN", "phone_number": "97000001"},
        follow_redirects=True,
    )
    assert Deposit.query.filter_by(user_id=user.id).count() == 0


def test_deposit_not_credited_before_confirmation(app, db):
    user = make_user(db)
    db.session.commit()
    deposit = payments.initiate_deposit(user, 5000, "XOF", "Benin", "MTN", "+22997000001")
    db.session.commit()
    assert finance.get_balance(user.id, "XOF", WALLET_DEPOSIT) == 0
    assert deposit.status == "pending"


def test_webhook_credits_deposit(app, client, db):
    user = make_user(db)
    db.session.commit()
    deposit = payments.initiate_deposit(user, 5000, "XOF", "Benin", "MTN", "+22997000001")
    db.session.commit()

    body, sig = signed_webhook(app, {
        "reference": deposit.reference,
        "amount": 5000,
        "currency": "XOF",
        "status": "success",
        "external_ref": "ext-123",
    })
    resp = client.post(
        "/payments/webhook/mock",
        data=body,
        content_type="application/json",
        headers={"X-Namara-Signature": sig},
    )
    assert resp.status_code == 200
    db.session.expire_all()
    assert finance.get_balance(user.id, "XOF", WALLET_DEPOSIT) == 5000
    assert Deposit.query.filter_by(reference=deposit.reference).first().status == "successful"


def test_webhook_idempotent(app, client, db):
    user = make_user(db)
    db.session.commit()
    deposit = payments.initiate_deposit(user, 5000, "XOF", "Benin", "MTN", "+22997000001")
    db.session.commit()

    payload = {
        "reference": deposit.reference,
        "amount": 5000,
        "currency": "XOF",
        "status": "success",
        "external_ref": "ext-123",
    }
    for _ in range(2):
        body, sig = signed_webhook(app, payload)
        client.post(
            "/payments/webhook/mock",
            data=body,
            content_type="application/json",
            headers={"X-Namara-Signature": sig},
        )
    db.session.expire_all()
    # Un seul crédit malgré deux événements.
    assert finance.get_balance(user.id, "XOF", WALLET_DEPOSIT) == 5000


def test_webhook_amount_mismatch_rejected(app, client, db):
    user = make_user(db)
    db.session.commit()
    deposit = payments.initiate_deposit(user, 5000, "XOF", "Benin", "MTN", "+22997000001")
    db.session.commit()

    body, sig = signed_webhook(app, {
        "reference": deposit.reference,
        "amount": 9999,
        "currency": "XOF",
        "status": "success",
        "external_ref": "ext-999",
    })
    resp = client.post(
        "/payments/webhook/mock",
        data=body,
        content_type="application/json",
        headers={"X-Namara-Signature": sig},
    )
    assert resp.status_code == 400
    assert finance.get_balance(user.id, "XOF", WALLET_DEPOSIT) == 0
