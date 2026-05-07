#!/usr/bin/env bash
# After pulling shim removals, migrate ~/.wakeup to quote utils/backup/*.sh only.
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
exec python3 "$SCRIPT_DIR/migrate_wakeup_backup_paths.py" "$@"
