"""Service financier central : crédits/débits atomiques et journal comptable.

Règle stricte : aucune route HTTP ne modifie directement un solde. Toutes les
opérations passent par ces fonctions, qui :
- verrouillent la ligne du portefeuille (SELECT ... FOR UPDATE en PostgreSQL) ;
- vérifient l'absence de solde négatif ;
- garantissent l'idempotence par référence unique ;
- écrivent une écriture comptable (LedgerEntry) traçable.
"""
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models import LedgerEntry, Wallet
from app.models.base import utcnow
from app.utils import new_reference


class FinancialError(Exception):
    """Erreur financière générique."""


class InsufficientFundsError(FinancialError):
    """Solde insuffisant pour l'opération."""


class DuplicateReferenceError(FinancialError):
    """La référence existe déjà (opération non idempotente rejetée)."""


def get_wallet(user_id: int, currency: str, wallet_type: str, for_update: bool = False) -> Wallet:
    query = Wallet.query.filter_by(user_id=user_id, currency=currency, type=wallet_type)
    if for_update:
        query = query.with_for_update()
    wallet = query.first()
    if wallet is None:
        wallet = Wallet(user_id=user_id, currency=currency, type=wallet_type, balance=0)
        db.session.add(wallet)
        db.session.flush()
    return wallet


def ensure_wallets(user_id: int, currency: str, types) -> None:
    """Crée tous les portefeuilles manquants pour un utilisateur."""
    for t in types:
        get_wallet(user_id, currency, t)


def _apply(
    user_id: int,
    currency: str,
    wallet_type: str,
    signed_amount: int,
    entry_type: str,
    transaction_type: str,
    source: str,
    reference: str = None,
    description: str = None,
    external_ref: str = None,
    operator: str = None,
    status: str = "confirmed",
) -> LedgerEntry:
    if reference is None:
        reference = new_reference("LED")
    if LedgerEntry.query.filter_by(reference=reference).first() is not None:
        raise DuplicateReferenceError(f"Référence dupliquée : {reference}")

    wallet = get_wallet(user_id, currency, wallet_type, for_update=True)
    new_balance = wallet.balance + signed_amount
    if new_balance < 0:
        raise InsufficientFundsError(
            f"Solde insuffisant sur le portefeuille {wallet_type} {currency}"
        )

    wallet.balance = new_balance
    entry = LedgerEntry(
        user_id=user_id,
        wallet_type=wallet_type,
        currency=currency,
        amount=signed_amount,
        entry_type=entry_type,
        transaction_type=transaction_type,
        reference=reference,
        status=status,
        balance_after=new_balance,
        source=source,
        operator=operator,
        external_ref=external_ref,
        description=description,
        confirmed_at=utcnow() if status == "confirmed" else None,
    )
    db.session.add(entry)
    db.session.flush()
    return entry


def credit(
    user_id: int,
    currency: str,
    wallet_type: str,
    amount: int,
    transaction_type: str,
    source: str,
    reference: str = None,
    description: str = None,
    external_ref: str = None,
    operator: str = None,
    status: str = "confirmed",
) -> LedgerEntry:
    """Crédite un portefeuille (montant positif)."""
    if amount <= 0:
        raise ValueError("Le montant doit être strictement positif.")
    return _apply(
        user_id, currency, wallet_type, amount, "credit",
        transaction_type, source, reference, description, external_ref, operator, status,
    )


def debit(
    user_id: int,
    currency: str,
    wallet_type: str,
    amount: int,
    transaction_type: str,
    source: str,
    reference: str = None,
    description: str = None,
    external_ref: str = None,
    operator: str = None,
    status: str = "confirmed",
) -> LedgerEntry:
    """Débite un portefeuille (montant positif), refuse un solde négatif."""
    if amount <= 0:
        raise ValueError("Le montant doit être strictement positif.")
    return _apply(
        user_id, currency, wallet_type, -amount, "debit",
        transaction_type, source, reference, description, external_ref, operator, status,
    )


def transfer(
    user_id: int,
    currency: str,
    from_wallet: str,
    to_wallet: str,
    amount: int,
    transaction_type: str,
    source: str,
    description: str = None,
    reference: str = None,
) -> None:
    """Transfert atomique entre deux portefeuilles (débit puis crédit)."""
    if amount <= 0:
        raise ValueError("Le montant doit être strictement positif.")
    ref_base = reference or new_reference("TRF")
    debit(user_id, currency, from_wallet, amount, transaction_type, source,
          reference=f"{ref_base}-OUT", description=description)
    credit(user_id, currency, to_wallet, amount, transaction_type, source,
           reference=f"{ref_base}-IN", description=description)


def get_balance(user_id: int, currency: str, wallet_type: str) -> int:
    wallet = Wallet.query.filter_by(user_id=user_id, currency=currency, type=wallet_type).first()
    return wallet.balance if wallet else 0


def get_balances(user_id: int, currency: str) -> dict:
    wallets = Wallet.query.filter_by(user_id=user_id, currency=currency).all()
    return {w.type: w.balance for w in wallets}
