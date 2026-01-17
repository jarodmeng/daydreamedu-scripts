#!/usr/bin/env python3
"""
Poll a single batch ID and download its results.

This script polls a single batch job until completion and downloads
the results to a specified output file.

Usage:
    python3 poll_and_merge_batches.py \
      --batch_id batch_123 \
      --output jsonl/results_003.jsonl
"""

import argparse
import json
import time
from pathlib import Path
from typing import Optional, Literal

try:
    from openai import OpenAI
except ImportError:
    raise SystemExit(
        "Missing dependency: openai\n"
        "Install it with: pip install openai\n"
    )


# Batch state management
BATCH_STATE = Literal["CREATED", "COMPLETED", "RESULT RETRIEVED"]


def load_batch_ids_file(batch_ids_file: Path) -> dict:
    """Load batch_ids.json file, migrating old format if needed."""
    if not batch_ids_file.exists():
        return {
            "created_at": int(time.time()),
            "updated_at": int(time.time()),
            "batches": []
        }
    
    try:
        with batch_ids_file.open("r", encoding="utf-8") as f:
            data = json.load(f)
        
        # Migrate old format to new format
        if "batches" in data:
            for batch in data.get("batches", []):
                # If batch doesn't have state, migrate it
                if "state" not in batch:
                    batch["state"] = "CREATED"
                    batch["state_history"] = [
                        {
                            "state": "CREATED",
                            "timestamp": batch.get("created_at", int(time.time()))
                        }
                    ]
                # If batch has state but no state_history, create it
                elif "state_history" not in batch:
                    batch["state_history"] = [
                        {
                            "state": batch["state"],
                            "timestamp": batch.get("created_at", int(time.time()))
                        }
                    ]
        
        return data
    except (json.JSONDecodeError, KeyError):
        # If file is corrupted, return empty structure
        return {
            "created_at": int(time.time()),
            "updated_at": int(time.time()),
            "batches": []
        }


