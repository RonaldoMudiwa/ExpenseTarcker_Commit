"""Fixed sets of values: spending categories, payment methods, income sources.

Each one inherits from str as well as Enum, so members behave like normal
strings and json.dumps handles them without any extra work.
"""

from __future__ import annotations

from enum import Enum, unique
from typing import Any, TypeVar

from .exceptions import ValidationError

_EnumT = TypeVar("_EnumT", bound=Enum)


class _LabelledEnum(str, Enum):
    """Shared helpers for the enums below, so they aren't written three times.

    Private because it is a detail of this module, not part of the package's
    public API.
    """

    @property
    def label(self) -> str:
        """A display name, so "eating_out" reads as "Eating Out"."""
        return self.value.replace("_", " ").title()

    @classmethod
    def from_string(cls, raw: str) -> "_LabelledEnum":
        """Build a member from messy text, ignoring case and separators.

        Handles input from CSV files, forms and the command line, where
        nobody types "eating_out" exactly.

        Args:
            raw: Text such as "Eating Out", "eating-out" or "  BILLS ".

        Returns:
            The matching member.

        Raises:
            ValidationError: If the text matches nothing, or isn't text.
        """
        if not isinstance(raw, str):
            raise ValidationError(
                f"{cls.__name__} must be created from a string, "
                f"got {type(raw).__name__}."
            )

        # Tidy the input once, then compare. Spaces and hyphens both become
        # underscores so "Eating Out" and "eating-out" reach the same member.
        normalised = raw.strip().lower().replace(" ", "_").replace("-", "_")

        for member in cls:
            if member.value == normalised:
                return member

        allowed = ", ".join(member.value for member in cls)
        raise ValidationError(
            f"Unknown {cls.__name__.lower()} {raw!r}. Allowed values: {allowed}."
        )

    def __str__(self) -> str:
        """Show the friendly label when printed."""
        return self.label


def coerce_enum(value: Any, enum_class: type[_EnumT]) -> _EnumT:
    """Turn a member or a piece of text into a member of enum_class.

    Every class that stores an enum field needs this same logic, so it lives
    here once. That way Expense and Income can't drift apart in how they
    handle bad input.

    Raises:
        ValidationError: If the value is neither a member nor usable text.
    """
    if isinstance(value, enum_class):
        return value
    if isinstance(value, str):
        return enum_class.from_string(value)  # type: ignore[attr-defined]
    raise ValidationError(
        f"{enum_class.__name__} must be a {enum_class.__name__} member or "
        f"text, got {type(value).__name__}."
    )


@unique  # stops two members sharing a value
class Category(_LabelledEnum):
    """What an expense was spent on."""

    GROCERIES = "groceries"
    EATING_OUT = "eating_out"
    TRANSPORT = "transport"
    HOUSING = "housing"
    BILLS = "bills"
    HEALTH = "health"
    ENTERTAINMENT = "entertainment"
    EDUCATION = "education"
    SHOPPING = "shopping"
    SAVINGS = "savings"
    OTHER = "other"


@unique
class PaymentMethod(_LabelledEnum):
    """Where the money for an expense came from.

    Kept apart from Category because the two answer different questions:
    what the money was for, versus which account it left.
    """

    CASH = "cash"
    DEBIT_CARD = "debit_card"
    CREDIT_CARD = "credit_card"
    BANK_TRANSFER = "bank_transfer"
    DIRECT_DEBIT = "direct_debit"
    OTHER = "other"


@unique
class IncomeSource(_LabelledEnum):
    """Where a payment came from.

    Income gets its own enum rather than reusing Category. Sharing one would
    allow nonsense like "income of category Groceries", and every report
    would then need guard clauses to filter it out.
    """

    SALARY = "salary"
    FREELANCE = "freelance"
    BONUS = "bonus"
    INVESTMENT = "investment"
    INTEREST = "interest"
    REFUND = "refund"
    GIFT = "gift"
    BENEFITS = "benefits"
    OTHER = "other"
