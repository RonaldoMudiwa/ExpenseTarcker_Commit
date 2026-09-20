""" Personal Expense Tracker.


A small well structured Python Apllication Tracker for recording , analysing personal spending
Built over one week as project 1 of a 12 week Portfolio , with every OOP Principle applied deriberatly rather than decoratively.

This file the packages front door. Importing the handful of names 
that callers actually need means user code can write::

 from ExpenseTracker import expense, Category.

Instead of reaching into module paths that can be recognised later.
The "__all__" list startes the poublic API Explicitly so everything
not on it can be understood to be internal.

"""

from .enums import Category , PaymentMethod
from .exceptions import ExpenseTrackertError, SerializationError , ValidationError
from .expense import Expense
from .transaction import Transaction

__version__ = "0.1.0"

__all__ [
            "Category",
            "PaymentMethod",
            "Expense",
            "Transaction",
            "ExpenseTrackerError",
            "ValidationError",
            "SerializationError",
            "__version__"

]
