"""The base class every money movement inherits from.

Transaction says what any transaction must be able to do. Expense and Income
say how. Shared work (validating, comparing, saving) is written here once so
the subclasses stay small.
"""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from datetime import date as date_type
from datetime import datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any, Mapping

from .exceptions import SerializationError, ValidationError

# Money is a Decimal, never a float. In binary floating point
# 0.1 + 0.2 == 0.30000000000000004, which is fine for physics and useless
# for money. Decimal stores base 10 digits exactly.
MONEY_PRECISION = Decimal("0.01")
MAX_DESCRIPTION_LENGTH = 120


class Transaction(ABC):
    """One movement of money, in or out.

    Fields are properties rather than plain attributes so validation runs on
    every write, not just at construction:

        expense.amount = -5     # raises, and the object is unchanged

    Two transactions are equal when they are the same type with the same id,
    the way a database row works. Two coffees at the same price on the same
    day are still two separate purchases, so comparing every field would give
    the wrong answer.
    """

    # Written into saved data so the loader knows which class to rebuild.
    # Subclasses override it.
    TRANSACTION_TYPE: str = "transaction"

    def __init__(
        self,
        amount: Decimal | int | float | str,
        description: str,
        transaction_date: date_type | str | None = None,
        transaction_id: str | None = None,
    ) -> None:
        """Create a transaction, checking every field first.

        Args:
            amount: A positive amount. Direction is the subclass's job, so
                the stored number is never negative.
            description: Short note, e.g. "Weekly shop at Tesco".
            transaction_date: A date or an ISO string. Defaults to today.
            transaction_id: An existing id, used when loading from storage.
                A new UUID is generated otherwise.

        Raises:
            ValidationError: If any argument fails its check.
        """
        # Set once, with no setter, so it can't be changed from outside.
        self._transaction_id: str = transaction_id or str(uuid.uuid4())

        # Go through the properties, not the private attributes, so the
        # validation runs in one place only.
        self.amount = amount
        self.description = description
        self.transaction_date = transaction_date

    # ------------------------------------------------------------------
    # Fields
    # ------------------------------------------------------------------

    @property
    def transaction_id(self) -> str:
        """Unique id for this transaction. Read only."""
        return self._transaction_id

    @property
    def amount(self) -> Decimal:
        """How much money moved. Always positive."""
        return self._amount

    @amount.setter
    def amount(self, value: Decimal | int | float | str) -> None:
        self._amount = self._validate_amount(value)

    @property
    def description(self) -> str:
        """Short note describing the transaction."""
        return self._description

    @description.setter
    def description(self, value: str) -> None:
        self._description = self._validate_description(value)

    @property
    def transaction_date(self) -> date_type:
        """The day the money moved."""
        return self._transaction_date

    @transaction_date.setter
    def transaction_date(self, value: date_type | str | None) -> None:
        self._transaction_date = self._validate_date(value)

    # ------------------------------------------------------------------
    # What subclasses must provide
    # ------------------------------------------------------------------

    @property
    @abstractmethod
    def signed_amount(self) -> Decimal:
        """The amount with its effect on the balance applied.

        Negative for an expense, positive for income. Because both answer
        this the same way, a running total is just:

            sum(t.signed_amount for t in items)

        with no checks on what type anything is.
        """
        raise NotImplementedError  # pragma: no cover - the ABC enforces this

    @abstractmethod
    def summary_line(self) -> str:
        """One formatted line describing this transaction."""
        raise NotImplementedError  # pragma: no cover - the ABC enforces this

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    @staticmethod
    def _validate_amount(value: Decimal | int | float | str) -> Decimal:
        """Return value as a positive Decimal rounded to 2 places."""
        # bool is a subclass of int in Python, so True would otherwise be
        # accepted as the amount 1.00.
        if isinstance(value, bool):
            raise ValidationError("Amount must be a number, not a boolean.")

        if value is None:
            raise ValidationError("Amount is required.")

        try:
            # Convert to str first. Decimal(0.1) keeps the float's rounding
            # error, while Decimal("0.1") is exactly one tenth.
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

        # ROUND_HALF_UP is how people expect money to round. Python's default
        # would turn 0.125 into 0.12.
        return amount.quantize(MONEY_PRECISION, rounding=ROUND_HALF_UP)

    @staticmethod
    def _validate_description(value: str) -> str:
        """Return the description trimmed, or raise if it is unusable."""
        if not isinstance(value, str):
            raise ValidationError(
                f"Description must be text, got {type(value).__name__}."
            )

        cleaned = " ".join(value.split())  # squash repeated whitespace
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
        """Return value as a date, defaulting to today."""
        if value is None:
            return date_type.today()

        # datetime is a subclass of date, so it has to be checked first.
        # The time is dropped because this app works in whole days.
        if isinstance(value, datetime):
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
    # Saving and loading
    # ------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        """Return a dictionary ready for JSON.

        The shared keys are fixed here. Subclasses add their own through
        _extra_fields, so the common part can't drift between types.
        """
        data: dict[str, Any] = {
            "transaction_id": self.transaction_id,
            "type": self.TRANSACTION_TYPE,
            "amount": str(self.amount),  # str keeps the Decimal exact in JSON
            "description": self.description,
            "date": self.transaction_date.isoformat(),
        }
        data.update(self._extra_fields())
        return data

    def _extra_fields(self) -> Mapping[str, Any]:
        """Extra keys for to_dict. Subclasses override this; empty by default."""
        return {}

    @classmethod
    @abstractmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "Transaction":
        """Rebuild a transaction from what to_dict produced."""
        raise NotImplementedError  # pragma: no cover - the ABC enforces this

    @staticmethod
    def _require(data: Mapping[str, Any], key: str) -> Any:
        """Read a required key, or raise a clear error. Used by from_dict."""
        if key not in data:
            raise SerializationError(f"Missing required key {key!r} in stored data.")
        return data[key]

    # ------------------------------------------------------------------
    # Dunder methods
    # ------------------------------------------------------------------

    def __eq__(self, other: object) -> bool:
        """Equal means the same type and the same id."""
        if not isinstance(other, Transaction):
            return NotImplemented  # let Python try the other side
        return (
            type(self) is type(other)
            and self.transaction_id == other.transaction_id
        )

    def __hash__(self) -> int:
        """Hash on the same fields as __eq__.

        Defining __eq__ without this makes the class unhashable, which breaks
        sets and dict keys.
        """
        return hash((type(self).__name__, self.transaction_id))

    def __lt__(self, other: "Transaction") -> bool:
        """Sort by date, so sorted() works with no key function."""
        if not isinstance(other, Transaction):
            return NotImplemented
        return self.transaction_date < other.transaction_date

    def __repr__(self) -> str:
        """Debugging form, showing everything."""
        return (
            f"{type(self).__name__}(amount={self.amount!r}, "
            f"description={self.description!r}, "
            f"transaction_date={self.transaction_date!r}, "
            f"transaction_id={self.transaction_id!r})"
        )

    def __str__(self) -> str:
        """Readable form, left to the subclass."""
        return self.summary_line()
