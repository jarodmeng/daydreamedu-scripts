#!/usr/bin/env python3
"""
Unit tests for extract_character_hwxnet.py

- 例词 unit tests: minimal HTML, no network (郭, 尧, 丁, 万, 乃, 之, 么, 丫, 丈).
- Live extraction tests: 曼，量，霜，和，我 (classification, pinyin, 部首, etc.).
- Extra 例词 segmentation checks for 郭 / 尧 / 丁 (live).
Run this script after modifying extract_character_hwxnet.py to ensure results are still correct.
"""

import json
import sys
from pathlib import Path

from bs4 import BeautifulSoup

from extract_character_hwxnet import extract_character_info, extract_meanings


# --- 例词 unit tests (minimal HTML, no network) ---

def _make_soup(con_basic_text: str) -> BeautifulSoup:
    """Build minimal HTML with h1 基本字义解释 and div.con_basic containing con_basic_text."""
    html = f"""
    <html><body>
    <h1>基本字义解释</h1>
    <div class="con_basic">
    {con_basic_text}
    </div>
    </body></html>
    """
    return BeautifulSoup(html, "lxml")


def _get_first_lici(meanings: list) -> list:
    """Return 例词 list from the first 释义 of the first sense."""
    if not meanings:
        return []
    for sense in meanings:
        for definition in sense.get("释义") or []:
            return definition.get("例词") or []
    return []


# (character, con_basic content = first 基本字义解释 bullet from HWXNet page, expected 例词 = first 释义’s 例词)
LICI_CASES = [
    # 郭 https://zd.hwxnet.com/search.do?keyword=郭
    ("郭", "● 郭guō ㄍㄨㄛˉ\n◎ 城外围着城的墙：城郭。\"爷娘闻女来，出郭相扶将\"。\n◎ 物体的外框或外壳。\n◎ 姓。", ["城郭", "爷娘闻女来，出郭相扶将"]),
    # 尧 https://zd.hwxnet.com/search.do?keyword=尧
    ("尧", "● 尧（堯）yáo ㄧㄠˊ\n◎ 传说中上古帝王名：尧舜（\"尧\"和\"舜\"，均为传说中上古的贤明君主。后泛指圣人）。尧天舜日（旧时喻太平盛世）。", ["尧舜，后泛指圣人", "尧天舜日"]),
    # 丁 https://zd.hwxnet.com/search.do?keyword=丁
    ("丁", "● 丁dīng ㄉㄧㄥˉ\n◎ 天干的第四位，用于作顺序第四的代称：丁是丁，卯是卯。\n◎ 成年男子。\n◎ 人口。\n◎ 从事某种劳动的人：园丁。", ["丁是丁，卯是卯"]),
    # 万 https://zd.hwxnet.com/search.do?keyword=万
    ("万", "● 万（萬）wàn ㄨㄢˋ\n◎ 数目，十个一千：万户侯（中国汉代侯爵的最高一级，享有万户农民的赋税。后泛指高官）。", ["万户侯，后泛指高官"]),
    # 乃 https://zd.hwxnet.com/search.do?keyword=乃
    ("乃", "● 乃nǎi ㄋㄞˇ\n◎ 才：今乃得之。\"断其喉，尽其肉，乃去\"。\n◎ 是，为：乃大丈夫也。\n◎ 竟：乃至如此。\n◎ 于是，就：\"因山势高峻，乃在山腰休息片时\"。\n◎ 你，你的：乃父。乃兄。\"家祭无忘告乃翁\"。", ["今乃得之", "断其喉，尽其肉，乃去"]),
    # 之 https://zd.hwxnet.com/search.do?keyword=之
    ("之", "● 之zhī ㄓˉ\n◎ 助词，表示领有、连属关系：赤子之心。\n◎ 助词，表示修饰关系：缓兵之计。不速之客。莫逆之交。\n◎ 用在主谓结构之间，使成为句子成分：\"大道之行也，天下为公\"。\n◎ 代词，代替人或事物：置之度外。等闲视之。\n◎ 代词，这，那：\"之二虫，又何知\"。\n◎ 虚用，无所指：久而久之。\n◎ 往，到：\"吾欲之南海\"。", ["赤子之心"]),
    # 么 https://zd.hwxnet.com/search.do?keyword=么
    ("么", "● 么（麽）me ㄇㄜ\n◎ 词尾：怎么。这么。多么。什么。\n◎ 助词，表示含蓄语气，用在前半句末了：不让你去么，你又要去。", ["怎么", "这么", "多么", "什么"]),
    # 丫 https://zd.hwxnet.com/search.do?keyword=丫
    ("丫", "● 丫yā ㄧㄚˉ\n◎ 分杈的：树丫。丫杈。\n◎ 像树枝的分杈：丫头（ａ．古代女孩子头上梳双髻，如树丫杈，因以称女孩子；ｂ．指受役使的女孩子，亦称\"丫鬟\"。\"头\"、\"鬟\"均读轻声）。脚丫子。", ["树丫", "丫杈"]),
    # 丈 https://zd.hwxnet.com/search.do?keyword=丈
    ("丈", "● 丈zhàng ㄓㄤˋ\n◎ 中国市制长度单位，十尺：万丈高楼。\n◎ 测量长度和面积：丈量（liàg）。\n◎ 对老年男子的尊称：丈人（a.古代对老人的尊称；b.岳父。\"人\"均读轻声）。老丈。", ["万丈高楼"]),
]


