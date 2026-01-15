#!/usr/bin/env python3
"""
Summarize token usage from OpenAI Batch API results.jsonl file.

This script parses the results.jsonl file and extracts token usage statistics
for each request, providing a summary of total tokens used for processing.

Usage:
    python3 summarize_tokens.py --input jsonl/results.jsonl
"""

import argparse
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple


# Model pricing per 1M tokens (input, output, cached_input)
# Format: (input_price, output_price, cached_input_price)
# Note: These are STANDARD API prices. Batch API gets 50% discount.
MODEL_PRICING = {
    'gpt-5-mini': (0.25, 2.00, 0.025),
    'gpt-5-mini-2025-08-07': (0.25, 2.00, 0.025),
    'gpt-4o-mini': (0.15, 0.60, 0.015),
    'gpt-4o': (2.50, 10.00, 0.25),
    'gpt-4-turbo': (10.00, 30.00, 1.00),
    'gpt-4': (30.00, 60.00, 3.00),
    'gpt-3.5-turbo': (0.50, 1.50, 0.05),
}

# Batch API discount: 50% off standard pricing
BATCH_DISCOUNT = 0.5


def get_model_pricing(model_name: str) -> Tuple[float, float, float]:
    """
    Get pricing for a model. Returns (input_price, output_price, cached_input_price) per 1M tokens.
    If model not found, returns None values.
    """
    # Try exact match first
    if model_name in MODEL_PRICING:
        return MODEL_PRICING[model_name]
    
    # Try matching by prefix (e.g., "gpt-5-mini-2025-08-07" -> "gpt-5-mini")
    for key, pricing in MODEL_PRICING.items():
        if model_name.startswith(key) or key in model_name:
            return pricing
    
    return None, None, None


def extract_model_name(result: Dict) -> Optional[str]:
    """Extract model name from a result line."""
    response = result.get('response', {})
    body = response.get('body', {})
    model = body.get('model', '')
    
    if not model:
        model = response.get('model', '')
    if not model:
        model = result.get('model', '')
    
    return model if model else None


def extract_token_usage(result: Dict) -> Optional[Dict[str, int]]:
    """
    Extract token usage from a result line.
    Returns dict with token usage information or None.
    """
    # Token usage is in response.body.usage
    response = result.get('response', {})
    body = response.get('body', {})
    usage = body.get('usage', {})
    
    if not usage:
        # Try alternative locations
        usage = response.get('usage', {})
        if not usage:
            usage = result.get('usage', {})
    
    if usage:
        # OpenAI Batch API uses input_tokens and output_tokens
        input_tokens = usage.get('input_tokens', usage.get('prompt_tokens', 0))
        output_tokens = usage.get('output_tokens', usage.get('completion_tokens', 0))
        total_tokens = usage.get('total_tokens', input_tokens + output_tokens)
        
        # Extract detailed token info if available
        input_details = usage.get('input_tokens_details', {})
        output_details = usage.get('output_tokens_details', {})
        cached_tokens = input_details.get('cached_tokens', 0)
        reasoning_tokens = output_details.get('reasoning_tokens', 0)
        
        return {
            'input_tokens': input_tokens,
            'output_tokens': output_tokens,
            'total_tokens': total_tokens,
            'cached_tokens': cached_tokens,
            'reasoning_tokens': reasoning_tokens,
            # Also include legacy field names for compatibility
            'prompt_tokens': input_tokens,
            'completion_tokens': output_tokens,
        }
    
    return None


