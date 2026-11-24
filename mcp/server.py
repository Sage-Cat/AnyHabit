from __future__ import annotations

from typing import Any, Literal

from mcp.server import MCPServer

from anyhabit_client import AnyHabitClient
from config import Settings


TrackerType = Literal["quit", "build", "boolean"]
Period = Literal["day", "week", "month", "year"]
WeekStart = Literal["monday", "sunday", "saturday"]

settings = Settings.load()
api = AnyHabitClient(settings)

mcp = MCPServer(
    "AnyHabit",
    version="0.1.0",
    instructions=(
        "Control and inspect an AnyHabit instance. Resolve tracker names to IDs "
        "before mutating them. Prefer archive over permanent deletion. Use "
        "record_relapse only when the user explicitly wants to reset a quit "
        "streak. Irreversible tools may be disabled by server configuration. "
        "Habit cultivation (passports, stages, recovery, ranks): base every "
        "statement on the returned data, keep facts apart from assumptions and "
        "say when there is not enough data. Record only what the user reported; "
        "never invent completions. A day without a record is 'no data', not a "
        "failure. Passport, criteria, stage and minimum-mode changes need the "
        "user's explicit approval of that exact change (user_confirmed=true) and a reason; "
        "history is appended, never rewritten. Stages move by themselves when "
        "the passport's criteria are met (stage_changes lists each move); a stage "
        "set by hand is an override the criteria then continue from. A habit may "
        "have a ladder of levels: moving up is allowed only for an integrated habit "
        "and only with the user's approval; it starts formation of the new level "
        "from that day while the rank keeps counting the previous level; a quit "
        "habit's rung with `streak_days` is reached by itself after that many days "
        "in a row without a relapse (a manual level change restarts the count); moving down is allowed from level 2 up. A failed formation attempt (`attempt.failed_on`) needs the "
        "user's decision: a new attempt (start_new_attempt) on level 1, a return to "
        "the previous level's stabilization (change_habit_level down, the rank can drop) above it; never act without "
        "the user's explicit approval. Ranks count integrated habits per level "
        "(`rank_level`)."
    ),
)


def _without_none(**values: Any) -> dict[str, Any]:
    return {key: value for key, value in values.items() if value is not None}


# ---------------------------------------------------------------------------
# System and account
# ---------------------------------------------------------------------------


@mcp.tool()
def health_check() -> dict[str, Any]:
    """Check whether the configured AnyHabit instance is healthy.

    This tool does not require an AnyHabit API token.
    """
    return api.get("/health", auth=False)


@mcp.tool()
def get_current_user() -> dict[str, Any]:
    """Return the AnyHabit user associated with the configured API token."""
    return api.get("/auth/me")


@mcp.tool()
def update_preferences(
    timezone: str | None = None,
    week_start: WeekStart | None = None,
    username: str | None = None,
) -> dict[str, Any]:
    """Update current-user preferences. Only supplied fields are changed."""
    payload = _without_none(
        timezone=timezone,
        week_start=week_start,
        username=username,
    )
    if not payload:
        raise ValueError("Provide at least one preference to update.")
    return api.patch("/auth/me", json_body=payload)


# ---------------------------------------------------------------------------
# Trackers
# ---------------------------------------------------------------------------


@mcp.tool()
def list_trackers(include_archived: bool = False) -> list[dict[str, Any]]:
    """List all trackers accessible to the current user."""
    return api.get(
        "/trackers/",
        params={"include_archived": str(include_archived).lower()},
    )


@mcp.tool()
def search_trackers(
    query: str,
    include_archived: bool = False,
) -> list[dict[str, Any]]:
    """Find trackers by name, category, description, type, or unit.

    Use this before changing a tracker when the user referred to it by name
    rather than by numeric ID.
    """
    needle = query.strip().casefold()
    trackers = list_trackers(include_archived=include_archived)
    if not needle:
        return trackers

    fields = ("name", "category", "description", "type", "unit")
    return [
        tracker
        for tracker in trackers
        if any(
            needle in str(tracker.get(field, "")).casefold()
            for field in fields
        )
    ]


