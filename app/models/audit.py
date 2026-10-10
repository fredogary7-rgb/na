"""Journal d'audit des actions sensibles."""
from app.extensions import db
from app.models.base import TimestampMixin, utcnow


class AuditLog(TimestampMixin, db.Model):
    __tablename__ = "audit_logs"

    id = db.Column(db.Integer, primary_key=True)
    admin_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    action = db.Column(db.String(80), nullable=False)
    target_type = db.Column(db.String(60), nullable=True)
    target_id = db.Column(db.String(64), nullable=True)
    details = db.Column(db.Text, nullable=True)
    ip_address = db.Column(db.String(45), nullable=True)

    def __repr__(self) -> str:
        return f"<AuditLog {self.action} {self.target_type} {self.target_id}>"
