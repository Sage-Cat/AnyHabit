"""Restore a JSON export produced by ``GET /export/``.

Export without import is a one-way door: it lets you look at your data but not
get it back. This closes the loop, which is what makes "take a backup before
upgrading" real advice rather than a gesture.

Two modes:

``merge`` (default)
    Adds what is missing and leaves everything else alone.  Trackers are
    matched on name + category; logs and journals are matched on timestamp so
    re-importing the same file twice does not duplicate history.

``replace``
    Deletes the caller's existing trackers first, then imports.  Destructive by
    design, and gated behind an explicit confirmation string.
"""

from __future__ import annotations

import json
from datetime import date, datetime
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile, status
from sqlalchemy.orm import Session

from .. import cultivation as cv
from .. import models, schemas
from ..deps import get_current_user, get_db
from ..time_utils import ensure_utc, to_utc, utcnow

router = APIRouter(prefix="/import", tags=["import"])

# v1.2.0 served the importer at /export/import/. Both addresses reach the same
# handler so upgrading does not silently break anyone's tooling.
legacy_router = APIRouter(prefix="/export", tags=["import"])

MAX_UPLOAD_BYTES = int(1024 * 1024 * 25)
REPLACE_CONFIRMATION = "ЗАМІНИТИ МОЇ ДАНІ"
# The upstream English phrase stays valid so existing API clients keep working.
REPLACE_CONFIRMATIONS = {REPLACE_CONFIRMATION, "REPLACE MY DATA"}

VALID_TYPES = {"quit", "build", "boolean"}
VALID_PERIODS = {"day", "week", "month", "year"}


