"""Habit cultivation: day states, recovery maths, stage readiness, ranks and the API.

Run with:  python -m backend.tests.test_cultivation
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Europe/Kyiv")
D0 = date(2026, 11, 2)  # a Monday

SPEC = {
    "name": "Sleep",
    "stage": "formation",
    "start_date": D0.isoformat(),
    "level": {"wake_by": "08:00", "min_sleep_h": 7},
    "minimum": {"wake_by": "09:00", "min_sleep_h": 5.5},
    "rules": {"confirm_days": 2, "recovery_ok_days": 2},
}


def main() -> int:
    from backend import cultivation as cv

    failures: list[str] = []

    def check(label: str, condition: bool, detail: str = "") -> None:
        if condition:
            print(f"  PASS  {label}")
        else:
            failures.append(f"{label} {detail}".strip())
            print(f"  FAIL  {label} {detail}")

    def night(wake_day: date, bed: str, wake: str, note: str = "", log_id: int = 1) -> cv.Night:
        bed_t, wake_t = cv.parse_hhmm(bed), cv.parse_hhmm(wake)
        bed_day = wake_day - timedelta(days=1) if bed_t > wake_t else wake_day
        return cv.Night(log_id, datetime.combine(bed_day, bed_t, TZ), datetime.combine(wake_day, wake_t, TZ), note)

    def versions(*items):
        return [{"id": i + 1, "effective_from": eff, "spec": spec} for i, (eff, spec) in enumerate(items)]

    def sleep_days(nights, until, vers=None, marks=None, modes=None):
        vers = vers or versions((D0, SPEC))
        obs: dict = {}
        for n in nights:
            obs.setdefault(n.wake.date(), cv.Observation()).nights.append(n)
        return cv.build_days("sleep", vers, obs, marks or {}, modes or [], until), vers

    print("\n[1] Day states")
    d = D0 + timedelta(days=1)
    days, _ = sleep_days([night(d, "23:00", "07:00")], d)
    check("on time and long enough is success", days[-1].status == "success", days[-1].status)
    check("a day without a record is no data, not a failure", days[0].status == "no_data", days[0].status)
    check("late but within minimum", sleep_days([night(d, "01:00", "08:30")], d)[0][-1].status == "minimum")
    check("below minimum is a failure", sleep_days([night(d, "04:00", "11:30")], d)[0][-1].status == "fail")
    check("on time but too short fails", sleep_days([night(d, "02:30", "07:30")], d)[0][-1].status == "fail")

    bounded = {**SPEC, "level": {"wake_by": "08:00", "min_sleep_h": 7, "max_sleep_h": 9}, "minimum": {}}
    statuses = [
        sleep_days([night(d, bed, "07:30")], d, vers=versions((D0, bounded)))[0][-1].status
        for bed in ("22:30", "23:30", "22:00")
    ]
    check("upper sleep bound respected", statuses == ["success", "success", "fail"], str(statuses))
    check(
        "level text",
        cv.level_text("sleep", bounded["level"]) == "підйом до 08:00, сон 7–9 год",
        cv.level_text("sleep", bounded["level"]),
    )
    try:
        cv.validate_spec("sleep", cv.merge_patch(bounded, {"level": {"max_sleep_h": 6}}))
        check("min > max rejected", False)
    except cv.PassportError:
        check("min > max rejected", True)

    nap = night(d, "14:00", "15:00", log_id=2)
    day = sleep_days([nap, night(d, "23:30", "07:00")], d)[0][-1]
    check(
        "longest sleep is the night, naps counted",
        (day.status, day.naps) == ("success", 1),
        str((day.status, day.naps)),
    )
    tap = cv.Night(3, datetime.combine(d, cv.parse_hhmm("05:43"), TZ), datetime.combine(d, cv.parse_hhmm("05:43"), TZ))
    day = sleep_days([tap], d)[0][-1]
    check("accidental zero-length record is neutral", (day.status, day.met) == ("no_data", None), str(day.status))
    huge = cv.Night(
        4,
        datetime.combine(d - timedelta(days=1), cv.parse_hhmm("06:00"), TZ),
        datetime.combine(d, cv.parse_hhmm("07:00"), TZ),
    )
    check("implausible 25 h record is flagged", sleep_days([huge], d)[0][-1].status == "invalid")

    marks = {d: {"status": "exception", "reason": "illness"}}
    day = sleep_days([night(d, "04:00", "12:00")], d, marks=marks)[0][-1]
    check("manual exception overrides", (day.status, day.met) == ("exception", None), day.status)
    marks = {d: {"status": "fail", "reason": "late, time unknown"}}
    check("manual failure without a record", sleep_days([], d, marks=marks)[0][-1].status == "fail")

    unrated = {**SPEC, "level": {"wake_by": None, "min_sleep_h": None}}
    day = sleep_days([night(d, "01:00", "10:00")], d, vers=versions((D0, unrated)))[0][-1]
    check("no criterion means unrated", (day.status, day.met) == ("unrated", None), day.status)

    stricter = {**SPEC, "level": {"wake_by": "07:30", "min_sleep_h": 7}}
    vers = versions((D0, SPEC), (D0 + timedelta(days=2), stricter))
    days, _ = sleep_days(
        [night(D0 + timedelta(days=1), "00:00", "07:45"), night(D0 + timedelta(days=2), "00:00", "07:45")],
        D0 + timedelta(days=2),
        vers=vers,
    )
    check(
        "criteria apply from their effective date",
        [x.status for x in days[1:]] == ["success", "minimum"],
        str([x.status for x in days]),
    )

    entry = night(d, "01:00", "08:30")
    normal = sleep_days([entry], d)[0][-1]
    degraded = sleep_days([entry], d, modes=[{"start_date": d, "end_date": None}])[0][-1]
    check("minimum is neutral in normal mode", (normal.status, normal.met) == ("minimum", None))
    check("minimum is met in degraded mode", (degraded.status, degraded.met) == ("minimum", True))

    obs = {d: cv.Observation(amount=12, events=1)}
    build_spec = {"name": "Read", "stage": "formation", "start_date": D0.isoformat(), "level": {"min_amount": 10}}
    days = cv.build_days("build", versions((D0, build_spec)), obs, {}, [], d)
    check("build habit: threshold met", days[-1].status == "success" and days[0].status == "no_data")
    quit_spec = {"name": "No phone", "stage": "formation", "start_date": D0.isoformat()}
    days = cv.build_days(
        "quit", versions((D0, quit_spec)), {d: cv.Observation(events=1)}, {}, [], d + timedelta(days=1)
    )
    check(
        "quit habit: relapse fails, past days succeed, today open",
        [x.status for x in days] == ["success", "fail", "no_data"],
        str([x.status for x in days]),
    )

    print("\n[2] Deviations and recovery")
    mon = D0
    nights = [
        night(mon, "04:00", "12:00", "Причина: робота"),
        night(mon + timedelta(1), "04:30", "12:30"),
        night(mon + timedelta(2), "23:00", "07:00"),
        night(mon + timedelta(3), "23:00", "07:00"),
    ]
    days, vers = sleep_days(nights, mon + timedelta(3))
    episodes = cv.find_episodes(days, vers)
    first = episodes[0] if episodes else None
    check(
        "Monday break, Wednesday back, confirmed Thursday",
        len(episodes) == 1 and (first.fail_days, first.days_to_first_ok, first.days_to_confirmed) == (2, 2, 3),
        str([e.as_dict(mon) for e in episodes]),
    )
    check("deviation reason captured", first is not None and first.reasons == ["робота"])
    summary = cv.recovery_summary(episodes, days, mon + timedelta(3), 2)
    check(
        "recovered within term",
        (summary["in_term"], summary["judged"]) == (1, 1) and summary["current_deviation"] is None,
    )

    nights = [
        night(D0, "04:00", "12:00"),
        night(D0 + timedelta(1), "23:00", "07:00"),
        night(D0 + timedelta(2), "04:00", "12:00"),
        night(D0 + timedelta(4), "23:00", "07:00"),
        night(D0 + timedelta(5), "23:00", "07:00"),
    ]
    days, vers = sleep_days(nights, D0 + timedelta(5))
    e = cv.find_episodes(days, vers)[0]
    check(
        "no data is neutral and a relapse resets confirmation",
        (e.fail_days, e.days_to_first_ok, e.days_to_confirmed) == (2, 1, 5),
        str((e.fail_days, e.days_to_first_ok, e.days_to_confirmed)),
    )

    days, vers = sleep_days([night(D0 + timedelta(i), "23:00", "07:00") for i in range(5)], D0 + timedelta(4))
    summary = cv.recovery_summary(cv.find_episodes(days, vers), days, D0 + timedelta(4), 2)
    check("recovery is untested without failures", not summary["tested"] and summary["in_term_share"] is None)

    days, vers = sleep_days([night(D0 + timedelta(i), "04:00", "12:00") for i in range(4)], D0 + timedelta(3))
    summary = cv.recovery_summary(cv.find_episodes(days, vers), days, D0 + timedelta(3), 2)
    check(
        "ongoing deviation past the term counts as missed",
        summary["current_deviation"]["fail_days"] == 4 and (summary["in_term"], summary["judged"]) == (0, 1),
    )

    print("\n[3] Stage readiness")
    spec = {
        **SPEC,
        "stage": "stabilization",
        "integration": {
            "window_days": 14,
            "min_observed_days": 10,
            "min_success_rate": 0.8,
            "max_recovery_days": 2,
            "max_deviation_days": 7,
        },
    }
    today = D0 + timedelta(days=13)
    perfect = [night(D0 + timedelta(i), "23:00", "07:00") for i in range(14)]
    days, vers = sleep_days(perfect, today, vers=versions((D0, spec)))
    check_result = cv.integration_check(spec, days, cv.find_episodes(days, vers), today)
    recovery = next(c for c in check_result["criteria"] if c["key"] == "recovery")
    check(
        "perfect run leaves recovery untested and not ready",
        recovery["status"] == "untested" and not check_result["ready"],
        str(recovery),
    )
    one_slip = perfect[:5] + [night(D0 + timedelta(5), "04:00", "12:00")] + perfect[6:]
    days, vers = sleep_days(one_slip, today, vers=versions((D0, spec)))
    episodes = cv.find_episodes(days, vers)
    check_result = cv.integration_check(spec, days, episodes, today)
    check("a quick recovery makes the habit ready", check_result["ready"], str(check_result["criteria"]))
    rec = cv.recommendation(spec, days, episodes, today)
    check("recommendation suggests integration", rec is not None and rec["to"] == "integrated", str(rec))
    formation = {**SPEC, "stabilization": {"window_days": 14, "min_success_rate": 0.7, "min_observed_days": 10}}
    days, vers = sleep_days(perfect, today, vers=versions((D0, formation)))
    rec = cv.recommendation(formation, days, cv.find_episodes(days, vers), today)
    check("formation → stabilization recommended", rec is not None and rec["to"] == "stabilization", str(rec))
    ready = cv.stage_readiness(formation, days, cv.find_episodes(days, vers), today)
    check("readiness is full once the move is recommended", ready == 1.0, str(ready))
    days, vers = sleep_days(perfect[:5], D0 + timedelta(days=4), vers=versions((D0, formation)))
    ready = cv.stage_readiness(formation, days, cv.find_episodes(days, vers), D0 + timedelta(days=4))
    check("readiness: 5 of 10 observed days, rate above the bar", ready == 0.5, str(ready))
    check("no readiness for an integrated habit", cv.stage_readiness({"stage": "integrated"}, days, [], today) is None)
    early = cv.stage_progress(formation, days, cv.find_episodes(days, vers), D0 + timedelta(days=4))
    check(
        "stage progress names what is missing",
        early["target"] == "stabilization" and early["blockers"] and "5 з 10" in early["blockers"][0],
        str(early),
    )
    days, vers = sleep_days(perfect, today, vers=versions((D0, spec)))
    stuck = cv.stage_progress(spec, days, cv.find_episodes(days, vers), today)
    check(
        "a perfect run waits just below 100% for a tested recovery",
        stuck["readiness"] == 0.99 and any("ще не було збою" in b for b in stuck["blockers"]),
        str(stuck),
    )

    print("\n[3b] Progress history")
    fvers = versions((D0, formation))
    fdays, _ = sleep_days(perfect, today, vers=fvers)
    hist = cv.progress_history([{"id": 1, "versions": fvers, "days": fdays}], D0 - timedelta(days=30), today)
    check("history starts with the first habit", hist["days"][0]["date"] == D0.isoformat(), hist["days"][0]["date"])
    check("one point per day", len(hist["days"]) == 14, str(len(hist["days"])))
    now = cv.compute_rank({1: fvers}, today, readiness={1: cv.stage_readiness(formation, fdays, [], today)})
    check(
        "the last day matches the current Прорив",
        hist["days"][-1]["breakthrough"] == now["next"]["breakthrough"],
        f"{hist['days'][-1]} vs {now['next']['breakthrough']}",
    )
    check(
        "readiness grows day by day as it was then",
        hist["readiness"][1][0]["value"] < hist["readiness"][1][-1]["value"] == 1.0,
        str([r["value"] for r in hist["readiness"][1]]),
    )
    check(
        "the stage path is one formation segment",
        hist["segments"][1] == [{"stage": "formation", "start": D0.isoformat(), "end": today.isoformat()}],
        str(hist["segments"][1]),
    )
    slips = cv.find_episodes(*sleep_days(one_slip, today, vers=versions((D0, spec))))
    monthly = cv.deviations_by_month(slips, today, months=3)
    check(
        "deviations per month with the days to the first good day",
        len(monthly) == 3
        and monthly[-1]["month"] == today.isoformat()[:7]
        and sum(m["deviations"] for m in monthly) == 1
        and [m["first_ok_median"] for m in monthly if m["deviations"]] == [1],
        str(monthly),
    )
    slipping = {**SPEC, "stage": "integrated", "maintenance": {"window_days": 14, "min_success_rate": 0.6}}
    late = [night(D0 + timedelta(i), "04:00", "12:00") for i in range(14)]
    days, vers = sleep_days(late, today, vers=versions((D0, slipping)))
    rec = cv.recommendation(slipping, days, cv.find_episodes(days, vers), today)
    check(
        "a slipping integrated habit goes back to stabilization",
        rec is not None and rec["to"] == "stabilization",
        str(rec),
    )
    check("the recovery stage is gone", "recovery" not in cv.STAGES)

    print("\n[3c] Stages move by themselves")
    fvers = versions((D0, SPEC))
    fdays, _ = sleep_days(perfect, today, vers=fvers)
    staged, changes = cv.staged_versions(fvers, fdays, today)
    moved = D0 + timedelta(days=9)  # the 10th observed day, all of them successes
    check(
        "formation moves to stabilization on the day the criteria are met",
        [(v["effective_from"], v["spec"]["stage"], v["author"]) for v in staged]
        == [(D0, "formation", "user"), (moved, "stabilization", "auto")]
        and changes[-1]["auto"]
        and changes[-1]["date"] == moved,
        str([(v["effective_from"], v["spec"]["stage"]) for v in staged]),
    )
    check("the stored versions are left as they are", len(fvers) == 1 and fvers[0]["spec"]["stage"] == "formation")
    tvers = [
        {**v, "reason": f"v{v['id']}"} for v in versions((D0, SPEC), (D0, {**SPEC, "level": {"wake_by": "08:30"}}))
    ]
    check(
        "the first stage comes with the reason of the version that set it",
        cv.staged_versions(tvers, fdays, today)[1][0]["reason"] == "v1",
        str(cv.staged_versions(tvers, fdays, today)[1][0]),
    )
    check(
        "rank counts the stage the habit reached",
        cv.compute_rank({1: staged}, today)["name"] == "Адепт другого рівня"
        and cv.compute_rank({1: fvers}, today)["name"] == "Адепт першого рівня",
    )
    stricter = {**SPEC, "level": {"wake_by": "08:00", "min_sleep_h": 7.5}}
    for label, later in (
        ("an older passport edit", stricter),
        ("a passport edit", {**stricter, cv.STAGE_SET: False}),
    ):
        evers = versions((D0, SPEC), (D0 + timedelta(days=11), later))
        edays, _ = sleep_days(perfect, today, vers=evers)
        estaged, _ = cv.staged_versions(evers, edays, today)
        check(
            f"{label} after the move keeps the stage",
            cv.latest_spec(estaged)["stage"] == "stabilization"
            and cv.latest_spec(estaged)["level"]["min_sleep_h"] == 7.5
            and cv.STAGE_SET not in cv.latest_spec(estaged),
            str([(v["effective_from"], v["spec"]["stage"]) for v in estaged]),
        )
    hand = {**SPEC, "stage": "integrated", cv.STAGE_SET: True}
    hvers = versions((D0, SPEC), (D0 + timedelta(days=11), hand))
    hdays, _ = sleep_days(perfect, today, vers=hvers)
    hstaged, hchanges = cv.staged_versions(hvers, hdays, today)
    check(
        "a stage set by hand holds while its criteria allow",
        cv.latest_spec(hstaged)["stage"] == "integrated" and not hchanges[-1]["auto"],
        str(hchanges),
    )
    holding = {**SPEC, "stage": "integrated", "maintenance": {"window_days": 14, "min_success_rate": 0.6}}
    # Ten good nights, then late ones: on day 15 only 8 of the last 14 are successes (57% < 60%).
    slide = [night(D0 + timedelta(i), "23:00", "07:00") for i in range(10)]
    slide += [night(D0 + timedelta(i), "04:00", "12:00") for i in range(10, 20)]
    dvers = versions((D0, holding))
    ddays, _ = sleep_days(slide, D0 + timedelta(days=19), vers=dvers)
    _dstaged, dchanges = cv.staged_versions(dvers, ddays, D0 + timedelta(days=19))
    check(
        "an integrated habit that slips goes back to stabilization by itself",
        dchanges[-1]["auto"]
        and (dchanges[-1]["from"], dchanges[-1]["to"]) == ("integrated", "stabilization")
        and dchanges[-1]["date"] == D0 + timedelta(days=15),
        str(dchanges),
    )
    pvers = versions((D0, {**SPEC, "stage": "planned", "start_date": (D0 + timedelta(days=3)).isoformat()}))
    pdays, _ = sleep_days([], D0 + timedelta(days=5), vers=pvers)
    pstaged, _ = cv.staged_versions(pvers, pdays, D0 + timedelta(days=5))
    check(
        "a planned habit starts forming on its start date",
        [(v["effective_from"], v["spec"]["stage"]) for v in pstaged]
        == [(D0, "planned"), (D0 + timedelta(days=3), "formation")],
        str([(v["effective_from"], v["spec"]["stage"]) for v in pstaged]),
    )
    waiting = sleep_days([], D0 + timedelta(days=1), vers=pvers)[0]
    check(
        "before its start date a planned habit keeps its passport without any day",
        waiting == []
        and [v["spec"]["stage"] for v in cv.staged_versions(pvers, waiting, D0 + timedelta(days=1))[0]] == ["planned"],
    )

    print("\n[4] Ranks")

    def stage_versions(*stages):
        return [
            {"id": i + 1, "effective_from": D0 + timedelta(days=on), "spec": {"name": "h", "stage": st}}
            for i, (st, on) in enumerate(stages)
        ]

    def rank_name(habits: dict, on: int) -> str:
        return cv.compute_rank(habits, D0 + timedelta(days=on))["name"]

    check("no habits: mortal", rank_name({}, 0) == "Звичайна людина")
    habits = {1: stage_versions(("formation", 0))}
    check("formation: adept 1", rank_name(habits, 0) == "Адепт першого рівня")
    habits = {1: stage_versions(("formation", 0), ("stabilization", 30))}
    check("stabilization: adept 2", rank_name(habits, 30) == "Адепт другого рівня")
    habits = {
        1: stage_versions(("formation", 0), ("integrated", 90)),
        2: stage_versions(("integrated", 200)),
        3: stage_versions(("integrated", 300)),
    }
    check("3 integrated habits: Magus rank 2", rank_name(habits, 300) == "Маг другого рангу", rank_name(habits, 300))
    two_stab = {1: stage_versions(("stabilization", 0)), 2: stage_versions(("stabilization", 0))}
    check("two habits in stabilization: adept 3", rank_name(two_stab, 0) == "Адепт третього рівня")
    one_each = {1: stage_versions(("integrated", 0)), 2: stage_versions(("stabilization", 0))}
    check("one integrated and one stabilizing: Magus rank 1", rank_name(one_each, 0) == "Маг першого рангу")
    lone = {1: stage_versions(("integrated", 0))}
    check("ranks are climbed in order: a lone integrated habit", rank_name(lone, 0) == "Адепт другого рівня")
    check("planned habit is not active", rank_name({1: stage_versions(("planned", 0))}, 0) == "Звичайна людина")
    pair = {1: stage_versions(("integrated", 0)), 2: stage_versions(("integrated", 0))}
    check("Magus rank 2 needs a habit held 1 month: 29 days", rank_name(pair, 28) == "Маг першого рангу")
    check("Magus rank 2 needs a habit held 1 month: 30 days", rank_name(pair, 29) == "Маг другого рангу")
    dropped = {
        1: stage_versions(("integrated", 0), ("stabilization", 40), ("integrated", 50)),
        2: stage_versions(("integrated", 0), ("stabilization", 40), ("integrated", 50)),
    }
    fallen = cv.compute_rank(dropped, D0 + timedelta(days=40))
    check(
        "a habit back in stabilization stops counting at once, peak remembered",
        fallen["name"] == "Адепт третього рівня" and fallen["peak_name"] == "Маг другого рангу" and fallen["warnings"],
        f"{fallen['name']} / {fallen['peak_name']}",
    )
    again = cv.compute_rank(dropped, D0 + timedelta(days=60))
    check(
        "re-integration starts the hold again",
        again["name"] == "Маг першого рангу" and {h["held_days"] for h in again["habits"]} == {11},
        f"{again['name']} {[h['held_days'] for h in again['habits']]}",
    )
    check("the hold is earned again after a month", rank_name(dropped, 79) == "Маг другого рангу")
    four = {i: stage_versions(("integrated", 0)) for i in range(1, 5)}
    check("Magus rank 3 needs two habits held 2 months", rank_name(four, 58) == "Маг другого рангу")
    check("Magus rank 3 after 60 days", rank_name(four, 59) == "Маг третього рангу")
    ladder = cv.compute_rank(four, D0)["ladder"]
    starting = {1: stage_versions(("formation", 0))}
    check("Прорив without readiness is 0", cv.compute_rank(starting, D0)["next"]["breakthrough"] == 0)
    half = cv.compute_rank(starting, D0, readiness={1: 0.5})["next"]
    check("Прорив counts readiness for the next stage", half["breakthrough"] == 50, str(half))
    holding = cv.compute_rank(pair, D0 + timedelta(days=14))["next"]
    check(
        "Прорив counts the hold already behind: 2 of 2 integrated, 15 of 30 days",
        holding["name"] == "Маг другого рангу" and holding["breakthrough"] == 75,
        str(holding),
    )
    report = cv.compute_rank(dropped, D0 + timedelta(days=60))
    check(
        "habits per stage today",
        report["stages"] == {"planned": 0, "formation": 0, "stabilization": 0, "integrated": 2},
        str(report["stages"]),
    )
    check(
        "stage timeline keeps only the changes and today",
        [t["date"] for t in report["timeline"]] == [(D0 + timedelta(days=n)).isoformat() for n in (0, 40, 50, 60)]
        and report["timeline"][1]["stabilization"] == 2,
        str(report["timeline"]),
    )
    check("hold shown in months", "утримуються ≥ 2 міс." in ladder[6]["requirement"], ladder[6]["requirement"])
    check("hold shown in years", "≥ 20 утримуються ≥ 1 рік" in ladder[10]["requirement"], ladder[10]["requirement"])
    check("5 years", "≥ 128 утримуються ≥ 5 років" in ladder[13]["requirement"], ladder[13]["requirement"])
    same_day = {1: stage_versions(("formation", 0), ("integrated", 5), ("stabilization", 5))}
    check("same-day correction: last version wins", rank_name(same_day, 5) == "Адепт другого рівня")

    print("\n[4b] Review regressions")
    dst = night(date(2026, 10, 25), "23:00", "07:00")  # clocks go back at 04:00 that night
    check("night across a DST switch counts elapsed hours", abs(dst.hours - 9) < 0.01, str(dst.hours))
    wake = datetime.combine(D0 + timedelta(1), cv.parse_hhmm("07:00"), TZ)
    typo = cv.Night(2, wake - timedelta(hours=20.5), wake)
    day = sleep_days([night(D0 + timedelta(1), "23:00", "07:00"), typo], D0 + timedelta(1))[0][-1]
    check(
        "a mistyped long entry does not hide the real night",
        day.status == "success" and abs(day.night.hours - 8) < 0.01,
        f"{day.status} {day.night.hours}",
    )

    quit_spec = {"name": "Quit", "stage": "formation", "start_date": D0.isoformat(), "level": {}}
    untracked = cv.build_days("quit", versions((D0, quit_spec)), {}, {}, [], D0 + timedelta(5), tracked=False)
    check(
        "quit habit without a tracker invents no successes",
        {d.status for d in untracked} == {"no_data"},
        str({d.status for d in untracked}),
    )
    window = cv.build_days("quit", versions((D0, quit_spec)), {}, {}, [], D0 + timedelta(3), today=D0 + timedelta(10))
    check("a past range ends on a closed day", window[-1].status == "success", window[-1].status)

    short, full = ("02:30", "07:30"), ("23:00", "07:00")
    pattern = [short, full, short, full, short, full, full]
    zigzag, zvers = sleep_days([night(D0 + timedelta(i), *pattern[i]) for i in range(7)], D0 + timedelta(6))
    episodes = cv.find_episodes(zigzag, zvers)
    check(
        "a zigzag deviation lasts until confirmed recovery",
        len(episodes) == 1 and episodes[0].elapsed(D0 + timedelta(6)) == 6,
        str([e.as_dict(D0) for e in episodes]),
    )
    strict = {**SPEC, "integration": {"window_days": 7, "min_observed_days": 1, "max_deviation_days": 3}}
    crit = {c["key"]: c for c in cv.integration_check(strict, zigzag, episodes, D0 + timedelta(6))["criteria"]}
    check(
        "long zigzag deviation fails the integration criterion",
        crit["long_deviation"]["status"] == "not_met" and crit["long_deviation"]["actual"] == 6,
        str(crit["long_deviation"]),
    )

    bad_specs = {
        "start_date": {**SPEC, "start_date": "yesterday"},
        "min_observed_days": {**SPEC, "integration": {"min_observed_days": "many"}},
        "priority": {**SPEC, "priority": "high"},
        "level type": {**SPEC, "level": "8h"},
        "min_amount": {**SPEC, "level": {"min_amount": "lots"}},
        "rules type": {**SPEC, "rules": [1]},
        "zero recovery term": {**SPEC, "rules": {"recovery_ok_days": 0}},
        "ancient start": {**SPEC, "start_date": "1900-01-01"},
    }
    for label, bad_spec in bad_specs.items():
        try:
            cv.validate_spec("sleep", bad_spec)
            check(f"invalid passport rejected: {label}", False)
        except cv.PassportError:
            check(f"invalid passport rejected: {label}", True)
    for label, ladder in {
        "integrated": [{"name": "A", "req": {"integrated": "abc"}}],
        "durable": [{"name": "A", "req": {"durable": [3]}}],
        "flag": [{"name": "A", "req": {"active": "yes"}}],
        "stabilizing count": [{"name": "A", "req": {"stabilizing": "two"}}],
    }.items():
        try:
            cv.validate_ranks(ladder)
            check(f"invalid rank ladder rejected: {label}", False)
        except cv.PassportError:
            check(f"invalid rank ladder rejected: {label}", True)
    check(
        "stabilizing accepts a count",
        cv.validate_ranks([{"name": "A", "req": {"stabilizing": 2}}])[0]["req"] == {"stabilizing": 2},
    )
    check("rank ladder gets req filled in", cv.validate_ranks([{"name": "A"}]) == [{"name": "A", "req": {}}])

    print("\n[4c] Tolerance band and all habits together")
    tolerant = {
        **SPEC,
        "level": {"wake_by": "08:00", "min_sleep_h": 7.5, "max_sleep_h": 9.5},
        "tolerance": {"wake_by": "08:00", "min_sleep_h": 6.5, "max_sleep_h": 10.5},
        "minimum": {"wake_by": "09:00", "min_sleep_h": 6.5, "max_sleep_h": 10.5},
    }
    cv.validate_spec("sleep", tolerant)
    tv = versions((D0, tolerant))
    short = sleep_days([night(d, "01:00", "08:00")], d, vers=tv)[0][-1]
    check(
        "7 h inside the tolerance counts as success with a warning",
        (short.status, short.met, bool(short.warning)) == ("success", True, True),
        f"{short.status} {short.warning!r}",
    )
    check("warning names what happened", "сон 7 год" in short.warning and "допуску" in short.warning, short.warning)
    check(
        "warning travels with the day",
        short.as_dict()["warning"] == short.warning and short.as_dict()["status"] == "success",
    )
    long = sleep_days([night(d, "21:30", "07:30")], d, vers=tv)[0][-1]
    check("10 h is still allowed with a warning", long.status == "success" and long.warning, long.status)
    on_target = sleep_days([night(d, "23:00", "07:30")], d, vers=tv)[0][-1]
    check("target night has no warning", on_target.status == "success" and not on_target.warning)
    too_short = sleep_days([night(d, "02:00", "08:00")], d, vers=tv)[0][-1]
    check("6 h is below the tolerance and the minimum", too_short.status == "fail", too_short.status)
    late = sleep_days([night(d, "00:00", "08:40")], d, vers=tv)[0][-1]
    check("late wake inside the minimum stays minimum", (late.status, late.warning) == ("minimum", ""), late.status)
    check(
        "rates count warnings without leaving success",
        cv.rate([short, on_target], 7, d)["warnings"] == 1 and cv.rate([short], 7, d)["success_rate"] == 1,
    )

    work = {
        "name": "Work",
        "stage": "formation",
        "start_date": D0.isoformat(),
        "level": {"done_by": "18:00"},
        "tolerance": {"done_by": "19:00"},
    }
    cv.validate_spec("boolean", work)
    check("boolean deadline text", cv.level_text("boolean", work["level"]) == "виконати до 18:00")
    check("tolerance defined only with a deadline", not cv.tolerance_defined("boolean", {}))

    def done_at(clock: str) -> cv.Day:
        hour, minute, *rest = (int(part) for part in clock.split(":"))
        obs = cv.Observation(
            amount=1,
            events=1,
            first_at=datetime.min.time().replace(hour=hour, minute=minute, second=rest[0] if rest else 0),
        )
        return cv.build_days("boolean", versions((D0, work)), {d: obs}, {}, [], d)[-1]

    results = {clock: done_at(clock) for clock in ("17:55", "18:00:40", "18:30", "19:00:59", "19:01")}
    check(
        "boolean deadline and tolerance by the minute",
        [(r.status, bool(r.warning)) for r in results.values()]
        == [("success", False), ("success", False), ("success", True), ("success", True), ("fail", False)],
        str([(c, r.status, r.warning) for c, r in results.items()]),
    )
    check("boolean warning names the time", "виконано о 18:30" in results["18:30"].warning, results["18:30"].warning)
    try:
        cv.validate_spec("boolean", {**work, "tolerance": {"done_by": "19h"}})
        check("bad deadline rejected", False)
    except cv.PassportError:
        check("bad deadline rejected", True)

    sleep_hist = sleep_days(
        [night(D0 + timedelta(days=i), "23:00", "07:00") for i in (0, 1, 3)]
        + [night(D0 + timedelta(days=2), "04:00", "11:30")],
        D0 + timedelta(days=4),
    )[0]
    work_hist = cv.build_days(
        "boolean",
        versions((D0, work)),
        {D0 + timedelta(days=i): cv.Observation(amount=1, events=1) for i in (0, 1, 2)},
        {},
        [],
        D0 + timedelta(days=4),
    )
    combined = cv.combined_stats(
        [{"id": 1, "name": "Sleep", "days": sleep_hist}, {"id": 2, "name": "Work", "days": work_hist}],
        D0 + timedelta(days=1),
        D0 + timedelta(days=4),
    )
    check("series cover the window", [len(h["series"]) for h in combined["habits"]] == [4, 4])
    check(
        "habit metadata passes through", combined["habits"][1]["name"] == "Work" and "days" not in combined["habits"][1]
    )
    day3 = combined["daily"][1]  # D0+2: sleep failed, work done
    check(
        "daily totals across habits",
        (day3["judged"], day3["counts"]["fail"], day3["success_rate"]) == (2, 1, 0.5),
        str(day3),
    )
    last = combined["daily"][-1]  # D0+4: nothing recorded yet
    check("an open day without data is not a failure", last["judged"] == 0 and last["success_rate"] is None)
    first_roll = combined["habits"][0]["series"][0]["rolling"]
    check("rolling share looks back before the window", first_roll == 1.0, str(first_roll))
    summary = combined["summary"]
    check(
        "clean streak counts days without a failure",
        (summary["clean_streak"], summary["best_clean_streak"]) == (1, 2),
        f"{summary['clean_streak']} {summary['best_clean_streak']}",
    )
    check("7-day totals add every habit", summary["rates"]["7"]["judged"] == 7, str(summary["rates"]["7"]))
    check("today's pending habits", summary["today"]["pending"] == 2, str(summary["today"]))
    empty = cv.combined_stats([], D0, D0)
    check("no habits: empty statistics", empty["summary"]["clean_streak"] == 0 and empty["daily"][0]["habits"] == 0)

    print("\n[5] API")
    workdir = Path(tempfile.mkdtemp(prefix="anyhabit-cultivation-"))
    os.environ["ANYHABIT_DATA_DIR"] = str(workdir / "data")
    os.environ["ANYHABIT_SECRET_KEY"] = "test-secret"
    os.environ["ANYHABIT_COOKIE_SECURE"] = "false"
    os.environ["ANYHABIT_BOOTSTRAP_PASSWORD"] = "test-password"
    try:
        from fastapi.testclient import TestClient

        from backend.main import app

        client = TestClient(app)
        client.post("/auth/login", json={"identifier": "owner@anyhabit.local", "password": "test-password"})
        client.patch("/auth/me", json={"timezone": "Europe/Kyiv"})

        created = client.post(
            "/cultivation/habits",
            json={
                "kind": "sleep",
                "spec": {
                    "name": "Sleep",
                    "description": "Wake rested",
                    "stage": "formation",
                    "level": {"wake_by": "08:00", "min_sleep_h": 7},
                    "minimum": {"wake_by": "09:00", "min_sleep_h": 5.5},
                    "start_date": (datetime.now(TZ).date() - timedelta(days=3)).isoformat(),
                },
                "reason": "first habit",
                "effective_from": (datetime.now(TZ).date() - timedelta(days=3)).isoformat(),
            },
        )
        check(
            "habit created with its own tracker",
            created.status_code == 201 and created.json()["tracker"] is not None,
            created.text[:300],
        )
        habit = created.json()
        hid = habit["id"]

        local_today = datetime.now(TZ).date()
        yesterday = local_today - timedelta(days=1)
        slept = client.post(
            f"/cultivation/habits/{hid}/sleep",
            json={
                "bedtime": f"{(yesterday - timedelta(days=1)).isoformat()}T23:00:00",
                "wake": f"{yesterday.isoformat()}T07:00:00",
                "state": "бадьоро",
            },
        )
        check(
            "sleep entry recorded",
            slept.status_code == 201 and slept.json()["day"]["status"] == "success",
            slept.text[:300],
        )
        logs = client.get(f"/trackers/{habit['tracker']['id']}/logs/").json()
        check("night stored as a tracker log", len(logs) == 1 and abs(logs[0]["amount"] - 8) < 0.01, str(logs)[:200])

        bad = client.post(
            f"/cultivation/habits/{hid}/sleep",
            json={"bedtime": f"{yesterday.isoformat()}T08:00:00", "wake": f"{yesterday.isoformat()}T07:00:00"},
        )
        check("wake before bedtime rejected", bad.status_code == 422, bad.text[:200])

        future = client.post(
            f"/cultivation/habits/{hid}/marks",
            json={"date": (local_today + timedelta(days=2)).isoformat(), "status": "fail", "reason": "x"},
        )
        check("future marks rejected", future.status_code == 422)
        marked = client.post(
            f"/cultivation/habits/{hid}/marks",
            json={"date": local_today.isoformat(), "status": "exception", "reason": "поїздка"},
        )
        check("day marked", marked.status_code == 201 and marked.json()["status"] == "exception", marked.text[:200])

        failed_day = local_today - timedelta(days=2)
        client.post(
            f"/cultivation/habits/{hid}/marks",
            json={"date": failed_day.isoformat(), "status": "fail", "reason": "пізно ліг"},
        )
        listed = next(h for h in client.get("/cultivation/habits").json() if h["id"] == hid)
        check(
            "the habit lists its marked days, newest first",
            listed["recent_marks"]
            == [
                {"date": local_today.isoformat(), "status": "exception", "reason": "поїздка"},
                {"date": failed_day.isoformat(), "status": "fail", "reason": "пізно ліг"},
            ],
            str(listed.get("recent_marks")),
        )
        heatmap = client.get(f"/trackers/{habit['tracker']['id']}/analytics").json()["build_heatmap"]
        cells = {cell["date"]: cell for week in heatmap["columns"] for cell in week if not cell["is_filler"]}
        check(
            "tracker heatmap shows the failed day",
            cells[failed_day.isoformat()]["status"] == "fail",
            str(cells.get(failed_day.isoformat())),
        )
        check(
            "tracker heatmap carries the other day states",
            cells[yesterday.isoformat()]["status"] == "success"
            and cells[local_today.isoformat()]["status"] == "exception",
            str([cells.get(yesterday.isoformat()), cells.get(local_today.isoformat())]),
        )
        before_start = (local_today - timedelta(days=10)).isoformat()
        check("days before the habit have no state", cells[before_start]["status"] is None, str(cells[before_start]))
        bundle = client.get(f"/trackers/{habit['tracker']['id']}/bundle").json()
        bundle_cells = [cell for week in bundle["analytics"]["build_heatmap"]["columns"] for cell in week]
        check(
            "tracker bundle carries the same failure",
            [c["date"] for c in bundle_cells if c["status"] == "fail"] == [failed_day.isoformat()],
        )

        changed = client.post(
            f"/cultivation/habits/{hid}/versions", json={"patch": {"level": {"min_sleep_h": 7.5}}, "reason": "stricter"}
        )
        body = changed.json()
        check(
            "passport change keeps history",
            changed.status_code == 201 and len(body["versions"]) == 2,
            changed.text[:200],
        )
        check("patched level applied", body["passport"]["level"] == {"wake_by": "08:00", "min_sleep_h": 7.5})
        back = client.post(
            f"/cultivation/habits/{hid}/versions",
            json={"patch": {"stage": "stabilization"}, "reason": "x", "effective_from": "2000-01-01"},
        )
        check("backdating before the last version refused", back.status_code == 422, back.text[:200])

        token = client.post("/developer/tokens", json={"name": "agent"}).json()["token"]
        agent = TestClient(app)
        headers = {"Authorization": f"Bearer {token}"}
        refused = agent.post(
            f"/cultivation/habits/{hid}/stage",
            headers=headers,
            json={"stage": "stabilization", "reason": "agent thinks so"},
        )
        check("agent cannot change the passport without user consent", refused.status_code == 409, refused.text[:200])
        allowed = agent.post(
            f"/cultivation/habits/{hid}/stage",
            headers=headers,
            json={"stage": "stabilization", "reason": "user agreed", "confirmed_by_user": True},
        )
        check(
            "agent change with consent is recorded as api",
            allowed.status_code == 201 and allowed.json()["versions"][-1]["author"] == "api",
            allowed.text[:200],
        )
        by_hand = allowed.json()
        check(
            "a stage set by hand is listed as such, and the passport hides the flag",
            by_hand["versions"][-1]["spec"].get(cv.STAGE_SET) is True
            and cv.STAGE_SET not in by_hand["passport"]
            and by_hand["stage_changes"][-1]["to"] == "stabilization"
            and by_hand["stage_changes"][-1]["auto"] is False,
            str(by_hand["stage_changes"]),
        )
        edited = client.post(
            f"/cultivation/habits/{hid}/versions", json={"patch": {"why": "rest"}, "reason": "why"}
        ).json()
        check(
            "a passport edit keeps the stage and does not set it by hand",
            edited["stage"] == "stabilization" and edited["versions"][-1]["spec"].get(cv.STAGE_SET) is False,
            str(edited["versions"][-1]["spec"]),
        )
        same = client.post(f"/cultivation/habits/{hid}/stage", json={"stage": "stabilization", "reason": "again"})
        check("setting the stage the habit already has is refused", same.status_code == 409, same.text[:200])

        agent_mark = agent.post(
            f"/cultivation/habits/{hid}/marks",
            headers=headers,
            json={"date": yesterday.isoformat(), "status": "fail", "reason": "late work"},
        )
        check("agent can record facts", agent_mark.status_code == 201)
        profile = agent.put("/cultivation/profile", headers=headers, json={"ranks": None})
        check("agent cannot change the rank system", profile.status_code == 403)

        from backend.security import ACCESS_COOKIE_NAME

        via_cookie = TestClient(app)
        via_cookie.cookies.set(ACCESS_COOKIE_NAME, token)
        sneaky = via_cookie.post(f"/cultivation/habits/{hid}/stage", json={"stage": "formation", "reason": "cookie"})
        check("a token in the cookie still needs consent", sneaky.status_code == 409, sneaky.text[:200])
        check(
            "a token in the cookie cannot change ranks",
            via_cookie.put("/cultivation/profile", json={"ranks": None}).status_code == 403,
        )
        read_token = client.post("/developer/tokens", json={"name": "reader", "scope": "read"}).json()["token"]
        read_mark = agent.post(
            f"/cultivation/habits/{hid}/marks",
            headers={"Authorization": f"Bearer {read_token}"},
            json={"date": yesterday.isoformat(), "status": "success", "reason": "x"},
        )
        check("read-only token cannot write", read_mark.status_code == 403, read_mark.text[:200])
        agent_mode = agent.post(
            f"/cultivation/habits/{hid}/modes/start",
            headers=headers,
            json={"reason": "agent", "start_date": (local_today - timedelta(days=3)).isoformat()},
        )
        check("agent cannot start minimum mode without consent", agent_mode.status_code == 409, agent_mode.text[:200])
        agent_mode = agent.post(
            f"/cultivation/habits/{hid}/modes/start",
            headers=headers,
            json={"reason": "user agreed", "confirmed_by_user": True},
        )
        check(
            "agreed minimum mode records its author",
            agent_mode.status_code == 201 and agent_mode.json()["mode"]["author"] == "api",
            agent_mode.text[:200],
        )
        agent.post(f"/cultivation/habits/{hid}/modes/end", headers=headers, json={"confirmed_by_user": True})

        ahead = client.post(
            f"/cultivation/habits/{hid}/stage",
            json={
                "stage": "integrated",
                "reason": "later",
                "effective_from": (local_today + timedelta(days=30)).isoformat(),
            },
        )
        check("future effective date refused", ahead.status_code == 422, ahead.text[:200])
        ancient = client.post(
            f"/cultivation/habits/{hid}/marks", json={"date": "1900-01-01", "status": "fail", "reason": "x"}
        )
        check("ancient mark refused", ancient.status_code == 422, ancient.text[:200])
        broken = client.post(
            f"/cultivation/habits/{hid}/versions",
            json={"patch": {"integration": {"min_observed_days": "many"}}, "reason": "typo"},
        )
        check("unreadable passport refused", broken.status_code == 422, broken.text[:200])
        check("overview still works after a refused passport", client.get("/cultivation/overview").status_code == 200)

        dst_sleep = client.post(
            f"/cultivation/habits/{hid}/sleep", json={"bedtime": "2026-10-24T23:00", "wake": "2026-10-25T07:00"}
        )
        check(
            "sleep entry across DST stores elapsed hours",
            dst_sleep.status_code == 201 and abs(dst_sleep.json()["hours"] - 9) < 0.01,
            dst_sleep.text[:200],
        )
        odd_sleep = client.post(
            f"/cultivation/habits/{hid}/sleep", json={"bedtime": "2026-10-26T06:00", "wake": "2026-10-26T12:40"}
        )
        odd_night = ((odd_sleep.json().get("day") or {}).get("sleep") or {}) if odd_sleep.status_code == 201 else {}
        check(
            "bedtime is shown to the minute it was entered",
            str(odd_night.get("bedtime", "")).startswith("2026-10-26T06:00"),
            odd_sleep.text[:300],
        )

        client.post(f"/cultivation/habits/{hid}/archive")
        archived_mark = client.post(
            f"/cultivation/habits/{hid}/marks",
            json={"date": local_today.isoformat(), "status": "success", "reason": "x"},
        )
        check("archived habit refuses new marks", archived_mark.status_code == 409, archived_mark.text[:200])
        client.post(f"/cultivation/habits/{hid}/unarchive")

        started = client.post(f"/cultivation/habits/{hid}/modes/start", json={"reason": "сесія"})
        check(
            "degraded mode started",
            started.status_code == 201 and started.json()["mode"] is not None,
            started.text[:200],
        )
        again = client.post(f"/cultivation/habits/{hid}/modes/start", json={"reason": "again"})
        check("only one active degraded mode", again.status_code == 409)
        ended = client.post(f"/cultivation/habits/{hid}/modes/end", json={"reason": "done"})
        check("degraded mode ended", ended.status_code == 200 and ended.json()["mode"] is None, ended.text[:200])

        overview = client.get("/cultivation/overview").json()
        check("overview lists the active habit", [h["id"] for h in overview["active"]] == [hid], str(overview)[:300])
        check("overview says what the habit is about", overview["active"][0]["description"] == "Wake rested")
        check(
            "overview carries the current thresholds for the charts",
            overview["active"][0]["level"] == {"wake_by": "08:00", "min_sleep_h": 7.5}
            and overview["active"][0]["tolerance"] == {},
            str(overview["active"][0].get("level")),
        )
        check("overview carries the rank", overview["rank"]["name"] == "Адепт другого рівня", overview["rank"]["name"])
        check(
            "overview rank carries Прорив and habits per stage",
            isinstance(overview["rank"]["next"]["breakthrough"], int)
            and overview["rank"]["stages"]["stabilization"] == 1
            and overview["rank"]["timeline"],
            str(overview["rank"].get("stages")),
        )
        progress = client.get("/cultivation/progress", params={"days": 30}).json()
        check(
            "progress history ends with today's Прорив",
            progress["days"][-1]["breakthrough"] == overview["rank"]["next"]["breakthrough"]
            and progress["habits"][0]["progress"]["target"] == "integrated"
            and progress["habits"][0]["segments"]
            and len(progress["deviations"]) == 12,
            str({k: progress[k] for k in ("since", "until")}),
        )
        check(
            "progress window is bounded",
            client.get("/cultivation/progress", params={"days": 400}).status_code == 422,
        )
        alone = client.get("/cultivation/rank").json()
        check(
            "rank endpoint gives the same Прорив",
            alone["next"]["breakthrough"] == overview["rank"]["next"]["breakthrough"],
            str(alone["next"]),
        )

        exported = client.get("/export/?data_type=all&format=json").json()
        cult = exported.get("cultivation", {})
        check(
            "JSON export includes cultivation history",
            len(cult.get("habits", [])) == 1 and len(cult["habits"][0]["versions"]) == 4,
            str(cult)[:300],
        )

        other = TestClient(app)
        other.post(
            "/auth/register", json={"username": "other", "email": "other@example.com", "password": "other-password"}
        )
        check("another user cannot see the habit", other.get(f"/cultivation/habits/{hid}").status_code == 404)

        def restore(who, data, mode="merge"):
            files = {"file": ("backup.json", json.dumps(data), "application/json")}
            params = {"mode": mode, "dry_run": "false"}
            if mode == "replace":
                params["confirm"] = "ЗАМІНИТИ МОЇ ДАНІ"
            return who.post("/import/", params=params, files=files)

        merged = restore(other, exported)
        check(
            "import restores cultivation into another account",
            merged.status_code == 200 and merged.json()["cultivation_habits_created"] == 1,
            merged.text[:300],
        )
        restored = other.get("/cultivation/habits").json()
        check(
            "restored habit is linked to its restored tracker",
            len(restored) == 1 and restored[0]["tracker"] is not None,
            str(restored)[:300],
        )
        again = restore(other, exported)
        check(
            "re-importing does not duplicate habits", again.json()["cultivation_habits_existing"] == 1, again.text[:300]
        )

        replaced = restore(client, exported, mode="replace")
        check(
            "replace import restores cultivation",
            replaced.status_code == 200 and replaced.json()["cultivation_habits_created"] == 1,
            replaced.text[:300],
        )
        mine = client.get("/cultivation/habits").json()
        check("replace keeps the habit usable", len(mine) == 1 and mine[0]["tracker"] is not None, str(mine)[:300])

        legacy = {
            k: v for k, v in client.get("/export/?data_type=all&format=json").json().items() if k != "cultivation"
        }
        restore(client, legacy, mode="replace")
        relinked = client.get("/cultivation/habits").json()
        check(
            "replace with an older file relinks habits to restored trackers",
            len(relinked) == 1 and relinked[0]["tracker"] is not None,
            str(relinked)[:300],
        )
        night_after = client.post(
            f"/cultivation/habits/{relinked[0]['id']}/sleep",
            json={
                "bedtime": f"{(local_today - timedelta(days=2)).isoformat()}T23:30",
                "wake": f"{(local_today - timedelta(days=1)).isoformat()}T07:00",
            },
        )
        check("sleep can be logged after a replace import", night_after.status_code == 201, night_after.text[:200])

        def with_habit(**changes):
            data = json.loads(json.dumps(exported))
            data["cultivation"]["habits"][0].update(changes)
            return data

        via_token = TestClient(app)
        crafted = with_habit()
        crafted["cultivation"]["habits"][0]["versions"][-1]["spec"]["name"] = "Crafted"
        crafted["cultivation"]["profile"] = {"ranks": [{"name": "God"}]}
        token_import = via_token.post(
            "/import/",
            headers=headers,
            params={"mode": "merge", "dry_run": "false"},
            files={"file": ("b.json", json.dumps(crafted), "application/json")},
        )
        check(
            "token import skips cultivation and ranks",
            token_import.status_code == 200
            and token_import.json()["cultivation_habits_created"] == 0
            and client.get("/cultivation/rank").json()["ladder"][0]["name"] != "God",
            token_import.text[:300],
        )

        stringy = with_habit()
        stringy["cultivation"]["habits"][0]["versions"][0]["spec"]["start_date"] = 20261101
        stringy["cultivation"]["habits"][0]["versions"][-1]["spec"]["name"] = "Stringy"
        third = TestClient(app)
        third.post(
            "/auth/register", json={"username": "third", "email": "third@example.com", "password": "third-password"}
        )
        typed = restore(third, stringy)
        check(
            "import rejects mistyped passport fields",
            typed.status_code == 200 and typed.json()["cultivation_habits_skipped"] == 1,
            typed.text[:300],
        )
        check("overview survives a mistyped import", third.get("/cultivation/overview").status_code == 200)
        mixed = client.post(
            "/cultivation/habits",
            json={"kind": "boolean", "reason": "x", "spec": {"name": "Stretch", "stage": "planned", "priority": "2"}},
        )
        check("string priority refused", mixed.status_code == 422, mixed.text[:200])

        before = len(client.get("/cultivation/habits").json())
        broken_file = with_habit(kind="unknown")
        kept = restore(client, broken_file, mode="replace")
        check(
            "replace keeps habits when the file has a damaged one",
            kept.status_code == 200 and len(client.get("/cultivation/habits").json()) == before,
            kept.text[:300],
        )
        odd = json.loads(json.dumps(exported))
        odd["cultivation"] = {"habits": 5}
        check("malformed cultivation section is a warning, not an error", restore(third, odd).status_code == 200)
        odd["cultivation"] = {"habits": [{"kind": "sleep", "versions": 3}]}
        check("malformed versions are skipped", restore(third, odd).json()["cultivation_habits_skipped"] == 1)

        workday = client.post(
            "/cultivation/habits",
            json={
                "kind": "boolean",
                "spec": {
                    "name": "Finish work",
                    "stage": "formation",
                    "level": {"done_by": "18:00"},
                    "tolerance": {"done_by": "19:00"},
                    "start_date": (local_today - timedelta(days=3)).isoformat(),
                },
                "reason": "deadline habit",
                "effective_from": (local_today - timedelta(days=3)).isoformat(),
            },
        )
        check("boolean habit with a deadline created", workday.status_code == 201, workday.text[:300])
        work_id, work_tracker = workday.json()["id"], workday.json()["tracker"]["id"]
        late_log = client.post(
            f"/trackers/{work_tracker}/logs/",
            json={
                "amount": 1,
                "timestamp": datetime.combine(
                    yesterday, datetime.min.time().replace(hour=18, minute=40), TZ
                ).isoformat(),
            },
        )
        check("late completion logged", late_log.status_code in (200, 201), late_log.text[:200])
        work_days = client.get(f"/cultivation/habits/{work_id}/days").json()
        late_day = next((x for x in work_days if x["date"] == yesterday.isoformat()), {})
        check(
            "completion inside the tolerance is a success with a warning",
            late_day.get("status") == "success" and "18:40" in late_day.get("warning", ""),
            str(late_day)[:300],
        )
        detail = client.get(f"/cultivation/habits/{work_id}").json()
        check(
            "today shows the deadline and the tolerance",
            detail["today"]["requirement"] == "виконати до 18:00"
            and detail["today"]["tolerance"] == "виконати до 19:00",
            str(detail["today"])[:300],
        )
        stats = client.get("/cultivation/stats", params={"days": 14})
        body = stats.json()
        check("combined statistics served", stats.status_code == 200 and len(body["daily"]) == 14, stats.text[:200])
        check(
            "statistics list active habits with their tracker colour field",
            work_id in {h["id"] for h in body["habits"]} and all("color" in h for h in body["habits"]),
            str([h.get("id") for h in body["habits"]]),
        )
        check(
            "statistics count the warning",
            body["summary"]["rates"]["7"]["warnings"] >= 1,
            str(body["summary"]["rates"]["7"]),
        )
        check("days are bounded", client.get("/cultivation/stats", params={"days": 2}).status_code == 422)

        lost = json.loads(json.dumps(exported))
        lost["trackers"][0]["type"] = "mystery"
        fourth = TestClient(app)
        fourth.post(
            "/auth/register", json={"username": "fourth", "email": "fourth@example.com", "password": "fourth-password"}
        )
        preview = fourth.post(
            "/import/",
            params={"mode": "merge", "dry_run": "true"},
            files={"file": ("b.json", json.dumps(lost), "application/json")},
        ).json()
        check(
            "preview warns that a habit loses its tracker",
            any("трекер не знайдено" in w for w in preview["warnings"]),
            str(preview["warnings"]),
        )

        later = fourth.post(
            "/cultivation/habits",
            json={
                "kind": "boolean",
                "spec": {
                    "name": "Later",
                    "stage": "formation",
                    "start_date": (local_today + timedelta(days=2)).isoformat(),
                },
                "reason": "starts later",
            },
        ).json()
        later_map = fourth.get(f"/trackers/{later['tracker']['id']}/analytics").json()["build_heatmap"]
        check(
            "a habit that has not started yet still has a map of day states",
            later_map["day_states"] is True
            and not any(cell["status"] for week in later_map["columns"] for cell in week),
            str(later_map.get("day_states")),
        )
        plain = fourth.post(
            "/trackers/", json={"name": "Read", "category": "Learning", "type": "build", "unit": "Pages"}
        ).json()
        plain_map = fourth.get(f"/trackers/{plain['id']}/analytics").json()["build_heatmap"]
        check(
            "a plain tracker keeps the regularity map",
            plain_map["day_states"] is False,
            str(plain_map.get("day_states")),
        )

        begun = (local_today - timedelta(days=11)).isoformat()
        reading = client.post(
            "/cultivation/habits",
            json={
                "kind": "boolean",
                "reason": "x",
                "effective_from": begun,
                "spec": {"name": "Read", "stage": "formation", "start_date": begun},
            },
        ).json()
        for back_days in range(1, 11):
            client.post(
                f"/cultivation/habits/{reading['id']}/marks",
                json={
                    "date": (local_today - timedelta(days=back_days)).isoformat(),
                    "status": "success",
                    "reason": "read",
                },
            )
        reading = client.get(f"/cultivation/habits/{reading['id']}").json()
        check(
            "ten good days move the habit to stabilization by themselves",
            reading["stage"] == "stabilization" and reading["stage_changes"][-1]["auto"] is True,
            str(reading["stage_changes"]),
        )
        undone = client.post(
            f"/cultivation/habits/{reading['id']}/stage", json={"stage": "formation", "reason": "not yet"}
        )
        after = client.get(f"/cultivation/habits/{reading['id']}").json()
        check(
            "a stage the criteria would leave at once is refused and leaves no version",
            undone.status_code == 409
            and "Стабілізація" in undone.json()["detail"]
            and len(after["versions"]) == len(reading["versions"]),
            undone.text[:200],
        )
        soon = client.post(
            "/cultivation/habits", json={"kind": "boolean", "reason": "x", "spec": {"name": "Run", "stage": "planned"}}
        )
        check("a planned habit without a future start date is refused", soon.status_code == 422, soon.text[:200])
        later = client.post(
            "/cultivation/habits",
            json={
                "kind": "boolean",
                "reason": "x",
                "spec": {
                    "name": "Run",
                    "stage": "planned",
                    "start_date": (local_today + timedelta(days=3)).isoformat(),
                },
            },
        )
        check(
            "a planned habit with a future start date waits for it",
            later.status_code == 201 and later.json()["stage"] == "planned",
            later.text[:200],
        )
        for made in (reading, later.json() if later.status_code == 201 else None):
            if made:
                client.post(f"/cultivation/habits/{made['id']}/archive")
    finally:
        shutil.rmtree(workdir, ignore_errors=True)

    print()
    if failures:
        print(f"{len(failures)} CHECK(S) FAILED:")
        for failure in failures:
            print(f"  - {failure}")
        return 1
    print("ALL CULTIVATION CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
