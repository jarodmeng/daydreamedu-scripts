#!/usr/bin/env python3
"""Student File Browser — filter-first operator inventory for on-disk main PDFs."""

from __future__ import annotations

import argparse
import json
import os
import sys
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, urlparse

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from ai_study_buddy.files import (
    build_enriched_inventory,
    build_main_pdf_index_for_roots,
    filter_main_pdf_cards,
    sort_main_pdf_cards,
    inventory_meta,
    list_daydreamedu_leaf_folders_under_root,
    list_goodnotes_leaf_folders_under_root,
    resolve_daydreamedu_root,
    resolve_goodnotes_root,
    filter_meta_for_response,
)
from ai_study_buddy.files.pdf_registry_paths import RegistryPathIndex
from ai_study_buddy.files.main_pdfs import OnDiskMainPdfRow
from ai_study_buddy.marking.review.repository import StudentReviewRepository
from ai_study_buddy.pdf_file_manager import PdfFileManager
from ai_study_buddy.student_file_browser.filters import filter_criteria_from_query
from ai_study_buddy.student_file_browser.path_guard import safe_resolve_under_root

FILES_VERSION = "0.3.6"
ROOT_IDS = ("daydreamedu", "goodnotes")
STATIC_DIR = Path(__file__).resolve().parent / "static"
DEFAULT_CONTEXT_ROOT = Path(__file__).resolve().parent.parent / "context"
INDEX_WARN_THRESHOLD = 2000


def _default_context_root() -> Path:
    raw = os.environ.get("AI_STUDY_BUDDY_CONTEXT_ROOT")
    if raw:
        return Path(raw).expanduser().resolve()
    return DEFAULT_CONTEXT_ROOT.resolve()


def _roots_config() -> dict[str, Path]:
    out: dict[str, Path] = {}
    dd = resolve_daydreamedu_root()
    if dd is not None:
        out["daydreamedu"] = dd
    gn = resolve_goodnotes_root()
    if gn is not None:
        out["goodnotes"] = gn
    return out


def _leaf_paths_set(root: Path, *, rid: str) -> frozenset[Path]:
    rr = root.resolve()
    if rid == "daydreamedu":
        leaves = list_daydreamedu_leaf_folders_under_root(root)
    elif rid == "goodnotes":
        leaves = list_goodnotes_leaf_folders_under_root(root)
    else:
        return frozenset()
    return frozenset(p.resolve() for p in leaves)


def _pdf_blocked_not_in_leaf(leaves: frozenset[Path], pdf_path: Path) -> bool:
    return pdf_path.resolve().parent not in leaves


def _content_disposition_inline(filename: str) -> str:
    fallback_ascii = filename.encode("ascii", "replace").decode("ascii").replace('"', "")
    utf8_encoded = quote(filename, safe="")
    return f'inline; filename="{fallback_ascii}"; filename*=UTF-8\'\'{utf8_encoded}'


def _open_browser_delayed(url: str, delay_sec: float = 0.35) -> None:
    def _run() -> None:
        time.sleep(delay_sec)
        try:
            webbrowser.open(url)
        except Exception:
            pass

    threading.Thread(target=_run, daemon=True).start()