def _parse_timestamp(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return to_utc(value)

    text = str(value).strip()
    if not text:
        return None

    # ``fromisoformat`` on Python 3.10 rejects the trailing "Z" that our own
    # exports and most other tools emit.
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"

    try:
        return to_utc(datetime.fromisoformat(text))
    except ValueError:
        return None


def _stamp_key(value: Any) -> str:
    """Comparable form of a timestamp, whatever shape it arrives in.

    SQLite hands datetimes back naive while parsed import values are aware, so
    comparing ``isoformat()`` directly never matched and every re-import
    duplicated the whole history.
    """
    normalized = ensure_utc(value) if value is not None else None
    return normalized.isoformat() if normalized else ""


def _coerce_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _coerce_int(value: Any, default: int = 1) -> int:
    try:
        return max(1, int(value))
    except (TypeError, ValueError):
        return default


def _clean_str(value: Any, default: str = "", limit: int = 2000) -> str:
    if value is None:
        return default
    return str(value).strip()[:limit]


def _tracker_key(name: str, category: str) -> tuple[str, str]:
    return (name.strip().lower(), (category or "General").strip().lower())


def _validated_tracker_fields(raw: dict, warnings: list[str]) -> dict | None:
    name = _clean_str(raw.get("name"), limit=120)
    if not name:
        warnings.append("Пропущено звичку без назви.")
        return None

    tracker_type = _clean_str(raw.get("type"), "build", limit=20).lower()
    if tracker_type not in VALID_TYPES:
        warnings.append(f"Пропущено «{name}»: невідомий тип звички «{tracker_type}».")
        return None

    units_per = _clean_str(raw.get("units_per"), "day", limit=10).lower()
    impact_per = _clean_str(raw.get("impact_per"), "day", limit=10).lower()

    start_date = _parse_timestamp(raw.get("start_date")) or utcnow()

    return {
        "name": name,
        "description": _clean_str(raw.get("description"), limit=2000),
        "color": _clean_str(raw.get("color"), limit=32),
        "category": _clean_str(raw.get("category"), "General", limit=60) or "General",
        "type": tracker_type,
        "unit": _clean_str(raw.get("unit"), limit=32),
        "impact_amount": max(0.0, _coerce_float(raw.get("impact_amount"))),
        "impact_unit": _clean_str(raw.get("impact_unit"), "$", limit=16) or "$",
        "impact_per": impact_per if impact_per in VALID_PERIODS else "day",
        "units_per_amount": max(0.0, _coerce_float(raw.get("units_per_amount"))),
        "units_per": units_per if units_per in VALID_PERIODS else "day",
        "units_per_interval": _coerce_int(raw.get("units_per_interval"), 1),
        "is_active": bool(raw.get("is_active", True)),
        "start_date": start_date,
        "current_streak_start_date": _parse_timestamp(raw.get("current_streak_start_date")) or start_date,
        "archived_at": _parse_timestamp(raw.get("archived_at")),
    }


def _apply_import(
    db: Session,
    payload: dict,
    user: models.User,
    mode: str,
    dry_run: bool,
    allow_cultivation: bool = True,
) -> schemas.ImportSummary:
    warnings: list[str] = []

    if not isinstance(payload, dict):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Файл резервної копії не є коректним JSON")

    declared_format = payload.get("format")
    is_recognised = declared_format == "anyhabit-backup" or payload.get("export_type") == "backup"
    if declared_format and not is_recognised:
        warnings.append(f"Файл має формат «{declared_format}»; імпорт виконується без гарантій.")

    raw_trackers = payload.get("trackers")
    if not isinstance(raw_trackers, list):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="У файлі немає звичок. Для відновлюваної копії експортуйте «Усі дані».",
        )

    summary = schemas.ImportSummary(
        dry_run=dry_run,
        mode=mode,
        source_version=payload.get("app_version"),
        source_exported_at=payload.get("export_date"),
    )

    existing_trackers = db.query(models.Tracker).filter(models.Tracker.owner_id == user.id).all()
    raw_cultivation = payload.get("cultivation")
    if raw_cultivation is not None and not isinstance(raw_cultivation, dict):
        warnings.append("Розділ культивації пошкоджений і пропущений.")
        raw_cultivation = None
    if raw_cultivation is not None and not allow_cultivation:
        # Passports, stages and the rank ladder change only with the user's
        # consent; a file sent with an API token must not bypass that.
        warnings.append("Розділ культивації через API-токен не імпортується: відновіть копію у вебінтерфейсі.")
        raw_cultivation = None
    plan, invalid_habits = _plan_cultivation(raw_cultivation, summary, warnings) if raw_cultivation else ([], 0)
    existing_habits = db.query(models.CultivatedHabit).filter(models.CultivatedHabit.user_id == user.id).all()
    # Deleting trackers unlinks cultivated habits (ON DELETE SET NULL); remember
    # what each was linked to, so a file without a cultivation section can
    # link them to the restored trackers again.
    tracker_keys = {t.id: _tracker_key(t.name or "", t.category or "") for t in existing_trackers}
    relink = {h.id: tracker_keys[h.tracker_id] for h in existing_habits if h.tracker_id in tracker_keys}

    if mode == "replace":
        summary.trackers_deleted = len(existing_trackers)
        if not dry_run and existing_trackers:
            tracker_ids = [tracker.id for tracker in existing_trackers]
            db.query(models.HabitLog).filter(models.HabitLog.tracker_id.in_(tracker_ids)).delete(
                synchronize_session=False
            )
            db.query(models.JournalEntry).filter(models.JournalEntry.tracker_id.in_(tracker_ids)).delete(
                synchronize_session=False
            )
            db.query(models.TrackerParticipant).filter(
                models.TrackerParticipant.tracker_id.in_(tracker_ids)
            ).delete(synchronize_session=False)
            db.query(models.Tracker).filter(models.Tracker.id.in_(tracker_ids)).delete(synchronize_session=False)
            db.flush()
        if raw_cultivation is not None and invalid_habits:
            warnings.append("Частину звичок культивації у файлі пошкоджено, тому наявні звички збережено.")
        elif raw_cultivation is not None:
            # The file carries its own cultivation history, which replaces ours.
            summary.cultivation_habits_deleted = len(existing_habits)
            if not dry_run and existing_habits:
                db.query(models.CultivatedHabit).filter(
                    models.CultivatedHabit.id.in_([h.id for h in existing_habits])
                ).delete(synchronize_session=False)
                db.flush()
            existing_habits = []
        existing_by_key: dict[tuple[str, str], models.Tracker] = {}
    else:
        existing_by_key = {
            _tracker_key(tracker.name or "", tracker.category or ""): tracker for tracker in existing_trackers
        }

    imported_by_source: dict[str, models.Tracker | None] = {}
    imported_by_name: dict[str, models.Tracker | None] = {}
    for raw_tracker in raw_trackers:
        if not isinstance(raw_tracker, dict):
            warnings.append("Пропущено пошкоджений запис звички.")
            continue

        fields = _validated_tracker_fields(raw_tracker, warnings)
        if fields is None:
            summary.trackers_skipped += 1
            continue

        key = _tracker_key(fields["name"], fields["category"])
        tracker = existing_by_key.get(key)
        source_id = raw_tracker.get("id")

        if tracker is None:
            summary.trackers_created += 1
            if not dry_run:
                tracker = models.Tracker(owner_id=user.id, visibility="private", **fields)
                db.add(tracker)
                db.flush()
                db.add(
                    models.TrackerParticipant(
                        tracker_id=tracker.id, user_id=user.id, role="owner", added_at=utcnow()
                    )
                )
                existing_by_key[key] = tracker
        else:
            # An existing tracker keeps its own configuration; only its missing
            # history is filled in, so a merge can never silently rewrite the
            # settings someone is actively using.
            summary.trackers_updated += 1
        if source_id is not None:
            imported_by_source[str(source_id)] = tracker
        imported_by_name.setdefault(fields["name"].strip().lower(), tracker)

        # Timestamps already on file, so re-importing the same backup is a
        # no-op rather than a duplicate.  Computed for dry runs too, otherwise a
        # preview would over-count history the user already has.
        existing_log_stamps: set[str] = set()
        existing_journal_stamps: set[str] = set()
        if tracker is not None:
            existing_log_stamps = {
                _stamp_key(ts)
                for (ts,) in db.query(models.HabitLog.timestamp)
                .filter(models.HabitLog.tracker_id == tracker.id, models.HabitLog.user_id == user.id)
                .all()
            }
            existing_journal_stamps = {
                _stamp_key(ts)
                for (ts,) in db.query(models.JournalEntry.timestamp)
                .filter(models.JournalEntry.tracker_id == tracker.id, models.JournalEntry.user_id == user.id)
                .all()
            }

        for raw_log in raw_tracker.get("logs") or []:
            if not isinstance(raw_log, dict):
                continue
            timestamp = _parse_timestamp(raw_log.get("timestamp"))
            if timestamp is None:
                warnings.append(f"Пропущено запис у «{fields['name']}» з нечитабельним часом.")
                continue
            if _stamp_key(timestamp) in existing_log_stamps:
                continue

            summary.logs_created += 1
            if not dry_run and tracker is not None:
                db.add(
                    models.HabitLog(
                        tracker_id=tracker.id,
                        user_id=user.id,
                        timestamp=timestamp,
                        amount=_coerce_float(raw_log.get("amount"), 1.0),
                        note=_clean_str(raw_log.get("note"), limit=500),
                    )
                )
                existing_log_stamps.add(_stamp_key(timestamp))

        for raw_journal in raw_tracker.get("journals") or []:
            if not isinstance(raw_journal, dict):
                continue
            timestamp = _parse_timestamp(raw_journal.get("timestamp"))
            if timestamp is None:
                warnings.append(f"Пропущено нотатку щоденника в «{fields['name']}» з нечитабельним часом.")
                continue
            if _stamp_key(timestamp) in existing_journal_stamps:
                continue

            content = _clean_str(raw_journal.get("content"), limit=10000)
            if not content:
                continue

            mood = raw_journal.get("mood")
            try:
                mood_value = int(mood) if mood is not None else None
            except (TypeError, ValueError):
                mood_value = None
            if mood_value is not None and not 1 <= mood_value <= 5:
                mood_value = None

            summary.journals_created += 1
            if not dry_run and tracker is not None:
                db.add(
                    models.JournalEntry(
                        tracker_id=tracker.id,
                        user_id=user.id,
                        timestamp=timestamp,
                        mood=mood_value,
                        content=content,
                        is_relapse=bool(raw_journal.get("is_relapse", False)),
                    )
                )
                existing_journal_stamps.add(_stamp_key(timestamp))

    if mode == "replace" and not dry_run:
        kept = {habit.id for habit in existing_habits}
        for habit_id, key in relink.items():
            tracker = existing_by_key.get(key)
            if habit_id in kept and tracker is not None:
                # An explicit UPDATE: the database already nulled the link, but
                # the loaded object may still hold an id the new tracker reuses.
                db.query(models.CultivatedHabit).filter(models.CultivatedHabit.id == habit_id).update(
                    {"tracker_id": tracker.id}, synchronize_session=False
                )
    if raw_cultivation is not None:
        _import_cultivation(db, user, plan, raw_cultivation.get("profile"), mode, dry_run, existing_habits,
                            imported_by_source, imported_by_name, summary, warnings)

    if dry_run:
        db.rollback()
    else:
        db.commit()

    summary.warnings = warnings[:50]
    return summary


