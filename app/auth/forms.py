"""Formulaires d'authentification (validation serveur + normalisation téléphone)."""
import phonenumbers
from flask_wtf import FlaskForm
from wtforms import BooleanField, PasswordField, SelectField, StringField
from wtforms.validators import DataRequired, EqualTo, Length, ValidationError

from app.constants import COUNTRIES, COUNTRY_FLAGS


def country_choices():
    return [(name, name) for name, info in COUNTRIES.items() if info["enabled"]]


def login_country_choices():
    """Choix de pays pour la connexion (drapeau + indicatif)."""
    choices = [("", "🌍 Choisir un pays")]
    for name, info in COUNTRIES.items():
        if info["enabled"]:
            flag = COUNTRY_FLAGS.get(name, "")
            choices.append((name, f"{flag} {info['phone_code']}"))
    return choices


def normalize_phone(country: str, local_number: str) -> str:
    """Normalise un numéro local en E.164 selon le pays."""
    info = COUNTRIES.get(country)
    if info is None:
        raise ValidationError("Pays invalide.")
    raw = info["phone_code"] + str(local_number or "").strip()
    try:
        parsed = phonenumbers.parse(raw, info["code"])
    except phonenumbers.NumberParseException:
        raise ValidationError("Numéro de téléphone invalide.")
    if not phonenumbers.is_valid_number(parsed):
        raise ValidationError("Numéro de téléphone invalide.")
    return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)


class RegistrationForm(FlaskForm):
    full_name = StringField("Nom complet", validators=[DataRequired(), Length(min=3, max=120)])
    country = SelectField("Pays", choices=country_choices, validators=[DataRequired()])
    phone_number = StringField("Numéro de téléphone", validators=[DataRequired()])
    password = PasswordField("Mot de passe", validators=[DataRequired(), Length(min=8, max=128)])
    confirm_password = PasswordField(
        "Confirmation du mot de passe",
        validators=[DataRequired(), EqualTo("password", "Les mots de passe ne correspondent pas.")],
    )
    referral_code = StringField("Code de parrainage (facultatif)")
    accept_terms = BooleanField("J'accepte les conditions d'utilisation", validators=[DataRequired()])
    accept_privacy = BooleanField("J'accepte la politique de confidentialité", validators=[DataRequired()])

    def validate_phone_number(self, field):
        self.normalized_phone = normalize_phone(self.country.data, field.data)


class LoginForm(FlaskForm):
    country = SelectField("Pays", choices=login_country_choices, default="")
    phone_number = StringField("Numéro de téléphone", validators=[DataRequired()])
    password = PasswordField("Mot de passe", validators=[DataRequired()])


class ForgotPasswordForm(FlaskForm):
    phone_number = StringField("Numéro de téléphone", validators=[DataRequired()])


class ResetPasswordForm(FlaskForm):
    password = PasswordField("Nouveau mot de passe", validators=[DataRequired(), Length(min=8, max=128)])
    confirm_password = PasswordField(
        "Confirmation",
        validators=[DataRequired(), EqualTo("password", "Les mots de passe ne correspondent pas.")],
    )


class VerifyOtpForm(FlaskForm):
    otp = StringField("Code de vérification", validators=[DataRequired(), Length(min=6, max=6)])
