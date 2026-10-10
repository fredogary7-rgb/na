"""Lecture/écriture des paramètres applicatifs (base + config)."""
from flask import current_app

from app.extensions import db
from app.models import ApplicationSetting


def _db_value(key):
    row = ApplicationSetting.query.filter_by(key=key).first()
    return row.value if row else None


def get_setting(key, default=None):
    value = _db_value(key)
    if value is None:
        value = current_app.config.get(key, default)
    return value


def get_bool(key, default=False):
    value = get_setting(key, default)
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in ("1", "true", "yes", "on")


def get_int(key, default=0):
    value = get_setting(key, default)
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def set_setting(key, value, description=None):
    row = ApplicationSetting.query.filter_by(key=key).first()
    if row is None:
        row = ApplicationSetting(key=key, value=str(value), description=description)
        db.session.add(row)
    else:
        row.value = str(value)
        if description is not None:
            row.description = description
    db.session.flush()
    return row
