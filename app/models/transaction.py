"""Journal financier : écritures comptables immuables et traçables.

Le montant est signé : positif = crédit, négatif = débit.
"""
from app.extensions import db
from app.models.base import TimestampMixin, utcnow


class LedgerEntry(TimestampMixin, db.Model):
    __tablename__ = "ledger_entries"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    wallet_type = db.Column(db.String(20), nullable=False)
    currency = db.Column(db.String(3), nullable=False)
    amount = db.Column(db.BigInteger, nullable=False)  # signé : + crédit, - débit
    entry_type = db.Column(db.String(10), nullable=False)  # credit / debit
    transaction_type = db.Column(db.String(40), nullable=False)
    reference = db.Column(db.String(64), unique=True, index=True, nullable=False)
    status = db.Column(db.String(20), default="confirmed", nullable=False)
    balance_after = db.Column(db.BigInteger, nullable=False)
    source = db.Column(db.String(40), nullable=False)
    operator = db.Column(db.String(30), nullable=True)  # opérateur Mobile Money si applicable
    external_ref = db.Column(db.String(120), nullable=True)
    description = db.Column(db.String(255), nullable=True)
    confirmed_at = db.Column(db.DateTime, nullable=True)

    def __repr__(self) -> str:
        return f"<LedgerEntry {self.reference} {self.amount}>"
