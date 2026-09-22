"""Runnable demonstration of the Day 2 domain model.

Run it from the project root with::

    python -m expense_tracker

Naming the file ``__main__.py`` is what makes ``python -m expense_tracker``
work: Python executes this module when the package is run as a script.

This is a temporary shop window for the model. It is replaced by the real
command line interface on Day 6, which is why it lives in a few small
functions and touches nothing else in the package.
"""

from __future__ import annotations

from .enums import Category, IncomeSource, PaymentMethod
from .exceptions import DuplicateTransactionError, TransactionNotFoundError
from .expense import Expense
from .income import Income
from .ledger import TransactionLedger


def build_sample_ledger() -> TransactionLedger:
    """Return a ledger of hand written transactions used purely for the demo.

    The list passed in mixes ``Expense`` and ``Income`` freely. Nothing in
    the ledger, and nothing below, ever asks which is which.
    """
    return TransactionLedger(
        [
            Income("2400.00", "September salary", IncomeSource.SALARY,
                   "2026-09-01", is_recurring=True),
            Expense("875.00", "Rent", Category.HOUSING,
                    "2026-09-02", PaymentMethod.BANK_TRANSFER),
            Expense("62.35", "Weekly shop", Category.GROCERIES,
                    "2026-09-03", PaymentMethod.DEBIT_CARD),
            Income("180.00", "Tutoring, four sessions", IncomeSource.FREELANCE,
                   "2026-09-07"),
            Expense("3.40", "Flat white", Category.EATING_OUT,
                    "2026-09-08", PaymentMethod.CASH),
            Expense("41.20", "Train season top up", Category.TRANSPORT,
                    "2026-09-09", PaymentMethod.DEBIT_CARD),
            Income("24.99", "Returned headphones", IncomeSource.REFUND,
                   "2026-09-11"),
        ]
    )


def demonstrate_polymorphism(ledger: TransactionLedger) -> None:
    """Print each transaction using the object's own formatting."""
    print("All transactions")
    print("-" * 64)
    print(ledger)  # __str__ calls summary_line on each member


def demonstrate_container_protocol(ledger: TransactionLedger) -> None:
    """Show that the ledger behaves like any other Python sequence."""
    print("\nContainer behaviour")
    print("-" * 64)
    print(f"len(ledger)          -> {len(ledger)}")
    print(f"ledger[0]            -> {ledger[0].description}")
    print(f"ledger[-1]           -> {ledger[-1].description}")
    print(f"first three, sliced  -> {len(ledger[:3])} transactions")
    print(f"ledger[0] in ledger  -> {ledger[0] in ledger}")
    print(f"sorted by date       -> {sorted(ledger)[0].transaction_date}")
    print(f"repr(ledger)         -> {ledger!r}")


def demonstrate_aggregates(ledger: TransactionLedger) -> None:
    """Show the totals, computed without a single type check."""
    print("\nSummary")
    print("-" * 64)
    print(ledger.summary())

    recurring = ledger.filter_by(lambda t: getattr(t, "is_recurring", False))
    print(f"\nReliable monthly income: £{recurring.total_income:,.2f}")

    groceries = ledger.filter_by(
        lambda t: getattr(t, "category", None) is Category.GROCERIES
    )
    print(f"Spent on groceries:      £{groceries.total_expenses:,.2f}")


def demonstrate_error_handling(ledger: TransactionLedger) -> None:
    """Show that the ledger refuses to enter an invalid state."""
    print("\nGuard rails")
    print("-" * 64)

    try:
        ledger.add(ledger[0])  # same object, same id
    except DuplicateTransactionError as exc:
        print(f"Duplicate rejected: {exc}")

    try:
        ledger.remove("not-a-real-id")
    except TransactionNotFoundError as exc:
        print(f"Missing id rejected: {exc}")


def main() -> None:
    """Run every demonstration in order."""
    ledger = build_sample_ledger()
    demonstrate_polymorphism(ledger)
    demonstrate_container_protocol(ledger)
    demonstrate_aggregates(ledger)
    demonstrate_error_handling(ledger)


# The standard guard. It means importing this module (for example, by a test)
# does not run the demo, while executing the package still does.
if __name__ == "__main__":
    main()
