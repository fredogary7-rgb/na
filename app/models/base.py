"""Mixins et utilitaires communs aux modèles."""
from datetime import datetime, timezone

from app.extensions import db


def utcnow():
    """Date/heure UTC naïve (compatible SQLite et PostgreSQL)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class TimestampMixin:
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=utcnow, onupdate=utcnow, nullable=False)
