#!/usr/bin/env python3
import argparse
import json
from pathlib import Path
from typing import List, Tuple


ROOT = Path(__file__).resolve().parents[3]
FENG_PATH = ROOT / "data" / "characters.json"
HWXNET_PATH = ROOT / "data" / "extracted_characters_hwxnet.json"


def load_feng_words(character: str) -> List[str]:
    data = json.loads(FENG_PATH.read_text(encoding="utf-8"))
    for item in data:
        if item.get("Character") == character:
            return list(item.get("Words") or [])
    return []


def load_hwxnet_words(character: str) -> List[str]:
    data = json.loads(HWXNET_PATH.read_text(encoding="utf-8"))
    entry = data.get(character)
    if not entry:
        return []

    words = []
    for sense in entry.get("基本字义解释", []) or []:
        for definition in sense.get("释义", []) or []:
            for ex in definition.get("例词", []) or []:
                if ex and ex not in words:
                    words.append(ex)
    return words


def pick_words(
    feng_words: List[str], hwxnet_words: List[str], max_words: int
) -> Tuple[List[str], List[str]]:
    # Prefer Feng words first, then HWXNet to fill gaps.
    if max_words <= 0:
        return [], []

    if len(feng_words) >= max_words:
        selected = sorted(feng_words, key=len)[:max_words]
        return selected, []

    selected = list(feng_words)
    remaining = max_words - len(selected)
    if remaining > 0:
        selected += sorted(hwxnet_words, key=len)[:remaining]
    return selected, hwxnet_words


def build_stem(character: str, max_words: int) -> str:
    feng_words = load_feng_words(character)
    hwxnet_words = load_hwxnet_words(character)
    selected, _ = pick_words(feng_words, hwxnet_words, max_words)

    if selected:
        words_str = " / ".join(selected)
    else:
        words_str = "暂无"

    return "\n".join(
        [
            f"看这个字：{character}",
            f"常见词组：{words_str}",
            "选择正确的拼音：",
        ]
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate a pinyin recall stem for a character."
    )
    parser.add_argument("character", help="Single Chinese character to test.")
    parser.add_argument(
        "--max-words",
        type=int,
        default=3,
        help="Max number of words to show in the stem.",
    )
    args = parser.parse_args()

    if len(args.character) != 1:
        raise SystemExit("Please provide exactly one Chinese character.")

    print(build_stem(args.character, args.max_words))


if __name__ == "__main__":
    main()
