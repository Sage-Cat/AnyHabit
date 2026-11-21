"""Habit cultivation: passports, day states, deviations, recovery, stages and ranks.

AnyHabit trackers hold the raw facts (logs, relapses).  A *cultivated habit*
links one tracker to a versioned passport (goal, criteria, current sub-goal,
minimum safe level, stage) and derives from both:

* a state for every calendar day — success, minimum, fail, exception, no data;
  a missing record is never treated as a failure;
* deviation episodes and the time it took to recover from each one;
* readiness checks for the next stage (recommendations only — the stage itself
  changes only through an explicit passport version);
* a cultivation rank computed solely from the stages in the passports.

Everything here is pure: the router loads rows and passes plain data in.
"""

from __future__ import annotations

import bisect
import copy
import math
import statistics
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta, timezone

# ---------------------------------------------------------------------------
# Vocabulary
# ---------------------------------------------------------------------------

STAGES = ("planned", "formation", "stabilization", "integrated")
STAGE_LABELS = {
    "planned": "Запланована",
    "formation": "Формування",
    "stabilization": "Стабілізація",
    "integrated": "Інтегрована",
}
DAY_STATUSES = ("success", "minimum", "fail", "exception", "no_data", "unrated", "invalid")
DAY_STATUS_LABELS = {
    "success": "Успіх",
    "minimum": "Мінімум",
    "fail": "Порушення",
    "exception": "Виняток",
    "no_data": "Немає даних",
    "unrated": "Без критерію",
    "invalid": "Перевірити запис",
}
MARK_STATUSES = ("success", "minimum", "fail", "exception", "clear")
HABIT_KINDS = ("sleep", "build", "boolean", "quit")

MAX_VALID_SLEEP_HOURS = 16.0
MIN_NIGHT_HOURS = 1.0  # shorter sleep logs are naps or accidental taps

DEFAULT_RULES = {"confirm_days": 2, "recovery_ok_days": 2}
DEFAULT_STABILIZATION = {"window_days": 14, "min_success_rate": 0.7, "min_observed_days": 10}
DEFAULT_INTEGRATION = {
    "window_days": 42,
    "min_success_rate": 0.85,
    "max_recovery_days": 2,
    "min_observed_days": 30,
    "max_deviation_days": 7,
}
DEFAULT_MAINTENANCE = {"window_days": 28, "min_success_rate": 0.6, "max_deviation_days": 7}


class PassportError(ValueError):
    """A passport (or a change to it) is not valid."""


# ---------------------------------------------------------------------------
# Passport helpers
# ---------------------------------------------------------------------------


def parse_hhmm(value: str) -> time:
    try:
        return datetime.strptime(str(value), "%H:%M").time()
    except (TypeError, ValueError) as exc:
        raise PassportError(f"Час має бути у форматі ГГ:ХХ, отримано «{value}»") from exc


def section(spec: dict | None, key: str, defaults: dict) -> dict:
    return {**defaults, **((spec or {}).get(key) or {})}


def level_defined(kind: str, level: dict | None) -> bool:
    if kind == "sleep":
        return bool(level) and any(level.get(k) is not None for k in ("wake_by", "min_sleep_h", "max_sleep_h"))
    # boolean / quit are judged by the presence of an event; build may add a threshold
    return True


# Dates before this are typos, and would make every request walk decades of days.
MIN_DATE = date(2000, 1, 1)
RANK_REQ_KEYS = {"active", "stabilizing", "integrated", "durable"}


def check_number(
    label: str,
    value,
    *,
    integer: bool = False,
    low: float | None = None,
    high: float | None = None,
    low_exclusive: bool = False,
) -> float:
    """A finite number within bounds, or a PassportError naming the field."""
    kind = "ціле число" if integer else "число"
    # Strings are refused even when they look numeric: later code sorts and
    # compares these values, and "2" next to 1 would break every overview.
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise PassportError(f"{label}: очікується {kind}")
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise PassportError(f"{label}: очікується {kind}") from None
    if not math.isfinite(number) or (integer and not number.is_integer()):
        raise PassportError(f"{label}: очікується {kind}")
    if low is not None and (number <= low if low_exclusive else number < low):
        raise PassportError(f"{label}: має бути {'більше' if low_exclusive else 'не менше'} {low:g}")
    if high is not None and number > high:
        raise PassportError(f"{label}: має бути не більше {high:g}")
    return int(number) if integer else number


def check_date(label: str, value) -> date:
    try:
        if not isinstance(value, str):
            raise ValueError
        day = date.fromisoformat(value)
    except ValueError:
        raise PassportError(f"{label}: очікується дата РРРР-ММ-ДД, отримано «{value}»") from None
    if day < MIN_DATE:
        raise PassportError(f"{label}: дата раніша за {MIN_DATE.isoformat()}")
    return day


def _check_level(label: str, level) -> None:
    if level is None:
        return
    if not isinstance(level, dict):
        raise PassportError(f"{label}: очікується об'єкт")
    for key in ("wake_by", "done_by"):
        if level.get(key) is not None:
            parse_hhmm(level[key])
    bounds = {}
    for bound in ("min_sleep_h", "max_sleep_h"):
        if level.get(bound) is not None:
            bounds[bound] = check_number(
                f"{label}.{bound}", level[bound], low=0, low_exclusive=True, high=MAX_VALID_SLEEP_HOURS
            )
    if len(bounds) == 2 and bounds["min_sleep_h"] > bounds["max_sleep_h"]:
        raise PassportError(f"{label}: мінімальна тривалість більша за максимальну")
    if level.get("min_amount") is not None:
        check_number(f"{label}.min_amount", level["min_amount"], low=0)


def validate_spec(kind: str, spec: dict) -> None:
    """Reject anything the calculations below could not read.

    A passport that passed here must never make a later request fail, because
    history is append-only: a broken version could not be taken back.
    """
    if not isinstance(spec, dict):
        raise PassportError("Паспорт має бути об'єктом")
    if not str(spec.get("name") or "").strip():
        raise PassportError("Потрібна назва звички")
    if spec.get("stage") not in STAGES:
        raise PassportError(f"Етап має бути одним із: {', '.join(STAGES)}")
    if spec.get("start_date") is not None:
        check_date("start_date", spec["start_date"])
    if spec.get("priority") is not None:
        check_number("priority", spec["priority"])
    _check_level("level", spec.get("level"))
    _check_level("minimum", spec.get("minimum"))
    _check_level("tolerance", spec.get("tolerance"))
    subgoals = spec.get("subgoals")
    if subgoals is not None and not isinstance(subgoals, list):
        raise PassportError("subgoals: очікується список")
    for i, subgoal in enumerate(subgoals or []):
        if not isinstance(subgoal, dict):
            raise PassportError(f"subgoals[{i}]: очікується об'єкт")
        _check_level(f"subgoals[{i}].level", subgoal.get("level"))
    for key in ("rules", "stabilization", "integration", "maintenance"):
        if spec.get(key) is not None and not isinstance(spec[key], dict):
            raise PassportError(f"{key}: очікується об'єкт")
    rules = section(spec, "rules", DEFAULT_RULES)
    check_number("rules.confirm_days", rules["confirm_days"], integer=True, low=1, high=365)
    check_number("rules.recovery_ok_days", rules["recovery_ok_days"], integer=True, low=1, high=365)
    for key, defaults in (
        ("stabilization", DEFAULT_STABILIZATION),
        ("integration", DEFAULT_INTEGRATION),
        ("maintenance", DEFAULT_MAINTENANCE),
    ):
        block = section(spec, key, defaults)
        check_number(f"{key}.min_success_rate", block["min_success_rate"], low=0, low_exclusive=True, high=1)
        check_number(f"{key}.window_days", block["window_days"], integer=True, low=1, high=3650)
        for name in ("min_observed_days", "max_recovery_days", "max_deviation_days"):
            if name in block:
                check_number(f"{key}.{name}", block[name], integer=True, low=0, high=3650)


