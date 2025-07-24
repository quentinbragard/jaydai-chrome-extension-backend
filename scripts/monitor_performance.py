# scripts/monitor_performance_fixed.py
"""
Fixed performance monitoring script with proper async handling
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
        timeout = aiohttp.ClientTimeout(total=30)
        self.session = aiohttp.ClientSession(timeout=timeout)
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
    
    async def monitor_application_metrics(self) -> Dict[str, Any]:
        """Get application performance metrics - FIXED VERSION"""
        try:
            result = await self.test_endpoint("/metrics")
            if result["success"]:
                # Properly get the response for metrics
                async with self.session.get(f"{self.base_url}/metrics") as response:
                    if response.status == 200:
                        metrics_text = await response.text()
                        try:
                            metrics_data = json.loads(metrics_text)
                            return metrics_data
                        except json.JSONDecodeError:
                            return {"error": "Invalid JSON in metrics response", "raw_response": metrics_text[:500]}
                    else:
                        return {"error": f"Metrics endpoint returned status {response.status}"}
            else:
                return {"error": "Failed to fetch metrics", "details": result}
        except Exception as e:
            return {"error": str(e)}
    
    async def comprehensive_performance_test(self, auth_token: str = None) -> Dict[str, Any]:
        """Run comprehensive performance tests"""
        headers = {"Authorization": f"Bearer {auth_token}"} if auth_token else None
        
        # Test endpoints to monitor
        endpoints_to_test = [
            {"endpoint": "/", "method": "GET"},
            {"endpoint": "/health", "method": "GET"},
        ]
        
        # Only test metrics if it exists
        try:
            metrics_test = await self.test_endpoint("/metrics")
            if metrics_test["success"]:
                endpoints_to_test.append({"endpoint": "/metrics", "method": "GET"})
        except:
            pass
        
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
            status_icon = "✅" if result["success"] else "❌"
            print(f"  {status_icon} {endpoint_config['endpoint']}: {result['response_time_ms']:.2f}ms")
        
        # Get application metrics
        print("Fetching application metrics...")
        app_metrics = await self.monitor_application_metrics()
        results["application_metrics"] = app_metrics
        
        return results

async def main():
    parser = argparse.ArgumentParser(description="Performance monitoring for Jaydai API")
    parser.add_argument("--url", default="http://localhost:8000", help="Base URL of the API")
    parser.add_argument("--auth-token", help="Authentication token for protected endpoints")
    parser.add_argument("--continuous", action="store_true", help="Run continuous monitoring")
    parser.add_argument("--interval", type=int, default=60, help="Monitoring interval in seconds")
    parser.add_argument("--output", help="Output file for results (JSON)")
    parser.add_argument("--env", choices=["local", "dev", "prod"], default="local", help="Environment to test")
    
    args = parser.parse_args()
    
    # Set URL based on environment
    if args.env == "dev":
        args.url = "https://api.dev.jayd.ai"
    elif args.env == "prod":
        args.url = "https://api.prod.jayd.ai"
    
    print(f"Monitoring {args.url} ({args.env} environment)")
    
    async with PerformanceMonitor(args.url) as monitor:
        if args.continuous:
            print(f"Starting continuous monitoring every {args.interval} seconds...")
            try:
                while True:
                    try:
                        results = await monitor.comprehensive_performance_test(args.auth_token)
                        
                        # Print summary
                        print(f"\n--- Performance Report {results['timestamp']} ---")
                        
                        # Calculate average response time
                        successful_tests = [t for t in results["endpoint_tests"] if t["success"]]
                        if successful_tests:
                            avg_response_time = sum(t["response_time_ms"] for t in successful_tests) / len(successful_tests)
                            print(f"Average Response Time: {avg_response_time:.2f}ms")
                        
                        for test in results["endpoint_tests"]:
                            status = "✅" if test["success"] else "❌"
                            if test["success"]:
                                print(f"{status} {test['endpoint']}: {test['response_time_ms']:.2f}ms")
                            else:
                                print(f"{status} {test['endpoint']}: ERROR - {test.get('error', 'Unknown error')}")
                        
                        # Show application metrics if available
                        if results["application_metrics"] and "error" not in results["application_metrics"]:
                            metrics = results["application_metrics"]
                            if "system" in metrics:
                                system = metrics["system"]
                                print(f"System: CPU {system.get('cpu_percent', 0):.1f}%, Memory {system.get('memory_percent', 0):.1f}%")
                        
                        # Save to file if specified
                        if args.output:
                            with open(args.output, 'w') as f:
                                json.dump(results, f, indent=2)
                        
                        print(f"Next check in {args.interval} seconds...\n")
                        await asyncio.sleep(args.interval)
                        
                    except KeyboardInterrupt:
                        print("\nMonitoring stopped by user")
                        break
                    except Exception as e:
                        print(f"Error during monitoring: {str(e)}")
                        await asyncio.sleep(args.interval)
            except KeyboardInterrupt:
                print("\nMonitoring stopped by user")
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

# Usage examples:
"""
# Test your deployed environments
python scripts/monitor_performance_fixed.py --env dev
python scripts/monitor_performance_fixed.py --env prod

# Continuous monitoring with authentication
python scripts/monitor_performance_fixed.py --env prod --auth-token "your-token" --continuous --interval 30

# Save results for analysis
python scripts/monitor_performance_fixed.py --env prod --output prod_performance.json
"""