def run_lici_unit_tests():
    """Run 例词 extraction tests with minimal HTML (no network). Returns (passed_count, failed_list)."""
    failed = []
    for character, con_basic_text, expected_lici in LICI_CASES:
        soup = _make_soup(con_basic_text)
        meanings = extract_meanings(soup, character)
        got = _get_first_lici(meanings)
        if got != expected_lici:
            failed.append((character, expected_lici, got))
    return len(LICI_CASES) - len(failed), failed


# --- Live extraction tests ---


# Expected results (ground truth)
EXPECTED_RESULTS = {
    "曼": {
        "分类": ["通用字", "次常用字"],
        "拼音": ["màn"],
        "部首": "曰",
        "总笔画": 11,
    },
    "量": {
        "分类": ["通用字", "常用字"],
        "拼音": ["liàng", "liáng"],
        "部首": "里",
        "总笔画": 12,
    },
    "霜": {
        "分类": ["通用字", "常用字"],
        "拼音": ["shuāng"],
        "部首": "雨",
        "总笔画": 17,
    },
    "和": {
        "分类": ["通用字", "常用字"],
        "拼音": ["hé", "hè", "huó", "huò", "huo", "hú"],
        "部首": "口",
        "总笔画": 8,
    },
    "我": {
        "分类": ["通用字", "常用字"],
        "拼音": ["wŏ", "wǒ"],  # Accept both ŏ (breve) and ǒ (caron)
        "部首": "戈",
        "总笔画": 7,
    }
}


def normalize_pinyin(pinyin_list):
    """
    Normalize pinyin for comparison.
    Converts ŏ (breve) to ǒ (caron) for consistency.
    """
    normalized = []
    for p in pinyin_list:
        # Replace ŏ with ǒ for comparison
        normalized.append(p.replace('ŏ', 'ǒ').lower())
    return sorted(set(normalized))


def compare_lists(expected, actual, field_name):
    """
    Compare two lists (order-independent).
    For pinyin, checks that all expected are present (allows extras).
    For other fields, requires exact match.
    Returns (match, message)
    """
    if not isinstance(expected, list):
        expected = [expected] if expected else []
    if not isinstance(actual, list):
        actual = [actual] if actual else []
    
    # Normalize pinyin for comparison
    if field_name == "拼音":
        expected_norm = normalize_pinyin(expected)
        actual_norm = normalize_pinyin(actual)
        
        # For pinyin, check that all expected are present (subset check)
        # This allows the extraction to find additional variants
        match = set(expected_norm).issubset(set(actual_norm))
        if match:
            message = f"Expected (all present): {expected}, Got: {actual}"
            if len(actual_norm) > len(expected_norm):
                extra = set(actual_norm) - set(expected_norm)
                message += f" (also found: {sorted(extra)})"
        else:
            missing = set(expected_norm) - set(actual_norm)
            message = f"Expected: {expected}, Got: {actual} (missing: {sorted(missing)})"
    else:
        expected_norm = sorted([str(x).lower() for x in expected])
        actual_norm = sorted([str(x).lower() for x in actual])
        match = expected_norm == actual_norm
        message = f"Expected: {expected}, Got: {actual}"
        if not match:
            message += f" (normalized: {expected_norm} vs {actual_norm})"
    
    return match, message


