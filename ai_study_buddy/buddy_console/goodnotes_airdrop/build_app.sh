#!/bin/bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
APP="$ROOT/AirDropShareLink.app"
SRC="$ROOT/share_link_app.m"
BIN="$APP/Contents/MacOS/AirDropShareLink"
PLIST="$APP/Contents/Info.plist"

mkdir -p "$APP/Contents/MacOS"

clang -framework Cocoa -o "$BIN" "$SRC"

cat > "$PLIST" <<'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleDevelopmentRegion</key>
    <string>en</string>
    <key>CFBundleExecutable</key>
    <string>AirDropShareLink</string>
    <key>CFBundleIdentifier</key>
    <string>com.daydreamedu.buddy-console.AirDropShareLink</string>
    <key>CFBundleName</key>
    <string>AirDropShareLink</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>CFBundleShortVersionString</key>
    <string>1.0</string>
    <key>CFBundleVersion</key>
    <string>1</string>
    <key>LSMinimumSystemVersion</key>
    <string>13.0</string>
    <key>LSUIElement</key>
    <true/>
    <key>NSHighResolutionCapable</key>
    <true/>
</dict>
</plist>
EOF

echo "Built $APP"
