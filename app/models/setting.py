"""Paramètres applicatifs modifiables en base (clé/valeur)."""
from app.extensions import db
from app.models.base import TimestampMixin


class ApplicationSetting(TimestampMixin, db.Model):
    __tablename__ = "application_settings"

    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(80), unique=True, index=True, nullable=False)
    value = db.Column(db.Text, nullable=False)
    description = db.Column(db.String(255), nullable=True)

    def __repr__(self) -> str:
        return f"<ApplicationSetting {self.key}={self.value}>"
