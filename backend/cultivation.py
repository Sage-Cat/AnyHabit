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

import copy
import statistics
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta

# ---------------------------------------------------------------------------
# Vocabulary
# ---------------------------------------------------------------------------

STAGES = ("planned", "formation", "stabilization", "integrated", "recovery")
STAGE_LABELS = {
    "planned": "Запланована",
    "formation": "Формування",
    "stabilization": "Стабілізація",
    "integrated": "Інтегрована",
    "recovery": "Потребує відновлення",
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
    except ValueError as exc:
        raise PassportError(f"Час має бути у форматі ГГ:ХХ, отримано «{value}»") from exc


def section(spec: dict | None, key: str, defaults: dict) -> dict:
    return {**defaults, **((spec or {}).get(key) or {})}


def level_defined(kind: str, level: dict | None) -> bool:
    if kind == "sleep":
        return bool(level) and any(level.get(k) is not None for k in ("wake_by", "min_sleep_h", "max_sleep_h"))
    # boolean / quit are judged by the presence of an event; build may add a threshold
    return True


def validate_spec(kind: str, spec: dict) -> None:
    if not isinstance(spec, dict):
        raise PassportError("Паспорт має бути об'єктом")
    if not str(spec.get("name") or "").strip():
        raise PassportError("Потрібна назва звички")
    if spec.get("stage") not in STAGES:
        raise PassportError(f"Етап має бути одним із: {', '.join(STAGES)}")
    levels = [("level", spec.get("level")), ("minimum", spec.get("minimum"))]
    levels += [(f"subgoals[{i}]", (sg or {}).get("level")) for i, sg in enumerate(spec.get("subgoals") or [])]
    for label, level in levels:
        level = level or {}
        if level.get("wake_by") is not None:
            parse_hhmm(level["wake_by"])
        for bound in ("min_sleep_h", "max_sleep_h"):
            value = level.get(bound)
            if value is not None and not (0 < float(value) <= MAX_VALID_SLEEP_HOURS):
                raise PassportError(f"{label}.{bound}: значення поза межами 0–{MAX_VALID_SLEEP_HOURS:g} год")
        if None not in (level.get("min_sleep_h"), level.get("max_sleep_h")) and float(level["min_sleep_h"]) > float(
            level["max_sleep_h"]
        ):
            raise PassportError(f"{label}: мінімальна тривалість більша за максимальну")
        if level.get("min_amount") is not None and float(level["min_amount"]) < 0:
            raise PassportError(f"{label}.min_amount не може бути від'ємним")
    rules = section(spec, "rules", DEFAULT_RULES)
    if int(rules["confirm_days"]) < 1 or int(rules["recovery_ok_days"]) < 0:
        raise PassportError("rules: confirm_days ≥ 1, recovery_ok_days ≥ 0")
    for key, defaults in (
        ("stabilization", DEFAULT_STABILIZATION),
        ("integration", DEFAULT_INTEGRATION),
        ("maintenance", DEFAULT_MAINTENANCE),
    ):
        block = section(spec, key, defaults)
        if not (0 < float(block["min_success_rate"]) <= 1):
            raise PassportError(f"{key}.min_success_rate має бути в межах (0; 1]")
        if int(block["window_days"]) < 1:
            raise PassportError(f"{key}.window_days ≥ 1")


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
    return "виконати"


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
        return (self.wake - self.bedtime).total_seconds() / 3600


@dataclass
class Observation:
    nights: list[Night] = field(default_factory=list)  # sleep: grouped by local wake date
    amount: float = 0.0  # build / boolean: sum of logs that day
    events: int = 0  # number of logs (or relapses for quit)
    notes: list[str] = field(default_factory=list)


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
        return obs.events > 0
    return True


def classify(kind: str, day: date, obs: Observation | None, spec: dict | None, mark: dict | None,
             degraded: bool, today: date) -> Day:
    obs = obs or Observation()
    result = Day(day, "no_data", degraded=degraded, amount=obs.amount, events=obs.events)

    if kind == "sleep":
        real = [n for n in obs.nights if n.hours >= MIN_NIGHT_HOURS]
        if real:
            result.night = max(real, key=lambda n: n.hours)
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
            elif day < today:
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
    if _meets(kind, obs, level, night):
        result.status = "success"
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


def build_days(kind: str, versions: list[dict], observations: dict[date, Observation], marks: dict[date, dict],
               modes: list[dict], until: date) -> list[Day]:
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
            classify(kind, current, observations.get(current), spec_for(versions, current), marks.get(current),
                     mode_on(modes, current) is not None, until)
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
        return ((self.first_ok or ref) - self.start).days

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
    return episodes


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
        _criterion("observed_days", "Достатньо спостережень", "met" if observed_ok else "not_met",
                   int(cfg["min_observed_days"]), stats["observed_days"])
    )

    rate_value = stats["success_rate"]
    rate_status = "insufficient" if rate_value is None else ("met" if rate_value >= float(cfg["min_success_rate"]) else "not_met")
    criteria.append(
        _criterion("success_rate", f"Успішних днів за {window} дн.", rate_status,
                   float(cfg["min_success_rate"]), rate_value)
    )

    window_episodes = [e for e in episodes if e.start >= since or e.confirmed is None or (e.confirmed and e.confirmed >= since)]
    longest = max((e.elapsed(today) for e in window_episodes), default=0)
    criteria.append(
        _criterion("long_deviation", "Немає тривалих відхилень",
                   "met" if longest <= int(cfg["max_deviation_days"]) else "not_met",
                   int(cfg["max_deviation_days"]), longest)
    )

    allowed = int(cfg["max_recovery_days"])
    judged = [e for e in window_episodes if e.first_ok or (today - e.start).days > allowed]
    if not judged:
        criteria.append(
            _criterion("recovery", f"Повернення протягом {allowed} дн. після збою", "untested", allowed, None,
                       "За період не було збоїв — здатність відновлюватися не перевірена.")
        )
    else:
        worst = max(e.days_to_first_ok if e.first_ok else (today - e.start).days for e in judged)
        criteria.append(
            _criterion("recovery", f"Повернення протягом {allowed} дн. після збою",
                       "met" if worst <= allowed else "not_met", allowed, worst)
        )

    criteria.append(
        _criterion("health", "Немає шкоди здоров'ю й іншим звичкам", "manual", note="Оцінюєте ви.")
    )
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
            return {"to": "stabilization", "reason": (
                f"За {cfg['window_days']} дн. успішних днів {stats['success_rate']:.0%} "
                f"(поріг {float(cfg['min_success_rate']):.0%})."
            )}
        return None
    if stage in ("stabilization", "recovery"):
        check = integration_check(spec, days, episodes, today)
        if check["ready"]:
            return {"to": "integrated", "reason": "Усі автоматичні критерії інтеграції виконано."}
        return None
    if stage == "integrated":
        cfg = section(spec, "maintenance", DEFAULT_MAINTENANCE)
        stats = rate(days, int(cfg["window_days"]), today)
        ongoing = next((e for e in episodes if e.confirmed is None), None)
        if ongoing and (today - ongoing.start).days > int(cfg["max_deviation_days"]):
            return {"to": "recovery", "reason": f"Відхилення триває {(today - ongoing.start).days} дн."}
        if stats["success_rate"] is not None and stats["success_rate"] < float(cfg["min_success_rate"]):
            return {"to": "recovery", "reason": (
                f"За {cfg['window_days']} дн. успішних днів лише {stats['success_rate']:.0%}."
            )}
    return None


