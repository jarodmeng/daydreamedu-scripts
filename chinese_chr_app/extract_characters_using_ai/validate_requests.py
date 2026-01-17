#!/usr/bin/env python3
"""
Validate OpenAI Batch API requests.jsonl file before submission.

This script checks:
1. File format (valid JSONL)
2. Each line is valid JSON
3. Required fields are present
4. Structure matches OpenAI Batch API requirements
5. File size is within limits (512 MB)
6. Check for duplicate custom_ids

Usage:
    python3 validate_requests.py --jsonl jsonl/requests.jsonl
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List, Set


def validate_jsonl_line(line_num: int, line: str) -> tuple[bool, Dict, List[str]]:
    """
    Validate a single JSONL line.
    Returns (is_valid, parsed_data, errors)
    """
    errors = []
    
    # Check if line is empty
    if not line.strip():
        return False, {}, ["Empty line"]
    
    # Parse JSON
    try:
        data = json.loads(line)
    except json.JSONDecodeError as e:
        return False, {}, [f"Invalid JSON: {e}"]
    
    # Check required top-level fields
    required_fields = ['custom_id', 'method', 'url', 'body']
    for field in required_fields:
        if field not in data:
            errors.append(f"Missing required field: {field}")
    
    # Validate custom_id
    if 'custom_id' in data:
        if not isinstance(data['custom_id'], str):
            errors.append(f"custom_id must be a string, got {type(data['custom_id'])}")
        elif not data['custom_id']:
            errors.append("custom_id cannot be empty")
    
    # Validate method and url
    if 'method' in data and data.get('method') != 'POST':
        errors.append(f"method must be 'POST', got '{data.get('method')}'")
    
    if 'url' in data and data.get('url') != '/v1/responses':
        errors.append(f"url must be '/v1/responses', got '{data.get('url')}'")
    
    # Validate body structure
    if 'body' in data:
        body = data['body']
        if not isinstance(body, dict):
            errors.append("body must be a dictionary")
        else:
            # Check for model
            if 'model' not in body:
                errors.append("body.model is required")
            
            # Check for input array
            if 'input' not in body:
                errors.append("body.input is required")
            elif not isinstance(body['input'], list):
                errors.append("body.input must be an array")
            elif len(body['input']) < 2:
                errors.append("body.input must have at least 2 items (system and user messages)")
            
            # Check input structure
            if isinstance(body.get('input'), list) and len(body['input']) >= 2:
                # Check system message
                system_msg = body['input'][0]
                if not isinstance(system_msg, dict) or system_msg.get('role') != 'system':
                    errors.append("First item in body.input must be system message with role='system'")
                
                # Check user message
                user_msg = body['input'][1]
                if not isinstance(user_msg, dict) or user_msg.get('role') != 'user':
                    errors.append("Second item in body.input must be user message with role='user'")
                
                # Check user message content
                if isinstance(user_msg, dict):
                    content = user_msg.get('content', [])
                    if not isinstance(content, list):
                        errors.append("user message content must be an array")
                    else:
                        # Check for image
                        has_image = False
                        for item in content:
                            if isinstance(item, dict) and item.get('type') == 'input_image':
                                has_image = True
                                break
                        if not has_image:
                            errors.append("user message content must include an input_image")
    
    is_valid = len(errors) == 0
    return is_valid, data, errors


def validate_file(file_path: Path, max_size_mb: int = 512) -> Dict:
    """
    Validate the entire JSONL file.
    Returns validation results dictionary.
    """
    if not file_path.exists():
        return {
            'valid': False,
            'error': f"File not found: {file_path}",
        }
    
    # Check file size
    file_size = file_path.stat().st_size
    file_size_mb = file_size / (1024 * 1024)
    max_size_bytes = max_size_mb * 1024 * 1024
    
    if file_size > max_size_bytes:
        return {
            'valid': False,
            'error': f"File size ({file_size_mb:.2f} MB) exceeds limit ({max_size_mb} MB)",
            'file_size_mb': file_size_mb,
        }
    
    # Read and validate each line
    total_lines = 0
    valid_lines = 0
    invalid_lines = []
    duplicate_ids: Set[str] = set()
    seen_ids: Set[str] = set()
    custom_ids: List[str] = []
    
    print(f"📖 Reading and validating: {file_path}")
    print(f"   File size: {file_size_mb:.2f} MB")
    
    with open(file_path, 'r', encoding='utf-8') as f:
        for line_num, line in enumerate(f, 1):
            total_lines += 1
            
            is_valid, data, errors = validate_jsonl_line(line_num, line)
            
            if is_valid:
                valid_lines += 1
                # Check for duplicate custom_ids
                if 'custom_id' in data:
                    custom_id = data['custom_id']
                    custom_ids.append(custom_id)
                    if custom_id in seen_ids:
                        duplicate_ids.add(custom_id)
                    seen_ids.add(custom_id)
            else:
                invalid_lines.append({
                    'line': line_num,
                    'errors': errors,
                    'custom_id': data.get('custom_id', 'unknown') if data else 'parse_failed',
                })
    
    # Summary
    result = {
        'valid': len(invalid_lines) == 0 and len(duplicate_ids) == 0,
        'file_size_mb': file_size_mb,
        'total_lines': total_lines,
        'valid_lines': valid_lines,
        'invalid_lines': len(invalid_lines),
        'duplicate_ids': len(duplicate_ids),
        'unique_custom_ids': len(seen_ids),
        'errors': invalid_lines[:20],  # First 20 errors
        'duplicate_custom_ids': list(duplicate_ids)[:20],  # First 20 duplicates
    }
    
    return result


def print_validation_results(result: Dict, file_path: Path):
    """Print validation results in a readable format."""
    print(f"\n{'='*60}")
    print(f"📊 Validation Results: {file_path.name}")
    print(f"{'='*60}")
    
    if 'error' in result:
        print(f"❌ {result['error']}")
        return
    
    print(f"\n📁 File Information:")
    print(f"   File size: {result['file_size_mb']:.2f} MB")
    print(f"   Total lines: {result['total_lines']:,}")
    print(f"   Valid lines: {result['valid_lines']:,}")
    
    if result['invalid_lines'] > 0:
        print(f"   ❌ Invalid lines: {result['invalid_lines']:,}")
    
    if result['duplicate_ids'] > 0:
        print(f"   ❌ Duplicate custom_ids: {result['duplicate_ids']:,}")
    
    print(f"   Unique custom_ids: {result['unique_custom_ids']:,}")
    
    # Show errors
    if result['errors']:
        print(f"\n❌ Validation Errors (showing first {len(result['errors'])}):")
        for error_info in result['errors']:
            print(f"   Line {error_info['line']} (custom_id: {error_info['custom_id']}):")
            for error in error_info['errors']:
                print(f"      - {error}")
        if result['invalid_lines'] > len(result['errors']):
            print(f"   ... and {result['invalid_lines'] - len(result['errors'])} more errors")
    
    # Show duplicates
    if result['duplicate_custom_ids']:
        print(f"\n⚠️  Duplicate custom_ids (showing first {len(result['duplicate_custom_ids'])}):")
        for dup_id in result['duplicate_custom_ids']:
            print(f"   - {dup_id}")
        if result['duplicate_ids'] > len(result['duplicate_custom_ids']):
            print(f"   ... and {result['duplicate_ids'] - len(result['duplicate_custom_ids'])} more duplicates")
    
    # Final verdict
    print(f"\n{'='*60}")
    if result['valid']:
        print(f"✅ Validation PASSED - File is ready for upload")
    else:
        print(f"❌ Validation FAILED - Please fix errors before uploading")
    print(f"{'='*60}")


def main():
    parser = argparse.ArgumentParser(
        description="Validate OpenAI Batch API requests.jsonl file before submission."
    )
    parser.add_argument(
        "--jsonl",
        default="jsonl/requests.jsonl",
        type=Path,
        help="Path to requests.jsonl file (default: jsonl/requests.jsonl)",
    )
    parser.add_argument(
        "--max_size_mb",
        type=int,
        default=512,
        help="Maximum file size in MB (default: 512, OpenAI limit)",
    )
    parser.add_argument(
        "--pattern",
        type=str,
        default=None,
        help="Pattern to match multiple files (e.g., 'jsonl/requests*.jsonl')",
    )
    
    args = parser.parse_args()
    
    # Handle pattern matching
    if args.pattern:
        import glob
        jsonl_files = sorted([Path(f) for f in glob.glob(args.pattern)])
        if not jsonl_files:
            raise SystemExit(f"No files found matching pattern: {args.pattern}")
    else:
        jsonl_files = [args.jsonl]
    
    # Validate each file
    all_valid = True
    for jsonl_file in jsonl_files:
        result = validate_file(jsonl_file, args.max_size_mb)
        print_validation_results(result, jsonl_file)
        if not result.get('valid', False):
            all_valid = False
    
    # Exit code
    if all_valid:
        print(f"\n✅ All files validated successfully!")
        sys.exit(0)
    else:
        print(f"\n❌ Validation failed for one or more files")
        sys.exit(1)


if __name__ == "__main__":
    main()