def validate_ranks(ranks) -> list[dict]:
    """Check a custom rank ladder and return it with every ``req`` present."""
    if not isinstance(ranks, list) or not ranks:
        raise PassportError("Порожній список рангів")
    out = []
    for i, rank in enumerate(ranks):
        if not isinstance(rank, dict) or not str(rank.get("name") or "").strip():
            raise PassportError(f"Ранг {i + 1}: потрібна назва")
        req = rank.get("req") or {}
        if not isinstance(req, dict):
            raise PassportError(f"Ранг «{rank['name']}»: req має бути об'єктом")
        unknown = set(req) - RANK_REQ_KEYS
        if unknown:
            raise PassportError(f"Невідомі вимоги рангу: {', '.join(sorted(unknown))}")
        if "active" in req and not isinstance(req["active"], bool):
            raise PassportError(f"Ранг «{rank['name']}»: active має бути true або false")
        if "stabilizing" in req and not isinstance(req["stabilizing"], bool):
            check_number(f"Ранг «{rank['name']}»: stabilizing", req["stabilizing"], integer=True, low=0, high=1000)
        if "integrated" in req:
            check_number(f"Ранг «{rank['name']}»: integrated", req["integrated"], integer=True, low=0, high=1000)
        if "durable" in req:
            durable = req["durable"]
            if not isinstance(durable, list) or len(durable) != 2:
                raise PassportError(f"Ранг «{rank['name']}»: durable має бути [кількість, днів]")
            check_number(f"Ранг «{rank['name']}»: durable[0]", durable[0], integer=True, low=0, high=1000)
            check_number(f"Ранг «{rank['name']}»: durable[1]", durable[1], integer=True, low=1, high=36500)
        out.append({**rank, "req": req})
    return out


def merge_patch(spec: dict, patch: dict) -> dict:
    """RFC 7386-style merge: nested dicts merge, ``None`` deletes, lists replace."""
    out = copy.deepcopy(spec)
    for key, value in (patch or {}).items():
        if value is None:
            out.pop(key, None)
        elif isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = merge_patch(out[key], value)
        else:
            out[key] = copy.deepcopy(value)
    return out


def spec_for(versions: list[dict], day: date) -> dict | None:
    """Passport in force on ``day``; versions are sorted by (effective_from, id)."""
    current = None
    for version in versions:
        if version["effective_from"] <= day:
            current = version["spec"]
    return current


def latest_spec(versions: list[dict]) -> dict | None:
    return max(versions, key=lambda v: (v["effective_from"], v["id"]))["spec"] if versions else None


def level_text(kind: str, level: dict | None, unit: str = "") -> str:
    level = level or {}
    if kind == "sleep":
        if not level_defined(kind, level):
            return "не задано"
        parts = []
        if level.get("wake_by") is not None:
            parts.append(f"підйом до {level['wake_by']}")
        lo, hi = level.get("min_sleep_h"), level.get("max_sleep_h")
        if lo is not None and hi is not None:
            parts.append(f"сон {lo:g}–{hi:g} год")
        elif lo is not None:
            parts.append(f"сон ≥ {lo:g} год")
        elif hi is not None:
            parts.append(f"сон ≤ {hi:g} год")
        return ", ".join(parts)
    if kind == "build" and level.get("min_amount") is not None:
        return f"≥ {float(level['min_amount']):g} {unit}".strip()
    if kind == "quit":
        return "без зриву"
    if kind == "boolean" and level.get("done_by") is not None:
        return f"виконати до {level['done_by']}"
    return "виконати"


def _hours_text(hours: float) -> str:
    return f"{round(hours, 1):g}".replace(".", ",")


def tolerance_defined(kind: str, tolerance: dict | None) -> bool:
    """A tolerance band only makes sense with a threshold to compare against."""
    if not tolerance:
        return False
    if kind == "boolean":
        return tolerance.get("done_by") is not None
    if kind == "build":
        return tolerance.get("min_amount") is not None
    return level_defined(kind, tolerance)


# ---------------------------------------------------------------------------
# Observations: what the tracker recorded for one calendar day
# ---------------------------------------------------------------------------


@dataclass
class Night:
    log_id: int
    bedtime: datetime  # local
    wake: datetime  # local
    note: str = ""

    @property
    def hours(self) -> float:
        # Elapsed time, not wall-clock difference: a night across a DST switch
        # is an hour longer or shorter than the clock suggests.
        return (self.wake.astimezone(timezone.utc) - self.bedtime.astimezone(timezone.utc)).total_seconds() / 3600


@dataclass
class Observation:
    nights: list[Night] = field(default_factory=list)  # sleep: grouped by local wake date
    amount: float = 0.0  # build / boolean: sum of logs that day
    events: int = 0  # number of logs (or relapses for quit)
    notes: list[str] = field(default_factory=list)
    first_at: time | None = None  # local time of the day's earliest log (not sleep)


def parse_note(note: str) -> dict:
    """Split a structured log note into reason / next-day state / free text."""
    fields = {"reason": "", "state": "", "note": []}
    for line in (note or "").splitlines():
        low = line.strip().lower()
        if low.startswith("причина:"):
            fields["reason"] = line.split(":", 1)[1].strip()
        elif low.startswith("стан:"):
            fields["state"] = line.split(":", 1)[1].strip()
        elif line.strip():
            fields["note"].append(line.strip())
    fields["note"] = "\n".join(fields["note"])
    return fields


def build_note(reason: str = "", state: str = "", note: str = "") -> str:
    lines = []
    if reason.strip():
        lines.append(f"Причина: {reason.strip()}")
    if state.strip():
        lines.append(f"Стан: {state.strip()}")
    if note.strip():
        lines.append(note.strip())
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Day classification
# ---------------------------------------------------------------------------


