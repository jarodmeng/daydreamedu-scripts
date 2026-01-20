#!/usr/bin/env python3
"""
Generate PNG files from Chinese character PDF cards.

This script:
1. Reads PDF files from the specified directory (named <dddd>-<dddd>.pdf)
2. Each PDF contains 20 pages (10 characters, 2 pages per character)
3. Extracts 2 PNG pages for each character
4. Creates a folder structure: png/<dddd>/ with the 2 PNG files

Usage:
    python3 generate_png_from_pdfs.py \
      --pdf_dir "/path/to/冯氏早教识字卡/" \
      --output_dir "chinese_chr_app/data/png"
"""

import argparse
import re
import sys
from pathlib import Path
from typing import Tuple, Optional

try:
    import fitz  # PyMuPDF
except ImportError:
    print("Error: PyMuPDF (fitz) is required. Install it with: pip3 install pymupdf")
    sys.exit(1)


def parse_index_range_from_filename(filename: str) -> Tuple[int, int]:
    """
    Parse index range from filename like '0001-0010.pdf'.
    Returns (start_index, end_index).
    """
    match = re.match(r'^(\d{4})-(\d{4})\.pdf$', filename)
    if not match:
        raise ValueError(f"Filename doesn't match pattern <dddd>-<dddd>.pdf: {filename}")
    
    start = int(match.group(1))
    end = int(match.group(2))
    
    if start > end:
        raise ValueError(f"Invalid range: start ({start}) > end ({end})")
    
    return start, end


def generate_pngs_from_pdf(pdf_path: Path, output_base_dir: Path, dpi: int = 300, 
                           min_index: Optional[int] = None, max_index: Optional[int] = None) -> int:
    """
    Generate PNG files from a PDF.
    
    Args:
        pdf_path: Path to the PDF file
        output_base_dir: Base directory for PNG output (will create png/<dddd>/ folders)
        dpi: DPI for rendering (default: 300)
    """
    # Parse filename to get character range
    try:
        start_idx, end_idx = parse_index_range_from_filename(pdf_path.name)
    except ValueError as e:
        print(f"⚠️  Skipping {pdf_path.name}: {e}")
        return 0
    
    # Open PDF
    try:
        doc = fitz.open(str(pdf_path))
    except Exception as e:
        print(f"❌ Error opening {pdf_path.name}: {e}")
        return 0
    
    total_pages = doc.page_count
    expected_pages = (end_idx - start_idx + 1) * 2
    
    if total_pages != expected_pages:
        print(f"⚠️  Warning: {pdf_path.name} has {total_pages} pages, expected {expected_pages}")
    
    # Process each character
    characters_processed = 0
    for char_idx in range(start_idx, end_idx + 1):
        # Skip if outside the specified range
        if min_index is not None and char_idx < min_index:
            continue
        if max_index is not None and char_idx > max_index:
            continue
        # Calculate page numbers for this character (0-indexed)
        # Character at index i has pages: 2*(i-start_idx) and 2*(i-start_idx)+1
        page1_idx = 2 * (char_idx - start_idx)
        page2_idx = page1_idx + 1
        
        if page2_idx >= total_pages:
            print(f"⚠️  Warning: Not enough pages for character {char_idx:04d} in {pdf_path.name}")
            break
        
        # Create character folder
        char_folder = output_base_dir / f"{char_idx:04d}"
        char_folder.mkdir(parents=True, exist_ok=True)
        
        # Render and save page 1
        try:
            page1 = doc[page1_idx]
            pix1 = page1.get_pixmap(dpi=dpi)
            png_path1 = char_folder / "page1.png"
            pix1.save(str(png_path1))
        except Exception as e:
            print(f"❌ Error rendering page 1 for character {char_idx:04d}: {e}")
            continue
        
        # Render and save page 2
        try:
            page2 = doc[page2_idx]
            pix2 = page2.get_pixmap(dpi=dpi)
            png_path2 = char_folder / "page2.png"
            pix2.save(str(png_path2))
        except Exception as e:
            print(f"❌ Error rendering page 2 for character {char_idx:04d}: {e}")
            continue
        
        characters_processed += 1
    
    doc.close()
    if characters_processed > 0:
        print(f"✅ Processed {characters_processed} characters from {pdf_path.name}")
    return characters_processed


