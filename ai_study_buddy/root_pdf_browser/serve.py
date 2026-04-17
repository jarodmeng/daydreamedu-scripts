#!/usr/bin/env python3
"""Local HTTP server: browse DAYDREAMEDU_ROOT / GOODNOTES_ROOT and view PDFs."""

from __future__ import annotations

import argparse
import json
import sys
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from ai_study_buddy.files.roots import resolve_daydreamedu_root, resolve_goodnotes_root

ROOT_IDS = ("daydreamedu", "goodnotes")
STATIC_DIR = Path(__file__).resolve().parent / "static"


def _open_browser_delayed(url: str, delay_sec: float = 0.35) -> None:
    """Open *url* in the default browser after a short delay so the server is accepting connections."""

    def _run() -> None:
        time.sleep(delay_sec)
        try:
            webbrowser.open(url)
        except Exception:
            pass

    threading.Thread(target=_run, daemon=True).start()


def _roots_config() -> dict[str, Path]:
    out: dict[str, Path] = {}
    dd = resolve_daydreamedu_root()
    if dd is not None:
        out["daydreamedu"] = dd
    gn = resolve_goodnotes_root()
    if gn is not None:
        out["goodnotes"] = gn
    return out


def safe_resolve_under_root(root: Path, rel: str) -> Path | None:
    """Return resolved path if *rel* stays under *root*; else None."""
    root_resolved = root.resolve()
    rel = (rel or "").strip()
    if rel.startswith("/"):
        return None
    rel_path = Path(rel)
    if rel_path.is_absolute():
        return None
    try:
        full = (root_resolved / rel_path).resolve()
    except OSError:
        return None
    if not full.is_relative_to(root_resolved):
        return None
    return full


def list_dir_children(root: Path, rel: str) -> tuple[list[str], list[str]] | None:
    """Return (subdir_names, pdf_basenames) for immediate children, or None if invalid."""
    target = safe_resolve_under_root(root, rel)
    if target is None or not target.is_dir():
        return None
    dirs: list[str] = []
    pdfs: list[str] = []
    try:
        for child in target.iterdir():
            name = child.name
            if name.startswith("."):
                continue
            try:
                if child.is_dir():
                    dirs.append(name)
                elif child.is_file() and child.suffix.lower() == ".pdf":
                    pdfs.append(name)
            except OSError:
                continue
    except OSError:
        return None
    dirs.sort(key=str.lower)
    pdfs.sort(key=str.lower)
    return dirs, pdfs


class RootPdfHandler(BaseHTTPRequestHandler):
    roots: dict[str, Path] = {}

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
        if path == "/api/config":
            roots = []
            labels = {"daydreamedu": "DaydreamEdu", "goodnotes": "GoodNotes"}
            for rid in ROOT_IDS:
                p = self.roots.get(rid)
                if p is not None:
                    roots.append({"id": rid, "label": labels[rid], "path": str(p)})
            self._send_json(200, {"roots": roots})
            return
        if path == "/api/list":
            qs = parse_qs(parsed.query)
            rid = (qs.get("id") or [""])[0]
            rel = (qs.get("rel") or [""])[0]
            root = self.roots.get(rid)
            if root is None:
                self._send_error_json(400, "Unknown or unavailable root id")
                return
            children = list_dir_children(root, rel)
            if children is None:
                self._send_error_json(400, "Not a directory or path not allowed")
                return
            dirs, pdfs = children
            self._send_json(200, {"dirs": dirs, "pdfs": pdfs})
            return
        if path == "/api/pdf":
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
            if target.suffix.lower() != ".pdf":
                self.send_error(400, "Not a PDF")
                return
            try:
                data = target.read_bytes()
            except OSError:
                self.send_error(500, "Read failed")
                return
            disp = target.name.replace('"', "")
            self.send_response(200)
            self.send_header("Content-Type", "application/pdf")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Content-Disposition", f'inline; filename="{disp}"')
            self.end_headers()
            self.wfile.write(data)
            return

        self.send_error(404, "Not found")

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
        if target.suffix.lower() != ".pdf":
            self.send_error(400, "Not a PDF")
            return
        try:
            length = target.stat().st_size
        except OSError:
            self.send_error(500, "Stat failed")
            return
        disp = target.name.replace('"', "")
        self.send_response(200)
        self.send_header("Content-Type", "application/pdf")
        self.send_header("Content-Length", str(length))
        self.send_header("Content-Disposition", f'inline; filename="{disp}"')
        self.end_headers()


def main() -> int:
    parser = argparse.ArgumentParser(description="Browse DaydreamEdu/GoodNotes roots and view PDFs locally.")
    parser.add_argument("--port", type=int, default=8770, help="Port (default 8770)")
    parser.add_argument(
        "--no-browser",
        action="store_true",
        help="Do not open the app URL in the default browser after startup.",
    )
    args = parser.parse_args()

    roots = _roots_config()
    if not roots:
        print(
            "No roots configured. Set DAYDREAMEDU_ROOT and/or GOODNOTES_ROOT, or add paths to\n"
            "  ai_study_buddy/local_daydreamedu_root.txt\n"
            "  ai_study_buddy/local_goodnotes_root.txt\n"
            "See ai_study_buddy/files/roots.py for resolution order.",
            file=sys.stderr,
        )
        return 1

    RootPdfHandler.roots = roots
    server = ThreadingHTTPServer(("127.0.0.1", args.port), RootPdfHandler)
    url = f"http://127.0.0.1:{args.port}/"
    print(f"Root PDF browser at {url}", flush=True)
    print(f"Serving: {', '.join(f'{k}={v}' for k, v in roots.items())}", flush=True)
    print("--- root-pdf-browser: ready (Ctrl+C to stop) ---", flush=True)
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