@dataclass
class Day:
    date: date
    status: str
    degraded: bool = False
    reason: str = ""
    detail: str = ""
    night: Night | None = None
    naps: int = 0
    amount: float = 0.0
    events: int = 0
    marked: bool = False
    warning: str = ""  # met only within the tolerance band: counts, but is flagged

    @property
    def met(self) -> bool | None:
        """True/False = requirement met/broken; None = neutral (no data, excused, unrated)."""
        if self.status == "success":
            return True
        if self.status == "minimum":
            # in degraded mode the minimum *is* the requirement
            return True if self.degraded else None
        if self.status == "fail":
            return False
        return None

    def as_dict(self) -> dict:
        out = {
            "date": self.date.isoformat(),
            "status": self.status,
            "status_label": DAY_STATUS_LABELS[self.status],
            "degraded": self.degraded,
            "reason": self.reason,
            "detail": self.detail,
            "marked": self.marked,
            "amount": self.amount,
            "events": self.events,
            "warning": self.warning,
        }
        if self.night:
            out["sleep"] = {
                "log_id": self.night.log_id,
                "bedtime": self.night.bedtime.isoformat(timespec="minutes"),
                "wake": self.night.wake.isoformat(timespec="minutes"),
                "hours": round(self.night.hours, 2),
                "state": parse_note(self.night.note)["state"],
                "naps": self.naps,
            }
        return out


def _meets(kind: str, obs: Observation, level: dict | None, night: Night | None) -> bool:
    level = level or {}
    if kind == "sleep":
        ok = True
        if level.get("wake_by") is not None:
            ok &= night.wake.time() <= parse_hhmm(level["wake_by"])
        if level.get("min_sleep_h") is not None:
            ok &= night.hours + 1e-9 >= float(level["min_sleep_h"])
        if level.get("max_sleep_h") is not None:
            ok &= night.hours - 1e-9 <= float(level["max_sleep_h"])
        return ok
    if kind == "build":
        threshold = level.get("min_amount")
        return obs.amount + 1e-9 >= float(threshold) if threshold is not None else obs.events > 0
    if kind == "boolean":
        if obs.events == 0:
            return False
        if level.get("done_by") is None or obs.first_at is None:
            return True
        # Minute precision: "by 18:00" includes a tap at 18:00:40.
        return obs.first_at.replace(second=0, microsecond=0) <= parse_hhmm(level["done_by"])
    return True


def _actual_text(kind: str, obs: Observation, night: Night | None, unit: str = "") -> str:
    if kind == "sleep" and night is not None:
        return f"підйом {night.wake:%H:%M}, сон {_hours_text(night.hours)} год"
    if kind == "boolean" and obs.first_at is not None:
        return f"виконано о {obs.first_at:%H:%M}"
    if kind == "build":
        return f"{obs.amount:g} {unit}".strip()
    return ""


def tolerance_warning(kind: str, obs: Observation, night: Night | None, spec: dict) -> str:
    actual = _actual_text(kind, obs, night)
    target = level_text(kind, spec.get("level"))
    allowed = level_text(kind, spec.get("tolerance"))
    head = f"{actual} — " if actual else ""
    return f"{head}поза ціллю ({target}), у межах допуску ({allowed})"


def classify(
    kind: str,
    day: date,
    obs: Observation | None,
    spec: dict | None,
    mark: dict | None,
    degraded: bool,
    today: date,
    tracked: bool = True,
) -> Day:
    obs = obs or Observation()
    result = Day(day, "no_data", degraded=degraded, amount=obs.amount, events=obs.events)

    if kind == "sleep":
        real = [n for n in obs.nights if n.hours >= MIN_NIGHT_HOURS]
        if real:
            # A mistyped 20-hour entry must not hide the real night next to it.
            plausible = [n for n in real if n.hours <= MAX_VALID_SLEEP_HOURS]
            result.night = max(plausible or real, key=lambda n: n.hours)
            result.naps = len(obs.nights) - 1
            result.reason = parse_note(result.night.note)["reason"]
        elif obs.nights:
            result.naps = len(obs.nights)
            result.detail = f"лише записи коротші за {MIN_NIGHT_HOURS:g} год"
    elif obs.notes:
        result.reason = parse_note(obs.notes[-1])["reason"]

    if mark:
        result.status, result.reason = mark["status"], mark.get("reason", "")
        result.detail, result.marked = "позначено вручну", True
        return result

    has_data = result.night is not None if kind == "sleep" else obs.events > 0
    if spec is None:
        # recorded before the passport existed: a fact without a criterion
        if has_data:
            result.status = "unrated"
        return result

    if kind == "sleep":
        if result.night is None:
            return result
        if result.night.hours > MAX_VALID_SLEEP_HOURS:
            result.status = "invalid"
            result.detail = f"запис на {result.night.hours:.1f} год — можливо, помилка"
            return result
        night = result.night
    else:
        night = None
        if kind == "quit":
            if obs.events:
                result.status = "fail"
            elif day < today and tracked:
                # Abstinence is the default state of a quit habit: a past day
                # without a relapse is a success, today is still open.
                result.status = "success"
            return result
        if obs.events == 0:
            return result  # nothing recorded ≠ not done

    level = spec.get("level")
    if not level_defined(kind, level):
        result.status = "unrated"
        return result
    tolerance = spec.get("tolerance")
    if _meets(kind, obs, level, night):
        result.status = "success"
    elif tolerance_defined(kind, tolerance) and _meets(kind, obs, tolerance, night):
        result.status = "success"
        result.warning = tolerance_warning(kind, obs, night, spec)
    elif spec.get("minimum") and level_defined(kind, spec.get("minimum")) and _meets(kind, obs, spec["minimum"], night):
        result.status = "minimum"
    else:
        result.status = "fail"
    return result


def mode_on(modes: list[dict], day: date) -> dict | None:
    for mode in modes:
        end = mode["end_date"] or date.max
        if mode["start_date"] <= day <= end:
            return mode
    return None


def build_days(
    kind: str,
    versions: list[dict],
    observations: dict[date, Observation],
    marks: dict[date, dict],
    modes: list[dict],
    until: date,
    today: date | None = None,
    tracked: bool = True,
) -> list[Day]:
    """Day states up to ``until``; ``today`` (default ``until``) is the still-open day.

    ``tracked`` is False when no tracker feeds the habit: then nothing can be
    inferred, not even the abstinence of a quit habit.
    """
    today = today or until
    starts = [
        date.fromisoformat(v["spec"]["start_date"]) if v["spec"].get("start_date") else v["effective_from"]
        for v in versions
    ]
    starts += [d for d in observations if d <= until] + [d for d in marks if d <= until]
    if not starts:
        return []
    days, current = [], min(starts)
    while current <= until:
        days.append(
            classify(
                kind,
                current,
                observations.get(current),
                spec_for(versions, current),
                marks.get(current),
                mode_on(modes, current) is not None,
                today,
                tracked,
            )
        )
        current += timedelta(days=1)
    return days


# ---------------------------------------------------------------------------
# Deviations and recovery
# ---------------------------------------------------------------------------


