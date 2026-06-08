#!/usr/bin/env python3
"""Refresh Winston P6/PSLE math error-tag HTML reports and math_error_types distribution.

Reads review notes from the learning DB (``LEARNING_DB_ENABLE_READS=1``) for
winston × singapore_primary_math completions that are marked and review-completed
(P6 + PSLE grade filter). In-scope incorrect = resolved wrong/partial, excluding
disqualified and amended-to-correct.

Writes:
- ``ai_study_buddy/buddy_console/frontend/public/winston_115_incorrect_questions.html``
- ``ai_study_buddy/buddy_console/frontend/public/winston_115_incorrect_by_paper.html``

Optionally patches the distribution table in ``math_error_types.md`` (``--update-md``).

Example::

  LEARNING_DB_ENABLE_READS=1 python3 refresh_winston_math_error_review_reports.py --update-md
"""

from __future__ import annotations

import argparse
import html as html_mod
import json
import os
import re
import sys
from collections import Counter
from pathlib import Path
from urllib.parse import quote, urlencode

_SCRIPT_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _SCRIPT_DIR.parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from ai_study_buddy.files import build_enriched_inventory, build_main_pdf_index_for_roots, filter_main_pdf_cards
from ai_study_buddy.files.on_disk_inventory import FilterCriteria
from ai_study_buddy.files.pdf_registry_paths import RegistryPathIndex
from ai_study_buddy.marking.core.artifact_lookup import find_marking_artifacts_for_attempt
from ai_study_buddy.marking.review.amendment_service import resolve_marking_result
from ai_study_buddy.marking.review.repository import StudentReviewRepository
from ai_study_buddy.pdf_file_manager import PdfFileManager

_TAG_RE = re.compile(
    r"\[(misreading|miscomputation|misanswering|misattempt|no attempt|mistranslation(?:\s+L[123])?)\]",
    re.I,
)

_TAG_COLORS = {
    "misreading": "#0e7490",
    "mistranslation l1": "#8b5cf6",
    "mistranslation l2": "#7c3aed",
    "mistranslation l3": "#5b21b6",
    "mistranslation": "#5b21b6",
    "miscomputation": "#15803d",
    "misanswering": "#b45309",
    "misattempt": "#a16207",
    "no attempt": "#64748b",
}

_SECTION_ORDER = [
    ("misreading", "Misreading"),
    ("mistranslation l1", "Mistranslation L1"),
    ("mistranslation l2", "Mistranslation L2"),
    ("mistranslation l3", "Mistranslation L3"),
    ("mistranslation", "Mistranslation"),
    ("miscomputation", "Miscomputation"),
    ("misanswering", "Misanswering"),
    ("misattempt", "Misattempt"),
    ("no attempt", "No attempt"),
]

_PUBLIC_DIR = _REPO_ROOT / "ai_study_buddy/buddy_console/frontend/public"
_MD_PATH = (
    _REPO_ROOT
    / "ai_study_buddy/context/subject_understandings/singapore_primary_math/math_error_types.md"
)


def _extract_tags(note: str) -> list[str]:
    return [re.sub(r"\s+", " ", m.group(1).lower()) for m in _TAG_RE.finditer(note or "")]


def _is_incorrect(q: dict) -> bool:
    outcome = (q.get("outcome") or "").lower()
    if outcome in ("correct", "disqualified", "excluded_disqualified"):
        return False
    if outcome in ("wrong", "incorrect", "partial"):
        return True
    em, mm = q.get("earned_marks"), q.get("max_marks")
    if isinstance(em, (int, float)) and isinstance(mm, (int, float)):
        return mm > 0 and em < mm
    return False


def _qreview_map(rs: dict) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for row in rs.get("question_reviews") or []:
        if isinstance(row, dict) and row.get("result_id"):
            out[str(row["result_id"])] = row
    return out


def _first_tag_key(tags: list[str]) -> str:
    order = [key for key, _ in _SECTION_ORDER]
    for key in order:
        for tag in tags:
            if tag == key:
                return key
    return tags[0] if tags else "untagged"


