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
    
    # Setup mock responses
    mock_supabase["folders"].get_template_folders_by_type = MagicMock()
    mock_supabase["folders"].get_template_folders_by_type.side_effect = [
        {"success": True, "folders": mock_user_folders},
        {"success": True, "folders": mock_official_folders},
        {"success": True, "folders": mock_org_folders}
    ]
    
    mock_supabase["folders"].get_user_pinned_folders = MagicMock(return_value=mock_pinned_folders)
    
    # Make the request
    response = test_client.get("/prompts/folders/", headers=valid_auth_header)
    
    # Assertions
    assert response.status_code == 200
    assert "success" in response.json()
    assert response.json()["success"] == True
    assert "userFolders" in response.json()
    assert "officialFolders" in response.json()
    assert "organizationFolders" in response.json()
    
    # Check the number of folders
    assert len(response.json()["userFolders"]) == 2
    assert len(response.json()["officialFolders"]) == 2
    assert len(response.json()["organizationFolders"]) == 1
    
    # Check pinned status
    assert response.json()["officialFolders"][0]["is_pinned"] == True
    assert response.json()["officialFolders"][1]["is_pinned"] == False

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
    
    # Setup mock responses
    mock_supabase["folders"].get_template_folders_by_type = MagicMock(
        return_value={"success": True, "folders": mock_official_folders}
    )
    
    mock_supabase["folders"].get_user_pinned_folders = MagicMock(return_value=mock_pinned_folders)
    
    # Make the request
    response = test_client.get("/prompts/folders/?type=official", headers=valid_auth_header)
    
    # Assertions
    assert response.status_code == 200
    assert "success" in response.json()
    assert response.json()["success"] == True
    assert "folders" in response.json()
    assert len(response.json()["folders"]) == 2
    
    # Check pinned status
    assert response.json()["folders"][0]["is_pinned"] == True
    assert response.json()["folders"][1]["is_pinned"] == False

def test_create_folder(test_client, mock_supabase, valid_auth_header, mock_authenticate_user):
    """Test creating a new folder."""
    # Mock the folder creation response
    created_folder = {
        "id": 6,
        "path": "/user/new-folder",
        "name": "New Folder",
        "description": "A new folder for testing",
        "type": "user",
        "tags": ["test"],
        "user_id": mock_authenticate_user,
        "created_at": "2025-03-15T12:00:00+00:00"
    }
    
    mock_supabase["folders"].table().insert().execute.return_value.data = [created_folder]
    
    # Make the request
    folder_data = {
        "name": "New Folder",
        "path": "/user/new-folder",
        "description": "A new folder for testing"
    }
    
    response = test_client.post("/prompts/folders/", json=folder_data, headers=valid_auth_header)
    
    # Assertions
    assert response.status_code == 200
    assert response.json()["success"] == True
    assert "folder" in response.json()
    assert response.json()["folder"]["id"] == 6
    assert response.json()["folder"]["name"] == "New Folder"
    assert response.json()["folder"]["path"] == "/user/new-folder"
    
    # Verify Supabase client was called correctly
    mock_supabase["folders"].table.assert_called_with("user_folders")
    mock_supabase["folders"].table().insert.assert_called_once()
    # Check that insert was called with appropriate data
    call_args = mock_supabase["folders"].table().insert.call_args[0][0]
    assert call_args["user_id"] == mock_authenticate_user
    assert call_args["name"] == "New Folder"
    assert call_args["path"] == "/user/new-folder"

def test_update_folder(test_client, mock_supabase, valid_auth_header, mock_authenticate_user):
    """Test updating an existing folder."""
    # Mock the verification response
    mock_supabase["folders"].table().select().eq().eq().execute.return_value.data = [{"id": 1}]
    
    # Mock the update response
    updated_folder = {
        "id": 1,
        "path": "/user/updated-folder",
        "name": "Updated Folder",
        "description": "An updated folder for testing",
        "type": "user",
        "tags": ["test", "updated"],
        "user_id": mock_authenticate_user,
        "created_at": "2025-03-15T12:00:00+00:00"
    }
    
    mock_supabase["folders"].table().update().eq().execute.return_value.data = [updated_folder]
    
    # Make the request
    folder_data = {
        "name": "Updated Folder",
        "path": "/user/updated-folder",
        "description": "An updated folder for testing"
    }
    
    response = test_client.put("/prompts/folders/1", json=folder_data, headers=valid_auth_header)
    
    # Assertions
    assert response.status_code == 200
    assert response.json()["success"] == True
    assert "folder" in response.json()
    assert response.json()["folder"]["id"] == 1
    assert response.json()["folder"]["name"] == "Updated Folder"
    assert response.json()["folder"]["path"] == "/user/updated-folder"
    
    # Verify Supabase client was called correctly
    mock_supabase["folders"].table.assert_called_with("user_folders")
    mock_supabase["folders"].table().select().eq.assert_called_with("id", 1)
    mock_supabase["folders"].table().select().eq().eq.assert_called_with("user_id", mock_authenticate_user)
    mock_supabase["folders"].table().update.assert_called_once()
    # Check that update was called with appropriate data
    call_args = mock_supabase["folders"].table().update.call_args[0][0]
    assert call_args["name"] == "Updated Folder"
    assert call_args["path"] == "/user/updated-folder"

