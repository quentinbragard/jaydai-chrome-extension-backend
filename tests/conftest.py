import pytest
from unittest.mock import patch, MagicMock
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
            mock.table.return_value = table_mock
            
            # Create method chains that return appropriate mocks
            select_mock = MagicMock()
            eq_mock = MagicMock()
            single_mock = MagicMock()
            execute_mock = MagicMock()
            execute_mock.data = []
            
            # Setup method chain for select
            table_mock.select.return_value = select_mock
            select_mock.eq.return_value = eq_mock
            eq_mock.eq.return_value = eq_mock  # Allow chaining multiple eq calls
            eq_mock.single.return_value = single_mock
            single_mock.execute.return_value = execute_mock
            eq_mock.execute.return_value = execute_mock
            
            # Method chains for insert
            insert_mock = MagicMock()
            table_mock.insert.return_value = insert_mock
            insert_mock.execute.return_value = execute_mock
            
            # Method chains for update
            update_mock = MagicMock()
            table_mock.update.return_value = update_mock
            update_mock.eq.return_value = eq_mock
            
            # Method chains for delete
            delete_mock = MagicMock()
            table_mock.delete.return_value = delete_mock
            delete_mock.eq.return_value = eq_mock
            
            # Setup mock for in_() method
            select_mock.in_.return_value = eq_mock
            eq_mock.in_.return_value = eq_mock
            
            # Setup mock for is_() method
            select_mock.is_.return_value = eq_mock
            eq_mock.is_.return_value = eq_mock
            
            # Setup order method
            select_mock.order.return_value = eq_mock
            
            # Setup storage
            mock.storage = MagicMock()
            
            # Setup auth
            mock.auth = MagicMock()
            mock.auth.sign_up = MagicMock()
            mock.auth.sign_in_with_password = MagicMock()
            mock.auth.refresh_session = MagicMock()
            mock.auth.get_user = MagicMock()
            
            # Setup user for auth responses with correct attribute structure
            user = MagicMock()
            user.id = "00000000-0000-0000-0000-000000000000"
            user.email = "test@example.com"
            
            session = MagicMock()
            session.access_token = "fake_token"
            session.refresh_token = "fake_refresh_token"
            session.expires_at = 3600
            
            auth_response = MagicMock()
            auth_response.user = user
            auth_response.session = session
            
            # Set the auth response
            if name == "helpers":
                mock.auth.get_user.return_value = auth_response
            
            # If this is the folders mock, add helper functions
            if name == "folders":
                mock.get_template_folders_by_type = MagicMock()
                mock.get_template_folders_by_type.return_value = {"success": True, "folders": []}
                
                mock.get_user_pinned_folders = MagicMock()
                mock.get_user_pinned_folders.return_value = {"official": [], "organization": []}
                
                mock.update_user_pinned_folders = MagicMock()
                mock.update_user_pinned_folders.return_value = {"success": True, "pinned_folders": []}
                
            # If this is the templates mock, add helper functions  
            if name == "templates":
                mock.get_all_templates = MagicMock()
                mock.get_all_templates.return_value = {
                    "success": True,
                    "pinnedFolders": {
                        "userTemplates": {"templates": [], "folders": []},
                        "officialTemplates": {"templates": [], "folders": []},
                        "organizationTemplates": {"templates": [], "folders": []}
                    }
                }
                
                mock.get_official_templates = MagicMock()
                mock.get_official_templates.return_value = {
                    "success": True,
                    "templates": [],
                    "folders": []
                }
                
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
    with patch('utils.notification_service.NotificationService.create_welcome_notification'):
        return mock_user_id