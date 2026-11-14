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
from ..security import looks_like_api_token
from ..time_utils import PeriodContext, ensure_utc, resolve_timezone, utcnow
from .logs import create_log

router = APIRouter(prefix="/cultivation", tags=["cultivation"])

KIND_TRACKER_TYPES = {"sleep": "build", "build": "build", "boolean": "boolean", "quit": "quit"}
RANK_REQ_KEYS = {"active", "stabilizing", "integrated", "durable"}


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
    stage: Literal["planned", "formation", "stabilization", "integrated", "recovery"]
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


class ModeEnd(BaseModel):
    end_date: Optional[date] = None
    reason: str = Field(default="", max_length=2000)


class SleepEntry(BaseModel):
    bedtime: datetime = Field(description="When you fell asleep; a naive value is read in your timezone")
    wake: datetime = Field(description="When you woke up; a naive value is read in your timezone")
    reason: str = Field(default="", max_length=500, description="Reason for a deviation, if any")
    state: str = Field(default="", max_length=200, description="How the next day felt")
    note: str = Field(default="", max_length=1000)


class ProfileUpdate(BaseModel):
    ranks: Optional[list[dict[str, Any]]] = Field(default=None, description="Rank ladder; null restores the default")
    recovery_grace_days: Optional[int] = Field(default=None, ge=0, le=3650)


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------


def _author(request: Request) -> str:
    header = request.headers.get("authorization", "")
    if header.lower().startswith("bearer ") and looks_like_api_token(header[7:].strip()):
        return "api"
    return "user"


def _require_user_confirmation(request: Request, confirmed: bool) -> str:
    """Goals and criteria change only with the user's consent.

    The web UI acts for the user directly; a script or AI agent using an API
    token must state that the user approved this exact change.
    """
    author = _author(request)
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
        local = ensure_utc(log.timestamp).astimezone(tz)
        obs = out.setdefault(local.date(), cv.Observation())
        obs.events += 1
        obs.amount += float(log.amount or 0)
        obs.notes.append(log.note or "")
        if habit.kind == "sleep" and log.amount and log.amount > 0:
            obs.nights.append(cv.Night(log.id, local - timedelta(hours=float(log.amount)), local, log.note or ""))
    return out


def _profile(db: Session, user: models.User) -> tuple[list[dict], int, bool]:
    row = db.query(models.CultivationProfile).filter(models.CultivationProfile.user_id == user.id).first()
    if row is None:
        return cv.DEFAULT_RANKS, cv.RECOVERY_GRACE_DAYS, False
    ranks = json.loads(row.ranks_json) if row.ranks_json else cv.DEFAULT_RANKS
    grace = row.recovery_grace_days if row.recovery_grace_days is not None else cv.RECOVERY_GRACE_DAYS
    return ranks, grace, bool(row.ranks_json)


# ---------------------------------------------------------------------------
# Assembling responses
# ---------------------------------------------------------------------------


def _tracker_info(db: Session, habit: models.CultivatedHabit) -> dict | None:
    if habit.tracker_id is None:
        return None
    tracker = db.query(models.Tracker).filter(models.Tracker.id == habit.tracker_id).first()
    if tracker is None:
        return None
    return {"id": tracker.id, "name": tracker.name, "type": tracker.type, "unit": tracker.unit or ""}


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
    days = cv.build_days(habit.kind, versions, _observations(db, habit, user), _marks(db, habit), modes, today)
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
            if (today_spec or {}).get("minimum") else None,
            "degraded": degraded_today,
            "day": today_day.as_dict() if today_day else None,
        },
        "next_subgoal": None if not subgoals else {
            **subgoals[0],
            "requirement": cv.level_text(habit.kind, (subgoals[0] or {}).get("level"), unit),
        },
        "mode": None if active_mode is None else {
            **active_mode,
            "start_date": active_mode["start_date"].isoformat(),
            "end_date": None,
        },
        "modes": [
            {**m, "start_date": m["start_date"].isoformat(), "end_date": m["end_date"].isoformat() if m["end_date"] else None}
            for m in modes
        ],
        "rates": {
            "7": cv.rate(days, 7, today),
            "30": cv.rate(days, 30, today),
            "integration": cv.rate(days, int(cv.section(spec, "integration", cv.DEFAULT_INTEGRATION)["window_days"]), today),
        },
        "recovery": cv.recovery_summary(episodes, days, today, int(rules["recovery_ok_days"])),
        "episodes": [e.as_dict(today) for e in episodes[-30:]],
        "monthly": cv.monthly(episodes, days),
        "integration": integration,
        "recommendation": cv.recommendation(spec, days, episodes, today) if spec else None,
        "days": [d.as_dict() for d in days[-history_days:]] if history_days else [],
    }


