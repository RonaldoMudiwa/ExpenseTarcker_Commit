"""Fixed lists of choices: categories, payment methods and income sources."""

from __future__ import annotations

from enum import Enum, unique
from typing import Any, TypeVar

from .exceptions import ValidationError

_EnumT = TypeVar("_EnumT", bound=Enum)


class _LabelledEnum(str, Enum):
    """Helpers shared by the enums below."""

    @property
    def label(self) -> str:
        """A display name, so "eating_out" reads as "Eating Out"."""
        return self.value.replace("_", " ").title()

    @classmethod
    def from_string(cls, raw: str) -> "_LabelledEnum":
        """Match text like "Eating Out", "eating-out" or "  BILLS ".

        Raises:
            ValidationError: If the text matches nothing, or isn't text.
        """
        if not isinstance(raw, str):
            raise ValidationError(
                f"{cls.__name__} must be created from a string, "
                f"got {type(raw).__name__}."
            )

        # Spaces and hyphens become underscores, so "Eating Out" matches "eating_out".
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
    """How an expense was paid."""

    CASH = "cash"
    DEBIT_CARD = "debit_card"
    CREDIT_CARD = "credit_card"
    BANK_TRANSFER = "bank_transfer"
    DIRECT_DEBIT = "direct_debit"
    OTHER = "other"


@unique
class IncomeSource(_LabelledEnum):
    """Where income came from. Separate from Category so income can't be "Groceries"."""

    SALARY = "salary"
    FREELANCE = "freelance"
    BONUS = "bonus"
    INVESTMENT = "investment"
    INTEREST = "interest"
    REFUND = "refund"
    GIFT = "gift"
    BENEFITS = "benefits"
    OTHER = "other"