def _import_date(value: Any) -> date | None:
    if not isinstance(value, str):
        return None
    try:
        day = date.fromisoformat(value)
    except ValueError:
        return None
    return day if day >= cv.MIN_DATE else None


def _as_list(value: Any) -> list:
    return value if isinstance(value, list) else []


def _author_of(raw: dict) -> str:
    return raw.get("author") if raw.get("author") in ("user", "api") else "user"


def _plan_cultivation(raw: dict, summary: schemas.ImportSummary, warnings: list[str]) -> tuple[list[dict], int]:
    """Validate every cultivated habit in the file before anything is deleted.

    Returns the importable habits and how many were rejected, so a replace
    never removes the user's habits in favour of ones that cannot be read.
    """
    plan: list[dict] = []
    invalid = 0
    raw_habits = raw.get("habits")
    if raw_habits is not None and not isinstance(raw_habits, list):
        warnings.append("Список звичок культивації пошкоджений.")
        return [], 1
    for raw_habit in raw_habits or []:
        problem, versions, name = "", [], ""
        if not isinstance(raw_habit, dict):
            problem = "пошкоджений запис"
        elif raw_habit.get("kind") not in cv.HABIT_KINDS:
            problem = "невідомий тип звички"
        elif not _as_list(raw_habit.get("versions")):
            problem = "немає версій паспорта"
        else:
            for raw_version in raw_habit["versions"]:
                spec = raw_version.get("spec") if isinstance(raw_version, dict) else None
                if isinstance(spec, dict):
                    name = str(spec.get("name") or name).strip()
                effective = _import_date(raw_version.get("effective_from")) if isinstance(raw_version, dict) else None
                try:
                    if effective is None:
                        raise cv.PassportError("невідома дата чинності")
                    cv.validate_spec(raw_habit["kind"], spec)
                except cv.PassportError as exc:
                    problem = str(exc)
                    break
                versions.append((effective, raw_version, spec))
        if problem:
            warnings.append(f"Пропущено звичку культивації «{name or '?'}»: {problem}.")
            summary.cultivation_habits_skipped += 1
            invalid += 1
            continue
        versions.sort(key=lambda item: item[0])
        plan.append({"kind": raw_habit["kind"], "name": str(versions[-1][2]["name"]).strip(),
                     "versions": versions, "raw": raw_habit})
    return plan, invalid


