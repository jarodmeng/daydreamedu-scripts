from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any

from ai_study_buddy.marking.assets.layout import (
    ANSWERS_DIRNAME,
    ATTEMPT_DIRNAME,
    BUNDLE_MANIFEST_FILENAME,
    FULL_PAGE_IMAGE_BASENAME_RE,
    is_supported_image_file,
)


@dataclass(frozen=True)
class ValidationIssue:
    code: str
    message: str
    severity: str
    path: str | None = None


@dataclass
class ValidationReport:
    issues: list[ValidationIssue] = field(default_factory=list)

    def add_error(self, code: str, message: str, path: str | None = None) -> None:
        self.issues.append(ValidationIssue(code=code, message=message, severity="error", path=path))

    def add_warning(self, code: str, message: str, path: str | None = None) -> None:
        self.issues.append(ValidationIssue(code=code, message=message, severity="warning", path=path))

    @property
    def errors(self) -> list[ValidationIssue]:
        return [issue for issue in self.issues if issue.severity == "error"]

    @property
    def warnings(self) -> list[ValidationIssue]:
        return [issue for issue in self.issues if issue.severity == "warning"]

    @property
    def ok(self) -> bool:
        return len(self.errors) == 0


def _iter_image_files(folder: Path) -> list[Path]:
    if not folder.is_dir():
        return []
    return sorted([p for p in folder.iterdir() if p.is_file() and is_supported_image_file(p.name)])


def _validate_full_page_names(
    *,
    folder: Path,
    label: str,
    strict: bool,
    report: ValidationReport,
) -> None:
    for image_path in _iter_image_files(folder):
        if FULL_PAGE_IMAGE_BASENAME_RE.match(image_path.name):
            continue
        message = f"Invalid full-page image filename under {label}/: {image_path.name}"
        if strict:
            report.add_error("invalid_full_page_filename", message, path=str(image_path))
        else:
            report.add_warning("invalid_full_page_filename", message, path=str(image_path))


def _validate_bundle_manifest(
    *,
    bundle_root: Path,
    attempt_images: list[Path],
    answers_images: list[Path],
    strict: bool,
    report: ValidationReport,
) -> None:
    manifest_path = bundle_root / BUNDLE_MANIFEST_FILENAME
    if not manifest_path.is_file():
        if strict:
            report.add_error("missing_manifest", "Missing bundle.json in strict mode", path=str(manifest_path))
        else:
            report.add_warning("missing_manifest", "Missing bundle.json", path=str(manifest_path))
        return

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception as exc:  # pragma: no cover - defensive parse guard
        report.add_error("invalid_manifest_json", f"bundle.json is not valid JSON: {exc}", path=str(manifest_path))
        return

    if not isinstance(manifest, dict):
        report.add_error("invalid_manifest_type", "bundle.json must be a JSON object", path=str(manifest_path))
        return

    layout_version = manifest.get("bundle_layout_version")
    if not isinstance(layout_version, int) or layout_version < 1:
        report.add_error(
            "invalid_manifest_layout_version",
            "bundle_layout_version must be integer >= 1",
            path=str(manifest_path),
        )

    attempt_count = manifest.get("attempt_page_count")
    if attempt_count is not None:
        if not isinstance(attempt_count, int) or attempt_count < 0:
            report.add_error(
                "invalid_manifest_attempt_page_count",
                "attempt_page_count must be integer >= 0 when present",
                path=str(manifest_path),
            )
        elif attempt_count != len(attempt_images):
            report.add_error(
                "manifest_attempt_page_count_mismatch",
                f"attempt_page_count={attempt_count} does not match discovered attempt images={len(attempt_images)}",
                path=str(manifest_path),
            )

    answers_count = manifest.get("answers_page_count")
    if answers_count is not None:
        if not isinstance(answers_count, int) or answers_count < 0:
            report.add_error(
                "invalid_manifest_answers_page_count",
                "answers_page_count must be integer >= 0 when present",
                path=str(manifest_path),
            )
        elif answers_count != len(answers_images):
            report.add_error(
                "manifest_answers_page_count_mismatch",
                f"answers_page_count={answers_count} does not match discovered answers images={len(answers_images)}",
                path=str(manifest_path),
            )


