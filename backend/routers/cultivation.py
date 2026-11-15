"""Habit cultivation API: passports, day states, recovery metrics, stages and ranks."""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from typing import Any, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .. import cultivation as cv
from .. import models, schemas
from ..access import require_tracker_access
from ..deps import get_current_user, get_db, get_period_context
from ..time_utils import PeriodContext, ensure_utc, resolve_timezone, utcnow
from .logs import create_log

router = APIRouter(prefix="/cultivation", tags=["cultivation"])

KIND_TRACKER_TYPES = {"sleep": "build", "build": "build", "boolean": "boolean", "quit": "quit"}


# ---------------------------------------------------------------------------
# Request bodies
# ---------------------------------------------------------------------------


class HabitCreate(BaseModel):
    kind: Literal["sleep", "build", "boolean", "quit"]
    spec: dict[str, Any]
    reason: str = Field(default="Створення звички", max_length=2000)
    tracker_id: Optional[int] = None
    create_tracker: bool = Field(default=True, description="Create a matching tracker when tracker_id is not given")
    effective_from: Optional[date] = None
    confirmed_by_user: bool = False


class PassportChange(BaseModel):
    spec: Optional[dict[str, Any]] = Field(default=None, description="Complete new passport")
    patch: Optional[dict[str, Any]] = Field(default=None, description="Merge patch applied to the current passport")
    reason: str = Field(min_length=1, max_length=2000)
    effective_from: Optional[date] = None
    confirmed_by_user: bool = Field(
        default=False, description="Required for API tokens: the user explicitly approved this change"
    )


class StageChange(BaseModel):
    stage: Literal["planned", "formation", "stabilization", "integrated"]
    reason: str = Field(min_length=1, max_length=2000)
    effective_from: Optional[date] = None
    confirmed_by_user: bool = False


class DayMarkCreate(BaseModel):
    date: date
    status: Literal["success", "minimum", "fail", "exception", "clear"]
    reason: str = Field(default="", max_length=2000)


class ModeStart(BaseModel):
    start_date: Optional[date] = None
    reason: str = Field(min_length=1, max_length=2000)
    confirmed_by_user: bool = Field(
        default=False, description="Required for API tokens: the minimum becomes the requirement"
    )


class ModeEnd(BaseModel):
    end_date: Optional[date] = None
    reason: str = Field(default="", max_length=2000)
    confirmed_by_user: bool = False


class SleepEntry(BaseModel):
    bedtime: datetime = Field(description="When you fell asleep; a naive value is read in your timezone")
    wake: datetime = Field(description="When you woke up; a naive value is read in your timezone")
    reason: str = Field(default="", max_length=500, description="Reason for a deviation, if any")
    state: str = Field(default="", max_length=200, description="How the next day felt")
    note: str = Field(default="", max_length=1000)


class ProfileUpdate(BaseModel):
    ranks: Optional[list[dict[str, Any]]] = Field(default=None, description="Rank ladder; null restores the default")


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------


def _author(request: Request) -> str:
    """Who acted: ``api`` for a personal access token (header or cookie), else ``user``."""
    return "api" if getattr(request.state, "auth_via", None) == "api_token" else "user"


def _require_write(request: Request) -> str:
    author = _author(request)
    if author == "api" and getattr(request.state, "token_scope", None) == "read":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Токен лише для читання")
    return author


def _require_user_confirmation(request: Request, confirmed: bool) -> str:
    """Goals and criteria change only with the user's consent.

    The web UI acts for the user directly; a script or AI agent using an API
    token must state that the user approved this exact change.
    """
    author = _require_write(request)
    if author == "api" and not confirmed:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Зміну паспорта звички має погодити користувач: передайте confirmed_by_user=true "
            "лише після його явної згоди.",
        )
    return author


def _today(user: models.User) -> date:
    return utcnow().astimezone(resolve_timezone(user.timezone)).date()


def _get_habit(db: Session, user: models.User, habit_id: int) -> models.CultivatedHabit:
    habit = (
        db.query(models.CultivatedHabit)
        .filter(models.CultivatedHabit.id == habit_id, models.CultivatedHabit.user_id == user.id)
        .first()
    )
    if habit is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Звичку не знайдено")
    return habit