@dataclass
class Episode:
    start: date
    fail_days: int = 1
    last_fail: date | None = None
    first_ok: date | None = None
    confirmed: date | None = None
    reasons: list[str] = field(default_factory=list)
    _streak: int = 0

    @property
    def kind(self) -> str:
        return "single" if self.fail_days == 1 else "period"

    @property
    def days_to_first_ok(self) -> int | None:
        return (self.first_ok - self.start).days if self.first_ok else None

    @property
    def days_to_confirmed(self) -> int | None:
        return (self.confirmed - self.start).days if self.confirmed else None

    def elapsed(self, ref: date) -> int:
        """How long the deviation lasted: until recovery was confirmed, or so far."""
        return ((self.confirmed or ref) - self.start).days

    def as_dict(self, ref: date) -> dict:
        return {
            "start": self.start.isoformat(),
            "kind": self.kind,
            "fail_days": self.fail_days,
            "first_ok": self.first_ok.isoformat() if self.first_ok else None,
            "confirmed": self.confirmed.isoformat() if self.confirmed else None,
            "days_to_first_ok": self.days_to_first_ok,
            "days_to_confirmed": self.days_to_confirmed,
            "ongoing_days": None if self.confirmed else (ref - self.start).days,
            "reasons": self.reasons,
        }


def find_episodes(days: list[Day], versions: list[dict]) -> list[Episode]:
    """A deviation starts on a broken day and ends after ``confirm_days`` met days in a row.

    Neutral days (no data, exceptions, unrated) neither break nor confirm recovery.
    """
    episodes: list[Episode] = []
    for _day, episodes in iter_episodes(days, versions):
        pass
    return episodes


def iter_episodes(days: list[Day], versions: list[dict]):
    """Yield each day with the deviations found up to it (the last may still be open).

    The list is updated in place on the next day, so read it before moving on.
    """
    episodes: list[Episode] = []
    current: Episode | None = None
    for day in days:
        met = day.met
        if met is False:
            if current is None:
                current = Episode(day.date, last_fail=day.date)
                episodes.append(current)
            else:
                current.fail_days += 1
                current.last_fail = day.date
                current._streak = 0
            if day.reason:
                current.reasons.append(day.reason)
        elif met is True and current is not None:
            current.first_ok = current.first_ok or day.date
            current._streak += 1
            rules = section(spec_for(versions, day.date), "rules", DEFAULT_RULES)
            if current._streak >= int(rules["confirm_days"]):
                current.confirmed = day.date
                current = None
        yield day, episodes


def rate(days: list[Day], window: int, until: date) -> dict:
    since = until - timedelta(days=window - 1)
    selected = [d for d in days if since <= d.date <= until]
    counts = {status: 0 for status in DAY_STATUSES}
    for day in selected:
        counts[day.status] += 1
    judged = counts["success"] + counts["minimum"] + counts["fail"]
    return {
        "window_days": window,
        "since": since.isoformat(),
        "until": until.isoformat(),
        "observed_days": judged,
        "counts": counts,
        "warnings": sum(1 for day in selected if day.status == "success" and day.warning),
        "success_rate": counts["success"] / judged if judged else None,
        "acceptable_rate": (counts["success"] + counts["minimum"]) / judged if judged else None,
    }


def _median(values: list[int]) -> float | None:
    return statistics.median(values) if values else None


def _mean(values: list[int]) -> float | None:
    return round(statistics.fmean(values), 2) if values else None


def recovery_summary(episodes: list[Episode], days: list[Day], ref: date, ok_days: int) -> dict:
    first = [e.days_to_first_ok for e in episodes if e.first_ok]
    confirmed = [e.days_to_confirmed for e in episodes if e.confirmed]
    ongoing = next((e for e in episodes if e.confirmed is None), None)
    # An episode can be judged once it either recovered or has run past the allowed term.
    judged = [e for e in episodes if e.first_ok or (ref - e.start).days > ok_days]
    in_term = [e for e in judged if e.first_ok and e.days_to_first_ok <= ok_days]
    observed = [d for d in days if d.status in ("success", "minimum", "fail")]
    span = (observed[-1].date - observed[0].date).days + 1 if observed else 0
    last = next((e for e in reversed(episodes) if e.first_ok), None)
    return {
        "episodes": len(episodes),
        "single": sum(e.fail_days == 1 for e in episodes),
        "periods": sum(e.fail_days > 1 for e in episodes),
        "tested": bool(judged),
        "current_deviation": ongoing.as_dict(ref) if ongoing else None,
        "last_recovery": last.as_dict(ref) if last else None,
        "first_ok_mean": _mean(first),
        "first_ok_median": _median(first),
        "confirmed_mean": _mean(confirmed),
        "confirmed_median": _median(confirmed),
        "longest_deviation_days": max((e.elapsed(ref) for e in episodes), default=None),
        "longest_fail_days": max((e.fail_days for e in episodes), default=None),
        "per_30_days": round(len(episodes) * 30 / span, 2) if span else None,
        "in_term_share": len(in_term) / len(judged) if judged else None,
        "in_term": len(in_term),
        "judged": len(judged),
        "ok_days": ok_days,
    }


def monthly(episodes: list[Episode], days: list[Day]) -> list[dict]:
    """Per-month deviation count, recovery medians and success rate."""
    months: dict[str, dict] = {}
    for day in days:
        bucket = months.setdefault(day.date.strftime("%Y-%m"), {"episodes": [], "success": 0, "judged": 0})
        if day.status in ("success", "minimum", "fail"):
            bucket["judged"] += 1
            bucket["success"] += day.status == "success"
    for episode in episodes:
        months.setdefault(episode.start.strftime("%Y-%m"), {"episodes": [], "success": 0, "judged": 0})[
            "episodes"
        ].append(episode)
    out = []
    for month, bucket in sorted(months.items()):
        eps = bucket["episodes"]
        out.append(
            {
                "month": month,
                "episodes": len(eps),
                "fail_days": sum(e.fail_days for e in eps),
                "first_ok_median": _median([e.days_to_first_ok for e in eps if e.first_ok]),
                "confirmed_median": _median([e.days_to_confirmed for e in eps if e.confirmed]),
                "success_rate": bucket["success"] / bucket["judged"] if bucket["judged"] else None,
            }
        )
    return out


# ---------------------------------------------------------------------------
# Stage readiness (recommendations only)
# ---------------------------------------------------------------------------


def _criterion(key: str, label: str, status: str, required=None, actual=None, note: str = "") -> dict:
    return {"key": key, "label": label, "status": status, "required": required, "actual": actual, "note": note}


