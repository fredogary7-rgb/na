"""Formulaires du tableau de bord (dépôt / retrait / profil)."""
from flask_wtf import FlaskForm
from wtforms import PasswordField, RadioField, SelectField, StringField
from wtforms.validators import DataRequired, EqualTo, Length, Optional

from app.utils import parse_amount


class DepositForm(FlaskForm):
    amount = StringField("Montant (FCFA)", validators=[DataRequired()])
    operator = SelectField("Opérateur Mobile Money", validators=[Optional()])
    phone_number = StringField("Numéro de téléphone", validators=[Optional()])
    otp = StringField("Code OTP (Orange Money)", validators=[Optional()])

    def clean_amount(self) -> int:
        return parse_amount(self.amount.data)


class WithdrawalForm(FlaskForm):
    amount = StringField("Montant (FCFA)", validators=[DataRequired()])
    card_id = SelectField(
        "Compte Mobile Money",
        coerce=lambda x: int(x) if x else None,
        choices=[],
        validators=[DataRequired()],
    )

    def clean_amount(self) -> int:
        return parse_amount(self.amount.data)


class CardForm(FlaskForm):
    operator = RadioField("Opérateur", validators=[DataRequired()])
    phone_number = StringField("Numéro Mobile Money", validators=[DataRequired()])
    name = StringField("Nom du titulaire (facultatif)", validators=[Optional(), Length(max=120)])


class ClaimForm(FlaskForm):
    pass


class ChangePasswordForm(FlaskForm):
    current_password = PasswordField("Mot de passe actuel", validators=[DataRequired()])
    new_password = PasswordField("Nouveau mot de passe", validators=[DataRequired(), Length(min=8, max=128)])
    confirm_password = PasswordField(
        "Confirmation du nouveau mot de passe",
        validators=[DataRequired(), EqualTo("new_password", "Les mots de passe ne correspondent pas.")],
    )

