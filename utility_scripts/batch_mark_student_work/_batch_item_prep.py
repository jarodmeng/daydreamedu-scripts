#!/usr/bin/env python3
"""Backward-compat shim — use batch_item_prep.py."""

from batch_item_prep import main

if __name__ == "__main__":
    raise SystemExit(main())
