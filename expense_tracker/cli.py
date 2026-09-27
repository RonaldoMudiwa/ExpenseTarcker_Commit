"""The command line interface.

Examples, run from the project root:

    python -m expense_tracker add-expense 3.40 "Flat white" -c "eating out"
    python -m expense_tracker add-income 2400 "Salary" -s salary --recurring
    python -m expense_tracker list --month 2026-09 --category groceries
    python -m expense_tracker report monthly
    python -m expense_tracker budget 2026-09 --limit groceries=250

Run with --help, or any command with --help, to see every option.
"""

from __future__ import annotations

import argparse
import logging
import sys
from typing import Sequence, TextIO

from .enums import Category, IncomeSource, PaymentMethod
from .exceptions import ExpenseTrackerError, ValidationError
from .expense import Expense
from .filters import (
    AmountRangeFilter,
    CategoryFilter,
    DateRangeFilter,
    IncomeSourceFilter,
    TextSearchFilter,
    TransactionFilter,
    TypeFilter,
    all_of,
)
from .income import Income
from .ledger import TransactionLedger
from .reports import Budget, ReportFormatter, ReportGenerator
from .repository import JSONTransactionRepository, TransactionRepository

DEFAULT_DATA_FILE = "data/transactions.json"

logger = logging.getLogger(__name__)


def sample_transactions() -> list[Expense | Income]:
    """A made up month of data, used by the demo command."""
    return [
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
        Income("24.99", "Returned headphones", IncomeSource.REFUND, "2026-09-11"),
        Expense("48.10", "Big shop", Category.GROCERIES,
                "2026-09-17", PaymentMethod.DEBIT_CARD),
        Expense("62.00", "Phone and broadband", Category.BILLS,
                "2026-09-20", PaymentMethod.DIRECT_DEBIT),
    ]


def parse_month(text: str) -> tuple[int, int]:
    """Turn "2026-09" into (2026, 9)."""
    try:
        year_text, month_text = text.strip().split("-")
        year, month = int(year_text), int(month_text)
    except ValueError as error:
        raise ValidationError(f"Month {text!r} should look like 2026-09.") from error
    if not 1 <= month <= 12:
        raise ValidationError(f"Month {text!r} should look like 2026-09.")
    return year, month


class ExpenseTrackerCLI:
    """Reads the command, does the work, prints the result.

    The storage and output are passed in, so tests can use an in-memory
    repository and capture what gets printed.
    """

    def __init__(self, repository: TransactionRepository, out: TextIO | None = None) -> None:
        self._repository = repository
        self._out = out or sys.stdout
        self._formatter = ReportFormatter()

    # ------------------------------------------------------------------
    # Commands
    # ------------------------------------------------------------------

    def add_expense(self, args: argparse.Namespace) -> None:
        expense = Expense(args.amount, args.description, args.category,
                          args.date, args.method)
        self._add(expense)

    def add_income(self, args: argparse.Namespace) -> None:
        income = Income(args.amount, args.description, args.source,
                        args.date, is_recurring=args.recurring)
        self._add(income)

    def remove(self, args: argparse.Namespace) -> None:
        ledger = self._repository.load()
        removed = ledger.remove(ledger.resolve_id(args.id))
        self._repository.save(ledger)
        self._print(f"Removed: {removed.summary_line()}")

    def list(self, args: argparse.Namespace) -> None:
        ledger = self._filtered(args)
        if not ledger:
            self._print("No transactions match.")
            return
        for transaction in sorted(ledger):
            # The first 8 characters of the id are enough to remove it later.
            self._print(f"{transaction.transaction_id[:8]}  {transaction.summary_line()}")

    def summary(self, args: argparse.Namespace) -> None:
        self._print(self._filtered(args).summary())

    def report(self, args: argparse.Namespace) -> None:
        report = ReportGenerator(self._filtered(args))
        if args.kind == "categories":
            self._print(self._formatter.category_table(report.spending_by_category()))
        elif args.kind == "sources":
            self._print(self._formatter.source_table(report.income_by_source()))
        else:
            self._print(self._formatter.monthly_table(report.monthly_breakdown()))

    def budget(self, args: argparse.Namespace) -> None:
        year, month = parse_month(args.month)
        budget = Budget()
        for item in args.limit:
            category, _, amount = item.partition("=")
            if not amount:
                raise ValidationError(f"Limit {item!r} should look like groceries=250.")
            budget.set_limit(category, amount)

        statuses = ReportGenerator(self._repository.load()).check_budget(budget, year, month)
        self._print(f"Budget for {year}-{month:02d}")
        self._print(self._formatter.budget_table(statuses))

    def demo(self, args: argparse.Namespace) -> None:
        ledger = self._repository.load()
        if ledger and not args.force:
            raise ValidationError(
                "The data file already has transactions. Use --force to add the demo ones anyway."
            )
        ledger.extend(sample_transactions())
        self._repository.save(ledger)
        self._print(f"Added {len(sample_transactions())} sample transactions.")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _add(self, transaction: Expense | Income) -> None:
        ledger = self._repository.load()
        ledger.add(transaction)
        self._repository.save(ledger)
        logger.debug("Added %s", transaction.transaction_id)
        self._print(f"Added: {transaction.summary_line()}")

    def _filtered(self, args: argparse.Namespace) -> TransactionLedger:
        return self._repository.load().filter_by(build_filter(args))

    def _print(self, text: str) -> None:
        print(text, file=self._out)


