#!/usr/bin/env python3
"""Backward-compat shim — use mark_done.py."""

from mark_done import main

if __name__ == "__main__":
    raise SystemExit(main())
