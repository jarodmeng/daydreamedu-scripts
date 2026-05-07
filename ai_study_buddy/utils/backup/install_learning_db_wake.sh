#!/usr/bin/env bash
# Install sleepwatcher wake hook for study_buddy.db only — usually unnecessary if pdf hook uses run_wake_all.sh.
# Run from repo root or this directory. Requires: brew install sleepwatcher.

set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
WAKE_SCRIPT="$SCRIPT_DIR/run_learning_db_wake.sh"
LAUNCH_AGENTS="$HOME/Library/LaunchAgents"
PLIST_ID="com.daydreamedu.study-buddy-backup-on-wake"
PLIST_PATH="$LAUNCH_AGENTS/$PLIST_ID.plist"
PDF_PLIST_PATH="$LAUNCH_AGENTS/com.daydreamedu.pdf-registry-backup-on-wake.plist"

_COMBINED_RE='utils/backup/run_wake_all\.sh'
_LEARNING_RE='utils/backup/run_learning_db_wake\.sh'

if [[ -x "/opt/homebrew/sbin/sleepwatcher" ]]; then
  SLEEPWATCHER="/opt/homebrew/sbin/sleepwatcher"
elif [[ -x "/usr/local/sbin/sleepwatcher" ]]; then
  SLEEPWATCHER="/usr/local/sbin/sleepwatcher"
else
  echo "sleepwatcher not found. Install with: brew install sleepwatcher"
  exit 1
fi

if brew services list 2>/dev/null | grep -q "sleepwatcher.*started"; then
  echo "Stopping system sleepwatcher (brew services) so we use a user agent instead..."
  brew services stop sleepwatcher 2>/dev/null || true
fi

mkdir -p "$LAUNCH_AGENTS"

WAKEUP="$HOME/.wakeup"
SKIP_WAKEUP_APPEND=false
if [[ -f "$WAKEUP" ]] && [[ -f "$PDF_PLIST_PATH" ]] && grep -Eq "$_COMBINED_RE" "$WAKEUP" 2>/dev/null; then
  echo "~/.wakeup uses combined pdf-registry wake runner — study_buddy.db is already backed up there."
  SKIP_WAKEUP_APPEND=true
fi

if [[ "$SKIP_WAKEUP_APPEND" != true ]]; then
  if [[ -f "$WAKEUP" ]] && grep -Eq "$_LEARNING_RE" "$WAKEUP" 2>/dev/null; then
    echo "~/.wakeup already invokes the learning_db wake script."
  else
    if [[ ! -f "$WAKEUP" ]]; then
      echo "Creating ~/.wakeup"
      echo '#!/bin/sh' > "$WAKEUP"
    else
      echo "Appending study_buddy backup call to ~/.wakeup"
      echo "" >> "$WAKEUP"
      echo "# study_buddy.db backup (DaydreamEdu utils/backup)" >> "$WAKEUP"
    fi
    echo "\"$WAKE_SCRIPT\"" >> "$WAKEUP"
    chmod +x "$WAKEUP"
  fi
fi

if [[ ! -f "$HOME/.sleep" ]]; then
  touch "$HOME/.sleep"
  chmod +x "$HOME/.sleep"
fi

if [[ "$SKIP_WAKEUP_APPEND" == true ]] && [[ -f "$PDF_PLIST_PATH" ]]; then
  echo "Sleepwatcher already managed by $PDF_PLIST_PATH; not loading a second agent ($PLIST_ID)."
  exit 0
fi

cat > "$PLIST_PATH" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>$PLIST_ID</string>
  <key>ProgramArguments</key>
  <array>
    <string>$SLEEPWATCHER</string>
    <string>-V</string>
    <string>-s</string>
    <string>$HOME/.sleep</string>
    <string>-w</string>
    <string>$HOME/.wakeup</string>
  </array>
  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <true/>
  <key>StandardOutPath</key>
  <string>/tmp/sleepwatcher-stdout.log</string>
  <key>StandardErrorPath</key>
  <string>/tmp/sleepwatcher-stderr.log</string>
</dict>
</plist>
EOF

launchctl unload "$PLIST_PATH" 2>/dev/null || true
launchctl load "$PLIST_PATH"
echo "Loaded $PLIST_ID. Repo root assumed: $REPO_ROOT"
echo "To remove learning-only agent: bash ai_study_buddy/utils/backup/uninstall_learning_db_wake.sh"
