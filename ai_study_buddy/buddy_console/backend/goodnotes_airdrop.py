from __future__ import annotations

import re
import subprocess
from pathlib import Path

_GOODNOTES_SHARE_URL_RE = re.compile(
    r"^https://(?:share|web)\.goodnotes\.com/s/[A-Za-z0-9_-]+$",
)


class GoodnotesAirDropError(Exception):
    pass


class GoodnotesAirDropUnavailableError(GoodnotesAirDropError):
    pass


def is_goodnotes_share_url(url: str) -> bool:
    return bool(_GOODNOTES_SHARE_URL_RE.match(url.strip()))


def _buddy_console_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _airdrop_helper_path() -> Path:
    return _buddy_console_root() / "goodnotes_airdrop" / "airdrop_share_link"


def launch_goodnotes_airdrop(url: str) -> None:
    link = url.strip()
    if not is_goodnotes_share_url(link):
        raise GoodnotesAirDropError("URL is not a supported Goodnotes share link")

    helper = _airdrop_helper_path()
    if not helper.is_file():
        raise GoodnotesAirDropUnavailableError(f"AirDrop helper not found: {helper}")

    subprocess.Popen(
        [str(helper), link],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
