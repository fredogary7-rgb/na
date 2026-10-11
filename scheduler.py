"""Planificateur quotidien : verse le revenu des investissements actifs.

Usage : `python scheduler.py` (processus séparé — service Railway dédié ou cron).
Le versement est idempotent : relancer ne crédite jamais deux fois le même jour.

Heure configurable via les variables :
  DAILY_PAYOUT_HOUR   (défaut 0)  — heure UTC
  DAILY_PAYOUT_MINUTE (défaut 5)  — minute UTC
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


def run_payout():
    with app.app_context():
        try:
            paid = payout_daily_income()
            db.session.commit()
            app.logger.info("accrue-daily : %s revenu(s) quotidien(s) versé(s).", paid)
        except Exception:
            db.session.rollback()
            app.logger.exception("Erreur lors du versement quotidien.")


if __name__ == "__main__":
    # Rattrape un éventuel jour manqué au démarrage (idempotent).
    run_payout()

    scheduler = BlockingScheduler(timezone="UTC")
    scheduler.add_job(run_payout, CronTrigger(hour=HOUR, minute=MINUTE), id="daily_payout")
    app.logger.info("Planificateur démarré : versement quotidien à %02d:%02d UTC.", HOUR, MINUTE)
    scheduler.start()
