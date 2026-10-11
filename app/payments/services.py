"""Catalogue des services Mobile Money (SoleasPay v3).

Chaque service référence un identifiant (service_id) utilisé par le prestataire
et un opérateur (marque) pour l'affichage du logo.
"""

COUNTRY_CODE = {
    "Benin": "BJ",
    "Cote d'Ivoire": "CI",
    "Mali": "ML",
    "Senegal": "SN",
    "Burkina Faso": "BF",
    "Niger": "NE",
    "Togo": "TG",
    "Cameroun": "CM",
    "Gabon": "GAB",
    "Republique du Congo": "COG",
    "RD Congo": "COD",
}

SERVICES = {
    # 🇨🇲 Cameroun
    "CM": [
        {"id": 1, "name": "MOMO CM", "description": "MTN Mobile Money Cameroun", "operator": "MTN", "logo": "mtn"},
        {"id": 2, "name": "OM CM", "description": "Orange Money Cameroun", "operator": "Orange", "logo": "orange"},
    ],
    # 🇨🇮 Côte d'Ivoire
    "CI": [
        {"id": 29, "name": "OM CI", "description": "Orange Money Côte d'Ivoire", "operator": "Orange", "logo": "orange"},
        {"id": 30, "name": "MOMO CI", "description": "MTN Money Côte d'Ivoire", "operator": "MTN", "logo": "mtn"},
        {"id": 31, "name": "MOOV CI", "description": "Moov Côte d'Ivoire", "operator": "Moov", "logo": "moov"},
        {"id": 32, "name": "WAVE CI", "description": "Wave Côte d'Ivoire", "operator": "Wave", "logo": "wave"},
    ],
    # 🇧🇫 Burkina Faso
    "BF": [
        {"id": 33, "name": "MOOV BF", "description": "Moov Burkina Faso", "operator": "Moov", "logo": "moov"},
        {"id": 34, "name": "OM BF", "description": "Orange Money Burkina Faso", "operator": "Orange", "logo": "orange"},
    ],
    # 🇧🇯 Bénin
    "BJ": [
        {"id": 35, "name": "MOMO BJ", "description": "MTN Money Bénin", "operator": "MTN", "logo": "mtn"},
        {"id": 36, "name": "MOOV BJ", "description": "Moov Bénin", "operator": "Moov", "logo": "moov"},
    ],
    # 🇹🇬 Togo
    "TG": [
        {"id": 37, "name": "T-MONEY TG", "description": "T-Money Togo", "operator": "T-Money", "logo": None},
        {"id": 38, "name": "MOOV TG", "description": "Moov Togo", "operator": "Moov", "logo": "moov"},
    ],
    # 🇨🇩 Congo RDC
    "COD": [
        {"id": 52, "name": "VODACOM COD", "description": "Vodacom Congo RDC", "operator": "Vodacom", "logo": None},
        {"id": 53, "name": "AIRTEL COD", "description": "Airtel Congo RDC", "operator": "Airtel", "logo": "airtel"},
        {"id": 54, "name": "ORANGE COD", "description": "Orange Congo RDC", "operator": "Orange", "logo": "orange"},
    ],
    # 🇨🇬 Congo Brazzaville
    "COG": [
        {"id": 55, "name": "AIRTEL COG", "description": "Airtel Congo", "operator": "Airtel", "logo": "airtel"},
        {"id": 56, "name": "MOMO COG", "description": "MTN MOMO Congo", "operator": "MTN", "logo": "mtn"},
    ],
    # 🇬🇦 Gabon
    "GAB": [
        {"id": 57, "name": "AIRTEL GAB", "description": "Airtel Gabon", "operator": "Airtel", "logo": "airtel"},
    ],
    # 🇺🇬 Ouganda
    "UGA": [
        {"id": 58, "name": "AIRTEL UGA", "description": "Airtel Uganda", "operator": "Airtel", "logo": "airtel"},
        {"id": 59, "name": "MOMO UGA", "description": "MTN MOMO Uganda", "operator": "MTN", "logo": "mtn"},
    ],
}


def country_code(country_name):
    return COUNTRY_CODE.get(country_name)


def services_for_country(country_name):
    code = COUNTRY_CODE.get(country_name)
    return SERVICES.get(code, [])


def service_by_name(country_name, name):
    for s in services_for_country(country_name):
        if s["name"] == name:
            return s
    return None
