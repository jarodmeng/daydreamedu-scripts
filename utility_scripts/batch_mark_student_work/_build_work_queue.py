#!/usr/bin/env python3
"""Backward-compat shim — use build_work_queue.py."""

from build_work_queue import main

if __name__ == "__main__":
    raise SystemExit(main())
