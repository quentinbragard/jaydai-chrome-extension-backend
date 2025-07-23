# scripts/monitor_performance.py
"""
Performance monitoring script for local development and production monitoring
"""
import asyncio
import aiohttp
import time
import json
import statistics
from datetime import datetime
from typing import Dict, List, Any
import argparse

class PerformanceMonitor:
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url.rstrip('/')
        self.session = None
        
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def test_endpoint(self, endpoint: str, method: str = "GET", data: Dict = None, headers: Dict = None) -> Dict[str, Any]:
        """Test a single endpoint and return performance metrics"""
        url = f"{self.base_url}{endpoint}"
        
        start_time = time.time()
        try:
            if method.upper() == "GET":
                async with self.session.get(url, headers=headers) as response:
                    content = await response.text()
                    status_code = response.status
            elif method.upper() == "POST":
                async with self.session.post(url, json=data, headers=headers) as response:
                    content = await response.text()
                    status_code = response.status
            else:
                raise ValueError(f"Unsupported method: {method}")
                
            response_time = (time.time() - start_time) * 1000
            
            return {
                "endpoint": endpoint,
                "method": method,
                "status_code": status_code,
                "response_time_ms": round(response_time, 2),
                "response_size_bytes": len(content.encode('utf-8')),
                "success": 200 <= status_code < 300,
                "timestamp": datetime.utcnow().isoformat()
            }
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            return {
                "endpoint": endpoint,
                "method": method,
                "status_code": 0,
                "response_time_ms": round(response_time, 2),
                "error": str(e),
                "success": False,
                "timestamp": datetime.utcnow().isoformat()
            }
    
    async def load_test_endpoint(self, endpoint: str, concurrent_requests: int = 10, total_requests: int = 100, headers: Dict = None) -> Dict[str, Any]:
        """Perform load testing on an endpoint"""
        print(f"Load testing {endpoint} with {concurrent_requests} concurrent requests, {total_requests} total...")
        
        semaphore = asyncio.Semaphore(concurrent_requests)
        results = []
        
        async def single_request():
            async with semaphore:
                return await self.test_endpoint(endpoint, headers=headers)
        
        # Create all tasks
        tasks = [single_request() for _ in range(total_requests)]
        
        # Execute all tasks
        start_time = time.time()
        results = await asyncio.gather(*tasks, return_exceptions=True)
        total_time = time.time() - start_time
        
        # Process results
        successful_results = [r for r in results if isinstance(r, dict) and r.get("success")]
        failed_results = [r for r in results if isinstance(r, dict) and not r.get("success")]
        
        if successful_results:
            response_times = [r["response_time_ms"] for r in successful_results]
            
            return {
                "endpoint": endpoint,
                "total_requests": total_requests,
                "concurrent_requests": concurrent_requests,
                "successful_requests": len(successful_results),
                "failed_requests": len(failed_results),
                "total_time_seconds": round(total_time, 2),
                "requests_per_second": round(total_requests / total_time, 2),
                "response_time_stats": {
                    "min_ms": round(min(response_times), 2),
                    "max_ms": round(max(response_times), 2),
                    "mean_ms": round(statistics.mean(response_times), 2),
                    "median_ms": round(statistics.median(response_times), 2),
                    "p95_ms": round(statistics.quantiles(response_times, n=20)[18], 2),  # 95th percentile
                    "p99_ms": round(statistics.quantiles(response_times, n=100)[98], 2)  # 99th percentile
                }
            }
        else:
            return {
                "endpoint": endpoint,
                "total_requests": total_requests,
                "successful_requests": 0,
                "failed_requests": len(failed_results),
                "total_time_seconds": round(total_time, 2),
                "error": "All requests failed"
            }
    
    async def monitor_application_metrics(self) -> Dict[str, Any]:
        """Get application performance metrics"""
        try:
            result = await self.test_endpoint("/metrics")
            if result["success"]:
                metrics_data = json.loads(await self.session.get(f"{self.base_url}/metrics").text())
                return metrics_data
            else:
                return {"error": "Failed to fetch metrics"}
        except Exception as e:
            return {"error": str(e)}
    
    async def comprehensive_performance_test(self, auth_token: str = None) -> Dict[str, Any]:
        """Run comprehensive performance tests"""
        headers = {"Authorization": f"Bearer {auth_token}"} if auth_token else None
        
        # Test endpoints to monitor
        endpoints_to_test = [
            {"endpoint": "/", "method": "GET"},
            {"endpoint": "/health", "method": "GET"},
            {"endpoint": "/metrics", "method": "GET"},
        ]
        
        # If auth token is provided, test authenticated endpoints
        if auth_token:
            endpoints_to_test.extend([
                {"endpoint": "/prompts/folders", "method": "GET"},
                {"endpoint": "/prompts/templates", "method": "GET"},
                {"endpoint": "/stats/user", "method": "GET"},
                {"endpoint": "/user/metadata", "method": "GET"},
            ])
        
        results = {
            "timestamp": datetime.utcnow().isoformat(),
            "base_url": self.base_url,
            "endpoint_tests": [],
            "load_tests": [],
            "application_metrics": None
        }
        
        # Test individual endpoints
        print("Testing individual endpoints...")
        for endpoint_config in endpoints_to_test:
            result = await self.test_endpoint(
                endpoint_config["endpoint"], 
                endpoint_config["method"], 
                headers=headers
            )
            results["endpoint_tests"].append(result)
            print(f"  {endpoint_config['endpoint']}: {result['response_time_ms']:.2f}ms")
        
        # Load test critical endpoints
        if auth_token:
            critical_endpoints = ["/prompts/folders", "/prompts/templates"]
            print("\nRunning load tests...")
            for endpoint in critical_endpoints:
                load_result = await self.load_test_endpoint(
                    endpoint, 
                    concurrent_requests=5, 
                    total_requests=50,
                    headers=headers
                )
                results["load_tests"].append(load_result)
                print(f"  {endpoint}: {load_result.get('requests_per_second', 0):.2f} req/s")
        
        # Get application metrics
        app_metrics = await self.monitor_application_metrics()
        results["application_metrics"] = app_metrics
        
        return results

