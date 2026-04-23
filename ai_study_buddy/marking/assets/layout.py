from __future__ import annotations

import re

ATTEMPT_DIRNAME = "attempt"
ANSWERS_DIRNAME = "answers"
CROPS_DIRNAME = "crops"
SCRIPTS_DIRNAME = "scripts"
BUNDLE_MANIFEST_FILENAME = "bundle.json"

SUPPORTED_IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".webp")
FULL_PAGE_IMAGE_BASENAME_RE = re.compile(r"^page-(\d+)\.(png|jpg|jpeg|webp)$", re.IGNORECASE)


def is_supported_image_file(name: str) -> bool:
    lower = name.casefold()
    return lower.endswith(SUPPORTED_IMAGE_EXTENSIONS)


def parse_page_index_from_name(name: str) -> int | None:
    match = FULL_PAGE_IMAGE_BASENAME_RE.match(name)
    if match is None:
        return None
    try:
        value = int(match.group(1))
    except ValueError:
        return None
    if value < 1:
        return None
    return value
