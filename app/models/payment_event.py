"""Événements de paiement reçus (webhooks), journalisés pour idempotence."""
from app.extensions import db
from app.models.base import TimestampMixin, utcnow


class PaymentEvent(TimestampMixin, db.Model):
    __tablename__ = "payment_events"

    id = db.Column(db.Integer, primary_key=True)
    provider = db.Column(db.String(30), nullable=False)
    event_type = db.Column(db.String(60), nullable=False)
    external_reference = db.Column(db.String(120), nullable=True, index=True)
    payload = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(20), default="received", nullable=False)
    processed_at = db.Column(db.DateTime, nullable=True)

    def __repr__(self) -> str:
        return f"<PaymentEvent {self.provider} {self.event_type} {self.status}>"
