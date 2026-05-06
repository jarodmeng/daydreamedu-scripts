"""Compare filesystem vs DB-backed `find_marking_artifacts_for_attempt` for the same completion set."""

from __future__ import annotations

import os
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path

from ai_study_buddy.learning_db.core.migrate import apply_migrations
from ai_study_buddy.marking.core.artifact_lookup import (
    MarkingArtifactRef,
    MatchCondition,
    find_marking_artifacts_for_attempt,
)
from ai_study_buddy.pdf_file_manager.pdf_file_manager import PdfFileManager


@dataclass
class ReaderParityMismatch:
    """One completion where FS and strict-DB paths disagree."""

    file_id: str
    path: str
    student_id: str | None
    filesystem_key: tuple[tuple[str, str], ...]
    db_key: tuple[tuple[str, str], ...]


@dataclass
class ReaderParityReport:
    """Summary of `find_marking_artifacts_for_attempt` FS vs DB strict parity over a corpus slice."""

    eligible: int
    skipped_no_student: int
    parity_checked: int
    mismatch_count: int
    mismatches: list[ReaderParityMismatch] = field(default_factory=list)
    errors: list[tuple[str, str]] = field(default_factory=list)


_ENV_KEYS = (
    "LEARNING_DB_ENABLE_READS",
    "LEARNING_DB_READ_FALLBACK_FILESYSTEM",
    "STUDY_BUDDY_DB_PATH",
    "STUDY_BUDDY_CONTEXT_ROOT",
)


def _snapshot_env(keys: tuple[str, ...]) -> dict[str, str | None]:
    return {k: os.environ.get(k) for k in keys}


def _restore_env(snap: dict[str, str | None]) -> None:
    for k, v in snap.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v


def _ref_key(refs: list[MarkingArtifactRef]) -> tuple[tuple[str, str], ...]:
    """Preserve API order (do not sort — ordering is part of the contract)."""

    rows: list[tuple[str, str]] = []
    for r in refs:
        mj = Path(r.marking_result_json).expanduser().resolve().as_posix()
        lr = Path(r.learning_report_md).expanduser().resolve().as_posix()
        rows.append((mj, lr))
    return tuple(rows)


def _iter_completion_mains(manager: PdfFileManager) -> list:
    mains = manager.find_files(file_type="main", is_template=False)
    with_student = [f for f in mains if f.student_id]
    with_student.sort(key=lambda f: (f.path, f.id))
    return with_student


def _count_mains_without_student(manager: PdfFileManager) -> int:
    mains = manager.find_files(file_type="main", is_template=False)
    return sum(1 for f in mains if not f.student_id)


@contextmanager
def _parity_env(study_buddy_db: Path, context_root: Path):
    snap = _snapshot_env(_ENV_KEYS)
    os.environ["STUDY_BUDDY_DB_PATH"] = str(study_buddy_db.resolve())
    os.environ["STUDY_BUDDY_CONTEXT_ROOT"] = str(Path(context_root).expanduser().resolve())
    try:
        yield
    finally:
        _restore_env(snap)


def _refs_filesystem(match_condition: MatchCondition, attempt_id: str, manager: PdfFileManager, context_root: Path) -> list[MarkingArtifactRef]:
    os.environ.pop("LEARNING_DB_ENABLE_READS", None)
    os.environ.pop("LEARNING_DB_READ_FALLBACK_FILESYSTEM", None)
    return find_marking_artifacts_for_attempt(
        attempt_id,
        match_condition=match_condition,
        manager=manager,
        context_root=context_root,
    )


def _refs_db_strict(match_condition: MatchCondition, attempt_id: str, manager: PdfFileManager, context_root: Path) -> list[MarkingArtifactRef]:
    os.environ["LEARNING_DB_ENABLE_READS"] = "1"
    os.environ["LEARNING_DB_READ_FALLBACK_FILESYSTEM"] = "0"
    return find_marking_artifacts_for_attempt(
        attempt_id,
        match_condition=match_condition,
        manager=manager,
        context_root=context_root,
    )


def run_reader_parity(
    *,
    study_buddy_db_path: Path,
    context_root: Path,
    pdf_registry_path: Path | None,
    limit: int | None = None,
    match_condition: MatchCondition = "json_only",
) -> ReaderParityReport:
    """
    For each non-template ``main`` file with ``student_id``, compare:

    - ``find_marking_artifacts_for_attempt`` with DB reads disabled (historical filesystem scan).
    - same function with reads enabled and filesystem fallback forced off (DB-only lookup).

    Precondition: JSON under ``context_root`` has been imported into ``study_buddy_db_path``.
    """

    db_path = study_buddy_db_path.expanduser().resolve()
    ctx = Path(context_root).expanduser().resolve()
    apply_migrations(db_path=db_path)

    manager = PdfFileManager(db_path=pdf_registry_path.expanduser().resolve() if pdf_registry_path else None)
    completions = _iter_completion_mains(manager)

    skipped = _count_mains_without_student(manager)

    mismatches: list[ReaderParityMismatch] = []
    errors: list[tuple[str, str]] = []

    n = 0
    with _parity_env(db_path, ctx):
        for f in completions:
            if limit is not None and n >= limit:
                break
            n += 1
            try:
                k_fs = _ref_key(
                    _refs_filesystem(match_condition, f.id, manager, ctx),
                )
                k_db = _ref_key(
                    _refs_db_strict(match_condition, f.id, manager, ctx),
                )
                if k_fs != k_db:
                    mismatches.append(
                        ReaderParityMismatch(
                            file_id=f.id,
                            path=f.path,
                            student_id=f.student_id,
                            filesystem_key=k_fs,
                            db_key=k_db,
                        )
                    )
            except Exception as exc:
                errors.append((f.id, f"{type(exc).__name__}: {exc}"))

    return ReaderParityReport(
        eligible=len(completions),
        skipped_no_student=skipped,
        parity_checked=n,
        mismatch_count=len(mismatches),
        mismatches=mismatches,
        errors=errors,
    )


def print_reader_parity_report(report: ReaderParityReport, *, detail_limit: int = 12) -> None:
    print("")
    print(
        "Reader parity (LEARNING_DB_ENABLE_READS=0 filesystem vs "
        "LEARNING_DB_ENABLE_READS=1, LEARNING_DB_READ_FALLBACK_FILESYSTEM=0 DB-only):"
    )
    print(f"- eligible mains (non-template, with student_id): {report.eligible}")
    print(f"- skipped mains (no student_id): {report.skipped_no_student}")
    print(f"- parity_checked: {report.parity_checked}")
    print(f"- mismatches: {report.mismatch_count}")
    print(f"- errors: {len(report.errors)}")
    for mid, err in report.errors[:detail_limit]:
        print(f"  ERROR {mid}: {err}")
    if len(report.errors) > detail_limit:
        print(f"  … {len(report.errors) - detail_limit} more error(s)")
    for mm in report.mismatches[:detail_limit]:
        print("")
        print(f"  mismatch file_id={mm.file_id}")
        print(f"    path={mm.path}")
        print(f"    filesystem: {mm.filesystem_key}")
        print(f"    db_strict:  {mm.db_key}")
    if len(report.mismatches) > detail_limit:
        print(f"  … {len(report.mismatches) - detail_limit} more mismatch(es)")
