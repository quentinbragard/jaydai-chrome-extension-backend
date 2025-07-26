# utils/geolocation.py - Backend IP geolocation service

import requests
import logging
from typing import Dict, Optional, Any
from functools import lru_cache
import os
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class GeolocationService:
    def __init__(self):
        # You can use multiple providers for fallback
        self.providers = [
            {
                'name': 'ipapi',
                'url': 'http://ip-api.com/json/{ip}',
                'free_limit': 1000,  # requests per month
                'fields': ['country', 'regionName', 'city', 'lat', 'lon', 'timezone', 'query']
            },
            {
                'name': 'ipinfo',
                'url': 'https://ipinfo.io/{ip}/json',
                'token': os.getenv('IPINFO_TOKEN'),  # Optional paid token
                'free_limit': 50000,  # requests per month
            },
            {
                'name': 'ipgeolocation',
                'url': 'https://api.ipgeolocation.io/ipgeo',
                'token': os.getenv('IPGEOLOCATION_TOKEN'),  # Optional paid token
                'free_limit': 1000,  # requests per month
            }
        ]
        
        # Cache to avoid repeated API calls for same IP
        self._cache = {}
        self._cache_duration = timedelta(hours=24)  # Cache for 24 hours

    def _is_cache_valid(self, ip: str) -> bool:
        """Check if cached data for IP is still valid."""
        if ip not in self._cache:
            return False
        
        cached_time = self._cache[ip].get('cached_at')
        if not cached_time:
            return False
            
        return datetime.utcnow() - cached_time < self._cache_duration

    def _get_client_ip(self, request) -> str:
        """Extract client IP from request, handling proxies and load balancers."""
        # Check for common proxy headers
        forwarded_for = request.headers.get('X-Forwarded-For')
        if forwarded_for:
            # Take the first IP in the chain (client IP)
            return forwarded_for.split(',')[0].strip()
        
        real_ip = request.headers.get('X-Real-IP')
        if real_ip:
            return real_ip
        
        # Fallback to direct client IP
        return str(request.client.host) if request.client else '127.0.0.1'

    def _call_ipapi(self, ip: str) -> Optional[Dict[str, Any]]:
        """Call ip-api.com service (free, no token required)."""
        try:
            url = f"http://ip-api.com/json/{ip}?fields=status,message,country,countryCode,region,regionName,city,zip,lat,lon,timezone,isp,org,as,query"
            response = requests.get(url, timeout=3)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('status') == 'success':
                    return {
                        'country': data.get('country'),
                        'region': data.get('regionName'),
                        'city': data.get('city'),
                        'latitude': data.get('lat'),
                        'longitude': data.get('lon'),
                        'timezone': data.get('timezone'),
                        'ip': data.get('query', ip),
                        'provider': 'ip-api.com'
                    }
                else:
                    logger.warning(f"IP-API error for {ip}: {data.get('message')}")
            
        except Exception as e:
            logger.error(f"Failed to get location from ip-api.com for {ip}: {e}")
        
        return None

    def _call_ipinfo(self, ip: str) -> Optional[Dict[str, Any]]:
        """Call ipinfo.io service."""
        try:
            token = os.getenv('IPINFO_TOKEN')
            headers = {'Authorization': f'Bearer {token}'} if token else {}
            
            url = f"https://ipinfo.io/{ip}/json"
            response = requests.get(url, headers=headers, timeout=3)
            
            if response.status_code == 200:
                data = response.json()
                if 'error' not in data:
                    loc = data.get('loc', '').split(',')
                    latitude = float(loc[0]) if len(loc) >= 2 and loc[0] else None
                    longitude = float(loc[1]) if len(loc) >= 2 and loc[1] else None
                    
                    return {
                        'country': data.get('country'),
                        'region': data.get('region'),
                        'city': data.get('city'),
                        'latitude': latitude,
                        'longitude': longitude,
                        'timezone': data.get('timezone'),
                        'ip': ip,
                        'provider': 'ipinfo.io'
                    }
            
        except Exception as e:
            logger.error(f"Failed to get location from ipinfo.io for {ip}: {e}")
        
        return None

    @lru_cache(maxsize=1000)
    def get_location_by_ip(self, ip: str) -> Optional[Dict[str, Any]]:
        """Get location data for an IP address with caching."""
        
        # Skip private/local IPs
        if ip in ['127.0.0.1', 'localhost'] or ip.startswith('192.168.') or ip.startswith('10.'):
            return None
        
        # Check cache first
        if self._is_cache_valid(ip):
            cached_data = self._cache[ip].copy()
            cached_data.pop('cached_at', None)  # Remove cache metadata
            return cached_data
        
        # Try different providers in order
        for provider_info in self.providers:
            try:
                if provider_info['name'] == 'ipapi':
                    location_data = self._call_ipapi(ip)
                elif provider_info['name'] == 'ipinfo':
                    location_data = self._call_ipinfo(ip)
                else:
                    continue  # Skip unknown providers
                
                if location_data:
                    # Cache the result
                    location_data['cached_at'] = datetime.utcnow()
                    self._cache[ip] = location_data.copy()
                    
                    # Remove cache metadata from return value
                    location_data.pop('cached_at', None)
                    logger.info(f"Got location for {ip}: {location_data.get('city')}, {location_data.get('country')}")
                    return location_data
                    
            except Exception as e:
                logger.error(f"Provider {provider_info['name']} failed for {ip}: {e}")
                continue
        
        logger.warning(f"All geolocation providers failed for IP: {ip}")
        return None

    def get_location_from_request(self, request) -> Optional[Dict[str, Any]]:
        """Extract location from FastAPI request object."""
        client_ip = self._get_client_ip(request)
        print(f"Client IP======================>>>: {client_ip}")
        return self.get_location_by_ip(client_ip)

# Global instance
geolocation_service = GeolocationService()

def get_location_from_request(request) -> Optional[Dict[str, Any]]:
    """Convenience function to get location from request."""
    return geolocation_service.get_location_from_request(request)