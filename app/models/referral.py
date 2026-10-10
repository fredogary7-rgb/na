"""Parrainage : relations et commissions."""
from app.extensions import db
from app.models.base import TimestampMixin, utcnow


class ReferralRelationship(TimestampMixin, db.Model):
    """Lien matérialisé entre un parrain et un filleul (niveau 1 à 3)."""

    __tablename__ = "referral_relationships"

    id = db.Column(db.Integer, primary_key=True)
    referrer_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    referred_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    level = db.Column(db.Integer, nullable=False)  # 1, 2 ou 3
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)

    def __repr__(self) -> str:
        return f"<ReferralRelationship {self.referrer_id}->{self.referred_id} L{self.level}>"


class ReferralCommission(TimestampMixin, db.Model):
    __tablename__ = "referral_commissions"

    id = db.Column(db.Integer, primary_key=True)
    referrer_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    referred_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    level = db.Column(db.Integer, nullable=False)
    source_type = db.Column(db.String(40), nullable=False)  # ex: "deposit"
    source_reference = db.Column(db.String(64), nullable=False, index=True)
    amount = db.Column(db.BigInteger, nullable=False)
    currency = db.Column(db.String(3), nullable=False)
    status = db.Column(db.String(20), default="pending", nullable=False)
    reference = db.Column(db.String(64), unique=True, index=True, nullable=False)
    confirmed_at = db.Column(db.DateTime, nullable=True)

    def __repr__(self) -> str:
        return f"<ReferralCommission {self.reference} {self.amount}>"
