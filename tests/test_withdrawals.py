"""Tests des retraits."""
import pytest

from app.constants import WALLET_DEPOSIT, WALLET_WITHDRAWABLE
from app.models import Withdrawal
from app.payments import service as payments
from app.services import finance
from app.services.finance import InsufficientFundsError

from tests.helpers import make_user


def test_withdrawal_minimum_rejected(app, db):
    user = make_user(db)
    finance.credit(user.id, "XOF", WALLET_WITHDRAWABLE, 5000, "test", "test")
    db.session.commit()
    with pytest.raises(ValueError):
        payments.create_withdrawal(user, 1000, "XOF", "Benin", "MTN", "97000001")


def test_withdrawal_reserves_funds(app, db):
    user = make_user(db)
    finance.credit(user.id, "XOF", WALLET_WITHDRAWABLE, 5000, "test", "test")
    db.session.commit()
    withdrawal = payments.create_withdrawal(user, 2000, "XOF", "Benin", "MTN", "97000001")
    db.session.commit()
    assert finance.get_balance(user.id, "XOF", WALLET_WITHDRAWABLE) == 3000
    assert withdrawal.status == "pending"


def test_cannot_withdraw_deposit_wallet(app, db):
    user = make_user(db)
    finance.credit(user.id, "XOF", WALLET_DEPOSIT, 5000, "test", "test")
    db.session.commit()
    # Le capital déposé n'est pas retirable : solde retirable à 0.
    with pytest.raises(InsufficientFundsError):
        payments.create_withdrawal(user, 2000, "XOF", "Benin", "MTN", "97000001")


def test_reject_refunds_funds(app, db):
    user = make_user(db)
    finance.credit(user.id, "XOF", WALLET_WITHDRAWABLE, 5000, "test", "test")
    db.session.commit()
    withdrawal = payments.create_withdrawal(user, 2000, "XOF", "Benin", "MTN", "97000001")
    db.session.commit()
    payments.refund_withdrawal(withdrawal, "rejected")
    db.session.commit()
    assert finance.get_balance(user.id, "XOF", WALLET_WITHDRAWABLE) == 5000
    assert withdrawal.status == "rejected"
