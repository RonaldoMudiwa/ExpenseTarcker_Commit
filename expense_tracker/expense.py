"""
The 'Expense' Class the first real 'Transaction'

This file is shoprter than transaction.py , all the validation,
equality , hashing and serialisation scaffolding was written all in the base class.
So new transaction only have to supply what is genuinley different about it::

*Two extra fields (category and payment method),
*the direction of the money (''signed_amount'' is negative'')
*how it print itslef (''summary_line'').

This is all because of inheritance.
"""

from __future__ import annotations

from datetime import date as date_type
from decimal import Decimal
from typing import Any, Mapping

from .enums import Category,PaymentMethod
from .exceptions import ValidationError
from .transaction import Transaction


class Expense(Transaction):
    """ Money leaving the Users Pockets.

    EG.
     from decimal import Decimal
     coffee = Expense(
                    amount = "4.00"
                    descrpition = "Coffee"
                    category = "Eating out"
                    transaction_date = "2026-09-20"
     )
     >>> coffe.amount
        Decimal('4.00')
     >>> coffe.signed_amount
        Decimal('-4.00')
    """

#: Overides the place hoilder on the base class. Written to storage and used later
# to pick the right class when reading data back.

    TRANSACTION_TYPE = "expense"

    def __init__(self , amount: Decimal | int | float | str,
              description: str,
              category: Category | str = Category.OTHER,
              transaction_date: date_type | str | None = None,
              payment_method: PaymentMethod | str = PaymentMethod.OTHER,
              transaction_id: str | None = None,
    ) -> None:
        """ Create a Validated expense.

        Args:
            amount: Positivce amount Spent
            escription: What the money was spent on.
            category: A ``Category`` member, or text such as ``"eating out"``.
            transaction_date: Date of the spend. Defaults to today.
            payment_method: A ``PaymentMethod`` member, or equivalent text.
            transaction_id: Existing identifier when rebuilding from storage.

        Raises:
            ValidationError: If any argument fails validation.
        """
        #''super().__init__'' runs the shared validation first. 
        # Calling it before touching the subclass state means a half-built object is never
        #left behind if the base class rejects an argument.

        super().__init__(
                amount = amount,
                description= description,
                transaction_date = transaction_date,
                transaction_id = transaction_id
            )
        
        #Assign via the properties so their validation runs here too.
        self.category = category
        self.payment_method = payment_method

        #-----------------------------------------------
        # Subclass specific properties
        #-----------------------------------------------

    @property
    def category(self) -> Category:
            """What the money was spent on."""
            return self._category

    @category.setter
    def category(self, value: Category| str) -> None:
            self._category = self._coerce_enum(value, Category)

    @property
    def payment_method(self) -> PaymentMethod:
            """ Where was the money paid from"""
            return self._payment_method

    @payment_method.setter
    def payment_method(self, value: PaymentMethod| str) -> None:
            self._payment_method = self._coerce_enum(value, PaymentMethod)
        
        #------------------------------
        #Implements of the abstract contract
        #-------------------------------------

    @property
    def signed_amount(self) -> Decimal:
            """ Expenses reduce the balance, so the signed amount is negative."""
            return -self.amount

    def summary_line(self) -> str:
        """ Return one aligned line, e.g. ''2026-09-18 -£4.00 Coffee. """

        return (
            f"{self.transaction_date.isoformat()}  "
            f"-£{self.amount:>8,.2f}  "
            f"{self.category.label:<14}  "
            f"{self.description}"
        )

    #-------------------------------------
    #Serialisation
    #-------------------------------------

    def _extra_fields(self) -> Mapping[str,Any]:
        """ Add the expense-only keys to the dictionary built by the base."""
        return {
                "category": self.category.value,
                "payment_method": self.payment_method.value,
        }

    @classmethod
    def  from_dict(cls,data:Mapping[str,Any]) -> "Expense":
        """ Rebuild an ''Expense'' from the output of ''to_dict''.

        A ''classmethod'' rather than a ''staticmethod'' because it needs
        ''cls'' to construct the object. That also means any future subclass of
        ''Expense'' inherits this factory and returns  its own type.

        Args: 
            data : A  mapping produced by ''to_dict'' (or read from JSON).

        Returns:
            The reconstructed expense, carrying its original identifier.

        Raises:
            SerializationError: If a required key is missing.
            ValidationError:  If a stored value is no longer valid.
        """

        return cls(
                    amount = cls._require(data, "amount"),
                    description= cls._require(data, "description"),
                    category = data.get("category", Category.OTHER),
                    transaction_date = data.get("date"),
                    payment_method = data.get("payment_method",PaymentMethod.OTHER),
                    transaction_id=data.get("transaction_id"),   
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------       

    @staticmethod
    def _coerce_enum(value:Any, enum_class: type) -> Any:
        """ Accept either an enum member or text and return a valid member.

            Keeping this in one helper means ''category'' and ''paymenth_mathod''
            share identical behavior and identical error messages.
        """

        if isinstance(value, enum_class):
            return value
        if isinstance(value, str):
            return enum_class.from_string(value)
        raise ValidationError(
            f"{enum_class.__name__} must be a {enum_class.__name__} member or "
            f"text, got {type(value).__name__}."

        )