def _compact(analysis: dict) -> dict:
    keep = ("id", "kind", "tracker", "name", "stage", "stage_label", "today", "next_subgoal", "mode",
            "recommendation", "integration")
    out = {key: analysis[key] for key in keep}
    out["success_rate_30"] = analysis["rates"]["30"]["success_rate"]
    out["recovery"] = {
        key: analysis["recovery"][key]
        for key in ("current_deviation", "last_recovery", "first_ok_median", "confirmed_median", "in_term_share", "tested")
    }
    out["priority"] = analysis["passport"].get("priority")
    out["days"] = analysis["days"][-14:]
    return out


def _rank(db: Session, user: models.User) -> dict:
    habits = (
        db.query(models.CultivatedHabit)
        .filter(models.CultivatedHabit.user_id == user.id, models.CultivatedHabit.archived_at.is_(None))
        .all()
    )
    ranks, grace, custom = _profile(db, user)
    report = cv.compute_rank({h.id: _versions(db, h) for h in habits}, _today(user), ranks, grace)
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
    by_priority = sorted(analyses, key=lambda a: (a["priority"] is None, a["priority"] or 0, a["id"]))
    warnings = []
    for item in analyses:
        rec = item["recommendation"]
        if item["stage"] == "integrated" and rec and rec["to"] == "recovery":
            warnings.append({"habit_id": item["id"], "message": f"«{item['name']}»: стійкість погіршується. {rec['reason']}"})
    return {
        "date": _today(current_user).isoformat(),
        "timezone": current_user.timezone or "UTC",
        "active": [a for a in by_priority if a["stage"] in ("formation", "stabilization", "recovery")],
        "integrated": [a for a in by_priority if a["stage"] == "integrated"],
        "planned": [a for a in by_priority if a["stage"] == "planned"],
        "warnings": warnings,
        "rank": _rank(db, current_user),
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
    db.commit()
    return _analyse(db, current_user, habit)


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
    days = cv.build_days(habit.kind, versions, _observations(db, habit, current_user), _marks(db, habit),
                         _modes(db, habit), min(end or today, today))
    return [d.as_dict() for d in days if (start is None or d.date >= start)]


def _add_version(db: Session, habit: models.CultivatedHabit, user: models.User, spec: dict, reason: str,
                 effective_from: Optional[date], author: str) -> None:
    try:
        cv.validate_spec(habit.kind, spec)
    except cv.PassportError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from None
    versions = _versions(db, habit)
    effective = effective_from or _today(user)
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
    db.commit()


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
    habit = _get_habit(db, current_user, habit_id)
    if (payload.spec is None) == (payload.patch is None):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Передайте або spec, або patch")
    current = cv.latest_spec(_versions(db, habit)) or {}
    spec = payload.spec if payload.spec is not None else cv.merge_patch(current, payload.patch)
    _add_version(db, habit, current_user, spec, payload.reason, payload.effective_from, author)
    return _analyse(db, current_user, habit)


@router.post("/habits/{habit_id}/stage", status_code=status.HTTP_201_CREATED)
def change_stage(
    habit_id: int,
    payload: StageChange,
    request: Request,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    author = _require_user_confirmation(request, payload.confirmed_by_user)
    habit = _get_habit(db, current_user, habit_id)
    current = cv.latest_spec(_versions(db, habit)) or {}
    if current.get("stage") == payload.stage:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Звичка вже на цьому етапі")
    spec = cv.merge_patch(current, {"stage": payload.stage})
    _add_version(db, habit, current_user, spec, payload.reason, payload.effective_from, author)
    return _analyse(db, current_user, habit)


@router.post("/habits/{habit_id}/marks", status_code=status.HTTP_201_CREATED)
def mark_day(
    habit_id: int,
    payload: DayMarkCreate,
    request: Request,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Record a manual verdict for one day (``clear`` removes the previous one)."""
    habit = _get_habit(db, current_user, habit_id)
    if payload.date > _today(current_user):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Не можна позначати майбутні дні")
    if payload.status != "clear" and not payload.reason.strip():
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Вкажіть причину позначки")
    db.add(
        models.CultivationDayMark(
            habit_id=habit.id,
            date=payload.date.isoformat(),
            status=payload.status,
            reason=payload.reason.strip(),
            author=_author(request),
        )
    )
    db.commit()
    days = habit_days(habit_id, payload.date, payload.date, current_user, db)
    return days[0] if days else {"date": payload.date.isoformat(), "status": "no_data"}


@router.post("/habits/{habit_id}/modes/start", status_code=status.HTTP_201_CREATED)
def start_mode(
    habit_id: int,
    payload: ModeStart,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Enter controlled degradation: the minimum level becomes the requirement until it ends."""
    habit = _get_habit(db, current_user, habit_id)
    if any(m["end_date"] is None for m in _modes(db, habit)):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Режим мінімуму вже активний")
    db.add(
        models.CultivationMode(
            habit_id=habit.id,
            start_date=(payload.start_date or _today(current_user)).isoformat(),
            reason=payload.reason.strip(),
        )
    )
    db.commit()
    return _analyse(db, current_user, habit, history_days=14)


@router.post("/habits/{habit_id}/modes/end")
def end_mode(
    habit_id: int,
    payload: ModeEnd,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    habit = _get_habit(db, current_user, habit_id)
    row = (
        db.query(models.CultivationMode)
        .filter(models.CultivationMode.habit_id == habit.id, models.CultivationMode.end_date.is_(None))
        .first()
    )
    if row is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Режим мінімуму не активний")
    end = payload.end_date or _today(current_user)
    if end < date.fromisoformat(row.start_date):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Дата завершення раніша за початок")
    row.end_date = end.isoformat()
    row.end_reason = payload.reason.strip()
    row.ended_at = utcnow()
    db.commit()
    return _analyse(db, current_user, habit, history_days=14)


@router.post("/habits/{habit_id}/sleep", status_code=status.HTTP_201_CREATED)
def log_sleep(
    habit_id: int,
    payload: SleepEntry,
    current_user: models.User = Depends(get_current_user),
    context: PeriodContext = Depends(get_period_context),
    db: Session = Depends(get_db),
):
    """Record one night: stored as a tracker log (amount = hours, timestamp = wake-up)."""
    habit = _get_habit(db, current_user, habit_id)
    if habit.kind != "sleep" or habit.tracker_id is None:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Це не звичка сну з трекером")
    tz = resolve_timezone(current_user.timezone)

    def aware(value: datetime) -> datetime:
        return value.replace(tzinfo=tz) if value.tzinfo is None else value

    bedtime, wake = aware(payload.bedtime), aware(payload.wake)
    hours = (wake - bedtime).total_seconds() / 3600
    if not 0 < hours <= 24:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Підйом має бути пізніше засинання (до 24 год)")
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
def archive_habit(habit_id: int, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    habit = _get_habit(db, current_user, habit_id)
    habit.archived_at = habit.archived_at or utcnow()
    db.commit()
    return {"id": habit.id, "archived": True}


@router.post("/habits/{habit_id}/unarchive")
def unarchive_habit(habit_id: int, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    habit = _get_habit(db, current_user, habit_id)
    habit.archived_at = None
    db.commit()
    return {"id": habit.id, "archived": False}


@router.get("/rank")
def rank(current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    return _rank(db, current_user)


@router.get("/profile")
def get_profile(current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    ranks, grace, custom = _profile(db, current_user)
    return {"ranks": ranks, "recovery_grace_days": grace, "custom_ladder": custom, "default_ranks": cv.DEFAULT_RANKS}


@router.put("/profile")
def update_profile(
    payload: ProfileUpdate,
    request: Request,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if _author(request) == "api":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Систему рангів змінює лише користувач у вебінтерфейсі")
    if payload.ranks is not None:
        if not payload.ranks:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Порожній список рангів")
        for rank_def in payload.ranks:
            if not str(rank_def.get("name") or "").strip() or not isinstance(rank_def.get("req", {}), dict):
                raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Кожен ранг потребує name і req")
            unknown = set(rank_def.get("req", {})) - RANK_REQ_KEYS
            if unknown:
                raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                                    detail=f"Невідомі вимоги рангу: {', '.join(sorted(unknown))}")
    row = db.query(models.CultivationProfile).filter(models.CultivationProfile.user_id == current_user.id).first()
    if row is None:
        row = models.CultivationProfile(user_id=current_user.id)
        db.add(row)
    if "ranks" in payload.model_fields_set:
        row.ranks_json = json.dumps(payload.ranks, ensure_ascii=False) if payload.ranks else ""
    if payload.recovery_grace_days is not None:
        row.recovery_grace_days = payload.recovery_grace_days
    db.commit()
    return get_profile(current_user, db)


def export_cultivation(db: Session, user: models.User) -> dict:
    """Full cultivation history for backups and the JSON export."""
    habits = db.query(models.CultivatedHabit).filter(models.CultivatedHabit.user_id == user.id).order_by(models.CultivatedHabit.id)
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
                    {"date": m.date, "status": m.status, "reason": m.reason, "author": m.author,
                     "created_at": ensure_utc(m.created_at).isoformat() if m.created_at else None}
                    for m in marks
                ],
                "modes": [
                    {**m, "start_date": m["start_date"].isoformat(),
                     "end_date": m["end_date"].isoformat() if m["end_date"] else None}
                    for m in _modes(db, habit)
                ],
            }
        )
    if profile is not None:
        out["profile"] = {
            "ranks": json.loads(profile.ranks_json) if profile.ranks_json else None,
            "recovery_grace_days": profile.recovery_grace_days,
        }
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
