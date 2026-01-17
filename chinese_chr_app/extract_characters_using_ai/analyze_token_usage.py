#!/usr/bin/env python3
"""
Analyze token usage from OpenAI batch results to estimate costs.
"""

import json
import sys
from pathlib import Path
from typing import Dict, List


def extract_token_usage(results_file: Path) -> Dict:
    """Extract token usage statistics from a results JSONL file."""
    total_input_tokens = 0
    total_output_tokens = 0
    total_cached_tokens = 0
    total_reasoning_tokens = 0
    total_tokens = 0
    entry_count = 0
    
    with open(results_file, 'r', encoding='utf-8') as f:
        for line in f:
            try:
                result = json.loads(line)
                response = result.get('response', {})
                body = response.get('body', {})
                usage = body.get('usage', {})
                
                if usage:
                    input_tokens = usage.get('input_tokens', 0)
                    output_tokens = usage.get('output_tokens', 0)
                    cached_tokens = usage.get('input_tokens_details', {}).get('cached_tokens', 0)
                    reasoning_tokens = usage.get('output_tokens_details', {}).get('reasoning_tokens', 0)
                    total = usage.get('total_tokens', 0)
                    
                    total_input_tokens += input_tokens
                    total_output_tokens += output_tokens
                    total_cached_tokens += cached_tokens
                    total_reasoning_tokens += reasoning_tokens
                    total_tokens += total
                    entry_count += 1
            except (json.JSONDecodeError, KeyError) as e:
                continue
    
    return {
        'file': str(results_file),
        'entries': entry_count,
        'input_tokens': total_input_tokens,
        'output_tokens': total_output_tokens,
        'cached_tokens': total_cached_tokens,
        'reasoning_tokens': total_reasoning_tokens,
        'total_tokens': total_tokens,
        'avg_tokens_per_entry': total_tokens / entry_count if entry_count > 0 else 0,
        'avg_input_per_entry': total_input_tokens / entry_count if entry_count > 0 else 0,
        'avg_output_per_entry': total_output_tokens / entry_count if entry_count > 0 else 0,
    }


def calculate_cost(tokens: Dict, model: str = 'gpt-5-mini') -> Dict:
    """
    Calculate cost based on OpenAI Batch API pricing.
    Batch API has 50% discount on input/output tokens.
    
    GPT-5-mini pricing (as of 2025):
    - Input: $0.15 per 1M tokens
    - Output: $0.60 per 1M tokens
    - Reasoning tokens: Same as output tokens
    
    With Batch API 50% discount:
    - Input: $0.075 per 1M tokens
    - Output: $0.30 per 1M tokens
    - Cached tokens: $0.00 (free)
    """
    # Batch API pricing (50% discount)
    input_price_per_million = 0.075
    output_price_per_million = 0.30
    
    # Calculate billable tokens (excluding cached)
    billable_input = tokens['input_tokens'] - tokens['cached_tokens']
    billable_output = tokens['output_tokens']  # Reasoning tokens are part of output
    
    input_cost = (billable_input / 1_000_000) * input_price_per_million
    output_cost = (billable_output / 1_000_000) * output_price_per_million
    total_cost = input_cost + output_cost
    
    return {
        'input_cost': input_cost,
        'output_cost': output_cost,
        'total_cost': total_cost,
        'billable_input_tokens': billable_input,
        'billable_output_tokens': billable_output,
    }


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 analyze_token_usage.py <results_file1.jsonl> [results_file2.jsonl ...]")
        sys.exit(1)
    
    results_files = [Path(f) for f in sys.argv[1:]]
    
    print("=" * 80)
    print("Token Usage Analysis")
    print("=" * 80)
    
    all_stats = []
    total_stats = {
        'entries': 0,
        'input_tokens': 0,
        'output_tokens': 0,
        'cached_tokens': 0,
        'reasoning_tokens': 0,
        'total_tokens': 0,
    }
    
    for results_file in results_files:
        if not results_file.exists():
            print(f"⚠️  File not found: {results_file}")
            continue
        
        stats = extract_token_usage(results_file)
        all_stats.append(stats)
        
        # Accumulate totals
        for key in total_stats:
            total_stats[key] += stats[key]
        
        cost = calculate_cost(stats)
        
        print(f"\n📄 {results_file.name}")
        print(f"   Entries: {stats['entries']}")
        print(f"   Input tokens: {stats['input_tokens']:,} (cached: {stats['cached_tokens']:,})")
        print(f"   Output tokens: {stats['output_tokens']:,} (reasoning: {stats['reasoning_tokens']:,})")
        print(f"   Total tokens: {stats['total_tokens']:,}")
        print(f"   Avg tokens/entry: {stats['avg_tokens_per_entry']:,.0f}")
        print(f"   Cost: ${cost['total_cost']:.4f}")
        print(f"      - Input: ${cost['input_cost']:.4f} ({cost['billable_input_tokens']:,} billable tokens)")
        print(f"      - Output: ${cost['output_cost']:.4f} ({cost['billable_output_tokens']:,} tokens)")
    
    # Overall summary
    if all_stats:
        print(f"\n{'=' * 80}")
        print("Overall Summary")
        print(f"{'=' * 80}")
        print(f"Total entries: {total_stats['entries']}")
        print(f"Total input tokens: {total_stats['input_tokens']:,} (cached: {total_stats['cached_tokens']:,})")
        print(f"Total output tokens: {total_stats['output_tokens']:,} (reasoning: {total_stats['reasoning_tokens']:,})")
        print(f"Total tokens: {total_stats['total_tokens']:,}")
        print(f"Average tokens per entry: {total_stats['total_tokens'] / total_stats['entries']:,.0f}")
        
        total_cost = calculate_cost(total_stats)
        print(f"\n💰 Total Cost: ${total_cost['total_cost']:.4f}")
        print(f"   - Input: ${total_cost['input_cost']:.4f}")
        print(f"   - Output: ${total_cost['output_cost']:.4f}")
        
        # Estimate for remaining characters
        if total_stats['entries'] > 0:
            avg_tokens = total_stats['total_tokens'] / total_stats['entries']
            avg_cost_per_entry = total_cost['total_cost'] / total_stats['entries']
            
            print(f"\n📊 Per-Entry Averages:")
            print(f"   Tokens per entry: {avg_tokens:,.0f}")
            print(f"   Cost per entry: ${avg_cost_per_entry:.6f}")
            
            # Calculate remaining characters
            # We have processed up to index 0904, and need to process up to 3000
            remaining_chars = 3000 - 904
            estimated_tokens = avg_tokens * remaining_chars
            estimated_cost = avg_cost_per_entry * remaining_chars
            
            print(f"\n🔮 Cost Estimate for Remaining Characters:")
            print(f"   Remaining characters: {remaining_chars:,} (0905-3000)")
            print(f"   Estimated tokens: {estimated_tokens:,.0f}")
            print(f"   Estimated cost: ${estimated_cost:.2f}")
            
            # Break down by day (considering free tier)
            free_tier_daily = 2_500_000  # 2.5M tokens/day free
            print(f"\n📅 Daily Free Tier: 2,500,000 tokens/day")
            if estimated_tokens <= free_tier_daily:
                print(f"   ✅ Can fit in 1 day (within free tier)")
            else:
                days_needed = (estimated_tokens / free_tier_daily)
                print(f"   ⚠️  Would need {days_needed:.1f} days of free tier")
                print(f"   💰 Cost after free tier: ${estimated_cost:.2f}")
    
    print(f"\n{'=' * 80}")


if __name__ == "__main__":
    main()