@mcp.tool()
def get_tracker(tracker_id: int) -> dict[str, Any]:
    """Get one tracker by numeric ID."""
    return api.get(f"/trackers/{tracker_id}/")


@mcp.tool()
def get_tracker_bundle(tracker_id: int) -> dict[str, Any]:
    """Get tracker, logs, journal entries, analytics and sharing data in one call."""
    return api.get(f"/trackers/{tracker_id}/bundle")


@mcp.tool()
def get_tracker_analytics(tracker_id: int) -> dict[str, Any]:
    """Return streaks, progress, consistency, charts and mood analytics."""
    return api.get(f"/trackers/{tracker_id}/analytics")


@mcp.tool()
def create_tracker(
    name: str,
    type: TrackerType,
    description: str = "",
    color: str = "",
    category: str = "General",
    impact_amount: float = 0.0,
    impact_unit: str = "$",
    impact_per: Period = "day",
    unit: str = "",
    units_per_amount: float = 0.0,
    units_per: Period = "day",
    units_per_interval: int = 1,
    is_active: bool = True,
    start_date: str | None = None,
    group_id: int | None = None,
    participant_ids: list[int] | None = None,
) -> dict[str, Any]:
    """Create an AnyHabit tracker.

    type=quit tracks time since a relapse, type=build accumulates amounts, and
    type=boolean records done/not-done per period. start_date is optional ISO-8601.
    """
    payload: dict[str, Any] = {
        "name": name,
        "type": type,
        "description": description,
        "color": color,
        "category": category,
        "impact_amount": impact_amount,
        "impact_unit": impact_unit,
        "impact_per": impact_per,
        "unit": unit,
        "units_per_amount": units_per_amount,
        "units_per": units_per,
        "units_per_interval": units_per_interval,
        "is_active": is_active,
        "participant_ids": participant_ids or [],
    }
    if start_date is not None:
        payload["start_date"] = start_date
    if group_id is not None:
        payload["group_id"] = group_id

    return api.post("/trackers/", json_body=payload)


@mcp.tool()
def update_tracker(
    tracker_id: int,
    name: str | None = None,
    description: str | None = None,
    color: str | None = None,
    category: str | None = None,
    type: TrackerType | None = None,
    impact_amount: float | None = None,
    impact_unit: str | None = None,
    impact_per: Period | None = None,
    unit: str | None = None,
    units_per_amount: float | None = None,
    units_per: Period | None = None,
    units_per_interval: int | None = None,
    is_active: bool | None = None,
    start_date: str | None = None,
    group_id: int | None = None,
    participant_ids: list[int] | None = None,
    clear_group: bool = False,
) -> dict[str, Any]:
    """Partially update a tracker.

    Only supplied values change. Set clear_group=true to make a shared tracker
    private again. Do not use clear_group together with group_id.
    """
    if clear_group and group_id is not None:
        raise ValueError("Use either clear_group=true or group_id, not both.")

    payload = _without_none(
        name=name,
        description=description,
        color=color,
        category=category,
        type=type,
        impact_amount=impact_amount,
        impact_unit=impact_unit,
        impact_per=impact_per,
        unit=unit,
        units_per_amount=units_per_amount,
        units_per=units_per,
        units_per_interval=units_per_interval,
        is_active=is_active,
        start_date=start_date,
        participant_ids=participant_ids,
    )
    if clear_group:
        payload["group_id"] = None
    elif group_id is not None:
        payload["group_id"] = group_id

    if not payload:
        raise ValueError("Provide at least one tracker field to update.")

    return api.patch(f"/trackers/{tracker_id}/", json_body=payload)


@mcp.tool()
def start_tracker(tracker_id: int) -> dict[str, Any]:
    """Resume a paused tracker.

    A cultivated habit fed by it resumes too: its criteria count again from
    today (a new attempt in its current stage; a failed attempt stays failed).
    """
    return api.put(f"/trackers/{tracker_id}/start")


