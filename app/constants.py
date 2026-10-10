"""Constantes métier de NAMARA : pays, devises, opérateurs."""

# Pays pris en charge et devise par défaut.
# La RDC n'est pas assimilée au franc CFA : sa devise (CDF) nécessite une
# configuration indépendante et aucune transaction n'y est autorisée tant
# que la devise et le prestataire ne sont pas configurés.
COUNTRIES = {
    "Benin": {"code": "BJ", "phone_code": "+229", "currency": "XOF", "enabled": True},
    "Cote d'Ivoire": {"code": "CI", "phone_code": "+225", "currency": "XOF", "enabled": True},
    "Mali": {"code": "ML", "phone_code": "+223", "currency": "XOF", "enabled": True},
    "Senegal": {"code": "SN", "phone_code": "+221", "currency": "XOF", "enabled": True},
    "Burkina Faso": {"code": "BF", "phone_code": "+226", "currency": "XOF", "enabled": True},
    "Niger": {"code": "NE", "phone_code": "+227", "currency": "XOF", "enabled": True},
    "Togo": {"code": "TG", "phone_code": "+228", "currency": "XOF", "enabled": True},
    "Cameroun": {"code": "CM", "phone_code": "+237", "currency": "XAF", "enabled": True},
    "Gabon": {"code": "GA", "phone_code": "+241", "currency": "XAF", "enabled": True},
    "Republique du Congo": {"code": "CG", "phone_code": "+242", "currency": "XAF", "enabled": True},
    "RD Congo": {"code": "CD", "phone_code": "+243", "currency": "CDF", "enabled": False},
}

# Types de portefeuilles (soldes séparés, jamais additionnés en une somme retirable).
WALLET_DEPOSIT = "deposit"          # Capital déposé — non retirable directement.
WALLET_BONUS = "bonus"              # Bonus promotionnel — non retirable.
WALLET_EARNINGS = "earnings"        # Revenus réalisés et validés.
WALLET_REFERRAL = "referral"        # Commissions de parrainage confirmées.
WALLET_WITHDRAWABLE = "withdrawable"  # Solde disponible pour retrait.

WALLET_TYPES = [
    WALLET_DEPOSIT,
    WALLET_BONUS,
    WALLET_EARNINGS,
    WALLET_REFERRAL,
    WALLET_WITHDRAWABLE,
]

# Opérateurs Mobile Money par pays.
OPERATORS = {
    "Benin": ["MTN", "Moov"],
    "Cote d'Ivoire": ["Orange", "MTN", "Moov", "Wave"],
    "Mali": ["Orange", "Moov"],
    "Senegal": ["Orange", "Wave"],
    "Burkina Faso": ["Orange", "Moov"],
    "Niger": ["Airtel", "Moov"],
    "Togo": ["Moov", "MTN"],
    "Cameroun": ["MTN", "Orange"],
    "Gabon": ["Airtel", "Moov"],
    "Republique du Congo": ["MTN", "Airtel"],
    "RD Congo": ["Airtel", "Orange", "Mov"],
}

# Tous les opérateurs Mobile Money disponibles (avec leur logo fourni).
ALL_OPERATORS = ["MTN", "Orange", "Moov", "Wave", "Airtel", "Mov", "Mix"]

# Drapeaux (emoji) par pays, pour les sélecteurs.
COUNTRY_FLAGS = {
    "Benin": "🇧🇯",
    "Cote d'Ivoire": "🇨🇮",
    "Mali": "🇲🇱",
    "Senegal": "🇸🇳",
    "Burkina Faso": "🇧🇫",
    "Niger": "🇳🇪",
    "Togo": "🇹🇬",
    "Cameroun": "🇨🇲",
    "Gabon": "🇬🇦",
    "Republique du Congo": "🇨🇬",
    "RD Congo": "🇨🇩",
}

# Statuts normalisés des opérations.
STATUS_PENDING = "pending"
STATUS_PROCESSING = "processing"
STATUS_APPROVED = "approved"
STATUS_SUCCESSFUL = "successful"
STATUS_FAILED = "failed"
STATUS_CANCELLED = "cancelled"
STATUS_REJECTED = "rejected"
