#!/usr/bin/env bash
# Uninstall study-buddy LaunchAgent strip learning-only lines from ~/.wakeup (combined runner untouched).

set -euo pipefail
PLIST_ID="com.daydreamedu.study-buddy-backup-on-wake"
PLIST_PATH="$HOME/Library/LaunchAgents/$PLIST_ID.plist"
WAKEUP="$HOME/.wakeup"

if [[ -f "$PLIST_PATH" ]]; then
  launchctl unload "$PLIST_PATH" 2>/dev/null || true
  rm -f "$PLIST_PATH"
  echo "Removed LaunchAgent: $PLIST_PATH"
else
  echo "LaunchAgent not found: $PLIST_PATH"
fi

if [[ -f "$WAKEUP" ]]; then
  TMP_FILE="$(mktemp)"
  /usr/bin/python3 - "$WAKEUP" "$TMP_FILE" <<'PY'
from pathlib import Path
import sys

wakeup = Path(sys.argv[1])
tmp = Path(sys.argv[2])
needles = (
    "learning_db/scripts/run_backup_on_wake.sh",
    "utils/backup/run_learning_db_wake.sh",
)
lines = wakeup.read_text(encoding="utf-8").splitlines()
filtered = [line for line in lines if not any(n in line for n in needles)]
tmp.write_text("\n".join(filtered) + ("\n" if filtered else ""), encoding="utf-8")
PY
  mv "$TMP_FILE" "$WAKEUP"
  chmod +x "$WAKEUP"
  echo "Removed learning-only wake hook lines from $WAKEUP"
else
  echo "No ~/.wakeup found."
fi

echo "Uninstall complete."
