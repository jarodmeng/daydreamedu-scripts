#!/usr/bin/env bash
# Run by sleepwatcher on wake (e.g. from ~/.wakeup). Backs up pdf_registry.db
# only if it has changed. Invoke from repo: scripts/install_run_on_wake.sh

set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../../../" && pwd)"
exec /usr/bin/env python3 "$REPO_ROOT/ai_study_buddy/utils/pdf_file_manager/scripts/backup_pdf_registry.py" --timestamp
