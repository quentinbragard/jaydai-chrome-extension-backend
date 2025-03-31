import pytest
from unittest.mock import patch, MagicMock

def test_get_templates(test_client, mock_supabase, valid_auth_header, mock_authenticate_user):
    """Test getting all templates."""
    # Mock the templates response
    mock_user_templates = [
        {
            "id": 1,
            "folder_id": 1,
            "title": "User Template 1",
            "content": "This is a user template",
            "type": "user",
            "tags": ["personal"],
            "locale": "en"
        },
        {
            "id": 2,
            "folder_id": 2,
            "title": "User Template 2",
            "content": "This is another user template",
            "type": "user",
            "tags": ["work"],
            "locale": "en"
        }
    ]
    
    mock_official_templates = [
        {
            "id": 3,
            "folder_id": 3,
            "title": "Official Template 1",
            "content": "This is an official template",
            "type": "official",
            "tags": ["starter"],
            "locale": "en"
        }
    ]
    
    mock_org_templates = [
        {
            "id": 4,
            "folder_id": 5,
            "title": "Organization Template 1",
            "content": "This is an organization template",
            "type": "organization",
            "tags": ["team"],
            "locale": "en"
        }
    ]
    
    # Mock folders
    mock_user_folders = [
        {"id": 1, "path": "/user/folder1", "templates": mock_user_templates[:1]},
        {"id": 2, "path": "/user/folder2", "templates": mock_user_templates[1:]}
    ]
    
    mock_official_folders = [
        {"id": 3, "path": "/official/folder1", "templates": mock_official_templates, "is_pinned": True}
    ]
    
    mock_org_folders = [
        {"id": 5, "path": "/org/folder1", "templates": mock_org_templates, "is_pinned": False}
    ]
    
    # Setup mock responses
    mock_supabase["templates"].get_all_templates = MagicMock(
        return_value={
            "success": True,
            "pinnedFolders": {
                "userTemplates": {
                    "templates": mock_user_templates,
                    "folders": mock_user_folders
                },
                "officialTemplates": {
                    "templates": mock_official_templates,
                    "folders": mock_official_folders
                },
                "organizationTemplates": {
                    "templates": mock_org_templates,
                    "folders": mock_org_folders
                }
            }
        }
    )
    
    # Make the request
    response = test_client.get("/prompts/templates/", headers=valid_auth_header)
    
    # Assertions
    assert response.status_code == 200
    assert "success" in response.json()
    assert response.json()["success"] == True
    assert "pinnedFolders" in response.json()
    assert "userTemplates" in response.json()["pinnedFolders"]
    assert "officialTemplates" in response.json()["pinnedFolders"]
    assert "organizationTemplates" in response.json()["pinnedFolders"]
    
    # Check template counts
    assert len(response.json()["pinnedFolders"]["userTemplates"]["templates"]) == 2
    assert len(response.json()["pinnedFolders"]["officialTemplates"]["templates"]) == 1
    assert len(response.json()["pinnedFolders"]["organizationTemplates"]["templates"]) == 1
    
    # Verify function was called with the right user_id
    mock_supabase["templates"].get_all_templates.assert_called_with(mock_authenticate_user)

def test_get_templates_by_type(test_client, mock_supabase, valid_auth_header, mock_authenticate_user):
    """Test getting templates by type."""
    # Mock the templates response for a specific type
    mock_official_templates = [
        {
            "id": 3,
            "folder_id": 3,
            "title": "Official Template 1",
            "content": "This is an official template",
            "type": "official",
            "tags": ["starter"],
            "locale": "en"
        },
        {
            "id": 4,
            "folder_id": 3,
            "title": "Official Template 2",
            "content": "This is another official template",
            "type": "official",
            "tags": ["advanced"],
            "locale": "en"
        }
    ]
    
    mock_folders = ["official/folder1", "official/folder2"]
    
    # Setup mock response
    mock_supabase["templates"].get_official_templates = MagicMock(
        return_value={
            "success": True,
            "templates": mock_official_templates,
            "folders": mock_folders
        }
    )
    
    # Make the request
    response = test_client.get("/prompts/templates/?type=official", headers=valid_auth_header)
    
    # Assertions
    assert response.status_code == 200
    assert "success" in response.json()
    assert response.json()["success"] == True
    assert "templates" in response.json()
    assert "folders" in response.json()
    assert len(response.json()["templates"]) == 2
    assert response.json()["templates"][0]["title"] == "Official Template 1"
    
    # Verify function was called correctly
    mock_supabase["templates"].get_official_templates.assert_called_with(mock_authenticate_user)

