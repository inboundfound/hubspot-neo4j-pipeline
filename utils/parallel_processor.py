"""Parallel processing utility with HubSpot rate limiting"""

import time
import threading
from collections import deque
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Callable, Any, Dict
from tqdm import tqdm


class ParallelProcessor:
    """
    Thread-safe parallel processor with sliding window rate limiting.
    
    Designed for HubSpot API Professional tier: 190 requests per 10 seconds.
    Uses conservative default of 170 req/10s for safety margin.
    """
    
    def __init__(self, max_requests_per_10s: int = 170):
        """
        Initialize parallel processor with rate limiting.
        
        Args:
            max_requests_per_10s: Maximum API requests allowed per 10-second window
        """
        self.max_requests_per_10s = max_requests_per_10s
        
        # Auto-calculate optimal worker count
        # For 170 req/10s, we want ~15 workers to maintain throughput
        # while respecting rate limits
        self.max_workers = min(20, max(10, max_requests_per_10s // 10))
        
        # Sliding window rate limiter
        self.request_times = deque()
        self.rate_limit_lock = threading.Lock()
        
        # Statistics tracking
        self.total_requests = 0
        self.total_wait_time = 0.0
    
    def _wait_for_rate_limit(self) -> float:
        """
        Ensure we don't exceed rate limits using sliding window.
        
        Returns:
            float: Time waited in seconds (for statistics)
        """
        wait_time = 0.0
        
        with self.rate_limit_lock:
            now = time.time()
            
            # Remove timestamps older than 10 seconds (sliding window)
            while self.request_times and self.request_times[0] < now - 10:
                self.request_times.popleft()
            
            # If we've hit the limit, wait until oldest request expires
            if len(self.request_times) >= self.max_requests_per_10s:
                sleep_time = 10 - (now - self.request_times[0]) + 0.1  # 0.1s buffer
                if sleep_time > 0:
                    time.sleep(sleep_time)
                    wait_time = sleep_time
                    now = time.time()
            
            # Record this request timestamp
            self.request_times.append(now)
            self.total_requests += 1
        
        return wait_time
    
    def process_batch(
        self,
        items: List[Any],
        func: Callable[[Any], Any],
        desc: str = "Processing",
        maintain_order: bool = True
    ) -> List[Any]:
        """
        Process a batch of items in parallel with rate limiting and progress tracking.
        
        Args:
            items: List of items to process
            func: Function to apply to each item (should make API call)
            desc: Description for progress bar
            maintain_order: If True, results match input order; if False, results in completion order
        
        Returns:
            List of results in same order as input items
        """
        if not items:
            return []
        
        results = [None] * len(items) if maintain_order else []
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all tasks with their indices
            future_to_index = {}
            for idx, item in enumerate(items):
                future = executor.submit(self._process_with_rate_limit, func, item)
                future_to_index[future] = idx
            
            # Process completed tasks with progress bar
            with tqdm(total=len(items), desc=desc) as pbar:
                for future in as_completed(future_to_index):
                    idx = future_to_index[future]
                    try:
                        result = future.result()
                        if maintain_order:
                            results[idx] = result
                        else:
                            results.append(result)
                    except Exception as e:
                        # Log error but continue processing
                        error_result = {'error': str(e), 'index': idx}
                        if maintain_order:
                            results[idx] = error_result
                        else:
                            results.append(error_result)
                    
                    pbar.update(1)
        
        return results
    
    def _process_with_rate_limit(self, func: Callable[[Any], Any], item: Any) -> Any:
        """
        Wrapper that applies rate limiting before calling function.
        
        Args:
            func: Function to call
            item: Item to pass to function
        
        Returns:
            Result from function call
        """
        # Wait for rate limit slot
        wait_time = self._wait_for_rate_limit()
        self.total_wait_time += wait_time
        
        # Execute the function
        return func(item)
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get processing statistics.
        
        Returns:
            Dictionary with statistics about requests and rate limiting
        """
        return {
            'total_requests': self.total_requests,
            'total_wait_time': self.total_wait_time,
            'avg_wait_per_request': self.total_wait_time / max(self.total_requests, 1),
            'max_workers': self.max_workers,
            'rate_limit': f"{self.max_requests_per_10s} req/10s"
        }
    
    def reset_statistics(self):
        """Reset statistics counters."""
        self.total_requests = 0
        self.total_wait_time = 0.0

