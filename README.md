# Personal Expense Tracker

A command line application for recording and analysing personal spending, written in
Python with no third party runtime dependencies.

Project 1 of a 12 week portfolio. The goal is not only a working tool but a codebase
that demonstrates the four object oriented principles, defensive validation, and a
test suite that documents the intended behaviour.

## Status

Day 1 of 7. The domain model is complete and fully tested. Storage, reporting and the
command line interface arrive over the rest of the week.

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
│   ├── enums.py          Category and PaymentMethod
│   ├── exceptions.py     Custom exception hierarchy
│   ├── transaction.py    Abstract base class for every money movement
│   └── expense.py        Concrete Expense implementation
├── tests/
│   └── test_expense.py   42 unit tests covering the model
├── data/                 Local storage, ignored by git
├── pytest.ini
└── requirements.txt
```

## Design notes

**Abstraction.** `Transaction` is an abstract base class. It defines what every money
movement must be able to do (report a signed amount, describe itself in one line)
without saying how. It cannot be instantiated directly.

**Encapsulation.** No attribute is written directly. Every field is stored privately
and exposed through a property whose setter validates the incoming value, so an
`Expense` cannot exist in an invalid state, not even after construction:

```python
expense.amount = -10   # ValidationError, and expense.amount is unchanged
```

**Inheritance.** Validation, equality, hashing, ordering and serialisation are written
once in `Transaction`. `Expense` supplies only what is genuinely different about it,
which is why the subclass is roughly a third of the length of its base.

**Polymorphism.** `signed_amount` and `summary_line` are declared abstract and
implemented per subclass, so a running total is a single expression over mixed
transaction types with no type checks anywhere:

```python
total = sum(t.signed_amount for t in transactions)
```

Two smaller decisions worth calling out:

- **Money is `Decimal`, never `float`.** Binary floating point cannot represent 0.10
  exactly, so `0.1 + 0.2` is not `0.3`. Every amount is parsed from its string form
  and quantised to two decimal places with `ROUND_HALF_UP`.
- **Equality is by identifier, not by value.** Two coffees of the same price on the
  same day are two separate transactions, so each object carries a UUID and equality
  compares type and identifier, matching how a database row behaves. `__hash__` is
  defined over the same fields to stay consistent with `__eq__`.

## Week plan

| Day | Focus |
| --- | --- |
| 1 | Package scaffolding, `Transaction` base class, `Expense`, enums, exceptions, unit tests |
| 2 | `Income` subclass and a `Transaction` repository collection |
| 3 | JSON persistence layer behind a storage interface |
| 4 | Filtering and search by date range, category and text |
| 5 | Reporting: totals by category, monthly breakdown, budget checks |
| 6 | Command line interface with `argparse` |
| 7 | CSV import and export, coverage pass, documentation |

## Testing

```bash
pytest          # 42 tests
pytest -q       # quiet
```

Tests are grouped by behaviour (`TestValidation`, `TestPolymorphism`,
`TestSerialization`) and exercise only the public interface, so internal refactoring
does not break them.
