"""Money going out."""

from __future__ import annotations

from datetime import date as date_type
from decimal import Decimal
from typing import Any, Mapping

from .enums import Category, PaymentMethod, coerce_enum
from .transaction import Transaction


class Expense(Transaction):
    """A single purchase or payment.

    Short compared with Transaction, because validating, comparing, hashing
    and saving were all written once in the base class. An expense only adds
    what is actually different: two extra fields, a negative direction, and
    how it prints.

        >>> coffee = Expense("4.00", "Flat white", "eating out", "2026-09-20")
        >>> coffee.amount
        Decimal('4.00')
        >>> coffee.signed_amount
        Decimal('-4.00')
    """

    TRANSACTION_TYPE = "expense"

    def __init__(
        self,
        amount: Decimal | int | float | str,
        description: str,
        category: Category | str = Category.OTHER,
        transaction_date: date_type | str | None = None,
        payment_method: PaymentMethod | str = PaymentMethod.OTHER,
        transaction_id: str | None = None,
    ) -> None:
        """Create an expense.

        Args:
            amount: A positive amount spent.
            description: What the money went on.
            category: A Category member, or text like "eating out".
            transaction_date: Date of the spend. Defaults to today.
            payment_method: A PaymentMethod member, or equivalent text.
            transaction_id: An existing id, used when loading from storage.

        Raises:
            ValidationError: If any argument fails its check.
        """
        # Run the shared validation first. If the base class rejects
        # something, no half built object is left behind.
        super().__init__(
            amount=amount,
            description=description,
            transaction_date=transaction_date,
            transaction_id=transaction_id,
        )

        # Through the properties, so these get validated too.
        self.category = category
        self.payment_method = payment_method

    # ------------------------------------------------------------------
    # Fields
    # ------------------------------------------------------------------

    @property
    def category(self) -> Category:
        """What the money was spent on."""
        return self._category

    @category.setter
    def category(self, value: Category | str) -> None:
        self._category = coerce_enum(value, Category)

    @property
    def payment_method(self) -> PaymentMethod:
        """Which account the money left."""
        return self._payment_method

    @payment_method.setter
    def payment_method(self, value: PaymentMethod | str) -> None:
        self._payment_method = coerce_enum(value, PaymentMethod)

    # ------------------------------------------------------------------
    # The base class contract
    # ------------------------------------------------------------------

    @property
    def signed_amount(self) -> Decimal:
        """Negative, because an expense lowers the balance."""
        return -self.amount

    def summary_line(self) -> str:
        """One line, e.g. "2026-09-18  -£    3.40  Eating Out      Flat white".

        The column widths match Income.summary_line, so a mixed list prints
        as a tidy table with no extra work.
        """
        return (
            f"{self.transaction_date.isoformat()}  "
            f"-£{self.amount:>8,.2f}  "
            f"{self.category.label:<14}  "
            f"{self.description}"
        )

    # ------------------------------------------------------------------
    # Saving and loading
    # ------------------------------------------------------------------

    def _extra_fields(self) -> Mapping[str, Any]:
        """The two keys only an expense has."""
        return {
            "category": self.category.value,
            "payment_method": self.payment_method.value,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "Expense":
        """Rebuild an Expense from what to_dict produced.

        A classmethod, not a staticmethod, because it needs cls to build the
        object. Any future subclass inherits this and gets its own type back.

        Missing optional keys fall back to the same defaults as __init__, so
        a record saved by an older version still loads.

        Raises:
            SerializationError: If amount or description is missing.
            ValidationError: If a stored value is no longer valid.
        """
        return cls(
            amount=cls._require(data, "amount"),
            description=cls._require(data, "description"),
            category=data.get("category", Category.OTHER),
            transaction_date=data.get("date"),
            payment_method=data.get("payment_method", PaymentMethod.OTHER),
            transaction_id=data.get("transaction_id"),
        )
