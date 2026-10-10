"""Support client : conversations et messages centralisés (Telegram + Web).

Les conversations Telegram et web partagent la même base, afin que l'équipe
d'assistance puisse tout traiter depuis une seule interface.
"""
import secrets

from app.extensions import db
from app.models.base import TimestampMixin, utcnow


def generate_public_reference() -> str:
    """Référence publique unique et non prévisible."""
    while True:
        ref = "SC-" + secrets.token_hex(8).upper()
        if SupportConversation.query.filter_by(public_reference=ref).first() is None:
            return ref


class SupportConversation(TimestampMixin, db.Model):
    __tablename__ = "support_conversations"

    id = db.Column(db.Integer, primary_key=True)
    public_reference = db.Column(db.String(32), unique=True, index=True, nullable=False)
    channel = db.Column(db.String(10), nullable=False, index=True)  # telegram / web
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)
    telegram_chat_id = db.Column(db.String(40), nullable=True, index=True)
    visitor_session_hash = db.Column(db.String(64), nullable=True, index=True)
    subject = db.Column(db.String(120), nullable=True)
    category = db.Column(db.String(40), nullable=True, index=True)
    status = db.Column(db.String(20), default="open", nullable=False, index=True)  # open/pending/answered/closed
    assigned_admin_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    last_message_at = db.Column(db.DateTime, nullable=True)

    messages = db.relationship(
        "SupportMessage", backref="conversation", lazy="dynamic",
        cascade="all, delete-orphan", order_by="SupportMessage.created_at",
    )

    def __repr__(self) -> str:
        return f"<SupportConversation {self.public_reference} {self.channel} {self.status}>"


class SupportMessage(TimestampMixin, db.Model):
    __tablename__ = "support_messages"

    id = db.Column(db.Integer, primary_key=True)
    conversation_id = db.Column(
        db.Integer, db.ForeignKey("support_conversations.id"), nullable=False, index=True
    )
    sender_type = db.Column(db.String(10), nullable=False)  # visitor / user / bot / admin
    message_text = db.Column(db.Text, nullable=True)
    attachment_path = db.Column(db.String(255), nullable=True)
    attachment_type = db.Column(db.String(30), nullable=True)
    is_read = db.Column(db.Boolean, default=False, nullable=False)
    internal_note = db.Column(db.Boolean, default=False, nullable=False)  # note interne
    # Déduplication des événements Telegram entrants.
    telegram_update_id = db.Column(db.String(40), unique=True, nullable=True)
    # Statut de livraison d'une réponse sortante (si envoi API requis).
    delivery_status = db.Column(db.String(20), default="none", nullable=False)

    def __repr__(self) -> str:
        return f"<SupportMessage {self.id} {self.sender_type}>"


class SupportFaq(TimestampMixin, db.Model):
    __tablename__ = "support_faqs"

    id = db.Column(db.Integer, primary_key=True)
    category = db.Column(db.String(60), nullable=False, index=True)
    question = db.Column(db.String(200), nullable=False)
    answer = db.Column(db.Text, nullable=False)
    keywords = db.Column(db.String(200), nullable=True)

    def __repr__(self) -> str:
        return f"<SupportFaq {self.question[:30]}>"
