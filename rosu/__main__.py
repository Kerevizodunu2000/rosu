# SPDX-License-Identifier: GPL-3.0-or-later
"""Run with ``python -m rosu``."""
import sys

from .app import run

if __name__ == "__main__":
    sys.exit(run())