@mcp.tool()
def stop_tracker(tracker_id: int) -> dict[str, Any]:
    """Pause an active tracker.

    A cultivated habit fed by it pauses too: its days are not judged, its stage
    and formation deadline stand still and it does not count for the rank.
    """
    return api.put(f"/trackers/{tracker_id}/stop")


@mcp.tool()
def archive_tracker(tracker_id: int) -> dict[str, Any]:
    """Archive a tracker without destroying its history."""
    return api.put(f"/trackers/{tracker_id}/archive")


@mcp.tool()
def unarchive_tracker(tracker_id: int) -> dict[str, Any]:
    """Restore an archived tracker."""
    return api.put(f"/trackers/{tracker_id}/unarchive")


@mcp.tool()
def record_relapse(tracker_id: int, note: str = "") -> dict[str, Any]:
    """Reset a quit tracker's current run by recording a relapse.

    Use only when the user explicitly says the quit streak/run should reset.
    """
    return api.post(
        f"/trackers/{tracker_id}/reset",
        params={"note": note},
    )


@mcp.tool()
def delete_tracker(tracker_id: int) -> dict[str, Any]:
    """Permanently delete a tracker and all of its history.

    Irreversible and disabled unless ANYHABIT_MCP_ALLOW_DESTRUCTIVE=true.
    """
    api.require_destructive("Permanent tracker deletion")
    return api.delete(f"/trackers/{tracker_id}")


# ---------------------------------------------------------------------------
# Logs
# ---------------------------------------------------------------------------


@mcp.tool()
def list_logs(
    tracker_id: int,
    mine_only: bool = True,
    limit: int = 100,
) -> list[dict[str, Any]]:
    """List activity logs for a tracker, newest first."""
    return api.get(
        f"/trackers/{tracker_id}/logs/",
        params={
            "mine_only": str(mine_only).lower(),
            "limit": limit,
        },
    )


@mcp.tool()
def log_progress(
    tracker_id: int,
    amount: float = 1.0,
    note: str = "",
    timestamp: str | None = None,
) -> dict[str, Any]:
    """Record progress/activity.

    timestamp is optional ISO-8601. Use record_relapse instead for a quit
    tracker relapse. For a yes/no habit with an evening done_by, a time after
    midnight and before 06:00 counts for the evening before: log the real moment.
    """
    payload: dict[str, Any] = {"amount": amount, "note": note}
    if timestamp is not None:
        payload["timestamp"] = timestamp
    return api.post(f"/trackers/{tracker_id}/logs/", json_body=payload)


@mcp.tool()
def update_log(
    tracker_id: int,
    log_id: int,
    amount: float | None = None,
    note: str | None = None,
    timestamp: str | None = None,
) -> dict[str, Any]:
    """Correct an existing activity log."""
    payload = _without_none(
        amount=amount,
        note=note,
        timestamp=timestamp,
    )
    if not payload:
        raise ValueError("Provide at least one log field to update.")
    return api.patch(
        f"/trackers/{tracker_id}/logs/{log_id}",
        json_body=payload,
    )


@mcp.tool()
def delete_log(tracker_id: int, log_id: int) -> dict[str, Any]:
    """Permanently delete an activity log.

    Disabled unless ANYHABIT_MCP_ALLOW_DESTRUCTIVE=true.
    """
    api.require_destructive("Log deletion")
    return api.delete(f"/trackers/{tracker_id}/logs/{log_id}")


# ---------------------------------------------------------------------------
# Journal
# ---------------------------------------------------------------------------


@mcp.tool()
def list_journal_entries(
    tracker_id: int,
    mine_only: bool = True,
    search: str = "",
    limit: int = 100,
) -> list[dict[str, Any]]:
    """List or text-search journal entries for a tracker."""
    return api.get(
        f"/trackers/{tracker_id}/journal/",
        params={
            "mine_only": str(mine_only).lower(),
            "search": search,
            "limit": limit,
        },
    )


