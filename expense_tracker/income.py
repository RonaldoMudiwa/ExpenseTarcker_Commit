"""Money arriving in the account.

``Income`` is the second concrete subclass of :class:`~.transaction.Transaction`,
and it is where Day 1's design starts to pay for itself.

Note what this module does *not* contain: no amount parsing, no date
parsing, no description validation, no equality, no hashing, no ordering, no
``to_dict``. All of that was written once in the base class and is inherited
unchanged. The only code here is the code that is genuinely different about
income, which is the test of whether a base class was drawn in the right
place.

The OOP principles visible in this file:

* **Inheritance** - ``Income`` reuses the whole of ``Transaction`` and adds
  two fields of its own.
* **Polymorphism** - ``signed_amount`` returns a *positive* number where
  ``Expense`` returns a negative one. Calling code sums a mixed list with
  ``sum(t.signed_amount for t in ledger)`` and never asks what type anything
  is. Adding a third transaction type later changes no existing code.
* **Liskov Substitution Principle** - anywhere a ``Transaction`` is expected,
  an ``Income`` works. It does not narrow the contract, strengthen the
  preconditions, or raise surprise exceptions the base class never promised.
* **Open Closed Principle** - the package gained a new behaviour by adding a
  file, not by editing ``Transaction`` or ``Expense``.
"""

from __future__ import annotations

from datetime import date as date_type
from decimal import Decimal
from typing import Any, Mapping

from .enums import IncomeSource, coerce_enum
from .exceptions import ValidationError
from .transaction import Transaction


class Income(Transaction):
    """A single payment received, such as a salary or a refund.

    The amount is stored as a positive number, exactly as it is for an
    expense. Direction is expressed by :attr:`signed_amount`, not by the
    sign of the stored value.

    Keeping stored amounts unsigned is a deliberate choice. If direction
    lived in the sign, then every report would have to remember whether a
    negative income means "money received and recorded oddly" or "a
    correction", and validation could no longer simply reject amounts that
    are not greater than zero.

    Example:
        >>> salary = Income("2400.00", "September salary", IncomeSource.SALARY,
        ...                 "2026-09-25", is_recurring=True)
        >>> salary.signed_amount
        Decimal('2400.00')
    """

    #: Overrides the base class tag. Written into ``to_dict`` output so the
    #: Day 3 JSON loader can tell which class to rebuild each record with.
    TRANSACTION_TYPE = "income"

    def __init__(
        self,
        amount: Decimal | int | float | str,
        description: str,
        source: IncomeSource | str = IncomeSource.OTHER,
        transaction_date: date_type | str | None = None,
        is_recurring: bool = False,
        transaction_id: str | None = None,
    ) -> None:
        """Create an income entry, validating every field before storing it.

        Args:
            amount: A positive amount. Accepts ``Decimal``, ``int``,
                ``float`` or text; it is parsed and rounded to two decimal
                places by the base class.
            description: Short label, e.g. ``"September salary"``.
            source: Where the money came from. A member of
                :class:`~.enums.IncomeSource` or text such as ``"salary"``.
            transaction_date: The date received. Defaults to today.
            is_recurring: ``True`` for regular income such as a monthly
                salary. Day 5's reporting uses this to separate reliable
                income from one off payments when projecting a budget.
            transaction_id: Existing identifier, used when rebuilding a
                stored record. A new UUID is generated when omitted.

        Raises:
            ValidationError: If any field is invalid.
        """
        # The base class runs first so that identity, amount, description and
        # date are all validated and stored before this class adds anything.
        # Calling ``super().__init__`` with keywords rather than positionally
        # means a future change to the base signature cannot silently bind
        # our arguments to the wrong parameters.
        super().__init__(
            amount=amount,
            description=description,
            transaction_date=transaction_date,
            transaction_id=transaction_id,
        )

        # Assigning through the properties, not to ``self._source`` directly,
        # so that construction and later mutation run the same validation.
        self.source = source
        self.is_recurring = is_recurring

    # ------------------------------------------------------------------
    # Encapsulated state specific to income
    # ------------------------------------------------------------------

    @property
    def source(self) -> IncomeSource:
        """Where the money came from."""
        return self._source

    @source.setter
    def source(self, value: IncomeSource | str) -> None:
        """Validate and store the source, accepting a member or text."""
        self._source = coerce_enum(value, IncomeSource)

    @property
    def is_recurring(self) -> bool:
        """Whether this income repeats on a regular schedule."""
        return self._is_recurring

    @is_recurring.setter
    def is_recurring(self, value: bool) -> None:
        """Store the flag, refusing truthy stand ins for a real boolean.

        ``if value:`` would happily accept ``"no"``, ``0.0`` or ``[]`` and
        silently record the wrong thing. Requiring an actual ``bool`` turns a
        caller's mistake into an immediate, obvious error.
        """
        if not isinstance(value, bool):
            raise ValidationError(
                f"is_recurring must be True or False, got {type(value).__name__}."
            )
        self._is_recurring = value

    # ------------------------------------------------------------------
    # Implementations of the abstract contract
    # ------------------------------------------------------------------

    @property
    def signed_amount(self) -> Decimal:
        """Income increases the balance, so the signed amount is positive.

        This single line is the whole of polymorphism in this project. The
        ledger's balance calculation never branches on type because each
        class already knows which direction it moves money in.
        """
        return self.amount

    def summary_line(self) -> str:
        """Return one aligned line, e.g. ``2026-09-25  +£2,400.00  Salary ...``.

        The column widths match :meth:`Expense.summary_line` on purpose, so a
        mixed list of transactions prints as a tidy table with no extra
        formatting work at the call site.
        """
        recurring_marker = " (recurring)" if self.is_recurring else ""
        return (
            f"{self.transaction_date.isoformat()}  "
            f"+£{self.amount:>8,.2f}  "
            f"{self.source.label:<14}  "
            f"{self.description}{recurring_marker}"
        )

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def _extra_fields(self) -> Mapping[str, Any]:
        """Add the income only keys to the dictionary built by the base.

        This is the *template method* pattern from Day 1 seen from the other
        side: ``to_dict`` is written once and fixed in ``Transaction``, and
        each subclass customises it only through this hook. The shape of the
        common keys therefore cannot drift between ``Expense`` and
        ``Income``.
        """
        return {
            "source": self.source.value,
            "is_recurring": self.is_recurring,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "Income":
        """Rebuild an ``Income`` from the output of :meth:`to_dict`.

        Required keys raise if missing, because an income with no amount is
        corrupt data rather than a gap worth guessing at. Optional keys fall
        back to the same defaults used by ``__init__``, so a record written
        by an older version of the app still loads.

        Args:
            data: A mapping produced by ``to_dict`` or read from JSON.

        Returns:
            The reconstructed income, carrying its original identifier.

        Raises:
            SerializationError: If a required key is missing.
            ValidationError: If a stored value is no longer valid.
        """
        return cls(
            amount=cls._require(data, "amount"),
            description=cls._require(data, "description"),
            source=data.get("source", IncomeSource.OTHER),
            transaction_date=data.get("date"),
            is_recurring=bool(data.get("is_recurring", False)),
            transaction_id=data.get("transaction_id"),
        )
