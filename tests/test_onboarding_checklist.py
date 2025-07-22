from unittest.mock import patch, MagicMock


def _setup_supabase_mock(record):
    """Create a side effect for supabase.table to return the given record."""

    def table_side_effect(table_name):
        table_mock = MagicMock()
        select_mock = MagicMock()
        eq_mock = MagicMock()
        single_mock = MagicMock()
        execute_mock = MagicMock()
        execute_mock.data = record

        table_mock.select.return_value = select_mock
        select_mock.eq.return_value = eq_mock
        eq_mock.maybe_single.return_value = single_mock
        single_mock.execute.return_value = execute_mock
        return table_mock

    return table_side_effect


def test_checklist_with_existing_metadata(test_client, valid_auth_header, mock_authenticate_user):
    metadata = {
        "first_template_created": True,
        "first_template_used": False,
        "first_block_created": True,
        "keyboard_shortcut_used": False,
        "onboarding_dismissed": False,
    }

    with patch("routes.onboarding.checklist.supabase") as supabase_mock:
        supabase_mock.table.side_effect = _setup_supabase_mock(metadata)

        response = test_client.get("/onboarding/checklist", headers=valid_auth_header)

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["first_template_created"] is True
    assert data["completed_count"] == 2
    assert data["total_count"] == 4


def test_checklist_without_metadata(test_client, valid_auth_header, mock_authenticate_user):
    with patch("routes.onboarding.checklist.supabase") as supabase_mock:
        supabase_mock.table.side_effect = _setup_supabase_mock(None)

        response = test_client.get("/onboarding/checklist", headers=valid_auth_header)

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["completed_count"] == 0
    assert data["progress"] == "0/4"
