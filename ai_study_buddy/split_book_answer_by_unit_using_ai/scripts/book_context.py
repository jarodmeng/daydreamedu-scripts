#!/usr/bin/env python3
"""
Shared book/registry helpers for split_book_answer_by_unit_using_ai scripts.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parent
# /<repo>/ai_study_buddy/split_book_answer_by_unit_using_ai
#                         ^ parents[1] = <repo>
REPO_ROOT = ROOT.parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from ai_study_buddy.pdf_file_manager.pdf_file_manager import PdfFileManager

ANSWER_KEYWORDS = (
    "answer",
    "answers",
    "worked solution",
    "worked solutions",
    "solution",
    "solutions",
    "答案",
    "解答",
    "参考答案",
    "详解",
)

MATH_PSLE_UNIT_ORDER = {
    "part b p1 to p5 commonly tested mcqs": 1,
    "part c p1 to p5 commonly tested saqs and laqs": 2,
    "part d p6 topical practice algebra": 3,
    "part d p6 topical practice fractions": 4,
    "part d p6 topical practice ratio": 5,
    "part d p6 topical practice percentage": 6,
    "part d p6 topical practice circles": 7,
    "part d p6 topical practice angles in geometric figures": 8,
    "part d p6 topical practice volume of solids and liquids": 9,
    "part d p6 topical practice average": 10,
    "part d p6 topical practice psle specimen paper set 1": 11,
    "specimen paper set 2": 12,
}

EPO_SECTION_ORDER = {
    "grammar_mcq": 0,
    "vocabulary_mcq": 15,
    "vocabulary_cloze": 30,
    "visual_text_comprehension": 45,
    "grammar_cloze": 60,
    "editing_spelling_grammar": 75,
    "comprehension_cloze": 90,
    "synthesis_transformation": 105,
    "comprehension_open_ended": 120,
}


def extract_system_message(prompt_md_path: Path) -> str:
    text = prompt_md_path.read_text(encoding="utf-8")
    marker = "## 1. System message"
    idx = text.find(marker)
    if idx == -1:
        raise ValueError(f"Could not find '{marker}' in {prompt_md_path}")
    rest = text[idx + len(marker) :]
    match = re.search(r"```text\s*\n(.*?)```", rest, re.DOTALL)
    if not match:
        raise ValueError(f"Could not find system message code block in {prompt_md_path}")
    return match.group(1).strip()


def find_book_group(book_label: str):
    mgr = PdfFileManager()
    for group in mgr.list_file_groups("book"):
        if group.label == book_label:
            return group
    raise ValueError(f"Book group not found: {book_label}")


def select_daydreamedu_files(group):
    return [m.file for m in group.members if m.file and "/DaydreamEdu/" in m.file.path]


def identify_front_matter(files):
    for file in files:
        unit = ""
        if isinstance(file.metadata, dict):
            unit = (file.metadata.get("unit") or "").lower()
        name = file.name.lower().replace("_", " ").replace("-", " ")
        unit = unit.replace("_", " ").replace("-", " ")
        if "front matter" in unit or "preface + toc" in unit or "front matter" in name or "preface + toc" in name:
            return file
    raise ValueError("Could not identify front matter file")


def identify_answer_file(files):
    candidates = []
    for file in files:
        name = file.name.lower()
        unit = ""
        if isinstance(file.metadata, dict):
            unit = (file.metadata.get("unit") or "").lower()
        haystacks = (name, unit)
        if any(keyword in hay for hay in haystacks for keyword in ANSWER_KEYWORDS):
            candidates.append(file)
    if len(candidates) != 1:
        names = [c.name for c in candidates]
        raise ValueError(f"Expected exactly one answer file, found {len(candidates)}: {names}")
    return candidates[0]


def parse_epo_unit_index(file) -> int | None:
    basename = file.name
    if basename.lower().endswith(".pdf"):
        basename = basename[:-4]
    basename = basename.removeprefix("_c_").removeprefix("c_")
    match = re.fullmatch(r"EPO_(.+)_(\d{2})(?: \(empty\))?", basename)
    if not match:
        return None

    section = match.group(1).lower().replace("-", "_")
    practice = int(match.group(2))
    offset = EPO_SECTION_ORDER.get(section)
    if offset is None:
        raise ValueError(f"Unknown EPO section in {file.name}: {section}")
    return offset + practice


def parse_unit_index(file) -> int:
    epo_index = parse_epo_unit_index(file)
    if epo_index is not None:
        return epo_index

    match = re.search(r"_Math Model P5 and P6_(\d{3})_", file.name)
    if match:
        return int(match.group(1))

    match = re.search(r" - (\d{2}) ", file.name)
    if match:
        return int(match.group(1))

    if isinstance(file.metadata, dict):
        unit = file.metadata.get("unit") or ""
        unit_norm = unit.strip().lower()

        match = re.match(r"(\d{2})\b", unit)
        if match:
            return int(match.group(1))
        match = re.search(r"\btopic\s+(\d+)\b", unit, re.IGNORECASE)
        if match:
            return int(match.group(1))
        if unit_norm in MATH_PSLE_UNIT_ORDER:
            return MATH_PSLE_UNIT_ORDER[unit_norm]
        match = re.search(r"\bpractice\s+(\d+)\b", unit, re.IGNORECASE)
        if match:
            return int(match.group(1))
        match = re.search(r"\bsituational writing practice\s+(\d+)\b", unit, re.IGNORECASE)
        if match:
            return int(match.group(1))
        match = re.search(r"模拟考卷\s*(\d+)", unit)
        if match:
            return int(match.group(1))
        match = re.search(r"作文\s*(\d+)", unit)
        if match:
            return 16 + int(match.group(1))
        if re.search(r"作文\s*范文", unit):
            return 22
        if re.search(r"试卷蓝图与复习指南", unit):
            return 23
        if re.search(r"\bconcept maps\b", unit, re.IGNORECASE):
            return 17
        match = re.search(r"\bspecimen paper set\s+(\d+)\b", unit, re.IGNORECASE)
        if match:
            return 17 + int(match.group(1))

    match = re.search(r"\btopic\s+(\d+)\b", file.name, re.IGNORECASE)
    if match:
        return int(match.group(1))

    file_name_norm = file.name.strip().lower().removeprefix("_c_").removeprefix("c_")
    if file_name_norm.endswith(".pdf"):
        file_name_norm = file_name_norm[:-4]
    if file_name_norm in MATH_PSLE_UNIT_ORDER:
        return MATH_PSLE_UNIT_ORDER[file_name_norm]

    match = re.search(r"\bpractice\s+(\d+)\b", file.name, re.IGNORECASE)
    if match:
        return int(match.group(1))
    match = re.search(r"\bsituational writing practice\s+(\d+)\b", file.name, re.IGNORECASE)
    if match:
        return int(match.group(1))
    match = re.search(r"模拟考卷\s*(\d+)", file.name)
    if match:
        return int(match.group(1))
    match = re.search(r"作文\s*(\d+)", file.name)
    if match:
        return 16 + int(match.group(1))
    if re.search(r"作文\s*范文", file.name):
        return 22
    if re.search(r"试卷蓝图与复习指南", file.name):
        return 23
    if re.search(r"\bconcept maps\b", file.name, re.IGNORECASE):
        return 17
    match = re.search(r"\bspecimen paper set\s+(\d+)\b", file.name, re.IGNORECASE)
    if match:
        return 17 + int(match.group(1))

    raise ValueError(f"Could not parse unit index from {file.name}")


def build_unit_list(files, front_matter_file, answer_file):
    units = []
    excluded_ids = {answer_file.id}
    if front_matter_file is not None:
        excluded_ids.add(front_matter_file.id)

    for file in files:
        if file.id in excluded_ids:
            continue
        units.append(
            {
                "unit_index": parse_unit_index(file),
                "unit_file": file.name,
                "unit_label": file.metadata.get("unit") if isinstance(file.metadata, dict) else file.name,
            }
        )

    units.sort(key=lambda item: item["unit_index"])
    return units


def build_user_payload(
    book_label: str,
    front_matter_file,
    answer_file,
    unit_files: list[dict],
    *,
    answer_file_display_name: str | None = None,
    answer_page_count_override: int | None = None,
) -> dict:
    page_count = answer_page_count_override if answer_page_count_override is not None else answer_file.page_count
    return {
        "book_label": book_label,
        "front_matter_file": front_matter_file.name if front_matter_file is not None else None,
        "answer_file": answer_file_display_name or answer_file.name,
        "answer_page_count": page_count,
        "unit_files": unit_files,
    }
