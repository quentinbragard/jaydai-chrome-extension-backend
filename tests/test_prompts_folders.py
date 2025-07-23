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
    with patch('utils.prompts.folders.get_user_pinned_folders') as mock_get_pinned, \
         patch('utils.prompts.folders.update_user_pinned_folders') as mock_update_pinned, \
         patch('routes.prompts.folders.pin_folder.user_has_access_to_folder', return_value=True):
        
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
    with patch('utils.prompts.folders.get_user_pinned_folders') as mock_get_pinned, \
         patch('utils.prompts.folders.update_user_pinned_folders') as mock_update_pinned:
        
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


def test_get_folders_filters_inaccessible(test_client, mock_supabase, valid_auth_header, mock_authenticate_user):
    """Ensure folders from other owners are not returned."""
    user_id = mock_authenticate_user
    metadata = {"company_id": "company1", "organization_ids": ["org1"]}

    folders = [
        {"id": 1, "type": "user", "user_id": user_id},
        {"id": 2, "type": "user", "user_id": "other"},
        {"id": 3, "type": "company", "company_id": "company1"},
        {"id": 4, "type": "company", "company_id": "company2"},
        {"id": 5, "type": "organization", "organization_id": "org1"},
        {"id": 6, "type": "organization", "organization_id": "org2"},
    ]

    class QueryMock:
        def __init__(self, data):
            self.data = data
            self.filters = []
            self.or_str = None

        def select(self, *args, **kwargs):
            return self

        def eq(self, field, value):
            self.filters.append(("eq", field, value))
            return self

        def is_(self, field, value):
            self.filters.append(("is", field, value))
            return self

        def in_(self, field, values):
            self.filters.append(("in", field, values))
            return self

        def or_(self, cond):
            self.or_str = cond
            return self

        def execute(self):
            result = self.data
            for typ, field, value in self.filters:
                if typ == "eq":
                    result = [r for r in result if r.get(field) == value]
                elif typ == "is":
                    if value == "null":
                        result = [r for r in result if r.get(field) is None]
                    else:
                        result = [r for r in result if r.get(field) == value]
                elif typ == "in":
                    result = [r for r in result if r.get(field) in value]

            if self.or_str:
                conds = [c.split(".eq.") for c in self.or_str.split(",")]
                result = [r for r in result if any(str(r.get(f)) == v for f, v in conds)]

            return MagicMock(data=result)

    def table_side_effect(name):
        if name == "prompt_folders":
            return QueryMock(folders)
        return QueryMock([])

    mock_supabase["folders"].table.side_effect = table_side_effect

    with patch("routes.prompts.folders.helpers.supabase", mock_supabase["folders"]), \
         patch("routes.prompts.folders.get_folders.supabase", mock_supabase["folders"]), \
         patch("routes.prompts.folders.get_folders.get_user_metadata", return_value=metadata), \
         patch("utils.access_control.get_user_metadata", return_value=metadata):
        response = test_client.get("/prompts/folders/", headers=valid_auth_header)

    assert response.status_code == 200
    data = response.json()["data"]["folders"]
    assert [f["id"] for f in data.get("user", [])] == [1]
    assert [f["id"] for f in data.get("company", [])] == [3]
    assert [f["id"] for f in data.get("organization", [])] == [5]


def test_get_folder_by_id_without_nested(test_client, mock_supabase, valid_auth_header, mock_authenticate_user):
    """Folder should be returned without subfolders or templates when withNested is False."""

    folder = {
        "id": 1,
        "title": {"en": "Root"},
        "type": "user",
    }

    response_mock = MagicMock()
    response_mock.data = folder
    mock_supabase["folders"].table().select().eq().single().execute.return_value = response_mock

    with patch('routes.prompts.folders.get_folder_by_id.apply_access_conditions', side_effect=lambda q, *_: q), \
         patch('routes.prompts.folders.get_folder_by_id.user_has_access_to_folder', return_value=True), \
         patch('routes.prompts.folders.get_folder_by_id.supabase', mock_supabase["folders"]):
        response = test_client.get("/prompts/folders/1", headers=valid_auth_header)

    assert response.status_code == 200
    assert response.json()["success"] is True
    assert response.json()["data"]["id"] == 1


def test_get_folder_by_id_with_nested(test_client, mock_supabase, valid_auth_header, mock_authenticate_user):
    """Folder with subfolders and templates when withNested is True."""

    folders = [
        {"id": 1, "title": {"en": "Root"}, "type": "user", "parent_folder_id": None},
        {"id": 2, "title": {"en": "Child"}, "type": "user", "parent_folder_id": 1},
    ]

    templates = [
        {"id": 10, "folder_id": 1, "title": {"en": "T1"}, "content": {"en": "body"}, "type": "user"},
        {"id": 11, "folder_id": 2, "title": {"en": "T2"}, "content": {"en": "body"}, "type": "user"},
    ]

    class QueryMock:
        def __init__(self, data):
            self.data = data
            self.filters = []
            self.single_flag = False

        def select(self, *args, **kwargs):
            return self

        def eq(self, field, value):
            self.filters.append((field, value))
            return self

        def in_(self, field, values):
            self.filters.append((field, values))
            return self

        def single(self):
            self.single_flag = True
            return self

        def execute(self):
            result = self.data
            for field, value in self.filters:
                if isinstance(value, list):
                    result = [r for r in result if r.get(field) in value]
                else:
                    result = [r for r in result if r.get(field) == value]
            if self.single_flag:
                result = result[0] if result else None
            return MagicMock(data=result)

    def table_side_effect(name):
        if name == "prompt_folders":
            return QueryMock(folders)
        if name == "prompt_templates":
            return QueryMock(templates)
        return QueryMock([])

    mock_supabase["folders"].table.side_effect = table_side_effect

    with patch('routes.prompts.folders.get_folder_by_id.apply_access_conditions', side_effect=lambda q, *_: q), \
         patch('routes.prompts.folders.get_folder_by_id.user_has_access_to_folder', return_value=True), \
         patch('routes.prompts.folders.get_folder_by_id.supabase', mock_supabase["folders"]):
        response = test_client.get("/prompts/folders/1?withNested=true", headers=valid_auth_header)

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["id"] == 1
    assert len(data.get("templates", [])) == 1
    assert data.get("subfolders")[0]["id"] == 2
    assert len(data.get("subfolders")[0].get("templates", [])) == 1


def test_get_folder_by_id_not_found(test_client, mock_supabase, valid_auth_header, mock_authenticate_user):
    """Return 404 when folder does not exist."""

    response_mock = MagicMock()
    response_mock.data = None
    mock_supabase["folders"].table().select().eq().single().execute.return_value = response_mock

    with patch('routes.prompts.folders.get_folder_by_id.apply_access_conditions', side_effect=lambda q, *_: q), \
         patch('routes.prompts.folders.get_folder_by_id.user_has_access_to_folder', return_value=None), \
         patch('routes.prompts.folders.get_folder_by_id.supabase', mock_supabase["folders"]):
        response = test_client.get("/prompts/folders/99", headers=valid_auth_header)

    assert response.status_code == 404