def integration_check(spec: dict, days: list[Day], episodes: list[Episode], today: date) -> dict:
    """Evaluate the passport's integration criteria over its window.

    A window without a single deviation leaves the recovery criterion
    *untested* — never silently passed.
    """
    cfg = section(spec, "integration", DEFAULT_INTEGRATION)
    window = int(cfg["window_days"])
    stats = rate(days, window, today)
    since = today - timedelta(days=window - 1)
    criteria = []

    observed_ok = stats["observed_days"] >= int(cfg["min_observed_days"])
    criteria.append(
        _criterion(
            "observed_days",
            "Достатньо спостережень",
            "met" if observed_ok else "not_met",
            int(cfg["min_observed_days"]),
            stats["observed_days"],
        )
    )

    rate_value = stats["success_rate"]
    rate_status = (
        "insufficient" if rate_value is None else ("met" if rate_value >= float(cfg["min_success_rate"]) else "not_met")
    )
    criteria.append(
        _criterion(
            "success_rate", f"Успішних днів за {window} дн.", rate_status, float(cfg["min_success_rate"]), rate_value
        )
    )

    window_episodes = [
        e for e in episodes if e.start >= since or e.confirmed is None or (e.confirmed and e.confirmed >= since)
    ]
    longest = max((e.elapsed(today) for e in window_episodes), default=0)
    criteria.append(
        _criterion(
            "long_deviation",
            "Немає тривалих відхилень",
            "met" if longest <= int(cfg["max_deviation_days"]) else "not_met",
            int(cfg["max_deviation_days"]),
            longest,
        )
    )

    allowed = int(cfg["max_recovery_days"])
    judged = [e for e in window_episodes if e.first_ok or (today - e.start).days > allowed]
    if not judged:
        criteria.append(
            _criterion(
                "recovery",
                f"Повернення протягом {allowed} дн. після збою",
                "untested",
                allowed,
                None,
                "За період не було збоїв — здатність відновлюватися не перевірена.",
            )
        )
    else:
        worst = max(e.days_to_first_ok if e.first_ok else (today - e.start).days for e in judged)
        criteria.append(
            _criterion(
                "recovery",
                f"Повернення протягом {allowed} дн. після збою",
                "met" if worst <= allowed else "not_met",
                allowed,
                worst,
            )
        )

    criteria.append(_criterion("health", "Немає шкоди здоров'ю й іншим звичкам", "manual", note="Оцінюєте ви."))
    automatic = [c for c in criteria if c["status"] != "manual"]
    return {
        "window_days": window,
        "since": since.isoformat(),
        "criteria": criteria,
        "ready": all(c["status"] == "met" for c in automatic),
        "confirmed_thresholds": bool(cfg.get("confirmed", False)),
    }


def recommendation(spec: dict, days: list[Day], episodes: list[Episode], today: date) -> dict | None:
    """Suggest a stage transition; the passport is never changed here."""
    stage = spec.get("stage")
    if stage == "formation":
        cfg = section(spec, "stabilization", DEFAULT_STABILIZATION)
        stats = rate(days, int(cfg["window_days"]), today)
        if (
            stats["observed_days"] >= int(cfg["min_observed_days"])
            and stats["success_rate"] is not None
            and stats["success_rate"] >= float(cfg["min_success_rate"])
        ):
            return {
                "to": "stabilization",
                "reason": (
                    f"За {cfg['window_days']} дн. успішних днів {stats['success_rate']:.0%} "
                    f"(поріг {float(cfg['min_success_rate']):.0%})."
                ),
            }
        return None
    if stage == "stabilization":
        check = integration_check(spec, days, episodes, today)
        if check["ready"]:
            return {"to": "integrated", "reason": "Усі автоматичні критерії інтеграції виконано."}
        return None
    if stage == "integrated":
        cfg = section(spec, "maintenance", DEFAULT_MAINTENANCE)
        stats = rate(days, int(cfg["window_days"]), today)
        ongoing = next((e for e in episodes if e.confirmed is None), None)
        if ongoing and (today - ongoing.start).days > int(cfg["max_deviation_days"]):
            return {"to": "stabilization", "reason": f"Відхилення триває {(today - ongoing.start).days} дн."}
        if stats["success_rate"] is not None and stats["success_rate"] < float(cfg["min_success_rate"]):
            return {
                "to": "stabilization",
                "reason": (f"За {cfg['window_days']} дн. успішних днів лише {stats['success_rate']:.0%}."),
            }
    return None


def stage_progress(spec: dict, days: list[Day], episodes: list[Episode], today: date) -> dict | None:
    """How close a habit is to its next stage and what still holds it back (None for other stages).

    Formation is measured against the stabilization criteria, stabilization
    against the integration ones: ``readiness`` is the share of the required
    observed days times the share of the required success rate.  It reaches 1
    only when the move is recommended, so a criterion still unmet keeps it just
    below; ``blockers`` names those criteria.
    """
    stage = spec.get("stage")
    if stage == "formation":
        cfg, target = section(spec, "stabilization", DEFAULT_STABILIZATION), "stabilization"
    elif stage == "stabilization":
        cfg, target = section(spec, "integration", DEFAULT_INTEGRATION), "integrated"
    else:
        return None
    stats = rate(days, int(cfg["window_days"]), today)
    need_days = int(cfg["min_observed_days"])
    need_rate = float(cfg["min_success_rate"])
    observed = min(stats["observed_days"] / need_days, 1.0) if need_days > 0 else 1.0
    success = min((stats["success_rate"] or 0.0) / need_rate, 1.0) if need_rate > 0 else 1.0
    advice = recommendation(spec, days, episodes, today)
    ready = bool(advice and advice["to"] == target)
    blockers = []
    if not ready and stage == "formation":
        if observed < 1:
            blockers.append(f"Днів із оцінкою за {cfg['window_days']} дн.: {stats['observed_days']} з {need_days}")
        if success < 1:
            blockers.append(f"Успішних днів {(stats['success_rate'] or 0):.0%} при порозі {need_rate:.0%}")
    elif not ready:
        for criterion in integration_check(spec, days, episodes, today)["criteria"]:
            if criterion["status"] == "untested":
                blockers.append(f"{criterion['label']}: ще не було збою, щоб це перевірити")
            elif criterion["status"] not in ("met", "manual"):
                blockers.append(criterion["label"])
    return {
        "target": target,
        "target_label": STAGE_LABELS[target],
        "readiness": 1.0 if ready else min(observed * success, 0.99),
        "window_days": int(cfg["window_days"]),
        "observed_days": stats["observed_days"],
        "need_days": need_days,
        "success_rate": stats["success_rate"],
        "need_rate": need_rate,
        "blockers": blockers,
    }


def stage_readiness(spec: dict, days: list[Day], episodes: list[Episode], today: date) -> float | None:
    """``readiness`` of :func:`stage_progress`, from 0 to 1."""
    progress = stage_progress(spec, days, episodes, today)
    return None if progress is None else progress["readiness"]


# Stages move by themselves; a version with this key set to true puts the habit
# on its stage by hand.  Versions from before that lack the key, and there a
# change of the stored stage was the hand-made move.
STAGE_SET = "stage_set"


def _sets_stage(version: dict, previous: dict | None) -> bool:
    spec = version["spec"]
    if STAGE_SET in spec:
        return bool(spec[STAGE_SET])
    return previous is None or previous["spec"].get("stage") != spec.get("stage")


