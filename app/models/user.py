"""Modèle utilisateur."""
import secrets
import string

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from app.extensions import db
from app.models.base import TimestampMixin, utcnow

_ALPHABET = string.ascii_uppercase + string.digits


def generate_referral_code(exclude=None):
    """Génère un code de parrainage unique (8 caractères)."""
    existing = exclude or set()
    while True:
        code = "".join(secrets.choice(_ALPHABET) for _ in range(8))
        if code not in existing:
            return code


def new_unique_referral_code():
    """Génère un code de parrainage garanti unique en base."""
    existing = {row[0] for row in db.session.query(User.referral_code).all()}
    return generate_referral_code(exclude=existing)



class User(UserMixin, TimestampMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(120), nullable=False)
    phone_number = db.Column(db.String(20), unique=True, index=True, nullable=False)  # E.164
    country = db.Column(db.String(60), nullable=False)
    currency = db.Column(db.String(3), nullable=False)  # XOF / XAF
    password_hash = db.Column(db.String(255), nullable=False)
    is_phone_verified = db.Column(db.Boolean, default=False, nullable=False)
    role = db.Column(db.String(20), default="user", nullable=False)  # user / admin
    status = db.Column(db.String(20), default="active", nullable=False)  # active / suspended
    referral_code = db.Column(db.String(8), unique=True, index=True, nullable=False)
    referrer_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    otp_secret = db.Column(db.String(6), nullable=True)
    otp_expires_at = db.Column(db.DateTime, nullable=True)

    wallets = db.relationship("Wallet", backref="user", lazy="dynamic")

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"

    def is_active(self) -> bool:
        """Flask-Login : un compte suspendu ne peut pas rester connecté."""
        return self.status == "active"

    def __repr__(self) -> str:
        return f"<User {self.id} {self.phone_number}>"
