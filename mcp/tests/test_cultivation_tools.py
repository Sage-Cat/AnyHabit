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
    with pytest.raises(ValueError, match="user_confirmed=true"):
        server.start_minimum_mode(1, "busy week", user_confirmed=False)
    with pytest.raises(ValueError, match="user_confirmed=true"):
        server.end_minimum_mode(1, user_confirmed=False)
    with pytest.raises(ValueError, match="user_confirmed=true"):
        server.change_habit_level(1, "up", "ready", user_confirmed=False)
    assert server.calls == []


def test_confirmed_minimum_mode_carries_consent(server):
    server.start_minimum_mode(4, "busy week", user_confirmed=True)
    method, path, kwargs = server.calls[-1]
    assert (method, path) == ("POST", "/cultivation/habits/4/modes/start")
    assert kwargs["json_body"]["confirmed_by_user"] is True


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


def test_stats_pass_the_window(server):
    server.get_cultivation_stats(30)
    assert server.calls[-1] == ("GET", "/cultivation/stats", {"params": {"days": 30}})


def test_progress_pass_the_window(server):
    server.get_cultivation_progress(365)
    assert server.calls[-1] == ("GET", "/cultivation/progress", {"params": {"days": 365}})


def test_confirmed_level_change_is_forwarded(server):
    server.change_habit_level(3, "up", "user agreed", user_confirmed=True, effective_from="2026-11-20")
    method, path, kwargs = server.calls[-1]
    assert (method, path) == ("POST", "/cultivation/habits/3/level")
    assert kwargs["json_body"] == {
        "direction": "up",
        "reason": "user agreed",
        "effective_from": "2026-11-20",
        "confirmed_by_user": True,
    }
    server.change_habit_level(3, "down", "too hard", user_confirmed=True)
    assert "effective_from" not in server.calls[-1][2]["json_body"]


def test_level_change_errors_pass_through(server, monkeypatch):
    def refuse(path, **kwargs):
        raise RuntimeError("409: Habit is already on the first level")

    monkeypatch.setattr(server.api, "post", refuse)
    with pytest.raises(RuntimeError, match="409"):
        server.change_habit_level(3, "down", "too hard", user_confirmed=True)
