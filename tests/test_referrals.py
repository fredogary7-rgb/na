"""Tests du parrainage."""
import pytest

from app.constants import WALLET_REFERRAL
from app.models import ReferralCommission
from app.payments import service as payments
from app.services import finance, referral
from app.services.referral import ReferralError

from tests.helpers import make_user, signed_webhook


def test_self_referral_rejected(app, db):
    user = make_user(db)
    db.session.commit()
    with pytest.raises(ReferralError):
        referral.attach_referrals(user, user.referral_code)


def test_commission_on_deposit(app, client, db):
    referrer = make_user(db, phone="+22997000001")
    referred = make_user(db, phone="+22997000002")
    referral.attach_referrals(referred, referrer.referral_code)
    db.session.commit()

    deposit = payments.initiate_deposit(referred, 10000, "XOF", "Benin", "MTN", "+22997000002")
    db.session.commit()

    body, sig = signed_webhook(app, {
        "reference": deposit.reference,
        "amount": 10000,
        "currency": "XOF",
        "status": "success",
        "external_ref": "ext-1",
    })
    client.post(
        "/payments/webhook/mock",
        data=body,
        content_type="application/json",
        headers={"X-Namara-Signature": sig},
    )
    db.session.expire_all()

    commission = ReferralCommission.query.filter_by(referrer_id=referrer.id).first()
    assert commission is not None
    assert commission.amount == 1200  # 12 % de 10 000
    assert commission.status == "confirmed"
    assert finance.get_balance(referrer.id, "XOF", WALLET_REFERRAL) == 1200


def test_no_double_commission(app, client, db):
    referrer = make_user(db, phone="+22997000001")
    referred = make_user(db, phone="+22997000002")
    referral.attach_referrals(referred, referrer.referral_code)
    db.session.commit()

    deposit = payments.initiate_deposit(referred, 10000, "XOF", "Benin", "MTN", "+22997000002")
    db.session.commit()

    payload = {
        "reference": deposit.reference,
        "amount": 10000,
        "currency": "XOF",
        "status": "success",
        "external_ref": "ext-1",
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
    assert ReferralCommission.query.filter_by(referrer_id=referrer.id).count() == 1
    assert finance.get_balance(referrer.id, "XOF", WALLET_REFERRAL) == 1200
