"""Page de parrainage : code, règles, historique des commissions."""
from urllib.parse import quote

from flask import Blueprint, current_app, render_template, url_for
from flask_login import current_user, login_required

from app.models import ReferralCommission, ReferralRelationship
from app.services import referral as referral_service

referrals_bp = Blueprint("referrals", __name__)


@referrals_bp.route("/")
@login_required
def index():
    commissions = (
        ReferralCommission.query.filter_by(referrer_id=current_user.id)
        .order_by(ReferralCommission.created_at.desc())
        .limit(100)
        .all()
    )
    level_1 = ReferralRelationship.query.filter_by(referrer_id=current_user.id, level=1).count()
    level_2 = ReferralRelationship.query.filter_by(referrer_id=current_user.id, level=2).count()
    level_3 = ReferralRelationship.query.filter_by(referrer_id=current_user.id, level=3).count()
    enabled = referral_service.referral_enabled()
    rate_1 = current_app.config.get("REFERRAL_LEVEL_1_BPS", 1200) / 100
    rate_2 = current_app.config.get("REFERRAL_LEVEL_2_BPS", 300) / 100
    rate_3 = current_app.config.get("REFERRAL_LEVEL_3_BPS", 200) / 100
    referral_link = url_for("auth.register", _external=True, ref=current_user.referral_code)
    share_text = (
        f"Rejoignez-moi sur NAMARA et gagnez ensemble ! "
        f"Inscrivez-vous avec mon code {current_user.referral_code} : {referral_link}"
    )
    share_whatsapp = f"https://wa.me/?text={quote(share_text)}"
    share_telegram = f"https://t.me/share/url?url={quote(referral_link)}&text={quote(share_text)}"
    return render_template(
        "dashboard/referrals.html",
        commissions=commissions,
        level_1=level_1,
        level_2=level_2,
        level_3=level_3,
        rate_1=rate_1,
        rate_2=rate_2,
        rate_3=rate_3,
        referral_link=referral_link,
        share_whatsapp=share_whatsapp,
        share_telegram=share_telegram,
        enabled=enabled,
    )
