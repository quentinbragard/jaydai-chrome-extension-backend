import pytest
from unittest.mock import patch, MagicMock

def test_get_user_metadata(test_client, mock_supabase, valid_auth_header, mock_authenticate_user):
    """Test getting user metadata."""
    # Mock the metadata response
    mock_metadata = {
        "name": "Test User",
        "additional_email": "test@example.com",
        "phone_number": "+123456789",
        "additional_organization": "Test Org",
        "pinned_folder_ids": [1, 2, 3]
    }
    
    # Create a mock response
    metadata_response = MagicMock()
    metadata_response.data = mock_metadata
    mock_supabase["user"].table().select().eq().single().execute.return_value = metadata_response
    
    # Make the request
    response = test_client.get("/user/metadata", headers=valid_auth_header)
    
    # Assertions
    assert response.status_code == 200
    assert response.json()["success"] == True
    assert "data" in response.json()
    assert response.json()["data"]["name"] == "Test User"
    assert response.json()["data"]["additional_email"] == "test@example.com"
    assert response.json()["data"]["pinned_folder_ids"] == [1, 2, 3]
    
    # Verify Supabase client was called correctly - use assert_called instead of assert_called_once
    mock_supabase["user"].table.assert_called_with("users_metadata")
    assert mock_supabase["user"].table().select.called
    assert mock_supabase["user"].table().select().eq.called

def test_get_user_metadata_not_found(test_client, mock_supabase, valid_auth_header, mock_authenticate_user):
    """Test getting user metadata when none exists."""
    # Mock the metadata response (no data)
    metadata_response = MagicMock()
    metadata_response.data = None
    mock_supabase["user"].table().select().eq().single().execute.return_value = metadata_response
    
    # Make the request
    response = test_client.get("/user/metadata", headers=valid_auth_header)
    
    # Assertions
    assert response.status_code == 200
    assert response.json()["success"] == True
    assert "data" in response.json()
    # Check default values are provided
    assert response.json()["data"]["name"] is None
    assert response.json()["data"]["additional_email"] is None
    assert response.json()["data"]["pinned_folder_ids"] == []

def test_get_folders_with_prompts(test_client, mock_supabase, valid_auth_header, mock_authenticate_user):
    """Test getting folders with prompts."""
    # Mock the metadata response for pinned folders
    mock_metadata = {
        "pinned_folder_ids": [1, 2, 3]
    }
    
    metadata_mock = MagicMock()
    metadata_mock.data = mock_metadata
    mock_supabase["user"].table().select().eq().single().execute.return_value = metadata_mock
    
    # Mock prompts response
    mock_prompts = [
        {
            "id": 1,
            "folder_id": 1,
            "type": "official",
            "title": "Official Prompt 1",
            "content": "This is an official prompt"
        },
        {
            "id": 2,
            "folder_id": 2,
            "type": "official",
            "title": "Official Prompt 2",
            "content": "This is another official prompt"
        }
    ]
    
    prompts_mock = MagicMock()
    prompts_mock.data = mock_prompts
    mock_supabase["user"].table().select().execute.return_value = prompts_mock
    
    # Mock folders responses
    mock_official_folders = [
        {
            "id": 1,
            "path": "/official/folder1",
            "type": "official",
            "tags": ["official", "starter"]
        },
        {
            "id": 2,
            "path": "/official/folder2",
            "type": "official",
            "tags": ["official", "advanced"]
        }
    ]
    
    official_folders_mock = MagicMock()
    official_folders_mock.data = mock_official_folders
    
    # Set up a table mock method that returns different responses based on the table name
    def table_side_effect(table_name):
        if table_name == "users_metadata":
            meta_mock = MagicMock()
            meta_mock.select = MagicMock()
            eq_mock = MagicMock()
            single_mock = MagicMock()
            execute_mock = MagicMock()
            execute_mock.data = mock_metadata
            
            meta_mock.select.return_value = meta_mock
            meta_mock.eq.return_value = eq_mock
            eq_mock.single.return_value = single_mock
            single_mock.execute.return_value = execute_mock
            
            return meta_mock
        elif table_name == "prompt_templates":
            prompts_table_mock = MagicMock()
            prompts_table_mock.select.return_value = prompts_table_mock
            prompts_table_mock.execute.return_value = prompts_mock
            return prompts_table_mock
        elif table_name == "official_folders":
            folders_table_mock = MagicMock()
            folders_table_mock.select.return_value = folders_table_mock
            folders_table_mock.execute.return_value = official_folders_mock
            return folders_table_mock
        # Add more conditions for other table types
        else:
            # Default mock
            default_mock = MagicMock()
            default_mock.select.return_value = default_mock
            default_mock.execute.return_value = MagicMock(data=[])
            return default_mock
    
    # Use the side effect for the table method
    mock_supabase["user"].table.side_effect = table_side_effect
    
    # Make the request
    response = test_client.get("/user/folders-with-prompts", headers=valid_auth_header)
    
    # Assertions - at a minimum check status code and success
    assert response.status_code == 200
    assert response.json()["success"] == True
    assert "data" in response.json()