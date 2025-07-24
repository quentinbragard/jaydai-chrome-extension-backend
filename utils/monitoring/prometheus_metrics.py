# utils/monitoring/prometheus_metrics.py
"""
Prometheus metrics integration for FastAPI
"""
import time
import psutil
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
from fastapi import FastAPI, Response
from starlette.middleware.base import BaseHTTPMiddleware
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)

# Define Prometheus metrics
REQUEST_COUNT = Counter(
    'http_requests_total',
    'Total HTTP requests',
    ['method', 'endpoint', 'status_code']
)

REQUEST_DURATION = Histogram(
    'http_request_duration_seconds',
    'HTTP request duration in seconds',
    ['method', 'endpoint']
)

ACTIVE_REQUESTS = Gauge(
    'http_requests_active',
    'Active HTTP requests'
)

DATABASE_QUERY_COUNT = Counter(
    'database_queries_total',
    'Total database queries',
    ['table', 'operation']
)

DATABASE_QUERY_DURATION = Histogram(
    'database_query_duration_seconds',
    'Database query duration in seconds',
    ['table', 'operation']
)

CACHE_OPERATIONS = Counter(
    'cache_operations_total',
    'Total cache operations',
    ['operation', 'result']  # hit, miss, set, delete
)

# System metrics
CPU_USAGE = Gauge('system_cpu_usage_percent', 'System CPU usage percentage')
MEMORY_USAGE = Gauge('system_memory_usage_percent', 'System memory usage percentage')
MEMORY_USAGE_BYTES = Gauge('system_memory_usage_bytes', 'System memory usage in bytes')

class PrometheusMiddleware(BaseHTTPMiddleware):
    """Middleware to collect Prometheus metrics"""
    
    def __init__(self, app, app_name: str = "jaydai_api"):
        super().__init__(app)
        self.app_name = app_name
    
    async def dispatch(self, request, call_next):
        # Skip metrics endpoint to avoid recursion
        if request.url.path == "/metrics":
            response = await call_next(request)
            return response
        
        # Track active requests
        ACTIVE_REQUESTS.inc()
        
        start_time = time.time()
        method = request.method
        path = self.get_path_template(request.url.path)
        
        try:
            response = await call_next(request)
            status_code = str(response.status_code)
        except Exception as e:
            status_code = "500"
            logger.error(f"Request failed: {str(e)}")
            raise
        finally:
            # Record metrics
            duration = time.time() - start_time
            
            REQUEST_COUNT.labels(
                method=method,
                endpoint=path,
                status_code=status_code
            ).inc()
            
            REQUEST_DURATION.labels(
                method=method,
                endpoint=path
            ).observe(duration)
            
            ACTIVE_REQUESTS.dec()
        
        return response
    
    def get_path_template(self, path: str) -> str:
        """Convert path to template for better grouping"""
        # Group similar paths together
        if path.startswith('/prompts/templates/'):
            if path.endswith('/duplicate'):
                return '/prompts/templates/{id}/duplicate'
            elif path.split('/')[-1].isdigit():
                return '/prompts/templates/{id}'
        elif path.startswith('/prompts/folders/'):
            if path.split('/')[-1].isdigit():
                return '/prompts/folders/{id}'
        elif path.startswith('/stats/user'):
            return '/stats/user'
        elif path.startswith('/user/'):
            return '/user/*'
        
        return path

def update_system_metrics():
    """Update system metrics"""
    try:
        # CPU and Memory metrics
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        
        CPU_USAGE.set(cpu_percent)
        MEMORY_USAGE.set(memory.percent)
        MEMORY_USAGE_BYTES.set(memory.used)
        
    except Exception as e:
        logger.error(f"Failed to update system metrics: {str(e)}")

# Database query tracking decorator
def track_db_query(table: str, operation: str):
    """Decorator to track database queries"""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = await func(*args, **kwargs)
                DATABASE_QUERY_COUNT.labels(table=table, operation=operation).inc()
                duration = time.time() - start_time
                DATABASE_QUERY_DURATION.labels(table=table, operation=operation).observe(duration)
                return result
            except Exception as e:
                DATABASE_QUERY_COUNT.labels(table=table, operation=f"{operation}_error").inc()
                raise
        return wrapper
    return decorator

# Cache operation tracking
def track_cache_operation(operation: str, result: str):
    """Track cache operations"""
    CACHE_OPERATIONS.labels(operation=operation, result=result).inc()

# Add metrics endpoint to your FastAPI app
def add_metrics_endpoint(app: FastAPI):
    """Add Prometheus metrics endpoint to FastAPI app"""
    
    @app.get("/metrics")
    async def get_metrics():
        """Prometheus metrics endpoint"""
        # Update system metrics before serving
        update_system_metrics()
        
        # Generate Prometheus metrics
        metrics_data = generate_latest()
        return Response(
            content=metrics_data,
            media_type=CONTENT_TYPE_LATEST
        )
