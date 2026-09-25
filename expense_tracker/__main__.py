"""A quick demo of what the model can do so far.

Run it from the project root:

    python -m expense_tracker

The file has to be called __main__.py for that command to work: Python runs
this module when the package is executed as a script.

Temporary. The real command line interface replaces it on Day 6, which is why
it stays in small functions and touches nothing else.
"""

from __future__ import annotations

from .enums import Category, IncomeSource, PaymentMethod
from .exceptions import DuplicateTransactionError, TransactionNotFoundError
from .expense import Expense
from .income import Income
from .ledger import TransactionLedger
from .repository import JSONTransactionRepository

# Relative to the project root, where the command is run from.
DATA_FILE = "data/transactions.json"


def build_sample_ledger() -> TransactionLedger:
    """A month of made up transactions.

    The list mixes Income and Expense freely, and nothing below ever asks
    which is which.
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


def show_transactions(ledger: TransactionLedger) -> None:
    """Print every transaction, each formatting itself."""
    print("All transactions")
    print("-" * 64)
    print(ledger)


def show_container_behaviour(ledger: TransactionLedger) -> None:
    """Show that the ledger works like any other Python sequence."""
    print("\nContainer behaviour")
    print("-" * 64)
    print(f"len(ledger)          -> {len(ledger)}")
    print(f"ledger[0]            -> {ledger[0].description}")
    print(f"ledger[-1]           -> {ledger[-1].description}")
    print(f"first three, sliced  -> {len(ledger[:3])} transactions")
    print(f"ledger[0] in ledger  -> {ledger[0] in ledger}")
    print(f"sorted by date       -> {sorted(ledger)[0].transaction_date}")
    print(f"repr(ledger)         -> {ledger!r}")


def show_totals(ledger: TransactionLedger) -> None:
    """Show the totals, worked out with no type checks anywhere."""
    print("\nSummary")
    print("-" * 64)
    print(ledger.summary())

    recurring = ledger.filter_by(lambda t: getattr(t, "is_recurring", False))
    print(f"\nReliable monthly income: £{recurring.total_income:,.2f}")

    groceries = ledger.filter_by(
        lambda t: getattr(t, "category", None) is Category.GROCERIES
    )
    print(f"Spent on groceries:      £{groceries.total_expenses:,.2f}")


def show_guard_rails(ledger: TransactionLedger) -> None:
    """Show the ledger refusing to end up in a broken state."""
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


def show_storage(ledger: TransactionLedger) -> None:
    """Save to a file, load it back, and check nothing changed."""
    print("\nSaving and loading")
    print("-" * 64)

    repository = JSONTransactionRepository(DATA_FILE)
    repository.save(ledger)
    print(f"Saved {len(ledger)} transactions to {repository.path}")

    reloaded = repository.load()
    print(f"Loaded {len(reloaded)} transactions back")
    print(f"Same balance after reload: {reloaded.balance == ledger.balance}")
    print(f"Same transactions after reload: {list(reloaded) == list(ledger)}")


def main() -> None:
    """Run each demo in turn."""
    ledger = build_sample_ledger()
    show_transactions(ledger)
    show_container_behaviour(ledger)
    show_totals(ledger)
    show_guard_rails(ledger)
    show_storage(ledger)


# Without this guard, importing the module would run the demo.
if __name__ == "__main__":
    main()
