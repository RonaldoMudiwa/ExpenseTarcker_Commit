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

    Worth noticing what isn't here. No amount parsing, no date parsing, no
    equality, no hashing, no to_dict. All inherited. Only the parts that are
    genuinely different about income are written below, which is the test of
    whether the base class was drawn in the right place.

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
        """Create an income entry.

        The amount is stored positive, same as an expense. Direction lives in
        signed_amount, not in the sign of the stored number. If it lived in
        the sign, validation could no longer simply reject anything below
        zero, and every report would have to work out whether a negative
        income meant a correction or a mistake.

        Args:
            amount: A positive amount received.
            description: Short label, e.g. "September salary".
            source: An IncomeSource member, or text like "salary".
            transaction_date: Date received. Defaults to today.
            is_recurring: True for regular income such as a monthly salary.
                Day 5's reporting uses this to separate dependable income
                from one off payments.
            transaction_id: An existing id, used when loading from storage.

        Raises:
            ValidationError: If any argument fails its check.
        """
        # Base class first, so nothing is half built if a check fails.
        # Keyword arguments, so a change to the base signature can't
        # silently bind these to the wrong parameters.
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
        # A plain truthiness check would accept "no", 0.0 and [] and store
        # the wrong thing without complaining. Demanding a real bool turns a
        # caller's slip into an obvious error.
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
        """Positive, because income raises the balance.

        This one line is why the ledger can total a mixed list without ever
        checking what type anything is.
        """
        return self.amount

    def summary_line(self) -> str:
        """One line, e.g. "2026-09-25  +£2,400.00  Salary          Pay".

        Column widths match Expense.summary_line so mixed lists line up.
        """
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

        Amount and description must be present, since income with no amount
        is corrupt rather than incomplete. Everything else falls back to the
        same defaults as __init__, so older records still load.

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
