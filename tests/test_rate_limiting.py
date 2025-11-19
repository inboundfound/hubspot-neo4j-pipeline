#!/usr/bin/env python3
"""Test script to verify rate limiting stays within 170 req/10s"""

import time
from collections import deque
from utils.parallel_processor import ParallelProcessor
from utils.logger import setup_logger


def simulate_api_call(item):
    """Simulate a quick API call"""
    time.sleep(0.01)  # Simulate 10ms API response time
    return f"processed_{item}"


def monitor_rate_limit(processor: ParallelProcessor, duration_seconds: int = 15):
    """
    Monitor the rate limiting over a period of time using sliding window verification.
    
    Args:
        processor: The ParallelProcessor instance to test
        duration_seconds: How long to monitor (default 15 seconds to cover 1.5 windows)
    """
    logger = setup_logger('RateLimitTest')
    
    logger.info("=" * 60)
    logger.info("RATE LIMITING TEST")
    logger.info("=" * 60)
    logger.info(f"Configuration:")
    logger.info(f"  - Max requests per 10s: {processor.max_requests_per_10s}")
    logger.info(f"  - Max workers: {processor.max_workers}")
    logger.info(f"  - Test duration: {duration_seconds} seconds")
    logger.info("")
    
    # Create enough items to test rate limiting
    # We want to process more than 170 items to trigger rate limiting
    num_items = 300
    items = list(range(num_items))
    
    logger.info(f"Processing {num_items} items...")
    logger.info("")
    
    # Track request timestamps
    request_times = []
    
    def track_and_call(item):
        request_times.append(time.time())
        return simulate_api_call(item)
    
    start_time = time.time()
    
    # Process items in parallel
    results = processor.process_batch(
        items=items,
        func=track_and_call,
        desc="Testing rate limit"
    )
    
    end_time = time.time()
    elapsed = end_time - start_time
    
    # Get statistics
    stats = processor.get_statistics()
    
    # Analyze rate limiting
    logger.info("")
    logger.info("=" * 60)
    logger.info("RESULTS")
    logger.info("=" * 60)
    logger.info(f"Total items processed: {len(results)}")
    logger.info(f"Total time: {elapsed:.2f} seconds")
    logger.info(f"Average throughput: {len(results) / elapsed:.2f} items/second")
    logger.info("")
    logger.info("Rate Limiting Statistics:")
    logger.info(f"  - Total API requests: {stats['total_requests']}")
    logger.info(f"  - Total wait time: {stats['total_wait_time']:.2f} seconds")
    logger.info(f"  - Avg wait per request: {stats['avg_wait_per_request']:.4f} seconds")
    logger.info(f"  - Configured limit: {stats['rate_limit']}")
    logger.info("")
    
    # Verify sliding window compliance
    max_allowed = processor.max_requests_per_10s
    logger.info("Verifying sliding window compliance...")
    
    violations = 0
    max_in_window = 0
    
    for i, t in enumerate(request_times):
        # Count requests in 10-second window starting at this time
        window_end = t + 10
        count_in_window = sum(1 for req_time in request_times if t <= req_time < window_end)
        max_in_window = max(max_in_window, count_in_window)
        
        if count_in_window > max_allowed:
            violations += 1
            if violations <= 3:  # Only log first 3 violations
                logger.warning(f"Window at {t:.2f}s has {count_in_window} requests (limit: {max_allowed})")
    
    logger.info(f"  - Max requests in any 10s window: {max_in_window}")
    logger.info(f"  - Sliding window violations: {violations}")
    logger.info("")
    
    if violations == 0:
        compliance_percentage = (max_in_window / max_allowed) * 100
        logger.info(f"✅ PASS: Rate limiting working correctly!")
        logger.info(f"   Max window usage: {compliance_percentage:.1f}% of limit")
        logger.info(f"   No violations detected")
    else:
        logger.error(f"❌ FAIL: Rate limit exceeded in {violations} windows!")
        logger.error(f"   Max in window: {max_in_window}")
        logger.error(f"   Limit: {max_allowed} req/10s")
        return False
    
    logger.info("")
    logger.info("=" * 60)
    
    return True


def test_sliding_window():
    """Test that the sliding window rate limiter works correctly"""
    logger = setup_logger('SlidingWindowTest')
    
    logger.info("=" * 60)
    logger.info("SLIDING WINDOW TEST")
    logger.info("=" * 60)
    
    # Create processor with lower limit for faster testing
    test_limit = 50
    processor = ParallelProcessor(max_requests_per_10s=test_limit)
    
    logger.info(f"Testing with limit of {test_limit} req/10s")
    logger.info("")
    
    # Track request timestamps manually
    request_times = []
    
    def track_and_call(item):
        request_times.append(time.time())
        return simulate_api_call(item)
    
    # Process items
    num_items = 100
    items = list(range(num_items))
    
    start_time = time.time()
    results = processor.process_batch(
        items=items,
        func=track_and_call,
        desc="Testing sliding window"
    )
    end_time = time.time()
    
    # Analyze sliding windows
    logger.info(f"Processed {len(results)} items in {end_time - start_time:.2f} seconds")
    logger.info("")
    logger.info("Analyzing 10-second sliding windows...")
    
    violations = 0
    for i, t in enumerate(request_times):
        # Count requests in 10-second window starting at this time
        window_end = t + 10
        count_in_window = sum(1 for req_time in request_times if t <= req_time < window_end)
        
        if count_in_window > test_limit:
            violations += 1
            if violations <= 3:  # Only log first 3 violations
                logger.warning(f"Window starting at {t:.2f}s has {count_in_window} requests (limit: {test_limit})")
    
    if violations == 0:
        logger.info(f"✅ PASS: No sliding window violations detected!")
    else:
        logger.error(f"❌ FAIL: {violations} sliding window violations detected")
        return False
    
    logger.info("")
    logger.info("=" * 60)
    
    return True


if __name__ == "__main__":
    logger = setup_logger('Main')
    
    print("\n" + "=" * 60)
    print("HUBSPOT RATE LIMITING VERIFICATION TEST")
    print("=" * 60)
    print()
    
    # Test 1: Rate limiting with configured limit
    processor = ParallelProcessor(max_requests_per_10s=170)
    test1_passed = monitor_rate_limit(processor, duration_seconds=15)
    
    print()
    
    # Test 2: Sliding window implementation
    test2_passed = test_sliding_window()
    
    print()
    print("=" * 60)
    print("FINAL RESULTS")
    print("=" * 60)
    
    if test1_passed and test2_passed:
        print("✅ All tests PASSED!")
        print("Rate limiting is working correctly and staying within limits.")
        exit(0)
    else:
        print("❌ Some tests FAILED!")
        print("Please review the rate limiting implementation.")
        exit(1)

