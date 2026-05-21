#!/usr/bin/env python3
"""Backward-compat shim — use work_queue_status.py."""

from work_queue_status import main

if __name__ == "__main__":
    raise SystemExit(main())