def _tag_span(tag: str) -> str:
    color = _TAG_COLORS.get(tag, "#64748b")
    label = f"[{tag}]" if tag != "no attempt" else "[no attempt]"
    if tag.startswith("mistranslation l"):
        label = f"[mistranslation {tag.split()[-1].upper()}]"
    return f'<span class="tag" style="background:{color}">{html_mod.escape(label)}</span>'


def _abridge(note: str, limit: int = 160) -> str:
    text = " ".join((note or "").split())
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"


def _review_link(*, attempt_id: str, result_id: str, question_index: int | None) -> str:
    params: dict[str, str] = {
        "attempt_id": attempt_id,
        "student_id": "winston",
        "result_id": result_id,
    }
    if question_index is not None:
        params["question_index"] = str(question_index)
    return "http://127.0.0.1:5178/review?" + urlencode(params, quote_via=quote)


def _lan_script() -> str:
    return """<script>
(function () {
  const BUDDY_CONSOLE_PORT = 5178;
  const LAN_HOST = "192.168.86.249";
  const host = (location.protocol === "file:" || !location.hostname) ? LAN_HOST : location.hostname;
  const base = "http://" + host + ":" + BUDDY_CONSOLE_PORT;
  document.querySelectorAll('a.open[href*="127.0.0.1:5178"]').forEach(function (a) {
    a.href = a.href.replace("http://127.0.0.1:5178", base);
  });
  var urlEl = document.getElementById("buddy-console-url");
  if (urlEl) urlEl.textContent = host + ":" + BUDDY_CONSOLE_PORT;
})();
</script>"""


def collect_items(*, context_root: Path) -> tuple[list[dict], int]:
    if os.environ.get("LEARNING_DB_ENABLE_READS", "").strip().lower() not in {"1", "true", "yes"}:
        raise SystemExit("Set LEARNING_DB_ENABLE_READS=1 — review notes live in study_buddy.db")

    pfm = PdfFileManager()
    index = RegistryPathIndex.from_pdf_file_manager(pfm)
    review_repo = StudentReviewRepository(context_root=context_root)
    rows = build_main_pdf_index_for_roots(exclude_activity_note_completions=True)
    cards = build_enriched_inventory(
        rows,
        index=index,
        pfm=pfm,
        review_repo=review_repo,
        context_root=context_root,
    )
    filtered = filter_main_pdf_cards(
        cards,
        FilterCriteria(
            student="winston",
            subject=("math",),
            grade=("P6", "PSLE"),
            has_marking="true",
            review_status="completed",
        ),
        pfm=pfm,
    )

    items: list[dict] = []
    for card in filtered:
        attempt_id = card.registry_file_id
        if not attempt_id:
            continue
        refs = find_marking_artifacts_for_attempt(attempt_id, manager=pfm, context_root=context_root)
        if not refs:
            continue
        mr_path = refs[0].marking_result_json
        base = json.loads(mr_path.read_text(encoding="utf-8"))
        stem = mr_path.stem
        rs = review_repo.load_review_state(
            student_id="winston",
            subject_context="singapore_primary_math",
            artifact_stem=stem,
        )
        am_path = context_root / "marking_amendments/winston/singapore_primary_math" / f"{stem}.json"
        amendment = json.loads(am_path.read_text(encoding="utf-8")) if am_path.exists() else {}
        resolved = resolve_marking_result(base_payload=base, amendment_state=amendment)
        qmap = _qreview_map(rs)
        unit = card.normal_name or card.basename
        page_map = {
            e.get("result_id"): e for e in (resolved.get("context") or {}).get("question_page_map") or []
        }
        for q in resolved.get("question_results") or []:
            rid = q.get("result_id")
            if not rid or not _is_incorrect(q):
                continue
            qr = qmap.get(str(rid)) or {}
            note = (qr.get("note_text") or "").strip()
            tags = _extract_tags(note)
            page = page_map.get(rid) or {}
            items.append(
                {
                    "unit": unit,
                    "attempt_id": attempt_id,
                    "result_id": str(rid),
                    "note": note,
                    "tags": tags,
                    "first_tag": _first_tag_key(tags),
                    "question_index": page.get("question_index"),
                }
            )
    return items, len(filtered)