@mcp.tool()
def add_journal_entry(
    tracker_id: int,
    content: str,
    mood: int | None = None,
    timestamp: str | None = None,
) -> dict[str, Any]:
    """Add a private journal entry. mood is optional from 1 to 5."""
    payload: dict[str, Any] = {"content": content}
    if mood is not None:
        payload["mood"] = mood
    if timestamp is not None:
        payload["timestamp"] = timestamp
    return api.post(
        f"/trackers/{tracker_id}/journal/",
        json_body=payload,
    )


@mcp.tool()
def update_journal_entry(
    tracker_id: int,
    journal_id: int,
    content: str,
    mood: int | None = None,
) -> dict[str, Any]:
    """Edit one of the current user's journal entries."""
    payload: dict[str, Any] = {"content": content}
    if mood is not None:
        payload["mood"] = mood
    return api.put(
        f"/trackers/{tracker_id}/journal/{journal_id}",
        json_body=payload,
    )


@mcp.tool()
def delete_journal_entry(
    tracker_id: int,
    journal_id: int,
) -> dict[str, Any]:
    """Permanently delete one journal entry.

    Disabled unless ANYHABIT_MCP_ALLOW_DESTRUCTIVE=true.
    """
    api.require_destructive("Journal entry deletion")
    return api.delete(f"/trackers/{tracker_id}/journal/{journal_id}")


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------


@mcp.tool()
def get_dashboard_summary() -> dict[str, Any]:
    """Return overall totals, categories, streaks and today's progress."""
    return api.get("/dashboard/summary")


@mcp.tool()
def get_recent_activity(limit: int = 20) -> dict[str, Any]:
    """Return recent logs and journal activity across trackers."""
    return api.get("/dashboard/activity", params={"limit": limit})


@mcp.tool()
def get_dashboard_home() -> dict[str, Any]:
    """Return the saved home-dashboard widget layout."""
    return api.get("/dashboard/home")


@mcp.tool()
def save_dashboard_home(
    widgets: list[dict[str, Any]],
    layouts: dict[str, Any],
) -> dict[str, Any]:
    """Save the home-dashboard widget/layout configuration."""
    return api.put(
        "/dashboard/home",
        json_body={"widgets": widgets, "layouts": layouts},
    )


# ---------------------------------------------------------------------------
# Groups
# ---------------------------------------------------------------------------


@mcp.tool()
def list_groups() -> list[dict[str, Any]]:
    """List groups the current user owns or belongs to."""
    return api.get("/groups/")


@mcp.tool()
def get_group(group_id: int) -> dict[str, Any]:
    """Get one group and its membership information."""
    return api.get(f"/groups/{group_id}")


@mcp.tool()
def list_group_members(group_id: int) -> list[dict[str, Any]]:
    """List the members of a group."""
    return api.get(f"/groups/{group_id}/members")


@mcp.tool()
def create_group(name: str) -> dict[str, Any]:
    """Create a new AnyHabit sharing group."""
    return api.post("/groups/", json_body={"name": name})


@mcp.tool()
def join_group(join_code: str) -> dict[str, Any]:
    """Join a group with its join code."""
    return api.post("/groups/join", json_body={"join_code": join_code})


@mcp.tool()
def rename_group(group_id: int, name: str) -> dict[str, Any]:
    """Rename a group. Only the group owner can do this."""
    return api.patch(f"/groups/{group_id}", json_body={"name": name})


@mcp.tool()
def rotate_group_join_code(group_id: int) -> dict[str, Any]:
    """Generate a new join code, invalidating the previous one."""
    return api.post(f"/groups/{group_id}/rotate-code")


@mcp.tool()
def leave_group(group_id: int) -> dict[str, Any]:
    """Leave a group the current user does not own."""
    return api.post(f"/groups/{group_id}/leave")