def main():
    parser = argparse.ArgumentParser(
        description="Generate PNG files from Chinese character PDF cards."
    )
    parser.add_argument(
        "--pdf_dir",
        required=True,
        type=Path,
        help="Directory containing PDF files (named <dddd>-<dddd>.pdf)",
    )
    parser.add_argument(
        "--output_dir",
        type=Path,
        help="Output directory for PNG files (default: pdf_dir/png)",
    )
    parser.add_argument(
        "--dpi",
        type=int,
        default=300,
        help="DPI for rendering PNG files (default: 300)",
    )
    parser.add_argument(
        "--max_pdfs",
        type=int,
        default=None,
        help="Process only the first N PDFs (for testing)",
    )
    parser.add_argument(
        "--index",
        type=int,
        default=None,
        help="Process only a specific character index (e.g., 11 for character 0011)",
    )
    parser.add_argument(
        "--range",
        type=str,
        default=None,
        help="Process a range of character indices (e.g., '11-20' for characters 0011-0020)",
    )
    
    args = parser.parse_args()
    
    # Parse index range if provided
    min_index = None
    max_index = None
    
    if args.index is not None:
        if args.range is not None:
            raise SystemExit("Error: Cannot specify both --index and --range")
        min_index = args.index
        max_index = args.index
    elif args.range is not None:
        # Parse range like "11-20" or "0011-0020"
        range_match = re.match(r'^(\d+)-(\d+)$', args.range)
        if not range_match:
            raise SystemExit(f"Error: Invalid range format: {args.range}. Use format like '11-20' or '0011-0020'")
        min_index = int(range_match.group(1))
        max_index = int(range_match.group(2))
        if min_index > max_index:
            raise SystemExit(f"Error: Invalid range: start ({min_index}) > end ({max_index})")
    
    pdf_dir = args.pdf_dir
    if not pdf_dir.is_dir():
        raise SystemExit(f"Error: PDF directory not found: {pdf_dir}")
    
    # Set output directory
    if args.output_dir:
        output_dir = args.output_dir
    else:
        output_dir = pdf_dir / "png"
    
    # Create output directory
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"📁 PDF directory: {pdf_dir}")
    print(f"📁 Output directory: {output_dir}")
    print(f"🖼️  DPI: {args.dpi}")
    if min_index is not None:
        print(f"🎯 Processing characters: {min_index:04d}" + (f"-{max_index:04d}" if max_index != min_index else ""))
    print()
    
    # Find all PDF files matching the pattern
    pdf_files = sorted(pdf_dir.glob("*.pdf"))
    pdf_files = [f for f in pdf_files if re.match(r'^\d{4}-\d{4}\.pdf$', f.name)]
    
    if not pdf_files:
        raise SystemExit(f"Error: No PDF files matching pattern <dddd>-<dddd>.pdf found in {pdf_dir}")
    
    if args.max_pdfs:
        pdf_files = pdf_files[:args.max_pdfs]
        print(f"⚠️  Processing only first {args.max_pdfs} PDFs (testing mode)")
    
    print(f"📄 Found {len(pdf_files)} PDF files to process\n")
    
    # Process each PDF
    total_characters = 0
    for pdf_file in pdf_files:
        # Check if this PDF might contain characters in our range
        if min_index is not None or max_index is not None:
            try:
                pdf_start, pdf_end = parse_index_range_from_filename(pdf_file.name)
                # Skip PDF if it doesn't overlap with our range
                if min_index is not None and pdf_end < min_index:
                    continue
                if max_index is not None and pdf_start > max_index:
                    continue
            except ValueError:
                pass
        
        chars_in_file = generate_pngs_from_pdf(pdf_file, output_dir, args.dpi, min_index, max_index)
        total_characters += chars_in_file
    
    print(f"\n✅ Processing complete!")
    print(f"   Total PDFs processed: {len(pdf_files)}")
    print(f"   Total characters processed: {total_characters}")
    print(f"   PNG files saved to: {output_dir}")


if __name__ == "__main__":
    main()
