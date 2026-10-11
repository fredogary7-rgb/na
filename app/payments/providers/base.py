"""Interface commune des fournisseurs de paiement.

Permet d'ajouter d'autres prestataires sans modifier la logique métier.
"""


class ProviderError(Exception):
    pass


class BaseProvider:
    name = "base"

    def initiate_deposit(self, deposit, otp=None):
        raise NotImplementedError

    def verify_status(self, external_ref: str):
        raise NotImplementedError

    def process_webhook(self, payload: dict) -> dict:
        """Normalise un événement webhook en structure standard :
        {reference, amount, currency, status, external_ref}."""
        raise NotImplementedError

    def normalize_status(self, raw) -> str:
        raise NotImplementedError

    def verify_signature(self, request) -> bool:
        raise NotImplementedError