def _stage_move(spec: dict, days: list[Day], episodes: list[Episode], day: date) -> dict | None:
    """Where the criteria move the habit on ``day``: ``{"to", "reason"}``, or None to stay."""
    if spec.get("stage") == "planned":
        start = spec.get("start_date")
        if start and day >= date.fromisoformat(str(start)):
            return {"to": "formation", "reason": "Настав день початку."}
        return None
    return recommendation(spec, days, episodes, day)


def staged_versions(versions: list[dict], days: list[Day], today: date) -> tuple[list[dict], list[dict]]:
    """The passport versions with the stage the habit really had, and its stage changes.

    Each day the criteria of the stage in force are checked on the days up to
    it; a move takes effect that same day, one step a day.  A version that sets
    the stage by hand puts the habit there, and the criteria go on from it.
    ``days`` must run without gaps up to ``today``, as :func:`build_days` makes
    them, or be empty while the habit waits for a future start date.
    """
    if not versions:
        return [], []
    by_hand: set[date] = set()
    previous = None
    for version in versions:
        if _sets_stage(version, previous):
            by_hand.add(version["effective_from"])
        previous = version

    staged: list[dict] = []
    changes: list[dict] = []
    stage: str | None = None
    source: dict | None = None
    pending = list(versions)
    walk = iter_episodes(days, versions)
    episodes: list[Episode] = []
    index = -1
    current = min([versions[0]["effective_from"]] + [day.date for day in days[:1]])
    while current <= today:
        if days and current >= days[0].date:
            _day, episodes = next(walk)
            index += 1
        started = None
        while pending and pending[0]["effective_from"] <= current:
            source = started = pending.pop(0)
        if source is None:
            current += timedelta(days=1)
            continue
        stored = source["spec"]
        if stage is None or current in by_hand:
            if stored.get("stage") != stage:
                changes.append(
                    {
                        "date": current,
                        "from": stage,
                        "to": stored.get("stage"),
                        "reason": source.get("reason", ""),
                        "auto": False,
                    }
                )
            stage = stored.get("stage")
        spec = {key: value for key, value in stored.items() if key != STAGE_SET}
        spec["stage"] = stage
        window = max(
            int(section(spec, key, defaults)["window_days"])
            for key, defaults in (
                ("stabilization", DEFAULT_STABILIZATION),
                ("integration", DEFAULT_INTEGRATION),
                ("maintenance", DEFAULT_MAINTENANCE),
            )
        )
        recent = days[max(0, index + 1 - window) : index + 1] if index >= 0 else []
        move = _stage_move(spec, recent, episodes, current)
        if move:
            changes.append({"date": current, "from": stage, "to": move["to"], "reason": move["reason"], "auto": True})
            stage = spec["stage"] = move["to"]
        if started or staged[-1]["spec"]["stage"] != stage:
            staged.append(
                {
                    "id": source["id"],
                    "effective_from": current,
                    "created_at": source.get("created_at") if started else None,
                    "reason": source.get("reason", "") if started else move["reason"],
                    "author": source.get("author", "user") if started else "auto",
                    "spec": spec,
                }
            )
        current += timedelta(days=1)
    return staged, changes


# ---------------------------------------------------------------------------
# Cultivation ranks (inspired by "Warlock of the Magus World")
# ---------------------------------------------------------------------------

ACTIVE_STAGES = ("formation", "stabilization", "integrated")

# active — some habit is being worked on; stabilizing — how many habits have
# reached stabilization or beyond (true means one); integrated — number of
# integrated habits; durable — (count, days) integrated habits held without a
# break that long.  A habit that drops out of integration goes back to
# stabilization and starts its run again.  ``confirmed`` marks the thresholds set by the user; the rest
# are proposals and can be overridden.  Ranks are climbed in order: a rank also
# needs every condition below it.
DEFAULT_RANKS: list[dict] = [
    {"name": "Звичайна людина", "req": {}, "confirmed": True},
    {"name": "Адепт першого рівня", "req": {"active": True}, "confirmed": True},
    {"name": "Адепт другого рівня", "req": {"stabilizing": 1}, "confirmed": True},
    {"name": "Адепт третього рівня", "req": {"stabilizing": 2}, "confirmed": True},
    {"name": "Маг першого рангу", "req": {"integrated": 1}, "confirmed": True},
    {"name": "Маг другого рангу", "req": {"integrated": 2, "durable": [1, 30]}, "confirmed": True},
    {"name": "Маг третього рангу", "req": {"integrated": 4, "durable": [2, 60]}, "confirmed": True},
    {"name": "Маг Нової Зірки", "req": {"integrated": 8, "durable": [4, 120]}, "confirmed": True},
    {"name": "Маг Нейтронної Зорі", "req": {"integrated": 16, "durable": [8, 120]}, "confirmed": True},
    {"name": "Маг Прямого Колапсу", "req": {"integrated": 32, "durable": [16, 240]}, "confirmed": True},
    {"name": "Маг Законів", "req": {"integrated": 64, "durable": [20, 365]}, "confirmed": True},
    {"name": "Великий Маг Законів", "req": {"integrated": 128, "durable": [40, 730]}, "confirmed": True},
    {"name": "Верховний Маг рангу Вічності", "req": {"integrated": 256, "durable": [80, 1095]}, "confirmed": True},
    {"name": "Той, хто знайшов свій Шлях", "req": {"integrated": 512, "durable": [128, 1825]}, "confirmed": True},
]


@dataclass
class HabitRankState:
    habit_id: int
    name: str
    stage: str | None
    counted: bool = False  # counts as integrated
    held_days: int = 0  # unbroken run of integrated


def simulate_stages(habit_id: int, versions: list[dict], until: date) -> dict[date, HabitRankState]:
    out: dict[date, HabitRankState] = {}
    if not versions:
        return out
    held_since: date | None = None
    current = min(v["effective_from"] for v in versions)
    while current <= until:
        spec = spec_for(versions, current) or {}
        stage = spec.get("stage")
        state = HabitRankState(habit_id, spec.get("name", ""), stage)
        if stage == "integrated":
            held_since = held_since or current
            state.counted = True
            state.held_days = (current - held_since).days + 1
        else:
            held_since = None
        out[current] = state
        current += timedelta(days=1)
    return out


def _stabilizing_need(req: dict) -> int:
    return int(req.get("stabilizing") or 0)  # true counts as one


def _stabilizing_have(states: list[HabitRankState]) -> int:
    return sum(s.stage == "stabilization" or s.counted for s in states)


def _rank_met(req: dict, states: list[HabitRankState]) -> bool:
    if req.get("active") and not any(s.stage in ACTIVE_STAGES for s in states):
        return False
    if _stabilizing_have(states) < _stabilizing_need(req):
        return False
    if sum(s.counted for s in states) < int(req.get("integrated", 0)):
        return False
    if req.get("durable"):
        count, days = req["durable"]
        if sum(s.counted and s.held_days >= int(days) for s in states) < int(count):
            return False
    return True


