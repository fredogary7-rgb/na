"""Utilitaires partagés : formatage, références, pays."""
import re
import secrets
import string
from datetime import datetime, timedelta

from app.constants import COUNTRIES


def format_amount(amount: int, currency: str = "XOF") -> str:
    """Formate un montant entier (FCFA) à la française : 3 000 FCFA."""
    label = "FCFA" if currency in ("XOF", "XAF") else currency
    value = f"{int(amount):,}".replace(",", "\u00a0")
    return f"{value} {label}"


def parse_amount(raw) -> int:
    """Convertit une saisie française ('3 000' ou '3000') en entier."""
    if raw is None:
        return 0
    if isinstance(raw, int):
        return raw
    digits = re.sub(r"[^\d]", "", str(raw))
    return int(digits) if digits else 0


def new_reference(prefix: str) -> str:
    return f"{prefix}-{secrets.token_hex(8).upper()}"


def currency_for_country(country: str) -> str:
    return COUNTRIES.get(country, {}).get("currency", "XOF")


def country_is_enabled(country: str) -> bool:
    return COUNTRIES.get(country, {}).get("enabled", False)


def operators_for_country(country: str):
    from app.constants import OPERATORS

    return OPERATORS.get(country, [])
