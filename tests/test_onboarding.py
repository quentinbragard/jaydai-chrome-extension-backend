import pytest
from unittest.mock import patch, MagicMock


def test_get_onboarding_template_from_pinned_folder(test_client, valid_auth_header, mock_authenticate_user):
    template = {
        "id": 1,
        "folder_id": 10,
        "title": {"en": "Welcome"},
        "content": {"en": "Body"},
        "type": "official",
        "created_at": "2025-01-01T00:00:00+00:00",
        "usage_count": 0,
    }

    def table_side_effect(table_name):
        if table_name == "users_metadata":
            table_mock = MagicMock()
            select_mock = MagicMock()
            eq_mock = MagicMock()
            single_mock = MagicMock()
            execute_mock = MagicMock()
            execute_mock.data = {"pinned_folder_ids": [10]}
            table_mock.select.return_value = select_mock
            select_mock.eq.return_value = eq_mock
            eq_mock.single.return_value = single_mock
            single_mock.execute.return_value = execute_mock
            return table_mock
        elif table_name == "prompt_templates":
            table_mock = MagicMock()
            select_mock = MagicMock()
            eq_mock = MagicMock()
            order_mock = MagicMock()
            limit_mock = MagicMock()
            execute_mock = MagicMock()
            execute_mock.data = [template]
            table_mock.select.return_value = select_mock
            select_mock.eq.return_value = eq_mock
            eq_mock.order.return_value = order_mock
            order_mock.limit.return_value = limit_mock
            limit_mock.execute.return_value = execute_mock
            return table_mock
        return MagicMock()

    with patch('routes.onboarding.which_template.supabase') as supabase_mock, \
         patch('routes.onboarding.which_template.apply_access_conditions', side_effect=lambda q, *_: q):
        supabase_mock.table.side_effect = table_side_effect

        response = test_client.get('/onboarding/which-template', headers=valid_auth_header)

    assert response.status_code == 200
    assert response.json()["success"] is True
    assert response.json()["data"]["folder_id"] == 10