def _writable_habit(db: Session, user: models.User, habit_id: int) -> models.CultivatedHabit:
    habit = _get_habit(db, user, habit_id)
    if habit.archived_at is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Звичку архівовано: спершу поверніть її з архіву"
        )
    return habit


def _check_day(label: str, value: date, today: date) -> None:
    if value < cv.MIN_DATE:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"{label}: дата раніша за {cv.MIN_DATE.isoformat()}",
        )
    if value > today:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"{label}: дата ще не настала")


def _versions(db: Session, habit: models.CultivatedHabit) -> list[dict]:
    rows = (
        db.query(models.CultivationPassportVersion)
        .filter(models.CultivationPassportVersion.habit_id == habit.id)
        .order_by(models.CultivationPassportVersion.effective_from, models.CultivationPassportVersion.id)
        .all()
    )
    return [
        {
            "id": row.id,
            "effective_from": date.fromisoformat(row.effective_from),
            "created_at": ensure_utc(row.created_at),
            "reason": row.reason,
            "author": row.author or "user",
            "spec": json.loads(row.spec_json),
        }
        for row in rows
    ]


def _marks(db: Session, habit: models.CultivatedHabit) -> dict[date, dict]:
    out: dict[date, dict] = {}
    rows = (
        db.query(models.CultivationDayMark)
        .filter(models.CultivationDayMark.habit_id == habit.id)
        .order_by(models.CultivationDayMark.id)
        .all()
    )
    for row in rows:
        day = date.fromisoformat(row.date)
        if row.status == "clear":
            out.pop(day, None)
        else:
            out[day] = {"status": row.status, "reason": row.reason or "", "author": row.author or "user"}
    return out


def _modes(db: Session, habit: models.CultivatedHabit) -> list[dict]:
    rows = (
        db.query(models.CultivationMode)
        .filter(models.CultivationMode.habit_id == habit.id)
        .order_by(models.CultivationMode.start_date, models.CultivationMode.id)
        .all()
    )
    return [
        {
            "id": row.id,
            "start_date": date.fromisoformat(row.start_date),
            "end_date": date.fromisoformat(row.end_date) if row.end_date else None,
            "reason": row.reason,
            "end_reason": row.end_reason or "",
            "author": row.author or "user",
        }
        for row in rows
    ]


def _observations(db: Session, habit: models.CultivatedHabit, user: models.User) -> dict[date, cv.Observation]:
    if habit.tracker_id is None:
        return {}
    tz = resolve_timezone(user.timezone)
    out: dict[date, cv.Observation] = {}
    if habit.kind == "quit":
        relapses = (
            db.query(models.JournalEntry)
            .filter(
                models.JournalEntry.tracker_id == habit.tracker_id,
                models.JournalEntry.user_id == user.id,
                models.JournalEntry.is_relapse.is_(True),
            )
            .all()
        )
        for entry in relapses:
            local = ensure_utc(entry.timestamp).astimezone(tz)
            obs = out.setdefault(local.date(), cv.Observation())
            obs.events += 1
            obs.notes.append(entry.content or "")
        return out

    logs = (
        db.query(models.HabitLog)
        .filter(models.HabitLog.tracker_id == habit.tracker_id, models.HabitLog.user_id == user.id)
        .order_by(models.HabitLog.timestamp)
        .all()
    )
    for log in logs:
        wake_utc = ensure_utc(log.timestamp)
        local = wake_utc.astimezone(tz)
        obs = out.setdefault(local.date(), cv.Observation())
        obs.events += 1
        obs.amount += float(log.amount or 0)
        obs.notes.append(log.note or "")
        if obs.first_at is None and habit.kind != "sleep":
            obs.first_at = local.time()  # logs are ordered, so this is the earliest
        if habit.kind == "sleep" and log.amount and log.amount > 0:
            # Subtract in UTC: local wall-clock arithmetic is off by an hour across DST.
            # The amount is stored rounded to 0.01 h, so snap back to whole minutes.
            bedtime = (wake_utc - timedelta(minutes=round(float(log.amount) * 60))).astimezone(tz)
            obs.nights.append(cv.Night(log.id, bedtime, local, log.note or ""))
    return out


def _profile(db: Session, user: models.User) -> tuple[list[dict], bool]:
    row = db.query(models.CultivationProfile).filter(models.CultivationProfile.user_id == user.id).first()
    if row is None or not row.ranks_json:
        return cv.DEFAULT_RANKS, False
    return json.loads(row.ranks_json), True