# ---------------------------------------------------------------------------
# Cultivation ranks (inspired by "Warlock of the Magus World")
# ---------------------------------------------------------------------------

RECOVERY_GRACE_DAYS = 60
ACTIVE_STAGES = ("formation", "stabilization", "integrated", "recovery")

# active — some habit is being worked on; stabilizing — one is stabilizing or
# integrated; integrated — number of integrated habits; durable — (count, days)
# integrated habits held without a break that long.  ``confirmed`` marks the
# thresholds set by the user; the rest are proposals and can be overridden.
DEFAULT_RANKS: list[dict] = [
    {"name": "Смертний", "req": {}, "confirmed": True},
    {"name": "Послушник 1 рівня", "req": {"active": True}, "confirmed": True},
    {"name": "Послушник 2 рівня", "req": {"stabilizing": True}, "confirmed": True},
    {"name": "Послушник 3 рівня", "req": {"integrated": 1}, "confirmed": True},
    {"name": "Напівмаг", "req": {"integrated": 2}, "confirmed": False},
    {"name": "Маг 1 рангу", "req": {"integrated": 3}, "confirmed": True},
    {"name": "Маг 2 рангу", "req": {"integrated": 5, "durable": [3, 180]}, "confirmed": False},
    {"name": "Маг 3 рангу", "req": {"integrated": 8, "durable": [5, 365]}, "confirmed": False},
    {"name": "Маг 4 рангу", "req": {"integrated": 12, "durable": [8, 730]}, "confirmed": False},
]


@dataclass
class HabitRankState:
    habit_id: int
    name: str
    stage: str | None
    counted: bool = False  # counts as integrated
    held_days: int = 0  # unbroken run of integrated (+ recovery within grace)
    recovery_days: int = 0


