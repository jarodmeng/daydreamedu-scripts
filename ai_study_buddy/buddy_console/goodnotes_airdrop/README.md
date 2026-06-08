# GoodNotes AirDrop helper (macOS)

Launches the macOS AirDrop sheet for a GoodNotes share URL (`https://share.goodnotes.com/s/...`).

Used by `buddy_console` via `POST /api/goodnotes/airdrop-share-link` (`backend/goodnotes_airdrop.py`).

## Build

```bash
./build_app.sh
```

The wrapper script `airdrop_share_link` auto-builds on first run if `AirDropShareLink.app` is missing.

## Manual use

```bash
./airdrop_share_link "https://share.goodnotes.com/s/..."
```

Requires macOS with AirDrop available. Logs to `~/Library/Logs/AirDropShareLink.log`.
