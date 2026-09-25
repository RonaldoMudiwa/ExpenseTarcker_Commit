"""Filters for picking out transactions.

Each filter asks one yes or no question. Join them with & (and), | (or)
and ~ (not):

    ledger.filter_by(DateRangeFilter.for_month(2026, 9) & CategoryFilter("groceries"))
"""

from __future__ import annotations

import calendar
from abc import ABC, abstractmethod
from datetime import date as date_type
from decimal import Decimal, InvalidOperation

from .enums import Category, IncomeSource, coerce_enum
from .exceptions import ValidationError
from .expense import Expense
from .income import Income
from .transaction import Transaction


class TransactionFilter(ABC):
    """A yes or no question about a transaction.

    Subclasses only need matches(). &, | and ~ come from here.
    """

    @abstractmethod
    def matches(self, transaction: Transaction) -> bool:
        """True if the transaction passes this filter."""

    def __call__(self, transaction: Transaction) -> bool:
        # So a filter can be passed anywhere a function is expected.
        return self.matches(transaction)

    def __and__(self, other: "TransactionFilter") -> "TransactionFilter":
        if not isinstance(other, TransactionFilter):
            return NotImplemented
        return AndFilter(self, other)

    def __or__(self, other: "TransactionFilter") -> "TransactionFilter":
        if not isinstance(other, TransactionFilter):
            return NotImplemented
        return OrFilter(self, other)

    def __invert__(self) -> "TransactionFilter":
        return NotFilter(self)


# ----------------------------------------------------------------------
# Joining filters
# ----------------------------------------------------------------------


class AndFilter(TransactionFilter):
    """Passes only if both filters pass."""

    def __init__(self, left: TransactionFilter, right: TransactionFilter) -> None:
        self._left = left
        self._right = right

    def matches(self, transaction: Transaction) -> bool:
        return self._left.matches(transaction) and self._right.matches(transaction)

    def __repr__(self) -> str:
        return f"({self._left!r} & {self._right!r})"


class OrFilter(TransactionFilter):
    """Passes if either filter passes."""

    def __init__(self, left: TransactionFilter, right: TransactionFilter) -> None:
        self._left = left
        self._right = right

    def matches(self, transaction: Transaction) -> bool:
        return self._left.matches(transaction) or self._right.matches(transaction)

    def __repr__(self) -> str:
        return f"({self._left!r} | {self._right!r})"


class NotFilter(TransactionFilter):
    """Passes when the inner filter fails."""

    def __init__(self, inner: TransactionFilter) -> None:
        self._inner = inner

    def matches(self, transaction: Transaction) -> bool:
        return not self._inner.matches(transaction)

    def __repr__(self) -> str:
        return f"~{self._inner!r}"


# ----------------------------------------------------------------------
# The filters themselves
# ----------------------------------------------------------------------


class DateRangeFilter(TransactionFilter):
    """Between two dates, both days included. Either end can be left out."""

    def __init__(
        self,
        start: date_type | str | None = None,
        end: date_type | str | None = None,
    ) -> None:
        self._start = self._to_date(start)
        self._end = self._to_date(end)

        if self._start and self._end and self._start > self._end:
            raise ValidationError(
                f"Start date {self._start} is after end date {self._end}."
            )

    @classmethod
    def for_month(cls, year: int, month: int) -> "DateRangeFilter":
        """The whole of one month, e.g. for_month(2026, 2)."""
        if not 1 <= month <= 12:
            raise ValidationError(f"Month must be 1 to 12, got {month}.")
        # Handles February in leap years for us.
        last_day = calendar.monthrange(year, month)[1]
        return cls(date_type(year, month, 1), date_type(year, month, last_day))

    @staticmethod
    def _to_date(value: date_type | str | None) -> date_type | None:
        if value is None or isinstance(value, date_type):
            return value
        if isinstance(value, str):
            try:
                return date_type.fromisoformat(value.strip())
            except ValueError as error:
                raise ValidationError(
                    f"Date {value!r} is not in YYYY-MM-DD format."
                ) from error
        raise ValidationError(f"Date must be a date or text, got {type(value).__name__}.")

    @property
    def start(self) -> date_type | None:
        return self._start

    @property
    def end(self) -> date_type | None:
        return self._end

    def matches(self, transaction: Transaction) -> bool:
        day = transaction.transaction_date
        if self._start and day < self._start:
            return False
        if self._end and day > self._end:
            return False
        return True

    def __repr__(self) -> str:
        return f"DateRangeFilter(start={self._start}, end={self._end})"


