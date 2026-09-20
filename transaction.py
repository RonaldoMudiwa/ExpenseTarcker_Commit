"""The abstract base class that every money movement in the app inherits from.

This module is the backbone of the project's object oriented design.

``Transaction`` defines *what every transaction must be able to do* without
saying how a specific kind of transaction does it. Concrete subclasses such
as ``Expense`` (this week) and ``Income`` (added later in the week) fill in
the gaps.

The four OOP principles appear here as follows:

* **Abstraction** - ``Transaction`` is an ``ABC`` with abstract members. It
  describes a contract and cannot be instantiated on its own.
* **Encapsulation** - all state is stored in private attributes (``_amount``)
  and exposed through properties that validate on every write, so an invalid
  transaction cannot exist.
* **Inheritance** - shared behaviour (validation, equality, serialisation)
  lives here once, so subclasses stay small.
* **Polymorphism** - ``signed_amount`` and ``summary_line`` are declared here
  and implemented differently by each subclass, so calling code can treat a
  list of mixed transactions uniformly.
"""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from datetime import date as date_type
from datetime import datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any, Mapping

from .exceptions import SerializationError, ValidationError

# Money is stored as ``Decimal``, never as ``float``.
#
# 0.1 + 0.2 == 0.30000000000000004 in binary floating point. That is fine for
# physics and unacceptable for money. ``Decimal`` stores base-10 digits
# exactly, which is why every financial system uses fixed point arithmetic.
MONEY_PRECISION = Decimal("0.01")
MAX_DESCRIPTION_LENGTH = 120