class StudentFileBrowserHandler(BaseHTTPRequestHandler):
    roots: dict[str, Path] = {}
    leaf_dirs_by_id: dict[str, frozenset[Path]] = {}
    index_rows: list[OnDiskMainPdfRow] = []
    enriched_cache: list | None = None
    context_root: Path = DEFAULT_CONTEXT_ROOT
    index_warn_threshold: int = INDEX_WARN_THRESHOLD

    def log_message(self, format, *args):
        return

    def _send_json(self, code: int, payload: object) -> None:
        data = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _send_error_json(self, code: int, message: str) -> None:
        self._send_json(code, {"error": message})

    def _serve_file(self, path: Path, content_type: str) -> None:
        data = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _get_enriched_cards(self):
        if self.enriched_cache is not None:
            return self.enriched_cache
        pfm = PdfFileManager()
        index = RegistryPathIndex.from_pdf_file_manager(pfm)
        review_repo = StudentReviewRepository(context_root=self.context_root)
        self.enriched_cache = build_enriched_inventory(
            self.index_rows,
            index=index,
            pfm=pfm,
            review_repo=review_repo,
            context_root=self.context_root,
        )
        return self.enriched_cache

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
        if path == "/":
            self._serve_file(STATIC_DIR / "index.html", "text/html; charset=utf-8")
            return
        if path == "/app.css":
            self._serve_file(STATIC_DIR / "app.css", "text/css; charset=utf-8")
            return
        if path == "/app.js":
            self._serve_file(STATIC_DIR / "app.js", "application/javascript; charset=utf-8")
            return
        if path == "/api/health":
            self._send_json(
                200,
                {
                    "status": "ok",
                    "index_count": len(self.index_rows),
                    "files_version": FILES_VERSION,
                },
            )
            return
        if path == "/api/config":
            qs = parse_qs(parsed.query)
            criteria = filter_criteria_from_query(qs)
            cards = self._get_enriched_cards()
            pfm = PdfFileManager()
            filter_meta = filter_meta_for_response(cards, criteria, pfm=pfm)
            students: list[dict[str, str]] = []
            try:
                pfm = PdfFileManager()
                for s in pfm.list_students():
                    students.append(
                        {
                            "student_id": s.id,
                            "display_name": s.name,
                            "email": s.email,
                        }
                    )
            except Exception:
                pass
            self._send_json(
                200,
                {
                    "roots": [
                        {"id": rid, "label": "DaydreamEdu" if rid == "daydreamedu" else "GoodNotes", "path": str(p)}
                        for rid, p in self.roots.items()
                    ],
                    "students": students,
                    **filter_meta,
                },
            )
            return
        if path == "/api/inventory":
            qs = parse_qs(parsed.query)
            criteria = filter_criteria_from_query(qs)
            cards = self._get_enriched_cards()
            pfm = PdfFileManager()
            filtered = filter_main_pdf_cards(cards, criteria, pfm=pfm)
            filtered = sort_main_pdf_cards(filtered, criteria.sort)
            filter_meta = filter_meta_for_response(cards, criteria, pfm=pfm)
            meta = inventory_meta(
                cards,
                filtered_count=len(filtered),
                show_is_registered_filter=filter_meta["show_is_registered_filter"],
            )
            warn = len(self.index_rows) > self.index_warn_threshold
            self._send_json(
                200,
                {
                    "items": [c.to_dict() for c in filtered],
                    "meta": {
                        "total_in_index": meta.total_in_index,
                        "total_after_filter": meta.total_after_filter,
                        "unregistered_in_index": meta.unregistered_in_index,
                        "index_size_warning": warn,
                        **filter_meta,
                    },
                },
            )
            return
        if path == "/api/pdf":
            qs = parse_qs(parsed.query)
            rid = (qs.get("id") or [""])[0]
            rel = (qs.get("rel") or [""])[0]
            root = self.roots.get(rid)
            if root is None:
                self._send_error_json(400, "Unknown or unavailable root id")
                return
            target = safe_resolve_under_root(root, rel)
            if target is None or not target.is_file() or target.suffix.lower() != ".pdf":
                self._send_error_json(404, "Not found")
                return
            leaf_set = self.leaf_dirs_by_id.get(rid, frozenset())
            if _pdf_blocked_not_in_leaf(leaf_set, target):
                self._send_error_json(404, "Not found")
                return
            try:
                data = target.read_bytes()
            except OSError:
                self._send_error_json(500, "Read failed")
                return
            disp = _content_disposition_inline(target.name)
            self.send_response(200)
            self.send_header("Content-Type", "application/pdf")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Content-Disposition", disp)
            self.end_headers()
            self.wfile.write(data)
            return

        self._send_error_json(404, "Not found")

    def do_HEAD(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path != "/api/pdf":
            self.send_error(405, "Method not allowed")
            return
        qs = parse_qs(parsed.query)
        rid = (qs.get("id") or [""])[0]
        rel = (qs.get("rel") or [""])[0]
        root = self.roots.get(rid)
        if root is None:
            self.send_error(400, "Unknown root")
            return
        target = safe_resolve_under_root(root, rel)
        if target is None or not target.is_file():
            self.send_error(404, "Not found")
            return
        leaf_set = self.leaf_dirs_by_id.get(rid, frozenset())
        if _pdf_blocked_not_in_leaf(leaf_set, target):
            self.send_error(404, "Not found")
            return
        try:
            length = target.stat().st_size
        except OSError:
            self.send_error(500, "Stat failed")
            return
        disp = _content_disposition_inline(target.name)
        self.send_response(200)
        self.send_header("Content-Type", "application/pdf")
        self.send_header("Content-Length", str(length))
        self.send_header("Content-Disposition", disp)
        self.end_headers()


def main() -> int:
    parser = argparse.ArgumentParser(description="Student File Browser (operator inventory).")
    parser.add_argument("--port", type=int, default=8771, help="Port (default 8771)")
    parser.add_argument("--no-browser", action="store_true", help="Do not open browser on startup")
    args = parser.parse_args()

    roots = _roots_config()
    if not roots:
        print(
            "No roots configured. Set DAYDREAMEDU_ROOT and/or GOODNOTES_ROOT.\n"
            "See ai_study_buddy/files/README.md",
            file=sys.stderr,
        )
        return 1

    pfm = PdfFileManager()
    registry_index = RegistryPathIndex.from_pdf_file_manager(pfm)
    index_rows = build_main_pdf_index_for_roots(
        exclude_activity_note_completions=True,
        registry_index=registry_index,
    )
    if len(index_rows) > INDEX_WARN_THRESHOLD:
        print(
            f"Warning: index has {len(index_rows)} main PDFs (threshold {INDEX_WARN_THRESHOLD}). "
            "Consider narrowing filters.",
            file=sys.stderr,
        )

    leaf_map = {rid: _leaf_paths_set(root, rid=rid) for rid, root in roots.items()}

    StudentFileBrowserHandler.roots = roots
    StudentFileBrowserHandler.leaf_dirs_by_id = leaf_map
    StudentFileBrowserHandler.index_rows = index_rows
    StudentFileBrowserHandler.enriched_cache = None
    StudentFileBrowserHandler.context_root = _default_context_root()

    server = ThreadingHTTPServer(("localhost", args.port), StudentFileBrowserHandler)
    url = f"http://localhost:{args.port}/"
    print(f"Student File Browser at {url}", flush=True)
    print(f"Index: {len(index_rows)} main PDFs", flush=True)
    if not args.no_browser:
        _open_browser_delayed(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
