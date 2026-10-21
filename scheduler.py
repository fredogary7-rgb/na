"""Planificateur quotidien : verse le revenu des investissements actifs et
publie le message d'information de la chaîne Telegram.

Usage : `python scheduler.py` (processus séparé — service Railway dédié ou cron).
Le versement est idempotent : relancer ne crédite jamais deux fois le même jour.

Variables configurables :
  DAILY_PAYOUT_HOUR      (défaut 0)  — heure UTC du versement
  DAILY_PAYOUT_MINUTE    (défaut 5)  — minute UTC du versement
  CHANNEL_MESSAGE_HOURS  (défaut "8,12,18") — heures d'envoi du message chaîne
  ANNOUNCEMENT_HOURS     (défaut "6,12,18") — heures d'envoi de l'annonce
  CHANNEL_TZ             (défaut "Africa/Porto-Novo") — fuseau des heures chaîne
"""
import os

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from app import create_app
from app.extensions import db
from app.services.investment import payout_daily_income

app = create_app(os.environ.get("FLASK_ENV", "production"))

HOUR = int(os.environ.get("DAILY_PAYOUT_HOUR", "0"))
MINUTE = int(os.environ.get("DAILY_PAYOUT_MINUTE", "5"))

CHANNEL_HOURS = [
    int(h) for h in os.environ.get("CHANNEL_MESSAGE_HOURS", "8,12,18").split(",") if h.strip()
]
CHANNEL_TZ = os.environ.get("CHANNEL_TZ", "Africa/Porto-Novo")

ANNOUNCEMENT_HOURS = [
    int(h) for h in os.environ.get("ANNOUNCEMENT_HOURS", "6,12,18").split(",") if h.strip()
]


def run_payout():
    with app.app_context():
        try:
            paid = payout_daily_income()
            db.session.commit()
            app.logger.info("accrue-daily : %s revenu(s) quotidien(s) versé(s).", paid)
        except Exception:
            db.session.rollback()
            app.logger.exception("Erreur lors du versement quotidien.")


def run_channel_message():
    from app.services import telegram

    with app.app_context():
        try:
            telegram.send_channel_info()
            app.logger.info("telegram-channel : message envoyé à la chaîne.")
        except Exception:
            app.logger.exception("Erreur lors de l'envoi du message à la chaîne.")


def run_announcement():
    from app.services import telegram

    with app.app_context():
        try:
            telegram.send_announcement()
            app.logger.info("telegram-announcement : annonce envoyée à la chaîne.")
        except Exception:
            app.logger.exception("Erreur lors de l'envoi de l'annonce.")


if __name__ == "__main__":
    # Rattrape un éventuel jour manqué au démarrage (idempotent).
    run_payout()

    scheduler = BlockingScheduler(timezone="UTC")
    scheduler.add_job(run_payout, CronTrigger(hour=HOUR, minute=MINUTE), id="daily_payout")
    app.logger.info("Planificateur démarré : versement quotidien à %02d:%02d UTC.", HOUR, MINUTE)

    for hour in CHANNEL_HOURS:
        scheduler.add_job(
            run_channel_message,
            CronTrigger(hour=hour, minute=0, timezone=CHANNEL_TZ),
            id=f"channel_message_{hour}",
        )
        app.logger.info("Message chaîne programmé à %02d:00 (%s).", hour, CHANNEL_TZ)

    for hour in ANNOUNCEMENT_HOURS:
        scheduler.add_job(
            run_announcement,
            CronTrigger(hour=hour, minute=0, timezone=CHANNEL_TZ),
            id=f"announcement_{hour}",
        )
        app.logger.info("Annonce programmée à %02d:00 (%s).", hour, CHANNEL_TZ)

    scheduler.start()
