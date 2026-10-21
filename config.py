"""Configuration centralisée de NAMARA.

Les montants financiers sont toujours stockés sous forme d'entiers dans la
plus petite unité monétaire applicable. Pour le FCFA (XOF / XAF), l'unité est
le franc CFA lui-même (0 décimale) : 3000 == 3 000 FCFA.
"""
import os
from datetime import timedelta

from dotenv import load_dotenv

load_dotenv()  # charge .env avant toute lecture des variables d'environnement

BASE_DIR = os.path.abspath(os.path.dirname(__file__))


def _as_bool(value: str) -> bool:
    return str(value).strip().lower() in ("1", "true", "yes", "on")


class Config:
    """Configuration de base partagée par tous les environnements."""

    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-only-secret-change-me")
    FLASK_ENV = os.environ.get("FLASK_ENV", "development")

    # Base de données : PostgreSQL en production, SQLite pour le dev/test.
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", "sqlite:///" + os.path.join(BASE_DIR, "namara_dev.db")
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    # Connexions PostgreSQL : pré-vérification + recyclage pour éviter les
    # connexions coupées par Neon/proxy après une période d'inactivité.
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_recycle": 280,
    }

    # Sessions / cookies sécurisés
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = os.environ.get("FLASK_ENV") == "production"
    PERMANENT_SESSION_LIFETIME = timedelta(hours=12)
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SAMESITE = "Lax"
    REMEMBER_COOKIE_SECURE = os.environ.get("FLASK_ENV") == "production"

    # Limitation des tentatives abusives
    RATELIMIT_ENABLED = True
    RATELIMIT_STORAGE_URI = "memory://"

    # Paramètres financiers par défaut (entiers, en FCFA).
    MIN_DEPOSIT = int(os.environ.get("MIN_DEPOSIT", "3000"))
    MIN_WITHDRAWAL = int(os.environ.get("MIN_WITHDRAWAL", "1500"))
    WITHDRAWAL_FEE_BPS = int(os.environ.get("WITHDRAWAL_FEE_BPS", "800"))  # 8,00 %
    BONUS_INSCRIPTION = int(os.environ.get("BONUS_INSCRIPTION", "0"))
    BONUS_ENABLED = _as_bool(os.environ.get("BONUS_ENABLED", "false"))

    # Devises supportées et nombre de décimales (0 pour XOF/XAF).
    CURRENCIES = {"XOF": 0, "XAF": 0}

    # Parrainage : désactivé par défaut tant que la conformité n'est pas validée.
    REFERRAL_ENABLED = _as_bool(os.environ.get("REFERRAL_ENABLED", "false"))
    REFERRAL_LEVEL_1_BPS = 1200  # 12,00 %
    REFERRAL_LEVEL_2_BPS = 300   # 3,00 %
    REFERRAL_LEVEL_3_BPS = 200   # 2,00 %
    REFERRAL_MAX_LEVEL = 3

    # Investissements : désactivés tant qu'aucun produit n'est approuvé.
    INVESTMENTS_ENABLED = _as_bool(os.environ.get("INVESTMENTS_ENABLED", "false"))

    # Catalogue produits — simulation hypothétique (NON validée).
    # Le taux quotidien est purement indicatif et ne constitue pas un rendement.
    SIMULATION_DAILY_RATE = float(os.environ.get("SIMULATION_DAILY_RATE", "0.08"))
    SIMULATION_SHOW_AMOUNTS = _as_bool(os.environ.get("SIMULATION_SHOW_AMOUNTS", "true"))
    # Souscriptions réelles : bloquées tant que le modèle économique n'est pas validé.
    SUBSCRIPTIONS_ENABLED = _as_bool(os.environ.get("SUBSCRIPTIONS_ENABLED", "false"))

    # Paiements : "mock" (simulation explicite) ou "soleaspay".
    PAYMENT_MODE = os.environ.get("PAYMENT_MODE", "mock")

    # SoleasPay — à adapter à la documentation officielle (ajout ultérieur).
    SOLEASPAY_API_KEY = os.environ.get("SOLEASPAY_API_KEY")
    SOLEASPAY_API_SECRET = os.environ.get("SOLEASPAY_API_SECRET")
    SOLEASPAY_BASE_URL = os.environ.get("SOLEASPAY_BASE_URL", "https://soleaspay.com")
    SOLEASPAY_WEBHOOK_SECRET = os.environ.get("SOLEASPAY_WEBHOOK_SECRET")
    # Secrets webhook supplémentaires acceptés (séparés par des virgules), pour
    # assurer la transition lors d'une rotation de la clé sans casser les paiements.
    SOLEASPAY_EXTRA_SECRETS = os.environ.get("SOLEASPAY_EXTRA_SECRETS", "")
    # Second site qui doit recevoir les mêmes webhooks SoleasPay (ex. transafrik.org).
    TRANSFRIK_WEBHOOK_URL = os.environ.get("TRANSFRIK_WEBHOOK_URL", "https://transafrik.org/webhook/soleaspay")

    # DrimPay v2 — https://drimpay.com/fr/docs/payin
    DRIMPAY_API_KEY = os.environ.get("DRIMPAY_API_KEY")
    DRIMPAY_WEBHOOK_SECRET = os.environ.get("DRIMPAY_WEBHOOK_SECRET")
    DRIMPAY_BASE_URL = os.environ.get("DRIMPAY_BASE_URL", "https://drimpay.com/api/v2")
    DRIMPAY_SANDBOX_BASE_URL = os.environ.get("DRIMPAY_SANDBOX_BASE_URL", "https://drimpay.com/sandbox-api/v2")
    # URL de notification DrimPay (renseignée à l'initiation du pay-in).
    DRIMPAY_WEBHOOK_URL = os.environ.get("DRIMPAY_WEBHOOK_URL", "https://namara.win/payments/webhook/drimpay")

    # RobotPay / WestPay (Niger) — https://westpay.cfd
    ROBOTPAY_API_KEY = os.environ.get("ROBOTPAY_API_KEY")
    ROBOTPAY_WEBHOOK_SECRET = os.environ.get("ROBOTPAY_WEBHOOK_SECRET")
    ROBOTPAY_MERCHANT_SLUG = os.environ.get("ROBOTPAY_MERCHANT_SLUG")
    ROBOTPAY_BASE_URL = os.environ.get("ROBOTPAY_BASE_URL", "https://westpay.cfd")
    ROBOTPAY_CHECKOUT_URL = os.environ.get("ROBOTPAY_CHECKOUT_URL", "https://checkout1.westpay.cfd/pay")
    ROBOTPAY_RETURN_URL = os.environ.get("ROBOTPAY_RETURN_URL", "https://namara.win/payments/robotpay/return")

    # Support client (Telegram + chat web)
    TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
    TELEGRAM_WEBHOOK_SECRET = os.environ.get("TELEGRAM_WEBHOOK_SECRET")
    TELEGRAM_WEBHOOK_URL = os.environ.get("TELEGRAM_WEBHOOK_URL")
    TELEGRAM_ADMIN_CHAT_ID = os.environ.get("TELEGRAM_ADMIN_CHAT_ID")
    TELEGRAM_CHANNEL_ID = os.environ.get("TELEGRAM_CHANNEL_ID", "@namara_win")
    TELEGRAM_MODE = os.environ.get("TELEGRAM_MODE", "off")  # off / webhook / polling
    SUPPORT_ATTACHMENT_MAX_BYTES = int(os.environ.get("SUPPORT_ATTACHMENT_MAX_BYTES", "2000000"))
    SUPPORT_MESSAGE_MAX_LENGTH = int(os.environ.get("SUPPORT_MESSAGE_MAX_LENGTH", "2000"))

    # Fournisseur d'IA optionnel (niveau 3 du support). Désactivé par défaut.
    # L'IA ne reçoit que le contexte factuel du site et n'exécute aucune opération.
    AI_API_KEY = os.environ.get("AI_API_KEY")
    AI_BASE_URL = os.environ.get("AI_BASE_URL", "https://api.openai.com/v1")
    AI_MODEL = os.environ.get("AI_MODEL", "gpt-4o-mini")
    AI_TIMEOUT = int(os.environ.get("AI_TIMEOUT", "10"))


class DevelopmentConfig(Config):
    DEBUG = True


class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "TEST_DATABASE_URL", "sqlite:///" + os.path.join(BASE_DIR, "namara_test.db")
    )
    WTF_CSRF_ENABLED = False
    RATELIMIT_ENABLED = False
    BONUS_ENABLED = False
    BONUS_INSCRIPTION = 0
    REFERRAL_ENABLED = True
    # Les tests utilisent toujours le fournisseur simulé (mock), quel que soit
    # le PAYMENT_MODE défini dans le .env local.
    PAYMENT_MODE = "mock"
    # Les tests d'investissement ont besoin de souscriptions actives.
    SUBSCRIPTIONS_ENABLED = True
    # Pas de transfert de webhook vers un site tiers pendant les tests.
    TRANSFRIK_WEBHOOK_URL = None


class ProductionConfig(Config):
    DEBUG = False
    SESSION_COOKIE_SECURE = True
    REMEMBER_COOKIE_SECURE = True


config_by_name = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
}