def rank_index(ranks: list[dict], states: list[HabitRankState]) -> int:
    index = 0
    for i, rank in enumerate(ranks):
        if not _rank_met(rank["req"], states):
            break
        index = i
    return index


def _hold_text(days: int) -> str:
    """Hold periods are set in 365-day years or 30-day months."""
    days = int(days)
    if days % 365 == 0:
        years = days // 365
        if years % 10 == 1 and years % 100 != 11:
            word = "рік"
        elif 2 <= years % 10 <= 4 and not 12 <= years % 100 <= 14:
            word = "роки"
        else:
            word = "років"
        return f"{years} {word}"
    return f"{days // 30} міс." if days % 30 == 0 else f"{days} дн."


def rank_requirement_text(req: dict) -> str:
    if not req:
        return "початковий стан"
    parts = []
    if req.get("active"):
        parts.append("є звичка в роботі")
    need = _stabilizing_need(req)
    if need == 1:
        parts.append("звичка у стабілізації")
    elif need > 1:
        parts.append(f"звичок у стабілізації чи далі ≥ {need}")
    if "integrated" in req:
        parts.append(f"інтегрованих звичок ≥ {req['integrated']}")
    if req.get("durable"):
        count, days = req["durable"]
        parts.append(f"з них ≥ {count} утримуються ≥ {_hold_text(days)}")
    return ", ".join(parts)


def _best(values: list[float], count: int) -> float:
    return sum(sorted(values, reverse=True)[: max(count, 0)])


def rank_progress(
    req: dict, states: list[HabitRankState], readiness: dict[int, float | None] | None = None
) -> list[dict]:
    """Conditions of a rank, each with ``fraction`` — how much of it is done.

    Habits one stage short add their readiness for the next stage, and held
    habits add the share of the hold period already behind them.
    """
    readiness = readiness or {}

    def ready(stage: str) -> list[float]:
        return [readiness.get(s.habit_id) or 0.0 for s in states if s.stage == stage]

    parts = []
    if req.get("active"):
        done = any(s.stage in ACTIVE_STAGES for s in states)
        parts.append({"label": "Звичка в роботі", "done": done, "fraction": 1.0 if done else 0.0})
    need = _stabilizing_need(req)
    if need:
        have = _stabilizing_have(states)
        fraction = min((have + _best(ready("formation"), need - have)) / need, 1.0)
        if need == 1:
            parts.append({"label": "Звичка у стабілізації", "done": have >= 1, "fraction": fraction})
        else:
            parts.append(
                {
                    "label": "Звички у стабілізації чи далі",
                    "have": have,
                    "need": need,
                    "done": have >= need,
                    "fraction": fraction,
                }
            )
    if "integrated" in req:
        need = int(req["integrated"])
        have = sum(s.counted for s in states)
        fraction = min((have + _best(ready("stabilization"), need - have)) / need, 1.0) if need else 1.0
        parts.append(
            {"label": "Інтегровані звички", "have": have, "need": need, "done": have >= need, "fraction": fraction}
        )
    if req.get("durable"):
        count, days = (int(v) for v in req["durable"])
        have = sum(s.counted and s.held_days >= days for s in states)
        held = [min(s.held_days / days, 1.0) for s in states if s.counted]
        parts.append(
            {
                "label": f"Утримуються ≥ {_hold_text(days)}",
                "have": have,
                "need": count,
                "done": have >= count,
                "fraction": _best(held, count) / count if count else 1.0,
            }
        )
    return parts


def breakthrough(parts: list[dict]) -> int:
    """«Прорив»: percent of the way to the next rank, the mean of its conditions, rounded down."""
    if not parts:
        return 100
    return int(sum(part["fraction"] for part in parts) / len(parts) * 100)


def _stage_counts(states: list[HabitRankState]) -> dict[str, int]:
    counts = {stage: 0 for stage in STAGES}
    for state in states:
        if state.stage in counts:
            counts[state.stage] += 1
    return counts


def compute_rank(
    habit_versions: dict[int, list[dict]],
    until: date,
    ranks: list[dict] | None = None,
    readiness: dict[int, float | None] | None = None,
) -> dict:
    """Rank on ``until`` with its history; ``readiness`` (habit id → 0..1) feeds the «Прорив» percent."""
    ranks = ranks or DEFAULT_RANKS
    daily = {hid: simulate_stages(hid, versions, until) for hid, versions in habit_versions.items()}
    first = min((min(days) for days in daily.values() if days), default=until)
    history, timeline, previous, peak = [], [], 0, 0
    current = first
    while current <= until:
        on_day = [days[current] for days in daily.values() if current in days]
        index = rank_index(ranks, on_day)
        counts = _stage_counts(on_day)
        if not timeline or any(timeline[-1][stage] != counts[stage] for stage in STAGES):
            timeline.append({"date": current.isoformat(), **counts})
        if index != previous:
            history.append(
                {
                    "date": current.isoformat(),
                    "from": previous,
                    "to": index,
                    "from_name": ranks[previous]["name"],
                    "to_name": ranks[index]["name"],
                }
            )
            previous = index
        peak = max(peak, index)
        current += timedelta(days=1)
    states = [days[until] for days in daily.values() if until in days]
    if timeline and timeline[-1]["date"] != until.isoformat():
        timeline.append({"date": until.isoformat(), **_stage_counts(states)})
    index = rank_index(ranks, states)
    nxt = ranks[index + 1] if index + 1 < len(ranks) else None
    progress = rank_progress(nxt["req"], states, readiness) if nxt else []

    warnings = []
    if index < peak:
        warnings.append(
            f"Найвищий досягнутий ранг — {ranks[peak]['name']}; він повернеться, коли звички знову інтегруються."
        )

    return {
        "index": index,
        "name": ranks[index]["name"],
        "peak_index": peak,
        "peak_name": ranks[peak]["name"],
        "next": None
        if nxt is None
        else {
            "index": index + 1,
            "name": nxt["name"],
            "requirement": rank_requirement_text(nxt["req"]),
            "progress": progress,
            "breakthrough": breakthrough(progress),
            "confirmed": nxt.get("confirmed", False),
        },
        "ladder": [
            {
                "index": i,
                "name": r["name"],
                "requirement": rank_requirement_text(r["req"]),
                "confirmed": r.get("confirmed", False),
            }
            for i, r in enumerate(ranks)
        ],
        "habits": [
            {
                "habit_id": s.habit_id,
                "name": s.name,
                "stage": s.stage,
                "counted": s.counted,
                "held_days": s.held_days,
            }
            for s in states
        ],
        "stages": _stage_counts(states),
        "timeline": timeline,
        "history": history,
        "warnings": warnings,
    }


