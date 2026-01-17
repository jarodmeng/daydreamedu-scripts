#!/usr/bin/env python3
"""
Simple file upload script - minimal code to test uploads.
"""
import os
import sys
from pathlib import Path

try:
    from openai import OpenAI
except ImportError:
    print("Error: openai package not installed")
    sys.exit(1)

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 upload_file_simple.py <jsonl_file>")
        sys.exit(1)
    
    file_path = Path(sys.argv[1])
    if not file_path.exists():
        print(f"Error: File not found: {file_path}")
        sys.exit(1)
    
    print(f"Uploading: {file_path.name} ({file_path.stat().st_size / (1024*1024):.1f} MB)")
    
    client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
    
    try:
        with open(file_path, "rb") as f:
            print("Calling client.files.create()...")
            file = client.files.create(file=f, purpose="batch")
        print(f"✅ Upload successful!")
        print(f"   File ID: {file.id}")
        
        # Create batch
        print("\nCreating batch...")
        batch = client.batches.create(
            input_file_id=file.id,
            endpoint="/v1/responses",
            completion_window="24h"
        )
        print(f"✅ Batch created!")
        print(f"   Batch ID: {batch.id}")
        print(f"   Status: {batch.status}")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
