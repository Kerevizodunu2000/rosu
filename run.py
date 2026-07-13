"""Convenience launcher: ``python run.py``."""
import sys

from rosu.app import run

if __name__ == "__main__":
    sys.exit(run())