async def main():
    parser = argparse.ArgumentParser(description="Performance monitoring for Jaydai API")
    parser.add_argument("--url", default="http://localhost:8000", help="Base URL of the API")
    parser.add_argument("--auth-token", help="Authentication token for protected endpoints")
    parser.add_argument("--load-test", action="store_true", help="Run load tests")
    parser.add_argument("--continuous", action="store_true", help="Run continuous monitoring")
    parser.add_argument("--interval", type=int, default=60, help="Monitoring interval in seconds")
    parser.add_argument("--output", help="Output file for results (JSON)")
    
    args = parser.parse_args()
    
    async with PerformanceMonitor(args.url) as monitor:
        if args.continuous:
            print(f"Starting continuous monitoring every {args.interval} seconds...")
            while True:
                try:
                    results = await monitor.comprehensive_performance_test(args.auth_token)
                    
                    # Print summary
                    print(f"\n--- Performance Report {results['timestamp']} ---")
                    for test in results["endpoint_tests"]:
                        status = "✅" if test["success"] else "❌"
                        print(f"{status} {test['endpoint']}: {test['response_time_ms']:.2f}ms")
                    
                    if results["load_tests"]:
                        print("\nLoad Test Results:")
                        for load_test in results["load_tests"]:
                            print(f"  {load_test['endpoint']}: {load_test.get('requests_per_second', 0):.2f} req/s")
                    
                    # Save to file if specified
                    if args.output:
                        with open(args.output, 'w') as f:
                            json.dump(results, f, indent=2)
                    
                    await asyncio.sleep(args.interval)
                    
                except KeyboardInterrupt:
                    print("\nMonitoring stopped by user")
                    break
                except Exception as e:
                    print(f"Error during monitoring: {str(e)}")
                    await asyncio.sleep(args.interval)
        else:
            # Single test run
            results = await monitor.comprehensive_performance_test(args.auth_token)
            
            # Print detailed results
            print(json.dumps(results, indent=2))
            
            # Save to file if specified
            if args.output:
                with open(args.output, 'w') as f:
                    json.dump(results, f, indent=2)
                print(f"Results saved to {args.output}")

if __name__ == "__main__":
    asyncio.run(main())

# Example usage commands:
"""
# Basic performance test
python scripts/monitor_performance.py --url https://your-api.run.app

# Load testing with authentication
python scripts/monitor_performance.py --url https://your-api.run.app --auth-token "your-jwt-token" --load-test

# Continuous monitoring
python scripts/monitor_performance.py --url https://your-api.run.app --auth-token "your-jwt-token" --continuous --interval 30

# Save results to file
python scripts/monitor_performance.py --url https://your-api.run.app --output performance_results.json
"""