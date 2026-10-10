"""Notifications in-app."""
from app.extensions import db
from app.models.base import TimestampMixin


class Notification(TimestampMixin, db.Model):
    __tablename__ = "notifications"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    event = db.Column(db.String(60), nullable=False)
    title = db.Column(db.String(120), nullable=False)
    message = db.Column(db.String(500), nullable=False)
    is_read = db.Column(db.Boolean, default=False, nullable=False)

    def __repr__(self) -> str:
        return f"<Notification {self.event} {self.user_id}>"
