"""Comptes Mobile Money enregistrés par l'utilisateur (destination de retrait).

Un « compte mobile » = opérateur (MTN, Orange, Moov, Wave, Airtel, Mov, Mix)
+ numéro de portefeuille. On n'enregistre jamais de numéro de carte bancaire.
"""
from app.extensions import db
from app.models.base import TimestampMixin


class Card(TimestampMixin, db.Model):
    __tablename__ = "cards"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    operator = db.Column(db.String(30), nullable=False)  # MTN / Orange / Moov / Wave / ...
    phone_number = db.Column(db.String(20), nullable=False)  # numéro du portefeuille mobile
    name = db.Column(db.String(120), nullable=True)  # nom du titulaire (facultatif)
    is_active = db.Column(db.Boolean, default=True, nullable=False)

    @property
    def last4(self) -> str:
        return (self.phone_number or "")[-4:]

    @property
    def masked(self) -> str:
        num = self.phone_number or ""
        return "•••• " + num[-4:] if len(num) > 4 else num

    def __repr__(self) -> str:
        return f"<Card {self.id} {self.operator} {self.phone_number}>"

