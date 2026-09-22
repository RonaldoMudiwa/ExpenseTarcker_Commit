"""An ordered, de-duplicated collection of transactions.

Day 1 produced objects. This module produces the thing that *holds* them.

A plain ``list`` would have worked. It was rejected for three reasons, each
worth being able to defend:

1. **Invariants.** A list cannot stop you appending the same transaction
   twice, or appending a string by accident. ``TransactionLedger`` enforces
   both rules in one place, so no calling code has to remember them.
2. **Behaviour belongs with data.** ``balance``, ``total_income`` and
   ``total_expenses`` are questions about the collection as a whole. Leaving
   them as loose functions scattered around the app is how procedural code
   ends up duplicated. This is encapsulation applied one level up, to a
   collection rather than a single object.
3. **Lookup cost.** Finding a transaction by identifier in a list is a scan.
   The ledger keeps a dictionary index alongside the order, so lookup and
   membership tests are constant time while iteration stays in insertion
   order.

The class subclasses ``collections.abc.Sequence`` rather than ``list``.
Inheriting from ``list`` would expose ``append``, ``insert``, ``extend`` and
``__setitem__``, every one of which bypasses the validation above; the
ledger would promise an invariant it could not keep. Composition (holding a
list privately) plus an abstract base class gives the useful half of a
list's interface and none of the dangerous half. This is "favour composition
over inheritance", and the Interface Segregation Principle, in one decision.

Because ``Sequence`` is implemented, a ledger already works with ``for``,
``len()``, ``in``, indexing, slicing, ``reversed()``, ``sorted()``,
unpacking and comprehensions, with no extra code.
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

# Zero as a ``Decimal``, defined once. Used as the starting value for every
# sum so that an empty ledger returns Decimal("0.00") rather than the int 0,
# keeping the return type of these properties consistent.
ZERO = Decimal("0.00")


class TransactionLedger(Sequence):
    """An ordered collection of unique transactions.

    Order is insertion order, not date order. Sorting is left to the caller
    (``sorted(ledger)`` works, since transactions compare by date) because a
    ledger that silently reordered itself would make the display layer's job
    harder, not easier.

    Example:
        >>> ledger = TransactionLedger()
        >>> ledger.add(Expense("3.40", "Flat white", Category.EATING_OUT))
        >>> ledger.add(Income("2400", "Salary", IncomeSource.SALARY))
        >>> len(ledger)
        2
        >>> ledger.balance
        Decimal('2396.60')
    """

    def __init__(self, transactions: Iterable[Transaction] | None = None) -> None:
        """Create a ledger, optionally pre-filled.

        Args:
            transactions: Any iterable of transactions. Each one is added
                through :meth:`add`, so the same validation applies as if
                they had been added one at a time. Defaults to empty.

        Raises:
            ValidationError: If any item is not a ``Transaction``.
            DuplicateTransactionError: If the iterable repeats a transaction.
        """
        # Two structures, one source of truth. ``_order`` preserves insertion
        # order for iteration and indexing; ``_by_id`` gives constant time
        # lookup. They are only ever written by ``add`` and ``remove``, which
        # is what keeps them in step.
        self._order: list[Transaction] = []
        self._by_id: dict[str, Transaction] = {}

        if transactions is not None:
            self.extend(transactions)

    # ------------------------------------------------------------------
    # Mutation, the only two methods allowed to touch the internals
    # ------------------------------------------------------------------

    def add(self, transaction: Transaction) -> Transaction:
        """Add one transaction to the end of the ledger.

        Args:
            transaction: Any concrete ``Transaction``, so ``Expense``,
                ``Income``, or any subclass added in future. The ledger is
                written entirely against the abstract base class and never
                asks which one it has.

        Returns:
            The transaction that was added, so calls can be chained or the
            result captured in one line.

        Raises:
            ValidationError: If the object is not a ``Transaction``.
            DuplicateTransactionError: If its identifier is already present.
        """
        # An explicit type check at a public boundary, rather than trusting
        # duck typing. The ledger's guarantees (a balance that means
        # something, ids that are unique) depend on every member honouring
        # the ``Transaction`` contract, so this is the one place worth being
        # strict about it.
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

        The operation is not atomic: transactions before a failure stay
        added. That is deliberate and documented rather than hidden, because
        rolling back would mean copying the whole ledger on every bulk add
        for a situation that indicates a bug in the caller anyway.

        Args:
            transactions: Any iterable of transactions.

        Raises:
            ValidationError: If any item is not a ``Transaction``.
            DuplicateTransactionError: If any item is already present.
        """
        for transaction in transactions:
            self.add(transaction)

    def remove(self, transaction_id: str) -> Transaction:
        """Remove a transaction by its identifier and return it.

        Removal is by identifier rather than by object so the command line
        interface (Day 6) can delete an entry using text typed by the user,
        without first having to find the object.

        Args:
            transaction_id: The identifier to remove.

        Returns:
            The transaction that was removed.

        Raises:
            TransactionNotFoundError: If no such identifier is held.
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
    # Lookup
    # ------------------------------------------------------------------

    def get(self, transaction_id: str) -> Transaction:
        """Return the transaction with this identifier.

        Args:
            transaction_id: The identifier to look up.

        Returns:
            The matching transaction. Constant time, because of the index.

        Raises:
            TransactionNotFoundError: If no such identifier is held.
        """
        try:
            return self._by_id[transaction_id]
        except KeyError as exc:
            # Re-raised as a domain error so callers never have to know that
            # a dictionary is used underneath. ``from exc`` keeps the
            # original traceback for debugging.
            raise TransactionNotFoundError(
                f"No transaction with id {transaction_id!r} in this ledger."
            ) from exc

    def filter_by(self, predicate: Callable[[Transaction], bool]) -> "TransactionLedger":
        """Return a new ledger holding only the transactions that match.

        Takes a function rather than a set of named arguments so that Day 4's
        date, category and text filters can all be expressed without this
        class growing a new parameter each time. The original is untouched,
        so filters can be chained safely.

        Args:
            predicate: A callable taking a transaction and returning a bool.

        Returns:
            A new ``TransactionLedger``. The transaction objects inside are
            shared, not copied, so editing one is visible in both ledgers.
        """
        return TransactionLedger(t for t in self._order if predicate(t))

    def of_type(self, transaction_type: type) -> "TransactionLedger":
        """Return a new ledger holding only transactions of the given class.

        Args:
            transaction_type: For example ``Income`` or ``Expense``.

        Returns:
            A new ``TransactionLedger`` containing the matching entries.
        """
        return self.filter_by(lambda t: isinstance(t, transaction_type))

    # ------------------------------------------------------------------
    # Aggregates, the payoff of polymorphism
    # ------------------------------------------------------------------

    @property
    def balance(self) -> Decimal:
        """Net position: income received minus money spent.

        One expression over a mixed collection, with no ``isinstance`` check
        and no ``if`` on transaction type. Each object already knows the
        direction it moves money in, so adding a new transaction class later
        requires no change to this line.
        """
        return sum((t.signed_amount for t in self._order), start=ZERO)

    @property
    def total_income(self) -> Decimal:
        """Sum of every amount that increases the balance."""
        return sum(
            (t.signed_amount for t in self._order if t.signed_amount > 0), start=ZERO
        )

    @property
    def total_expenses(self) -> Decimal:
        """Sum of every amount that decreases the balance, as a positive number.

        Returned unsigned because reports read better as "spent £412.80"
        than "spent £-412.80". The sign is a presentation concern here, not a
        property of the data.
        """
        return -sum(
            (t.signed_amount for t in self._order if t.signed_amount < 0), start=ZERO
        )

    def summary(self) -> str:
        """Return a short, printable overview of the ledger.

        Kept separate from ``__str__`` so that the short form (used in logs
        and error messages) and the full form (shown to a user) can differ.
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
        """Count transactions whose class declares this ``TRANSACTION_TYPE``.

        Counting by the class attribute rather than by ``isinstance`` keeps
        this method from importing ``Income`` or ``Expense``, so the ledger
        stays dependent only on the abstraction it was written against. That
        is the Dependency Inversion Principle: high level code depends on
        ``Transaction``, not on the concrete classes below it.

        Args:
            transaction_type_tag: For example ``"income"`` or ``"expense"``.

        Returns:
            How many transactions carry that tag.
        """
        return sum(1 for t in self._order if t.TRANSACTION_TYPE == transaction_type_tag)

    def to_dicts(self) -> list[dict[str, Any]]:
        """Serialise every transaction, ready for the Day 3 JSON storage layer.

        Each object serialises itself through the template method defined in
        ``Transaction``, so this method needs no knowledge of the fields any
        particular subclass holds.
        """
        return [t.to_dict() for t in self._order]

    # ------------------------------------------------------------------
    # Container protocol
    # ------------------------------------------------------------------

    def __len__(self) -> int:
        """Support ``len(ledger)``."""
        return len(self._order)

    @overload
    def __getitem__(self, index: int) -> Transaction: ...

    @overload
    def __getitem__(self, index: slice) -> "TransactionLedger": ...

    def __getitem__(self, index: int | slice) -> Transaction | "TransactionLedger":
        """Support ``ledger[0]`` and ``ledger[:3]``.

        A slice returns another ``TransactionLedger`` rather than a list, so
        that the result still answers ``balance`` and can be filtered
        further. Returning the same type from a slice is the convention every
        well behaved sequence follows.
        """
        if isinstance(index, slice):
            return TransactionLedger(self._order[index])
        return self._order[index]

    def __iter__(self) -> Iterator[Transaction]:
        """Support ``for transaction in ledger``.

        ``Sequence`` would supply an iterator built on repeated indexing.
        Iterating the internal list directly is both faster and clearer.
        """
        return iter(self._order)

    def __contains__(self, item: object) -> bool:
        """Support ``transaction in ledger`` and ``"some-uuid" in ledger``.

        Accepting either an object or a bare identifier is a small
        convenience for the command line layer, which only ever holds the
        text a user typed. Both paths are a dictionary lookup, so membership
        stays constant time instead of the linear scan ``Sequence`` would
        otherwise perform.
        """
        if isinstance(item, Transaction):
            return item.transaction_id in self._by_id
        if isinstance(item, str):
            return item in self._by_id
        return False

    def __bool__(self) -> bool:
        """An empty ledger is falsey, matching every other Python container.

        Defined explicitly rather than left to ``__len__`` so the intent is
        obvious to a reader.
        """
        return bool(self._order)

    def __add__(self, other: "TransactionLedger") -> "TransactionLedger":
        """Combine two ledgers into a new one, leaving both unchanged.

        Args:
            other: The ledger to merge in.

        Returns:
            A new ledger holding this ledger's transactions followed by the
            other's.

        Raises:
            DuplicateTransactionError: If the two ledgers share a transaction.
        """
        if not isinstance(other, TransactionLedger):
            # Returning ``NotImplemented`` rather than raising lets Python
            # try the other operand's ``__radd__`` before giving up with a
            # standard TypeError. Raising here would short circuit that.
            return NotImplemented

        combined = TransactionLedger(self._order)
        combined.extend(other)
        return combined

    def __repr__(self) -> str:
        """Unambiguous form for debugging, as ``repr`` is meant to be."""
        return (
            f"{type(self).__name__}(size={len(self._order)}, "
            f"balance={self.balance})"
        )

    def __str__(self) -> str:
        """Readable table of every transaction, one per line.

        Each line comes from the transaction's own ``summary_line``, so the
        ledger formats a mixed collection without knowing anything about the
        classes inside it.
        """
        if not self._order:
            return "Ledger is empty."
        return "\n".join(t.summary_line() for t in self._order)
