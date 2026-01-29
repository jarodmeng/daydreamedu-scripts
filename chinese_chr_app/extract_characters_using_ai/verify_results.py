#!/usr/bin/env python3
"""
Verify that extracted characters appear in their sentences and words.
This validates that the new prompt's character validation is working.
"""

import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Tuple


def extract_table_from_response(response_text: str) -> str:
    """Extract markdown table from response text."""
    table_start = response_text.find('| Index | Character | Pinyin | Radical | Strokes | Structure | Sentence | Words |')
    if table_start == -1:
        return ""
    
    table_text = response_text[table_start:]
    lines = table_text.split('\n')
    table_lines = []
    for line in lines:
        if line.strip() and ('|' in line or not table_lines):
            table_lines.append(line)
        elif table_lines and not line.strip():
            break
    
    return '\n'.join(table_lines)


def parse_markdown_table(table_text: str) -> Dict[str, str]:
    """Parse a markdown table row and extract fields."""
    lines = [line.strip() for line in table_text.strip().split('\n') if line.strip()]
    
    if len(lines) < 2:
        return {}
    
    data_lines = lines[1:]
    
    for line in data_lines:
        if re.match(r'^\|[\s\-:]+\|', line):
            continue
        
        parts = [p.strip() for p in line.split('|') if p.strip()]
        
        if len(parts) >= 8:
            return {
                'Index': parts[0],
                'Character': parts[1],
                'Pinyin': parts[2],
                'Radical': parts[3],
                'Strokes': parts[4],
                'Structure': parts[5],
                'Sentence': parts[6],
                'Words': parts[7],
            }
    
    return {}


def verify_character_in_context(char: str, sentence: str, words_str: str) -> Tuple[bool, List[str]]:
    """Verify that character appears in sentence and words."""
    issues = []
    
    # Check sentence
    if char not in sentence:
        issues.append(f"Character '{char}' NOT found in Sentence: '{sentence}'")
    
    # Parse words JSON array
    try:
        words = json.loads(words_str) if words_str else []
        if not isinstance(words, list):
            words = []
    except json.JSONDecodeError:
        issues.append(f"Failed to parse Words JSON: {words_str}")
        words = []
    
    # Check words
    if words:
        found_in_words = any(char in word for word in words)
        if not found_in_words:
            issues.append(f"Character '{char}' NOT found in any Words: {words}")
    else:
        issues.append(f"No words provided (empty array)")
    
    return len(issues) == 0, issues


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 verify_results.py <results_file.jsonl> [results_file2.jsonl ...]")
        sys.exit(1)
    
    all_issues = []
    total_entries = 0
    valid_entries = 0
    
    for results_file in sys.argv[1:]:
        results_path = Path(results_file)
        if not results_path.exists():
            print(f"⚠️  File not found: {results_path}")
            continue
        
        print(f"\n📖 Verifying: {results_path}")
        
        with open(results_path, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                try:
                    result = json.loads(line)
                except json.JSONDecodeError:
                    print(f"⚠️  Line {line_num}: Invalid JSON")
                    continue
                
                index = result.get('custom_id', '')  # API field name; value is character card Index
                response = result.get('response', {})
                body = response.get('body', {})
                output = body.get('output', [])
                
                # Extract text from output
                output_text = ''
                if isinstance(output, list):
                    for item in output:
                        if item.get('type') == 'message' and item.get('status') == 'completed':
                            content = item.get('content', [])
                            for content_item in content:
                                if content_item.get('type') == 'output_text':
                                    output_text = content_item.get('text', '')
                                    break
                            if output_text:
                                break
                
                if not output_text:
                    continue
                
                # Parse table
                table_text = extract_table_from_response(output_text)
                if not table_text:
                    continue
                
                char_data = parse_markdown_table(table_text)
                if not char_data or 'Character' not in char_data:
                    continue
                
                total_entries += 1
                char = char_data['Character']
                sentence = char_data.get('Sentence', '')
                words_str = char_data.get('Words', '[]')
                
                # Verify character appears in context
                is_valid, issues = verify_character_in_context(char, sentence, words_str)
                
                if is_valid:
                    valid_entries += 1
                else:
                    all_issues.append({
                        'Index': index,
                        'character': char,
                        'sentence': sentence,
                        'words': words_str,
                        'issues': issues
                    })
    
    # Print summary
    print(f"\n{'='*60}")
    print(f"📊 Verification Summary")
    print(f"{'='*60}")
    print(f"Total entries checked: {total_entries}")
    print(f"✅ Valid entries (character in sentence & words): {valid_entries}")
    print(f"❌ Entries with issues: {len(all_issues)}")
    
    if all_issues:
        print(f"\n❌ Issues found:")
        for issue in all_issues:
            print(f"\n  Index {issue['Index']}:")
            print(f"    Character: {issue['character']}")
            print(f"    Sentence: {issue['sentence']}")
            try:
                words = json.loads(issue['words'])
                print(f"    Words: {words}")
            except:
                print(f"    Words: {issue['words']}")
            for problem in issue['issues']:
                print(f"    ⚠️  {problem}")
    else:
        print(f"\n✅ All entries passed validation! The new prompt is working correctly.")
    
    print(f"\n{'='*60}")


if __name__ == "__main__":
    main()