@mcp.tool()
def remove_group_member(group_id: int, user_id: int) -> dict[str, Any]:
    """Remove a member from a group.

    Disabled unless ANYHABIT_MCP_ALLOW_DESTRUCTIVE=true.
    """
    api.require_destructive("Removing a group member")
    return api.delete(f"/groups/{group_id}/members/{user_id}")


@mcp.tool()
def delete_group(group_id: int) -> dict[str, Any]:
    """Disband a group.

    Disabled unless ANYHABIT_MCP_ALLOW_DESTRUCTIVE=true.
    """
    api.require_destructive("Group deletion")
    return api.delete(f"/groups/{group_id}")


# ---------------------------------------------------------------------------
# Habit cultivation
# ---------------------------------------------------------------------------

CultivationKind = Literal["sleep", "build", "boolean", "quit"]
CultivationStage = Literal["planned", "formation", "stabilization", "integrated"]
DayMarkStatus = Literal["success", "minimum", "fail", "exception", "clear"]


def _require_user_confirmation(user_confirmed: bool, action: str) -> None:
    if not user_confirmed:
        raise ValueError(
            f"{action} changes the user's goals or criteria. Describe the exact change, "
            "get the user's explicit approval, then call again with user_confirmed=true."
        )


@mcp.tool()
def get_cultivation_overview() -> dict[str, Any]:
    """Active, integrated and planned habits with today's requirement, recovery state and the rank."""
    return api.get("/cultivation/overview")


@mcp.tool()
def list_cultivated_habits(include_archived: bool = False) -> list[dict[str, Any]]:
    """List cultivated habits with their stage, today's state and a 14-day history."""
    return api.get("/cultivation/habits", params={"include_archived": include_archived})


@mcp.tool()
def get_cultivated_habit(habit_id: int, history_days: int = 90) -> dict[str, Any]:
    """Full passport, version history, success rates, deviations, recovery metrics,
    monthly dynamics, integration criteria check and the stage changes.

    Also `ladder` (levels, current level, can_upgrade / upgrade_blocker,
    can_downgrade; for a quit habit's automatic rungs `auto`, the current
    `streak` and the `next_streak` needed) and `level_changes` (each move
    between levels, `auto` for a move made by the streak). `paused` is true while
    the habit's tracker is paused.
    """
    return api.get(f"/cultivation/habits/{habit_id}", params={"history_days": history_days})


@mcp.tool()
def get_habit_days(habit_id: int, start: str | None = None, end: str | None = None) -> list[dict[str, Any]]:
    """Day-by-day states (success, minimum, fail, exception, no_data, unrated, invalid).

    Dates are YYYY-MM-DD in the user's timezone. A yes/no habit with an evening
    done_by counts a log made after midnight (before 06:00) for the evening
    before; that day carries first_next_day.
    """
    return api.get(f"/cultivation/habits/{habit_id}/days", params=_without_none(start=start, end=end))


@mcp.tool()
def get_cultivation_rank() -> dict[str, Any]:
    """Current cultivation rank, «Прорив» (percent to the next rank), habits per stage, rank history and warnings."""
    return api.get("/cultivation/rank")


@mcp.tool()
def get_cultivation_stats(days: int = 84) -> dict[str, Any]:
    """All active habits together: per-day states, 7-day rolling success, warnings and totals.

    days (7-366) is the length of the returned series. A day inside a habit's
    tolerance band counts as a success and carries a warning.
    """
    return api.get("/cultivation/stats", params={"days": days})


@mcp.tool()
def get_cultivation_progress(days: int = 90) -> dict[str, Any]:
    """Cultivation progress over time: «Прорив» (percent to the next rank) per day,
    each habit's readiness for its next stage with what still blocks it, its
    stage path, and deviations per month with the median days to recovery.

    days (7-366) is the length of the history.
    """
    return api.get("/cultivation/progress", params={"days": days})