def test_create_template(test_client, mock_supabase, valid_auth_header, mock_authenticate_user):
    """Test creating a new template."""
    # Mock the template creation response
    created_template = {
        "id": 5,
        "folder_id": 1,
        "title": "New Template",
        "content": "This is a new template",
        "type": "user",
        "tags": ["test"],
        "locale": "en",
        "created_at": "2025-03-15T12:00:00+00:00"
    }
    
    mock_supabase["templates"].table().insert().execute.return_value.data = [created_template]
    
    # Make the request
    template_data = {
        "folder_id": 1,
        "title": "New Template",
        "content": "This is a new template",
        "type": "user",
        "tags": ["test"],
        "locale": "en"
    }
    
    response = test_client.post("/prompts/templates/", json=template_data, headers=valid_auth_header)
    
    # Assertions
    assert response.status_code == 200
    assert response.json()["success"] == True
    assert "template" in response.json()
    assert response.json()["template"]["id"] == 5
    assert response.json()["template"]["title"] == "New Template"
    
    # Verify Supabase client was called correctly
    mock_supabase["templates"].table.assert_called_with("prompt_templates")
    mock_supabase["templates"].table().insert.assert_called_once()
    # Check that insert was called with appropriate data
    call_args = mock_supabase["templates"].table().insert.call_args[0][0]
    assert call_args["type"] == "user"
    assert call_args["title"] == "New Template"
    assert call_args["content"] == "This is a new template"

def test_update_template(test_client, mock_supabase, valid_auth_header, mock_authenticate_user):
    """Test updating an existing template."""
    # Mock the verification response
    mock_supabase["templates"].table().select().eq().eq().execute.return_value.data = [{"id": "1"}]
    
    # Mock the update response
    updated_template = {
        "id": "1",
        "folder_id": 1,
        "title": "Updated Template",
        "content": "This is an updated template",
        "type": "user",
        "tags": ["test", "updated"],
        "locale": "en",
        "created_at": "2025-03-15T12:00:00+00:00"
    }
    
    mock_supabase["templates"].table().update().eq().execute.return_value.data = [updated_template]
    
    # Make the request
    template_data = {
        "folder_id": 1,
        "title": "Updated Template",
        "content": "This is an updated template",
        "type": "user",
        "tags": ["test", "updated"],
        "locale": "en"
    }
    
    response = test_client.put("/prompts/templates/1", json=template_data, headers=valid_auth_header)
    
    # Assertions
    assert response.status_code == 200
    assert response.json()["success"] == True
    assert "template" in response.json()
    assert response.json()["template"]["id"] == "1"
    assert response.json()["template"]["title"] == "Updated Template"
    
    # Verify Supabase client was called correctly
    mock_supabase["templates"].table.assert_called_with("prompt_templates")
    mock_supabase["templates"].table().select().eq.assert_called_with("id", "1")
    mock_supabase["templates"].table().select().eq().eq.assert_called_with("user_id", mock_authenticate_user)
    mock_supabase["templates"].table().update.assert_called_once()

def test_delete_template(test_client, mock_supabase, valid_auth_header, mock_authenticate_user):
    """Test deleting a template."""
    # Mock the verification response
    mock_supabase["templates"].table().select().eq().eq().execute.return_value.data = [{"id": "1"}]
    
    # Mock the delete response
    mock_supabase["templates"].table().delete().eq().execute.return_value.data = [{"id": "1"}]
    
    # Make the request
    response = test_client.delete("/prompts/templates/1", headers=valid_auth_header)
    
    # Assertions
    assert response.status_code == 200
    assert response.json()["success"] == True
    assert response.json()["message"] == "Template deleted"
    
    # Verify Supabase client was called correctly
    mock_supabase["templates"].table.assert_called_with("prompt_templates")
    mock_supabase["templates"].table().select().eq.assert_called_with("id", "1")
    mock_supabase["templates"].table().select().eq().eq.assert_called_with("user_id", mock_authenticate_user)
    mock_supabase["templates"].table().delete.assert_called_once()
    mock_supabase["templates"].table().delete().eq.assert_called_with("id", "1")

def test_track_template_usage(test_client, mock_supabase, valid_auth_header, mock_authenticate_user):
    """Test tracking template usage."""
    # Mock the template response
    template = {
        "id": "1",
        "folder_id": 1,
        "title": "Test Template",
        "content": "This is a test template",
        "type": "user",
        "tags": ["test"],
        "locale": "en",
        "usage_count": 5,
        "last_used_at": "2025-03-10T12:00:00+00:00"
    }
    
    mock_supabase["templates"].table().select().eq().single().execute.return_value.data = template
    
    # Mock the update response
    updated_template = {
        **template,
        "usage_count": 6,
        "last_used_at": "2025-03-15T12:00:00+00:00"
    }
    
    mock_supabase["templates"].table().update().eq().execute.return_value.data = [updated_template]
    
    # Make the request
    response = test_client.post("/prompts/templates/use/1", headers=valid_auth_header)
    
    # Assertions
    assert response.status_code == 200
    assert response.json()["success"] == True
    assert "usage_count" in response.json()
    assert response.json()["usage_count"] == 6
    
    # Verify Supabase client was called correctly
    mock_supabase["templates"].table.assert_called_with("prompt_templates")
    mock_supabase["templates"].table().select().eq.assert_called_with("id", "1")
    mock_supabase["templates"].table().update.assert_called_once()
    # Check that update increased usage_count by 1
    call_args = mock_supabase["templates"].table().update.call_args[0][0]
    assert call_args["usage_count"] == 6