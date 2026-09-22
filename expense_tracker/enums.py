"""Enumerations used across the expense tracker.

An enum is the right tool whenever a field may only hold one of a fixed,
known set of values. Compared with passing raw strings around it gives us:

* a single definition of the allowed values (no typos in "grocries"),
* autocompletion and static checking in editors,
* a natural place to hang behaviour, such as a human readable label.

All enums below inherit from ``str`` as well as ``Enum``. That makes every
member behave like a normal string (so ``json.dumps`` and f-strings just
work) while still being a proper enum member.
"""

from __future__ import annotations

from enum import Enum, unique
from typing import Any, TypeVar

from .exceptions import ValidationError

#: Type variable used by :func:`coerce_enum` so that static type checkers
#: know the function returns a member of the exact enum passed in, not a
#: vague ``Enum``.
_EnumT = TypeVar("_EnumT", bound=Enum)


class _LabelledEnum(str, Enum):
    """Shared behaviour for the enums in this module.

    This class exists purely so that ``Category``, ``PaymentMethod`` and
    ``IncomeSource`` do not duplicate the same two helpers. It is a small
    but real example of inheritance being used to remove duplication, and of
    the DRY principle (Don't Repeat Yourself) applied to code we control.

    It is deliberately private (leading underscore): it is an implementation
    detail of this module, not part of the public API of the package.
    """

    @property
    def label(self) -> str:
        """Return a human readable name, e.g. ``"Eating Out"``.

        Implemented as a property rather than a method because it reads as a
        simple attribute at the call site (``category.label``) and performs
        no meaningful work beyond formatting.
        """
        return self.value.replace("_", " ").title()

    @classmethod
    def from_string(cls, raw: str) -> "_LabelledEnum":
        """Build a member from free text, tolerating case and spacing.

        This is a *factory method*: an alternative constructor that takes
        messy real world input (from a CSV, a form, a command line) and
        returns a valid member, or raises a clear error.

        Args:
            raw: Text such as ``"Eating Out"``, ``"eating_out"`` or ``"  BILLS "``.

        Returns:
            The matching enum member.

        Raises:
            ValidationError: If ``raw`` is not a string or matches no member.
        """
        if not isinstance(raw, str):
            raise ValidationError(
                f"{cls.__name__} must be created from a string, "
                f"got {type(raw).__name__}."
            )

        # Normalise once, then compare. Lowercase, trim, and treat spaces and
        # hyphens as underscores so "Eating Out" and "eating-out" both work.
        normalised = raw.strip().lower().replace(" ", "_").replace("-", "_")

        for member in cls:
            if member.value == normalised:
                return member

        allowed = ", ".join(member.value for member in cls)
        raise ValidationError(
            f"Unknown {cls.__name__.lower()} {raw!r}. Allowed values: {allowed}."
        )

    def __str__(self) -> str:
        """Print the friendly label when the member is shown to a user."""
        return self.label


def coerce_enum(value: Any, enum_class: type[_EnumT]) -> _EnumT:
    """Accept an enum member or text and return a valid member of ``enum_class``.

    Every domain object that stores an enum field needs exactly this logic:
    pass members through untouched, parse strings, reject anything else with
    a consistent message. Writing it once here means ``Expense`` and
    ``Income`` cannot drift apart in how they treat bad input.

    Args:
        value: An existing member, or text such as ``"eating out"``.
        enum_class: The enum the value must belong to.

    Returns:
        A valid member of ``enum_class``.

    Raises:
        ValidationError: If the value is neither a member nor parsable text.
    """
    if isinstance(value, enum_class):
        return value
    if isinstance(value, str):
        return enum_class.from_string(value)  # type: ignore[attr-defined]
    raise ValidationError(
        f"{enum_class.__name__} must be a {enum_class.__name__} member or "
        f"text, got {type(value).__name__}."
    )


@unique  # guarantees no two members share the same value
class Category(_LabelledEnum):
    """The spending categories a single expense can belong to.

    Kept deliberately short for now. Week 1 adds reporting that groups
    expenses by this field, so the list is intended to be stable.
    """

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
    """How an expense was paid for.

    Separate from ``Category`` because the two answer different questions:
    a category says *what the money was for*, a payment method says *where
    the money came from*. Keeping them apart is the Single Responsibility
    Principle applied at the level of data modelling.
    """

    CASH = "cash"
    DEBIT_CARD = "debit_card"
    CREDIT_CARD = "credit_card"
    BANK_TRANSFER = "bank_transfer"
    DIRECT_DEBIT = "direct_debit"
    OTHER = "other"


@unique
class IncomeSource(_LabelledEnum):
    """Where a single piece of income came from.

    Income deliberately does not reuse ``Category``. A category describes
    what money was spent on; a source describes where money arrived from.
    Forcing both through one enum would create members that are nonsense for
    half the code that touches them ("income of category Groceries"), which
    is exactly the kind of leaky model that causes defensive ``if`` checks
    later on.

    Adding this enum, rather than widening an existing one, is the Open
    Closed Principle in practice: the package grows by adding new code, not
    by editing code that already works.
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