def test_delete_folder(test_client, mock_supabase, valid_auth_header, mock_authenticate_user):
    """Test deleting a folder."""
    # Mock the verification response
    mock_supabase["folders"].table().select().eq().eq().execute.return_value.data = [{"id": 1}]
    
    # Mock the delete response
    mock_supabase["folders"].table().delete().eq().execute.return_value.data = [{"id": 1}]
    
    # Make the request
    response = test_client.delete("/prompts/folders/1", headers=valid_auth_header)
    
    # Assertions
    assert response.status_code == 200
    assert response.json()["success"] == True
    assert response.json()["message"] == "Folder deleted"
    
    # Verify Supabase client was called correctly
    mock_supabase["folders"].table.assert_called_with("user_folders")
    mock_supabase["folders"].table().select().eq.assert_called_with("id", 1)
    mock_supabase["folders"].table().select().eq().eq.assert_called_with("user_id", mock_authenticate_user)
    mock_supabase["folders"].table().delete.assert_called_once()
    mock_supabase["folders"].table().delete().eq.assert_called_with("id", 1)

def test_pin_folder(test_client, mock_supabase, valid_auth_header, mock_authenticate_user):
    """Test pinning a folder."""
    # Mock the pinned folders response
    mock_pinned_folders = {
        "official": [2],
        "organization": []
    }
    
    # Mock the update response
    updated_pinned_folders = [1, 2]
    
    # Set up the mocks
    mock_supabase["folders"].get_user_pinned_folders = MagicMock(return_value=mock_pinned_folders)
    mock_supabase["folders"].update_user_pinned_folders = MagicMock(
        return_value={"success": True, "pinned_folders": updated_pinned_folders}
    )
    
    # Make the request
    response = test_client.post("/prompts/folders/pin/1", headers=valid_auth_header)
    
    # Assertions
    assert response.status_code == 200
    assert response.json()["success"] == True
    assert "pinned_folders" in response.json()
    assert response.json()["pinned_folders"] == updated_pinned_folders
    
    # Verify helper functions were called correctly
    mock_supabase["folders"].get_user_pinned_folders.assert_called_with(mock_authenticate_user)
    mock_supabase["folders"].update_user_pinned_folders.assert_called_with(
        mock_authenticate_user, "official", [1, 2]
    )

def test_unpin_folder(test_client, mock_supabase, valid_auth_header, mock_authenticate_user):
    """Test unpinning a folder."""
    # Mock the pinned folders response
    mock_pinned_folders = {
        "official": [1, 2],
        "organization": []
    }
    
    # Mock the update response
    updated_pinned_folders = [2]
    
    # Set up the mocks
    mock_supabase["folders"].get_user_pinned_folders = MagicMock(return_value=mock_pinned_folders)
    mock_supabase["folders"].update_user_pinned_folders = MagicMock(
        return_value={"success": True, "pinned_folders": updated_pinned_folders}
    )
    
    # Make the request
    response = test_client.post("/prompts/folders/unpin/1", headers=valid_auth_header)
    
    # Assertions
    assert response.status_code == 200
    assert response.json()["success"] == True
    assert "pinned_folders" in response.json()
    assert response.json()["pinned_folders"] == updated_pinned_folders
    
    # Verify helper functions were called correctly
    mock_supabase["folders"].get_user_pinned_folders.assert_called_with(mock_authenticate_user)
    mock_supabase["folders"].update_user_pinned_folders.assert_called_with(
        mock_authenticate_user, "official", [2]
    )

def test_update_pinned_folders(test_client, mock_supabase, valid_auth_header, mock_authenticate_user):
    """Test updating all pinned folders."""
    # Mock the update responses
    mock_supabase["folders"].update_user_pinned_folders = MagicMock(
        side_effect=[
            {"success": True, "pinned_folders": [2, 3]},
            {"success": True, "pinned_folders": [5]}
        ]
    )
    
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
    assert response.json()["pinnedOfficialFolderIds"] == [2, 3]
    assert response.json()["pinnedOrganizationFolderIds"] == [5]
    
    # Verify helper functions were called correctly
    mock_supabase["folders"].update_user_pinned_folders.assert_any_call(
        mock_authenticate_user, "official", [2, 3]
    )
    mock_supabase["folders"].update_user_pinned_folders.assert_any_call(
        mock_authenticate_user, "organization", [5]
    )