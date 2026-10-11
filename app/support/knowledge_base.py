"""Base de connaissances NAMARA + moteur d'intentions (support client).

Les réponses sont construites à partir des données réelles du site : montants
issus de la configuration, produits approuvés en base, règles de parrainage,
parcours de dépôt/retrait réellement implémentés. Aucun montant, délai ni
rendement n'est codé en dur de façon arbitraire.

Architecture de réponse :
  Niveau 1 : détection d'intention (mots-clés normalisés + mémoire de contexte).
  Niveau 2 : base de connaissances structurée (réponses construites sur les
             données réelles).
  Niveau 3 : fournisseur d'IA configurable (optionnel), contraint par le contexte.
  Niveau 4 : transmission au service client humain.
"""
import re
import unicodedata

from flask import current_app

from app.services import settings
from app.services.investment import available_products


# ---------------------------------------------------------------------------
# Normalisation (accents, casse, ponctuation)
# ---------------------------------------------------------------------------
def normalize(text):
    """Minuscules, sans accents, ponctuation supprimée, espaces normalisés."""
    text = (text or "").lower()
    text = unicodedata.normalize("NFD", text)
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    text = re.sub(r"[^a-z0-9\s]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


# ---------------------------------------------------------------------------
# Valeurs réelles (configuration + base de données)
# ---------------------------------------------------------------------------
def _min_deposit():
    return settings.get_int("MIN_DEPOSIT", current_app.config.get("MIN_DEPOSIT", 3000))


def _min_withdrawal():
    return settings.get_int("MIN_WITHDRAWAL", current_app.config.get("MIN_WITHDRAWAL", 1500))


def _withdrawal_fee_pct():
    bps = current_app.config.get("WITHDRAWAL_FEE_BPS", 800)
    return bps / 100.0  # 800 bps = 8.00 %


def _fmt(amount):
    return f"{amount:,}".replace(",", " ")


# ---------------------------------------------------------------------------
# Réponses construites sur les données réelles
# ---------------------------------------------------------------------------
def answer_deposit_how():
    return (
        "Bien sûr ! Pour effectuer un dépôt sur NAMARA :\n\n"
        "1. Connectez-vous à votre compte NAMARA.\n"
        "2. Ouvrez la rubrique « Recharger ».\n"
        "3. Sélectionnez un opérateur Mobile Money disponible dans votre pays.\n"
        "4. Saisissez le montant et votre numéro de téléphone Mobile Money.\n"
        "5. Validez puis confirmez le paiement sur votre téléphone.\n\n"
        f"Le dépôt minimum est de {_fmt(_min_deposit())} FCFA. "
        "Votre solde n'est crédité qu'après confirmation authentifiée du prestataire.\n\n"
        "Avez-vous besoin d'aide pour un nouveau dépôt, ou un dépôt précédent n'a-t-il pas été crédité ?"
    )


def answer_deposit_not_credited():
    return (
        "Je comprends. Voici comment vérifier un dépôt non crédité :\n\n"
        "1. Dans « Recharger », consultez l'historique et le statut de votre dépôt.\n"
        "2. Vérifiez sur votre téléphone que le paiement Mobile Money a bien été confirmé.\n"
        "3. Si le statut reste « en attente », la confirmation du prestataire n'a pas encore été reçue.\n\n"
        "Transmettez-nous la référence du dépôt (ou une capture du reçu) et un conseiller vérifiera votre dossier."
    )


def answer_deposit_methods():
    return (
        "Les dépôts s'effectuent par Mobile Money, via l'opérateur disponible dans "
        "votre pays (par exemple MTN, Orange, Moov, Wave ou Airtel selon votre pays).\n\n"
        "La liste exacte des opérateurs s'affiche dans le formulaire de dépôt, "
        "après sélection de votre pays.\n\n"
        "Aucun autre moyen de paiement n'est actuellement activé."
    )


def answer_withdrawal_how():
    fee = _withdrawal_fee_pct()
    return (
        "Pour effectuer un retrait sur NAMARA :\n\n"
        "1. Enregistrez d'abord votre compte Mobile Money dans « Cartes ».\n"
        "2. Ouvrez la rubrique « Retirer ».\n"
        "3. Saisissez le montant et sélectionnez votre compte enregistré.\n"
        "4. Vérifiez le récapitulatif (frais et montant net) puis confirmez.\n\n"
        f"Le retrait minimum est de {_fmt(_min_withdrawal())} FCFA. "
        f"Des frais de {fee:.2f} % sont retenus sur le montant demandé.\n\n"
        "Le montant net est versé sur votre compte Mobile Money enregistré."
    )


def answer_withdrawal_pending():
    return (
        "Un retrait « en attente » signifie qu'il a été enregistré mais pas encore traité.\n\n"
        "Consultez son statut dans « Retirer » → historique. "
        "Le délai de traitement dépend de l'équipe et du prestataire ; nous ne pouvons pas garantir un délai précis.\n\n"
        "Si besoin, donnez-nous la référence du retrait et un conseiller vérifiera son statut."
    )


def answer_withdrawal_rejected():
    return (
        "Si un retrait est refusé, le montant réservé est normalement remboursé sur votre solde retirable.\n\n"
        "Les motifs possibles (selon les règles du site) sont : compte Mobile Money invalide, "
        "montant inférieur au minimum, ou solde retirable insuffisant.\n\n"
        "Pour connaître le motif exact, consultez l'historique ou transmettez la référence à un conseiller."
    )


def answer_products():
    products = available_products()
    if not products:
        return (
            "Aucun produit d'investissement n'est actuellement disponible. "
            "Les produits ne sont proposés qu'après validation réglementaire et configuration."
        )
    lines = ["Voici les produits actuellement disponibles :", ""]
    for p in products:
        lines.append(f"• {p.name} — durée {p.duration_days} jours")
        lines.append(f"  Montant : de {_fmt(p.min_amount)} à {_fmt(p.max_amount)} {p.currency}")
        if p.annual_rate_bps:
            lines.append(f"  Taux annuel annoncé : {p.annual_rate_bps / 100:.2f} %")
        if p.description:
            lines.append(f"  {p.description}")
        lines.append("")
    lines.append("Aucun rendement n'est garanti : les revenus sont estimés puis validés économiquement.")
    lines.append("Pour souscrire, connectez-vous et ouvrez la rubrique « Investissements ».")
    return "\n".join(lines)


def answer_referral():
    if not settings.get_bool("REFERRAL_ENABLED", False):
        return (
            "Le programme de parrainage n'est pas encore activé : il est soumis à une "
            "validation réglementaire. Revenez bientôt."
        )
    l1 = current_app.config.get("REFERRAL_LEVEL_1_BPS", 1200) / 100.0
    l2 = current_app.config.get("REFERRAL_LEVEL_2_BPS", 300) / 100.0
    l3 = current_app.config.get("REFERRAL_LEVEL_3_BPS", 200) / 100.0
    return (
        "Le parrainage vous permet de percevoir des commissions lorsque vos filleuls "
        "effectuent des opérations éligibles (par exemple un dépôt confirmé).\n\n"
        f"• Niveau 1 : {l1:.2f} %\n• Niveau 2 : {l2:.2f} %\n• Niveau 3 : {l3:.2f} %\n\n"
        "Les commissions sont validées par la conformité. Pour inviter un ami, "
        "connectez-vous et ouvrez « Parrainages » pour copier votre lien ou votre code."
    )


def answer_password():
    return (
        "Pour réinitialiser votre mot de passe, contactez le service client NAMARA :\n\n"
        "• Telegram : @narama_bot (ce canal)\n"
        "• Chat du site : page « Assistance »\n\n"
        "Un conseiller vérifiera votre identité et vous aidera à définir un nouveau mot de passe "
        "en toute sécurité. Nous ne vous demanderons jamais votre mot de passe actuel ni votre code OTP."
    )


def answer_login():
    return (
        "Si vous n'arrivez pas à vous connecter :\n\n"
        "1. Vérifiez votre numéro de téléphone et votre mot de passe.\n"
        "2. Assurez-vous que votre compte a été vérifié.\n\n"
        "Si vous avez oublié votre mot de passe ou si le problème persiste, contactez le "
        "service client (Telegram @narama_bot ou le chat du site)."
    )


def answer_verify():
    return (
        "La vérification du téléphone est nécessaire pour activer les opérations financières.\n\n"
        "Cette vérification est réalisée par notre équipe : contactez le service client via "
        "Telegram (@narama_bot) ou le chat du site, et un conseiller vous aidera à vérifier votre numéro."
    )


def answer_account_help():
    return (
        "Comment puis-je vous aider avec votre compte ?\n\n"
        "• Problème de connexion\n"
        "• Mot de passe oublié\n"
        "• Code de vérification\n"
        "• Modifier mes informations"
    )


def answer_technical():
    return (
        "Désolé pour la gêne. Essayez ces vérifications :\n\n"
        "1. Rafraîchissez la page.\n"
        "2. Utilisez un navigateur à jour (Chrome, Firefox, Safari).\n"
        "3. Vérifiez votre connexion internet.\n\n"
        "Si le problème persiste, décrivez-le précisément (page, action, message d'erreur) "
        "et un conseiller vous aidera."
    )


def answer_how_works():
    return (
        "NAMARA est une plateforme financière opérant en francs CFA (XOF / XAF).\n\n"
        "1. Créez votre compte (nom, téléphone, pays).\n"
        "2. Vérifiez votre téléphone.\n"
        "3. Effectuez un dépôt via Mobile Money.\n"
        "4. Gérez vos soldes (dépôts, bonus, revenus, commissions, solde retirable).\n\n"
        "Les produits d'investissement et le parrainage ne sont activés qu'après validation réglementaire."
    )


def answer_contact():
    return (
        "Vous pouvez joindre le service client NAMARA :\n\n"
        "• Telegram : @narama_bot (ce canal)\n"
        "• Site web : page « Assistance » (chat)\n\n"
        "Pour suivre une demande, utilisez /status suivi de sa référence."
    )


def answer_human():
    return (
        "Je vais transmettre votre demande à un conseiller NAMARA. "
        "Un membre de l'équipe vous répondra dès que possible."
    )


def answer_greeting():
    return (
        "Bonjour ! 👋 Comment puis-je vous aider ? Vous pouvez me poser une question "
        "sur les dépôts, les retraits, les produits, votre compte ou le parrainage."
    )


# ---------------------------------------------------------------------------
# Définitions d'intentions (mots-clés normalisés)
# ---------------------------------------------------------------------------
def _intent(key, category, keywords, answer, buttons=()):
    return {"key": key, "category": category, "keywords": keywords,
            "answer": answer, "buttons": list(buttons)}


INTENTS = [
    _intent("deposit_how", "deposit",
            ["effectuer un depot", "faire un depot", "comment deposer", "deposer de l argent",
             "je veux deposer", "recharger mon compte", "recharger", "verser de l argent",
             "versement", "ajouter de l argent", "depos", "depot", "minimum de depot"],
            answer_deposit_how, ["deposit_not_credited", "deposit_methods", "human"]),
    _intent("deposit_not_credited", "deposit",
            ["depot n est pas arrive", "depot pas arrive", "pas recu mon argent", "pas credite",
             "paye mais", "solde n a pas change", "solde n a pas bouge", "depot non credite",
             "mon depot", "n est pas arrive", "argent n arrive pas"],
            answer_deposit_not_credited, ["deposit_how", "human"]),
    _intent("deposit_methods", "deposit",
            ["moyens de paiement", "moyen de paiement", "comment payer", "operateur",
             "mobile money", "wave", "moov", "airtel", "orange", "mtn"],
            answer_deposit_methods, ["deposit_how", "human"]),
    _intent("withdrawal_how", "withdrawal",
            ["comment retirer", "retirer mes gains", "recuperer mon argent", "effectuer un retrait",
             "faire un retrait", "retirer", "un retrait", "minimum de retrait", "retirer de l argent"],
            answer_withdrawal_how, ["withdrawal_pending", "withdrawal_rejected", "human"]),
    _intent("withdrawal_pending", "withdrawal",
            ["retrait bloque", "bloque", "bloquer", "retrait en attente", "en attente",
             "retrait en cours", "en cours", "combien de temps", "pas encore recu",
             "toujours pas recu", "retrait retard", "retard"],
            answer_withdrawal_pending, ["withdrawal_how", "human"]),
    _intent("withdrawal_rejected", "withdrawal",
            ["retrait refuse", "refuse", "retrait rejete", "rejete", "retrait annule", "annule",
             "pourquoi refuse", "pourquoi rejete", "retrait echoue", "echoue"],
            answer_withdrawal_rejected, ["withdrawal_how", "human"]),
    _intent("products", "products",
            ["quels produits", "vos produits", "produits proposez", "produits propose",
             "comment fonctionne un produit", "produit", "investissement", "souscrire",
             "duree d un produit", "montant minimum"],
            answer_products, ["referral_how", "human"]),
    _intent("referral_how", "referral",
            ["parrainage", "parrainer", "lien de parrainage", "inviter un ami", "filleul",
             "commission", "code de parrainage"],
            answer_referral, ["products", "human"]),
    _intent("account_password", "account",
            ["oublie mon mot de passe", "mot de passe oublie", "reinitialiser mot de passe",
             "nouveau mot de passe", "mot de passe"],
            answer_password, ["account_login", "human"]),
    _intent("account_login", "account",
            ["n arrive pas a me connecter", "connexion", "me connecter",
             "je ne peux pas me connecter", "login", "compte bloque"],
            answer_login, ["account_password", "human"]),
    _intent("account_verify", "account",
            ["code de verification", "verifier mon compte", "ne recois pas mon code",
             "ne recois pas le code", "code otp", "verification du telephone"],
            answer_verify, ["account_login", "human"]),
    _intent("account_help", "account",
            ["probleme de compte", "mon compte", "modifier mes informations", "compte"],
            answer_account_help, ["account_login", "account_password", "account_verify", "human"]),
    _intent("technical", "technical",
            ["probleme technique", "bug", "erreur", "ne fonctionne pas", "marche pas",
             "site plante", "application plante"],
            answer_technical, ["human"]),
    _intent("how_works", "general",
            ["comment fonctionne namara", "comment ca marche", "comment marche", "c est quoi namara",
             "quest ce que namara", "presentation"],
            answer_how_works, ["deposit_how", "products", "human"]),
    _intent("contact", "general",
            ["contacter le support", "contacter un conseiller", "contacter namara",
             "joindre le support", "signaler un probleme", "ou contacter"],
            answer_contact, ["human"]),
    _intent("human", "human",
            ["parler a un conseiller", "parler a un humain", "un conseiller", "agent",
             "assistance humaine", "etre humain"],
            answer_human, []),
    _intent("greeting", "general",
            ["bonjour", "bonsoir", "salut", "hello", "bonne journee", "coucou",
             "bonjour j ai une question"],
            answer_greeting, ["deposit_how", "withdrawal_how", "products", "human"]),
]

INTENTS_BY_KEY = {i["key"]: i for i in INTENTS}




BUTTON_LABELS = {
    "deposit_how": "Effectuer un dépôt",
    "deposit_not_credited": "Dépôt non crédité",
    "deposit_methods": "Voir les moyens de paiement",
    "withdrawal_how": "Effectuer un retrait",
    "withdrawal_pending": "Retrait en attente",
    "withdrawal_rejected": "Retrait refusé",
    "products": "Voir les produits",
    "referral_how": "Parrainage",
    "account_password": "Mot de passe oublié",
    "account_login": "Problème de connexion",
    "account_verify": "Code de vérification",
    "account_help": "Problème de compte",
    "technical": "Problème technique",
    "how_works": "Comment ça marche",
    "contact": "Nous contacter",
    "human": "Parler à un conseiller",
}

CATEGORY_TO_INTENT = {
    "account": "account_help",
    "deposit": "deposit_how",
    "withdrawal": "withdrawal_how",
    "products": "products",
    "referral": "referral_how",
    "technical": "technical",
    "human": "human",
}

FOLLOWUPS = {
    "deposit_how": {
        "deposit_not_credited": ["arrive pas", "pas arrive", "pas recu", "pas credite",
                                 "paye mais", "solde n a pas", "ne recois pas", "n arrive pas"],
        "deposit_methods": ["moyen", "paiement", "operateur", "mobile money", "comment payer"],
    },
    "withdrawal_how": {
        "withdrawal_pending": ["en attente", "bloque", "combien de temps", "pas recu", "retard"],
        "withdrawal_rejected": ["refuse", "rejete", "annule", "pourquoi"],
    },
    "products": {
        "products": ["combien", "minimum", "duree", "rendement", "taux", "souscrire"],
    },
}


# ---------------------------------------------------------------------------
# Moteur de résolution
# ---------------------------------------------------------------------------
def _score_intent(normalized, intent):
    score = 0
    for kw in intent["keywords"]:
        if kw in normalized:
            score += 3 if " " in kw else (2 if len(kw) > 6 else 1)
    return score


def _match(normalized):
    best, best_score = None, 0
    for intent in INTENTS:
        s = _score_intent(normalized, intent)
        if s > best_score:
            best, best_score = intent["key"], s
    return best if best_score > 0 else None


def _followup(normalized, context):
    mapping = FOLLOWUPS.get(context)
    if not mapping:
        return None
    for target, keywords in mapping.items():
        for kw in keywords:
            if kw in normalized:
                return target
    return None


def build_keyboard(keys):
    if not keys:
        return None
    buttons = [{"text": BUTTON_LABELS.get(k, k), "callback_data": "intent:" + k} for k in keys]
    return {"inline_keyboard": [buttons]}


def build_context():
    lines = [
        "NAMARA est une plateforme financière opérant en francs CFA (XOF / XAF).",
        f"Dépôt minimum : {_fmt(_min_deposit())} FCFA.",
        f"Retrait minimum : {_fmt(_min_withdrawal())} FCFA.",
        f"Frais de retrait : {_withdrawal_fee_pct():.2f} % du montant demandé.",
        "Les dépôts se font par Mobile Money (opérateur selon le pays) et ne sont "
        "crédités qu'après confirmation authentifiée du prestataire.",
        "Les retraits sont versés sur le compte Mobile Money enregistré par l'utilisateur.",
    ]
    products = available_products()
    if products:
        for p in products:
            lines.append(
                f"Produit {p.name} : durée {p.duration_days} jours, "
                f"{p.min_amount}-{p.max_amount} {p.currency}, "
                f"taux annuel annoncé {p.annual_rate_bps / 100:.2f} %."
            )
    else:
        lines.append("Aucun produit d'investissement approuvé actuellement.")
    if settings.get_bool("REFERRAL_ENABLED", False):
        lines.append("Parrainage activé (commissions de niveau 1/2/3 selon la configuration).")
    else:
        lines.append("Parrainage désactivé (validation réglementaire en attente).")
    return "\n".join(lines)


def _fallback(text):
    from app.services import ai

    try:
        answer = ai.ask(text, build_context())
        if answer:
            return {"reply": answer, "intent": None, "category": None,
                    "buttons": ["human"], "handoff": False}
    except ai.AIUnavailable:
        pass
    return {
        "reply": (
            "Je ne dispose pas d'une réponse suffisamment fiable pour cette question. "
            "Je peux transmettre votre demande à un conseiller NAMARA."
        ),
        "intent": None,
        "category": None,
        "buttons": ["human"],
        "handoff": True,
    }


def resolve(text, context=None):
    """Résout un message libre en une réponse structurée.

    Retourne un dict : {reply, intent, category, buttons, handoff}.
    """
    normalized = normalize(text)
    key = _match(normalized)
    if key is None and context:
        key = _followup(normalized, context)
    if key is None:
        return _fallback(text)

    intent = INTENTS_BY_KEY[key]
    return {
        "reply": intent["answer"](),
        "intent": key,
        "category": intent["category"],
        "buttons": intent.get("buttons", []),
        "handoff": False,
    }


def resolve_intent(key):
    """Résout une intention à partir de sa clé (clic sur un bouton).

    Retourne le même format que resolve(), ou None si la clé est inconnue.
    """
    intent = INTENTS_BY_KEY.get(key)
    if intent is None:
        return None
    return {
        "reply": intent["answer"](),
        "intent": key,
        "category": intent["category"],
        "buttons": intent.get("buttons", []),
        "handoff": False,
    }


def button_payload(keys):
    """Convertit une liste de clés en objets {key, label} pour le frontend."""
    return [{"key": k, "label": BUTTON_LABELS.get(k, k)} for k in keys]


# Menu de démarrage du chat (identique aux catégories Telegram).
START_ACTIONS = ["deposit_how", "withdrawal_how", "products", "referral_how", "account_help", "human"]

