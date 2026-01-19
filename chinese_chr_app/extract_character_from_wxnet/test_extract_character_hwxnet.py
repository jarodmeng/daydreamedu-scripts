#!/usr/bin/env python3
"""
Unit tests for extract_character_hwxnet.py

Tests extraction for: 曼，量，霜，和，我
Run this script after modifying extract_character_hwxnet.py to ensure results are still correct.
"""

import json
import sys
from pathlib import Path
from extract_character_hwxnet import extract_character_info


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
    
    if total_failed == 0:
        print(f"\n✓✓✓ ALL TESTS PASSED! ✓✓✓")
        return 0
    else:
        print(f"\n✗✗✗ SOME TESTS FAILED ✗✗✗")
        
        # Show failed tests
        print(f"\nFailed tests:")
        for char, result in results.items():
            if not result or not result.get("passed"):
                print(f"  - {char}")
                for field, field_result in result.get("fields", {}).items():
                    if not field_result.get("match"):
                        print(f"      {field}: {field_result.get('message', 'N/A')}")
        
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
