"""Fournisseur SoleasPay (intégration réelle, à finaliser).

Les identifiants et la documentation officielle seront fournis ultérieurement.
Ne pas inventer les URL, paramètres, signatures ou réponses de son API :
les méthodes lèvent une erreur explicite tant que la documentation n'est pas
disponible.
"""
from app.payments.providers.base import BaseProvider, ProviderError


class SoleasPayProvider(BaseProvider):
    name = "soleaspay"

    def _missing_docs(self):
        raise ProviderError(
            "L'intégration SoleasPay nécessite la documentation officielle de "
            "l'API (URL, paramètres, signatures, réponses). Elle n'est pas encore "
            "disponible : aucun paiement réel ne peut être initié."
        )

    def initiate_deposit(self, deposit):
        self._missing_docs()

    def verify_status(self, external_ref: str):
        self._missing_docs()

    def process_webhook(self, payload: dict) -> dict:
        self._missing_docs()

    def normalize_status(self, raw) -> str:
        self._missing_docs()

    def verify_signature(self, request) -> bool:
        self._missing_docs()
