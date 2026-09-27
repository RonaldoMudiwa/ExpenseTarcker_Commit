"""The base class every kind of transaction inherits from."""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from datetime import date as date_type
from datetime import datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any, Mapping

from .exceptions import SerializationError, ValidationError

# Money is kept as Decimal, never float, because 0.1 + 0.2 as floats gives
# 0.30000000000000004.
MONEY_PRECISION = Decimal("0.01")
MAX_DESCRIPTION_LENGTH = 120


class Transaction(ABC):
    """One movement of money, in or out.

    Every field is checked whenever it is set, so a transaction can never
    hold a bad value. Two transactions are equal when they share an id, so
    two identical coffees on the same day still count as two purchases.
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
        """
        Args:
            amount: Always positive. Whether it is money in or out depends
                on the subclass.
            description: Short note, e.g. "Weekly shop at Tesco".
            transaction_date: A date or "YYYY-MM-DD". Defaults to today.
            transaction_id: Only passed when loading saved data.

        Raises:
            ValidationError: If any value is not allowed.
        """
        # Set once, with no setter, so it can't be changed from outside.
        self._transaction_id: str = transaction_id or str(uuid.uuid4())

        # Set through the properties so the checks run.
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
        """Negative for money out, positive for money in."""
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
            # Through str first, because Decimal(0.1) keeps the float's error.
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

        # Round halves up, like a shop would. Python's default rounds 0.125 to 0.12.
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

        # Checked before date, because a datetime is also a date. The time is dropped.
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
        """A dictionary ready to save as JSON."""
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
        """Needed so transactions work in sets and as dict keys."""
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
