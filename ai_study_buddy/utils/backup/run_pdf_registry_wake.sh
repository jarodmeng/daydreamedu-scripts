#!/usr/bin/env bash
# Backs up pdf_registry.db on wake (timestamp + tiering). Invoked directly or via run_wake_all.sh.

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
export PYTHONPATH="$REPO_ROOT${PYTHONPATH:+:$PYTHONPATH}"

LOG_FILE="$HOME/Library/Logs/pdf_registry_backup_on_wake.log"
mkdir -p "$(dirname "$LOG_FILE")"
exec >>"$LOG_FILE" 2>&1

echo "[$(/bin/date '+%Y-%m-%d %H:%M:%S %z')] wake backup start (pdf_registry)"

ATTEMPTS=6
SLEEP_SECONDS=10
attempt=1
while true; do
  if /usr/bin/env python3 -m ai_study_buddy.pdf_file_manager.scripts.backup_pdf_registry --timestamp; then
    break
  fi

  if [[ "$attempt" -ge "$ATTEMPTS" ]]; then
    echo "[$(/bin/date '+%Y-%m-%d %H:%M:%S %z')] backup failed after ${ATTEMPTS} attempts"
    exit 1
  fi

  echo "[$(/bin/date '+%Y-%m-%d %H:%M:%S %z')] backup attempt ${attempt} failed, retrying in ${SLEEP_SECONDS}s"
  /bin/sleep "$SLEEP_SECONDS"
  attempt=$((attempt + 1))
done

/usr/bin/env python3 -m ai_study_buddy.pdf_file_manager.scripts.apply_backup_tiering --hot-days 7 --cold-days 60
echo "[$(/bin/date '+%Y-%m-%d %H:%M:%S %z')] wake backup done (pdf_registry)"