# ---------------------------------------------------------------------------
# Assembling responses
# ---------------------------------------------------------------------------


def _tracker_info(db: Session, habit: models.CultivatedHabit) -> dict | None:
    if habit.tracker_id is None:
        return None
    tracker = db.query(models.Tracker).filter(models.Tracker.id == habit.tracker_id).first()
    if tracker is None:
        return None
    return {
        "id": tracker.id,
        "name": tracker.name,
        "type": tracker.type,
        "unit": tracker.unit or "",
        "color": tracker.color or "",
    }


def _version_out(version: dict, with_spec: bool = True) -> dict:
    out = {
        "id": version["id"],
        "effective_from": version["effective_from"].isoformat(),
        "created_at": version["created_at"].isoformat() if version["created_at"] else None,
        "reason": version["reason"],
        "author": version["author"],
    }
    if with_spec:
        out["spec"] = version["spec"]
    return out


def _analyse(db: Session, user: models.User, habit: models.CultivatedHabit, history_days: int = 60) -> dict:
    today = _today(user)
    versions = _versions(db, habit)
    spec = cv.latest_spec(versions) or {}
    tracker = _tracker_info(db, habit)
    unit = (tracker or {}).get("unit", "")
    modes = _modes(db, habit)
    days = cv.build_days(
        habit.kind,
        versions,
        _observations(db, habit, user),
        _marks(db, habit),
        modes,
        today,
        tracked=tracker is not None,
    )
    episodes = cv.find_episodes(days, versions)
    rules = cv.section(spec, "rules", cv.DEFAULT_RULES)
    today_spec = cv.spec_for(versions, today) or spec
    active_mode = next((m for m in modes if m["end_date"] is None), None)
    degraded_today = cv.mode_on(modes, today) is not None
    today_day = days[-1] if days and days[-1].date == today else None
    subgoals = spec.get("subgoals") or []
    integration = cv.integration_check(spec, days, episodes, today) if spec else None
    stage = spec.get("stage")

    return {
        "id": habit.id,
        "kind": habit.kind,
        "tracker": tracker,
        "archived": habit.archived_at is not None,
        "name": spec.get("name", ""),
        "stage": stage,
        "stage_label": cv.STAGE_LABELS.get(stage, ""),
        "passport": spec,
        "versions": [_version_out(v) for v in versions],
        "today": {
            "date": today.isoformat(),
            "requirement": cv.level_text(habit.kind, (today_spec or {}).get("level"), unit),
            "minimum": cv.level_text(habit.kind, (today_spec or {}).get("minimum"), unit)
            if (today_spec or {}).get("minimum")
            else None,
            "tolerance": cv.level_text(habit.kind, (today_spec or {}).get("tolerance"), unit)
            if cv.tolerance_defined(habit.kind, (today_spec or {}).get("tolerance"))
            else None,
            "degraded": degraded_today,
            "day": today_day.as_dict() if today_day else None,
        },
        "next_subgoal": None
        if not subgoals
        else {
            **subgoals[0],
            "requirement": cv.level_text(habit.kind, (subgoals[0] or {}).get("level"), unit),
        },
        "mode": None
        if active_mode is None
        else {
            **active_mode,
            "start_date": active_mode["start_date"].isoformat(),
            "end_date": None,
        },
        "modes": [
            {
                **m,
                "start_date": m["start_date"].isoformat(),
                "end_date": m["end_date"].isoformat() if m["end_date"] else None,
            }
            for m in modes
        ],
        "rates": {
            "7": cv.rate(days, 7, today),
            "30": cv.rate(days, 30, today),
            "integration": cv.rate(
                days, int(cv.section(spec, "integration", cv.DEFAULT_INTEGRATION)["window_days"]), today
            ),
        },
        "recovery": cv.recovery_summary(episodes, days, today, int(rules["recovery_ok_days"])),
        "episodes": [e.as_dict(today) for e in episodes[-30:]],
        "monthly": cv.monthly(episodes, days),
        "integration": integration,
        "recommendation": cv.recommendation(spec, days, episodes, today) if spec else None,
        "readiness": cv.stage_readiness(spec, days, episodes, today) if spec else None,
        "days": [d.as_dict() for d in days[-history_days:]] if history_days else [],
    }


