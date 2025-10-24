"""
Performance monitoring and timing utilities.
"""
import time
import functools
from typing import Dict, Any, Callable
from datetime import datetime


class PerformanceTimer:
    """Context manager and decorator for timing operations."""

    def __init__(self, operation_name: str, log_func=print):
        self.operation_name = operation_name
        self.log = log_func
        self.start_time = None
        self.end_time = None
        self.duration = None

    def __enter__(self):
        self.start_time = time.time()
        self.log(f"⏱️  START: {self.operation_name}")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.end_time = time.time()
        self.duration = self.end_time - self.start_time

        if exc_type is None:
            self.log(f"✅ COMPLETE: {self.operation_name} ({self.duration:.3f}s)")
        else:
            self.log(f"❌ FAILED: {self.operation_name} ({self.duration:.3f}s) - {exc_val}")

        return False  # Don't suppress exceptions


def timed(operation_name: str = None):
    """Decorator to time function execution."""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            name = operation_name or f"{func.__module__}.{func.__name__}"
            timer = PerformanceTimer(name)
            timer.__enter__()
            try:
                result = func(*args, **kwargs)
                timer.__exit__(None, None, None)
                return result
            except Exception as e:
                timer.__exit__(type(e), e, None)
                raise
        return wrapper
    return decorator


class PerformanceMetrics:
    """Track and report performance metrics."""

    def __init__(self):
        self.metrics = {}
        self.start_time = time.time()

    def record(self, operation: str, duration: float, metadata: Dict[str, Any] = None):
        """Record a timed operation."""
        if operation not in self.metrics:
            self.metrics[operation] = {
                'count': 0,
                'total_time': 0.0,
                'min_time': float('inf'),
                'max_time': 0.0,
                'metadata': []
            }

        m = self.metrics[operation]
        m['count'] += 1
        m['total_time'] += duration
        m['min_time'] = min(m['min_time'], duration)
        m['max_time'] = max(m['max_time'], duration)

        if metadata:
            m['metadata'].append(metadata)

    def get_summary(self) -> Dict[str, Any]:
        """Get performance summary."""
        total_elapsed = time.time() - self.start_time

        summary = {
            'total_elapsed_seconds': round(total_elapsed, 3),
            'operations': {}
        }

        for operation, data in self.metrics.items():
            avg_time = data['total_time'] / data['count'] if data['count'] > 0 else 0
            summary['operations'][operation] = {
                'count': data['count'],
                'total_time': round(data['total_time'], 3),
                'avg_time': round(avg_time, 3),
                'min_time': round(data['min_time'], 3),
                'max_time': round(data['max_time'], 3),
                'percentage_of_total': round((data['total_time'] / total_elapsed * 100), 1) if total_elapsed > 0 else 0
            }

        return summary

    def print_report(self):
        """Print formatted performance report."""
        summary = self.get_summary()

        print("\n" + "="*80)
        print("⚡ PERFORMANCE REPORT")
        print("="*80)
        print(f"Total Elapsed: {summary['total_elapsed_seconds']}s")
        print()

        # Sort by total time descending
        sorted_ops = sorted(
            summary['operations'].items(),
            key=lambda x: x[1]['total_time'],
            reverse=True
        )

        for op_name, stats in sorted_ops:
            print(f"{op_name}:")
            print(f"  Count: {stats['count']}")
            print(f"  Total: {stats['total_time']}s ({stats['percentage_of_total']}%)")
            print(f"  Avg: {stats['avg_time']}s")
            print(f"  Min: {stats['min_time']}s | Max: {stats['max_time']}s")
            print()

        print("="*80)


def create_logger(prefix: str = ""):
    """Create a logger function with timestamp and prefix."""
    def log(message: str, level: str = "INFO"):
        timestamp = datetime.utcnow().isoformat()[:-3] + 'Z'
        full_prefix = f"[{timestamp}] [{level}]"
        if prefix:
            full_prefix += f" [{prefix}]"
        print(f"{full_prefix} {message}")
    return log
