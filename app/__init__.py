"""Application factory de NAMARA."""
import logging
import os

import click
from flask import Flask, render_template
from werkzeug.middleware.proxy_fix import ProxyFix

from app.extensions import csrf, db, limiter, login_manager, migrate
from config import config_by_name


def create_app(config_name: str = None) -> Flask:
    config_name = config_name or os.environ.get("FLASK_ENV", "development")
    app = Flask(__name__)
    app.config.from_object(config_by_name[config_name])

    # Derrière le proxy Railway (HTTPS en externe, HTTP en interne) : faire
    # confiance aux en-têtes X-Forwarded-* pour générer des URL absolues en
    # https:// (liens de parrainage et de réinitialisation de mot de passe).
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1)

    register_extensions(app)
    register_blueprints(app)
    register_error_handlers(app)
    register_template_helpers(app)
    register_cli(app)
    configure_logging(app)

    return app


def register_extensions(app):
    db.init_app(app)
    migrate.init_app(app, db)
    csrf.init_app(app)
    limiter.init_app(app)
    login_manager.init_app(app)

    from app.models import User

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))


def register_blueprints(app):
    from app.admin.routes import admin_bp
    from app.auth.routes import auth_bp
    from app.dashboard.routes import dashboard_bp
    from app.investments.routes import investments_bp
    from app.payments.routes import payments_bp
    from app.public.routes import public_bp
    from app.referrals.routes import referrals_bp
    from app.support.routes import support_bp

    app.register_blueprint(public_bp)
    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(dashboard_bp, url_prefix="/dashboard")
    app.register_blueprint(payments_bp, url_prefix="/payments")
    app.register_blueprint(referrals_bp, url_prefix="/referrals")
    app.register_blueprint(investments_bp, url_prefix="/investments")
    app.register_blueprint(admin_bp, url_prefix="/admin")
    app.register_blueprint(support_bp, url_prefix="/support")


def register_error_handlers(app):
    @app.errorhandler(403)
    def forbidden(e):
        return render_template("errors/403.html"), 403

    @app.errorhandler(404)
    def not_found(e):
        return render_template("errors/404.html"), 404

    @app.errorhandler(500)
    def server_error(e):
        db.session.rollback()
        app.logger.exception("Erreur serveur interne")
        return render_template("errors/500.html"), 500


def register_template_helpers(app):
    from app.utils import format_amount, operator_logo

    def badge_class(status):
        mapping = {
            "successful": "success",
            "pending": "pending",
            "processing": "processing",
            "approved": "approved",
            "failed": "failed",
            "rejected": "rejected",
            "cancelled": "cancelled",
        }
        return mapping.get(status, "cancelled")

    def format_sim(amount, currency="XOF"):
        """Formate un montant simulé (arrondi uniquement à l'affichage)."""
        return format_amount(int(round(amount)), currency)

    app.jinja_env.globals["format_amount"] = format_amount
    app.jinja_env.globals["format_sim"] = format_sim
    app.jinja_env.globals["badge_class"] = badge_class
    app.jinja_env.globals["operator_logo"] = operator_logo
    app.jinja_env.globals["APP_NAME"] = "NAMARA"
    app.jinja_env.globals["APP_SLOGAN"] = "Votre capital, une vision d'avenir."

    @app.context_processor
    def inject_unread_notifications():
        from flask_login import current_user

        if current_user.is_authenticated:
            from app.models import Notification

            count = Notification.query.filter_by(
                user_id=current_user.id, is_read=False
            ).count()
            return {"unread_notifications": count}
        return {"unread_notifications": 0}


