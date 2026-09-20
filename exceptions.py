""" Custom excpetion hierachy for the Personal Expense Tracker.

Why use a custom hierachy instead of using a built in ValeErro everywhere?

1. Its lets calling code catch *our* errors specifically::

        try:
            expense = Expense(....)
        except ExpenseTrackerError:
            ... # Only catches problems raiused by this package
2. It documents the failure modes of the package in one place.
3. Every excption nbelow inherits from a single base class, so a caller can
   catch broadly (''ExpenseTracker'') or narrowly (''ValidationError).
   Thios is inheritance used for its simple and practical Purpose.
   """

from __future__ import annotations

class ExpenseTrackerError(Exception):
    """ Base class for ever error raised by this package.

    Nothing in thios class should raise a bare ''Excpetion''. Anything that
    Anything that goes wrong inside the domain model raises this class or one of its 
    subclasses, so ''excpet ExpenseTrackerError'' is  guaranteed  to be a complete saftey net
    for callers
    """

class ValidationErro(ExpenseTrackerError):
    """ Raised when data supplied to a domain falls in itys own rules.

    Eg. A negative amount , an empoty category , an unkown categiry.

    The The domain object validates itself rather than trusting the caller. That is the
    whole point of Encapusalation: an object should never be able to
    exist in an invlid state.
    """

