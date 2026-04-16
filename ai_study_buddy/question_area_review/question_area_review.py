#!/usr/bin/env python3

import argparse
import json
import subprocess
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parent
STATIC_DIR = ROOT / "static"


def clamp_bbox(bbox):
    x1, y1, x2, y2 = [float(v) for v in bbox]
    x1 = max(0.0, min(1.0, x1))
    y1 = max(0.0, min(1.0, y1))
    x2 = max(0.0, min(1.0, x2))
    y2 = max(0.0, min(1.0, y2))
    if x2 <= x1:
        x2 = min(1.0, x1 + 0.001)
    if y2 <= y1:
        y2 = min(1.0, y1 + 0.001)
    return [round(x1, 6), round(y1, 6), round(x2, 6), round(y2, 6)]


class ReviewState:
    def __init__(self, index_path: Path):
        self.index_path = index_path.resolve()
        self.index = {}
        self.unit_file_path = None
        self.questions = []
        self.stimulus_blocks = []
        self.file_id = None
        self.render_dir = None
        self.last_loaded_mtime_ns = None
        self._load_index(force=True)

    def _load_index(self, force: bool = False):
        stat = self.index_path.stat()
        if not force and self.last_loaded_mtime_ns == stat.st_mtime_ns:
            return

        with self.index_path.open("r", encoding="utf-8") as handle:
            self.index = json.load(handle)

        self.unit_file_path = Path(self.index["unit_file_path"]).expanduser().resolve()
        self.questions = self.index.get("questions", [])
        self.stimulus_blocks = self.index.get("stimulus_blocks", [])
        self.file_id = self.index.get("unit_file_id") or self.index_path.stem
        self.render_dir = self.index_path.parent / ".review_pages" / self.file_id
        self.render_dir.mkdir(parents=True, exist_ok=True)
        self._render_pages_if_missing()
        self.last_loaded_mtime_ns = stat.st_mtime_ns

    def _render_pages_if_missing(self):
        expected = self.render_dir / "page-01.png"
        if expected.exists():
            return

        cmd = [
            "pdftoppm",
            "-png",
            "-scale-to",
            "1600",
            str(self.unit_file_path),
            str(self.render_dir / "page"),
        ]
        try:
            subprocess.run(cmd, check=True, capture_output=True, text=True)
        except FileNotFoundError as exc:
            raise RuntimeError("pdftoppm is required but not installed.") from exc
        except subprocess.CalledProcessError as exc:
            raise RuntimeError(exc.stderr.strip() or "pdftoppm failed.") from exc

    def _stimulus_lookup(self):
        return {block["block_id"]: block for block in self.stimulus_blocks}

    def payload(self):
        self._load_index()
        stim_by_id = self._stimulus_lookup()
        questions = []
        for idx, question in enumerate(self.questions):
            prompt_regions = question.get("prompt_regions") or []
            linked_stimulus = stim_by_id.get(question.get("stimulus_block_id"))
            questions.append(
                {
                    "index": idx,
                    "question_id": question.get("question_id"),
                    "display_label": question.get("display_label"),
                    "question_number": question.get("question_number"),
                    "sub_part": question.get("sub_part"),
                    "question_type": question.get("question_type"),
                    "max_marks": question.get("max_marks"),
                    "printed_question_text": question.get("printed_question_text"),
                    "review_status": question.get("review_status", "unreviewed"),
                    "stimulus_block_id": question.get("stimulus_block_id"),
                    "prompt_regions": prompt_regions,
                    "region_count": len(prompt_regions),
                    "linked_stimulus": linked_stimulus,
                }
            )

        reviewed = sum(1 for q in self.questions if q.get("review_status") in {"accepted", "corrected"})
        return {
            "index_path": str(self.index_path),
            "unit_label": self.index.get("unit_label"),
            "book_label": self.index.get("book_label"),
            "subject": self.index.get("subject"),
            "grade": self.index.get("grade"),
            "index_status": self.index.get("index_status", "generated"),
            "total_questions": len(self.questions),
            "reviewed_questions": reviewed,
            "first_unreviewed_index": next(
                (i for i, q in enumerate(self.questions) if q.get("review_status", "unreviewed") == "unreviewed"),
                0,
            ),
            "questions": questions,
        }

    def page_image_path(self, page: int) -> Path:
        self._load_index()
        return self.render_dir / f"page-{page:02d}.png"

    def save_question(self, question_index: int, region_index: int, page: int, bbox, review_status: str):
        self._load_index()
        question = self.questions[question_index]
        prompt_regions = question.setdefault("prompt_regions", [])
        if not (0 <= region_index < len(prompt_regions)):
            raise IndexError("Invalid region index")

        prompt_regions[region_index]["page"] = int(page)
        prompt_regions[region_index]["bbox"] = clamp_bbox(bbox)
        question["review_status"] = review_status

        all_reviewed = all(
            q.get("review_status", "unreviewed") in {"accepted", "corrected"} for q in self.questions
        )
        self.index["index_status"] = "verified" if all_reviewed else "generated"
        self._write_index()

        return {
            "question_index": question_index,
            "review_status": review_status,
            "bbox": prompt_regions[region_index]["bbox"],
            "page": prompt_regions[region_index]["page"],
            "index_status": self.index["index_status"],
        }

    def save_stimulus(self, question_index: int, stimulus_block_id: str, region_index: int, page: int, bbox):
        self._load_index()
        stimulus = next((block for block in self.stimulus_blocks if block.get("block_id") == stimulus_block_id), None)
        if stimulus is None:
            raise IndexError("Stimulus block not found")

        regions = stimulus.setdefault("regions", [])
        if not (0 <= region_index < len(regions)):
            raise IndexError("Invalid stimulus region index")

        regions[region_index]["page"] = int(page)
        regions[region_index]["bbox"] = clamp_bbox(bbox)
        self.questions[question_index]["review_status"] = "corrected"

        all_reviewed = all(
            q.get("review_status", "unreviewed") in {"accepted", "corrected"} for q in self.questions
        )
        self.index["index_status"] = "verified" if all_reviewed else "generated"
        self._write_index()

        return {
            "question_index": question_index,
            "stimulus_block_id": stimulus_block_id,
            "review_status": "corrected",
            "bbox": regions[region_index]["bbox"],
            "page": regions[region_index]["page"],
            "index_status": self.index["index_status"],
        }

    def _write_index(self):
        with self.index_path.open("w", encoding="utf-8") as handle:
            json.dump(self.index, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        self.last_loaded_mtime_ns = self.index_path.stat().st_mtime_ns


class ReviewHandler(BaseHTTPRequestHandler):
    state = None

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        if path == "/":
            self._serve_file(STATIC_DIR / "index.html", "text/html; charset=utf-8")
            return
        if path == "/review.css":
            self._serve_file(STATIC_DIR / "review.css", "text/css; charset=utf-8")
            return
        if path == "/review.js":
            self._serve_file(STATIC_DIR / "review.js", "application/javascript; charset=utf-8")
            return
        if path == "/api/index":
            self._send_json(200, self.state.payload())
            return
        if path.startswith("/api/page/"):
            try:
                page = int(path.rsplit("/", 1)[-1])
            except ValueError:
                self.send_error(400, "Invalid page")
                return
            image_path = self.state.page_image_path(page)
            if not image_path.exists():
                self.send_error(404, "Page render not found")
                return
            self._serve_file(image_path, "image/png")
            return

        self.send_error(404, "Not found")

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/save-question":
            try:
                length = int(self.headers.get("Content-Length", "0"))
                payload = json.loads(self.rfile.read(length))
                result = self.state.save_question(
                    question_index=int(payload["question_index"]),
                    region_index=int(payload["region_index"]),
                    page=int(payload["page"]),
                    bbox=payload["bbox"],
                    review_status=str(payload["review_status"]),
                )
            except Exception as exc:
                self._send_json(400, {"error": str(exc)})
                return

            self._send_json(200, {"ok": True, "result": result, "index": self.state.payload()})
            return

        if parsed.path == "/api/save-stimulus":
            try:
                length = int(self.headers.get("Content-Length", "0"))
                payload = json.loads(self.rfile.read(length))
                result = self.state.save_stimulus(
                    question_index=int(payload["question_index"]),
                    stimulus_block_id=str(payload["stimulus_block_id"]),
                    region_index=int(payload["region_index"]),
                    page=int(payload["page"]),
                    bbox=payload["bbox"],
                )
            except Exception as exc:
                self._send_json(400, {"error": str(exc)})
                return

            self._send_json(200, {"ok": True, "result": result, "index": self.state.payload()})
            return

        else:
            self.send_error(404, "Not found")
            return

    def log_message(self, format, *args):
        return

    def _serve_file(self, path: Path, content_type: str):
        data = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _send_json(self, code: int, payload):
        data = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def main():
    parser = argparse.ArgumentParser(description="Review AI-generated question index bounding boxes.")
    parser.add_argument("index_path", help="Path to unit_question_index.json")
    parser.add_argument("--port", type=int, default=8765, help="Port to serve the review UI on")
    args = parser.parse_args()

    index_path = Path(args.index_path)
    if not index_path.exists():
        print(f"Index file not found: {index_path}", file=sys.stderr)
        return 1

    try:
        state = ReviewState(index_path)
    except Exception as exc:
        print(f"Failed to initialize review tool: {exc}", file=sys.stderr)
        return 1

    ReviewHandler.state = state
    server = ThreadingHTTPServer(("127.0.0.1", args.port), ReviewHandler)

    print(f"Review tool ready for {state.index_path}")
    print(f"Open http://127.0.0.1:{args.port}/")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