class Transaction(ABC):
    """Base class for any single movement of money.

    Attributes are exposed as properties rather than plain public attributes
    so that validation runs on assignment as well as on construction::

        expense.amount = -5      # raises ValidationError, object stays valid

    Equality follows *entity* semantics: two transactions are equal when they
    are the same concrete type and carry the same ``transaction_id``. This
    mirrors how a database row works. Two separate coffees costing the same
    amount on the same day are still two distinct transactions, so comparing
    every field would be wrong.
    """

    #: Short machine readable tag used in serialised output. Subclasses must
    #: override it. Declared here so the base class can rely on it existing.
    TRANSACTION_TYPE: str = "transaction"

    def __init__(
        self,
        amount: Decimal | int | float | str,
        description: str,
        transaction_date: date_type | str | None = None,
        transaction_id: str | None = None,
    ) -> None:
        """Create a transaction, validating every field before storing it.

        Args:
            amount: A positive amount. The *direction* of the money (in or
                out) is the subclass's job, not the caller's, so the raw
                amount is always stored positive.
            description: Short free text, e.g. ``"Weekly shop at Tesco"``.
            transaction_date: The date the money moved. Accepts a ``date``
                object or an ISO string (``"2026-09-18"``). Defaults to today.
            transaction_id: Existing identifier, used when rebuilding an
                object from storage. A new UUID is generated when omitted.

        Raises:
            ValidationError: If any argument fails its validation rule.
        """
        # The identifier is assigned once and never exposed through a setter,
        # making it effectively read-only from outside the class.
        self._transaction_id: str = transaction_id or str(uuid.uuid4())

        # Assign through the properties (not the private attributes) so the
        # validation logic runs exactly once, in one place.
        self.amount = amount
        self.description = description
        self.transaction_date = transaction_date

    # ------------------------------------------------------------------
    # Properties: the public, validated interface to the private state
    # ------------------------------------------------------------------

    @property
    def transaction_id(self) -> str:
        """Unique identifier for this transaction (read-only)."""
        return self._transaction_id

    @property
    def amount(self) -> Decimal:
        """The absolute size of the transaction, always positive."""
        return self._amount

    @amount.setter
    def amount(self, value: Decimal | int | float | str) -> None:
        self._amount = self._validate_amount(value)

    @property
    def description(self) -> str:
        """Short human written note describing the transaction."""
        return self._description

    @description.setter
    def description(self, value: str) -> None:
        self._description = self._validate_description(value)

    @property
    def transaction_date(self) -> date_type:
        """The calendar date on which the money moved."""
        return self._transaction_date

    @transaction_date.setter
    def transaction_date(self, value: date_type | str | None) -> None:
        self._transaction_date = self._validate_date(value)

    # ------------------------------------------------------------------
    # Abstract members: the contract every subclass must satisfy
    # ------------------------------------------------------------------

    @property
    @abstractmethod
    def signed_amount(self) -> Decimal:
        """Return the amount with its effect on the balance applied.

        An expense returns a negative number, income returns a positive one.
        Because both subclasses answer the same question in their own way,
        a running balance is simply ``sum(t.signed_amount for t in items)``
        with no type checks anywhere. That is polymorphism paying for itself.
        """
        raise NotImplementedError  # pragma: no cover - enforced by ABC

    @abstractmethod
    def summary_line(self) -> str:
        """Return a single formatted line describing this transaction."""
        raise NotImplementedError  # pragma: no cover - enforced by ABC

    # ------------------------------------------------------------------
    # Validation helpers
    #
    # These are static methods: they belong to the class conceptually but
    # need no access to a particular instance (``self``) or to the class
    # itself (``cls``). Marking them ``@staticmethod`` states that clearly.
    # ------------------------------------------------------------------

    @staticmethod
    def _validate_amount(value: Decimal | int | float | str) -> Decimal:
        """Convert ``value`` to a positive ``Decimal`` rounded to 2 places."""
        # ``bool`` is a subclass of ``int`` in Python, so ``True`` would
        # otherwise sneak through as the amount 1.00. Reject it explicitly.
        if isinstance(value, bool):
            raise ValidationError("Amount must be a number, not a boolean.")

        if value is None:
            raise ValidationError("Amount is required.")

        try:
            # ``str(value)`` first: Decimal(0.1) captures the binary error,
            # whereas Decimal("0.1") is exactly one tenth.
            amount = Decimal(str(value).strip())
        except (InvalidOperation, ValueError, TypeError) as error:
            raise ValidationError(f"Amount {value!r} is not a valid number.") from error

        if not amount.is_finite():
            raise ValidationError("Amount must be a finite number.")

        if amount <= 0:
            raise ValidationError(
                f"Amount must be greater than zero, got {amount}. "
                "Direction is determined by the transaction type, not the sign."
            )

        # ROUND_HALF_UP matches how people expect money to round. Python's
        # default, ROUND_HALF_EVEN, would turn 0.125 into 0.12.
        return amount.quantize(MONEY_PRECISION, rounding=ROUND_HALF_UP)

    @staticmethod
    def _validate_description(value: str) -> str:
        """Ensure the description is non-empty text of a sensible length."""
        if not isinstance(value, str):
            raise ValidationError(
                f"Description must be text, got {type(value).__name__}."
            )

        cleaned = " ".join(value.split())  # collapse runs of whitespace
        if not cleaned:
            raise ValidationError("Description cannot be empty.")

        if len(cleaned) > MAX_DESCRIPTION_LENGTH:
            raise ValidationError(
                f"Description cannot exceed {MAX_DESCRIPTION_LENGTH} characters "
                f"(got {len(cleaned)})."
            )
        return cleaned

    @staticmethod
    def _validate_date(value: date_type | str | None) -> date_type:
        """Normalise ``value`` to a ``date``, defaulting to today."""
        if value is None:
            return date_type.today()

        if isinstance(value, datetime):
            # ``datetime`` is a subclass of ``date``, so this check must come
            # first. Drop the time component: this app works in whole days.
            return value.date()

        if isinstance(value, date_type):
            return value

        if isinstance(value, str):
            try:
                return date_type.fromisoformat(value.strip())
            except ValueError as error:
                raise ValidationError(
                    f"Date {value!r} is not in ISO format (YYYY-MM-DD)."
                ) from error

        raise ValidationError(
            f"Date must be a date or an ISO string, got {type(value).__name__}."
        )

    # ------------------------------------------------------------------
    # Serialisation (template method pattern)
    #
    # ``to_dict`` fixes the shared shape of the output and calls the hook
    # ``_extra_fields`` for the parts only a subclass knows about. Subclasses
    # override the small hook, never the whole method, so the common keys can
    # never drift apart between types.
    # ------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON friendly dictionary representing this transaction."""
        data: dict[str, Any] = {
            "transaction_id": self.transaction_id,
            "type": self.TRANSACTION_TYPE,
            "amount": str(self.amount),  # str keeps Decimal precision in JSON
            "description": self.description,
            "date": self.transaction_date.isoformat(),
        }
        data.update(self._extra_fields())
        return data

    def _extra_fields(self) -> Mapping[str, Any]:
        """Hook for subclasses to add their own keys to ``to_dict``.

        Returns an empty mapping by default, so a subclass with no extra
        state needs to do nothing at all.
        """
        return {}

    @staticmethod
    def _require(data: Mapping[str, Any], key: str) -> Any:
        """Fetch ``key`` from ``data`` or raise a clear serialisation error.

        Shared by the ``from_dict`` factory methods of every subclass.
        """
        if key not in data:
            raise SerializationError(f"Missing required key {key!r} in stored data.")
        return data[key]

    # ------------------------------------------------------------------
    # Dunder methods: making the object behave like a first class Python type
    # ------------------------------------------------------------------

    def __eq__(self, other: object) -> bool:
        """Two transactions are equal when they are the same stored entity."""
        if not isinstance(other, Transaction):
            return NotImplemented  # lets Python try the reflected comparison
        return (
            type(self) is type(other)
            and self.transaction_id == other.transaction_id
        )

    def __hash__(self) -> int:
        """Keep ``__hash__`` consistent with ``__eq__``.

        Defining ``__eq__`` without ``__hash__`` makes a class unhashable,
        which would break sets and dictionary keys. Hashing the same fields
        used by ``__eq__`` keeps the two in step.
        """
        return hash((type(self).__name__, self.transaction_id))

    def __lt__(self, other: "Transaction") -> bool:
        """Order transactions by date, so ``sorted()`` works out of the box."""
        if not isinstance(other, Transaction):
            return NotImplemented
        return self.transaction_date < other.transaction_date

    def __repr__(self) -> str:
        """Unambiguous form aimed at developers and debuggers."""
        return (
            f"{type(self).__name__}(amount={self.amount!r}, "
            f"description={self.description!r}, "
            f"transaction_date={self.transaction_date!r}, "
            f"transaction_id={self.transaction_id!r})"
        )

    def __str__(self) -> str:
        """Readable form aimed at end users, delegated to the subclass."""
        return self.summary_line()
