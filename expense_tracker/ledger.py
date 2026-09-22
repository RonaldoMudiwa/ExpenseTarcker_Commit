"""A collection of transactions that keeps itself tidy.

A plain list would have worked, but a list can't stop you adding the same
transaction twice or appending a string by mistake. Putting those rules in
one place means no calling code has to remember them.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator, Sequence
from decimal import Decimal
from typing import Any, Callable, overload

from .exceptions import (
    DuplicateTransactionError,
    TransactionNotFoundError,
    ValidationError,
)
from .transaction import Transaction

# Defined once so an empty ledger returns Decimal("0.00") rather than int 0,
# keeping the return type of the totals consistent.
ZERO = Decimal("0.00")


class TransactionLedger(Sequence):
    """An ordered collection of unique transactions.

    Subclasses Sequence rather than list. Inheriting from list would hand out
    append, insert and __setitem__, all of which skip the checks below, so
    the ledger would promise something it couldn't deliver. Holding a list
    privately gives the useful half of a list and none of the risky half.

    Because Sequence is implemented, len(), in, indexing, slicing, iteration,
    reversed(), sorted() and unpacking all work with no extra code.

    Order is insertion order, not date order. Sorting is left to the caller,
    since a collection that quietly reordered itself would make the display
    code harder to reason about, not easier.

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
        # Two structures, one source of truth. _order keeps insertion order
        # for iterating and indexing; _by_id makes lookup instant instead of
        # a scan. Only add() and remove() touch them, which is what keeps
        # them in step.
        self._order: list[Transaction] = []
        self._by_id: dict[str, Transaction] = {}

        if transactions is not None:
            self.extend(transactions)

    # ------------------------------------------------------------------
    # Changing the contents
    # ------------------------------------------------------------------

    def add(self, transaction: Transaction) -> Transaction:
        """Add one transaction to the end and return it.

        Works with any Transaction subclass, now or later, because the ledger
        is written against the base class and never asks which one it has.

        Raises:
            ValidationError: If the object is not a Transaction.
            DuplicateTransactionError: If its id is already here.
        """
        # An explicit type check rather than trusting duck typing. The
        # ledger's promises (a balance that means something, ids that are
        # unique) all rest on every member honouring the Transaction
        # contract, so this is the one place worth being strict.
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

        Not all or nothing: anything added before a failure stays added.
        That is documented rather than hidden, because rolling back would
        mean copying the whole ledger on every bulk add, for a situation that
        means the caller has a bug anyway.
        """
        for transaction in transactions:
            self.add(transaction)

    def remove(self, transaction_id: str) -> Transaction:
        """Remove a transaction by id and return it.

        By id rather than by object, so Day 6's command line can delete an
        entry from text the user typed without finding the object first.

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
        """Return the transaction with this id. Instant, thanks to the index.

        Raises:
            TransactionNotFoundError: If no transaction has that id.
        """
        try:
            return self._by_id[transaction_id]
        except KeyError as exc:
            # Re-raised as our own error so callers never need to know a dict
            # is involved. "from exc" keeps the original traceback.
            raise TransactionNotFoundError(
                f"No transaction with id {transaction_id!r} in this ledger."
            ) from exc

    def filter_by(self, predicate: Callable[[Transaction], bool]) -> "TransactionLedger":
        """Return a new ledger of the transactions that match.

        Takes a function rather than a pile of named arguments, so Day 4's
        date, category and text filters all fit without this class growing a
        parameter each time. The original is untouched, so filters chain.

        The transaction objects are shared, not copied, so editing one shows
        up in both ledgers.
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
        """Money in minus money out.

        One expression over a mixed collection, no isinstance, no branching
        on type. Each object already knows which way it moves money, so a new
        transaction class later would need no change to this line.
        """
        return sum((t.signed_amount for t in self._order), start=ZERO)

    @property
    def total_income(self) -> Decimal:
        """Everything that raises the balance."""
        return sum(
            (t.signed_amount for t in self._order if t.signed_amount > 0), start=ZERO
        )

    @property
    def total_expenses(self) -> Decimal:
        """Everything that lowers the balance, as a positive number.

        Unsigned because "spent £412.80" reads better than "spent £-412.80".
        The sign is a display choice here, not part of the data.
        """
        return -sum(
            (t.signed_amount for t in self._order if t.signed_amount < 0), start=ZERO
        )

    def summary(self) -> str:
        """A short printable overview.

        Separate from __str__ so the brief version (logs, error messages) and
        the full listing can differ.
        """
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
        """Count transactions carrying this TRANSACTION_TYPE tag.

        Counting by the tag rather than by isinstance keeps this file from
        importing Income or Expense, so the ledger depends only on the base
        class it was written against.
        """
        return sum(1 for t in self._order if t.TRANSACTION_TYPE == transaction_type_tag)

    def to_dicts(self) -> list[dict[str, Any]]:
        """Every transaction as a dictionary, ready for Day 3's storage layer.

        Each object serialises itself, so this needs no knowledge of what
        fields any particular subclass holds.
        """
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
        """ledger[0] and ledger[:3].

        A slice gives back another ledger rather than a list, so the result
        still answers .balance and can be filtered again. Returning your own
        type from a slice is what every well behaved sequence does.
        """
        if isinstance(index, slice):
            return TransactionLedger(self._order[index])
        return self._order[index]

    def __iter__(self) -> Iterator[Transaction]:
        """for transaction in ledger.

        Sequence would build an iterator out of repeated indexing. Iterating
        the internal list is faster and clearer.
        """
        return iter(self._order)

    def __contains__(self, item: object) -> bool:
        """transaction in ledger, and also "some-id" in ledger.

        Accepting a bare id helps the command line layer, which only ever has
        the text the user typed. Both routes are a dict lookup, so this stays
        instant instead of the scan Sequence would otherwise do.
        """
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
            # Returning NotImplemented lets Python try the other operand's
            # __radd__ before giving up with a TypeError. Raising here would
            # cut that short.
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
        """One line per transaction.

        Each line comes from the transaction itself, so the ledger formats a
        mixed collection without knowing anything about the classes in it.
        """
        if not self._order:
            return "Ledger is empty."
        return "\n".join(t.summary_line() for t in self._order)
