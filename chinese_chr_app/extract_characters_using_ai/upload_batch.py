#!/usr/bin/env python3
"""
Upload JSONL file to OpenAI Batch API and manage batch processing.

This script:
1. Uploads a JSONL file to create a batch
2. Monitors batch status
3. Retrieves results when complete
4. Saves results to a file

Requirements:
    pip install openai

Usage:
    python3 upload_batch.py \
      --jsonl jsonl/requests.jsonl \
      --output jsonl/results.jsonl \
      --poll_interval 60
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


def add_batch_to_file(
    batch_ids_file: Path,
    file: str,
    file_id: str,
    batch_id: str,
    timestamp: Optional[int] = None
):
    """Add a new batch to batch_ids.json with CREATED state."""
    if timestamp is None:
        timestamp = int(time.time())
    
    data = load_batch_ids_file(batch_ids_file)
    
    # Check if batch already exists
    for batch in data.get("batches", []):
        if batch.get("batch_id") == batch_id:
            # Batch already exists, don't add again
            return
    
    # Add new batch
    batch_info = {
        "file": str(file),
        "file_id": file_id,
        "batch_id": batch_id,
        "state": "CREATED",
        "created_at": timestamp,
        "state_history": [
            {
                "state": "CREATED",
                "timestamp": timestamp
            }
        ]
    }
    
    data["batches"].append(batch_info)
    data["updated_at"] = timestamp
    
    # Set created_at if this is the first batch
    if not data.get("created_at"):
        data["created_at"] = timestamp
    
    with batch_ids_file.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def upload_file(client: OpenAI, file_path: Path) -> str:
    """
    Upload a file to OpenAI and return the file ID.
    """
    print(f"📤 Uploading file: {file_path}")
    with open(file_path, "rb") as f:
        file = client.files.create(file=f, purpose="batch")
    print(f"✅ File uploaded successfully. File ID: {file.id}")
    return file.id


def create_batch(client: OpenAI, file_id: str, metadata: Optional[dict] = None) -> str:
    """
    Create a batch from an uploaded file and return the batch ID.
    """
    print(f"🔄 Creating batch from file ID: {file_id}")
    batch_params = {
        "input_file_id": file_id,
        "endpoint": "/v1/responses",
        "completion_window": "24h",
    }
    if metadata:
        batch_params["metadata"] = metadata

    batch = client.batches.create(**batch_params)
    print(f"✅ Batch created successfully. Batch ID: {batch.id}")
    return batch.id


def get_batch_status(client: OpenAI, batch_id: str) -> dict:
    """
    Get the current status of a batch.
    """
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
    max_wait_time: Optional[int] = None,
) -> dict:
    """
    Poll batch status until it's complete or failed.
    Returns the final batch status.
    """
    start_time = time.time()
    print(f"\n⏳ Polling batch status (ID: {batch_id})...")
    print(f"   Poll interval: {poll_interval} seconds")
    if max_wait_time:
        print(f"   Max wait time: {max_wait_time} seconds")

    while True:
        status = get_batch_status(client, batch_id)
        elapsed = int(time.time() - start_time)

        print(
            f"\n[{elapsed}s] Status: {status['status']} | "
            f"Completed: {status['completed']}/{status['total_requests']} | "
            f"Failed: {status['failed']}"
        )

        if status["status"] in ("completed", "failed", "expired", "cancelled"):
            print(f"\n✅ Batch finished with status: {status['status']}")
            return status

        if max_wait_time and elapsed >= max_wait_time:
            print(f"\n⏰ Max wait time reached ({max_wait_time}s)")
            return status

        time.sleep(poll_interval)


def download_file(client: OpenAI, file_id: str, output_path: Path):
    """
    Download a file from OpenAI and save it locally.
    """
    print(f"📥 Downloading file ID: {file_id} to {output_path}")
    file_content = client.files.content(file_id)
    output_path.write_bytes(file_content.read())
    print(f"✅ File downloaded successfully")


def download_results(
    client: OpenAI,
    batch_status: dict,
    output_path: Path,
    error_path: Optional[Path] = None,
):
    """
    Download batch results and optionally error file.
    """
    if batch_status["output_file_id"]:
        download_file(client, batch_status["output_file_id"], output_path)

    if batch_status["error_file_id"] and error_path:
        download_file(client, batch_status["error_file_id"], error_path)
    elif batch_status["error_file_id"]:
        error_path = output_path.parent / f"{output_path.stem}_errors.jsonl"
        download_file(client, batch_status["error_file_id"], error_path)


def main():
    parser = argparse.ArgumentParser(
        description="Upload JSONL file to OpenAI Batch API and manage processing."
    )
    parser.add_argument(
        "--jsonl",
        default="jsonl/requests.jsonl",
        type=Path,
        help="Path to input JSONL file (default: jsonl/requests.jsonl)",
    )
    parser.add_argument(
        "--output",
        default="jsonl/results.jsonl",
        type=Path,
        help="Path to save results JSONL file (default: jsonl/results.jsonl)",
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
        help="Don't poll for completion, just create the batch and exit",
    )
    parser.add_argument(
        "--batch_id",
        type=str,
        default=None,
        help="Existing batch ID to check status (skip upload/create)",
    )
    parser.add_argument(
        "--api_key",
        type=str,
        default=None,
        help="OpenAI API key (default: from OPENAI_API_KEY env var)",
    )
    parser.add_argument(
        "--metadata",
        type=str,
        default=None,
        help="JSON metadata to attach to batch (e.g., '{\"description\": \"Chinese chars\"}')",
    )

    args = parser.parse_args()

    # Initialize OpenAI client
    client = OpenAI(api_key=args.api_key)

    # Handle existing batch ID
    if args.batch_id:
        batch_ids_file = args.output.parent / "batch_ids.json"
        print(f"📊 Checking status of existing batch: {args.batch_id}")
        batch_status = get_batch_status(client, args.batch_id)
        print(json.dumps(batch_status, indent=2))

        if batch_status["status"] in ("completed", "failed", "expired", "cancelled"):
            if batch_status["status"] == "completed":
                update_batch_state(batch_ids_file, args.batch_id, "COMPLETED")
            if batch_status["output_file_id"]:
                download_results(client, batch_status, args.output, args.errors)
                if batch_status["status"] == "completed":
                    update_batch_state(batch_ids_file, args.batch_id, "RESULT RETRIEVED")
        elif not args.no_poll:
            batch_status = poll_batch_status(
                client, args.batch_id, args.poll_interval, args.max_wait_time
            )
            if batch_status["status"] == "completed":
                update_batch_state(batch_ids_file, args.batch_id, "COMPLETED")
                download_results(client, batch_status, args.output, args.errors)
                update_batch_state(batch_ids_file, args.batch_id, "RESULT RETRIEVED")
        return

    # Create output directory if it doesn't exist
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if args.errors:
        args.errors.parent.mkdir(parents=True, exist_ok=True)

    # Validate input file
    if not args.jsonl.exists():
        raise SystemExit(f"Input file not found: {args.jsonl}")

    # Parse metadata if provided
    metadata = None
    if args.metadata:
        try:
            metadata = json.loads(args.metadata)
        except json.JSONDecodeError as e:
            raise SystemExit(f"Invalid JSON metadata: {e}")

    # Upload file
    file_id = upload_file(client, args.jsonl)

    # Create batch
    batch_id = create_batch(client, file_id, metadata)

    print(f"\n📋 Batch Information:")
    print(f"   Batch ID: {batch_id}")
    print(f"   File ID: {file_id}")
    print(f"   Save this batch ID to check status later:")
    print(f"   python3 upload_batch.py --batch_id {batch_id}")

    # Save batch to batch_ids.json with CREATED state
    batch_ids_file = args.output.parent / "batch_ids.json"
    add_batch_to_file(batch_ids_file, str(args.jsonl), file_id, batch_id)
    
    data = load_batch_ids_file(batch_ids_file)
    print(f"\n💾 Batch saved to: {batch_ids_file.resolve()}")
    print(f"   State: CREATED")
    print(f"   Total batches in file: {len(data.get('batches', []))}")

    if args.no_poll:
        print("\n⏸️  Skipping polling (--no_poll flag set)")
        return

    # Poll for completion
    batch_status = poll_batch_status(
        client, batch_id, args.poll_interval, args.max_wait_time
    )

    # Update state to COMPLETED if batch finished successfully
    batch_ids_file = args.output.parent / "batch_ids.json"
    if batch_status["status"] == "completed":
        update_batch_state(batch_ids_file, batch_id, "COMPLETED")
        print(f"📝 Batch state updated to: COMPLETED")
        
        # Download results
        download_results(client, batch_status, args.output, args.errors)
        
        # Update state to RESULT RETRIEVED after downloading
        update_batch_state(batch_ids_file, batch_id, "RESULT RETRIEVED")
        print(f"📝 Batch state updated to: RESULT RETRIEVED")
        
        print(f"\n✅ Results saved to: {args.output.resolve()}")
        if args.errors and batch_status["error_file_id"]:
            print(f"✅ Errors saved to: {args.errors.resolve()}")
    else:
        print(f"\n⚠️  Batch did not complete successfully. Status: {batch_status['status']}")
        if batch_status["error_file_id"]:
            error_path = args.errors or (args.output.parent / f"{args.output.stem}_errors.jsonl")
            download_file(client, batch_status["error_file_id"], error_path)
            print(f"📥 Error file saved to: {error_path.resolve()}")


if __name__ == "__main__":
    main()
