#!/usr/bin/env python3
"""
Organize characters by radicals.
Outputs a JSON file where each entry contains:
- radical: the radical character
- characters: array of characters that have that radical
"""
import json
import argparse
from pathlib import Path
from collections import defaultdict

# Default data directory (relative to script location)
# Script is at: chinese_chr_app/extract_characters_using_ai/organize_by_radicals.py
# Data is at: chinese_chr_app/data/
DEFAULT_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DEFAULT_INPUT = str(DEFAULT_DATA_DIR / "characters.json")
DEFAULT_OUTPUT = str(DEFAULT_DATA_DIR / "characters_by_radicals.json")

def organize_by_radicals(input_json_path, output_json_path):
    """
    Organize characters by their radicals.
    
    Args:
        input_json_path: Path to input characters.json file
        output_json_path: Path to output JSON file
    """
    # Load character data
    print(f"Loading characters from: {input_json_path}")
    with open(input_json_path, 'r', encoding='utf-8') as f:
        characters = json.load(f)
    
    print(f"Loaded {len(characters)} characters")
    
    # Organize by radical
    radical_dict = defaultdict(list)
    
    for char in characters:
        radical = char.get('Radical', '').strip()
        # Remove dictionary markers if present
        if ' (dictionary)' in radical:
            radical = radical.replace(' (dictionary)', '')
        
        if radical:
            character_info = {
                'Character': char.get('Character', ''),
                'Index': char.get('Index', ''),
                'Pinyin': char.get('Pinyin', []),
                'Strokes': char.get('Strokes', ''),
                'Structure': char.get('Structure', '')
            }
            radical_dict[radical].append(character_info)
    
    # Convert to the desired format
    result = []
    for radical, chars in sorted(radical_dict.items()):
        result.append({
            'radical': radical,
            'characters': chars
        })
    
    # Save to output file
    print(f"\nOrganized into {len(result)} unique radicals")
    print(f"Saving to: {output_json_path}")
    
    with open(output_json_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    
    # Print statistics
    print("\nStatistics:")
    print(f"  Total radicals: {len(result)}")
    print(f"  Total characters: {len(characters)}")
    
    # Show top 10 radicals by character count
    sorted_radicals = sorted(result, key=lambda x: len(x['characters']), reverse=True)
    print("\nTop 10 radicals by character count:")
    for i, entry in enumerate(sorted_radicals[:10], 1):
        print(f"  {i}. {entry['radical']}: {len(entry['characters'])} characters")
    
    print(f"\n✓ Successfully organized characters by radicals!")

def main():
    parser = argparse.ArgumentParser(
        description='Organize characters by radicals and output JSON'
    )
    parser.add_argument(
        '--input',
        type=str,
        default=DEFAULT_INPUT,
        help=f'Input characters.json file path (default: {DEFAULT_INPUT})'
    )
    parser.add_argument(
        '--output',
        type=str,
        default=DEFAULT_OUTPUT,
        help=f'Output JSON file path (default: {DEFAULT_OUTPUT})'
    )
    
    args = parser.parse_args()
    
    # Resolve paths relative to script directory
    script_dir = Path(__file__).resolve().parent
    input_path = script_dir / args.input
    output_path = script_dir / args.output
    
    if not input_path.exists():
        print(f"Error: Input file not found: {input_path}")
        return 1
    
    # Create output directory if it doesn't exist
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    organize_by_radicals(input_path, output_path)
    return 0

if __name__ == '__main__':
    exit(main())
