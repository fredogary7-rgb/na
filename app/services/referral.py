"""Service de parrainage : relations et calcul de commissions.

Les commissions ne sont jamais versées pour le simple recrutement d'un
utilisateur. Elles sont rattachées à une opération économique qualifiée
(par exemple un dépôt confirmé) et désactivées tant que la conformité n'est
pas validée (REFERRAL_ENABLED / paramètre en base).
"""
from app.extensions import db
from app.models import ReferralCommission, ReferralRelationship, User
from app.models.base import utcnow
from app.services import finance
from app.utils import new_reference


class ReferralError(Exception):
    pass


def attach_referrals(new_user: User, referral_code: str, max_level: int = 3) -> None:
    """Attache un nouvel utilisateur à son arbre de parrainage (niveaux 1 à 3)."""
    if not referral_code:
        return
    referrer = User.query.filter_by(referral_code=referral_code.strip().upper()).first()
    if referrer is None:
        raise ReferralError("Code de parrainage invalide.")
    if referrer.id == new_user.id:
        raise ReferralError("Auto-parrainage interdit.")

    current = referrer
    level = 1
    seen = set()
    while current is not None and level <= max_level:
        if current.id in seen:
            raise ReferralError("Référence circulaire détectée.")
        seen.add(current.id)
        exists = ReferralRelationship.query.filter_by(
            referrer_id=current.id, referred_id=new_user.id, level=level
        ).first()
        if exists is None:
            db.session.add(
                ReferralRelationship(
                    referrer_id=current.id, referred_id=new_user.id, level=level
                )
            )
        level += 1
        current = current.referrer_id and User.query.get(current.referrer_id) or None


def referral_enabled() -> bool:
    from app.services import settings

    return settings.get_bool("REFERRAL_ENABLED", False)


def _rate_bps(level: int) -> int:
    from flask import current_app

    return current_app.config.get(
        f"REFERRAL_LEVEL_{level}_BPS", {1: 1200, 2: 300, 3: 200}.get(level, 0)
    )


def compute_commissions(
    referred_user: User,
    source_type: str,
    source_reference: str,
    base_amount: int,
    currency: str,
) -> list:
    """Calcule et enregistre les commissions (statut 'pending') pour une opération.

    Renvoie la liste des ReferralCommission créées (aucune si désactivé).
    """
    if not referral_enabled():
        return []
    relations = (
        ReferralRelationship.query.filter_by(referred_id=referred_user.id)
        .order_by(ReferralRelationship.level.asc())
        .all()
    )
    created = []
    for rel in relations:
        bps = _rate_bps(rel.level)
        if bps <= 0:
            continue
        amount = (base_amount * bps) // 10000
        if amount <= 0:
            continue
        reference = new_reference("RC")
        commission = ReferralCommission(
            referrer_id=rel.referrer_id,
            referred_id=referred_user.id,
            level=rel.level,
            source_type=source_type,
            source_reference=source_reference,
            amount=amount,
            currency=currency,
            status="pending",
            reference=reference,
        )
        db.session.add(commission)
        created.append(commission)
    db.session.flush()
    return created


def confirm_commission(commission: ReferralCommission) -> None:
    """Confirme une commission : crédite le portefeuille 'referral'."""
    if commission.status == "confirmed":
        return
    finance.credit(
        commission.referrer_id,
        commission.currency,
        "referral",
        commission.amount,
        "referral_commission",
        "referral",
        reference=f"{commission.reference}-CRED",
        description=f"Commission parrainage niveau {commission.level}",
    )
    commission.status = "confirmed"
    commission.confirmed_at = utcnow()
    db.session.flush()

    from app.notifications.service import notify

    notify(
        commission.referrer_id,
        "referral_commission",
        "Commission de parrainage reçue",
        f"Vous avez reçu une commission de {commission.amount} {commission.currency}.",
    )


def reverse_commission(commission: ReferralCommission) -> None:
    """Annulation comptable d'une commission déjà confirmée."""
    if commission.status == "reversed":
        return
    if commission.status == "confirmed":
        finance.debit(
            commission.referrer_id,
            commission.currency,
            "referral",
            commission.amount,
            "referral_reversal",
            "referral",
            reference=f"{commission.reference}-REV",
            description=f"Annulation commission {commission.reference}",
        )
    commission.status = "reversed"
    db.session.flush()
