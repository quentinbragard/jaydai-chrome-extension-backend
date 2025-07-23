# utils/middleware/performance_monitoring.py
import time
import logging
import json
import psutil
import asyncio
from typing import Dict, Any
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from collections import defaultdict, deque
from datetime import datetime, timedelta
import threading

# Global metrics storage (in production, use Redis)
request_metrics = defaultdict(lambda: {
    'total_requests': 0,
    'total_time': 0,
    'response_times': deque(maxlen=100),  # Keep last 100 response times
    'error_count': 0,
    'slow_requests': 0  # > 1 second
})

class PerformanceMonitoringMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, threshold_ms: float = 1000):
        super().__init__(app)
        self.threshold_ms = threshold_ms
        self.logger = logging.getLogger("performance")
        
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        start_memory = psutil.Process().memory_info().rss / 1024 / 1024  # MB
        
        # Extract user info if available
        user_id = None
        try:
            if hasattr(request.state, 'user_id'):
                user_id = request.state.user_id
        except:
            pass
            
        # Process request
        try:
            response = await call_next(request)
            status_code = response.status_code
            error = None
        except Exception as e:
            status_code = 500
            error = str(e)
            response = Response(
                content=json.dumps({"error": "Internal server error"}),
                status_code=500,
                media_type="application/json"
            )
        
        # Calculate metrics
        end_time = time.time()
        duration_ms = (end_time - start_time) * 1000
        end_memory = psutil.Process().memory_info().rss / 1024 / 1024  # MB
        memory_diff = end_memory - start_memory
        
        # Update metrics
        endpoint = f"{request.method} {request.url.path}"
        metrics = request_metrics[endpoint]
        metrics['total_requests'] += 1
        metrics['total_time'] += duration_ms
        metrics['response_times'].append(duration_ms)
        
        if status_code >= 400:
            metrics['error_count'] += 1
        if duration_ms > self.threshold_ms:
            metrics['slow_requests'] += 1
        
        # Log detailed performance data
        log_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "method": request.method,
            "path": request.url.path,
            "status_code": status_code,
            "duration_ms": round(duration_ms, 2),
            "memory_usage_mb": round(end_memory, 2),
            "memory_diff_mb": round(memory_diff, 2),
            "user_id": user_id,
            "query_params": dict(request.query_params),
            "is_slow": duration_ms > self.threshold_ms
        }
        
        if error:
            log_data["error"] = error
            
        # Log as JSON for Cloud Logging
        if duration_ms > self.threshold_ms or status_code >= 400:
            self.logger.warning(json.dumps(log_data))
        else:
            self.logger.info(json.dumps(log_data))
            
        return response

# Performance metrics endpoint
async def get_performance_metrics():
    """Get current performance metrics"""
    current_metrics = {}
    
    for endpoint, metrics in request_metrics.items():
        if metrics['total_requests'] > 0:
            response_times = list(metrics['response_times'])
            current_metrics[endpoint] = {
                'total_requests': metrics['total_requests'],
                'avg_response_time_ms': round(metrics['total_time'] / metrics['total_requests'], 2),
                'error_rate': round(metrics['error_count'] / metrics['total_requests'] * 100, 2),
                'slow_request_rate': round(metrics['slow_requests'] / metrics['total_requests'] * 100, 2),
                'p95_response_time': round(sorted(response_times)[int(len(response_times) * 0.95)], 2) if response_times else 0,
                'p99_response_time': round(sorted(response_times)[int(len(response_times) * 0.99)], 2) if response_times else 0
            }
    
    # System metrics
    system_metrics = {
        'cpu_percent': psutil.cpu_percent(),
        'memory_percent': psutil.virtual_memory().percent,
        'memory_used_mb': psutil.virtual_memory().used / 1024 / 1024
    }
    
    return {
        'endpoints': current_metrics,
        'system': system_metrics,
        'timestamp': datetime.utcnow().isoformat()
    }