def summarize(items: list[dict], *, file_count: int) -> dict:
    tag_inst = Counter()
    first_tag = Counter()
    for it in items:
        for tag in it["tags"]:
            tag_inst[tag] += 1
        if it["tags"]:
            first_tag[it["first_tag"]] += 1
    mt_l1 = tag_inst.get("mistranslation l1", 0)
    mt_l2 = tag_inst.get("mistranslation l2", 0)
    mt_l3 = tag_inst.get("mistranslation l3", 0)
    mt_plain = tag_inst.get("mistranslation", 0)
    mt_total = mt_l1 + mt_l2 + mt_l3 + mt_plain
    tag_sum = sum(tag_inst.values())
    question_count = len(items)
    multi = sum(1 for it in items if len(it["tags"]) > 1)
    return {
        "file_count": file_count,
        "question_count": question_count,
        "tag_instance_sum": tag_sum,
        "multi_tag_questions": multi,
        "tag_instances": dict(tag_inst),
        "first_tag_groups": dict(first_tag),
        "mistranslation_total": mt_total,
        "mistranslation_l1": mt_l1,
        "mistranslation_l2": mt_l2,
        "mistranslation_l3": mt_l3,
        "misreading": tag_inst.get("misreading", 0),
        "miscomputation": tag_inst.get("miscomputation", 0),
        "misanswering": tag_inst.get("misanswering", 0),
        "no_attempt": tag_inst.get("no attempt", 0),
    }