@mcp.tool()
def get_cultivation_vocabulary() -> dict[str, Any]:
    """Stage and day-state labels, habit kinds and passport defaults."""
    return api.get("/cultivation/vocabulary")


@mcp.tool()
def export_cultivation() -> dict[str, Any]:
    """Complete cultivation history: passports with every version, day marks, minimum-mode periods."""
    return api.get("/cultivation/export")


@mcp.tool()
def log_sleep(
    habit_id: int,
    bedtime: str,
    wake: str,
    reason: str = "",
    state: str = "",
    note: str = "",
) -> dict[str, Any]:
    """Record one night for a sleep habit, exactly as the user reported it.

    bedtime/wake are ISO datetimes; without an offset they are read in the
    user's timezone. reason explains a deviation, state is how the next day felt.
    """
    return api.post(
        f"/cultivation/habits/{habit_id}/sleep",
        json_body={"bedtime": bedtime, "wake": wake, "reason": reason, "state": state, "note": note},
    )


@mcp.tool()
def mark_habit_day(habit_id: int, date: str, status: DayMarkStatus, reason: str = "") -> dict[str, Any]:
    """Record the user's verdict for a day (e.g. an excused exception or a failure with unknown details).

    The latest mark wins; status=clear removes it. A reason is required except for clear.
    """
    return api.post(
        f"/cultivation/habits/{habit_id}/marks",
        json_body={"date": date, "status": status, "reason": reason},
    )


@mcp.tool()
def start_minimum_mode(
    habit_id: int, reason: str, user_confirmed: bool, start_date: str | None = None
) -> dict[str, Any]:
    """Start controlled degradation: until it ends, the minimum level is the requirement.

    This changes what counts as success, so it needs the user's explicit approval.
    """
    _require_user_confirmation(user_confirmed, "Starting minimum mode")
    return api.post(
        f"/cultivation/habits/{habit_id}/modes/start",
        json_body=_without_none(reason=reason, start_date=start_date, confirmed_by_user=True),
    )


@mcp.tool()
def end_minimum_mode(
    habit_id: int, user_confirmed: bool, reason: str = "", end_date: str | None = None
) -> dict[str, Any]:
    """End the active minimum mode and return to the normal requirement (needs the user's approval)."""
    _require_user_confirmation(user_confirmed, "Ending minimum mode")
    return api.post(
        f"/cultivation/habits/{habit_id}/modes/end",
        json_body=_without_none(reason=reason, end_date=end_date, confirmed_by_user=True),
    )


@mcp.tool()
def create_cultivated_habit(
    kind: CultivationKind,
    spec: dict[str, Any],
    reason: str,
    user_confirmed: bool,
    tracker_id: int | None = None,
    effective_from: str | None = None,
) -> dict[str, Any]:
    """Create a habit passport (and a matching tracker unless tracker_id is given).

    spec keys: name, description, why, trait, priority, stage, goal, level,
    minimum, subgoals, levels, current_level, rules, stabilization, integration,
    maintenance — see get_cultivation_vocabulary for defaults. levels is an
    optional ladder: a list of {name?, level, tolerance?, minimum?} (a quit
    habit's rung: {name?, streak_days?}, reached by itself after that many days
    in a row without a relapse); current_level is 1-based. A sleep level may set bed_by (HH:MM, fall asleep no later than).
    Requires the user's approval.
    """
    _require_user_confirmation(user_confirmed, "Creating a habit passport")
    return api.post(
        "/cultivation/habits",
        json_body=_without_none(
            kind=kind,
            spec=spec,
            reason=reason,
            tracker_id=tracker_id,
            effective_from=effective_from,
            confirmed_by_user=True,
        ),
    )


