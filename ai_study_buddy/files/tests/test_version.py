"""Tests for ai_study_buddy.files package version."""

import re

from ai_study_buddy import files


def test_files_version_is_semver_patch_string() -> None:
    assert re.fullmatch(r"\d+\.\d+\.\d+", files.__version__)


def test_files_version_exported_from_package() -> None:
    assert "__version__" in files.__all__
