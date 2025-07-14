import pytest


def test_extension_redirect(test_client):
    response = test_client.get(
        "/stripe/redirect?payment=success&session_id=abc123&ext=testext"
    )
    assert response.status_code == 200
    assert "chrome-extension://testext" in response.text
    assert "payment=success" in response.text
    assert "session_id=abc123" in response.text