def register_cli(app):
    from app.constants import WALLET_TYPES

    @app.cli.command("create-admin")
    @click.option("--phone", prompt="Numéro de téléphone (E.164, ex: +22997000000)")
    @click.option("--name", prompt="Nom complet")
    @click.option("--country", prompt="Pays", default="Benin", show_default=True)
    @click.option("--password", prompt=True, hide_input=True, confirmation_prompt=True)
    def create_admin(phone, name, country, password):
        """Crée un compte administrateur (aucun mot de passe stocké en clair)."""
        from app.models import User
        from app.models.user import new_unique_referral_code
        from app.services.finance import ensure_wallets
        from app.utils import currency_for_country

        if User.query.filter_by(phone_number=phone).first():
            click.echo("Ce numéro de téléphone existe déjà.")
            return
        user = User(
            full_name=name,
            phone_number=phone,
            country=country,
            currency=currency_for_country(country),
            role="admin",
            is_phone_verified=True,
            referral_code=new_unique_referral_code(),
        )
        user.set_password(password)
        db.session.add(user)
        db.session.flush()
        ensure_wallets(user.id, user.currency, WALLET_TYPES)
        db.session.commit()
        click.echo(f"Administrateur créé : {phone}")

    @app.cli.command("telegram-set-webhook")
    def telegram_set_webhook():
        """Configure le webhook Telegram (nécessite TELEGRAM_WEBHOOK_URL)."""
        from app.services import telegram

        with app.app_context():
            url = app.config.get("TELEGRAM_WEBHOOK_URL")
            secret = app.config.get("TELEGRAM_WEBHOOK_SECRET")
            if not url:
                click.echo("TELEGRAM_WEBHOOK_URL non configuré.")
                return
            try:
                telegram.set_webhook(url, secret_token=secret)
                click.echo("Webhook Telegram configuré.")
            except Exception as exc:  # noqa: BLE001
                click.echo(f"Erreur : {exc}")

    @app.cli.command("telegram-poll")
    def telegram_poll():
        """Lance le polling Telegram (développement local uniquement)."""
        import time

        import requests

        from app.support import telegram_handler

        with app.app_context():
            token = app.config.get("TELEGRAM_BOT_TOKEN")
            if not token:
                click.echo("TELEGRAM_BOT_TOKEN non configuré.")
                return
            click.echo("Polling Telegram démarré (Ctrl+C pour arrêter).")
            offset = 0
            while True:
                try:
                    resp = requests.get(
                        f"https://api.telegram.org/bot{token}/getUpdates",
                        params={"timeout": 30, "offset": offset},
                        timeout=40,
                    ).json()
                    if resp.get("ok"):
                        for update in resp.get("result", []):
                            offset = update["update_id"] + 1
                            telegram_handler.handle_update(update)
                            db.session.commit()
                except requests.RequestException as exc:
                    click.echo(f"Erreur réseau : {exc}")
                    time.sleep(5)

    @app.cli.command("seed-faq")
    def seed_faq():
        """Insère les FAQ de support par défaut (si la table est vide)."""
        from app.services.support import seed_default_faq

        with app.app_context():
            seed_default_faq()
            db.session.commit()
            click.echo("FAQ de support insérées.")

    @app.cli.command("seed-products")
    def seed_products():
        """Initialise le catalogue NAMARA (idempotent — aucun doublon)."""
        from app.services.investment import seed_catalog_products

        with app.app_context():
            created = seed_catalog_products()
            db.session.commit()
            click.echo(f"Catalogue NAMARA initialisé ({created} produit(s) créé(s)).")

    @app.cli.command("accrue-daily")
    def accrue_daily():
        """Verse le revenu quotidien des investissements actifs (idempotent)."""
        from app.services.investment import payout_daily_income

        with app.app_context():
            paid = payout_daily_income()
            db.session.commit()
            click.echo(f"{paid} revenu(s) quotidien(s) versé(s).")


def configure_logging(app):
    handler = logging.StreamHandler()
    handler.setFormatter(
        logging.Formatter("[%(asctime)s] %(levelname)s in %(module)s: %(message)s")
    )
    app.logger.addHandler(handler)
    app.logger.setLevel(logging.INFO)
