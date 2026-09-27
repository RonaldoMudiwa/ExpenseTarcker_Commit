"""Lets the package run as a program:

    python -m expense_tracker --help
"""

import sys

from .cli import main

if __name__ == "__main__":
    sys.exit(main())
