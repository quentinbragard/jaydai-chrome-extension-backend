# scripts/debug_production.py
"""
Debug script to identify production issues
"""
import asyncio
import aiohttp
import json
import sys
from datetime import datetime

class ProductionDebugger:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip('/')
        self.session = None
        
    async def __aenter__(self):
        timeout = aiohttp.ClientTimeout(total=30)
        self.session = aiohttp.ClientSession(timeout=timeout)
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def debug_endpoint(self, endpoint: str, headers: dict = None):
        """Debug a specific endpoint with detailed error info"""
        url = f"{self.base_url}{endpoint}"
        
        try:
            async with self.session.get(url, headers=headers) as response:
                content = await response.text()
                
                print(f"\n🔍 DEBUG: {endpoint}")
                print(f"Status: {response.status}")
                print(f"Headers: {dict(response.headers)}")
                
                try:
                    json_content = json.loads(content)
                    print(f"Response: {json.dumps(json_content, indent=2)}")
                except:
                    print(f"Raw Response: {content[:500]}...")
                
                return {
                    "endpoint": endpoint,
                    "status": response.status,
                    "content": content,
                    "headers": dict(response.headers)
                }
        except Exception as e:
            print(f"❌ Error calling {endpoint}: {str(e)}")
            return {"endpoint": endpoint, "error": str(e)}
    
    async def test_authentication(self, token: str):
        """Test if authentication is working"""
        headers = {"Authorization": f"Bearer {token}"}
        
        # Test a simple authenticated endpoint
        print("🔐 Testing Authentication...")
        result = await self.debug_endpoint("/user/metadata", headers)
        
        if result.get("status") == 500:
            print("❌ Authentication causing 500 errors")
            print("This suggests issues with:")
            print("  - Token validation")
            print("  - Database connection in auth middleware")
            print("  - Supabase configuration")
        elif result.get("status") == 401:
            print("❌ Token is invalid or expired")
        elif result.get("status") == 200:
            print("✅ Authentication working")
        
        return result
    
    async def test_database_connection(self):
        """Test database connectivity"""
        print("\n🗄️ Testing Database Connection...")
        
        # Health endpoint should test database
        result = await self.debug_endpoint("/health")
        
        if result.get("status") == 200:
            try:
                health_data = json.loads(result["content"])
                db_status = health_data.get("components", {}).get("database", {})
                print(f"Database Status: {db_status}")
                
                if db_status.get("status") != "healthy":
                    print("❌ Database connection issues detected")
                    print("Check:")
                    print("  - SUPABASE_URL environment variable")
                    print("  - SUPABASE_SERVICE_ROLE_KEY environment variable")
                    print("  - Network connectivity to Supabase")
                else:
                    print("✅ Database connection healthy")
            except:
                print("❌ Could not parse health response")
        
        return result
    
    async def analyze_slow_endpoints(self, headers: dict = None):
        """Analyze why endpoints are slow"""
        print("\n🐌 Analyzing Slow Endpoints...")
        
        # Test folders endpoint specifically
        result = await self.debug_endpoint("/prompts/folders", headers)
        
        print("\nSlow endpoint analysis:")
        print("❌ /prompts/folders taking 932ms suggests:")
        print("  1. N+1 query problem (multiple database calls)")
        print("  2. No caching layer")
        print("  3. Inefficient access control queries")
        print("  4. Large data sets being processed")
        
        return result

async def main():
    if len(sys.argv) < 2:
        print("Usage: python debug_production.py <environment> [auth_token]")
        print("Environment: dev, prod")
        sys.exit(1)
    
    env = sys.argv[1]
    auth_token = sys.argv[2] if len(sys.argv) > 2 else None
    
    urls = {
        "dev": "https://api.dev.jayd.ai",
        "prod": "https://api.prod.jayd.ai"
    }
    
    if env not in urls:
        print(f"Invalid environment: {env}")
        sys.exit(1)
    
    base_url = urls[env]
    print(f"🔍 Debugging {env} environment: {base_url}")
    
    async with ProductionDebugger(base_url) as debugger:
        # Test basic connectivity
        await debugger.debug_endpoint("/")
        
        # Test database
        await debugger.test_database_connection()
        
        # Test authentication if token provided
        if auth_token:
            headers = {"Authorization": f"Bearer {auth_token}"}
            await debugger.test_authentication(auth_token)
            await debugger.analyze_slow_endpoints(headers)
        else:
            print("\n⚠️ No auth token provided, skipping authenticated endpoint tests")
            print("Run with: python debug_production.py prod YOUR_TOKEN")

if __name__ == "__main__":
    asyncio.run(main())

