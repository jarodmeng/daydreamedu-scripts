#!/usr/bin/env bash
# Install "run backup on wake" using sleepwatcher. Run from repo root or from this script's directory.
# Requires: brew install sleepwatcher (will prompt if missing).

set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../../../" && pwd)"
WAKE_SCRIPT="$SCRIPT_DIR/run_backup_on_wake.sh"
LAUNCH_AGENTS="$HOME/Library/LaunchAgents"
PLIST_ID="com.daydreamedu.pdf-registry-backup-on-wake"
PLIST_PATH="$LAUNCH_AGENTS/$PLIST_ID.plist"

# Resolve sleepwatcher (Homebrew Intel vs Apple Silicon)
if [[ -x "/opt/homebrew/sbin/sleepwatcher" ]]; then
  SLEEPWATCHER="/opt/homebrew/sbin/sleepwatcher"
elif [[ -x "/usr/local/sbin/sleepwatcher" ]]; then
  SLEEPWATCHER="/usr/local/sbin/sleepwatcher"
else
  echo "sleepwatcher not found. Install with: brew install sleepwatcher"
  exit 1
fi

# If user already runs sleepwatcher via brew services, they may get double runs. Stop it.
if brew services list 2>/dev/null | grep -q "sleepwatcher.*started"; then
  echo "Stopping system sleepwatcher (brew services) so we use a user agent instead..."
  brew services stop sleepwatcher 2>/dev/null || true
fi

mkdir -p "$LAUNCH_AGENTS"

# ~/.wakeup: run our backup script (append if file exists and doesn't already call us)
WAKEUP="$HOME/.wakeup"
if [[ -f "$WAKEUP" ]] && grep -q "run_backup_on_wake.sh" "$WAKEUP" 2>/dev/null; then
  echo "~/.wakeup already invokes the backup script."
else
  if [[ ! -f "$WAKEUP" ]]; then
    echo "Creating ~/.wakeup"
    echo '#!/bin/sh' > "$WAKEUP"
  else
    echo "Appending backup call to existing ~/.wakeup"
    echo "" >> "$WAKEUP"
    echo "# pdf_registry backup (DaydreamEdu)" >> "$WAKEUP"
  fi
  echo "\"$WAKE_SCRIPT\" &" >> "$WAKEUP"
  chmod +x "$WAKEUP"
fi

# Empty ~/.sleep if missing (sleepwatcher expects it when using brew paths)
if [[ ! -f "$HOME/.sleep" ]]; then
  touch "$HOME/.sleep"
  chmod +x "$HOME/.sleep"
fi

# Install user LaunchAgent so sleepwatcher runs in our context (and backup sees our Google Drive)
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
echo "Loaded $PLIST_ID. Backup will run when this Mac wakes from sleep (only if DB changed)."
echo "To remove: launchctl unload $PLIST_PATH; edit or remove ~/.wakeup"
