import pytest
from unittest.mock import patch, MagicMock

def test_get_folders(test_client, mock_supabase, valid_auth_header, mock_authenticate_user):
    """Test getting all folders."""
    # Mock the folder responses
    mock_user_folders = [
        {
            "id": 1,
            "path": "/user/folder1",
            "type": "user",
            "tags": ["personal"],
            "user_id": mock_authenticate_user
        },
        {
            "id": 2,
            "path": "/user/folder2",
            "type": "user",
            "tags": ["work"],
            "user_id": mock_authenticate_user
        }
    ]
    
    mock_official_folders = [
        {
            "id": 3,
            "path": "/official/folder1",
            "type": "official",
            "tags": ["starter"]
        },
        {
            "id": 4,
            "path": "/official/folder2",
            "type": "official",
            "tags": ["advanced"]
        }
    ]
    
    mock_org_folders = [
        {
            "id": 5,
            "path": "/org/folder1",
            "type": "organization",
            "tags": ["team"]
        }
    ]
    
    # Mock user metadata for pinned folders
    mock_pinned_folders = {
        "official": [3],
        "organization": []
    }
    
    # Directly patch the function calls in the route
    with patch('routes.prompts.folders.get_template_folders_by_type') as mock_get_folders, \
         patch('routes.prompts.folders.get_user_pinned_folders') as mock_get_pinned:
        
        # Setup mock responses
        mock_get_folders.side_effect = [
            {"success": True, "folders": mock_user_folders},
            {"success": True, "folders": mock_official_folders},
            {"success": True, "folders": mock_org_folders}
        ]
        
        mock_get_pinned.return_value = mock_pinned_folders
        
        # Make the request
        response = test_client.get("/prompts/folders/", headers=valid_auth_header)
    
    # Assertions
    assert response.status_code == 200
    assert "success" in response.json()
    assert response.json()["success"] == True
    
    # We don't verify the exact calls since we're patching the functions directly

def test_get_folders_by_type(test_client, mock_supabase, valid_auth_header, mock_authenticate_user):
    """Test getting folders by type."""
    # Mock the folder response
    mock_official_folders = [
        {
            "id": 3,
            "path": "/official/folder1",
            "type": "official",
            "tags": ["starter"]
        },
        {
            "id": 4,
            "path": "/official/folder2",
            "type": "official",
            "tags": ["advanced"]
        }
    ]
    
    # Mock user metadata for pinned folders
    mock_pinned_folders = {
        "official": [3],
        "organization": []
    }
    
    # Directly patch the function calls in the route
    with patch('routes.prompts.folders.get_template_folders_by_type') as mock_get_folders, \
         patch('routes.prompts.folders.get_user_pinned_folders') as mock_get_pinned:
        
        # Setup mock responses
        mock_get_folders.return_value = {
            "success": True,
            "folders": mock_official_folders
        }
        
        mock_get_pinned.return_value = mock_pinned_folders
        
        # Make the request
        response = test_client.get("/prompts/folders/?type=official", headers=valid_auth_header)
    
    # Assertions
    assert response.status_code == 200
    assert "success" in response.json()
    assert response.json()["success"] == True

def test_pin_folder(test_client, mock_supabase, valid_auth_header, mock_authenticate_user):
    """Test pinning a folder."""
    # Mock the pinned folders response
    mock_pinned_folders = {
        "official": [2],
        "organization": []
    }
    
    # Mock the update response
    updated_pinned_folders = [1, 2]
    
    # Directly patch the function calls in the route
    with patch('routes.prompts.folders.get_user_pinned_folders') as mock_get_pinned, \
         patch('routes.prompts.folders.update_user_pinned_folders') as mock_update_pinned:
        
        # Setup mock responses
        mock_get_pinned.return_value = mock_pinned_folders
        mock_update_pinned.return_value = {
            "success": True,
            "pinned_folders": updated_pinned_folders
        }
        
        # Make the request
        response = test_client.post("/prompts/folders/pin/1", headers=valid_auth_header)
    
    # Assertions
    assert response.status_code == 200
    assert response.json()["success"] == True

def test_unpin_folder(test_client, mock_supabase, valid_auth_header, mock_authenticate_user):
    """Test unpinning a folder."""
    # Mock the pinned folders response
    mock_pinned_folders = {
        "official": [1, 2],
        "organization": []
    }
    
    # Mock the update response
    updated_pinned_folders = [2]
    
    # Directly patch the function calls in the route
    with patch('routes.prompts.folders.get_user_pinned_folders') as mock_get_pinned, \
         patch('routes.prompts.folders.update_user_pinned_folders') as mock_update_pinned:
        
        # Setup mock responses
        mock_get_pinned.return_value = mock_pinned_folders
        mock_update_pinned.return_value = {
            "success": True,
            "pinned_folders": updated_pinned_folders
        }
        
        # Make the request
        response = test_client.post("/prompts/folders/unpin/1", headers=valid_auth_header)
    
    # Assertions
    assert response.status_code == 200
    assert response.json()["success"] == True

def test_update_pinned_folders(test_client, mock_supabase, valid_auth_header, mock_authenticate_user):
    """Test updating all pinned folders."""
    # Directly patch the function calls in the route
    with patch('routes.prompts.folders.update_user_pinned_folders') as mock_update_pinned:
        
        # Setup mock responses to be returned for each call
        mock_update_pinned.side_effect = [
            {"success": True, "pinned_folders": [2, 3]},
            {"success": True, "pinned_folders": [5]}
        ]
        
        # Make the request
        request_data = {
            "official_folder_ids": [2, 3],
            "organization_folder_ids": [5]
        }
        
        response = test_client.post("/prompts/folders/update-pinned", json=request_data, headers=valid_auth_header)
    
    # Assertions
    assert response.status_code == 200
    assert response.json()["success"] == True
    assert "pinnedOfficialFolderIds" in response.json()
    assert "pinnedOrganizationFolderIds" in response.json()
    
    # Verify the function was called twice
    assert mock_update_pinned.call_count == 2