"""Money coming in."""

from __future__ import annotations

from datetime import date as date_type
from decimal import Decimal
from typing import Any, Mapping

from .enums import IncomeSource, coerce_enum
from .exceptions import ValidationError
from .transaction import Transaction


class Income(Transaction):
    """A payment received: salary, refund, freelance work.

        >>> pay = Income("2400.00", "September salary", "salary",
        ...              "2026-09-25", is_recurring=True)
        >>> pay.signed_amount
        Decimal('2400.00')
    """

    TRANSACTION_TYPE = "income"

    def __init__(
        self,
        amount: Decimal | int | float | str,
        description: str,
        source: IncomeSource | str = IncomeSource.OTHER,
        transaction_date: date_type | str | None = None,
        is_recurring: bool = False,
        transaction_id: str | None = None,
    ) -> None:
        """
        Args:
            amount: A positive amount received.
            description: Short label, e.g. "September salary".
            source: An IncomeSource member, or text like "salary".
            transaction_date: Date received. Defaults to today.
            is_recurring: True for regular income such as a monthly salary.
            transaction_id: An existing id, used when loading from storage.

        Raises:
            ValidationError: If any argument fails its check.
        """
        # Shared checks first, so nothing is half set up if one fails.
        super().__init__(
            amount=amount,
            description=description,
            transaction_date=transaction_date,
            transaction_id=transaction_id,
        )

        self.source = source
        self.is_recurring = is_recurring

    # ------------------------------------------------------------------
    # Fields
    # ------------------------------------------------------------------

    @property
    def source(self) -> IncomeSource:
        """Where the money came from."""
        return self._source

    @source.setter
    def source(self, value: IncomeSource | str) -> None:
        self._source = coerce_enum(value, IncomeSource)

    @property
    def is_recurring(self) -> bool:
        """Whether this income repeats on a schedule."""
        return self._is_recurring

    @is_recurring.setter
    def is_recurring(self, value: bool) -> None:
        # Only a real True or False. Otherwise "no" would count as True.
        if not isinstance(value, bool):
            raise ValidationError(
                f"is_recurring must be True or False, got {type(value).__name__}."
            )
        self._is_recurring = value

    # ------------------------------------------------------------------
    # The base class contract
    # ------------------------------------------------------------------

    @property
    def signed_amount(self) -> Decimal:
        """Positive, because income raises the balance."""
        return self.amount

    def summary_line(self) -> str:
        """One line, e.g. "2026-09-25  +£2,400.00  Salary          Pay"."""
        recurring_marker = " (recurring)" if self.is_recurring else ""
        return (
            f"{self.transaction_date.isoformat()}  "
            f"+£{self.amount:>8,.2f}  "
            f"{self.source.label:<14}  "
            f"{self.description}{recurring_marker}"
        )

    # ------------------------------------------------------------------
    # Saving and loading
    # ------------------------------------------------------------------

    def _extra_fields(self) -> Mapping[str, Any]:
        """The two keys only income has."""
        return {
            "source": self.source.value,
            "is_recurring": self.is_recurring,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "Income":
        """Rebuild an Income from what to_dict produced.

        Missing optional keys fall back to the defaults.

        Raises:
            SerializationError: If amount or description is missing.
            ValidationError: If a stored value is no longer valid.
        """
        return cls(
            amount=cls._require(data, "amount"),
            description=cls._require(data, "description"),
            source=data.get("source", IncomeSource.OTHER),
            transaction_date=data.get("date"),
            is_recurring=bool(data.get("is_recurring", False)),
            transaction_id=data.get("transaction_id"),
        )
