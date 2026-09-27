"""Totals and summaries worked out from a ledger.

ReportGenerator does the maths and returns plain data. ReportFormatter
turns that data into text. Keeping them apart means the command line,
a CSV export or a web page later can all use the same numbers.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Iterator

from .enums import Category, IncomeSource, coerce_enum
from .exceptions import ValidationError
from .expense import Expense
from .filters import DateRangeFilter
from .income import Income
from .ledger import TransactionLedger

ZERO = Decimal("0.00")


def _to_money(value: Decimal | int | str) -> Decimal:
    """Turn a limit like "200" into Decimal("200.00"). Must be above zero."""
    # Floats aren't exact enough for money, and True counts as 1 in Python.
    if isinstance(value, (bool, float)):
        raise ValidationError("Use a whole number, text or Decimal for amounts.")
    try:
        amount = Decimal(str(value).strip())
    except InvalidOperation as error:
        raise ValidationError(f"Amount {value!r} is not a number.") from error
    if not amount.is_finite() or amount <= 0:
        raise ValidationError(f"Amount must be greater than zero, got {value!r}.")
    return amount.quantize(Decimal("0.01"))


# ----------------------------------------------------------------------
# Results
# ----------------------------------------------------------------------


@dataclass(frozen=True)
class MonthSummary:
    """Money in and out for one calendar month."""

    year: int
    month: int
    income: Decimal
    expenses: Decimal

    @property
    def net(self) -> Decimal:
        """Positive means you saved money that month."""
        return self.income - self.expenses

    @property
    def label(self) -> str:
        return f"{self.year}-{self.month:02d}"


@dataclass(frozen=True)
class BudgetStatus:
    """How one category is doing against its limit."""

    category: Category
    limit: Decimal
    spent: Decimal

    @property
    def remaining(self) -> Decimal:
        """Negative when over budget."""
        return self.limit - self.spent

    @property
    def percent_used(self) -> Decimal:
        return (self.spent / self.limit * 100).quantize(Decimal("0.1"))

    @property
    def is_over(self) -> bool:
        return self.spent > self.limit


# ----------------------------------------------------------------------
# Budget
# ----------------------------------------------------------------------


class Budget:
    """Monthly spending limits, one per category.

        >>> budget = Budget({"groceries": "250", "eating out": "60"})
        >>> budget.limit_for(Category.GROCERIES)
        Decimal('250.00')
    """

    def __init__(self, limits: dict[Category | str, Decimal | int | str] | None = None) -> None:
        self._limits: dict[Category, Decimal] = {}
        for category, amount in (limits or {}).items():
            self.set_limit(category, amount)

    def set_limit(self, category: Category | str, amount: Decimal | int | str) -> None:
        """Add or change the limit for one category."""
        self._limits[coerce_enum(category, Category)] = _to_money(amount)

    def remove_limit(self, category: Category | str) -> None:
        self._limits.pop(coerce_enum(category, Category), None)

    def limit_for(self, category: Category | str) -> Decimal | None:
        """The limit, or None if this category has no budget."""
        return self._limits.get(coerce_enum(category, Category))

    def __iter__(self) -> Iterator[tuple[Category, Decimal]]:
        return iter(self._limits.items())

    def __len__(self) -> int:
        return len(self._limits)

    def __repr__(self) -> str:
        return f"Budget({ {c.value: str(a) for c, a in self._limits.items()} })"


# ----------------------------------------------------------------------
# Working out the numbers
# ----------------------------------------------------------------------


class ReportGenerator:
    """Answers questions about a ledger. Never changes it."""

    def __init__(self, ledger: TransactionLedger) -> None:
        self._ledger = ledger

    def spending_by_category(self) -> dict[Category, Decimal]:
        """Total spent per category, biggest first."""
        totals: dict[Category, Decimal] = defaultdict(lambda: ZERO)
        for transaction in self._ledger.of_type(Expense):
            totals[transaction.category] += transaction.amount
        return dict(sorted(totals.items(), key=lambda item: item[1], reverse=True))

    def income_by_source(self) -> dict[IncomeSource, Decimal]:
        """Total received per source, biggest first."""
        totals: dict[IncomeSource, Decimal] = defaultdict(lambda: ZERO)
        for transaction in self._ledger.of_type(Income):
            totals[transaction.source] += transaction.amount
        return dict(sorted(totals.items(), key=lambda item: item[1], reverse=True))

    def monthly_breakdown(self) -> list[MonthSummary]:
        """One summary per month that has any transactions, oldest first."""
        income: dict[tuple[int, int], Decimal] = defaultdict(lambda: ZERO)
        expenses: dict[tuple[int, int], Decimal] = defaultdict(lambda: ZERO)

        for transaction in self._ledger:
            key = (transaction.transaction_date.year, transaction.transaction_date.month)
            # signed_amount tells us the direction without checking the type.
            if transaction.signed_amount > 0:
                income[key] += transaction.amount
            else:
                expenses[key] += transaction.amount

        months = sorted(set(income) | set(expenses))
        return [
            MonthSummary(year, month, income[(year, month)], expenses[(year, month)])
            for year, month in months
        ]

    def recurring_income(self) -> Decimal:
        """Income marked as recurring, e.g. salary. Useful for planning."""
        return sum(
            (t.amount for t in self._ledger.of_type(Income) if t.is_recurring),
            start=ZERO,
        )

    def check_budget(self, budget: Budget, year: int, month: int) -> list[BudgetStatus]:
        """Compare one month's spending with the budget, worst first."""
        month_ledger = self._ledger.filter_by(DateRangeFilter.for_month(year, month))
        spent = ReportGenerator(month_ledger).spending_by_category()

        statuses = [
            BudgetStatus(category, limit, spent.get(category, ZERO))
            for category, limit in budget
        ]
        return sorted(statuses, key=lambda s: s.percent_used, reverse=True)