def _import_cultivation(
    db: Session,
    user: models.User,
    plan: list[dict],
    raw_profile: Any,
    mode: str,
    dry_run: bool,
    existing_habits: list[models.CultivatedHabit],
    by_source: dict[str, models.Tracker | None],
    by_name: dict[str, models.Tracker | None],
    summary: schemas.ImportSummary,
    warnings: list[str],
) -> None:
    """Restore passports, day marks, minimum modes and the rank ladder.

    A habit is matched on kind + current name; a match is left alone in merge
    mode, like an existing tracker.  Every restored habit is analysed before
    commit, so nothing the app cannot read is ever stored.
    """
    from .cultivation import _analyse

    existing_names = set()
    for habit in existing_habits:
        latest = (
            db.query(models.CultivationPassportVersion)
            .filter(models.CultivationPassportVersion.habit_id == habit.id)
            .order_by(models.CultivationPassportVersion.effective_from.desc(), models.CultivationPassportVersion.id.desc())
            .first()
        )
        if latest is not None:
            existing_names.add((habit.kind, str(json.loads(latest.spec_json).get("name", "")).strip().lower()))

    created: list[tuple[str, models.CultivatedHabit]] = []
    for item in plan:
        kind, name, raw_habit = item["kind"], item["name"], item["raw"]
        if (kind, name.lower()) in existing_names:
            summary.cultivation_habits_existing += 1
            continue

        # by_source holds None for a tracker that a dry run would create, so
        # "known but not created yet" and "missing from the file" stay distinct.
        source_id, tracker_name = raw_habit.get("tracker_id"), raw_habit.get("tracker_name")
        found, tracker = False, None
        if source_id is not None and str(source_id) in by_source:
            found, tracker = True, by_source[str(source_id)]
        elif tracker_name and str(tracker_name).strip().lower() in by_name:
            found, tracker = True, by_name[str(tracker_name).strip().lower()]
        if not found and (source_id is not None or tracker_name):
            warnings.append(f"«{name}»: трекер не знайдено у файлі; звичку буде відновлено без трекера.")

        summary.cultivation_habits_created += 1
        existing_names.add((kind, name.lower()))
        if dry_run:
            continue

        habit = models.CultivatedHabit(
            user_id=user.id,
            tracker_id=tracker.id if tracker is not None else None,
            kind=kind,
            archived_at=_parse_timestamp(raw_habit.get("archived_at")),
        )
        db.add(habit)
        db.flush()
        for effective, raw_version, spec in item["versions"]:
            db.add(
                models.CultivationPassportVersion(
                    habit_id=habit.id,
                    effective_from=effective.isoformat(),
                    created_at=_parse_timestamp(raw_version.get("created_at")) or utcnow(),
                    reason=_clean_str(raw_version.get("reason"), "Імпорт", limit=2000) or "Імпорт",
                    author=_author_of(raw_version),
                    spec_json=json.dumps(spec, ensure_ascii=False),
                )
            )
        for raw_mark in _as_list(raw_habit.get("marks")):
            day = _import_date(raw_mark.get("date")) if isinstance(raw_mark, dict) else None
            if day is None or raw_mark.get("status") not in cv.MARK_STATUSES:
                continue
            db.add(
                models.CultivationDayMark(
                    habit_id=habit.id,
                    date=day.isoformat(),
                    status=raw_mark["status"],
                    reason=_clean_str(raw_mark.get("reason"), limit=2000),
                    author=_author_of(raw_mark),
                    created_at=_parse_timestamp(raw_mark.get("created_at")) or utcnow(),
                )
            )
        for raw_mode in _as_list(raw_habit.get("modes")):
            start = _import_date(raw_mode.get("start_date")) if isinstance(raw_mode, dict) else None
            if start is None:
                continue
            end = _import_date(raw_mode.get("end_date"))
            db.add(
                models.CultivationMode(
                    habit_id=habit.id,
                    start_date=start.isoformat(),
                    end_date=end.isoformat() if end and end >= start else None,
                    reason=_clean_str(raw_mode.get("reason"), "Імпорт", limit=2000) or "Імпорт",
                    end_reason=_clean_str(raw_mode.get("end_reason"), limit=2000),
                    author=_author_of(raw_mode),
                )
            )
        created.append((name, habit))

    if created:
        db.flush()
        for name, habit in created:
            try:
                _analyse(db, user, habit, history_days=0)
            except (cv.PassportError, ValueError, TypeError, KeyError) as exc:
                db.rollback()
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Звичку культивації «{name}» з файлу не вдається прочитати: {exc}. Нічого не змінено.",
                ) from None

    if isinstance(raw_profile, dict):
        profile = db.query(models.CultivationProfile).filter(models.CultivationProfile.user_id == user.id).first()
        if profile is not None and mode != "replace":
            return  # merge keeps the ladder the user already has
        ranks = raw_profile.get("ranks")
        try:
            ranks = cv.validate_ranks(ranks) if ranks else None
        except cv.PassportError as exc:
            warnings.append(f"Власну систему рангів пропущено: {exc}.")
            ranks = None
        if dry_run:
            return
        if profile is None:
            profile = models.CultivationProfile(user_id=user.id)
            db.add(profile)
        profile.ranks_json = json.dumps(ranks, ensure_ascii=False) if ranks else ""


@legacy_router.post("/import/", response_model=schemas.ImportSummary, include_in_schema=False)
@router.post("/", response_model=schemas.ImportSummary)
async def import_data(
    request: Request,
    file: UploadFile = File(..., description="A JSON export produced by GET /export/"),
    mode: str = Query("merge", description="merge or replace"),
    dry_run: bool = Query(True, description="Preview the result without writing anything"),
    confirm: str = Query("", description=f"Required for replace mode: '{REPLACE_CONFIRMATION}'"),
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if mode not in {"merge", "replace"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="mode має бути 'merge' або 'replace'")

    if mode == "replace" and not dry_run and confirm.strip() not in REPLACE_CONFIRMATIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Режим заміни видаляє наявні звички. Підтвердьте значенням «{REPLACE_CONFIRMATION}».",
        )

    raw = await file.read()
    if len(raw) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Файл резервної копії має бути не більшим за {MAX_UPLOAD_BYTES // (1024 * 1024)} МБ",
        )

    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Файл не є коректним JSON. Експорт у CSV імпортувати не можна.",
        ) from exc

    via_token = getattr(request.state, "auth_via", None) == "api_token"
    return _apply_import(db, payload, current_user, mode, dry_run, allow_cultivation=not via_token)
