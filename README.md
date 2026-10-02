# Personal Expense Tracker

A command line app for tracking spending and income, written in Python using
only the standard library.

Project 1 of a 12 week portfolio. Built over seven days, one commit a day, with
a focus on clean object oriented design and thorough tests.

## What it does

- Record expenses and income, with categories, payment methods and sources
- Search by month, date range, category, amount or text, and combine filters
- Reports: spending by category, income by source, month by month totals
- Budget checks that flag any category that went over its limit
- Saves to a JSON file, so nothing is lost between runs
- Import from and export to CSV, so data can go in and out of Excel

```
$ python -m expense_tracker report categories --month 2026-09
Category               Spent    Share
--------------------------------------------
Housing         £     875.00    80.1%
Groceries       £     110.45    10.1%
Bills           £      62.00     5.7%
Transport       £      41.20     3.8%
Eating Out      £       3.40     0.3%
--------------------------------------------
Total           £   1,092.05
```

## Getting started

```bash
git clone https://github.com/RonaldoMudiwa/ExpenseTarcker_Commit.git
cd ExpenseTarcker_Commit

python -m venv .venv
.venv\Scripts\activate           # macOS or Linux: source .venv/bin/activate
pip install -r requirements.txt  # only needed for the tests

python -m expense_tracker demo   # add some sample data
python -m expense_tracker list   # see it
```

Needs Python 3.10 or newer.

Always run it with `python -m expense_tracker`, not by opening a file directly.
The `-m` tells Python to treat the folder as a package, which the imports inside
it need. Running `python expense_tracker/cli.py` gives an
`attempted relative import` error.

## Commands

```bash
python -m expense_tracker add-expense 3.40 "Flat white" -c "eating out" -m cash
python -m expense_tracker add-income 2400 "Salary" -s salary --recurring
python -m expense_tracker list
python -m expense_tracker list --month 2026-09 --category groceries --min 20
python -m expense_tracker remove 3f2a9c1d
python -m expense_tracker summary --type expense
python -m expense_tracker report categories     # or: sources, monthly
python -m expense_tracker budget 2026-09 --limit groceries=250 --limit "eating out=60"
python -m expense_tracker export september.csv --month 2026-09
python -m expense_tracker import bank.csv --skip-duplicates
```

- `list` shows the first 8 characters of each id, which is enough for `remove`.
- `list`, `summary`, `report` and `export` all take the same filters:
  `--month`, `--from`, `--to`, `--category`, `--source`, `--type`, `--search`,
  `--min` and `--max`. Using more than one means all of them must match.
- Data is kept in `data/transactions.json`. Use `--file` to point somewhere else.
- Add `-v` to see what the program is doing, and `--help` on any command.

### CSV files

An exported file has these columns:

```
transaction_id,type,date,amount,description,category,payment_method,source,is_recurring
```

A file made by hand only needs `type`, `date`, `amount` and `description`.
Headings can be in any case, and missing values use the defaults. If any row
is wrong, nothing is imported and the error says which line to fix. Importing
the same file twice is refused unless you add `--skip-duplicates`.

## How it's built

```
expense_tracker/
├── transaction.py    Abstract base class for every transaction
├── expense.py        Money going out
├── income.py         Money coming in
├── enums.py          Category, PaymentMethod, IncomeSource
├── exceptions.py     All the errors the app can raise
├── ledger.py         A collection that refuses duplicates
├── factory.py        Rebuilds the right class from saved data
├── repository.py     Saving and loading (JSON file or in memory)
├── filters.py        Search rules that join with & | ~
├── reports.py        Totals, monthly breakdown, budgets
├── csv_io.py         CSV import and export
├── cli.py            The command line interface
└── __main__.py       Lets python -m expense_tracker run the app
```

### The four OOP principles

**Abstraction.** `Transaction` says what every transaction must be able to do
without saying how, and can't be created on its own. `TransactionRepository`
and `TransactionFilter` work the same way for storage and search.

**Encapsulation.** Every field is private and checked whenever it is set, so an
object can never hold a bad value, even after it is created:

```python
expense.amount = -10   # raises ValidationError, and the amount is unchanged
```

**Inheritance.** Checking, comparing and saving are written once in
`Transaction`. `Expense` and `Income` only add what is different about them.

**Polymorphism.** `signed_amount` is negative for an expense and positive for
income, so the balance is one line with no type checks:

```python
balance = sum(t.signed_amount for t in ledger)
```

### Other decisions

- **Money is `Decimal`, never `float`.** As floats, `0.1 + 0.2` gives
  `0.30000000000000004`. Amounts are rounded to pennies the way a shop would.
- **Two transactions are equal only if they share an id.** Two identical coffees
  on the same day are still two purchases.
- **The ledger is not a `list` subclass.** If it were, `append()` would let
  duplicates and wrong types straight in. It holds a list privately instead and
  only changes through `add()` and `remove()`.
- **Storage can be swapped.** The app only talks to `TransactionRepository`, so
  moving to a database means writing one new class.
- **Saving can't corrupt the file.** Data is written to a temporary file first
  and then swapped in, so a crash part way through leaves the old file whole.
- **Reports keep maths and display apart.** `ReportGenerator` works out the
  numbers and `ReportFormatter` turns them into text, so the same numbers could
  feed a web page later.
- **Errors are clear.** Every error the user can fix comes out as one readable
  line, not a crash.

## Using it from Python

```python
from expense_tracker import (
    Budget, Category, CategoryFilter, DateRangeFilter, Expense, Income,
    IncomeSource, JSONTransactionRepository, ReportFormatter, ReportGenerator,
)

repo = JSONTransactionRepository("data/transactions.json")
ledger = repo.load()

ledger.add(Income("2400", "Salary", IncomeSource.SALARY, "2026-09-01", is_recurring=True))
ledger.add(Expense("62.35", "Weekly shop", Category.GROCERIES, "2026-09-03"))
repo.save(ledger)

september = DateRangeFilter.for_month(2026, 9)
food = CategoryFilter(Category.GROCERIES, Category.EATING_OUT)
print(ledger.filter_by(september & food).total_expenses)   # 62.35

report = ReportGenerator(ledger)
budget = Budget({"groceries": "250"})
print(ReportFormatter().budget_table(report.check_budget(budget, 2026, 9)))
```

## Tests

```bash
pytest                                  # 353 tests
pytest --cov=expense_tracker            # with coverage, currently 97%
```

The tests only use the public parts of each class, so the insides can be
changed without breaking them. Storage tests use a temporary folder and the
command line tests use an in-memory repository, so your real data is never
touched.

## Built over seven days

| Day | Commit |
| --- | --- |
| 1 | `Transaction` base class, `Expense`, enums and errors |
| 2 | `Income` and the `TransactionLedger` collection |
| 3 | JSON storage behind a repository interface |
| 4 | Filtering and search |
| 5 | Reports and budget checks |
| 6 | Command line interface |
| 7 | CSV import and export, final tests and this README |
