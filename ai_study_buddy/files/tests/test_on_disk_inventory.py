"""Tests for ai_study_buddy.files.on_disk_inventory."""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

from ai_study_buddy.files.main_pdfs import OnDiskMainPdfRow
from ai_study_buddy.files.on_disk_inventory import (
    FilterCriteria,
    OnDiskMainPdfCard,
    enrich_on_disk_main_pdf,
    filter_main_pdf_cards,
    inventory_meta,
    should_show_is_registered_filter,
    distinct_book_group_names,
    workflow_filter_options,
    filter_dropdown_options,
)
from ai_study_buddy.files.path_facets import infer_path_facets
from ai_study_buddy.files.pdf_registry_paths import RegistryPathIndex


def _row(path: Path, root_id: str = "daydreamedu") -> OnDiskMainPdfRow:
    return OnDiskMainPdfRow(
        absolute_path=path.resolve(),
        basename=path.name,
        root_id=root_id,
        facets=infer_path_facets(path, root_id=root_id),
    )


def test_enrich_unregistered_completion(tmp_path: Path) -> None:
    pdf = tmp_path / "_c_x.pdf"
    pdf.write_bytes(b"%PDF")
    row = _row(pdf)
    idx = RegistryPathIndex(
        registered_resolved_paths=frozenset(),
        scan_root_resolved_paths=frozenset(),
        pdf_files_row_count=0,
        scan_roots_row_count=0,
        file_by_resolved_path={},
    )
    pfm = MagicMock()
    review_repo = MagicMock()
    card = enrich_on_disk_main_pdf(
        row,
        index=idx,
        pfm=pfm,
        review_repo=review_repo,
        context_root=tmp_path,
    )
    assert card.is_registered is False
    assert card.has_template is False
    assert card.has_marking is False
    assert card.review_status is None


def _card(*, root_id: str, subject: str = "math") -> OnDiskMainPdfCard:
    return OnDiskMainPdfCard(
        absolute_path=f"/fake/{root_id}/file.pdf",
        basename="file.pdf",
        root_id=root_id,
        scope="completion",
        subject=subject,
        grade_or_scope="P4",
        doc_type="exam",
        book_group_name=None,
        student_email=None,
        parse_status="ok",
        is_registered=False,
    )


def test_filter_main_pdf_cards_root_id() -> None:
    cards = [_card(root_id="daydreamedu"), _card(root_id="goodnotes")]
    dd_only = filter_main_pdf_cards(cards, FilterCriteria(root_id="daydreamedu"))
    assert len(dd_only) == 1
    assert dd_only[0].root_id == "daydreamedu"
    all_roots = filter_main_pdf_cards(cards, FilterCriteria(root_id="all"))
    assert len(all_roots) == 2


def test_filter_dropdown_options_root_ids() -> None:
    cards = [_card(root_id="daydreamedu"), _card(root_id="goodnotes")]
    opts = filter_dropdown_options(cards, FilterCriteria(root_id="all"))
    assert set(opts.root_ids) == {"daydreamedu", "goodnotes"}
    assert opts.root_counts.get("all") == 2
    assert opts.root_counts.get("daydreamedu") == 1


def test_filter_main_pdf_cards_scope_and_subject(tmp_path: Path) -> None:
    p1 = tmp_path / "a.pdf"
    p2 = tmp_path / "b.pdf"
    cards = [
        enrich_on_disk_main_pdf(
            OnDiskMainPdfRow(
                absolute_path=p1,
                basename="a.pdf",
                root_id="daydreamedu",
                facets=infer_path_facets(
                    Path("/fake/Math/emma@x.com/P4/Exam/a.pdf"),
                    root_id="daydreamedu",
                ),
            ),
            index=RegistryPathIndex(frozenset(), frozenset(), 0, 0, {}),
            pfm=MagicMock(),
            review_repo=MagicMock(),
            context_root=tmp_path,
        ),
        enrich_on_disk_main_pdf(
            OnDiskMainPdfRow(
                absolute_path=p2,
                basename="b.pdf",
                root_id="daydreamedu",
                facets=infer_path_facets(
                    Path("/fake/English/emma@x.com/P4/Exercise/b.pdf"),
                    root_id="daydreamedu",
                ),
            ),
            index=RegistryPathIndex(frozenset(), frozenset(), 0, 0, {}),
            pfm=MagicMock(),
            review_repo=MagicMock(),
            context_root=tmp_path,
        ),
    ]
    filtered = filter_main_pdf_cards(
        cards,
        FilterCriteria(scope="completion", subject="math", doc_type="exam"),
    )
    assert len(filtered) == 1
    assert filtered[0].subject == "math"


def test_inventory_meta_show_is_registered_filter() -> None:
    cards = [
        SimpleNamespace(is_registered=True),
        SimpleNamespace(is_registered=False),
    ]
    meta = inventory_meta(cards, filtered_count=2)  # type: ignore[arg-type]
    assert meta.show_is_registered_filter is True
    assert meta.unregistered_in_index == 1


def _card(**kwargs: object) -> OnDiskMainPdfCard:
    defaults: dict[str, object] = {
        "absolute_path": "/x/a.pdf",
        "basename": "a.pdf",
        "root_id": "daydreamedu",
        "scope": "completion",
        "subject": "science",
        "grade_or_scope": "P6",
        "doc_type": "exam",
        "book_group_name": None,
        "student_email": "winston@example.com",
        "student_id": "winston",
        "parse_status": "ok",
        "is_registered": True,
        "has_template": None,
        "has_marking": None,
        "has_marking_amendment": None,
        "review_status": None,
    }
    defaults.update(kwargs)
    return OnDiskMainPdfCard(**defaults)  # type: ignore[arg-type]


