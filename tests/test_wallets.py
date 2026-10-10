"""Tests des portefeuilles et du bonus."""
import pytest

from app.constants import WALLET_BONUS, WALLET_DEPOSIT, WALLET_WITHDRAWABLE
from app.models import LedgerEntry, User
from app.services import finance
from app.services.finance import InsufficientFundsError

from tests.helpers import make_user, register


def test_welcome_bonus_credited_once(app, client, db):
    register(client)
    user = User.query.filter_by(phone_number="+22997000002").first()
    bonus_entries = LedgerEntry.query.filter_by(
        user_id=user.id, transaction_type="welcome_bonus"
    ).all()
    assert len(bonus_entries) == 1
    assert finance.get_balance(user.id, "XOF", WALLET_BONUS) == 1500


def test_wallet_separation(app, db):
    user = make_user(db)
    finance.credit(user.id, "XOF", WALLET_DEPOSIT, 5000, "deposit", "test")
    finance.credit(user.id, "XOF", WALLET_BONUS, 1500, "bonus", "test")
    db.session.commit()
    # Les portefeuilles sont indépendants.
    assert finance.get_balance(user.id, "XOF", WALLET_DEPOSIT) == 5000
    assert finance.get_balance(user.id, "XOF", WALLET_BONUS) == 1500
    assert finance.get_balance(user.id, "XOF", WALLET_WITHDRAWABLE) == 0


def test_no_negative_balance(app, db):
    user = make_user(db)
    with pytest.raises(InsufficientFundsError):
        finance.debit(user.id, "XOF", WALLET_WITHDRAWABLE, 100, "withdrawal", "test")


def test_currency_isolation(app, db):
    user = make_user(db, currency="XOF")
    finance.credit(user.id, "XOF", WALLET_DEPOSIT, 1000, "deposit", "test")
    # Le même montant dans une autre devise n'existe pas.
    assert finance.get_balance(user.id, "XAF", WALLET_DEPOSIT) == 0
