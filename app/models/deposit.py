"""Dépôts."""
from app.extensions import db
from app.models.base import TimestampMixin


class Deposit(TimestampMixin, db.Model):
    __tablename__ = "deposits"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    amount = db.Column(db.BigInteger, nullable=False)
    currency = db.Column(db.String(3), nullable=False)
    country = db.Column(db.String(60), nullable=False)
    operator = db.Column(db.String(30), nullable=False)
    phone_number = db.Column(db.String(20), nullable=False)
    provider = db.Column(db.String(30), nullable=False)
    service_id = db.Column(db.Integer, nullable=True)  # id du service Mobile Money (SoleasPay)
    reference = db.Column(db.String(64), unique=True, index=True, nullable=False)
    status = db.Column(db.String(20), default="pending", nullable=False, index=True)
    external_ref = db.Column(db.String(120), nullable=True)
    confirmed_at = db.Column(db.DateTime, nullable=True)

    def __repr__(self) -> str:
        return f"<Deposit {self.reference} {self.amount} {self.currency} {self.status}>"
