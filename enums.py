""" Enumarisation used across the ExpenseTracker.

An enum is the right tool whenever a field may only hold one of a fixed 
known set of Values. Compared to passing raw striongs around it gives us::

a single definition of tyhe allowed values 
auto completion and static checking in editors
a natural; place to hang behaviour such as human readable label.

Both 'enums' below inherit from 'str' and 'Enum' , that makes every member
behave like a normal string so (j.son dumps and f-strings just work) while 
still being a proper enum member

"""
from __future__ import annotations
from enum import Enum, unique
from .exceptions import ValidationError

class  _LabelledEnum(str,Enum):
    """ shared behaviour of enums in the module.
    This class exists specifically so that PaymentMethod and Category
    do not duplicate the same helpers, It is small but covers inheritance to remove duplication
    and the DRY( Dont repeat yourself Principle) applied to code we control.

    It is deliberatly Private (leading underscore) ::
    It is an implimantation of this module , not part of the public API of the package.

    """
    @property
    def label(self) -> str:
        """ Return a human readable name eg Eating out

        Implemented as a property rather than a method because it reads as a simple a
        simple attribute at the call site ('category.label') and performs nop meaningful work beyonf formating.
        """
        return self.value.replace("_","").title()


    @classmethod
    def from_string(cls,raw: str) -> "_LabelledEnum":
        """ Build a member from free text, tolerating case and spacing.

        This is a factory method : an alternative constructor that takes messy real world input ( from a CSV, a form, a command line )
        returns a valid emeber, or raises a clear error.

        Args:
        raw: Text such as 'Eating Out' , 'eating_out' or 'Bills'

        Returns:
            The matching enum number.

        Raises:
            ValidationError: If ''raw'' is not a tring or matches no member.
        """
        if not isinstance(raw,str):
            raise ValidationError(
                    f"{cls.__name__} must be created from a string,"
                    f"got {type(raw).__name__}"
            )

        # Normalise once, then compare. Lowercase, trim , and treat spaces and
        #hyphens as underscores so "Eating Out" and "eating-out" both work.abs
        normalised = raw.strip().lower().replace(" ","_").replace(" ","_")

        for  member in cls:
            if member.value.value == normalised:
                return member

        allowed = "' ".join(member.value for member in cls)
        raise ValidationError(
                f"Unkown {cls.__name__.lower()} {raw!r}. Allowed values: {allowed}."
        )
    
    def __str__(self) -> str:
        """Print the friendly label when the mebmer is shown to a user."""
        return self.label


@unique #gurantees no two members share the same values
class Category(_LabelledEnum):
    """ The spending categories a single expense can belong to

    Kept  deliberatly short for now. Week 1 adds reporting that gorups expenses by this field,
    so the list is intended to be stable.
    """

    GROCERIES = "groceries"
    EATING_OUT = "eating_out"
    TRANSPORT = "transport"
    HOUSING = "housing"
    BILLS = "bills"
    HEALTH = "health"
    ENTERTAINMENT = "entertainment"
    EDUCATION = "education"
    SHOPPING = "shopping"
    SAVINGS = "savings"
    OTHER = "other"

@unique
class PaymentMethod(_LabelledEnum):
    """ How an expense was paid for

    Seperate from 'category' becausxe the two answer different questions:
    a category says what the money was for , a Payment Method says where the money came from
    Keeping the two seperate is a single responsibility Prinmciple applied at the level of data modelling
    """

    CASH = "cash"
    DEBIT_CARD = "debit_card"
    CREDIT_CARD = "credit_card"
    BANK_TRANSFER = "bank_transfer"
    DIRECT_DEBIT = "direct_debit"
    OTHER = "other"