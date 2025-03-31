import pytest
from unittest.mock import patch, MagicMock, create_autospec
from fastapi.testclient import TestClient
from main import app

@pytest.fixture
def test_client():
    """Create a test client for the FastAPI app."""
    return TestClient(app)

@pytest.fixture
def mock_supabase():
    """Mock the Supabase client used in the application."""
    with patch("routes.auth.supabase") as mock_auth_supabase, \
         patch("routes.save.supabase") as mock_save_supabase, \
         patch("routes.stats.supabase") as mock_stats_supabase, \
         patch("routes.notifications.supabase") as mock_notifications_supabase, \
         patch("routes.prompts.supabase") as mock_prompts_supabase, \
         patch("routes.prompts.folders.supabase") as mock_folders_supabase, \
         patch("routes.prompts.templates.supabase") as mock_templates_supabase, \
         patch("routes.user.supabase") as mock_user_supabase, \
         patch("utils.supabase_helpers.supabase") as mock_helpers_supabase, \
         patch("utils.notification_service.supabase") as mock_notification_service_supabase:
        
        # Configure all mocks to have the same behavior
        mocks = {
            "auth": mock_auth_supabase,
            "save": mock_save_supabase,
            "stats": mock_stats_supabase,
            "notifications": mock_notifications_supabase,
            "prompts": mock_prompts_supabase,
            "folders": mock_folders_supabase,
            "templates": mock_templates_supabase,
            "user": mock_user_supabase,
            "helpers": mock_helpers_supabase,
            "notification_service": mock_notification_service_supabase
        }
        
        # Setup common behavior for all mocks
        for name, mock in mocks.items():
            # Setup table method for database operations
            table_mock = MagicMock()
            select_mock = MagicMock()
            insert_mock = MagicMock()
            update_mock = MagicMock()
            delete_mock = MagicMock()
            
            # Create method chain
            table_mock.select.return_value = select_mock
            table_mock.insert.return_value = insert_mock
            table_mock.update.return_value = update_mock
            table_mock.delete.return_value = delete_mock
            
            mock.table.return_value = table_mock
            
            # Setup storage
            mock.storage = MagicMock()
            mock.storage.list_buckets = MagicMock()
            
            # Setup auth
            mock.auth = MagicMock()
            mock.auth.sign_up = MagicMock()
            mock.auth.sign_in_with_password = MagicMock()
            mock.auth.refresh_session = MagicMock()
            mock.auth.get_user = MagicMock()
            
            # If this is the helpers mock, setup the get_user method
            if name == "helpers":
                user_response = MagicMock()
                user_response.user = MagicMock()
                user_response.user.id = "00000000-0000-0000-0000-000000000000"
                mock.auth.get_user.return_value = user_response
            
            # If this is the folders mock, add helper functions
            if name == "folders":
                mock.get_template_folders_by_type = MagicMock()
                mock.get_user_pinned_folders = MagicMock()
                mock.update_user_pinned_folders = MagicMock()
                
            # If this is the templates mock, add helper functions  
            if name == "templates":
                mock.get_all_templates = MagicMock()
                mock.get_official_templates = MagicMock()
                mock.get_user_templates = MagicMock()
                mock.get_organization_templates = MagicMock()
        
        yield mocks

@pytest.fixture
def valid_auth_header():
    """Returns a valid authorization header for testing authenticated endpoints."""
    return {"Authorization": "Bearer fake_valid_token"}

@pytest.fixture
def mock_user_id():
    """Returns a mock user ID for testing."""
    return "00000000-0000-0000-0000-000000000000"

@pytest.fixture
def mock_authenticate_user(mock_supabase, mock_user_id):
    """Mock the authentication process to return a valid user ID."""
    helpers_supabase = mock_supabase["helpers"]
    # This is already setup in the mock_supabase fixture
    return mock_user_id