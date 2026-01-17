#!/usr/bin/env python3
"""
List recent batches from OpenAI Batch API.

This script retrieves and displays recent batch jobs, which is useful
for finding batch IDs when you've already uploaded files.

Usage:
    python3 list_batches.py --limit 10
"""

import argparse
from datetime import datetime
from pathlib import Path

try:
    from openai import OpenAI
except ImportError:
    raise SystemExit(
        "Missing dependency: openai\n"
        "Install it with: pip install openai\n"
    )


def format_timestamp(ts: int) -> str:
    """Format Unix timestamp to readable date."""
    if ts:
        return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")
    return "N/A"


def list_batches(client: OpenAI, limit: int = 10, status_filter: str = None):
    """
    List recent batches from OpenAI.
    """
    print(f"📋 Fetching recent batches (limit: {limit})...\n")
    
    try:
        batches = client.batches.list(limit=limit)
    except Exception as e:
        raise SystemExit(f"Error listing batches: {e}")
    
    if not batches.data:
        print("No batches found.")
        return []
    
    # Filter by status if requested
    if status_filter:
        batches.data = [b for b in batches.data if b.status == status_filter]
    
    if not batches.data:
        print(f"No batches found with status: {status_filter}")
        return []
    
    # Group by status
    by_status = {}
    for batch in batches.data:
        status = batch.status
        if status not in by_status:
            by_status[status] = []
        by_status[status].append(batch)
    
    # Print batches grouped by status
    batch_list = []
    for status in sorted(by_status.keys()):
        status_batches = by_status[status]
        status_icon = {
            'validating': '🔍',
            'in_progress': '⏳',
            'finalizing': '🏁',
            'completed': '✅',
            'failed': '❌',
            'expired': '⏰',
            'cancelled': '🚫',
        }.get(status, '📋')
        
        print(f"\n{status_icon} {status.upper()} ({len(status_batches)} batch(es))")
        print(f"{'='*80}")
        print(f"{'Batch ID':<40} {'Status':<15} {'Created':<20} {'Requests':<10}")
        print(f"{'='*80}")
        
        for batch in status_batches:
            batch_id = batch.id
            created_at = format_timestamp(batch.created_at) if hasattr(batch, 'created_at') else "N/A"
            
            # Get request counts
            total = batch.request_counts.total if hasattr(batch, 'request_counts') else 0
            completed = batch.request_counts.completed if hasattr(batch, 'request_counts') else 0
            failed = batch.request_counts.failed if hasattr(batch, 'request_counts') else 0
            
            requests_info = f"{completed}/{total}"
            if failed > 0:
                requests_info += f" ({failed} failed)"
            
            print(f"{batch_id:<40} {status:<15} {created_at:<20} {requests_info:<10}")
            
            batch_list.append({
                'id': batch_id,
                'status': status,
                'created_at': created_at,
                'total': total,
                'completed': completed,
                'failed': failed,
            })
    
    print(f"\n{'='*80}")
    print(f"\n📊 Summary: Found {len(batch_list)} batch(es) total")
    for status, count in sorted(by_status.items()):
        print(f"   {status}: {count}")
    
    return batch_list


def main():
    parser = argparse.ArgumentParser(
        description="List recent batches from OpenAI Batch API."
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Number of batches to retrieve (default: 10)",
    )
    parser.add_argument(
        "--status",
        type=str,
        default=None,
        help="Filter by status (e.g., in_progress, completed, validating, finalizing)",
    )
    parser.add_argument(
        "--api_key",
        type=str,
        default=None,
        help="OpenAI API key (default: from OPENAI_API_KEY env var)",
    )
    
    args = parser.parse_args()
    
    # Initialize OpenAI client
    client = OpenAI(api_key=args.api_key)
    
    # List batches
    batches = list_batches(client, args.limit, args.status)
    
    # Show batch IDs for easy copying
    if batches:
        print(f"\n📋 Batch IDs (for use with upload_batch.py --batch_id):")
        for batch in batches:
            print(f"   {batch['id']} - {batch['status']} ({batch['completed']}/{batch['total']} completed)")


if __name__ == "__main__":
    main()
