#!/usr/bin/env python3
"""
Batch extract character information from HWXNet for all characters in characters.json.
Includes rate limiting, progress tracking, and timing information.
"""

import json
import time
import sys
import threading
from pathlib import Path
from typing import Dict, List, Any, Tuple, Optional
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
import traceback

# Import the extraction function
from extract_character_hwxnet import extract_character_info

# Paths
SCRIPT_DIR = Path(__file__).resolve().parent
BASE_DIR = SCRIPT_DIR.parent
DATA_DIR = BASE_DIR / "data"
CHARACTERS_JSON = DATA_DIR / "characters.json"
OUTPUT_JSON = DATA_DIR / "extracted_characters_hwxnet.json"
BACKUP_DIR = DATA_DIR / "backups"
PROGRESS_JSON = SCRIPT_DIR / "extraction_progress_hwxnet.json"

LEVEL_JSON_FILES = [
    DATA_DIR / "level-1.json",
    DATA_DIR / "level-2.json",
    DATA_DIR / "level-3.json",
]


def load_characters(limit: int = None) -> List[str]:
    """Load characters from characters.json."""
    if not CHARACTERS_JSON.exists():
        raise FileNotFoundError(f"Characters file not found: {CHARACTERS_JSON}")
    
    with open(CHARACTERS_JSON, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # Extract unique characters
    characters = []
    seen = set()
    for entry in data:
        char = entry.get('Character', '').strip()
        if char and char not in seen:
            characters.append(char)
            seen.add(char)
    
    if limit:
        characters = characters[:limit]
    
    return characters


def load_characters_from_txt(file_path: Path, limit: int = None) -> List[str]:
    """
    Load characters from a text file (one character per line).
    Ignores blank lines and lines starting with '#'.
    """
    if not file_path.exists():
        raise FileNotFoundError(f"Characters file not found: {file_path}")

    characters: List[str] = []
    seen = set()

    for raw_line in file_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        # Expect exactly one unicode character per line
        if len(line) != 1:
            raise ValueError(f"Invalid line in {file_path} (expected 1 character): {raw_line!r}")

        if line not in seen:
            characters.append(line)
            seen.add(line)

        if limit and len(characters) >= limit:
            break

    return characters


def load_progress() -> Dict[str, Any]:
    """Load previous extraction progress."""
    if PROGRESS_JSON.exists():
        with open(PROGRESS_JSON, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {
        "processed": {},
        "failed": {},
        "last_updated": None
    }


def save_progress(progress: Dict[str, Any]):
    """Save extraction progress."""
    progress["last_updated"] = datetime.now().isoformat()
    with open(PROGRESS_JSON, 'w', encoding='utf-8') as f:
        json.dump(progress, f, ensure_ascii=False, indent=2)

def load_existing_output() -> Dict[str, Any]:
    """Load existing extracted results from OUTPUT_JSON, if present."""
    if not OUTPUT_JSON.exists():
        return {}
    try:
        with open(OUTPUT_JSON, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def load_char_to_index_mapping() -> Dict[str, str]:
    """Load character to index mapping from characters.json."""
    if not CHARACTERS_JSON.exists():
        return {}
    
    try:
        with open(CHARACTERS_JSON, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return {item['Character']: item['Index'] for item in data}
    except Exception:
        return {}


# Cache the mapping to avoid reloading
_char_to_index_cache = None

def get_char_to_index_mapping() -> Dict[str, str]:
    """Get character to index mapping (cached)."""
    global _char_to_index_cache
    if _char_to_index_cache is None:
        _char_to_index_cache = load_char_to_index_mapping()
    return _char_to_index_cache


def load_char_to_zibiao_index_mapping() -> Dict[str, int]:
    """
    Load character -> zibiao index mapping from level-*.json.
    These indices correspond to the Zìbiǎo-style ordering used in the level files.
    """
    mapping: Dict[str, int] = {}
    for p in LEVEL_JSON_FILES:
        if not p.exists():
            continue
        try:
            with open(p, "r", encoding="utf-8") as f:
                data = json.load(f)
            for item in data:
                ch = item.get("char")
                idx = item.get("index")
                if isinstance(ch, str) and isinstance(idx, int):
                    mapping[ch] = idx
        except Exception:
            # If any level file is unreadable, skip it (mapping will be partial)
            continue
    return mapping


_char_to_zibiao_index_cache = None


def get_char_to_zibiao_index_mapping() -> Dict[str, int]:
    """Get character -> zibiao index mapping (cached)."""
    global _char_to_zibiao_index_cache
    if _char_to_zibiao_index_cache is None:
        _char_to_zibiao_index_cache = load_char_to_zibiao_index_mapping()
    return _char_to_zibiao_index_cache


_did_backup_output = False


def ensure_output_backup():
    """
    Ensure OUTPUT_JSON is backed up once per run before any write.
    Backup is stored in DATA_DIR/backups (gitignored).
    """
    global _did_backup_output
    if _did_backup_output:
        return
    if not OUTPUT_JSON.exists():
        _did_backup_output = True
        return

    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_path = BACKUP_DIR / f"{OUTPUT_JSON.stem}.{ts}.json"
    # Avoid collisions if multiple backups in same second
    if backup_path.exists():
        ts = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        backup_path = BACKUP_DIR / f"{OUTPUT_JSON.stem}.{ts}.json"

    backup_path.write_bytes(OUTPUT_JSON.read_bytes())
    print(f"Backed up existing output to: {backup_path}")
    _did_backup_output = True


def save_results(results: Dict[str, Any]):
    """Save extracted results, preserving and adding index fields."""
    # IMPORTANT: backup original output before any merge/write
    ensure_output_backup()

    # Get character to index mapping first (always needed)
    char_to_index = get_char_to_index_mapping()
    char_to_zibiao_index = get_char_to_zibiao_index_mapping()
    
    # Load existing file to preserve all existing entries and their index fields
    merged_results = {}
    if OUTPUT_JSON.exists():
        try:
            with open(OUTPUT_JSON, 'r', encoding='utf-8') as f:
                merged_results = json.load(f)
        except Exception:
            pass  # If file is corrupted, start fresh
    
    # Update with new results, ALWAYS ensuring index fields are present
    for char, data in results.items():
        # CRITICAL: Always preserve index from existing merged_results if present
        existing_index = None
        existing_zibiao_index = None
        if char in merged_results and 'index' in merged_results[char]:
            existing_index = merged_results[char]['index']
        if char in merged_results and 'zibiao_index' in merged_results[char]:
            existing_zibiao_index = merged_results[char]['zibiao_index']
        
        # Update the entry with new data
        merged_results[char] = data
        
        # CRITICAL: Restore index if it existed, or add from mapping
        if existing_index:
            merged_results[char]['index'] = existing_index
        elif char in char_to_index:
            merged_results[char]['index'] = char_to_index[char]

        # Add/restore zibiao_index (from level lists)
        if existing_zibiao_index is not None:
            merged_results[char]['zibiao_index'] = existing_zibiao_index
        elif char in char_to_zibiao_index:
            merged_results[char]['zibiao_index'] = char_to_zibiao_index[char]
    
    # CRITICAL: Ensure ALL entries have index fields (for any that might be missing)
    # This handles cases where the file was written without indices
    for char, data in merged_results.items():
        if 'index' not in data and char in char_to_index:
            data['index'] = char_to_index[char]
        if 'zibiao_index' not in data and char in char_to_zibiao_index:
            data['zibiao_index'] = char_to_zibiao_index[char]
    
    # Save merged results
    with open(OUTPUT_JSON, 'w', encoding='utf-8') as f:
        json.dump(merged_results, f, ensure_ascii=False, indent=2)


class RateLimiter:
    """Thread-safe rate limiter using token bucket algorithm."""
    def __init__(self, rate: float):
        """
        Args:
            rate: Requests per second
        """
        self.rate = rate
        self.min_interval = 1.0 / rate if rate > 0 else 0
        self.last_request_time = 0.0
        self.lock = threading.Lock()
    
    def acquire(self):
        """Wait until a request can be made."""
        with self.lock:
            current_time = time.time()
            elapsed = current_time - self.last_request_time
            if elapsed < self.min_interval:
                time.sleep(self.min_interval - elapsed)
            self.last_request_time = time.time()


def extract_with_retry(char: str, max_retries: int = 3, retry_delay: float = 2.0) -> Tuple[Optional[Dict[str, Any]], int]:
    """
    Extract character information with retry logic.
    
    Args:
        char: Character to extract
        max_retries: Maximum number of retry attempts
        retry_delay: Seconds to wait between retries
        
    Returns:
        Tuple of (extracted_info, attempts_used) or (None, attempts_used) if all retries failed
    """
    last_error = None
    
    for attempt in range(1, max_retries + 1):
        try:
            info = extract_character_info(char)
            return info, attempt
        except Exception as e:
            last_error = e
            if attempt < max_retries:
                time.sleep(retry_delay)
    
    # All retries failed
    return None, max_retries


def batch_extract(characters: List[str], 
                  rate_limit_seconds: float = 1.5,
                  test_mode: bool = False,
                  max_retries: int = 3,
                  retry_delay: float = 2.0,
                  overwrite: bool = False) -> Dict[str, Any]:
    """
    Extract information for a list of characters with rate limiting.
    
    Args:
        characters: List of characters to extract
        rate_limit_seconds: Seconds to wait between requests
        test_mode: If True, only process first 100 characters
        max_retries: Maximum number of retry attempts
        retry_delay: Seconds to wait between retries
        overwrite: If True, reprocess and overwrite existing entries
        
    Returns:
        Dictionary with results, timing, and statistics
    """
    if test_mode:
        characters = characters[:100]
        print(f"TEST MODE: Processing first {len(characters)} characters")
    
    # Load previous progress
    progress = load_progress()
    processed = progress.get("processed", {})
    failed = progress.get("failed", {})

    # Also treat existing OUTPUT_JSON entries as processed (skip by default)
    existing_output = load_existing_output()
    if existing_output:
        for ch, entry in existing_output.items():
            if ch not in processed and isinstance(entry, dict):
                processed[ch] = entry
    
    # Filter out already processed characters (unless overwrite is enabled)
    if overwrite:
        remaining = [c for c in characters if c not in failed]
        if processed:
            print(f"OVERWRITE MODE: Will reprocess {len([c for c in characters if c in processed])} existing entries")
    else:
        remaining = [c for c in characters if c not in processed and c not in failed]
    
    if not remaining:
        print("All characters have already been processed!")
        return {
            "total": len(characters),
            "processed": len(processed),
            "failed": len(failed),
            "results": processed
        }
    
    print(f"Total characters to process: {len(characters)}")
    print(f"Already processed: {len(processed)}")
    print(f"Already failed: {len(failed)}")
    print(f"Remaining: {len(remaining)}")
    print(f"Rate limit: {rate_limit_seconds} seconds between requests")
    print(f"Max retries: {max_retries}")
    print(f"Retry delay: {retry_delay} seconds")
    print("=" * 70)
    
    results = processed.copy()
    # Ensure all loaded results have index fields
    char_to_index = get_char_to_index_mapping()
    char_to_zibiao_index = get_char_to_zibiao_index_mapping()
    for char, data in results.items():
        if 'index' not in data and char in char_to_index:
            data['index'] = char_to_index[char]
        if 'zibiao_index' not in data and char in char_to_zibiao_index:
            data['zibiao_index'] = char_to_zibiao_index[char]
    
    new_failed = {}
    
    # Timing statistics
    times = []
    retry_stats = {"total_retries": 0, "retried_successfully": 0}
    start_time = time.time()
    
    for i, char in enumerate(remaining, 1):
        char_start = time.time()
        
        try:
            print(f"[{i}/{len(remaining)}] Processing: {char}", end=" ... ", flush=True)
            
            # Extract character information with retry
            info, attempts = extract_with_retry(char, max_retries=max_retries, retry_delay=retry_delay)
            
            if info is None:
                # All retries failed
                char_time = time.time() - char_start
                error_msg = f"Failed after {attempts} attempts"
                print(f"✗ FAILED ({char_time:.2f}s, {attempts} attempts)")
                new_failed[char] = {
                    "error": error_msg,
                    "attempts": attempts,
                    "timestamp": datetime.now().isoformat()
                }
                failed[char] = new_failed[char]
                
                # Save progress even on failure
                if i % 10 == 0:
                    progress["processed"] = processed
                    progress["failed"] = {**failed, **new_failed}
                    save_progress(progress)
                
                # Still rate limit on failure
                if i < len(remaining):
                    time.sleep(rate_limit_seconds)
            else:
                # Success (possibly after retries)
                # Add index number to the result
                char_to_index = get_char_to_index_mapping()
                if char in char_to_index:
                    info['index'] = char_to_index[char]

                # Add zibiao index (from level lists) when available
                char_to_zibiao_index = get_char_to_zibiao_index_mapping()
                if char in char_to_zibiao_index:
                    info['zibiao_index'] = char_to_zibiao_index[char]
                
                results[char] = info
                processed[char] = info
                
                char_time = time.time() - char_start
                times.append(char_time)
                avg_time = sum(times) / len(times)
                remaining_count = len(remaining) - i
                estimated_remaining = timedelta(seconds=int(avg_time * remaining_count))
                
                retry_info = ""
                if attempts > 1:
                    retry_info = f" (retry {attempts}/{max_retries})"
                    retry_stats["total_retries"] += attempts - 1
                    retry_stats["retried_successfully"] += 1
                
                print(f"✓ ({char_time:.2f}s{retry_info}) | Avg: {avg_time:.2f}s | Est. remaining: {estimated_remaining}")
                
                # Save progress every 10 characters
                if i % 10 == 0:
                    progress["processed"] = processed
                    progress["failed"] = {**failed, **new_failed}
                    save_progress(progress)
                    save_results(results)
                    print(f"  → Progress saved ({i}/{len(remaining)} complete)")
                
                # Rate limiting
                if i < len(remaining):  # Don't wait after last character
                    time.sleep(rate_limit_seconds)
                
        except KeyboardInterrupt:
            print(f"\n\nInterrupted by user. Saving progress...")
            progress["processed"] = processed
            progress["failed"] = {**failed, **new_failed}
            save_progress(progress)
            save_results(results)
            print(f"Progress saved. Processed {len(processed)} characters.")
            sys.exit(0)
    
    # Final save
    progress["processed"] = processed
    progress["failed"] = {**failed, **new_failed}
    save_progress(progress)
    save_results(results)
    
    # Calculate statistics
    total_time = time.time() - start_time
    avg_time = sum(times) / len(times) if times else 0
    min_time = min(times) if times else 0
    max_time = max(times) if times else 0
    
    stats = {
        "total": len(characters),
        "processed": len(processed),
        "failed": len(failed),
        "new_processed": len([c for c in remaining if c in processed]),
        "new_failed": len(new_failed),
        "retry_stats": retry_stats,
        "timing": {
            "total_time_seconds": total_time,
            "total_time_formatted": str(timedelta(seconds=int(total_time))),
            "average_time_per_character": avg_time,
            "min_time": min_time,
            "max_time": max_time,
            "characters_processed": len(times)
        },
        "results": results
    }
    
    return stats


def extract_worker(char: str, 
                   rate_limiter: RateLimiter,
                   progress_lock: threading.Lock,
                   results: Dict[str, Any],
                   processed: Dict[str, Any],
                   failed: Dict[str, Any],
                   new_failed: Dict[str, Any],
                   times: List[float],
                   retry_stats: Dict[str, int],
                   max_retries: int,
                   retry_delay: float,
                   counter: Dict[str, int],
                   total_count: int) -> Tuple[str, Optional[Dict[str, Any]], float, int]:
    """
    Worker function for parallel extraction.
    
    Returns:
        Tuple of (character, result, time_taken, attempts)
    """
    char_start = time.time()
    
    # Show start message
    with progress_lock:
        in_progress = counter.get('in_progress', 0)
        counter['in_progress'] = in_progress + 1
        print(f"[Worker] Starting: {char} (Active: {counter['in_progress']})", flush=True)
    
    try:
        # Acquire rate limiter token
        rate_limiter.acquire()
        
        # Extract with retry
        info, attempts = extract_with_retry(char, max_retries=max_retries, retry_delay=retry_delay)
        
        char_time = time.time() - char_start
        
        # Update shared state with lock
        with progress_lock:
            counter['completed'] += 1
            counter['in_progress'] = max(0, counter.get('in_progress', 0) - 1)
            i = counter['completed']
            
            if info is None:
                # Failed
                new_failed[char] = {
                    "error": f"Failed after {attempts} attempts",
                    "attempts": attempts,
                    "timestamp": datetime.now().isoformat()
                }
                failed[char] = new_failed[char]
                return char, None, char_time, attempts
            else:
                # Success
                # Add index number to the result
                char_to_index = get_char_to_index_mapping()
                if char in char_to_index:
                    info['index'] = char_to_index[char]

                # Add zibiao index (from level lists) when available
                char_to_zibiao_index = get_char_to_zibiao_index_mapping()
                if char in char_to_zibiao_index:
                    info['zibiao_index'] = char_to_zibiao_index[char]
                
                results[char] = info
                processed[char] = info
                times.append(char_time)
                
                if attempts > 1:
                    retry_stats["total_retries"] += attempts - 1
                    retry_stats["retried_successfully"] += 1
                
                return char, info, char_time, attempts
    except Exception as e:
        char_time = time.time() - char_start
        with progress_lock:
            counter['in_progress'] = max(0, counter.get('in_progress', 0) - 1)
            print(f"[Worker] Error processing {char}: {e}", flush=True)
        raise


def batch_extract_parallel(characters: List[str],
                          num_workers: int = 2,
                          global_rate_limit: float = 0.5,  # requests per second
                          test_mode: bool = False,
                          max_retries: int = 3,
                          retry_delay: float = 2.0,
                          overwrite: bool = False) -> Dict[str, Any]:
    """
    Extract information for a list of characters using parallel processing.
    
    Args:
        characters: List of characters to extract
        num_workers: Number of parallel workers
        global_rate_limit: Global rate limit in requests per second
        test_mode: If True, only process first 100 characters
        max_retries: Maximum retry attempts
        retry_delay: Delay between retries
        overwrite: If True, reprocess and overwrite existing entries
        
    Returns:
        Dictionary with results, timing, and statistics
    """
    if test_mode:
        characters = characters[:100]
        print(f"TEST MODE: Processing first {len(characters)} characters")
    
    # Load previous progress
    progress = load_progress()
    processed = progress.get("processed", {})
    failed = progress.get("failed", {})

    # Also treat existing OUTPUT_JSON entries as processed (skip by default)
    existing_output = load_existing_output()
    if existing_output:
        for ch, entry in existing_output.items():
            if ch not in processed and isinstance(entry, dict):
                processed[ch] = entry
    
    # Filter out already processed characters (unless overwrite is enabled)
    if overwrite:
        remaining = [c for c in characters if c not in failed]
        if processed:
            print(f"OVERWRITE MODE: Will reprocess {len([c for c in characters if c in processed])} existing entries")
    else:
        remaining = [c for c in characters if c not in processed and c not in failed]
    
    if not remaining:
        print("All characters have already been processed!")
        return {
            "total": len(characters),
            "processed": len(processed),
            "failed": len(failed),
            "results": processed
        }
    
    print(f"Total characters to process: {len(characters)}")
    print(f"Already processed: {len(processed)}")
    print(f"Already failed: {len(failed)}")
    print(f"Remaining: {len(remaining)}")
    print(f"Parallel workers: {num_workers}")
    print(f"Global rate limit: {global_rate_limit} requests/second")
    print(f"Max retries: {max_retries}")
    print(f"Retry delay: {retry_delay} seconds")
    print("=" * 70)
    
    # Shared state
    results = processed.copy()
    # Ensure all loaded results have index fields
    char_to_index = get_char_to_index_mapping()
    char_to_zibiao_index = get_char_to_zibiao_index_mapping()
    for char, data in results.items():
        if 'index' not in data and char in char_to_index:
            data['index'] = char_to_index[char]
        if 'zibiao_index' not in data and char in char_to_zibiao_index:
            data['zibiao_index'] = char_to_zibiao_index[char]
    
    new_failed = {}
    times = []
    retry_stats = {"total_retries": 0, "retried_successfully": 0}
    progress_lock = threading.Lock()
    rate_limiter = RateLimiter(global_rate_limit)
    counter = {"completed": 0, "in_progress": 0}
    
    start_time = time.time()
    
    try:
        with ThreadPoolExecutor(max_workers=num_workers) as executor:
            # Submit all tasks
            futures = {
                executor.submit(
                    extract_worker,
                    char=char,
                    rate_limiter=rate_limiter,
                    progress_lock=progress_lock,
                    results=results,
                    processed=processed,
                    failed=failed,
                    new_failed=new_failed,
                    times=times,
                    retry_stats=retry_stats,
                    max_retries=max_retries,
                    retry_delay=retry_delay,
                    counter=counter,
                    total_count=len(remaining)
                ): char for char in remaining
            }
            
            # Process completed tasks with real-time progress display
            print(f"\nStarting parallel extraction with {num_workers} workers...\n", flush=True)
            
            for future in as_completed(futures):
                char = futures[future]
                try:
                    char, info, char_time, attempts = future.result()
                    
                    with progress_lock:
                        i = counter['completed']
                        active = counter.get('in_progress', 0)
                        avg_time = sum(times) / len(times) if times else 0
                        remaining_count = len(remaining) - i
                        estimated_remaining = timedelta(seconds=int(avg_time * remaining_count)) if avg_time > 0 else timedelta(0)
                        
                        # Real-time progress display with flush
                        if info is None:
                            status_msg = f"[{i}/{len(remaining)}] {char}: ✗ FAILED ({char_time:.2f}s, {attempts} attempts) [Active: {active}]"
                        else:
                            retry_info = ""
                            if attempts > 1:
                                retry_info = f" (retry {attempts}/{max_retries})"
                            status_msg = f"[{i}/{len(remaining)}] {char}: ✓ ({char_time:.2f}s{retry_info}) | Avg: {avg_time:.2f}s | Est. remaining: {estimated_remaining} [Active: {active}]"
                        
                        print(status_msg, flush=True)
                        
                        # Save progress every 10 characters
                        if i % 10 == 0:
                            progress["processed"] = processed
                            progress["failed"] = {**failed, **new_failed}
                            save_progress(progress)
                            save_results(results)
                            print(f"  → Progress saved ({i}/{len(remaining)} complete)", flush=True)
                            
                except KeyboardInterrupt:
                    print(f"\n\nInterrupted by user. Saving progress...")
                    progress["processed"] = processed
                    progress["failed"] = {**failed, **new_failed}
                    save_progress(progress)
                    save_results(results)
                    print(f"Progress saved. Processed {len(processed)} characters.")
                    sys.exit(0)
                except Exception as e:
                    print(f"\nError processing {char}: {e}")
                    import traceback
                    traceback.print_exc()
    
    except KeyboardInterrupt:
        print(f"\n\nInterrupted by user. Saving progress...")
        progress["processed"] = processed
        progress["failed"] = {**failed, **new_failed}
        save_progress(progress)
        save_results(results)
        print(f"Progress saved. Processed {len(processed)} characters.")
        sys.exit(0)
    
    # Final save
    progress["processed"] = processed
    progress["failed"] = {**failed, **new_failed}
    save_progress(progress)
    save_results(results)
    
    # Calculate statistics
    total_time = time.time() - start_time
    avg_time = sum(times) / len(times) if times else 0
    min_time = min(times) if times else 0
    max_time = max(times) if times else 0
    
    stats = {
        "total": len(characters),
        "processed": len(processed),
        "failed": len(failed),
        "new_processed": len([c for c in remaining if c in processed]),
        "new_failed": len(new_failed),
        "retry_stats": retry_stats,
        "timing": {
            "total_time_seconds": total_time,
            "total_time_formatted": str(timedelta(seconds=int(total_time))),
            "average_time_per_character": avg_time,
            "min_time": min_time,
            "max_time": max_time,
            "characters_processed": len(times)
        },
        "results": results
    }
    
    return stats


def main():
    """Main function."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Batch extract character information from HWXNet')
    parser.add_argument('--test', action='store_true', 
                       help='Test mode: only process first 100 characters')
    parser.add_argument('--limit', type=int, default=None,
                       help='Limit number of characters to process')
    parser.add_argument('--rate-limit', type=float, default=1.5,
                       help='Rate limit in seconds between requests (default: 1.5)')
    parser.add_argument('--max-retries', type=int, default=3,
                       help='Maximum number of retry attempts for failed requests (default: 3)')
    parser.add_argument('--retry-delay', type=float, default=2.0,
                       help='Seconds to wait between retry attempts (default: 2.0)')
    parser.add_argument('--parallel', action='store_true',
                       help='Use parallel processing (ThreadPoolExecutor)')
    parser.add_argument('--workers', type=int, default=2,
                       help='Number of parallel workers (default: 2, only used with --parallel)')
    parser.add_argument('--global-rate-limit', type=float, default=0.5,
                       help='Global rate limit in requests per second (default: 0.5, only used with --parallel)')
    parser.add_argument('--resume', action='store_true',
                       help='Resume from previous progress')
    parser.add_argument('--overwrite', action='store_true',
                       help='Reprocess and overwrite existing entries')
    parser.add_argument('--characters-file', type=str, default=None,
                       help='Path to a text file (one character per line) to process instead of characters.json (relative paths are resolved from this script directory)')
    
    args = parser.parse_args()
    
    # Load characters
    if args.characters_file:
        characters_file_path = Path(args.characters_file)
        if not characters_file_path.is_absolute():
            characters_file_path = SCRIPT_DIR / characters_file_path
        print(f"Loading characters from: {characters_file_path} ...")
        characters = load_characters_from_txt(characters_file_path, limit=args.limit)
    else:
        print("Loading characters from characters.json...")
        characters = load_characters(limit=args.limit)
    print(f"Loaded {len(characters)} characters")
    print()
    
    # Run extraction (parallel or sequential)
    if args.parallel:
        stats = batch_extract_parallel(
            characters,
            num_workers=args.workers,
            global_rate_limit=args.global_rate_limit,
            test_mode=args.test,
            max_retries=args.max_retries,
            retry_delay=args.retry_delay,
            overwrite=args.overwrite
        )
    else:
        stats = batch_extract(
            characters, 
            rate_limit_seconds=args.rate_limit,
            test_mode=args.test,
            max_retries=args.max_retries,
            retry_delay=args.retry_delay,
            overwrite=args.overwrite
        )
    
    # Print summary
    print()
    print("=" * 70)
    print("EXTRACTION SUMMARY")
    print("=" * 70)
    print(f"Total characters: {stats['total']}")
    print(f"Successfully processed: {stats['processed']}")
    print(f"Failed: {stats['failed']}")
    if stats.get('retry_stats'):
        retry_stats = stats['retry_stats']
        if retry_stats['total_retries'] > 0:
            print(f"Retry statistics:")
            print(f"  Total retries: {retry_stats['total_retries']}")
            print(f"  Successfully retried: {retry_stats['retried_successfully']}")
    if stats['timing']['characters_processed'] > 0:
        print()
        print("Timing Statistics:")
        print(f"  Total time: {stats['timing']['total_time_formatted']}")
        print(f"  Average per character: {stats['timing']['average_time_per_character']:.2f} seconds")
        print(f"  Min time: {stats['timing']['min_time']:.2f} seconds")
        print(f"  Max time: {stats['timing']['max_time']:.2f} seconds")
        print()
        
        # Estimate for full 3000 characters
        if args.test:
            avg = stats['timing']['average_time_per_character']
            rate_limit = args.rate_limit
            total_time_per_char = avg + rate_limit
            estimated_total = total_time_per_char * 3000
            estimated_hours = estimated_total / 3600
            
            print("Estimated time for all 3000 characters:")
            print(f"  Per character (avg + rate limit): {total_time_per_char:.2f} seconds")
            print(f"  Total estimated time: {timedelta(seconds=int(estimated_total))}")
            print(f"  Total estimated hours: {estimated_hours:.1f} hours")
    
    print()
    print(f"Results saved to: {OUTPUT_JSON}")
    print(f"Progress saved to: {PROGRESS_JSON}")


if __name__ == "__main__":
    main()
