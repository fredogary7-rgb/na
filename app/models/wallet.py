"""Portefeuilles : soldes séparés par type et par devise."""
from sqlalchemy import CheckConstraint, UniqueConstraint

from app.extensions import db
from app.models.base import TimestampMixin


class Wallet(TimestampMixin, db.Model):
    __tablename__ = "wallets"
    __table_args__ = (
        UniqueConstraint("user_id", "currency", "type", name="uq_wallet_user_currency_type"),
        CheckConstraint("balance >= 0", name="ck_wallet_balance_non_negative"),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    currency = db.Column(db.String(3), nullable=False)
    type = db.Column(db.String(20), nullable=False)
    balance = db.Column(db.BigInteger, default=0, nullable=False)

    def __repr__(self) -> str:
        return f"<Wallet {self.user_id} {self.currency} {self.type} {self.balance}>"
