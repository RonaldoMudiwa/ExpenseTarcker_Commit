"""A collection of transactions that refuses duplicates."""

from __future__ import annotations

from collections.abc import Iterable, Iterator, Sequence
from decimal import Decimal
from typing import Any, Callable, overload

from .exceptions import (
    DuplicateTransactionError,
    LedgerError,
    TransactionNotFoundError,
    ValidationError,
)
from .transaction import Transaction

# So an empty ledger's totals are Decimal("0.00"), not the number 0.
ZERO = Decimal("0.00")


class TransactionLedger(Sequence):
    """An ordered collection of unique transactions.

    Works like a read-only list: len(), in, indexing, slicing, sorted() and
    for loops all work. The only way to change it is add() and remove(),
    which do the checks. It isn't a list subclass, because then append()
    would let anything in without being checked.

        >>> ledger = TransactionLedger()
        >>> ledger.add(Expense("3.40", "Flat white", Category.EATING_OUT))
        >>> ledger.add(Income("2400", "Salary", IncomeSource.SALARY))
        >>> ledger.balance
        Decimal('2396.60')
    """

    def __init__(self, transactions: Iterable[Transaction] | None = None) -> None:
        """Create a ledger, optionally filled from any iterable.

        Raises:
            ValidationError: If an item is not a Transaction.
            DuplicateTransactionError: If the iterable repeats a transaction.
        """
        # _order keeps the order things were added. _by_id makes finding
        # by id instant. Only add() and remove() change them.
        self._order: list[Transaction] = []
        self._by_id: dict[str, Transaction] = {}

        if transactions is not None:
            self.extend(transactions)

    # ------------------------------------------------------------------
    # Changing the contents
    # ------------------------------------------------------------------

    def add(self, transaction: Transaction) -> Transaction:
        """Add one transaction to the end and return it.

        Raises:
            ValidationError: If the object is not a Transaction.
            DuplicateTransactionError: If its id is already here.
        """
        if not isinstance(transaction, Transaction):
            raise ValidationError(
                "Only Transaction objects can be added to a ledger, got "
                f"{type(transaction).__name__}."
            )

        if transaction.transaction_id in self._by_id:
            raise DuplicateTransactionError(
                f"Transaction {transaction.transaction_id} is already in the ledger. "
                "Create a new transaction rather than adding the same object twice."
            )

        self._by_id[transaction.transaction_id] = transaction
        self._order.append(transaction)
        return transaction

    def extend(self, transactions: Iterable[Transaction]) -> None:
        """Add several transactions in order.

        If one fails, the ones before it stay added.
        """
        for transaction in transactions:
            self.add(transaction)

    def remove(self, transaction_id: str) -> Transaction:
        """Remove a transaction by id and return it.

        Raises:
            TransactionNotFoundError: If no transaction has that id.
        """
        transaction = self._by_id.pop(transaction_id, None)
        if transaction is None:
            raise TransactionNotFoundError(
                f"No transaction with id {transaction_id!r} in this ledger."
            )

        self._order.remove(transaction)  # equality is by id, so this is exact
        return transaction

    def clear(self) -> None:
        """Empty the ledger, leaving it usable."""
        self._order.clear()
        self._by_id.clear()

    # ------------------------------------------------------------------
    # Finding things
    # ------------------------------------------------------------------

    def get(self, transaction_id: str) -> Transaction:
        """Return the transaction with this id.

        Raises:
            TransactionNotFoundError: If no transaction has that id.
        """
        try:
            return self._by_id[transaction_id]
        except KeyError as exc:
            # Our own error, so callers don't need to know a dict is used.
            raise TransactionNotFoundError(
                f"No transaction with id {transaction_id!r} in this ledger."
            ) from exc

    def resolve_id(self, prefix: str) -> str:
        """Turn the start of an id, like "3f2a9c", into the full id.

        Saves typing the whole 36 character id on the command line.

        Raises:
            TransactionNotFoundError: If nothing starts with it.
            LedgerError: If more than one id starts with it.
        """
        prefix = prefix.strip()
        if not prefix:
            raise TransactionNotFoundError("Give at least part of an id.")

        matches = [tid for tid in self._by_id if tid.startswith(prefix)]
        if not matches:
            raise TransactionNotFoundError(f"No transaction id starts with {prefix!r}.")
        if len(matches) > 1:
            raise LedgerError(
                f"{len(matches)} transactions start with {prefix!r}. "
                "Type a few more characters."
            )
        return matches[0]

    def filter_by(self, predicate: Callable[[Transaction], bool]) -> "TransactionLedger":
        """Return a new ledger of the transactions that match.

        The original is left alone. The transactions themselves are shared,
        not copied.
        """
        return TransactionLedger(t for t in self._order if predicate(t))

    def of_type(self, transaction_type: type) -> "TransactionLedger":
        """Return a new ledger of just one class, e.g. of_type(Income)."""
        return self.filter_by(lambda t: isinstance(t, transaction_type))

    # ------------------------------------------------------------------
    # Totals
    # ------------------------------------------------------------------

    @property
    def balance(self) -> Decimal:
        """Money in minus money out."""
        return sum((t.signed_amount for t in self._order), start=ZERO)

    @property
    def total_income(self) -> Decimal:
        """Everything that raises the balance."""
        return sum(
            (t.signed_amount for t in self._order if t.signed_amount > 0), start=ZERO
        )

    @property
    def total_expenses(self) -> Decimal:
        """Everything that lowers the balance, shown as a positive number."""
        return -sum(
            (t.signed_amount for t in self._order if t.signed_amount < 0), start=ZERO
        )

    def summary(self) -> str:
        """Count, totals and balance, ready to print."""
        if not self._order:
            return "Ledger is empty."

        lines = [
            f"{len(self._order)} transactions "
            f"({self.of_type_count('income')} in, {self.of_type_count('expense')} out)",
            f"Total in:   £{self.total_income:>10,.2f}",
            f"Total out:  £{self.total_expenses:>10,.2f}",
            f"Balance:    £{self.balance:>10,.2f}",
        ]
        return "\n".join(lines)

    def of_type_count(self, transaction_type_tag: str) -> int:
        """Count transactions of one type, e.g. "income"."""
        return sum(1 for t in self._order if t.TRANSACTION_TYPE == transaction_type_tag)

    def to_dicts(self) -> list[dict[str, Any]]:
        """Every transaction as a dictionary, ready to save."""
        return [t.to_dict() for t in self._order]

    # ------------------------------------------------------------------
    # Behaving like a Python container
    # ------------------------------------------------------------------

    def __len__(self) -> int:
        """len(ledger)."""
        return len(self._order)

    @overload
    def __getitem__(self, index: int) -> Transaction: ...

    @overload
    def __getitem__(self, index: slice) -> "TransactionLedger": ...

    def __getitem__(self, index: int | slice) -> Transaction | "TransactionLedger":
        """ledger[0] and ledger[:3]. A slice gives back another ledger."""
        if isinstance(index, slice):
            return TransactionLedger(self._order[index])
        return self._order[index]

    def __iter__(self) -> Iterator[Transaction]:
        """for transaction in ledger."""
        return iter(self._order)

    def __contains__(self, item: object) -> bool:
        """Works with a transaction or just its id."""
        if isinstance(item, Transaction):
            return item.transaction_id in self._by_id
        if isinstance(item, str):
            return item in self._by_id
        return False

    def __bool__(self) -> bool:
        """An empty ledger is falsey, like every other Python container."""
        return bool(self._order)

    def __add__(self, other: "TransactionLedger") -> "TransactionLedger":
        """Combine two ledgers into a new one, leaving both alone.

        Raises:
            DuplicateTransactionError: If the two share a transaction.
        """
        if not isinstance(other, TransactionLedger):
            # Tells Python this addition isn't supported, so it raises TypeError.
            return NotImplemented

        combined = TransactionLedger(self._order)
        combined.extend(other)
        return combined

    def __repr__(self) -> str:
        """Debugging form."""
        return (
            f"{type(self).__name__}(size={len(self._order)}, "
            f"balance={self.balance})"
        )

    def __str__(self) -> str:
        """One line per transaction."""
        if not self._order:
            return "Ledger is empty."
        return "\n".join(t.summary_line() for t in self._order)
