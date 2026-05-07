#!/usr/bin/env bash
# Canonical wake entrypoint: pdf_registry backup, then study_buddy.db. ~/.wakeup should quote this script.

set -euo pipefail
B="$(cd "$(dirname "$0")" && pwd)"
/bin/bash "$B/run_pdf_registry_wake.sh"
/bin/bash "$B/run_learning_db_wake.sh"