def build_filter(args: argparse.Namespace) -> TransactionFilter:
    """Turn the filter options the user typed into one combined filter."""
    chosen: list[TransactionFilter] = []

    if args.month:
        chosen.append(DateRangeFilter.for_month(*parse_month(args.month)))
    if args.date_from or args.date_to:
        chosen.append(DateRangeFilter(args.date_from, args.date_to))
    if args.category:
        chosen.append(CategoryFilter(*args.category))
    if args.source:
        chosen.append(IncomeSourceFilter(*args.source))
    if args.type:
        chosen.append(TypeFilter(Expense if args.type == "expense" else Income))
    if args.search:
        chosen.append(TextSearchFilter(args.search))
    if args.min is not None or args.max is not None:
        chosen.append(AmountRangeFilter(args.min, args.max))

    return all_of(*chosen)


# ----------------------------------------------------------------------
# Setting up the parser
# ----------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="expense_tracker",
        description="Track your spending and income from the command line.",
    )
    parser.add_argument("--file", default=DEFAULT_DATA_FILE,
                        help=f"where to keep your data (default: {DEFAULT_DATA_FILE})")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="show extra detail about what the program is doing")

    # Shared by every command that shows data, so they all filter the same way.
    filters = argparse.ArgumentParser(add_help=False)
    group = filters.add_argument_group("filters")
    group.add_argument("--month", help="one month, e.g. 2026-09")
    group.add_argument("--from", dest="date_from", help="start date, e.g. 2026-09-01")
    group.add_argument("--to", dest="date_to", help="end date, e.g. 2026-09-30")
    group.add_argument("--category", action="append",
                       help="expense category (repeat for more than one)")
    group.add_argument("--source", action="append",
                       help="income source (repeat for more than one)")
    group.add_argument("--type", choices=["expense", "income"])
    group.add_argument("--search", help="text in the description")
    group.add_argument("--min", help="smallest amount")
    group.add_argument("--max", help="largest amount")

    commands = parser.add_subparsers(dest="command", required=True, metavar="COMMAND")

    add_expense = commands.add_parser("add-expense", help="record money going out")
    add_expense.add_argument("amount")
    add_expense.add_argument("description")
    add_expense.add_argument("-c", "--category", default=Category.OTHER.value,
                             help="e.g. groceries, bills, 'eating out'")
    add_expense.add_argument("-d", "--date", help="YYYY-MM-DD, default today")
    add_expense.add_argument("-m", "--method", default=PaymentMethod.OTHER.value,
                             help="e.g. cash, 'debit card'")

    add_income = commands.add_parser("add-income", help="record money coming in")
    add_income.add_argument("amount")
    add_income.add_argument("description")
    add_income.add_argument("-s", "--source", default=IncomeSource.OTHER.value,
                            help="e.g. salary, freelance, refund")
    add_income.add_argument("-d", "--date", help="YYYY-MM-DD, default today")
    add_income.add_argument("--recurring", action="store_true",
                            help="it happens every month, like a salary")

    remove = commands.add_parser("remove", help="delete a transaction by id")
    remove.add_argument("id", help="the id shown by 'list', or its first few characters")

    commands.add_parser("list", parents=[filters], help="show transactions")
    commands.add_parser("summary", parents=[filters], help="show totals and balance")

    report = commands.add_parser("report", parents=[filters], help="show a report")
    report.add_argument("kind", choices=["categories", "sources", "monthly"])

    budget = commands.add_parser("budget", help="compare a month with spending limits")
    budget.add_argument("month", help="e.g. 2026-09")
    budget.add_argument("--limit", action="append", required=True,
                        help="CATEGORY=AMOUNT, e.g. groceries=250 (repeat for more)")

    demo = commands.add_parser("demo", help="fill the data file with sample transactions")
    demo.add_argument("--force", action="store_true",
                      help="add them even if the file already has data")

    return parser


# Maps each command name to the method that runs it.
COMMANDS = {
    "add-expense": ExpenseTrackerCLI.add_expense,
    "add-income": ExpenseTrackerCLI.add_income,
    "remove": ExpenseTrackerCLI.remove,
    "list": ExpenseTrackerCLI.list,
    "summary": ExpenseTrackerCLI.summary,
    "report": ExpenseTrackerCLI.report,
    "budget": ExpenseTrackerCLI.budget,
    "demo": ExpenseTrackerCLI.demo,
}


def main(argv: Sequence[str] | None = None,
         repository: TransactionRepository | None = None,
         out: TextIO | None = None,
         err: TextIO | None = None) -> int:
    """Run one command. Returns 0 on success and 1 on a known error."""
    args = build_parser().parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.WARNING,
        format="%(levelname)s %(name)s: %(message)s",
    )

    repository = repository or JSONTransactionRepository(args.file)
    cli = ExpenseTrackerCLI(repository, out)

    try:
        COMMANDS[args.command](cli, args)
    except ExpenseTrackerError as error:
        # A clear one line message for mistakes the user can fix, rather
        # than a long traceback.
        print(f"Error: {error}", file=err or sys.stderr)
        return 1
    return 0