def parse_results(input_path: Path) -> Dict:
    """
    Parse results.jsonl and extract token usage statistics.
    """
    if not input_path.exists():
        raise SystemExit(f"Input file not found: {input_path}")
    
    total_requests = 0
    successful_requests = 0
    failed_requests = 0
    requests_without_tokens = 0
    
    total_input_tokens = 0
    total_output_tokens = 0
    total_tokens = 0
    total_cached_tokens = 0
    total_reasoning_tokens = 0
    
    per_request_tokens: List[Dict[str, any]] = []
    detected_model = None
    
    print(f"📖 Reading results from: {input_path}")
    
    with open(input_path, 'r', encoding='utf-8') as f:
        for line_num, line in enumerate(f, 1):
            try:
                result = json.loads(line)
                total_requests += 1
                
                # Extract model name from first successful request
                if not detected_model:
                    model_name = extract_model_name(result)
                    if model_name:
                        detected_model = model_name
                
                custom_id = result.get('custom_id', f'line_{line_num}')
                
                # Check if request failed
                response = result.get('response', {})
                if response.get('status_code') and response.get('status_code') != 200:
                    failed_requests += 1
                    continue
                
                # Extract token usage
                token_usage = extract_token_usage(result)
                
                if token_usage:
                    successful_requests += 1
                    total_input_tokens += token_usage['input_tokens']
                    total_output_tokens += token_usage['output_tokens']
                    total_tokens += token_usage['total_tokens']
                    total_cached_tokens += token_usage.get('cached_tokens', 0)
                    total_reasoning_tokens += token_usage.get('reasoning_tokens', 0)
                    
                    per_request_tokens.append({
                        'custom_id': custom_id,
                        'input_tokens': token_usage['input_tokens'],
                        'output_tokens': token_usage['output_tokens'],
                        'total_tokens': token_usage['total_tokens'],
                        'cached_tokens': token_usage.get('cached_tokens', 0),
                        'reasoning_tokens': token_usage.get('reasoning_tokens', 0),
                    })
                else:
                    requests_without_tokens += 1
                    # Check if it's a successful request without token info
                    if response.get('body'):
                        successful_requests += 1
                    else:
                        failed_requests += 1
                        
            except json.JSONDecodeError as e:
                print(f"⚠️  Failed to parse line {line_num}: {e}")
                failed_requests += 1
    
    return {
        'total_requests': total_requests,
        'successful_requests': successful_requests,
        'failed_requests': failed_requests,
        'requests_without_tokens': requests_without_tokens,
        'total_input_tokens': total_input_tokens,
        'total_output_tokens': total_output_tokens,
        'total_tokens': total_tokens,
        'total_cached_tokens': total_cached_tokens,
        'total_reasoning_tokens': total_reasoning_tokens,
        'per_request_tokens': per_request_tokens,
        'model': detected_model,
    }


def format_number(num: int) -> str:
    """Format number with commas."""
    return f"{num:,}"


def print_summary(stats: Dict):
    """Print token usage summary."""
    print("\n" + "="*60)
    print("📊 Token Usage Summary")
    print("="*60)
    
    print(f"\n📋 Request Statistics:")
    print(f"   Total requests:        {format_number(stats['total_requests'])}")
    print(f"   Successful requests:   {format_number(stats['successful_requests'])}")
    print(f"   Failed requests:       {format_number(stats['failed_requests'])}")
    if stats['requests_without_tokens'] > 0:
        print(f"   Requests without tokens: {format_number(stats['requests_without_tokens'])}")
    
    if stats['total_tokens'] > 0:
        print(f"\n🔢 Token Usage:")
        print(f"   Input tokens:          {format_number(stats['total_input_tokens'])}")
        print(f"   Output tokens:         {format_number(stats['total_output_tokens'])}")
        print(f"   Total tokens:          {format_number(stats['total_tokens'])}")
        
        if stats['total_cached_tokens'] > 0:
            print(f"   Cached tokens:         {format_number(stats['total_cached_tokens'])}")
        if stats['total_reasoning_tokens'] > 0:
            print(f"   Reasoning tokens:      {format_number(stats['total_reasoning_tokens'])}")
        
        if stats['successful_requests'] > 0:
            avg_input = stats['total_input_tokens'] // stats['successful_requests']
            avg_output = stats['total_output_tokens'] // stats['successful_requests']
            avg_total = stats['total_tokens'] // stats['successful_requests']
            
            print(f"\n📈 Average per request:")
            print(f"   Avg input tokens:     {format_number(avg_input)}")
            print(f"   Avg output tokens:    {format_number(avg_output)}")
            print(f"   Avg total tokens:     {format_number(avg_total)}")
        
        # Cost estimation using detected model pricing
        # Since results.jsonl is from Batch API, apply 50% discount
        model_name = stats.get('model', 'unknown')
        input_price, output_price, cached_price = get_model_pricing(model_name)
        
        if input_price is not None and output_price is not None:
            # Apply Batch API discount (50% off)
            batch_input_price = input_price * BATCH_DISCOUNT
            batch_output_price = output_price * BATCH_DISCOUNT
            batch_cached_price = cached_price * BATCH_DISCOUNT
            
            # Calculate costs
            # Non-cached input tokens
            non_cached_input = stats['total_input_tokens'] - stats['total_cached_tokens']
            input_cost = (non_cached_input * batch_input_price + stats['total_cached_tokens'] * batch_cached_price) / 1_000_000
            output_cost = stats['total_output_tokens'] * batch_output_price / 1_000_000
            total_cost = input_cost + output_cost
            
            print(f"\n💰 Estimated Cost ({model_name} - Batch API, 50% discount):")
            if stats['total_cached_tokens'] > 0:
                print(f"   Input (non-cached): ${non_cached_input * batch_input_price / 1_000_000:.4f}")
                print(f"   Input (cached):     ${stats['total_cached_tokens'] * batch_cached_price / 1_000_000:.4f}")
                print(f"   Input (total):      ${input_cost:.4f}")
            else:
                print(f"   Input:              ${input_cost:.4f}")
            print(f"   Output:             ${output_cost:.4f}")
            print(f"   Total:              ${total_cost:.4f}")
        else:
            print(f"\n💰 Cost Estimation:")
            print(f"   Model detected: {model_name}")
            print(f"   ⚠️  Pricing not available for this model.")
            print(f"   Please check OpenAI pricing page for current rates.")
    else:
        print(f"\n⚠️  No token usage data found in results file.")
        print(f"   This might mean:")
        print(f"   - The results file doesn't contain token usage information")
        print(f"   - The API response format is different than expected")
    
    print("\n" + "="*60)