def progress_history(habits: list[dict], since: date, today: date, ranks: list[dict] | None = None) -> dict:
    """Cultivation progress day by day, from ``since`` (or the first habit) to ``today``.

    ``habits`` holds ``id``, ``versions`` and ``days`` built through ``today``.
    Each day is judged as it was then: the passport in force, the days and
    deviations up to that day, the stages of that day.  Returns «Прорив» with
    the rank per day, every habit's readiness for its next stage, and its stages
    as segments.
    """
    ranks = ranks or DEFAULT_RANKS
    daily = {h["id"]: simulate_stages(h["id"], h["versions"], today) for h in habits}
    first = min((min(states) for states in daily.values() if states), default=today)
    start = max(since, first)
    dates = {h["id"]: [d.date for d in h["days"]] for h in habits}
    points: list[dict] = []
    readiness_series: dict[int, list[dict]] = {h["id"]: [] for h in habits}
    segments: dict[int, list[dict]] = {h["id"]: [] for h in habits}
    current = start
    while current <= today:
        readiness: dict[int, float | None] = {}
        for habit in habits:
            hid = habit["id"]
            spec = spec_for(habit["versions"], current)
            if spec is None:
                continue
            cut = habit["days"][: bisect.bisect_right(dates[hid], current)]
            readiness[hid] = stage_readiness(spec, cut, find_episodes(cut, habit["versions"]), current)
            readiness_series[hid].append({"date": current.isoformat(), "value": readiness[hid]})
            stage = daily[hid][current].stage if current in daily[hid] else None
            run = segments[hid]
            if run and run[-1]["stage"] == stage:
                run[-1]["end"] = current.isoformat()
            else:
                run.append({"stage": stage, "start": current.isoformat(), "end": current.isoformat()})
        states = [states_by_day[current] for states_by_day in daily.values() if current in states_by_day]
        index = rank_index(ranks, states)
        nxt = ranks[index + 1] if index + 1 < len(ranks) else None
        points.append(
            {
                "date": current.isoformat(),
                "breakthrough": breakthrough(rank_progress(nxt["req"], states, readiness)) if nxt else 100,
                "rank_index": index,
                "rank_name": ranks[index]["name"],
                "next_name": nxt["name"] if nxt else None,
            }
        )
        current += timedelta(days=1)
    return {"days": points, "readiness": readiness_series, "segments": segments}


def deviations_by_month(episodes: list[Episode], today: date, months: int = 12) -> list[dict]:
    """Deviations of all habits per month (by start), with the median days to the first good day."""
    out = []
    year, month = today.year, today.month
    keys = []
    for _ in range(months):
        keys.append(f"{year:04d}-{month:02d}")
        year, month = (year, month - 1) if month > 1 else (year - 1, 12)
    for key in reversed(keys):
        started = [e for e in episodes if e.start.isoformat()[:7] == key]
        first_ok = [e.days_to_first_ok for e in started if e.first_ok]
        out.append(
            {
                "month": key,
                "deviations": len(started),
                "fail_days": sum(e.fail_days for e in started),
                "first_ok_median": _median(first_ok),
                "unrecovered": sum(1 for e in started if e.first_ok is None),
            }
        )
    return out


# ---------------------------------------------------------------------------
# All habits together (home statistics)
# ---------------------------------------------------------------------------

ROLLING_DAYS = 7
JUDGED_STATUSES = ("success", "minimum", "fail")


def _share(part: int, whole: int) -> float | None:
    return part / whole if whole else None


def _counts(days: list[Day]) -> dict:
    counts = {status: 0 for status in DAY_STATUSES}
    for day in days:
        counts[day.status] += 1
    judged = sum(counts[s] for s in JUDGED_STATUSES)
    return {
        "counts": counts,
        "judged": judged,
        "warnings": sum(1 for day in days if day.status == "success" and day.warning),
        "success_rate": _share(counts["success"], judged),
        "acceptable_rate": _share(counts["success"] + counts["minimum"], judged),
    }


def _window(by_date: dict[date, Day], end: date, length: int) -> list[Day]:
    picked = (by_date.get(end - timedelta(days=offset)) for offset in range(length))
    return [day for day in picked if day is not None]


def _clean_streaks(by_habit: list[dict[date, Day]], today: date) -> tuple[int, int]:
    """Days in a row with at least one judged habit and no habit broken.

    A past day without any judged habit ends the run; today is still open, so
    it only extends the run once something is recorded.
    """
    starts = [min(days) for days in by_habit if days]
    if not starts:
        return 0, 0
    run = best = 0
    current = min(starts)
    while current <= today:
        statuses = [days[current].status for days in by_habit if current in days]
        judged = sum(1 for s in statuses if s in JUDGED_STATUSES)
        if "fail" in statuses or (judged == 0 and current < today):
            run = 0
        elif judged:
            run += 1
        best = max(best, run)
        current += timedelta(days=1)
    return run, best


def combined_stats(habits: list[dict], since: date, today: date) -> dict:
    """Every habit's day states side by side, plus totals across them.

    ``habits`` are dicts with ``id`` and their full ``days`` (Day objects);
    other keys are passed through. Shares follow the per-habit rates: success
    over judged days (success, minimum, fail) — a day without data is never a
    failure, and the rolling share looks back across ``since`` as well.
    """
    dates = [since + timedelta(days=offset) for offset in range((today - since).days + 1)]
    by_habit = [{day.date: day for day in habit["days"]} for habit in habits]

    habit_rows = []
    for habit, days in zip(habits, by_habit):
        all_days = list(days.values())
        habit_rows.append(
            {
                **{key: value for key, value in habit.items() if key != "days"},
                "rates": {
                    "7": _counts(_window(days, today, 7)),
                    "30": _counts(_window(days, today, 30)),
                    "all": _counts(all_days),
                },
                "series": [
                    {
                        "date": current.isoformat(),
                        "status": days[current].status if current in days else None,
                        "warning": days[current].warning if current in days else "",
                        "rolling": _counts(_window(days, current, ROLLING_DAYS))["success_rate"],
                    }
                    for current in dates
                ],
            }
        )

    daily = []
    for current in dates:
        present = [days[current] for days in by_habit if current in days]
        rolling = [day for days in by_habit for day in _window(days, current, ROLLING_DAYS)]
        daily.append(
            {
                "date": current.isoformat(),
                "habits": len(present),
                **_counts(present),
                "rolling": _counts(rolling)["success_rate"],
            }
        )

    streak, best = _clean_streaks(by_habit, today)
    today_days = [days[today] for days in by_habit if today in days]
    return {
        "since": since.isoformat(),
        "until": today.isoformat(),
        "habits": habit_rows,
        "daily": daily,
        "summary": {
            "habits": len(habits),
            "today": {**_counts(today_days), "pending": sum(1 for d in today_days if d.status == "no_data")},
            "rates": {
                key: _counts([day for days in by_habit for day in _window(days, today, length)])
                for key, length in (("7", 7), ("30", 30))
            }
            | {"all": _counts([day for days in by_habit for day in days.values()])},
            "clean_streak": streak,
            "best_clean_streak": best,
        },
    }