def _resolve_relative_bundle_path(bundle_root: Path, rel_text: str) -> Path | None:
    if not rel_text.strip():
        return None
    if rel_text.startswith("/"):
        return None
    pure = PurePosixPath(rel_text)
    if pure.is_absolute():
        return None
    if any(part in ("", ".", "..") for part in pure.parts):
        return None
    normalized = str(pure)
    if normalized != rel_text:
        return None

    resolved = (bundle_root / Path(rel_text)).resolve()
    try:
        resolved.relative_to(bundle_root.resolve())
    except ValueError:
        return None
    return resolved


def _validate_evidence_images(
    *,
    bundle_root: Path,
    artifact_dict: dict[str, Any] | None,
    strict: bool,
    report: ValidationReport,
) -> None:
    if artifact_dict is None:
        return
    context = artifact_dict.get("context")
    if not isinstance(context, dict):
        return
    page_map = context.get("question_page_map")
    if not isinstance(page_map, list):
        return

    for index, entry in enumerate(page_map, start=1):
        if not isinstance(entry, dict):
            continue
        evidence_image = entry.get("evidence_image")
        if evidence_image is None:
            continue
        if not isinstance(evidence_image, str):
            report.add_error(
                "invalid_evidence_image_type",
                f"question_page_map[{index}].evidence_image must be a string when present",
            )
            continue

        resolved = _resolve_relative_bundle_path(bundle_root, evidence_image)
        if resolved is None:
            report.add_error(
                "invalid_evidence_image_path",
                f"question_page_map[{index}].evidence_image must be a normalized relative path under bundle root",
                path=evidence_image,
            )
            continue

        confidence = entry.get("confidence")
        must_exist = strict or confidence == "high"
        if must_exist and not resolved.is_file():
            report.add_error(
                "missing_evidence_image",
                f"question_page_map[{index}].evidence_image does not exist",
                path=evidence_image,
            )
        elif not must_exist and not resolved.is_file():
            report.add_warning(
                "missing_evidence_image",
                f"question_page_map[{index}].evidence_image does not exist",
                path=evidence_image,
            )


def validate_marking_asset_bundle(
    *,
    bundle_root: Path,
    artifact_dict: dict | None,
    strict: bool = False,
) -> ValidationReport:
    report = ValidationReport()
    if not bundle_root.is_dir():
        report.add_error("missing_bundle_root", "Bundle root is not a directory", path=str(bundle_root))
        return report

    attempt_dir = bundle_root / ATTEMPT_DIRNAME
    answers_dir = bundle_root / ANSWERS_DIRNAME
    if not attempt_dir.is_dir():
        report.add_error("missing_attempt_dir", "Bundle is missing required attempt/ directory", path=str(attempt_dir))
        return report

    attempt_images = _iter_image_files(attempt_dir)
    answers_images = _iter_image_files(answers_dir)
    if strict and len(attempt_images) == 0:
        report.add_error("empty_attempt_dir", "attempt/ must contain at least one image in strict mode", path=str(attempt_dir))

    _validate_full_page_names(folder=attempt_dir, label=ATTEMPT_DIRNAME, strict=strict, report=report)
    if answers_dir.is_dir():
        _validate_full_page_names(folder=answers_dir, label=ANSWERS_DIRNAME, strict=strict, report=report)
    _validate_bundle_manifest(
        bundle_root=bundle_root,
        attempt_images=attempt_images,
        answers_images=answers_images,
        strict=strict,
        report=report,
    )
    _validate_evidence_images(
        bundle_root=bundle_root,
        artifact_dict=artifact_dict,
        strict=strict,
        report=report,
    )
    return report


def assert_marking_asset_bundle_ready_for_review(
    bundle_root: Path,
    artifact_dict: dict | None,
) -> None:
    report = validate_marking_asset_bundle(bundle_root=bundle_root, artifact_dict=artifact_dict, strict=True)
    if report.ok:
        return
    message = "; ".join(issue.message for issue in report.errors[:5])
    raise ValueError(f"Marking asset bundle is not ready for review: {message}")