def test_should_show_is_registered_filter_contextual() -> None:
    cards = [
        _card(is_registered=True, student_email="winston@example.com"),
        _card(
            is_registered=False,
            subject="math",
            student_email="winston@example.com",
        ),
    ]
    criteria = FilterCriteria(
        scope="completion",
        student="winston",
        subject="science",
        grade="P6",
        doc_type="exam",
    )
    assert should_show_is_registered_filter(cards, criteria) is False
    assert (
        should_show_is_registered_filter(
            cards,
            FilterCriteria(scope="completion", subject="all"),
        )
        is True
    )


def test_workflow_filter_options_shown_when_multiple_values() -> None:
    cards = [
        _card(is_registered=True, has_template=True, has_marking=True, review_status="completed"),
        _card(
            is_registered=True,
            has_template=False,
            has_marking=False,
            review_status="not_started",
        ),
    ]
    opts = workflow_filter_options(cards, FilterCriteria(scope="completion"))
    assert opts.show_has_template_filter is True
    assert opts.show_has_marking_filter is True
    assert opts.show_review_status_filter is True
    assert opts.review_status_options == ("not_started", "completed")
    assert opts.has_template_options == ("true", "false")
    assert opts.has_marking_options == ("true", "false")


def test_workflow_filter_options_hidden_when_uniform_multi_file() -> None:
    """≥2 registered completions with identical flags → no workflow filters (nothing to narrow)."""
    cards = [
        _card(is_registered=True, has_template=True, has_marking=False, review_status="not_started"),
        _card(is_registered=True, has_template=True, has_marking=False, review_status="not_started"),
    ]
    opts = workflow_filter_options(cards, FilterCriteria(scope="completion"))
    assert not opts.show_has_template_filter
    assert opts.has_template_options == ("true",)
    assert not opts.show_has_marking_filter
    assert opts.has_marking_options == ("false",)
    assert not opts.show_review_status_filter


def test_workflow_filter_options_hidden_for_single_registered() -> None:
    cards = [
        _card(is_registered=True, has_template=True, has_marking=False, review_status="not_started"),
    ]
    opts = workflow_filter_options(cards, FilterCriteria(scope="completion"))
    assert not opts.show_has_template_filter
    assert not opts.show_has_marking_filter
    assert not opts.show_review_status_filter


def test_filter_main_pdf_cards_has_template_and_review() -> None:
    cards = [
        _card(is_registered=True, has_template=True, review_status="completed"),
        _card(is_registered=True, has_template=False, review_status="not_started"),
    ]
    filtered = filter_main_pdf_cards(
        cards,
        FilterCriteria(scope="completion", has_template="true", review_status="completed"),
    )
    assert len(filtered) == 1
    assert filtered[0].has_template is True


def test_workflow_filter_options_template_only_true_in_slice() -> None:
    cards = [
        _card(is_registered=True, has_template=True, has_marking=False),
        _card(is_registered=True, has_template=True, has_marking=False),
    ]
    opts = workflow_filter_options(
        cards,
        FilterCriteria(scope="completion", student="winston"),
    )
    assert opts.has_template_options == ("true",)
    assert not opts.show_has_template_filter


def test_filter_dropdown_options_contextual() -> None:
    cards = [
        _card(
            subject="math",
            grade_or_scope="P6",
            doc_type="exam",
            student_email="a@example.com",
            student_id="a",
        ),
        _card(
            subject="science",
            grade_or_scope="P5",
            doc_type="book",
            book_group_name="Book A",
            student_email="b@example.com",
            student_id="b",
        ),
    ]
    opts = filter_dropdown_options(
        cards,
        FilterCriteria(scope="completion", subject="math"),
    )
    assert opts.scopes == ("completion",)
    assert opts.scope_counts == {"all": 1, "completion": 1}
    assert opts.subjects == ("math", "science")
    assert opts.subject_counts == {"all": 2, "math": 1, "science": 1}
    assert opts.grades == ("P6",)
    assert opts.grade_counts == {"all": 1, "P6": 1}
    assert opts.doc_types == ("exam",)
    assert opts.doc_type_counts == {"all": 1, "exam": 1}
    assert opts.student_ids == ("a",)
    assert opts.student_counts == {"": 1, "a": 1}


def test_workflow_filter_option_counts() -> None:
    cards = [
        _card(is_registered=True, has_template=True, has_marking=True, review_status="completed"),
        _card(
            is_registered=False,
            has_template=False,
            has_marking=False,
            review_status=None,
        ),
    ]
    opts = workflow_filter_options(cards, FilterCriteria(scope="completion"))
    assert opts.is_registered_counts == {"": 2, "true": 1, "false": 1}
    assert opts.has_template_counts == {"": 2, "true": 1}


def test_distinct_book_group_names() -> None:
    cards = [
        _card(doc_type="book", book_group_name="Alpha Book", subject="math", grade_or_scope="P6"),
        _card(doc_type="book", book_group_name="Beta Book", subject="math", grade_or_scope="P5"),
        _card(doc_type="exam", book_group_name=None, subject="math", grade_or_scope="P6"),
    ]
    criteria = FilterCriteria(scope="completion", subject="math", grade="P6", doc_type="book")
    assert distinct_book_group_names(cards, criteria) == ["Alpha Book"]
    assert distinct_book_group_names(cards, FilterCriteria(doc_type="exam")) == []