@mcp.tool()
def change_habit_passport(
    habit_id: int,
    reason: str,
    user_confirmed: bool,
    patch: dict[str, Any] | None = None,
    spec: dict[str, Any] | None = None,
    effective_from: str | None = None,
) -> dict[str, Any]:
    """Append a new passport version (merge patch or full spec) with its reason.

    Goals, criteria and sub-goals change only with the user's explicit approval.
    The patch may edit the ladder (`levels`) and a sleep level's `bed_by`. A rung
    of a quit habit may carry `streak_days` (days in a row without a relapse;
    refused on other kinds): when the next rung has it, the habit moves up by
    itself once the streak reaches it and starts formation of that level; quit
    rungs need only a name and optional `streak_days`. A manual level change
    restarts the streak. The
    passport's own level, tolerance and minimum follow its current rung; the
    level itself moves only with change_habit_level, and `levels: null` removes
    the ladder.
    """
    _require_user_confirmation(user_confirmed, "Changing a habit passport")
    return api.post(
        f"/cultivation/habits/{habit_id}/versions",
        json_body=_without_none(
            patch=patch, spec=spec, reason=reason, effective_from=effective_from, confirmed_by_user=True
        ),
    )


@mcp.tool()
def change_habit_stage(
    habit_id: int,
    stage: CultivationStage,
    reason: str,
    user_confirmed: bool,
    effective_from: str | None = None,
) -> dict[str, Any]:
    """Put a habit on a stage by hand. Stages move by themselves; this overrides that, then the criteria go on."""
    _require_user_confirmation(user_confirmed, "Changing a habit stage")
    return api.post(
        f"/cultivation/habits/{habit_id}/stage",
        json_body=_without_none(stage=stage, reason=reason, effective_from=effective_from, confirmed_by_user=True),
    )


@mcp.tool()
def archive_cultivated_habit(habit_id: int) -> dict[str, Any]:
    """Archive a cultivated habit: it leaves the lists, the rank and the reminders; its history is kept."""
    return api.post(f"/cultivation/habits/{habit_id}/archive")


@mcp.tool()
def unarchive_cultivated_habit(habit_id: int) -> dict[str, Any]:
    """Restore an archived cultivated habit."""
    return api.post(f"/cultivation/habits/{habit_id}/unarchive")


@mcp.tool()
def change_habit_level(
    habit_id: int,
    direction: Literal["up", "down"],
    reason: str,
    user_confirmed: bool,
    effective_from: str | None = None,
) -> dict[str, Any]:
    """Move a habit one level up or down its ladder (the passport's `levels`).

    Up needs an integrated habit that has a next level; the new level starts
    its formation from that day, while the rank keeps counting the previous
    level. Up onto an automatic (`streak_days`) rung is refused. Down (only from
    level 2) after a failed attempt (attempt action `fallback`) returns the habit
    to stabilization of the previous level (the rank can drop); a voluntary down
    otherwise returns it to the lower level, integrated again if the habit was
    credited there. Requires the user's approval.
    """
    _require_user_confirmation(user_confirmed, "Changing a habit level")
    return api.post(
        f"/cultivation/habits/{habit_id}/level",
        json_body=_without_none(
            direction=direction, reason=reason, effective_from=effective_from, confirmed_by_user=True
        ),
    )


@mcp.tool()
def start_new_attempt(
    habit_id: int,
    reason: str,
    user_confirmed: bool,
    effective_from: str | None = None,
) -> dict[str, Any]:
    """Start a new formation attempt for a habit.

    Use only after the habit's formation attempt failed (the habit output has
    `attempt.failed_on`, action `new_attempt`) and the user decided to try
    again. It restarts formation and the criteria windows from that day.
    Requires the user's approval.
    """
    _require_user_confirmation(user_confirmed, "Starting a new attempt")
    return api.post(
        f"/cultivation/habits/{habit_id}/attempt",
        json_body=_without_none(reason=reason, effective_from=effective_from, confirmed_by_user=True),
    )


if __name__ == "__main__":
    if settings.transport == "stdio":
        mcp.run()
    else:
        mcp.run(
            transport="streamable-http",
            host=settings.host,
            port=settings.port,
            streamable_http_path=settings.path,
            stateless_http=settings.stateless_http,
        )