def simulate_stages(habit_id: int, versions: list[dict], until: date, grace_days: int) -> dict[date, HabitRankState]:
    out: dict[date, HabitRankState] = {}
    if not versions:
        return out
    held_since: date | None = None
    recovery_since: date | None = None
    current = min(v["effective_from"] for v in versions)
    while current <= until:
        spec = spec_for(versions, current) or {}
        stage = spec.get("stage")
        state = HabitRankState(habit_id, spec.get("name", ""), stage)
        if stage == "integrated":
            held_since = held_since or current
            recovery_since = None
            state.counted = True
        elif stage == "recovery" and held_since is not None:
            recovery_since = recovery_since or current
            state.recovery_days = (current - recovery_since).days + 1
            if state.recovery_days <= grace_days:
                state.counted = True
            else:
                held_since = None
        else:
            held_since = recovery_since = None
        if state.counted:
            state.held_days = (current - held_since).days + 1
        out[current] = state
        current += timedelta(days=1)
    return out


def _rank_met(req: dict, states: list[HabitRankState]) -> bool:
    if req.get("active") and not any(s.stage in ACTIVE_STAGES for s in states):
        return False
    if req.get("stabilizing") and not any(s.stage == "stabilization" or s.counted for s in states):
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


def rank_requirement_text(req: dict) -> str:
    if not req:
        return "початковий стан"
    parts = []
    if req.get("active"):
        parts.append("є звичка в роботі")
    if req.get("stabilizing"):
        parts.append("звичка у стабілізації")
    if "integrated" in req:
        parts.append(f"інтегрованих звичок ≥ {req['integrated']}")
    if req.get("durable"):
        count, days = req["durable"]
        parts.append(f"з них ≥ {count} утримуються ≥ {days} дн.")
    return ", ".join(parts)


def rank_progress(req: dict, states: list[HabitRankState]) -> list[dict]:
    parts = []
    if req.get("active"):
        parts.append({"label": "Звичка в роботі", "done": any(s.stage in ACTIVE_STAGES for s in states)})
    if req.get("stabilizing"):
        parts.append({"label": "Звичка у стабілізації", "done": any(s.stage == "stabilization" or s.counted for s in states)})
    if "integrated" in req:
        have = sum(s.counted for s in states)
        parts.append({"label": "Інтегровані звички", "have": have, "need": int(req["integrated"]),
                      "done": have >= int(req["integrated"])})
    if req.get("durable"):
        count, days = req["durable"]
        have = sum(s.counted and s.held_days >= int(days) for s in states)
        parts.append({"label": f"Утримуються ≥ {days} дн.", "have": have, "need": int(count), "done": have >= int(count)})
    return parts


def compute_rank(habit_versions: dict[int, list[dict]], until: date, ranks: list[dict] | None = None,
                 grace_days: int = RECOVERY_GRACE_DAYS) -> dict:
    ranks = ranks or DEFAULT_RANKS
    daily = {hid: simulate_stages(hid, versions, until, grace_days) for hid, versions in habit_versions.items()}
    first = min((min(days) for days in daily.values() if days), default=until)
    history, previous, peak = [], 0, 0
    current = first
    while current <= until:
        index = rank_index(ranks, [days[current] for days in daily.values() if current in days])
        if index != previous:
            history.append({"date": current.isoformat(), "from": previous, "to": index,
                            "from_name": ranks[previous]["name"], "to_name": ranks[index]["name"]})
            previous = index
        peak = max(peak, index)
        current += timedelta(days=1)
    states = [days[until] for days in daily.values() if until in days]
    index = rank_index(ranks, states)
    nxt = ranks[index + 1] if index + 1 < len(ranks) else None

    warnings = []
    for state in states:
        if state.stage == "recovery" and state.counted:
            warnings.append(
                f"Ранг нестабільний: «{state.name}» у відновленні {state.recovery_days} дн., "
                f"ще враховується {grace_days - state.recovery_days} дн."
            )
        elif state.stage == "recovery":
            warnings.append(f"«{state.name}» у відновленні довше {grace_days} дн. і не враховується.")
    if index < peak:
        warnings.append(f"Найвищий досягнутий ранг — {ranks[peak]['name']}; він повернеться після відновлення звичок.")

    return {
        "index": index,
        "name": ranks[index]["name"],
        "peak_index": peak,
        "peak_name": ranks[peak]["name"],
        "next": None if nxt is None else {
            "index": index + 1,
            "name": nxt["name"],
            "requirement": rank_requirement_text(nxt["req"]),
            "progress": rank_progress(nxt["req"], states),
            "confirmed": nxt.get("confirmed", False),
        },
        "ladder": [
            {"index": i, "name": r["name"], "requirement": rank_requirement_text(r["req"]),
             "confirmed": r.get("confirmed", False)}
            for i, r in enumerate(ranks)
        ],
        "habits": [
            {"habit_id": s.habit_id, "name": s.name, "stage": s.stage, "counted": s.counted,
             "held_days": s.held_days, "recovery_days": s.recovery_days}
            for s in states
        ],
        "history": history,
        "warnings": warnings,
        "grace_days": grace_days,
    }
