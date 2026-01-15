#!/usr/bin/env python3
"""
Parse OpenAI Batch API results and extract Chinese character data.

This script:
1. Reads the results.jsonl file from OpenAI Batch API
2. Extracts markdown tables from each response
3. Parses the structured data (Index, Character, Pinyin, Radical, Strokes, Structure)
4. Outputs to CSV and/or JSON format
5. Provides statistics and validation

Usage:
    python3 parse_results.py \
      --input results.jsonl \
      --output characters.csv \
      --json characters.json
"""

import argparse
import json
import csv
import re
from pathlib import Path
from typing import List, Dict, Optional, Any


def parse_markdown_table(table_text: str) -> Optional[Dict[str, str]]:
    """
    Parse a markdown table row and extract fields.
    Expected format:
    | Index | Character | Pinyin | Radical | Strokes | Structure |
    | 0001  | 爸       | bà     | 父      | 8       | 左右结构  |
    """
    lines = [line.strip() for line in table_text.strip().split('\n') if line.strip()]
    
    if len(lines) < 2:
        return None
    
    # Skip header row (first line)
    data_lines = lines[1:]
    
    for line in data_lines:
        # Skip separator lines (|---|---|---|)
        if re.match(r'^\|[\s\-:]+\|', line):
            continue
        
        # Parse table row: | value1 | value2 | value3 | ...
        parts = [p.strip() for p in line.split('|') if p.strip()]
        
        if len(parts) >= 6:
            return {
                'Index': parts[0],
                'Character': parts[1],
                'Pinyin': parts[2],
                'Radical': parts[3],
                'Strokes': parts[4],
                'Structure': parts[5],
            }
    
    return None


def extract_table_from_response(response_text: str) -> Optional[str]:
    """
    Extract markdown table from response text.
    Looks for table starting with | Index | Character | ...
    """
    # Find table start
    table_start = response_text.find('| Index | Character |')
    if table_start == -1:
        return None
    
    # Find the end of the table (empty line or end of text)
    table_text = response_text[table_start:]
    
    # Extract until we hit an empty line or end
    lines = table_text.split('\n')
    table_lines = []
    for line in lines:
        if line.strip() and ('|' in line or not table_lines):
            table_lines.append(line)
        elif table_lines and not line.strip():
            break
    
    return '\n'.join(table_lines)


def parse_result_line(line: str) -> Optional[Dict[str, Any]]:
    """
    Parse a single JSONL line from results file.
    Returns dict with custom_id and parsed character data.
    """
    try:
        result = json.loads(line)
    except json.JSONDecodeError as e:
        print(f"⚠️  Failed to parse JSON line: {e}")
        return None
    
    # Extract custom_id (character index)
    custom_id = result.get('custom_id', '')
    
    # Extract response content
    response = result.get('response', {})
    body = response.get('body', {})
    output = body.get('output', '')
    
    # Handle output structure: output is a list, text is in output[1]["content"][0]["text"]
    output_text = ''
    if isinstance(output, list):
        # Find the message with output_text content
        for item in output:
            if item.get('type') == 'message' and item.get('status') == 'completed':
                content = item.get('content', [])
                for content_item in content:
                    if content_item.get('type') == 'output_text':
                        output_text = content_item.get('text', '')
                        break
                if output_text:
                    break
    elif isinstance(output, str):
        output_text = output
    
    if not output_text:
        return {
            'custom_id': custom_id,
            'error': 'No output text found in response',
            'raw_output': str(output)[:200] if output else 'No output',
        }
    
    # Try to extract markdown table
    table_text = extract_table_from_response(output_text)
    if not table_text:
        return {
            'custom_id': custom_id,
            'error': 'No table found in response',
            'raw_output': output_text[:200] if output_text else 'No output',
        }
    
    # Parse the table
    char_data = parse_markdown_table(table_text)
    if not char_data:
        return {
            'custom_id': custom_id,
            'error': 'Failed to parse table',
            'raw_table': table_text[:200],
        }
    
    # Add custom_id to the data
    char_data['custom_id'] = custom_id
    
    return char_data


def validate_character_data(data: Dict[str, str]) -> List[str]:
    """
    Validate character data and return list of warnings/errors.
    """
    issues = []
    
    # Check required fields
    required_fields = ['Index', 'Character', 'Pinyin', 'Radical', 'Strokes', 'Structure']
    for field in required_fields:
        if field not in data or not data[field]:
            issues.append(f"Missing {field}")
    
    # Validate Index format (should be digits, normalize to 4 digits)
    if 'Index' in data and data['Index']:
        if not data['Index'].isdigit():
            issues.append(f"Invalid Index format: {data['Index']}")
        else:
            # Normalize to 4 digits
            data['Index'] = f"{int(data['Index']):04d}"
    
    # Validate Character (should be single Chinese character)
    if 'Character' in data and data['Character']:
        if not re.match(r'^[\u4e00-\u9fff]$', data['Character']):
            issues.append(f"Invalid Character: {data['Character']}")
    
    # Validate Strokes (should be a number)
    if 'Strokes' in data and data['Strokes']:
        # Remove (dictionary) marker if present
        strokes_clean = data['Strokes'].replace(' (dictionary)', '').strip()
        if not strokes_clean.isdigit():
            issues.append(f"Invalid Strokes format: {data['Strokes']}")
    
    return issues