class CategoryFilter(TransactionFilter):
    """Expenses in any of these categories. Income never matches."""

    def __init__(self, *categories: Category | str) -> None:
        if not categories:
            raise ValidationError("Give at least one category.")
        self._categories = frozenset(coerce_enum(c, Category) for c in categories)

    def matches(self, transaction: Transaction) -> bool:
        return isinstance(transaction, Expense) and transaction.category in self._categories

    def __repr__(self) -> str:
        names = ", ".join(sorted(c.value for c in self._categories))
        return f"CategoryFilter({names})"


class IncomeSourceFilter(TransactionFilter):
    """Income from any of these sources. Expenses never match."""

    def __init__(self, *sources: IncomeSource | str) -> None:
        if not sources:
            raise ValidationError("Give at least one income source.")
        self._sources = frozenset(coerce_enum(s, IncomeSource) for s in sources)

    def matches(self, transaction: Transaction) -> bool:
        return isinstance(transaction, Income) and transaction.source in self._sources

    def __repr__(self) -> str:
        names = ", ".join(sorted(s.value for s in self._sources))
        return f"IncomeSourceFilter({names})"


class TypeFilter(TransactionFilter):
    """Only one kind of transaction, e.g. TypeFilter(Expense)."""

    def __init__(self, transaction_class: type[Transaction]) -> None:
        if not (isinstance(transaction_class, type)
                and issubclass(transaction_class, Transaction)):
            raise ValidationError("TypeFilter needs a Transaction class.")
        self._class = transaction_class

    def matches(self, transaction: Transaction) -> bool:
        return isinstance(transaction, self._class)

    def __repr__(self) -> str:
        return f"TypeFilter({self._class.__name__})"


class AmountRangeFilter(TransactionFilter):
    """Amounts between two values, both included."""

    def __init__(
        self,
        minimum: Decimal | int | str | None = None,
        maximum: Decimal | int | str | None = None,
    ) -> None:
        self._minimum = self._to_decimal(minimum)
        self._maximum = self._to_decimal(maximum)

        if (self._minimum is not None and self._maximum is not None
                and self._minimum > self._maximum):
            raise ValidationError(
                f"Minimum {self._minimum} is bigger than maximum {self._maximum}."
            )

    @staticmethod
    def _to_decimal(value: Decimal | int | str | None) -> Decimal | None:
        if value is None:
            return None
        # Floats aren't exact enough for money, and True counts as 1 in Python.
        if isinstance(value, (bool, float)):
            raise ValidationError("Use a whole number, text or Decimal for amounts.")
        try:
            return Decimal(str(value).strip())
        except InvalidOperation as error:
            raise ValidationError(f"Amount {value!r} is not a number.") from error

    def matches(self, transaction: Transaction) -> bool:
        amount = transaction.amount
        if self._minimum is not None and amount < self._minimum:
            return False
        if self._maximum is not None and amount > self._maximum:
            return False
        return True

    def __repr__(self) -> str:
        return f"AmountRangeFilter(minimum={self._minimum}, maximum={self._maximum})"


class TextSearchFilter(TransactionFilter):
    """Descriptions containing the text, any case. "tesco" finds "TESCO"."""

    def __init__(self, text: str) -> None:
        if not isinstance(text, str) or not text.strip():
            raise ValidationError("Search text cannot be empty.")
        # casefold is a stronger lower() that also works for other languages.
        self._needle = text.strip().casefold()

    def matches(self, transaction: Transaction) -> bool:
        return self._needle in transaction.description.casefold()

    def __repr__(self) -> str:
        return f"TextSearchFilter({self._needle!r})"


class MatchAll(TransactionFilter):
    """Lets everything through."""

    def matches(self, transaction: Transaction) -> bool:
        return True

    def __repr__(self) -> str:
        return "MatchAll()"


def all_of(*filters: TransactionFilter) -> TransactionFilter:
    """Join any number of filters with "and". None given matches everything."""
    combined: TransactionFilter = MatchAll()
    for extra in filters:
        combined = combined & extra
    return combined