def render_by_type_html(items: list[dict], summary: dict) -> str:
    si = summary["tag_instances"]
    summary_line = (
        f"misreading: {si.get('misreading', 0)} · "
        f"mistranslation L1: {si.get('mistranslation l1', 0)} · "
        f"mistranslation L2: {si.get('mistranslation l2', 0)} · "
        f"mistranslation L3: {si.get('mistranslation l3', 0)} · "
        f"miscomputation: {si.get('miscomputation', 0)} · "
        f"misanswering: {si.get('misanswering', 0)} · "
        f"no attempt: {si.get('no attempt', 0)}"
    )
    qn = summary["question_count"]
    rows: list[str] = []
    by_first: dict[str, list[dict]] = {key: [] for key, _ in _SECTION_ORDER}
    for it in items:
        key = it["first_tag"] if it["first_tag"] in by_first else "misanswering"
        by_first.setdefault(key, []).append(it)

    for key, title in _SECTION_ORDER:
        group = by_first.get(key) or []
        if not group:
            continue
        group.sort(key=lambda x: (x["unit"].casefold(), x["result_id"]))
        color = _TAG_COLORS.get(key, "#64748b")
        rows.append(
            f'<tr class="section"><td colspan="5">'
            f'<span class="section-tag" style="background:{color}">{html_mod.escape(title)}</span> '
            f'<span class="section-count">{len(group)} questions</span></td></tr>'
        )
        for it in group:
            tag_html = " ".join(_tag_span(t) for t in it["tags"]) or '<span class="tag" style="background:#94a3b8">untagged</span>'
            link = _review_link(
                attempt_id=it["attempt_id"],
                result_id=it["result_id"],
                question_index=it["question_index"],
            )
            rows.append(
                "<tr>"
                f'<td class="unit">{html_mod.escape(it["unit"])}</td>'
                f'<td class="rid">{html_mod.escape(it["result_id"])}</td>'
                f'<td class="tags">{tag_html}</td>'
                f'<td class="note">{html_mod.escape(_abridge(it["note"]))}</td>'
                f'<td class="act"><a class="open" href="{html_mod.escape(link)}" target="_blank" rel="noreferrer">open ↗</a></td>'
                "</tr>"
            )

    body = "\n".join(rows)
    return f"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Winston P6/PSLE math — {qn} incorrect questions</title>
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; margin: 24px; color: #111; background: #f8fafc; }}
  h1 {{ font-size: 20px; margin: 0 0 4px; }}
  p.sub {{ color: #475569; margin: 0 0 8px; font-size: 13px; }}
  p.summary {{ color: #64748b; margin: 0 0 16px; font-size: 12px; }}
  .note-banner {{ background: #eff6ff; border: 1px solid #bfdbfe; color: #1e40af; padding: 10px 14px; border-radius: 8px; font-size: 12.5px; margin-bottom: 16px; }}
  table {{ border-collapse: collapse; width: 100%; background: #fff; box-shadow: 0 1px 3px rgba(0,0,0,.08); border-radius: 8px; overflow: hidden; }}
  th, td {{ padding: 8px 12px; border-bottom: 1px solid #e5e7eb; text-align: left; vertical-align: top; font-size: 13px; }}
  th {{ background: #f1f5f9; font-size: 11px; text-transform: uppercase; letter-spacing: .04em; color: #475569; position: sticky; top: 0; z-index: 1; }}
  tr.section td {{ background: #f8fafc; border-bottom: 1px solid #cbd5e1; padding: 10px 12px; }}
  .section-tag {{ color: #fff; padding: 3px 10px; border-radius: 999px; font-size: 12px; font-weight: 600; }}
  .section-count {{ color: #64748b; font-size: 12px; margin-left: 6px; }}
  td.unit {{ max-width: 280px; font-weight: 500; }}
  td.rid {{ color: #2563eb; font-weight: 600; white-space: nowrap; width: 72px; }}
  td.tags {{ white-space: nowrap; }}
  .tag {{ color: #fff; padding: 2px 7px; border-radius: 999px; font-size: 10px; font-weight: 600; margin-right: 4px; display: inline-block; }}
  td.note {{ color: #334155; max-width: 480px; font-size: 12px; line-height: 1.4; }}
  a.open {{ display: inline-block; background: #2563eb; color: #fff; padding: 4px 10px; border-radius: 6px; text-decoration: none; font-size: 12px; font-weight: 600; white-space: nowrap; }}
  a.open:hover {{ background: #1d4ed8; }}
</style>
</head>
<body>
<h1>Winston — {qn} in-scope incorrect questions (P6 / PSLE math)</h1>
<p class="sub">Sorted by first error-type tag (mistranslation L1 → L2 → L3), then completion file name, then question id.</p>
<p class="summary">{html_mod.escape(summary_line)}</p>
<div class="note-banner">Buddy Console at <code id="buddy-console-url">192.168.86.249:5178</code> must be running before opening links. Mistranslation uses <code>[mistranslation L1|L2|L3]</code> severity levels.</div>
<table>
<thead><tr>
  <th>Completion file</th><th>Q</th><th>Tags</th><th>Review note (abridged)</th><th></th>
</tr></thead>
<tbody>
{body}
</tbody>
</table>
{_lan_script()}
</body></html>
"""


def render_by_paper_html(items: list[dict], summary: dict) -> str:
    qn = summary["question_count"]
    papers = sorted({it["unit"] for it in items}, key=str.casefold)
    by_paper: dict[str, list[dict]] = {p: [] for p in papers}
    for it in items:
        by_paper[it["unit"]].append(it)

    rows: list[str] = []
    for paper in papers:
        group = sorted(by_paper[paper], key=lambda x: (x["question_index"] or 10_000, x["result_id"]))
        rows.append(
            f'<tr class="section"><td colspan="5">'
            f'<span class="paper">{html_mod.escape(paper)}</span>'
            f'<span class="section-count">{len(group)} incorrect</span></td></tr>'
        )
        for it in group:
            tag_html = " ".join(_tag_span(t) for t in it["tags"])
            idx = it["question_index"]
            idx_cell = str(idx) if idx is not None else "—"
            link = _review_link(
                attempt_id=it["attempt_id"],
                result_id=it["result_id"],
                question_index=it["question_index"],
            )
            rows.append(
                "<tr>"
                f'<td class="qidx">{html_mod.escape(idx_cell)}</td>'
                f'<td class="rid">{html_mod.escape(it["result_id"])}</td>'
                f'<td class="tags">{tag_html}</td>'
                f'<td class="note">{html_mod.escape(_abridge(it["note"]))}</td>'
                f'<td class="act"><a class="open" href="{html_mod.escape(link)}" target="_blank" rel="noreferrer">open ↗</a></td>'
                "</tr>"
            )

    body = "\n".join(rows)
    return f"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Winston P6/PSLE math — incorrect questions by paper</title>
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; margin: 24px; color: #111; background: #f8fafc; }}
  h1 {{ font-size: 20px; margin: 0 0 4px; }}
  p.sub {{ color: #475569; margin: 0 0 16px; font-size: 13px; }}
  .note-banner {{ background: #eff6ff; border: 1px solid #bfdbfe; color: #1e40af; padding: 10px 14px; border-radius: 8px; font-size: 12.5px; margin-bottom: 16px; }}
  table {{ border-collapse: collapse; width: 100%; background: #fff; box-shadow: 0 1px 3px rgba(0,0,0,.08); border-radius: 8px; overflow: hidden; }}
  th, td {{ padding: 8px 12px; border-bottom: 1px solid #e5e7eb; text-align: left; vertical-align: top; font-size: 13px; }}
  th {{ background: #f1f5f9; font-size: 11px; text-transform: uppercase; letter-spacing: .04em; color: #475569; position: sticky; top: 0; z-index: 1; }}
  tr.section td {{ background: #eef2ff; border-bottom: 1px solid #c7d2fe; padding: 10px 12px; }}
  .paper {{ font-weight: 600; color: #1e3a8a; }}
  .section-count {{ color: #64748b; font-size: 12px; margin-left: 8px; font-weight: 400; }}
  td.qidx {{ color: #64748b; width: 36px; text-align: right; font-variant-numeric: tabular-nums; }}
  td.rid {{ color: #2563eb; font-weight: 600; white-space: nowrap; width: 72px; }}
  td.tags {{ white-space: nowrap; }}
  .tag {{ color: #fff; padding: 2px 7px; border-radius: 999px; font-size: 10px; font-weight: 600; margin-right: 4px; display: inline-block; }}
  td.note {{ color: #334155; max-width: 520px; font-size: 12px; line-height: 1.4; }}
  a.open {{ display: inline-block; background: #2563eb; color: #fff; padding: 4px 10px; border-radius: 6px; text-decoration: none; font-size: 12px; font-weight: 600; white-space: nowrap; }}
  a.open:hover {{ background: #1d4ed8; }}
</style>
</head>
<body>
<h1>Winston — incorrect questions by paper (P6 / PSLE math)</h1>
<p class="sub">{qn} in-scope incorrect questions across {len(papers)} papers, sorted by paper name then question index.</p>
<div class="note-banner">Buddy Console at <code id="buddy-console-url">192.168.86.249:5178</code> must be running before opening links. Each link opens <code>/review</code> with <code>attempt_id</code>, URL-encoded <code>result_id</code>, and <code>question_index</code>.</div>
<table>
<thead><tr>
  <th>#</th><th>Q id</th><th>Tags</th><th>Review note (abridged)</th><th></th>
</tr></thead>
<tbody>
{body}
</tbody>
</table>
{_lan_script()}
</body></html>
"""


def _pct(n: int, denom: int) -> str:
    if denom <= 0:
        return "~0%"
    return f"~{round(100 * n / denom)}%"


def update_math_error_types_md(summary: dict) -> None:
    text = _MD_PATH.read_text(encoding="utf-8")
    qn = summary["question_count"]
    fc = summary["file_count"]
    tag_sum = summary["tag_instance_sum"]
    multi = summary["multi_tag_questions"]

    overview_old = (
        "completions (115 in-scope incorrect questions across 80 marked, review-completed files;"
    )
    overview_new = (
        f"completions ({qn} in-scope incorrect questions across {fc} marked, review-completed files;"
    )
    if overview_old in text:
        text = text.replace(overview_old, overview_new)
    elif "in-scope incorrect questions across" in text:
        text = re.sub(
            r"\(\d+ in-scope incorrect questions across \d+ marked, review-completed files;",
            f"({qn} in-scope incorrect questions across {fc} marked, review-completed files;",
            text,
            count=1,
        )

    section_old = "## Approximate distribution (Winston, 115 in-scope incorrect)"
    section_new = f"## Approximate distribution (Winston, {qn} in-scope incorrect)"
    text = text.replace(section_old, section_new)

    intro_old = (
        f"Classification from Winston's own `[tag]` prefixes on review notes (authoritative). All 115\n"
        f"in-scope incorrect questions are tagged. Five questions carry two tags, so tag instances sum\n"
        f"to **120** over 115 questions:"
    )
    intro_new = (
        f"Classification from Winston's own `[tag]` prefixes on review notes (authoritative). All {qn}\n"
        f"in-scope incorrect questions are tagged. {multi} questions carry two tags, so tag instances sum\n"
        f"to **{tag_sum}** over {qn} questions:"
    )
    text = text.replace(intro_old, intro_new)

    mt = summary["mistranslation_total"]
    table = f"""| Type | Count | Share |
|------|------:|------:|
| Mistranslation | {mt} | {_pct(mt, tag_sum)} |
| — L1 (localized slip) | {summary['mistranslation_l1']} | {_pct(summary['mistranslation_l1'], tag_sum)} |
| — L2 (partly sound strategy) | {summary['mistranslation_l2']} | {_pct(summary['mistranslation_l2'], tag_sum)} |
| — L3 (strategy not sound) | {summary['mistranslation_l3']} | {_pct(summary['mistranslation_l3'], tag_sum)} |
| Miscomputation | {summary['miscomputation']} | {_pct(summary['miscomputation'], tag_sum)} |
| Misanswering (4a + 4b) | {summary['misanswering']} | {_pct(summary['misanswering'], tag_sum)} |
| Misreading (givens) | {summary['misreading']} | {_pct(summary['misreading'], tag_sum)} |
| Incomplete / not-attempted (`[no attempt]`) | {summary['no_attempt']} | {_pct(summary['no_attempt'], qn)} |"""

    text = re.sub(
        r"\| Type \| Count \| Share \|\n\|------\|------:\|------:\|\n(?:\|[^\n]+\n)+",
        table + "\n",
        text,
        count=1,
    )

    denom_old = "**120 tag instances** (115 questions; five carry two tags)"
    denom_new = f"**{tag_sum} tag instances** ({qn} questions; {multi} carry two tags)"
    text = text.replace(denom_old, denom_new)

    l_sum = summary["mistranslation_l1"] + summary["mistranslation_l2"] + summary["mistranslation_l3"]
    text = re.sub(
        r"L1 \+ L2 \+ L3 = \d+ mistranslation tags \(~50% of 120\)\.",
        f"L1 + L2 + L3 = {l_sum} mistranslation tags ({_pct(l_sum, tag_sum)} of {tag_sum}).",
        text,
        count=1,
    )
    text = re.sub(
        r"`\[no attempt\]` share uses \*\*115 questions\*\* \(5 of 115 ≈ 4%\)",
        f"`[no attempt]` share uses **{qn} questions** ({summary['no_attempt']} of {qn} ≈ {round(100*summary['no_attempt']/qn)}%)",
        text,
        count=1,
    )

    l2l3 = summary["mistranslation_l2"] + summary["mistranslation_l3"]
    text = re.sub(
        r"are \*\*L2 or L3\*\* \(\d+ of \d+\)",
        f"are **L2 or L3** ({l2l3} of {mt})",
        text,
        count=1,
    )

    _MD_PATH.write_text(text, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--context-root",
        type=Path,
        default=_REPO_ROOT / "ai_study_buddy/context",
        help="AI Study Buddy context root (default: ai_study_buddy/context)",
    )
    parser.add_argument(
        "--update-md",
        action="store_true",
        help="Patch distribution section in math_error_types.md",
    )
    args = parser.parse_args()

    items, file_count = collect_items(context_root=args.context_root.resolve())
    summary = summarize(items, file_count=file_count)

    untagged = [it for it in items if not it["tags"]]
    no_note = [it for it in items if not it["note"]]
    if untagged or no_note:
        print(f"WARNING: untagged={len(untagged)} no_note={len(no_note)}", file=sys.stderr)

    _PUBLIC_DIR.mkdir(parents=True, exist_ok=True)
    by_type_path = _PUBLIC_DIR / "winston_115_incorrect_questions.html"
    by_paper_path = _PUBLIC_DIR / "winston_115_incorrect_by_paper.html"
    by_type_path.write_text(render_by_type_html(items, summary), encoding="utf-8")
    by_paper_path.write_text(render_by_paper_html(items, summary), encoding="utf-8")

    if args.update_md:
        update_math_error_types_md(summary)

    print(json.dumps(summary, indent=2))
    print(f"Wrote {by_type_path}")
    print(f"Wrote {by_paper_path}")
    if args.update_md:
        print(f"Updated {_MD_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
