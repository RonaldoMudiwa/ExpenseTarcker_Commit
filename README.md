# Personal Expense Tracker

A command line tool for recording and analysing personal spending, written in
Python with no third party runtime dependencies.

Project 1 of a 12 week portfolio. The aim is not just a working tool but a
codebase that shows the four object oriented principles used for real reasons,
validation that actually holds, and tests that document what the code promises.

## Status

Day 2 of 7. Two transaction types and a collection to hold them. Storage,
reporting and the command line interface follow over the rest of the week.

## Quick start

```bash
git clone https://github.com/RonaldoMudiwa/ExpenseTarcker_Commit.git
cd ExpenseTarcker_Commit

python -m venv .venv
.venv\Scripts\activate           # macOS or Linux: source .venv/bin/activate

pip install -r requirements.txt  # pytest only, the app itself is stdlib
python -m expense_tracker        # run the demo
pytest                           # run the tests
```

Needs Python 3.10 or newer, for the `X | Y` type syntax.

### Running it

Use `python -m expense_tracker`, not `python expense_tracker/__main__.py`.

The package uses relative imports (`from .enums import Category`). The leading
dot means "the package I belong to". Run a file by its path and Python sees a
lone script with no package around it, so the dot points at nothing and you get
`ImportError: attempted relative import with no known parent package`. The `-m`
flag imports the folder as a package first, then runs `__main__.py` inside it.

In VS Code the ▶ button runs the broken form. Type the command in the terminal,
or add a `launch.json` with `"module": "expense_tracker"`.

## Layout

```
ExpenseTarcker_Commit/
├── expense_tracker/
│   ├── __init__.py       What the package exports
│   ├── __main__.py       Demo, run with python -m expense_tracker
│   ├── enums.py          Category, PaymentMethod, IncomeSource
│   ├── exceptions.py     Error hierarchy
│   ├── transaction.py    Abstract base class
│   ├── expense.py        Money going out
│   ├── income.py         Money coming in
│   └── ledger.py         Collection of transactions
├── tests/
│   ├── test_expense.py
│   ├── test_income.py
│   └── test_ledger.py
├── data/                 Runtime storage, ignored by git
├── pytest.ini
└── requirements.txt
```

## Design notes

**Abstraction.** `Transaction` is an abstract base class. It says what every
money movement must be able to do (report a signed amount, describe itself in
one line) without saying how. It cannot be instantiated.

**Encapsulation.** Nothing is written directly. Every field is private with a
property setter that validates, so an object cannot end up broken, not even
after construction:

```python
expense.amount = -10   # raises, and expense.amount is unchanged
```

The same idea applies to the collection. `TransactionLedger` owns its list and
index privately, so a duplicate or a stray string can never get in.

**Inheritance.** Validation, equality, hashing, ordering and serialisation are
written once in `Transaction`. `Expense` and `Income` add only what is actually
different, which is why each is a fraction of the length of the base class.

**Polymorphism.** `signed_amount` is negative on an expense and positive on
income, so a total is one expression with no type checks:

```python
balance = sum(t.signed_amount for t in ledger)
```

Adding a third transaction type later would need no change to that line.

Three smaller decisions:

- **Money is `Decimal`, never `float`.** Binary floating point cannot hold 0.10
  exactly, so `0.1 + 0.2` is not `0.3`. Amounts are parsed from strings and
  rounded to two places with `ROUND_HALF_UP`, which is how people expect money
  to round. Python's default would turn 0.125 into 0.12.
- **Equality is by id, not by value.** Two coffees at the same price on the same
  day are two separate purchases, so each object carries a UUID and equality
  compares type and id, the way a database row behaves.
- **The ledger subclasses `collections.abc.Sequence`, not `list`.** A list
  subclass would expose `append`, `insert` and `__setitem__`, all of which skip
  the validation, so it would promise unique ids and fail to deliver. Holding a
  list privately and implementing `Sequence` gives the useful half and none of
  the risky half.

## Using a ledger

```python
from expense_tracker import Category, Expense, Income, IncomeSource, TransactionLedger

ledger = TransactionLedger()
ledger.add(Income("2400.00", "September salary", IncomeSource.SALARY, is_recurring=True))
ledger.add(Expense("875.00", "Rent", Category.HOUSING))

len(ledger)                       # 2
ledger[0]                         # first added
ledger[:1]                        # a new ledger, not a list
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
| 1 | Package setup, `Transaction` base class, `Expense`, enums, exceptions |
| 2 | `Income` subclass and the `TransactionLedger` collection |
| 3 | JSON storage behind a repository interface |
| 4 | Filtering and search by date range, category and text |
| 5 | Reporting: totals by category, monthly breakdown, budget checks |
| 6 | Command line interface with `argparse` |
| 7 | CSV import and export, coverage pass, documentation |

## Tests

```bash
pytest          # 142 tests
pytest -q       # quiet
```

Grouped by behaviour (`TestValidation`, `TestPolymorphism`,
`TestContainerProtocol`, `TestSerialization`) and written against the public
interface only, so refactoring the internals does not break them.
