#!/usr/bin/env python3
"""
Extract each practice and the answer key from English Practice 1000+ merged PDF
into separate files using the Practice Page Index CSV.
Output: EPO_<section>_<practice index>.pdf and EPO_Answers.pdf
"""

import csv
import re
from pathlib import Path

from pypdf import PdfReader, PdfWriter

PDF_PATH = Path(
    "/Users/jarodm/Library/CloudStorage/GoogleDrive-genrong.meng@gmail.com/My Drive/DaydreamEdu/Singapore Primary English/English_Practice_1000+_merged.pdf"
)
CSV_PATH = Path("/Users/jarodm/Downloads/Practice Page Index - Practice Page Index.csv")
OUT_DIR = PDF_PATH.parent


def slug(s: str) -> str:
    """Make section name safe for filenames: spaces and / to underscore, remove ( )."""
    s = s.replace(" / ", " ").replace("/", " ")
    s = s.replace("(", " ").replace(")", " ")
    s = re.sub(r"\s+", "_", s.strip())
    return re.sub(r"_+", "_", s).strip("_")


def parse_page_range(s: str) -> tuple[int, int]:
    """Parse '6 – 7' or '36' or '66 – 68' into (start, end) 1-based inclusive."""
    s = s.strip()
    # En-dash or hyphen as separator
    parts = re.split(r"\s*[–\-]\s*", s, maxsplit=1)
    parts = [p.strip() for p in parts if p.strip()]
    if not parts:
        raise ValueError(f"Invalid page range: {s!r}")
    start = int(parts[0])
    end = int(parts[1]) if len(parts) > 1 else start
    return start, end


def main():
    reader = PdfReader(PDF_PATH)
    rows = []
    with open(CSV_PATH, newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        current_section = None
        for row in r:
            if (s := row.get("Section", "").strip()):
                current_section = s
            row["Section"] = current_section
            rows.append(row)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for row in rows:
        section = row["Section"]
        practice_num = row.get("Practice Number", "").strip()
        page_range_str = row.get("PDF Page Range", "").strip()
        if not page_range_str:
            continue

        start, end = parse_page_range(page_range_str)
        # 1-based to 0-based indices
        pages = list(range(start - 1, end))

        writer = PdfWriter()
        for i in pages:
            writer.add_page(reader.pages[i])

        if section == "Answer Key":
            out_path = OUT_DIR / "EPO_Answers.pdf"
        else:
            # "Practice 1" -> 1, "Practice 15" -> 15
            m = re.match(r"Practice\s+(\d+)", practice_num, re.I)
            if not m:
                continue
            idx = int(m.group(1))
            out_path = OUT_DIR / f"EPO_{slug(section)}_{idx:02d}.pdf"

        with open(out_path, "wb") as f:
            writer.write(f)
        print(out_path.name)

    print("Done.")


if __name__ == "__main__":
    main()