# ----------------------------------------------------------------------
# Turning the numbers into text
# ----------------------------------------------------------------------


class ReportFormatter:
    """Plain text tables for the terminal."""

    WIDTH = 44

    def category_table(self, totals: dict[Category, Decimal]) -> str:
        if not totals:
            return "No spending to report."
        grand_total = sum(totals.values(), start=ZERO)
        lines = [f"{'Category':<16}{'Spent':>12}{'Share':>9}", "-" * self.WIDTH]
        for category, amount in totals.items():
            share = amount / grand_total * 100
            lines.append(f"{category.label:<16}£{amount:>11,.2f}{share:>8.1f}%")
        lines.append("-" * self.WIDTH)
        lines.append(f"{'Total':<16}£{grand_total:>11,.2f}")
        return "\n".join(lines)

    def source_table(self, totals: dict[IncomeSource, Decimal]) -> str:
        if not totals:
            return "No income to report."
        lines = [f"{'Source':<16}{'Received':>12}", "-" * self.WIDTH]
        for source, amount in totals.items():
            lines.append(f"{source.label:<16}£{amount:>11,.2f}")
        return "\n".join(lines)

    def monthly_table(self, months: list[MonthSummary]) -> str:
        if not months:
            return "No transactions to report."
        lines = [
            f"{'Month':<9}{'In':>11}{'Out':>12}{'Net':>12}",
            "-" * self.WIDTH,
        ]
        for m in months:
            lines.append(
                f"{m.label:<9}£{m.income:>10,.2f} £{m.expenses:>10,.2f} "
                f"{self._signed(m.net):>11}"
            )
        return "\n".join(lines)

    def budget_table(self, statuses: list[BudgetStatus]) -> str:
        if not statuses:
            return "No budget limits set."
        lines = [
            f"{'Category':<16}{'Spent':>11}{'Limit':>12}{'Used':>9}",
            "-" * 54,
        ]
        for s in statuses:
            flag = "  OVER" if s.is_over else ""
            lines.append(
                f"{s.category.label:<16}£{s.spent:>10,.2f}  £{s.limit:>9,.2f}"
                f"{s.percent_used:>8}%{flag}"
            )
        return "\n".join(lines)

    @staticmethod
    def _signed(amount: Decimal) -> str:
        sign = "-" if amount < 0 else "+"
        return f"{sign}£{abs(amount):,.2f}"