def print_detailed_stats(stats: Dict, top_n: int = 10):
    """Print detailed statistics including top N requests by token usage."""
    if not stats['per_request_tokens']:
        return
    
    print(f"\n📊 Detailed Statistics:")
    print(f"   Requests with token data: {len(stats['per_request_tokens'])}")
    
    # Sort by total tokens
    sorted_requests = sorted(
        stats['per_request_tokens'],
        key=lambda x: x['total_tokens'],
        reverse=True
    )
    
    if sorted_requests:
        print(f"\n🔝 Top {min(top_n, len(sorted_requests))} requests by token usage:")
        for i, req in enumerate(sorted_requests[:top_n], 1):
            print(f"   {i:2d}. {req['custom_id']:>6s}: "
                  f"input={format_number(req['input_tokens']):>8s}, "
                  f"output={format_number(req['output_tokens']):>8s}, "
                  f"total={format_number(req['total_tokens']):>8s}")
        
        # Min/Max
        min_req = min(stats['per_request_tokens'], key=lambda x: x['total_tokens'])
        max_req = max(stats['per_request_tokens'], key=lambda x: x['total_tokens'])
        
        print(f"\n   Min tokens: {format_number(min_req['total_tokens'])} (custom_id: {min_req['custom_id']})")
        print(f"   Max tokens: {format_number(max_req['total_tokens'])} (custom_id: {max_req['custom_id']})")


def main():
    parser = argparse.ArgumentParser(
        description="Summarize token usage from OpenAI Batch API results.jsonl file."
    )
    parser.add_argument(
        "--input",
        default="jsonl/results.jsonl",
        type=Path,
        help="Path to results.jsonl file (default: jsonl/results.jsonl)",
    )
    parser.add_argument(
        "--detailed",
        action="store_true",
        help="Show detailed statistics including top requests by token usage",
    )
    parser.add_argument(
        "--top-n",
        type=int,
        default=10,
        help="Number of top requests to show in detailed mode (default: 10)",
    )
    
    args = parser.parse_args()
    
    # Parse results
    stats = parse_results(args.input)
    
    # Print summary
    print_summary(stats)
    
    # Print detailed stats if requested
    if args.detailed:
        print_detailed_stats(stats, args.top_n)
    
    print("\n✅ Summary complete!")


if __name__ == "__main__":
    main()
