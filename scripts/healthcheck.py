# Docker healthcheck script
# scripts/healthcheck.py
"""
Advanced healthcheck for Cloud Run with custom metrics
"""
import requests
import sys
import json
import time
import os

def check_health():
    """Comprehensive health check"""
    health_url = f"http://localhost:{os.getenv('PORT', '8000')}/health"
    
    try:
        start_time = time.time()
        response = requests.get(health_url, timeout=10)
        response_time = (time.time() - start_time) * 1000
        
        if response.status_code == 200:
            health_data = response.json()
            
            # Check if all components are healthy
            components = health_data.get("components", {})
            all_healthy = all(
                comp.get("status") == "healthy" 
                for comp in components.values()
            )
            
            if all_healthy and response_time < 5000:  # 5 second timeout
                print(f"✅ Health check passed ({response_time:.2f}ms)")
                return 0
            else:
                print(f"⚠️ Health check degraded ({response_time:.2f}ms)")
                print(json.dumps(health_data, indent=2))
                return 1
        else:
            print(f"❌ Health check failed with status {response.status_code}")
            return 1
            
    except Exception as e:
        print(f"❌ Health check error: {str(e)}")
        return 1

if __name__ == "__main__":
    sys.exit(check_health())

