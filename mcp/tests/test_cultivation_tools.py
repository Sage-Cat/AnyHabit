from __future__ import annotations

import importlib

import pytest


@pytest.fixture()
def server(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("ANYHABIT_MCP_URL", "http://127.0.0.1:9")
    monkeypatch.setenv("ANYHABIT_MCP_TOKEN", "ahb_test")
    module = importlib.import_module("server")
    calls: list[tuple[str, str, dict]] = []

    class StubApi:
        def get(self, path, **kwargs):
            calls.append(("GET", path, kwargs))
            return {}

        def post(self, path, **kwargs):
            calls.append(("POST", path, kwargs))
            return {}

    monkeypatch.setattr(module, "api", StubApi())
    module.calls = calls
    return module


def test_passport_changes_need_user_confirmation(server):
    with pytest.raises(ValueError, match="user_confirmed=true"):
        server.change_habit_stage(1, "integrated", "looks ready", user_confirmed=False)
    with pytest.raises(ValueError, match="user_confirmed=true"):
        server.change_habit_passport(1, "stricter", user_confirmed=False, patch={"level": {}})
    with pytest.raises(ValueError, match="user_confirmed=true"):
        server.create_cultivated_habit("sleep", {"name": "x"}, "new", user_confirmed=False)
    assert server.calls == []


def test_confirmed_change_is_forwarded_with_consent_flag(server):
    server.change_habit_stage(3, "stabilization", "user agreed", user_confirmed=True)
    method, path, kwargs = server.calls[-1]
    assert (method, path) == ("POST", "/cultivation/habits/3/stage")
    assert kwargs["json_body"]["confirmed_by_user"] is True


def test_facts_are_recorded_without_confirmation(server):
    server.log_sleep(2, "2026-11-13T23:00", "2026-11-14T07:00", reason="", state="ok")
    server.mark_habit_day(2, "2026-11-12", "exception", "illness")
    paths = [path for _, path, _ in server.calls]
    assert paths == ["/cultivation/habits/2/sleep", "/cultivation/habits/2/marks"]