def test_character(char, expected):
    """
    Test extraction for a single character.
    Returns (passed, results_dict)
    """
    print(f"\n{'='*70}")
    print(f"Testing character: {char}")
    print(f"{'='*70}")
    
    try:
        result = extract_character_info(char)
    except Exception as e:
        print(f"  ✗ EXTRACTION FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False, None
    
    # Test each field
    all_passed = True
    field_results = {}
    
    for field in ["分类", "拼音", "部首", "总笔画"]:
        expected_value = expected.get(field)
        actual_value = result.get(field)
        
        if isinstance(expected_value, list):
            match, message = compare_lists(expected_value, actual_value, field)
        else:
            match = expected_value == actual_value
            message = f"Expected: {expected_value}, Got: {actual_value}"
        
        status = "✓" if match else "✗"
        print(f"  {field}: {status} {message}")
        
        field_results[field] = {
            "match": match,
            "expected": expected_value,
            "actual": actual_value,
            "message": message
        }
        
        if not match:
            all_passed = False
    
    # Check that 基本字义解释 exists and is not empty
    meanings = result.get("基本字义解释", [])
    if meanings:
        print(f"  基本字义解释: ✓ Found {len(meanings)} meaning entry/entries")
        field_results["基本字义解释"] = {"match": True, "count": len(meanings)}
    else:
        print(f"  基本字义解释: ✗ Missing or empty")
        field_results["基本字义解释"] = {"match": False, "count": 0}
        all_passed = False
    
    # Check that 英文翻译 exists and is not empty
    english = result.get("英文翻译", [])
    if english:
        print(f"  英文翻译: ✓ Found {len(english)} translation(s)")
        field_results["英文翻译"] = {"match": True, "count": len(english)}
    else:
        print(f"  英文翻译: ✗ Missing or empty")
        field_results["英文翻译"] = {"match": False, "count": 0}
        all_passed = False
    
    # 常用词组: must be present and a list (may be empty for characters without the section)
    common_phrases = result.get("常用词组", None)
    if common_phrases is None:
        print(f"  常用词组: ✗ Missing (expected key)")
        field_results["常用词组"] = {"match": False, "message": "key missing"}
        all_passed = False
    elif not isinstance(common_phrases, list):
        print(f"  常用词组: ✗ Not a list: {type(common_phrases)}")
        field_results["常用词组"] = {"match": False, "message": f"not a list: {type(common_phrases)}"}
        all_passed = False
    else:
        print(f"  常用词组: ✓ Present, {len(common_phrases)} phrase(s)")
        field_results["常用词组"] = {"match": True, "count": len(common_phrases)}
    
    if all_passed:
        print(f"\n  ✓✓✓ ALL TESTS PASSED for {char} ✓✓✓")
    else:
        print(f"\n  ✗✗✗ SOME TESTS FAILED for {char} ✗✗✗")
    
    return all_passed, {
        "character": char,
        "passed": all_passed,
        "fields": field_results,
        "full_result": result
    }


def main():
    """Run all tests."""
    # 例词 unit tests (minimal HTML, no network)
    print("="*70)
    print("例词 UNIT TESTS (minimal HTML, no network)")
    print("="*70)
    lici_passed, lici_failed = run_lici_unit_tests()
    for character, _, _ in LICI_CASES:
        status = "OK" if not any(f[0] == character for f in lici_failed) else "FAIL"
        print(f"  {character}: {status}")
    print(f"Passed: {lici_passed}/{len(LICI_CASES)}")
    if lici_failed:
        for character, expected, got in lici_failed:
            print(f"  FAIL {character}: expected {expected}, got {got}")
    print()

    print("="*70)
    print("UNIT TESTS FOR extract_character_hwxnet.py")
    print("="*70)
    print(f"\nTesting {len(EXPECTED_RESULTS)} characters:")
    for char in EXPECTED_RESULTS.keys():
        print(f"  - {char}")

    results = {}
    total_passed = 0
    total_failed = 0

    for char, expected in EXPECTED_RESULTS.items():
        passed, result = test_character(char, expected)
        results[char] = result
        
        if passed:
            total_passed += 1
        else:
            total_failed += 1
    
    # Summary
    print(f"\n{'='*70}")
    print("TEST SUMMARY")
    print(f"{'='*70}")
    print(f"Total characters tested: {len(EXPECTED_RESULTS)}")
    print(f"Passed: {total_passed}")
    print(f"Failed: {total_failed}")
    
    # Test 卢 for 常用词组 (section present on HWXNet)
    print(f"\n{'='*70}")
    print("EXTRA: 常用词组 test for 卢 (expect non-empty, contains 卢比, 卢布)")
    print(f"{'='*70}")
    try:
        lu_result = extract_character_info("卢")
        phrases = lu_result.get("常用词组", [])
        if not isinstance(phrases, list):
            print(f"  ✗ 卢 常用词组 is not a list: {type(phrases)}")
            total_failed += 1
        elif len(phrases) == 0:
            print(f"  ✗ 卢 常用词组 is empty (expected phrases)")
            total_failed += 1
        elif "卢比" not in phrases or "卢布" not in phrases:
            print(f"  ✗ 卢 常用词组 missing expected: got {phrases[:10]}")
            total_failed += 1
        else:
            print(f"  ✓ 卢 常用词组: {len(phrases)} phrases, includes 卢比, 卢布")
    except Exception as e:
        print(f"  ✗ 卢 extraction failed: {e}")
        import traceback
        traceback.print_exc()
        total_failed += 1
    
    if total_failed == 0:
        print(f"\n✓✓✓ ALL CORE FIELD TESTS PASSED! ✓✓✓")

    # Additional behavior checks for HWXNet 例词 / stem-word inputs.
    # These rely on the current HWXNet content structure and are meant to
    # catch regressions in our 例词 segmentation logic.
    print(f"\n{'='*70}")
    print("EXTRA: 例词 segmentation checks for 郭 / 尧 / 丁")
    print(f"{'='*70}")
    extra_failed = 0

    def _collect_example_phrases(entry, ch: str):
        """Flatten all 例词 phrases for a character entry."""
        phrases = []
        for sense in entry.get("基本字义解释") or []:
            for definition in sense.get("释义") or []:
                for ex in definition.get("例词") or []:
                    if ex and ex not in phrases:
                        phrases.append(ex)
        return phrases

    # 郭: ensure we never surface bare 爷娘闻女来; instead we should see a phrase
    # that includes 郭 and spans the comma-separated quote.
    try:
        guo = extract_character_info("郭")
        guo_lici = _collect_example_phrases(guo, "郭")
        bad_segment = "爷娘闻女来"
        if any(bad_segment == p for p in guo_lici):
            print(f"  ✗ 郭 例词 still contains bare {bad_segment!r}: {guo_lici}")
            extra_failed += 1
        if not any("郭" in p and "爷娘闻女来" in p for p in guo_lici):
            print(f"  ✗ 郭 例词 missing merged phrase containing both 郭 and 爷娘闻女来: {guo_lici}")
            extra_failed += 1
        else:
            print("  ✓ 郭 例词 segmentation looks correct (no bare 爷娘闻女来).")
    except Exception as e:
        print(f"  ✗ 郭 extraction failed: {e}")
        import traceback
        traceback.print_exc()
        extra_failed += 1

    # 尧: ensure explanatory text like “后泛指圣人” is not a bare 例词 without 尧.
    try:
        yao = extract_character_info("尧")
        yao_lici = _collect_example_phrases(yao, "尧")
        if any("后泛指" in p and "尧" not in p for p in yao_lici):
            print(f"  ✗ 尧 例词 contains bare explanatory phrase without 尧: {yao_lici}")
            extra_failed += 1
        else:
            print("  ✓ 尧 例词 segmentation looks correct (no bare explanatory clause without 尧).")
    except Exception as e:
        print(f"  ✗ 尧 extraction failed: {e}")
        import traceback
        traceback.print_exc()
        extra_failed += 1

    # 丁: the idiom 丁是丁，卯是卯 should appear as one phrase, not with 卯是卯 alone.
    try:
        ding = extract_character_info("丁")
        ding_lici = _collect_example_phrases(ding, "丁")
        if any("卯是卯" == p for p in ding_lici):
            print(f"  ✗ 丁 例词 still contains bare '卯是卯': {ding_lici}")
            extra_failed += 1
        else:
            print("  ✓ 丁 例词 segmentation looks correct (no bare 卯是卯).")
    except Exception as e:
        print(f"  ✗ 丁 extraction failed: {e}")
        import traceback
        traceback.print_exc()
        extra_failed += 1

    if total_failed == 0 and extra_failed == 0 and not lici_failed:
        print(f"\n✓✓✓ ALL TESTS PASSED! ✓✓✓")
        return 0

    print(f"\n✗✗✗ SOME TESTS FAILED ✗✗✗")

    # Show failed core-field tests
    print(f"\nFailed core-field tests:")
    for char, result in results.items():
        if not result or not result.get("passed"):
            print(f"  - {char}")
            for field, field_result in result.get("fields", {}).items():
                if not field_result.get("match"):
                    print(f"      {field}: {field_result.get('message', 'N/A')}")

    if lici_failed:
        print(f"\n例词 unit tests failed: {len(lici_failed)}")
    if extra_failed:
        print(f"\nAdditional 例词 segmentation checks failed: {extra_failed}")

    return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
