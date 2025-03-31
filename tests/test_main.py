import pytest
from unittest.mock import patch, MagicMock

def test_root_endpoint(test_client):
    """Test the root endpoint returns a welcome message."""
    response = test_client.get("/")
    assert response.status_code == 200
    assert "message" in response.json()
    assert response.json()["message"] == "Welcome to Archimind API"
    assert response.json()["status"] == "running"

def test_health_check_healthy(test_client, mock_supabase):
    """Test the health check endpoint when all services are healthy."""
    # Configure the mock to simulate a successful database connection
    mock_supabase["stats"].storage.list_buckets.return_value = []
    
    # Create a mock for time.time() to return a constant value
    with patch('time.time', return_value=1617321600.0):
        response = test_client.get("/health")
    
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"
    assert "components" in response.json()
    assert response.json()["components"]["api"]["status"] == "healthy"
    assert response.json()["components"]["database"]["status"] == "healthy"

def test_health_check_degraded(test_client, mock_supabase):
    """Test the health check endpoint when database is unhealthy."""
    # Patch the database connection to raise an exception
    mock_supabase["stats"].storage.list_buckets.side_effect = Exception("Database connection error")
    
    # Make the request - ensure we check the response code properly
    with patch('time.time', return_value=1617321600.0):  # Mock time for consistent results
        response = test_client.get("/health")
    
    # Verify the mock was called
    assert mock_supabase["stats"].storage.list_buckets.called
    
    # Check the response - either degraded status at 503 or at 200
    if response.status_code == 503:
        assert response.json()["status"] == "degraded"
    else:
        assert response.json()["status"] == "degraded"
        assert response.json()["components"]["database"]["status"] == "unhealthy"