def _compact(analysis: dict) -> dict:
    keep = (
        "id",
        "kind",
        "tracker",
        "name",
        "stage",
        "stage_label",
        "today",
        "next_subgoal",
        "mode",
        "recommendation",
        "integration",
        "readiness",
    )
    out = {key: analysis[key] for key in keep}
    out["success_rate_30"] = analysis["rates"]["30"]["success_rate"]
    out["recovery"] = {
        key: analysis["recovery"][key]
        for key in (
            "current_deviation",
            "last_recovery",
            "first_ok_median",
            "confirmed_median",
            "in_term_share",
            "tested",
        )
    }
    out["priority"] = analysis["passport"].get("priority")
    out["days"] = analysis["days"][-14:]
    return out


def _rank(db: Session, user: models.User, readiness: dict[int, float | None] | None = None) -> dict:
    habits = (
        db.query(models.CultivatedHabit)
        .filter(models.CultivatedHabit.user_id == user.id, models.CultivatedHabit.archived_at.is_(None))
        .all()
    )
    ranks, custom = _profile(db, user)
    if readiness is None:
        readiness = {h.id: _analyse(db, user, h, history_days=0)["readiness"] for h in habits}
    report = cv.compute_rank({h.id: _versions(db, h) for h in habits}, _today(user), ranks, readiness)
    report["custom_ladder"] = custom
    return report


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("/overview")
def overview(current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Everything the home screen needs: active, integrated and planned habits plus the rank."""
    habits = (
        db.query(models.CultivatedHabit)
        .filter(models.CultivatedHabit.user_id == current_user.id, models.CultivatedHabit.archived_at.is_(None))
        .order_by(models.CultivatedHabit.id)
        .all()
    )
    analyses = [_compact(_analyse(db, current_user, h, history_days=14)) for h in habits]

    def priority_key(item: dict) -> tuple:
        priority = item["priority"]
        numeric = isinstance(priority, (int, float)) and not isinstance(priority, bool)
        return (not numeric, priority if numeric else 0, item["id"])

    by_priority = sorted(analyses, key=priority_key)
    warnings = []
    for item in analyses:
        rec = item["recommendation"]
        if item["stage"] == "integrated" and rec and rec["to"] == "stabilization":
            warnings.append(
                {"habit_id": item["id"], "message": f"«{item['name']}»: стійкість погіршується. {rec['reason']}"}
            )
    return {
        "date": _today(current_user).isoformat(),
        "timezone": current_user.timezone or "UTC",
        "active": [a for a in by_priority if a["stage"] in ("formation", "stabilization")],
        "integrated": [a for a in by_priority if a["stage"] == "integrated"],
        "planned": [a for a in by_priority if a["stage"] == "planned"],
        "warnings": warnings,
        "rank": _rank(db, current_user, {a["id"]: a["readiness"] for a in analyses}),
    }


@router.get("/stats")
def stats(
    days: int = Query(84, ge=7, le=366, description="How many days of series to return"),
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """All non-planned habits together: day states, 7-day rolling success and totals."""
    today = _today(current_user)
    habits = (
        db.query(models.CultivatedHabit)
        .filter(models.CultivatedHabit.user_id == current_user.id, models.CultivatedHabit.archived_at.is_(None))
        .order_by(models.CultivatedHabit.id)
        .all()
    )
    items = []
    for habit in habits:
        versions = _versions(db, habit)
        spec = cv.latest_spec(versions) or {}
        if spec.get("stage") == "planned":
            continue
        tracker = _tracker_info(db, habit)
        items.append(
            {
                "id": habit.id,
                "name": spec.get("name", ""),
                "kind": habit.kind,
                "stage": spec.get("stage"),
                "stage_label": cv.STAGE_LABELS.get(spec.get("stage"), ""),
                "tracker_id": tracker["id"] if tracker else None,
                "color": tracker["color"] if tracker else "",
                "days": cv.build_days(
                    habit.kind,
                    versions,
                    _observations(db, habit, current_user),
                    _marks(db, habit),
                    _modes(db, habit),
                    today,
                    tracked=tracker is not None,
                ),
            }
        )
    since = today - timedelta(days=days - 1)
    return {
        "date": today.isoformat(),
        "timezone": current_user.timezone or "UTC",
        **cv.combined_stats(items, since, today),
    }


@router.get("/progress")
def progress(
    days: int = Query(90, ge=7, le=366, description="How many days of history to return"),
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Cultivation progress: «Прорив» per day, readiness and stage path per habit, deviations per month."""
    today = _today(current_user)
    habits = (
        db.query(models.CultivatedHabit)
        .filter(models.CultivatedHabit.user_id == current_user.id, models.CultivatedHabit.archived_at.is_(None))
        .order_by(models.CultivatedHabit.id)
        .all()
    )
    rows, episodes = [], []
    for habit in habits:
        versions = _versions(db, habit)
        tracker = _tracker_info(db, habit)
        day_list = cv.build_days(
            habit.kind,
            versions,
            _observations(db, habit, current_user),
            _marks(db, habit),
            _modes(db, habit),
            today,
            tracked=tracker is not None,
        )
        found = cv.find_episodes(day_list, versions)
        episodes.extend(found)
        rows.append({"id": habit.id, "versions": versions, "days": day_list, "episodes": found, "tracker": tracker})
    ranks, _custom = _profile(db, current_user)
    history = cv.progress_history(rows, today - timedelta(days=days - 1), today, ranks)
    held = {
        h["habit_id"]: h["held_days"]
        for h in cv.compute_rank({r["id"]: r["versions"] for r in rows}, today, ranks)["habits"]
    }
    out_habits = []
    for row in rows:
        spec = cv.latest_spec(row["versions"]) or {}
        stage = spec.get("stage")
        out_habits.append(
            {
                "id": row["id"],
                "name": spec.get("name", ""),
                "color": row["tracker"]["color"] if row["tracker"] else "",
                "stage": stage,
                "stage_label": cv.STAGE_LABELS.get(stage, ""),
                "progress": cv.stage_progress(spec, row["days"], row["episodes"], today) if spec else None,
                "held_days": held.get(row["id"], 0),
                "readiness": history["readiness"][row["id"]],
                "segments": history["segments"][row["id"]],
            }
        )
    return {
        "since": history["days"][0]["date"] if history["days"] else today.isoformat(),
        "until": today.isoformat(),
        "days": history["days"],
        "habits": out_habits,
        "deviations": cv.deviations_by_month(episodes, today),
    }


@router.get("/habits")
def list_habits(
    include_archived: bool = False,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(models.CultivatedHabit).filter(models.CultivatedHabit.user_id == current_user.id)
    if not include_archived:
        query = query.filter(models.CultivatedHabit.archived_at.is_(None))
    return [_compact(_analyse(db, current_user, h, history_days=14)) for h in query.order_by(models.CultivatedHabit.id)]


@router.post("/habits", status_code=status.HTTP_201_CREATED)
def create_habit(
    payload: HabitCreate,
    request: Request,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    author = _require_user_confirmation(request, payload.confirmed_by_user)
    spec = dict(payload.spec)
    spec.setdefault("stage", "formation")
    today = _today(current_user)
    spec.setdefault("start_date", today.isoformat())
    if payload.effective_from is not None:
        _check_day("effective_from", payload.effective_from, today)
    try:
        cv.validate_spec(payload.kind, spec)
    except cv.PassportError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from None

    tracker_type = KIND_TRACKER_TYPES[payload.kind]
    if payload.tracker_id is not None:
        tracker = require_tracker_access(db, current_user.id, payload.tracker_id, write=True)
        if tracker.type != tracker_type:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Для звички типу «{payload.kind}» потрібна звичка-трекер типу «{tracker_type}»",
            )
        tracker_id = tracker.id
    elif payload.create_tracker:
        level = spec.get("level") or {}
        tracker = models.Tracker(
            owner_id=current_user.id,
            name=str(spec["name"]).strip(),
            description=str(spec.get("description") or ""),
            category="Культивація",
            type=tracker_type,
            unit="год" if payload.kind == "sleep" else str(spec.get("unit") or ""),
            units_per_amount=float(level.get("min_sleep_h") or level.get("min_amount") or 0),
            units_per="day",
            units_per_interval=1,
            impact_per="day",
            start_date=utcnow(),
            current_streak_start_date=utcnow(),
        )
        db.add(tracker)
        db.flush()
        tracker_id = tracker.id
    else:
        tracker_id = None

    habit = models.CultivatedHabit(user_id=current_user.id, tracker_id=tracker_id, kind=payload.kind)
    db.add(habit)
    db.flush()
    db.add(
        models.CultivationPassportVersion(
            habit_id=habit.id,
            effective_from=(payload.effective_from or today).isoformat(),
            reason=payload.reason.strip() or "Створення звички",
            author=author,
            spec_json=json.dumps(spec, ensure_ascii=False),
        )
    )
    analysis = _analyse_or_rollback(db, current_user, habit)
    db.commit()
    return analysis


@router.get("/habits/{habit_id}")
def get_habit(
    habit_id: int,
    history_days: int = Query(90, ge=0, le=3650),
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return _analyse(db, current_user, _get_habit(db, current_user, habit_id), history_days=history_days)


@router.get("/habits/{habit_id}/days")
def habit_days(
    habit_id: int,
    start: Optional[date] = None,
    end: Optional[date] = None,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    habit = _get_habit(db, current_user, habit_id)
    today = _today(current_user)
    versions = _versions(db, habit)
    days = cv.build_days(
        habit.kind,
        versions,
        _observations(db, habit, current_user),
        _marks(db, habit),
        _modes(db, habit),
        min(end or today, today),
        today=today,
        tracked=_tracker_info(db, habit) is not None,
    )
    return [d.as_dict() for d in days if (start is None or d.date >= start)]


def _analyse_or_rollback(db: Session, user: models.User, habit: models.CultivatedHabit) -> dict:
    """Analyse pending changes before commit, so nothing unreadable is ever stored."""
    db.flush()
    try:
        return _analyse(db, user, habit)
    except (cv.PassportError, ValueError, TypeError, KeyError) as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"Паспорт не вдається застосувати: {exc}"
        ) from None


def _add_version(
    db: Session,
    habit: models.CultivatedHabit,
    user: models.User,
    spec: dict,
    reason: str,
    effective_from: Optional[date],
    author: str,
) -> dict:
    try:
        cv.validate_spec(habit.kind, spec)
    except cv.PassportError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from None
    versions = _versions(db, habit)
    today = _today(user)
    effective = effective_from or today
    # A future date would show the new stage now but count the old one in ranks,
    # and could not be undone, because history only moves forward.
    _check_day("effective_from", effective, today)
    if versions and effective < versions[-1]["effective_from"]:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Дата чинності раніша за останню версію ({versions[-1]['effective_from'].isoformat()}): "
            "історію паспорта не переписуємо",
        )
    db.add(
        models.CultivationPassportVersion(
            habit_id=habit.id,
            effective_from=effective.isoformat(),
            reason=reason.strip(),
            author=author,
            spec_json=json.dumps(spec, ensure_ascii=False),
        )
    )
    analysis = _analyse_or_rollback(db, user, habit)
    db.commit()
    return analysis


@router.post("/habits/{habit_id}/versions", status_code=status.HTTP_201_CREATED)
def change_passport(
    habit_id: int,
    payload: PassportChange,
    request: Request,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Record a new passport version.  Nothing is overwritten: the old one stays in history."""
    author = _require_user_confirmation(request, payload.confirmed_by_user)
    habit = _writable_habit(db, current_user, habit_id)
    if (payload.spec is None) == (payload.patch is None):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Передайте або spec, або patch")
    current = cv.latest_spec(_versions(db, habit)) or {}
    spec = payload.spec if payload.spec is not None else cv.merge_patch(current, payload.patch)
    return _add_version(db, habit, current_user, spec, payload.reason, payload.effective_from, author)


@router.post("/habits/{habit_id}/stage", status_code=status.HTTP_201_CREATED)
def change_stage(
    habit_id: int,
    payload: StageChange,
    request: Request,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    author = _require_user_confirmation(request, payload.confirmed_by_user)
    habit = _writable_habit(db, current_user, habit_id)
    current = cv.latest_spec(_versions(db, habit)) or {}
    if current.get("stage") == payload.stage:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Звичка вже на цьому етапі")
    spec = cv.merge_patch(current, {"stage": payload.stage})
    return _add_version(db, habit, current_user, spec, payload.reason, payload.effective_from, author)


@router.post("/habits/{habit_id}/marks", status_code=status.HTTP_201_CREATED)
def mark_day(
    habit_id: int,
    payload: DayMarkCreate,
    request: Request,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Record a manual verdict for one day (``clear`` removes the previous one)."""
    author = _require_write(request)
    habit = _writable_habit(db, current_user, habit_id)
    if payload.date > _today(current_user):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Не можна позначати майбутні дні")
    _check_day("date", payload.date, _today(current_user))
    if payload.status != "clear" and not payload.reason.strip():
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Вкажіть причину позначки")
    db.add(
        models.CultivationDayMark(
            habit_id=habit.id,
            date=payload.date.isoformat(),
            status=payload.status,
            reason=payload.reason.strip(),
            author=author,
        )
    )
    db.commit()
    days = habit_days(habit_id, payload.date, payload.date, current_user, db)
    return days[0] if days else {"date": payload.date.isoformat(), "status": "no_data"}


@router.post("/habits/{habit_id}/modes/start", status_code=status.HTTP_201_CREATED)
def start_mode(
    habit_id: int,
    payload: ModeStart,
    request: Request,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Enter controlled degradation: the minimum level becomes the requirement until it ends.

    That changes what counts as success, so an API token needs the user's consent.
    """
    author = _require_user_confirmation(request, payload.confirmed_by_user)
    habit = _writable_habit(db, current_user, habit_id)
    start = payload.start_date or _today(current_user)
    _check_day("start_date", start, _today(current_user))
    if any(m["end_date"] is None for m in _modes(db, habit)):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Режим мінімуму вже активний")
    db.add(
        models.CultivationMode(
            habit_id=habit.id,
            start_date=start.isoformat(),
            reason=payload.reason.strip(),
            author=author,
        )
    )
    db.commit()
    return _analyse(db, current_user, habit, history_days=14)


@router.post("/habits/{habit_id}/modes/end")
def end_mode(
    habit_id: int,
    payload: ModeEnd,
    request: Request,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_user_confirmation(request, payload.confirmed_by_user)
    habit = _writable_habit(db, current_user, habit_id)
    row = (
        db.query(models.CultivationMode)
        .filter(models.CultivationMode.habit_id == habit.id, models.CultivationMode.end_date.is_(None))
        .first()
    )
    if row is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Режим мінімуму не активний")
    end = payload.end_date or _today(current_user)
    _check_day("end_date", end, _today(current_user))
    if end < date.fromisoformat(row.start_date):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Дата завершення раніша за початок"
        )
    row.end_date = end.isoformat()
    row.end_reason = payload.reason.strip()
    row.ended_at = utcnow()
    db.commit()
    return _analyse(db, current_user, habit, history_days=14)


@router.post("/habits/{habit_id}/sleep", status_code=status.HTTP_201_CREATED)
def log_sleep(
    habit_id: int,
    payload: SleepEntry,
    request: Request,
    current_user: models.User = Depends(get_current_user),
    context: PeriodContext = Depends(get_period_context),
    db: Session = Depends(get_db),
):
    """Record one night: stored as a tracker log (amount = hours, timestamp = wake-up)."""
    _require_write(request)
    habit = _writable_habit(db, current_user, habit_id)
    if habit.kind != "sleep" or habit.tracker_id is None:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Це не звичка сну з трекером")
    tz = resolve_timezone(current_user.timezone)

    def aware(value: datetime) -> datetime:
        return value.replace(tzinfo=tz) if value.tzinfo is None else value

    bedtime, wake = aware(payload.bedtime), aware(payload.wake)
    # Elapsed time in UTC: the same tzinfo on both ends would subtract wall clocks.
    hours = (ensure_utc(wake) - ensure_utc(bedtime)).total_seconds() / 3600
    if bedtime.astimezone(tz).date() < cv.MIN_DATE:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"Дата раніша за {cv.MIN_DATE.isoformat()}"
        )
    if not 0 < hours <= 24:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Підйом має бути пізніше засинання (до 24 год)"
        )
    if wake > utcnow() + timedelta(minutes=10):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Час підйому ще не настав")
    log = create_log(
        tracker_id=habit.tracker_id,
        log=schemas.HabitLogCreate(
            amount=round(hours, 2),
            note=cv.build_note(payload.reason, payload.state, payload.note),
            timestamp=wake,
        ),
        timestamp=None,
        current_user=current_user,
        context=context,
        db=db,
    )
    wake_day = wake.astimezone(tz).date()
    days = habit_days(habit_id, wake_day, wake_day, current_user, db)
    return {"log_id": log.id, "hours": round(hours, 2), "day": days[0] if days else None}


@router.post("/habits/{habit_id}/archive")
def archive_habit(
    habit_id: int,
    request: Request,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_write(request)
    habit = _get_habit(db, current_user, habit_id)
    habit.archived_at = habit.archived_at or utcnow()
    db.commit()
    return {"id": habit.id, "archived": True}


@router.post("/habits/{habit_id}/unarchive")
def unarchive_habit(
    habit_id: int,
    request: Request,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_write(request)
    habit = _get_habit(db, current_user, habit_id)
    habit.archived_at = None
    db.commit()
    return {"id": habit.id, "archived": False}


@router.get("/rank")
def rank(current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    return _rank(db, current_user)


@router.get("/profile")
def get_profile(current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    ranks, custom = _profile(db, current_user)
    return {"ranks": ranks, "custom_ladder": custom, "default_ranks": cv.DEFAULT_RANKS}


@router.put("/profile")
def update_profile(
    payload: ProfileUpdate,
    request: Request,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if _author(request) == "api":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Систему рангів змінює лише користувач у вебінтерфейсі"
        )
    ranks = None
    if payload.ranks is not None:
        try:
            ranks = cv.validate_ranks(payload.ranks)
        except cv.PassportError as exc:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from None
    row = db.query(models.CultivationProfile).filter(models.CultivationProfile.user_id == current_user.id).first()
    if row is None:
        row = models.CultivationProfile(user_id=current_user.id)
        db.add(row)
    if "ranks" in payload.model_fields_set:
        row.ranks_json = json.dumps(ranks, ensure_ascii=False) if ranks else ""
    db.commit()
    return get_profile(current_user, db)


def export_cultivation(db: Session, user: models.User) -> dict:
    """Full cultivation history for backups and the JSON export."""
    habits = (
        db.query(models.CultivatedHabit)
        .filter(models.CultivatedHabit.user_id == user.id)
        .order_by(models.CultivatedHabit.id)
    )
    profile = db.query(models.CultivationProfile).filter(models.CultivationProfile.user_id == user.id).first()
    out = {"habits": [], "profile": None}
    for habit in habits:
        tracker = _tracker_info(db, habit)
        marks = (
            db.query(models.CultivationDayMark)
            .filter(models.CultivationDayMark.habit_id == habit.id)
            .order_by(models.CultivationDayMark.id)
            .all()
        )
        out["habits"].append(
            {
                "id": habit.id,
                "kind": habit.kind,
                "tracker_id": habit.tracker_id,
                "tracker_name": tracker["name"] if tracker else None,
                "archived_at": habit.archived_at.isoformat() if habit.archived_at else None,
                "versions": [_version_out(v) for v in _versions(db, habit)],
                "marks": [
                    {
                        "date": m.date,
                        "status": m.status,
                        "reason": m.reason,
                        "author": m.author,
                        "created_at": ensure_utc(m.created_at).isoformat() if m.created_at else None,
                    }
                    for m in marks
                ],
                "modes": [
                    {
                        **m,
                        "start_date": m["start_date"].isoformat(),
                        "end_date": m["end_date"].isoformat() if m["end_date"] else None,
                    }
                    for m in _modes(db, habit)
                ],
            }
        )
    if profile is not None:
        out["profile"] = {"ranks": json.loads(profile.ranks_json) if profile.ranks_json else None}
    return out


@router.get("/export")
def export(current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    return export_cultivation(db, current_user)


@router.get("/vocabulary")
def vocabulary(_user: models.User = Depends(get_current_user)):
    """Labels for stages, day states and habit kinds, for clients and agents."""
    return {
        "stages": cv.STAGE_LABELS,
        "day_statuses": cv.DAY_STATUS_LABELS,
        "mark_statuses": list(cv.MARK_STATUSES),
        "kinds": list(cv.HABIT_KINDS),
        "spec_defaults": {
            "rules": cv.DEFAULT_RULES,
            "stabilization": cv.DEFAULT_STABILIZATION,
            "integration": cv.DEFAULT_INTEGRATION,
            "maintenance": cv.DEFAULT_MAINTENANCE,
        },
    }
