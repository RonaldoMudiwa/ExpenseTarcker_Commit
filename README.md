# Personal Expense Tracker

A command line application for recording and analysing personal spending, written in
Python with no third party runtime dependencies.

Project 1 of a 12 week portfolio. The goal is not only a working tool but a codebase
that demonstrates the four object oriented principles, defensive validation, and a
test suite that documents the intended behaviour.

## Status

Day 2 of 7. The domain model now has two transaction types and a collection class to
hold them. Storage, reporting and the command line interface arrive over the rest of
the week.

## Quick start

```bash
git clone https://github.com/<your-username>/personal-expense-tracker.git
cd personal-expense-tracker

python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

pip install -r requirements.txt  # pytest only, the app itself is stdlib
python -m expense_tracker        # run the demo
pytest                           # run the test suite
```

Requires Python 3.10 or newer (the code uses `X | Y` type unions).

## Project layout

```
personal-expense-tracker/
├── expense_tracker/
│   ├── __init__.py       Public API of the package
│   ├── __main__.py       Demo entry point, run with python -m expense_tracker
│   ├── enums.py          Category, PaymentMethod, IncomeSource
│   ├── exceptions.py     Custom exception hierarchy
│   ├── transaction.py    Abstract base class for every money movement
│   ├── expense.py        Money leaving the account
│   ├── income.py         Money arriving in the account
│   └── ledger.py         Ordered, de-duplicated collection of transactions
├── tests/
│   ├── test_expense.py   Model tests
│   ├── test_income.py    Income tests
│   └── test_ledger.py    Collection tests
├── data/                 Local storage, ignored by git
├── pytest.ini
└── requirements.txt
```

## Design notes

**Abstraction.** `Transaction` is an abstract base class. It defines what every money
movement must be able to do (report a signed amount, describe itself in one line)
without saying how. It cannot be instantiated directly.

**Encapsulation.** No attribute is written directly. Every field is stored privately
and exposed through a property whose setter validates the incoming value, so a
transaction cannot exist in an invalid state, not even after construction:

```python
expense.amount = -10   # ValidationError, and expense.amount is unchanged
```

The same idea applies one level up, to the collection. `TransactionLedger` owns its
internal list and index privately, so a duplicate entry or a stray string can never
get in.

**Inheritance.** Validation, equality, hashing, ordering and serialisation are written
once in `Transaction`. `Expense` and `Income` supply only what is genuinely different
about them, which is why each subclass is a fraction of the length of its base.

**Polymorphism.** `signed_amount` and `summary_line` are declared abstract and
implemented per subclass, so a running total is a single expression over mixed
transaction types with no type checks anywhere:

```python
balance = sum(t.signed_amount for t in ledger)
```

An expense returns a negative signed amount, an income a positive one. Adding a
third transaction type later would require no change to any calculation.

Three smaller decisions worth calling out:

- **Money is `Decimal`, never `float`.** Binary floating point cannot represent 0.10
  exactly, so `0.1 + 0.2` is not `0.3`. Every amount is parsed from its string form
  and quantised to two decimal places with `ROUND_HALF_UP`.
- **Equality is by identifier, not by value.** Two coffees of the same price on the
  same day are two separate transactions, so each object carries a UUID and equality
  compares type and identifier, matching how a database row behaves. `__hash__` is
  defined over the same fields to stay consistent with `__eq__`.
- **The ledger subclasses `collections.abc.Sequence`, not `list`.** Inheriting from
  `list` would expose `append`, `insert` and `__setitem__`, all of which bypass the
  ledger's validation, so it would advertise a guarantee it could not keep. Holding a
  list privately and implementing the `Sequence` interface gives the useful half of a
  list's behaviour and none of the dangerous half.

## Working with a ledger

```python
from expense_tracker import Category, Expense, Income, IncomeSource, TransactionLedger

ledger = TransactionLedger()
ledger.add(Income("2400.00", "September salary", IncomeSource.SALARY, is_recurring=True))
ledger.add(Expense("875.00", "Rent", Category.HOUSING))

len(ledger)                       # 2
ledger[0]                         # first transaction added
ledger[:1]                        # a new TransactionLedger, not a list
sorted(ledger)                    # oldest first
ledger.balance                    # Decimal('1525.00')
ledger.total_expenses             # Decimal('875.00'), unsigned for display
ledger.of_type(Income)            # a new ledger of income only
ledger.filter_by(lambda t: t.amount > 100)
print(ledger)                     # one formatted line per transaction
```

## Week plan

| Day | Focus |
| --- | --- |
| 1 | Package scaffolding, `Transaction` base class, `Expense`, enums, exceptions, unit tests |
| 2 | `Income` subclass and the `TransactionLedger` collection class |
| 3 | JSON persistence layer behind a storage interface |
| 4 | Filtering and search by date range, category and text |
| 5 | Reporting: totals by category, monthly breakdown, budget checks |
| 6 | Command line interface with `argparse` |
| 7 | CSV import and export, coverage pass, documentation |

## Testing

```bash
pytest          # full suite
pytest -q       # quiet
```

Tests are grouped by behaviour (`TestValidation`, `TestPolymorphism`,
`TestContainerProtocol`, `TestSerialization`) and exercise only the public interface,
so internal refactoring does not break them.
