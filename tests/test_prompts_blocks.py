import pytest
from unittest.mock import MagicMock


def test_get_blocks_published_filter(test_client, mock_supabase, valid_auth_header, mock_authenticate_user):
    returned_blocks = [
        {
            "id": 1,
            "title": {"en": "Block 1"},
            "content": {"en": "Content"},
            "type": "role",
            "published": True,
            "created_at": "2025-03-15T12:00:00+00:00"
        }
    ]

    execute_mock = MagicMock()
    execute_mock.data = returned_blocks
    mock_supabase["blocks"].table().select().eq().execute.return_value = execute_mock
    select_mock = mock_supabase["blocks"].table().select.return_value

    response = test_client.get("/prompts/blocks/?published=true", headers=valid_auth_header)

    assert response.status_code == 200
    assert response.json()["success"] is True
    select_mock.eq.assert_any_call("published", True)


def test_get_blocks_search(test_client, mock_supabase, valid_auth_header, mock_authenticate_user):
    returned_blocks = [
        {
            "id": 2,
            "title": {"en": "Search Match"},
            "content": {"en": "Something"},
            "type": "role",
            "published": True,
            "created_at": "2025-03-15T12:00:00+00:00"
        }
    ]

    execute_mock = MagicMock()
    execute_mock.data = returned_blocks
    mock_supabase["blocks"].table().select().eq().execute.return_value = execute_mock
    select_mock = mock_supabase["blocks"].table().select.return_value
    eq_mock = select_mock.eq.return_value

    response = test_client.get("/prompts/blocks/?q=Search", headers=valid_auth_header)

    assert response.status_code == 200
    assert response.json()["success"] is True
    select_mock.or_.assert_any_call("title.ilike.%Search%,content.ilike.%Search%")
