"""Runnable demonstration of the day 1 domain model.

Run it from the project root with::

    python -m expense_tracker

Naming the file ``__main__.py`` is what makes ``python -m expense_tracker``
work: Python executes this module when the package is run as a script.

This is a temporary shop window for the model. It is replaced by the real
command line interface later in the week, which is why it lives in one
small function and touches nothing else in the package.
"""

from __future__ import annotations

from decimal import Decimal

from .enums import Category, PaymentMethod
from .exceptions import ValidationError
from .expense import Expense
from .transaction import Transaction


def build_sample_expenses() -> list[Transaction]:
    """Return a few hand written expenses used purely for the demo.

    The return type is annotated as ``list[Transaction]``, not
    ``list[Expense]``. That is deliberate: the code below only relies on the
    base class contract, so it will keep working unchanged once ``Income``
    joins the list later this week. Programming to the abstraction rather
    than the concrete type is what makes that possible.
    """
    return [
        Expense("42.15", "Weekly shop", Category.GROCERIES, "2026-09-14"),
        Expense("3.40", "Flat white", "eating out", "2026-09-15", PaymentMethod.CASH),
        Expense(28, "Rail season top up", Category.TRANSPORT, "2026-09-16"),
        Expense("9.99", "Streaming subscription", Category.ENTERTAINMENT, "2026-09-17",
                PaymentMethod.DIRECT_DEBIT),
    ]


def main() -> None:
    """Print the sample expenses, a total, and one deliberate failure."""
    expenses = build_sample_expenses()

    print("Personal Expense Tracker - day 1 domain model\n")
    print("Recorded expenses")
    print("-" * 64)

    # ``sorted`` works because ``Transaction`` implements ``__lt__``.
    # ``print(expense)`` works because ``__str__`` delegates to
    # ``summary_line``. Neither line needs to know it is holding an Expense.
    for expense in sorted(expenses):
        print(expense)

    # Polymorphism in one line: every transaction knows its own direction.
    total = sum((item.signed_amount for item in expenses), start=Decimal("0.00"))
    print("-" * 64)
    print(f"Net movement: £{total:,.2f}\n")

    # Round trip through the serialisation layer.
    stored = expenses[0].to_dict()
    restored = Expense.from_dict(stored)
    print("Serialisation round trip")
    print("-" * 64)
    print(f"Stored dictionary: {stored}")
    print(f"Restored object equals original: {restored == expenses[0]}\n")

    # Encapsulation in action: the object refuses to become invalid.
    print("Validation")
    print("-" * 64)
    try:
        expenses[0].amount = -10
    except ValidationError as error:
        print(f"Rejected as expected: {error}")
        print(f"Original amount is untouched: £{expenses[0].amount}")


# This guard means the demo runs only when the module is executed directly.
# If another module ever imports this file, nothing is printed.
if __name__ == "__main__":
    main()
