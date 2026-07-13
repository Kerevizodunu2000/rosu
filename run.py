# SPDX-License-Identifier: GPL-3.0-or-later
"""Convenience launcher: ``python run.py``."""
import sys

from rosu.app import run

if __name__ == "__main__":
    sys.exit(run())
