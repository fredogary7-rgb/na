"""Service centralisé du support client (conversations + messages + FAQ)."""
from flask import current_app

from app.extensions import db
from app.models import SupportConversation, SupportFaq, SupportMessage
from app.models.base import utcnow
from app.models.support import generate_public_reference

SUPPORT_CATEGORIES = [
    ("account", "Problème de compte"),
    ("deposit", "Dépôt"),
    ("withdrawal", "Retrait"),
    ("products", "Produits"),
    ("referral", "Parrainage"),
    ("technical", "Problème technique"),
    ("human", "Parler à un conseiller"),
]

CATEGORY_LABELS = dict(SUPPORT_CATEGORIES)


def category_label(key):
    return CATEGORY_LABELS.get(key, key or "Général")


def _new_conversation(**kwargs):
    conv = SupportConversation(public_reference=generate_public_reference(), **kwargs)
    db.session.add(conv)
    db.session.flush()
    return conv


def get_or_create_telegram_conversation(telegram_chat_id, user_id=None, category=None, subject=None):
    conv = (
        SupportConversation.query.filter_by(channel="telegram", telegram_chat_id=str(telegram_chat_id))
        .order_by(SupportConversation.created_at.desc())
        .first()
    )
    if conv is None or conv.status == "closed":
        conv = _new_conversation(
            channel="telegram",
            telegram_chat_id=str(telegram_chat_id),
            user_id=user_id,
            category=category,
            subject=subject,
            status="open",
        )
    return conv


def get_or_create_web_conversation(visitor_session_hash, user_id=None, category=None, subject=None):
    conv = (
        SupportConversation.query.filter_by(channel="web", visitor_session_hash=visitor_session_hash)
        .order_by(SupportConversation.created_at.desc())
        .first()
    )
    if conv is None or conv.status == "closed":
        conv = _new_conversation(
            channel="web",
            visitor_session_hash=visitor_session_hash,
            user_id=user_id,
            category=category,
            subject=subject,
            status="open",
        )
    elif user_id is not None and conv.user_id is None:
        conv.user_id = user_id
    return conv


def get_web_conversation(visitor_session_hash):
    return (
        SupportConversation.query.filter_by(channel="web", visitor_session_hash=visitor_session_hash)
        .order_by(SupportConversation.created_at.desc())
        .first()
    )


def add_message(conversation, sender_type, text=None, attachment_path=None, attachment_type=None,
                internal_note=False, telegram_update_id=None):
    if text and len(text) > current_app.config.get("SUPPORT_MESSAGE_MAX_LENGTH", 2000):
        text = text[: current_app.config.get("SUPPORT_MESSAGE_MAX_LENGTH", 2000)]
    msg = SupportMessage(
        conversation_id=conversation.id,
        sender_type=sender_type,
        message_text=text,
        attachment_path=attachment_path,
        attachment_type=attachment_type,
        internal_note=internal_note,
        telegram_update_id=telegram_update_id,
    )
    db.session.add(msg)
    conversation.last_message_at = utcnow()
    db.session.flush()
    return msg


def mark_read(conversation, sender_types=("visitor", "user")):
    SupportMessage.query.filter(
        SupportMessage.conversation_id == conversation.id,
        SupportMessage.sender_type.in_(sender_types),
    ).update({"is_read": True}, synchronize_session=False)



def find_faq(text):
    """Recherche une réponse FAQ fiable par mots-clés (aucune invention)."""
    if not text:
        return None
    lowered = text.lower()
    best, best_score = None, 0
    for faq in SupportFaq.query.all():
        score = 0
        for kw in (faq.keywords or "").lower().split(","):
            kw = kw.strip()
            if kw and kw in lowered:
                score += 1
        if faq.question.lower() in lowered:
            score += 3
        if score > best_score:
            best, best_score = faq, score
    return best if best_score > 0 else None


def unavailable_reply():
    return (
        "Je ne dispose pas d'une réponse suffisamment fiable pour cette question. "
        "Je peux transmettre votre demande au service client NAMARA."
    )


def seed_default_faq():
    """Insère les FAQ par défaut si la table est vide."""
    if SupportFaq.query.count() > 0:
        return
    entries = [
        ("inscription", "Comment créer un compte ?",
         "Rendez-vous sur la page d'inscription du site NAMARA, renseignez votre nom, votre numéro de téléphone et votre pays, puis définissez un mot de passe.",
         "inscription,compte,créer,creer,s'inscrire,inscrire"),
        ("securite", "Comment sécuriser mon compte ?",
         "Ne partagez jamais votre mot de passe, votre code OTP ou votre code PIN. Utilisez un mot de passe fort et vérifiez votre téléphone.",
         "sécurité,securite,mot de passe,otp,pin"),
        ("depot", "Comment effectuer un dépôt ?",
         "Allez dans « Recharger » sur votre tableau de bord, choisissez votre opérateur Mobile Money et suivez les instructions.",
         "dépôt,depot,recharger,verser,fonds"),
        ("retrait", "Comment retirer mes fonds ?",
         "Allez dans « Retrait », sélectionnez votre compte Mobile Money enregistré, saisissez le montant (minimum 1 500 FCFA, frais de 8 %) puis validez.",
         "retrait,retirer,enlever,argent"),
        ("parrainage", "Comment fonctionne le parrainage ?",
         "Partagez votre code de parrainage. Les commissions sont soumises aux conditions du programme, validées par la conformité.",
         "parrainage,parrainer,code,filleul,commission"),
        ("bonus", "Mon bonus est-il retirable ?",
         "Le bonus de bienvenue est promotionnel et non retirable. Il est distinct de votre solde réel.",
         "bonus,bienvenue,promotion"),
        ("historique", "Où voir mes transactions ?",
         "Consultez l'onglet « Historique » de votre tableau de bord pour voir vos opérations.",
         "historique,transactions,opérations,operations"),
        ("technique", "Le site ne fonctionne pas, que faire ?",
         "Essayez de rafraîchir la page ou de changer de navigateur. Si le problème persiste, contactez un conseiller.",
         "technique,probleme,problème,bug,erreur"),
    ]
    for category, question, answer, keywords in entries:
        db.session.add(SupportFaq(category=category, question=question, answer=answer, keywords=keywords))
    db.session.flush()
