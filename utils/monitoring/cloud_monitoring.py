# utils/monitoring/cloud_monitoring.py
"""
Google Cloud Monitoring integration for advanced metrics
"""
import os
import time
import logging
from google.cloud import monitoring_v3
from google.cloud.monitoring_v3 import TimeSeries, Point, TimeInterval
from datetime import datetime, timezone
import json
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

class CloudMonitoringClient:
    def __init__(self):
        self.project_id = os.getenv("GCP_PROJECT_ID")
        self.client = None
        
        try:
            if self.project_id:
                self.client = monitoring_v3.MetricServiceClient()
                self.project_name = f"projects/{self.project_id}"
                logger.info(f"Cloud Monitoring initialized for project {self.project_id}")
            else:
                logger.warning("GCP_PROJECT_ID not set, Cloud Monitoring disabled")
        except Exception as e:
            logger.error(f"Failed to initialize Cloud Monitoring: {str(e)}")
    
    def send_custom_metric(self, metric_name: str, value: float, labels: Dict[str, str] = None):
        """Send custom metric to Google Cloud Monitoring"""
        if not self.client:
            return
        
        try:
            # Create metric descriptor if it doesn't exist
            series = TimeSeries()
            series.metric.type = f"custom.googleapis.com/{metric_name}"
            series.resource.type = "cloud_run_revision"
            series.resource.labels["service_name"] = os.getenv("K_SERVICE", "jaydai-api")
            series.resource.labels["revision_name"] = os.getenv("K_REVISION", "unknown")
            series.resource.labels["location"] = os.getenv("CLOUD_RUN_REGION", "europe-west1")
            
            # Add custom labels
            if labels:
                for key, val in labels.items():
                    series.metric.labels[key] = str(val)
            
            # Create data point
            now = time.time()
            seconds = int(now)
            nanos = int((now - seconds) * 10 ** 9)
            interval = TimeInterval({"end_time": {"seconds": seconds, "nanos": nanos}})
            point = Point({"interval": interval, "value": {"double_value": value}})
            series.points = [point]
            
            # Send to Cloud Monitoring
            self.client.create_time_series(name=self.project_name, time_series=[series])
            
        except Exception as e:
            logger.error(f"Failed to send metric {metric_name}: {str(e)}")

# Global instance
cloud_monitoring = CloudMonitoringClient()

# Enhanced middleware with Cloud Monitoring
class CloudMonitoringMiddleware:
    def __init__(self, app):
        self.app = app
        
    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        
        start_time = time.time()
        path = scope["path"]
        method = scope["method"]
        
        # Process request
        await self.app(scope, receive, send)
        
        # Calculate metrics
        duration = (time.time() - start_time) * 1000  # ms
        
        # Send to Cloud Monitoring
        cloud_monitoring.send_custom_metric(
            "api_request_duration",
            duration,
            {"endpoint": path, "method": method}
        )
        
        cloud_monitoring.send_custom_metric(
            "api_request_count",
            1,
            {"endpoint": path, "method": method}
        )