def main():
    parser = argparse.ArgumentParser(
        description="Parse OpenAI Batch API results and extract character data."
    )
    parser.add_argument(
        "--input",
        required=True,
        type=Path,
        help="Path to results.jsonl file",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Path to output CSV file (optional)",
    )
    parser.add_argument(
        "--json",
        type=Path,
        help="Path to output JSON file (optional)",
    )
    parser.add_argument(
        "--validate",
        action="store_true",
        help="Validate extracted data and show warnings",
    )
    parser.add_argument(
        "--stats",
        action="store_true",
        help="Show statistics about parsed data",
    )

    args = parser.parse_args()

    if not args.input.exists():
        raise SystemExit(f"Input file not found: {args.input}")

    if not args.output and not args.json:
        raise SystemExit("Must specify at least one output format (--output or --json)")

    print(f"📖 Reading results from: {args.input}")
    
    # Parse all results
    all_data = []
    errors = []
    validation_issues = []
    
    with open(args.input, 'r', encoding='utf-8') as f:
        for line_num, line in enumerate(f, 1):
            result = parse_result_line(line)
            if result:
                if 'error' in result:
                    errors.append((line_num, result))
                else:
                    all_data.append(result)
                    if args.validate:
                        issues = validate_character_data(result)
                        if issues:
                            validation_issues.append((result.get('custom_id', 'unknown'), issues))

    print(f"✅ Parsed {len(all_data)} successful results")
    if errors:
        print(f"⚠️  Found {len(errors)} errors")

    # Sort by Index
    all_data.sort(key=lambda x: int(x.get('Index', '0') or '0'))

    # Write CSV
    if args.output:
        print(f"📝 Writing CSV to: {args.output}")
        fieldnames = ['custom_id', 'Index', 'Character', 'Pinyin', 'Radical', 'Strokes', 'Structure']
        with open(args.output, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for data in all_data:
                # Only write if no error
                if 'error' not in data:
                    writer.writerow(data)
        print(f"✅ CSV written: {len(all_data)} rows")

    # Write JSON
    if args.json:
        print(f"📝 Writing JSON to: {args.json}")
        with open(args.json, 'w', encoding='utf-8') as f:
            json.dump(all_data, f, ensure_ascii=False, indent=2)
        print(f"✅ JSON written: {len(all_data)} entries")

    # Show errors
    if errors:
        print(f"\n❌ Errors found:")
        for line_num, error in errors[:10]:  # Show first 10
            print(f"   Line {line_num}: {error.get('error', 'Unknown error')}")
            if 'raw_output' in error:
                print(f"      Output: {error['raw_output']}")
        if len(errors) > 10:
            print(f"   ... and {len(errors) - 10} more errors")

    # Show validation issues
    if validation_issues:
        print(f"\n⚠️  Validation issues found:")
        for custom_id, issues in validation_issues[:10]:  # Show first 10
            print(f"   {custom_id}: {', '.join(issues)}")
        if len(validation_issues) > 10:
            print(f"   ... and {len(validation_issues) - 10} more issues")

    # Show statistics
    if args.stats:
        print(f"\n📊 Statistics:")
        print(f"   Total entries: {len(all_data)}")
        print(f"   Errors: {len(errors)}")
        print(f"   Validation issues: {len(validation_issues)}")
        
        if all_data:
            # Count entries with dictionary corrections
            dict_corrections = sum(
                1 for d in all_data
                if '(dictionary)' in str(d.get('Pinyin', '')) or
                   '(dictionary)' in str(d.get('Radical', '')) or
                   '(dictionary)' in str(d.get('Strokes', ''))
            )
            print(f"   Dictionary corrections: {dict_corrections}")
            
            # Show index range
            indices = [int(d.get('Index', '0') or '0') for d in all_data if d.get('Index')]
            if indices:
                print(f"   Index range: {min(indices):04d} - {max(indices):04d}")
            
            # Count unique characters
            characters = [d.get('Character') for d in all_data if d.get('Character')]
            unique_chars = len(set(characters))
            print(f"   Unique characters: {unique_chars}")

    print(f"\n✅ Parsing complete!")


if __name__ == "__main__":
    main()