def update_batch_state(
    batch_ids_file: Path,
    batch_id: str,
    new_state: BATCH_STATE,
    timestamp: Optional[int] = None
) -> bool:
    """
    Update the state of a batch in batch_ids.json.
    Returns True if batch was found and updated, False otherwise.
    """
    if timestamp is None:
        timestamp = int(time.time())
    
    data = load_batch_ids_file(batch_ids_file)
    
    # Find the batch
    batch_found = False
    for batch in data.get("batches", []):
        if batch.get("batch_id") == batch_id:
            batch_found = True
            old_state = batch.get("state", "CREATED")
            
            # Only update if state actually changed
            if old_state != new_state:
                batch["state"] = new_state
                
                # Initialize state_history if it doesn't exist
                if "state_history" not in batch:
                    batch["state_history"] = []
                
                # Add new state entry
                batch["state_history"].append({
                    "state": new_state,
                    "timestamp": timestamp
                })
            
            break
    
    if batch_found:
        data["updated_at"] = timestamp
        with batch_ids_file.open("w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        return True
    
    return False


def get_batch_status(client: OpenAI, batch_id: str) -> dict:
    """Get the current status of a batch."""
    batch = client.batches.retrieve(batch_id)
    return {
        "id": batch.id,
        "status": batch.status,
        "total_requests": batch.request_counts.total if hasattr(batch, "request_counts") else None,
        "completed": batch.request_counts.completed if hasattr(batch, "request_counts") else None,
        "failed": batch.request_counts.failed if hasattr(batch, "request_counts") else None,
        "output_file_id": batch.output_file_id if hasattr(batch, "output_file_id") else None,
        "error_file_id": batch.error_file_id if hasattr(batch, "error_file_id") else None,
    }


def poll_batch_status(
    client: OpenAI,
    batch_id: str,
    poll_interval: int = 60,
    max_wait_time: int = None,
) -> dict:
    """Poll batch status until it's complete or failed."""
    start_time = time.time()
    print(f"\n⏳ Polling batch: {batch_id}")
    print(f"   Poll interval: {poll_interval} seconds")

    while True:
        status = get_batch_status(client, batch_id)
        elapsed = int(time.time() - start_time)

        print(
            f"[{elapsed}s] Status: {status['status']} | "
            f"Completed: {status['completed']}/{status['total_requests']} | "
            f"Failed: {status['failed']}"
        )

        if status["status"] in ("completed", "failed", "expired", "cancelled"):
            print(f"✅ Batch finished with status: {status['status']}")
            return status

        if max_wait_time and elapsed >= max_wait_time:
            print(f"⏰ Max wait time reached ({max_wait_time}s)")
            return status

        time.sleep(poll_interval)


def download_file(client: OpenAI, file_id: str, output_path: Path):
    """Download a file from OpenAI and save it locally."""
    print(f"📥 Downloading file ID: {file_id} to {output_path.name}")
    file_content = client.files.content(file_id)
    output_path.write_bytes(file_content.read())
    print(f"✅ File downloaded successfully")


def main():
    parser = argparse.ArgumentParser(
        description="Poll a single batch ID and download its results."
    )
    parser.add_argument(
        "--batch_id",
        type=str,
        required=True,
        help="Batch ID to poll (e.g., batch_123)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Path to save results JSONL file (e.g., jsonl/results_003.jsonl)",
    )
    parser.add_argument(
        "--errors",
        type=Path,
        help="Path to save errors JSONL file (optional)",
    )
    parser.add_argument(
        "--poll_interval",
        type=int,
        default=60,
        help="Seconds between status checks (default: 60)",
    )
    parser.add_argument(
        "--max_wait_time",
        type=int,
        default=None,
        help="Maximum seconds to wait for batch completion (default: unlimited)",
    )
    parser.add_argument(
        "--no_poll",
        action="store_true",
        help="Don't poll, just check current status and download if complete",
    )
    parser.add_argument(
        "--api_key",
        type=str,
        default=None,
        help="OpenAI API key (default: from OPENAI_API_KEY env var)",
    )
    parser.add_argument(
        "--batch_ids_file",
        type=Path,
        default=None,
        help="Path to batch_ids.json file for state tracking (default: output directory)",
    )

    args = parser.parse_args()

    # Initialize OpenAI client
    client = OpenAI(api_key=args.api_key)

    # Create output directory
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if args.errors:
        args.errors.parent.mkdir(parents=True, exist_ok=True)

    # Determine batch_ids.json location
    batch_ids_file = args.batch_ids_file
    if batch_ids_file is None:
        batch_ids_file = args.output.parent / "batch_ids.json"

    print(f"📋 Processing batch: {args.batch_id}")
    print(f"{'='*60}")

    if args.no_poll:
        # Just check status
        batch_status = get_batch_status(client, args.batch_id)
        print(f"Status: {batch_status['status']}")
    else:
        # Poll until completion
        batch_status = poll_batch_status(
            client, args.batch_id, args.poll_interval, args.max_wait_time
        )

    # Download results if completed
    if batch_status["status"] == "completed":
        # Update state to COMPLETED
        if batch_ids_file.exists():
            update_batch_state(batch_ids_file, args.batch_id, "COMPLETED")
            print(f"📝 Batch state updated to: COMPLETED")

        if batch_status.get("output_file_id"):
            download_file(client, batch_status["output_file_id"], args.output)

        if batch_status.get("error_file_id"):
            error_path = args.errors or (args.output.parent / f"{args.output.stem}_errors.jsonl")
            download_file(client, batch_status["error_file_id"], error_path)

        # Update state to RESULT RETRIEVED after downloading
        if batch_ids_file.exists():
            update_batch_state(batch_ids_file, args.batch_id, "RESULT RETRIEVED")
            print(f"📝 Batch state updated to: RESULT RETRIEVED")

        print(f"✅ Results saved to: {args.output.resolve()}")
    else:
        print(f"⚠️  Batch did not complete successfully. Status: {batch_status['status']}")
        if batch_status.get("error_file_id"):
            error_path = args.errors or (args.output.parent / f"{args.output.stem}_errors.jsonl")
            download_file(client, batch_status["error_file_id"], error_path)


if __name__ == "__main__":
    main()
