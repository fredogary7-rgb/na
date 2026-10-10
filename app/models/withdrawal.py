"""Retraits."""
from app.extensions import db
from app.models.base import TimestampMixin


class Withdrawal(TimestampMixin, db.Model):
    __tablename__ = "withdrawals"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    amount = db.Column(db.BigInteger, nullable=False)  # montant brut demandé
    fee = db.Column(db.BigInteger, default=0, nullable=False)  # frais retenus
    net_amount = db.Column(db.BigInteger, default=0, nullable=False)  # montant net versé
    currency = db.Column(db.String(3), nullable=False)
    country = db.Column(db.String(60), nullable=False)
    operator = db.Column(db.String(30), nullable=False)
    wallet_number = db.Column(db.String(30), nullable=False)
    reference = db.Column(db.String(64), unique=True, index=True, nullable=False)
    status = db.Column(db.String(20), default="pending", nullable=False, index=True)
    external_ref = db.Column(db.String(120), nullable=True)
    processed_at = db.Column(db.DateTime, nullable=True)

    def __repr__(self) -> str:
        return f"<Withdrawal {self.reference} {self.amount} {self.currency} {self.status}>"
