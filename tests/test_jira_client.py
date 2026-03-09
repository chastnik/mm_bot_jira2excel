from requests.exceptions import Timeout

from jira_client import JiraClient


def test_test_connection_uses_configured_timeout(monkeypatch):
    captured_kwargs = {}

    class FakeJira:
        def __init__(self, *args, **kwargs):
            captured_kwargs.update(kwargs)

        def current_user(self):
            return "demo-user"

    monkeypatch.setattr("jira_client.JIRA", FakeJira)
    monkeypatch.setattr("jira_client.Config.JIRA_REQUEST_TIMEOUT", 7, raising=False)

    client = JiraClient()
    success, _ = client.test_connection("user", "pass")

    assert success is True
    assert captured_kwargs["timeout"] == (7, 7)


def test_test_connection_returns_human_message_on_timeout(monkeypatch):
    class FakeJira:
        def __init__(self, *args, **kwargs):
            raise Timeout("jira did not respond in time")

    monkeypatch.setattr("jira_client.JIRA", FakeJira)
    monkeypatch.setattr("jira_client.Config.JIRA_REQUEST_TIMEOUT", 5, raising=False)

    client = JiraClient()
    success, message = client.test_connection("user", "pass")

    assert success is False
    assert "Таймаут" in message
