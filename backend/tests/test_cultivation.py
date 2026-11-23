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
    slipped = dchanges[1]
    check(
        "an integrated habit that slips goes back to stabilization by itself",
        slipped["auto"]
        and (slipped["from"], slipped["to"]) == ("integrated", "stabilization")
        and slipped["date"] == D0 + timedelta(days=15),
        str(dchanges),
    )
    check(
        "a stabilization that keeps failing drops to formation",
        dchanges[2]["auto"] and (dchanges[2]["from"], dchanges[2]["to"]) == ("stabilization", "formation"),
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
    check("the default ranks ask for no hold: two integrated habits are Magus rank 2 at once", rank_name(pair, 0) == "Маг другого рангу")
    check("no default rank has a hold", not any("durable" in r["req"] for r in cv.DEFAULT_RANKS))
    # A custom ladder may still ask habits to be held.
    held_ranks = [dict(r) for r in cv.DEFAULT_RANKS]
    held_ranks[5] = {**held_ranks[5], "req": {**held_ranks[5]["req"], "durable": [1, 30]}}
    held_ranks[6] = {**held_ranks[6], "req": {**held_ranks[6]["req"], "durable": [2, 60]}}
    held_ranks[10] = {**held_ranks[10], "req": {**held_ranks[10]["req"], "durable": [20, 365]}}
    held_ranks[13] = {**held_ranks[13], "req": {**held_ranks[13]["req"], "durable": [128, 1825]}}

    def rank_name(habits: dict, on: int, ranks=held_ranks) -> str:
        return cv.compute_rank(habits, D0 + timedelta(days=on), ranks)["name"]

    check("Magus rank 2 needs a habit held 1 month: 29 days", rank_name(pair, 28) == "Маг першого рангу")
    check("Magus rank 2 needs a habit held 1 month: 30 days", rank_name(pair, 29) == "Маг другого рангу")
    dropped = {
        1: stage_versions(("integrated", 0), ("stabilization", 40), ("integrated", 50)),
        2: stage_versions(("integrated", 0), ("stabilization", 40), ("integrated", 50)),
    }
    fallen = cv.compute_rank(dropped, D0 + timedelta(days=40), held_ranks)
    check(
        "a habit back in stabilization stops counting at once, peak remembered",
        fallen["name"] == "Адепт третього рівня" and fallen["peak_name"] == "Маг другого рангу" and fallen["warnings"],
        f"{fallen['name']} / {fallen['peak_name']}",
    )
    again = cv.compute_rank(dropped, D0 + timedelta(days=60), held_ranks)
    check(
        "re-integration starts the hold again",
        again["name"] == "Маг першого рангу" and {h["held_days"] for h in again["habits"]} == {11},
        f"{again['name']} {[h['held_days'] for h in again['habits']]}",
    )
    check("the hold is earned again after a month", rank_name(dropped, 79) == "Маг другого рангу")
    four = {i: stage_versions(("integrated", 0)) for i in range(1, 5)}
    check("Magus rank 3 needs two habits held 2 months", rank_name(four, 58) == "Маг другого рангу")
    check("Magus rank 3 after 60 days", rank_name(four, 59) == "Маг третього рангу")
    ladder = cv.compute_rank(four, D0, held_ranks)["ladder"]
    starting = {1: stage_versions(("formation", 0))}
    check("Прорив without readiness is 0", cv.compute_rank(starting, D0)["next"]["breakthrough"] == 0)
    half = cv.compute_rank(starting, D0, readiness={1: 0.5})["next"]
    check("Прорив counts readiness for the next stage", half["breakthrough"] == 50, str(half))
    holding = cv.compute_rank(pair, D0 + timedelta(days=14), held_ranks)["next"]
    check(
        "Прорив counts the hold already behind: 2 of 2 integrated, 15 of 30 days",
        holding["name"] == "Маг другого рангу" and holding["breakthrough"] == 75,
        str(holding),
    )
    report = cv.compute_rank(dropped, D0 + timedelta(days=60), held_ranks)
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

    print("\n[4a] Attempts, credit and ranks by level")

    def refused(ranks) -> bool:
        try:
            cv.validate_ranks(ranks)
        except cv.PassportError:
            return True
        return False

    def steps(*items):
        """items: (day offset, stage, level[, stage_set]) — versions of a sleep habit on its ladder."""
        out = []
        for i, item in enumerate(items):
            on, st, lv = item[:3]
            flag = item[3] if len(item) > 3 else True
            spec = {**SPEC, "stage": st, "current_level": lv, "stage_set": flag}
            out.append({"id": i + 1, "effective_from": D0 + timedelta(days=on), "spec": spec})
        return out

    def good(first: int, last: int) -> list:
        return [night(D0 + timedelta(i), "23:00", "07:00") for i in range(first, last + 1)]

    def bad(first: int, last: int) -> list:
        return [night(D0 + timedelta(i), "04:00", "12:00") for i in range(first, last + 1)]

    def walk(vers, nights, last: int):
        """The staged versions, stage changes and attempt per day up to day ``last``."""
        until = D0 + timedelta(days=last)
        days_, _ = sleep_days(nights, until, vers=vers)
        attempts: dict = {}
        staged_, changes_ = cv.staged_versions(vers, days_, until, attempts)
        return staged_, changes_, attempts

    def stage_on(staged_, on: int) -> str | None:
        return (cv.spec_for(staged_, D0 + timedelta(days=on)) or {}).get("stage")

    def credit_on(staged_, on: int) -> int:
        return cv.simulate_stages(1, staged_, D0 + timedelta(days=on))[D0 + timedelta(days=on)].credit

    ones = [{"name": "-", "req": {}}, {"name": "M1", "req": {"by_level": {"1": 1}}}]

    def rank_on(staged_, on: int, ranks=ones) -> int:
        return cv.rank_index(ranks, [cv.simulate_stages(1, staged_, D0 + timedelta(days=on))[D0 + timedelta(days=on)]])

    up_vers = steps((0, "integrated", 1), (10, "formation", 2))
    st, ch, att = walk(up_vers, good(0, 40), 40)
    check("an upgrade puts the habit in formation", stage_on(st, 9) == "integrated" and stage_on(st, 10) == "formation")
    check(
        "the upgrade keeps the lower rank and the hold run",
        credit_on(st, 12) == 1
        and rank_on(st, 12) == 1
        and cv.simulate_stages(1, st, D0 + timedelta(days=12))[D0 + timedelta(days=12)].held_days == 13,
    )
    check(
        "an upgrade does not re-promote from the old successes",
        stage_on(st, 12) == "formation" and stage_on(st, 18) == "formation" and stage_on(st, 19) == "stabilization",
        str([(c["date"], c["to"]) for c in ch]),
    )
    check(
        "the new level integrates only after its own window and the credit follows",
        credit_on(st, 19) == 1 and stage_on(st, 40) in ("stabilization", "integrated"),
        str([(c["date"].isoformat(), c["to"]) for c in ch]),
    )
    check(
        "the attempt starts on the upgrade day",
        att[D0 + timedelta(days=12)].start == D0 + timedelta(days=10)
        and att[D0 + timedelta(days=12)].formation_since == D0 + timedelta(days=10)
        and att[D0 + timedelta(days=5)].start is None,
    )

    fail_vers = steps((0, "formation", 1))
    st, ch, att = walk(fail_vers, bad(0, 12) + good(13, 35), 35)
    gone = att[D0 + timedelta(days=13)]
    check(
        "formation that runs out of time flags the failure and changes nothing",
        gone.failed_on == D0 + timedelta(days=13)
        and att[D0 + timedelta(days=12)].failed_on is None
        and gone.deadline == D0 + timedelta(days=13)
        and stage_on(st, 13) == "formation"
        and not ch[1:],
        str(ch),
    )
    check(
        "a failed attempt stops the automatic moves", stage_on(st, 35) == "formation" and not any(c["auto"] for c in ch)
    )
    patient = steps((0, "formation", 1))
    patient[0]["spec"] = {**SPEC, "stage_set": True, "stabilization": {"formation_days": 40}}
    _, ch_patient, _ = walk(patient, bad(0, 12) + good(13, 35), 35)
    check(
        "with a longer formation window the same days move on",
        any(c["auto"] and c["to"] == "stabilization" for c in ch_patient),
        str(ch_patient),
    )
    retry = steps((0, "formation", 1), (20, "formation", 1))
    st, ch, att = walk(retry, bad(0, 19) + good(20, 40), 40)
    check(
        "a new by-hand version restarts the window and the moves",
        att[D0 + timedelta(days=19)].failed_on == D0 + timedelta(days=13)
        and att[D0 + timedelta(days=20)].failed_on is None
        and att[D0 + timedelta(days=20)].formation_since == D0 + timedelta(days=20)
        and att[D0 + timedelta(days=21)].deadline == D0 + timedelta(days=33)
        and stage_on(st, 28) == "formation"
        and stage_on(st, 29) == "stabilization",
        str([(c["date"].isoformat(), c["to"]) for c in ch]),
    )

    fall_back = steps((0, "integrated", 1), (10, "formation", 2), (25, "integrated", 1))
    st, ch, att = walk(fall_back, good(0, 9) + bad(10, 27), 27)
    check(
        "a failed harder level leaves the rank and the stage untouched",
        att[D0 + timedelta(days=23)].failed_on == D0 + timedelta(days=23)
        and stage_on(st, 24) == "formation"
        and all(credit_on(st, n) == 1 for n in range(10, 28))
        and rank_on(st, 24) == 1,
    )
    check(
        "after the fallback the habit is integrated and the harder level's fails do not drop it",
        stage_on(st, 25) == "integrated"
        and stage_on(st, 27) == "integrated"
        and not any(c["auto"] and c["date"] >= D0 + timedelta(days=25) for c in ch)
        and att[D0 + timedelta(days=27)].start == D0 + timedelta(days=25),
        str([(c["date"].isoformat(), c["to"], c["auto"]) for c in ch]),
    )

    dropped = steps((0, "integrated", 1), (10, "stabilization", 1, False))
    check(
        "a level-1 habit that falls out of integration loses its credit and the rank",
        credit_on(dropped, 9) == 1
        and credit_on(dropped, 10) == 0
        and rank_on(dropped, 9) == 1
        and rank_on(dropped, 10) == 0,
    )
    hard = steps((0, "integrated", 3), (10, "stabilization", 3, False))
    check(
        "a level-3 habit that falls out of integration keeps the credit of the level below",
        credit_on(hard, 9) == 3 and credit_on(hard, 10) == 2,
    )
    check(
        "a habit created on rung 2 has no credit until it integrates",
        credit_on(steps((0, "formation", 2)), 5) == 0
        and credit_on(steps((0, "stabilization", 2)), 5) == 0
        and credit_on(steps((0, "formation", 2), (5, "integrated", 2)), 5) == 2,
    )

    def state(credit_: int, stage_: str, level: int = 1, held: int = 5) -> cv.HabitRankState:
        return cv.HabitRankState(1, "h", stage_, credit_, held if credit_ else 0, level)

    star = {"by_level": {"1": 1, "2": 1, "3": 1}}
    check(
        "a level-3 credit counts for 1+, 2+ and 3+ but not 4+",
        cv._rank_met(star, [state(3, "integrated", 3)])
        and not cv._rank_met({"by_level": {"4": 1}}, [state(3, "integrated", 3)]),
    )
    check(
        "a credited habit in a harder attempt counts for stabilizing and for the rank",
        cv._rank_met({"stabilizing": 2}, [state(2, "formation", 3), state(0, "stabilization", 1)])
        and not cv._rank_met({"stabilizing": 2}, [state(0, "formation", 3), state(0, "stabilization", 1)])
        and cv._rank_met({"active": True}, [state(1, "planned", 1)]),
    )
    check(
        "a hold counts on days with a credit, whatever the attempt",
        cv._rank_met({"by_level": {"1": 1}, "durable": [1, 10]}, [state(1, "formation", 2, held=12)])
        and not cv._rank_met({"by_level": {"1": 1}, "durable": [1, 10]}, [state(1, "formation", 2, held=8)]),
    )
    check("integrated still means level 1", cv.by_level({"integrated": 3}) == {1: 3})

    check(
        "validate_ranks keeps by_level with string keys",
        cv.validate_ranks([{"name": "A", "req": {"by_level": {"1": 2, 3: 1}}}])[0]["req"]["by_level"]
        == {"1": 2, "3": 1},
    )
    check(
        "validate_ranks refuses a bad by_level",
        all(
            refused([{"name": "A", "req": {"by_level": bad_}}])
            for bad_ in (
                [],
                {"0": 1},
                {"101": 1},
                {"x": 1},
                {"1": -1},
                {"1": 1.5},
                {"1": "2"},
                {"1": 100001},
                {1: 1, "1": 2},
                {2.5: 1},
            )
        ),
    )
    check("min_level is gone from the rank requirements", refused([{"name": "A", "req": {"min_level": 2}}]))
    check(
        "the default ranks follow the table",
        [r["req"] for r in cv.DEFAULT_RANKS[4:]]
        == [
            {"by_level": {"1": 1}},
            {"by_level": {"1": 2}},
            {"by_level": {"1": 4}},
            {"by_level": {"1": 8, "2": 1}},
            {"by_level": {"1": 16, "2": 2, "3": 1}},
            {"by_level": {"1": 25, "2": 4, "3": 2, "4": 1}},
            {"by_level": {"2": 8, "3": 4, "4": 2, "5": 1}},
            {"by_level": {"3": 8, "4": 4, "5": 2}},
            {"by_level": {"4": 8, "5": 4}},
            {"by_level": {"5": 8}},
        ]
        and all(r.get("confirmed") for r in cv.DEFAULT_RANKS)
        and cv.validate_ranks(cv.DEFAULT_RANKS) == cv.DEFAULT_RANKS,
    )
    check(
        "the default requirement texts name only the integrated counts",
        cv.rank_requirement_text(cv.DEFAULT_RANKS[5]["req"]) == "інтегрованих звичок ≥ 2"
        and cv.rank_requirement_text(cv.DEFAULT_RANKS[7]["req"]) == "інтегрованих звичок: рівня 1+ ≥ 8, рівня 2+ ≥ 1",
    )
    check(
        "a requirement with one level reads as before",
        cv.rank_requirement_text({"by_level": {"1": 2}, "durable": [1, 30]})
        == "інтегрованих звичок ≥ 2, з них ≥ 1 утримуються ≥ 1 міс."
        and cv.rank_requirement_text({"integrated": 8, "durable": [4, 120]})
        == "інтегрованих звичок ≥ 8, з них ≥ 4 утримуються ≥ 4 міс.",
    )
    check(
        "a requirement with several levels names each one",
        cv.rank_requirement_text({"by_level": {"1": 8, "2": 1}, "durable": [4, 120]})
        == "інтегрованих звичок: рівня 1+ ≥ 8, рівня 2+ ≥ 1; ≥ 4 утримуються ≥ 4 міс."
        and cv.rank_requirement_text({"by_level": {"3": 8, "4": 4}})
        == "інтегрованих звичок: рівня 3+ ≥ 8, рівня 4+ ≥ 4",
        cv.rank_requirement_text({"by_level": {"1": 8, "2": 1}, "durable": [4, 120]}),
    )
    partial = cv.rank_progress(
        {"by_level": {"1": 2, "2": 2}},
        [
            cv.HabitRankState(1, "a", "stabilization", level=1),
            cv.HabitRankState(2, "b", "stabilization", level=2),
            cv.HabitRankState(3, "c", "integrated", credit=1, held_days=3, level=1),
        ],
        {1: 1.0, 2: 0.5},
    )
    check(
        "progress has one part per level; only habits at the level are one stage short",
        [p["label"] for p in partial] == ["Інтегровані звички", "Інтегровані звички рівня 2+"]
        and partial[0]["have"] == 1
        and abs(partial[0]["fraction"] - 1.0) < 1e-9
        and partial[1]["have"] == 0
        and abs(partial[1]["fraction"] - 0.25) < 1e-9,
        str(partial),
    )
    report = cv.compute_rank({1: steps((0, "integrated", 2))}, D0 + timedelta(days=1))
    check(
        "rank habits carry the level, the credit and the counted flag",
        report["habits"][0]["level"] == 2 and report["habits"][0]["credit"] == 2 and report["habits"][0]["counted"],
    )

    rewalk, _ = sleep_days(good(0, 18) + bad(19, 19) + bad(24, 26), D0 + timedelta(days=26))
    clipped_days, clipped_eps = cv.clip_attempt(
        rewalk, steps((0, "integrated", 1), (20, "integrated", 1)), D0 + timedelta(days=20)
    )
    check(
        "deviations inside an attempt are found again from its first day",
        [e.start for e in clipped_eps] == [D0 + timedelta(days=24)]
        and clipped_days[0].date == D0 + timedelta(days=20)
        and cv.recommendation({**SPEC, "stage": "integrated"}, clipped_days, clipped_eps, D0 + timedelta(days=33))["to"]
        == "stabilization",
        str([e.start for e in clipped_eps]),
    )
    ready_days, _ = sleep_days(good(0, 12), D0 + timedelta(days=12))
    open_ = cv.stage_progress(SPEC, ready_days, [], D0 + timedelta(days=12))
    shut = cv.stage_progress(SPEC, ready_days, [], D0 + timedelta(days=12), failed=True)
    check(
        "a failed attempt is never fully ready and says why",
        open_["readiness"] == 1.0
        and shut["readiness"] == 0.99
        and shut["blockers"][0] == "Формування провалено — потрібне рішення",
        str(shut),
    )
    twice = cv.rank_progress(
        {"stabilizing": 3},
        [
            cv.HabitRankState(1, "a", "formation", credit=2, level=3),
            cv.HabitRankState(2, "b", "formation"),
        ],
        {1: 1.0, 2: 0.5},
    )
    check(
        "a credited habit in formation is not counted twice for stabilizing",
        abs(twice[0]["fraction"] - 0.5) < 1e-9 and twice[0]["have"] == 1,
        str(twice),
    )

    def refuses_formation(value) -> bool:
        try:
            cv.validate_spec("sleep", {**SPEC, "stabilization": {"formation_days": value}})
        except cv.PassportError:
            return True
        return False

    check(
        "formation_days is an integer from 1 to 365",
        all(refuses_formation(v) for v in (0, 366, 1.5, "7", True))
        and not any(refuses_formation(v) for v in (1, 7, 365, None)),
    )
    check(
        "formation_days defaults to the stabilization window",
        cv.formation_days(SPEC) == 14
        and cv.formation_days({"stabilization": {"window_days": 20}}) == 20
        and cv.formation_days({"stabilization": {"formation_days": 5}}) == 5,
    )
    short = [cv.Day(D0 + timedelta(i), "success" if i < 2 else "fail") for i in range(6)]
    kept = {**SPEC, "stage": "integrated"}
    check(
        "maintenance judges the success rate only from 7 observed days",
        cv.DEFAULT_MAINTENANCE["min_observed_days"] == 7
        and cv.recommendation(kept, short, [], D0 + timedelta(days=5)) is None
        and (
            cv.recommendation({**kept, "maintenance": {"min_observed_days": 0}}, short, [], D0 + timedelta(days=5))
            or {}
        ).get("to")
        == "stabilization",
    )

    print("\n[4a2] Levels by streak")

    rungs_q = [{"name": "Start"}, {"name": "Week", "streak_days": 7}, {"streak_days": 15}]
    quit_ladder = {"name": "Quit", "stage": "formation", "start_date": D0.isoformat(), "level": {}, "levels": rungs_q}

    def qwalk(marks, last, spec=None):
        """A quit habit with the streak ladder: staged versions, the attempt per day and the level log."""
        vers = [{"id": 1, "effective_from": D0, "spec": {**(spec or quit_ladder), "stage_set": True, "current_level": 1}}]
        until = D0 + timedelta(days=last)
        marked = {D0 + timedelta(days=n): {"status": "fail", "reason": ""} for n in marks}
        days_ = cv.build_days("quit", vers, {}, marked, [], until)
        attempts: dict = {}
        log: list = []
        staged_, changes_ = cv.staged_versions(vers, days_, until, attempts, log)
        return staged_, changes_, attempts, log

    def level_on(staged_, on: int) -> int:
        return cv.current_level_number(cv.spec_for(staged_, D0 + timedelta(days=on)))

    st, ch, att, log = qwalk([], 8)
    check(
        "a streak raises the level by itself on the day it is reached",
        level_on(st, 5) == 1 and level_on(st, 6) == 2 and stage_on(st, 6) == "formation",
        str(log),
    )
    check(
        "the automatic level starts a new attempt in formation",
        att[D0 + timedelta(days=6)].start == D0 + timedelta(days=6)
        and att[D0 + timedelta(days=6)].formation_since == D0 + timedelta(days=6)
        and att[D0 + timedelta(days=6)].level == 2
        and att[D0 + timedelta(days=5)].start is None,
    )
    check(
        "the level log marks the automatic step",
        log
        == [
            {
                "date": (D0 + timedelta(days=6)).isoformat(),
                "from": 1,
                "to": 2,
                "reason": "Серія без зриву 7 дн. — рівень 2",
                "author": "auto",
                "auto": True,
            }
        ],
        str(log),
    )
    st_i, ch_i, _, _ = qwalk([], 8, {**quit_ladder, "stage": "integrated"})
    check(
        "from integration the automatic level puts the habit in formation",
        stage_on(st_i, 5) == "integrated" and stage_on(st_i, 6) == "formation"
        and any(c["auto"] and c["from"] == "integrated" and c["to"] == "formation" for c in ch_i),
        str(ch_i),
    )

    st, ch, att, log = qwalk([10], 30)
    check(
        "a relapse keeps the level and starts the streak over",
        level_on(st, 10) == 2 and level_on(st, 12) == 2 and att[D0 + timedelta(days=12)].streak == 2,
    )
    check(
        "the next level needs a new streak of its own length",
        level_on(st, 24) == 2 and level_on(st, 25) == 3 and [c["to"] for c in log] == [2, 3],
        str(log),
    )

    st, ch, att, log = qwalk([], 20, {**quit_ladder, "stabilization": {"formation_days": 3}})
    check(
        "a failed attempt stops the streak from raising the level",
        att[D0 + timedelta(days=2)].failed_on == D0 + timedelta(days=2) and level_on(st, 20) == 1 and not log,
        str(log),
    )

    manual = [
        {"id": 1, "effective_from": D0, "spec": {**quit_ladder, "stage_set": True, "current_level": 2}},
        {"id": 2, "effective_from": D0 + timedelta(days=10), "spec": {**quit_ladder, "stage_set": False, "current_level": 1, "level_set": {"from": 2, "to": 1}}},
    ]
    mdays = cv.build_days("quit", manual, {}, {}, [], D0 + timedelta(days=20))
    mlog: list = []
    mst, _ = cv.staged_versions(manual, mdays, D0 + timedelta(days=20), None, mlog)
    check(
        "a level moved down by hand is earned again from that day",
        level_on(mst, 10) == 1 and level_on(mst, 15) == 1 and level_on(mst, 16) == 2
        and [(c["auto"], c["to"]) for c in mlog] == [(False, 1), (True, 2)],
        str(mlog),
    )
    derived_edit = manual + [
        {"id": 3, "effective_from": D0 + timedelta(days=19), "spec": {**quit_ladder, "stage_set": False, "current_level": 2, "level_set": False}}
    ]
    elog: list = []
    eatt: dict = {}
    cv.staged_versions(derived_edit, mdays, D0 + timedelta(days=20), eatt, elog)
    check(
        "an edit that stores the derived level is not a level change",
        eatt[D0 + timedelta(days=20)].start == D0 + timedelta(days=16) and [c["to"] for c in elog] == [1, 2],
        str(elog),
    )

    pending_streak = {**quit_ladder, "stage": "planned", "start_date": (D0 + timedelta(days=10)).isoformat()}
    pst, _, patt, _ = qwalk([], 22, pending_streak)
    check(
        "days before the start of a planned habit do not count towards the streak",
        patt[D0 + timedelta(days=10)].streak == 0 and level_on(pst, 16) == 1 and level_on(pst, 17) == 2,
        str([(n, patt[D0 + timedelta(days=n)].streak) for n in (9, 10, 11, 16, 17)]),
    )

    def walk_levels(*stored_specs):
        vers_ = [
            {"id": i + 1, "effective_from": D0 + timedelta(days=on), "spec": {**quit_ladder, "stage_set": False, **extra}}
            for i, (on, extra) in enumerate(stored_specs)
        ]
        until = D0 + timedelta(days=5)
        days_ = cv.build_days("quit", vers_, {}, {}, [], until)
        att_, log_ = {}, []
        st_, _ = cv.staged_versions(vers_, days_, until, att_, log_)
        return st_, att_, log_

    st_old, att_old, log_old = walk_levels((0, {"current_level": 1}), (3, {"current_level": 2}))
    check(
        "an old version without the mark moves the level when its stored level differs",
        level_on(st_old, 3) == 2 and att_old[D0 + timedelta(days=4)].start == D0 + timedelta(days=3)
        and [(c["from"], c["to"], c["auto"]) for c in log_old] == [(1, 2, False)],
        str(log_old),
    )
    st_off, att_off, log_off = walk_levels((0, {"current_level": 1}), (3, {"current_level": 2, "level_set": False}))
    check(
        "a version marked level_set false never moves the level",
        level_on(st_off, 3) == 1 and att_off[D0 + timedelta(days=4)].start is None and not log_off,
        str(log_off),
    )
    st_mv, _att_mv, log_mv = walk_levels((0, {"current_level": 1}), (3, {"current_level": 2, "level_set": {"from": 1, "to": 2}}))
    st_miss, att_miss, log_miss = walk_levels(
        (0, {"current_level": 1}), (3, {"current_level": 2, "level_set": {"from": 2, "to": 3}})
    )
    check(
        "a level move holds only from the level it was made from; otherwise the derived level stays and a new attempt begins",
        level_on(st_mv, 3) == 2
        and level_on(st_miss, 3) == 1
        and not log_miss
        and att_miss[D0 + timedelta(days=4)].start == D0 + timedelta(days=3),
        str((log_mv, log_miss)),
    )

    ladder_q = cv.build_ladder("quit", {**quit_ladder, "current_level": 1}, "formation", "", 5)
    check(
        "the ladder shows the streak rungs, the streak and the next goal",
        [x["requirement"] for x in ladder_q["levels"]] == ["без зриву", "7 дн. без зриву поспіль", "15 дн. без зриву поспіль"]
        and [x["name"] for x in ladder_q["levels"]] == ["Start", "Week", None]
        and [x["streak_days"] for x in ladder_q["levels"]] == [None, 7, 15]
        and ladder_q["auto"] is True
        and ladder_q["streak"] == 5
        and ladder_q["next_streak"] == 7
        and not ladder_q["can_upgrade"]
        and ladder_q["upgrade_blocker"] == "Рівень підвищиться сам після серії 7 дн. без зриву",
        str(ladder_q),
    )
    top = cv.build_ladder("quit", {**quit_ladder, "current_level": 3}, "formation", "", 20)
    check("the last rung has no automatic goal", top["auto"] is None and top["next_streak"] is None and top["streak"] == 20)

    def bad_rungs(kind, rungs) -> bool:
        base = {**SPEC, "levels": rungs}
        try:
            cv.validate_spec(kind, base)
        except cv.PassportError:
            return True
        return False

    lvl = {"wake_by": "08:00"}
    check(
        "streak_days is an integer from 1 to 36500 that grows along the ladder",
        all(bad_rungs("quit", [{"name": "a"}, {"streak_days": v}]) for v in (0, 36501, 1.5, 7.0, "7", True))
        and bad_rungs("quit", [{"streak_days": 7}, {"streak_days": 7}])
        and bad_rungs("quit", [{"streak_days": 30}, {"streak_days": 7}])
        and not bad_rungs("quit", [{"name": "a"}, {"streak_days": 7}, {"streak_days": 36500}]),
    )
    check(
        "streak_days belongs to quit habits only; any other rung needs its requirement",
        all(bad_rungs(kind, [{"level": lvl}, {"level": lvl, "streak_days": 7}]) for kind in ("sleep", "build", "boolean"))
        and not bad_rungs("quit", [{"name": "a"}, {"streak_days": 7}])
        and bad_rungs("sleep", [{"level": lvl}, {}])
        and bad_rungs("build", [{}]),
    )

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
    check(
        "a boolean day gives the time it was done",
        results["18:00:40"].as_dict()["first_at"] == "18:00",
        str(results["18:00:40"].as_dict()),
    )
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

    print("\n[4d] Levels, bed_by and demotion")
    rung_a = {"name": "Base", "level": {"bed_by": "23:30", "wake_by": "08:00", "min_sleep_h": 7}}
    rung_b = {"level": {"bed_by": "23:00", "wake_by": "07:30", "min_sleep_h": 7}, "minimum": {"wake_by": "09:00"}}
    laddered = {**SPEC, "levels": [rung_a, rung_b], "current_level": 2}
    cv.validate_spec("sleep", laddered)
    cv.validate_spec("sleep", {**SPEC, "levels": [rung_a]})

    def refused(label, patch):
        try:
            cv.validate_spec("sleep", {**SPEC, **patch})
            check(label, False)
        except cv.PassportError as exc:
            check(label, True, str(exc))

    refused("an empty ladder is refused", {"levels": []})
    refused("a ladder must be a list", {"levels": {"level": {}}})
    refused("a rung must be an object", {"levels": [rung_a, "x"]})
    refused("a rung level is checked", {"levels": [{"level": {"bed_by": "late"}}]})
    refused("a rung minimum is checked", {"levels": [{"minimum": {"min_sleep_h": -1}}]})
    refused("a rung name must be text", {"levels": [{"name": 3}]})
    refused("current_level above the ladder is refused", {"levels": [rung_a], "current_level": 2})
    refused("current_level 0 is refused", {"levels": [rung_a], "current_level": 0})
    refused("current_level must be an integer", {"levels": [rung_a], "current_level": 1.5})
    refused("current_level needs a ladder", {"current_level": 1})
    refused("drop_rate above 1 is refused", {"stabilization": {"drop_rate": 1.5}})
    refused("drop_rate of 0 is refused", {"stabilization": {"drop_rate": 0}})
    refused("drop_rate above the promotion threshold is refused", {"stabilization": {"drop_rate": 0.8}})
    refused("a rung needs a requirement", {"levels": [{"name": "x"}]})
    refused("a sleep rung needs a defined requirement", {"levels": [{"level": {}}]})
    cv.validate_spec("sleep", {**SPEC, "stabilization": {"min_success_rate": 0.4}})
    check("a low promotion threshold still validates without drop_rate", True)

    bed = {**SPEC, "level": {"bed_by": "00:00"}, "minimum": {}}
    bvers = versions((D0, bed))

    def bed_status(bed_time: str, spec_vers=bvers, seconds: int = 0) -> str:
        bt = cv.parse_hhmm(bed_time)
        bed_day = d - timedelta(days=1) if bt.hour >= 12 else d
        start = datetime.combine(bed_day, bt, TZ).replace(second=seconds)
        wake = datetime.combine(d, cv.parse_hhmm("10:15"), TZ)
        return sleep_days([cv.Night(1, start, wake)], d, vers=spec_vers)[0][-1].status

    check(
        "bed_by 00:00 includes 23:30 and 00:00, not 00:01",
        [bed_status(t) for t in ("23:30", "00:00", "00:01")] == ["success", "success", "fail"],
        str([bed_status(t) for t in ("23:30", "00:00", "00:01")]),
    )
    check("bed_by counts minutes: 00:00:40 still meets 00:00", bed_status("00:00", seconds=40) == "success")
    check("a morning bedtime is later than any evening one", bed_status("04:00") == "fail")
    check(
        "a sleep level with only bed_by is defined",
        cv.level_defined("sleep", {"bed_by": "23:30"}) and cv.tolerance_defined("sleep", {"bed_by": "23:30"}),
    )
    check(
        "level text puts the bedtime first",
        cv.level_text("sleep", {"bed_by": "00:00", "wake_by": "10:15", "min_sleep_h": 7, "max_sleep_h": 10})
        == "заснути до 00:00, підйом до 10:15, сон 7–10 год",
        cv.level_text("sleep", {"bed_by": "00:00", "wake_by": "10:15", "min_sleep_h": 7, "max_sleep_h": 10}),
    )
    soft = {**SPEC, "level": {"bed_by": "23:30"}, "tolerance": {"bed_by": "00:30"}, "minimum": {}}
    soft_day = bed_status("00:10", spec_vers=versions((D0, soft)))
    soft_full = sleep_days(
        [cv.Night(1, datetime.combine(d, cv.parse_hhmm("00:10"), TZ), datetime.combine(d, cv.parse_hhmm("08:00"), TZ))],
        d,
        vers=versions((D0, soft)),
    )[0][-1]
    check(
        "bedtime inside the tolerance is a success whose warning says when sleep began",
        soft_day == "success" and soft_full.warning.startswith("заснув 00:10, підйом 08:00"),
        soft_full.warning,
    )

    check(
        "a ladder-less habit has one rung and cannot be upgraded",
        cv.build_ladder("sleep", SPEC, "integrated")
        == {
            "current": 1,
            "count": 1,
            "levels": [
                {
                    "number": 1,
                    "name": None,
                    "streak_days": None,
                    "requirement": "підйом до 08:00, сон ≥ 7 год",
                    "tolerance": None,
                    "minimum": "підйом до 09:00, сон ≥ 5.5 год",
                    "current": True,
                }
            ],
            "can_upgrade": False,
            "upgrade_blocker": "Наступного рівня в паспорті немає",
            "can_downgrade": False,
            "auto": None,
            "streak": None,
            "next_streak": None,
        },
        str(cv.build_ladder("sleep", SPEC, "integrated")),
    )
    ladder = cv.build_ladder("sleep", {**laddered, "current_level": 1}, "stabilization")
    check(
        "the ladder explains why a habit cannot go up yet",
        ladder["upgrade_blocker"] == "Підвищити рівень можна лише інтегрованій звичці"
        and not ladder["can_upgrade"]
        and [x["current"] for x in ladder["levels"]] == [True, False]
        and ladder["levels"][0]["name"] == "Base"
        and cv.build_ladder("sleep", {**laddered, "current_level": 1}, "integrated")["can_upgrade"],
        str(ladder),
    )
    fall_nights = [night(D0 + timedelta(i), "23:00", "07:00") for i in range(10)]
    fall_nights += [night(D0 + timedelta(i), "04:00", "12:00") for i in range(10, 30)]
    fall_vers = versions((D0, SPEC))
    fall_days, _ = sleep_days(fall_nights, D0 + timedelta(days=29), vers=fall_vers)
    fall = [c for c in cv.staged_versions(fall_vers, fall_days, D0 + timedelta(days=29))[1] if c["auto"]]
    drop = next((c for c in fall if c["to"] == "formation"), None)
    check(
        "stabilization drops to formation when successes fall under the drop rate",
        bool(drop) and drop["from"] == "stabilization" and "поріг падіння 50%" in drop["reason"],
        str(fall),
    )
    steady = [
        night(D0 + timedelta(i), "23:00" if i % 10 < 7 else "04:00", "07:00" if i % 10 < 7 else "12:00")
        for i in range(60)
    ]
    steady_days, _ = sleep_days(steady, D0 + timedelta(days=59), vers=fall_vers)
    steady_moves = [
        (c["from"], c["to"]) for c in cv.staged_versions(fall_vers, steady_days, D0 + timedelta(days=59))[1]
    ]
    check(
        "a habit at the promotion threshold does not flip-flop",
        ("formation", "stabilization") in steady_moves and ("stabilization", "formation") not in steady_moves,
        str(steady_moves),
    )
    low = {**SPEC, "stage": "stabilization", "stabilization": {"min_success_rate": 0.4}}
    low_nights = [
        night(D0 + timedelta(i), "23:00" if i < 6 else "04:00", "07:00" if i < 6 else "12:00") for i in range(14)
    ]
    low_days, _ = sleep_days(low_nights, D0 + timedelta(days=13), vers=versions((D0, low)))
    check(
        "the drop never sits above the promotion threshold",
        cv.recommendation(low, low_days, [], D0 + timedelta(days=13)) is None,
        str(cv.recommendation(low, low_days, [], D0 + timedelta(days=13))),
    )
    keep = cv.stage_progress({**SPEC, "stage": "stabilization"}, fall_days[:12], [], D0 + timedelta(days=11))
    check(
        "stage progress still reads a stabilization that may drop", keep is not None and keep["target"] == "integrated"
    )

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
            cv.STAGE_SET not in by_hand["versions"][-1]["spec"]
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
            edited["stage"] == "stabilization"
            and cv.STAGE_SET not in edited["versions"][-1]["spec"]
            and edited["stage_changes"] == by_hand["stage_changes"],
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
        work_map = client.get(f"/trackers/{work_tracker}/analytics").json()["build_heatmap"]
        work_cells = {cell["date"]: cell for week in work_map["columns"] for cell in week}
        check(
            "the tracker map carries the time a deadline habit was done",
            work_cells[yesterday.isoformat()]["first_at"] == "18:40"
            and work_cells[local_today.isoformat()]["first_at"] is None,
            str(work_cells.get(yesterday.isoformat())),
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
            f"/cultivation/habits/{reading['id']}/stage", json={"stage": "planned", "reason": "not yet"}
        )
        after = client.get(f"/cultivation/habits/{reading['id']}").json()
        check(
            "a stage the criteria would leave at once is refused and leaves no version",
            undone.status_code == 409
            and "Формування" in undone.json()["detail"]
            and len(after["versions"]) == len(reading["versions"]),
            undone.text[:200],
        )
        again = client.post(
            f"/cultivation/habits/{reading['id']}/stage", json={"stage": "formation", "reason": "start over"}
        )
        check(
            "a stage set by hand begins a new attempt that ignores the earlier days",
            again.status_code == 201
            and again.json()["stage"] == "formation"
            and again.json()["attempt"]["start"] == local_today.isoformat()
            and again.json()["attempt"]["formation_since"] == local_today.isoformat()
            and again.json()["recommendation"] is None,
            again.text[:300],
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

        # Levels: a ladder, a synthetic integrated habit, moves up and down.
        begin = local_today - timedelta(days=50)
        rungs = [
            {
                "name": "Base",
                "level": {"bed_by": "23:30", "wake_by": "08:00", "min_sleep_h": 7},
                "minimum": {"wake_by": "09:00", "min_sleep_h": 5.5},
            },
            {"name": "Firm", "level": {"bed_by": "23:00", "wake_by": "07:30", "min_sleep_h": 7}},
        ]
        ladder_habit = client.post(
            "/cultivation/habits",
            json={
                "kind": "sleep",
                "reason": "ladder",
                "effective_from": begin.isoformat(),
                "spec": {
                    "name": "Steps",
                    "stage": "formation",
                    "start_date": begin.isoformat(),
                    "level": rungs[0]["level"],
                    "minimum": rungs[0]["minimum"],
                    "levels": rungs,
                    "current_level": 1,
                },
            },
        )
        check("a habit with a ladder is created", ladder_habit.status_code == 201, ladder_habit.text[:300])
        lid = ladder_habit.json()["id"]
        first = ladder_habit.json()
        check(
            "ladder output of a fresh habit",
            first["ladder"]["current"] == 1
            and first["ladder"]["count"] == 2
            and first["ladder"]["levels"][0]["requirement"] == "заснути до 23:30, підйом до 08:00, сон ≥ 7 год"
            and first["ladder"]["levels"][1]["name"] == "Firm"
            and first["ladder"]["upgrade_blocker"] == "Формування провалено — потрібне рішення"  # 50 days in formation
            and not first["ladder"]["can_upgrade"]
            and first["level_changes"] == [],
            str(first["ladder"]),
        )
        early = client.post(f"/cultivation/habits/{lid}/level", json={"direction": "up", "reason": "too early"})
        check(
            "up on a habit that is not integrated is refused and leaves no version",
            early.status_code == 409
            and early.json()["detail"] == "Підвищити рівень можна лише інтегрованій звичці"
            and len(client.get(f"/cultivation/habits/{lid}").json()["versions"]) == 1,
            early.text[:200],
        )
        for back_days in range(1, 51):
            client.post(
                f"/cultivation/habits/{lid}/marks",
                json={
                    "date": (local_today - timedelta(days=back_days)).isoformat(),
                    "status": "fail" if back_days == 30 else "success",
                    "reason": "mark",
                },
            )
        made = client.get(f"/cultivation/habits/{lid}").json()
        if made["stage"] != "integrated":
            by_hand_up = client.post(
                f"/cultivation/habits/{lid}/stage", json={"stage": "integrated", "reason": "synthetic history"}
            )
            check("the synthetic habit is put on integrated", by_hand_up.status_code == 201, by_hand_up.text[:300])
        made = client.get(f"/cultivation/habits/{lid}").json()
        check(
            "the integrated habit may go up",
            made["stage"] == "integrated"
            and made["ladder"]["can_upgrade"]
            and made["ladder"]["upgrade_blocker"] is None,
            str((made["stage"], made["ladder"])),
        )
        down_first = client.post(f"/cultivation/habits/{lid}/level", json={"direction": "down", "reason": "no"})
        check(
            "down at the first level is refused",
            down_first.status_code == 409 and down_first.json()["detail"] == "Звичка вже на першому рівні",
            down_first.text[:200],
        )
        no_consent = agent.post(
            f"/cultivation/habits/{lid}/level",
            headers=headers,
            json={"direction": "up", "reason": "agent thinks so"},
        )
        check(
            "a token without confirmed_by_user cannot change the level",
            no_consent.status_code == 409
            and len(client.get(f"/cultivation/habits/{lid}").json()["versions"]) == len(made["versions"]),
            no_consent.text[:200],
        )
        before_levels = len(made["versions"])
        upgraded = client.post(f"/cultivation/habits/{lid}/level", json={"direction": "up", "reason": "ready"})
        up = upgraded.json()
        check(
            "up makes level 2 and copies the rung into the passport",
            upgraded.status_code == 201
            and len(up["versions"]) == before_levels + 1
            and up["passport"]["current_level"] == 2
            and up["passport"]["level"] == rungs[1]["level"]
            and "minimum" not in up["passport"]
            and "tolerance" not in up["passport"]
            and up["passport"]["levels"] == rungs,
            upgraded.text[:400],
        )
        check(
            "an upgrade starts the new level in formation and keeps the rank level",
            up["stage"] == "formation"
            and up["stage_changes"][-1]["to"] == "formation"
            and up["stage_changes"][-1]["auto"] is False
            and up["rank_level"] == 1
            and up["attempt"]["start"] == local_today.isoformat()
            and up["attempt"]["level"] == 2
            and up["attempt"]["formation_since"] == local_today.isoformat()
            and up["attempt"]["days"] == 14
            and up["attempt"]["day"] == 1
            and up["attempt"]["failed_on"] is None
            and up["attempt"]["action"] is None
            and made["rank_level"] == 1,
            str((up["stage_changes"][-1], up["attempt"], up["rank_level"])),
        )
        check(
            "ladder and level changes show the move",
            up["ladder"]["current"] == 2
            and [x["current"] for x in up["ladder"]["levels"]] == [False, True]
            and up["ladder"]["can_downgrade"]
            and not up["ladder"]["can_upgrade"]
            and up["ladder"]["upgrade_blocker"] == "Наступного рівня в паспорті немає"
            and up["level_changes"]
            == [
                {
                    "date": local_today.isoformat(),
                    "from": 1,
                    "to": 2,
                    "reason": "ready",
                    "author": "user",
                    "auto": False,
                }
            ],
            str((up["ladder"], up["level_changes"])),
        )
        check(
            "versions hide the stage_set flag",
            all(cv.STAGE_SET not in v["spec"] for v in up["versions"]),
            str([v["spec"].keys() for v in up["versions"]][-2:]),
        )
        compact = next(h for h in client.get("/cultivation/habits").json() if h["id"] == lid)
        check("the compact habit carries the ladder", compact["ladder"] == up["ladder"], str(compact.get("ladder")))
        check(
            "the compact habit carries the attempt and the rank level",
            compact["attempt"] == up["attempt"] and compact["rank_level"] == up["rank_level"],
            str((compact.get("attempt"), compact.get("rank_level"))),
        )
        late_night = client.post(
            f"/cultivation/habits/{lid}/sleep",
            json={
                "bedtime": f"{(local_today - timedelta(days=1)).isoformat()}T23:30:00",
                "wake": f"{local_today.isoformat()}T07:00:00",
            },
        )
        check(
            "a night after the move is judged by the harder rung",
            late_night.status_code == 201 and late_night.json()["day"]["status"] == "fail",
            late_night.text[:300],
        )
        exported_levels = client.get("/export/?data_type=all&format=json").json()
        fifth = TestClient(app)
        fifth.post(
            "/auth/register", json={"username": "fifth", "email": "fifth@example.com", "password": "fifth-password"}
        )
        round_trip = restore(fifth, exported_levels)
        check("an export with levels imports", round_trip.status_code == 200, round_trip.text[:300])
        back_home = next((h for h in fifth.get("/cultivation/habits").json() if h["name"] == "Steps"), None)
        restored_levels = fifth.get(f"/cultivation/habits/{back_home['id']}").json() if back_home else {}
        check(
            "export and import keep levels and current_level",
            restored_levels.get("passport", {}).get("levels") == rungs
            and restored_levels["passport"].get("current_level") == 2
            and restored_levels["ladder"]["current"] == 2
            and restored_levels["stage"] == "formation"
            and restored_levels["attempt"]["start"] == local_today.isoformat(),
            str(restored_levels.get("passport")),
        )
        again_up = client.post(f"/cultivation/habits/{lid}/level", json={"direction": "up", "reason": "more"})
        check(
            "up at the last rung is refused",
            again_up.status_code == 409 and again_up.json()["detail"] == "Наступного рівня в паспорті немає",
            again_up.text[:200],
        )
        stepped_down = client.post(f"/cultivation/habits/{lid}/level", json={"direction": "down", "reason": "too hard"})
        down = stepped_down.json()
        check(
            "down returns to level 1 with its fields",
            stepped_down.status_code == 201
            and down["passport"]["current_level"] == 1
            and down["passport"]["level"] == rungs[0]["level"]
            and down["passport"]["minimum"] == rungs[0]["minimum"]
            and [c["to"] for c in down["level_changes"]] == [2, 1]
            and down["stage"] == "integrated"
            and down["rank_level"] == 1
            and down["attempt"]["start"] == local_today.isoformat()
            and down["attempt"]["formation_since"] is None,
            stepped_down.text[:400],
        )
        down_again = client.post(f"/cultivation/habits/{lid}/level", json={"direction": "down", "reason": "no"})
        check("down at level 1 is refused again", down_again.status_code == 409, down_again.text[:200])

        def edit(patch: dict):
            return client.post(f"/cultivation/habits/{lid}/versions", json={"patch": patch, "reason": "edit"})

        skipped = edit({"current_level": 2})
        check(
            "a passport edit cannot move the level",
            skipped.status_code == 409 and skipped.json()["detail"] == cv.LEVEL_MOVE_REFUSED,
            skipped.text[:200],
        )
        softer = [{**rungs[0], "tolerance": {"wake_by": "10:15"}}, rungs[1]]
        edited = edit({"levels": softer})
        check(
            "editing the current rung changes the passport's own fields",
            edited.status_code == 201 and edited.json()["passport"]["tolerance"] == {"wake_by": "10:15"},
            edited.text[:300],
        )
        mirrored = edit({"minimum": {"wake_by": "10:30"}})  # a merge patch: min_sleep_h stays
        mirrored_spec = mirrored.json().get("passport", {})
        check(
            "editing the passport's own fields is written into the current rung",
            mirrored.status_code == 201
            and mirrored_spec["levels"][0]["minimum"] == {"wake_by": "10:30", "min_sleep_h": 5.5}
            and mirrored_spec["levels"][1] == rungs[1],
            mirrored.text[:300],
        )
        dropped = edit({"levels": None})
        dropped_spec = dropped.json().get("passport", {})
        check(
            "removing the ladder keeps the current requirement",
            dropped.status_code == 201
            and "levels" not in dropped_spec
            and "current_level" not in dropped_spec
            and dropped_spec["minimum"] == {"wake_by": "10:30", "min_sleep_h": 5.5},
            dropped.text[:300],
        )
        high_start = edit({"levels": rungs, "current_level": 2})
        check(
            "a new ladder starts at level 1",
            high_start.status_code == 409 and high_start.json()["detail"] == cv.NEW_LADDER_AT_ONE,
            high_start.text[:200],
        )
        client.post(f"/cultivation/habits/{lid}/archive")

        made = client.post(
            "/cultivation/habits",
            json={
                "kind": "boolean",
                "spec": {
                    "name": "Ladder at creation",
                    "level": {"done_by": "18:00"},
                    "levels": [{"level": {"done_by": "18:00"}}, {"level": {"done_by": "17:00"}}],
                    "current_level": 2,
                },
                "reason": "created on level 2",
            },
        )
        check(
            "a habit created on a rung takes that rung's requirement",
            made.status_code == 201 and made.json()["passport"]["level"] == {"done_by": "17:00"},
            made.text[:300],
        )
        if made.status_code == 201:
            client.post(f"/cultivation/habits/{made.json()['id']}/archive")

        # Attempts: a short formation window runs out on its own; a ladder habit falls back.
        long_ago = local_today - timedelta(days=12)
        steps_ = [{"level": {"done_by": "18:00"}}, {"level": {"done_by": "17:00"}}]
        brief = client.post(
            "/cultivation/habits",
            json={
                "kind": "boolean",
                "reason": "short window",
                "effective_from": long_ago.isoformat(),
                "spec": {
                    "name": "Short",
                    "stage": "formation",
                    "start_date": long_ago.isoformat(),
                    "stabilization": {"formation_days": 3},
                },
            },
        )
        brief_id = brief.json()["id"]
        out = brief.json()["attempt"]
        check(
            "a formation past its window is flagged failed on the last day",
            out["failed_on"] == (long_ago + timedelta(days=2)).isoformat()
            and out["action"] == "new_attempt"
            and out["fallback_level"] is None
            and out["deadline"] == (long_ago + timedelta(days=2)).isoformat()
            and out["days"] == 3
            and out["day"] == 13
            and out["start"] == long_ago.isoformat()
            and brief.json()["stage"] == "formation"
            and brief.json()["recommendation"] is None,
            str(out),
        )
        fresh = client.post(
            "/cultivation/habits",
            json={"kind": "boolean", "reason": "new", "spec": {"name": "Fresh", "stage": "formation"}},
        ).json()
        running = client.post(
            f"/cultivation/habits/{fresh['id']}/attempt", json={"reason": "again", "confirmed_by_user": True}
        )
        check(
            "a new attempt is refused while the current one runs",
            running.status_code == 409 and running.json()["detail"] == "Спроба ще триває",
            running.text[:200],
        )
        unconfirmed = agent.post(f"/cultivation/habits/{brief_id}/attempt", headers=headers, json={"reason": "go"})
        check(
            "a token needs the user's confirmation for a new attempt",
            unconfirmed.status_code == 409 and "confirmed_by_user" in unconfirmed.json()["detail"],
            unconfirmed.text[:200],
        )
        read_only = agent.post(
            f"/cultivation/habits/{brief_id}/attempt",
            headers={"Authorization": f"Bearer {read_token}"},
            json={"reason": "go", "confirmed_by_user": True},
        )
        check("a read-only token cannot start an attempt", read_only.status_code == 403, read_only.text[:200])
        restarted = client.post(f"/cultivation/habits/{brief_id}/attempt", json={"reason": "second try"})
        again_out = restarted.json().get("attempt", {})
        check(
            "a new attempt after the failure restarts the formation window",
            restarted.status_code == 201
            and restarted.json()["stage"] == "formation"
            and again_out["failed_on"] is None
            and again_out["action"] is None
            and again_out["start"] == local_today.isoformat()
            and again_out["formation_since"] == local_today.isoformat()
            and again_out["deadline"] == (local_today + timedelta(days=2)).isoformat()
            and restarted.json()["versions"][-1]["reason"] == "second try",
            restarted.text[:300],
        )
        client.post(f"/cultivation/habits/{brief_id}/archive")
        client.post(f"/cultivation/habits/{fresh['id']}/archive")

        rank_habit = client.post(
            "/cultivation/habits",
            json={
                "kind": "boolean",
                "reason": "ladder",
                "effective_from": long_ago.isoformat(),
                "spec": {
                    "name": "Fallback",
                    "stage": "integrated",
                    "start_date": long_ago.isoformat(),
                    "level": steps_[0]["level"],
                    "levels": steps_,
                    "current_level": 1,
                    "stabilization": {"formation_days": 2},
                },
            },
        )
        rid = rank_habit.json()["id"]
        climbed = client.post(
            f"/cultivation/habits/{rid}/level",
            json={"direction": "up", "reason": "try", "effective_from": (local_today - timedelta(days=10)).isoformat()},
        )
        hard = climbed.json()
        check(
            "a harder level that ran out of time offers the fallback and keeps the rank level",
            climbed.status_code == 201
            and hard["stage"] == "formation"
            and hard["attempt"]["failed_on"] == (local_today - timedelta(days=9)).isoformat()
            and hard["attempt"]["action"] == "fallback"
            and hard["attempt"]["fallback_level"] == 1
            and hard["attempt"]["level"] == 2
            and hard["rank_level"] == 1,
            str((hard.get("attempt"), hard.get("rank_level"))),
        )
        above = client.post(f"/cultivation/habits/{rid}/attempt", json={"reason": "retry"})
        check(
            "above level 1 a failed attempt cannot restart, only fall back",
            above.status_code == 409
            and above.json()["detail"] == "Вище рівня 1 провалена спроба повертає на попередній рівень"
            and len(client.get(f"/cultivation/habits/{rid}").json()["versions"]) == len(hard["versions"]),
            above.text[:200],
        )
        fell = client.post(f"/cultivation/habits/{rid}/level", json={"direction": "down", "reason": "too hard"})
        soft = fell.json()
        check(
            "the fallback after a failed attempt puts the habit back in stabilization on the easier level",
            fell.status_code == 201
            and soft["stage"] == "stabilization"
            and soft["passport"]["current_level"] == 1
            and soft["rank_level"] == 0
            and soft["attempt"]["failed_on"] is None
            and soft["attempt"]["start"] == local_today.isoformat(),
            fell.text[:300],
        )
        forged = client.post(
            f"/cultivation/habits/{rid}/versions",
            json={"patch": {"current_level": 2, cv.STAGE_SET: True}, "reason": "sneaky"},
        )
        check("a passport edit cannot fake a level change", forged.status_code == 409, forged.text[:200])
        client.post(f"/cultivation/habits/{rid}/stage", json={"stage": "integrated", "reason": "earned again"})
        client.post(f"/cultivation/habits/{rid}/level", json={"direction": "up", "reason": "again"})
        stripped = client.post(
            f"/cultivation/habits/{rid}/versions", json={"patch": {"levels": None}, "reason": "no ladder"}
        )
        check(
            "removing a ladder above level 1 cannot fake a level change either",
            stripped.status_code == 409 and stripped.json()["detail"] == cv.LEVEL_MOVE_REFUSED,
            stripped.text[:200],
        )
        plain_start = local_today - timedelta(days=5)
        plain = client.post(
            "/cultivation/habits",
            json={
                "kind": "boolean",
                "reason": "plain",
                "effective_from": plain_start.isoformat(),
                "spec": {"name": "Plain", "stage": "formation", "start_date": plain_start.isoformat()},
            },
        ).json()
        flag = client.post(
            f"/cultivation/habits/{plain['id']}/versions",
            json={"patch": {"description": "note", cv.STAGE_SET: True}, "reason": "edit"},
        )
        check(
            "a stage_set flag in a passport edit is overwritten and begins no attempt",
            flag.status_code == 201
            and flag.json()["attempt"]["start"] == plain_start.isoformat()
            and flag.json()["attempt"]["formation_since"] == plain_start.isoformat()
            and len(flag.json()["stage_changes"]) == len(plain["stage_changes"]),
            flag.text[:300],
        )
        client.post(f"/cultivation/habits/{plain['id']}/archive")
        client.post(f"/cultivation/habits/{rid}/archive")

        # Levels by streak: a quit habit whose ladder rises by itself.
        began = local_today - timedelta(days=20)
        streak_rungs = [{"name": "Base"}, {"name": "Week", "streak_days": 7}, {"streak_days": 15}]
        streaker = client.post(
            "/cultivation/habits",
            json={
                "kind": "quit",
                "reason": "streak ladder",
                "effective_from": began.isoformat(),
                "spec": {
                    "name": "Streak",
                    "stage": "formation",
                    "start_date": began.isoformat(),
                    "levels": streak_rungs,
                    "current_level": 1,
                },
            },
        )
        check("a quit habit with a streak ladder and no level requirements is created", streaker.status_code == 201, streaker.text[:300])
        sid = streaker.json()["id"]
        streaked = streaker.json()
        check(
            "the streak raised the level twice by itself, with no stored version",
            streaked["passport"]["current_level"] == 3
            and streaked["ladder"]["current"] == 3
            and len(streaked["versions"]) == 1
            and [(c["to"], c["auto"], c["author"]) for c in streaked["level_changes"]] == [(2, True, "auto"), (3, True, "auto")]
            and streaked["level_changes"][0]["date"] == (began + timedelta(days=6)).isoformat()
            and streaked["level_changes"][0]["reason"] == "Серія без зриву 7 дн. — рівень 2"
            and streaked["attempt"]["start"] == (began + timedelta(days=14)).isoformat()
            and streaked["stage"] == "formation"
            and streaked["ladder"]["auto"] is None
            and streaked["ladder"]["streak"] == 20,
            str((streaked["level_changes"], streaked["attempt"], streaked["ladder"]["streak"])),
        )
        edit_text = client.post(
            f"/cultivation/habits/{sid}/versions", json={"patch": {"description": "note"}, "reason": "describe"}
        )
        edited_streak = edit_text.json()
        check(
            "a passport edit that stores the derived level begins no attempt and is no level change",
            edit_text.status_code == 201
            and edited_streak["passport"]["current_level"] == 3
            and edited_streak["attempt"]["start"] == streaked["attempt"]["start"]
            and edited_streak["level_changes"] == streaked["level_changes"],
            edit_text.text[:300],
        )
        back_one = client.post(f"/cultivation/habits/{sid}/level", json={"direction": "down", "reason": "easier"})
        check(
            "a voluntary step back from the streak level is a new attempt that is earned again",
            back_one.status_code == 201
            and back_one.json()["passport"]["current_level"] == 2
            and back_one.json()["attempt"]["start"] == local_today.isoformat()
            and back_one.json()["level_changes"][-1]["auto"] is False,
            back_one.text[:300],
        )
        client.post(f"/cultivation/habits/{sid}/archive")

        recent = local_today - timedelta(days=5)
        slow = client.post(
            "/cultivation/habits",
            json={
                "kind": "quit",
                "reason": "slow ladder",
                "effective_from": recent.isoformat(),
                "spec": {
                    "name": "Slow",
                    "stage": "integrated",
                    "start_date": recent.isoformat(),
                    "levels": [{"name": "Base"}, {"name": "Month", "streak_days": 30}],
                    "current_level": 1,
                },
            },
        )
        slow_out = slow.json()
        check(
            "the ladder shows the streak and the goal of the next automatic level",
            slow.status_code == 201
            and slow_out["ladder"]["auto"] is True
            and slow_out["ladder"]["streak"] == 5
            and slow_out["ladder"]["next_streak"] == 30
            and slow_out["ladder"]["levels"][1]["requirement"] == "30 дн. без зриву поспіль"
            and slow_out["ladder"]["levels"][1]["streak_days"] == 30
            and slow_out["ladder"]["levels"][1]["name"] == "Month"
            and not slow_out["ladder"]["can_upgrade"],
            str(slow_out.get("ladder")),
        )
        by_hand_up = client.post(f"/cultivation/habits/{slow_out['id']}/level", json={"direction": "up", "reason": "now"})
        check(
            "a level with a streak cannot be raised by hand",
            by_hand_up.status_code == 409
            and by_hand_up.json()["detail"] == "Рівень підвищиться сам після серії 30 дн. без зриву",
            by_hand_up.text[:200],
        )
        def quit_ladder_habit(name: str, days_ago: int, threshold: int = 7):
            start = local_today - timedelta(days=days_ago)
            made_ = client.post(
                "/cultivation/habits",
                json={
                    "kind": "quit",
                    "reason": name,
                    "effective_from": start.isoformat(),
                    "spec": {
                        "name": name,
                        "stage": "formation",
                        "start_date": start.isoformat(),
                        "levels": [{"name": "Base"}, {"streak_days": threshold}],
                        "current_level": 1,
                    },
                },
            )
            return made_.json(), start

        raised, start_a = quit_ladder_habit("Raised", 10)
        up_day = start_a + timedelta(days=6)
        check(
            "the streak ladder habit rose on the seventh clean day",
            raised["passport"]["current_level"] == 2
            and raised["attempt"]["start"] == up_day.isoformat()
            and raised["ladder"]["streak"] == 10,
            str((raised.get("attempt"), raised["ladder"])),
        )
        edit_on = client.post(
            f"/cultivation/habits/{raised['id']}/versions",
            json={"patch": {"description": "note"}, "reason": "edit", "effective_from": up_day.isoformat()},
        )
        edited_on = edit_on.json()
        check(
            "an edit on the day of the automatic level keeps the level and the streak",
            edit_on.status_code == 201
            and edited_on["passport"]["current_level"] == 2
            and edited_on["ladder"]["streak"] == 10
            and edited_on["attempt"]["start"] == up_day.isoformat()
            and [c["auto"] for c in edited_on["level_changes"]] == [True],
            edit_on.text[:300],
        )
        stage_on_day = client.post(
            f"/cultivation/habits/{raised['id']}/stage",
            json={"stage": "stabilization", "reason": "by hand", "effective_from": (up_day + timedelta(days=1)).isoformat()},
        )
        staged_on = stage_on_day.json()
        check(
            "a stage set by hand the next day keeps the level and the streak too",
            stage_on_day.status_code == 201
            and staged_on["passport"]["current_level"] == 2
            and staged_on["ladder"]["streak"] == 10
            and [c["auto"] for c in staged_on["level_changes"]] == [True]
            and staged_on["stage"] == "stabilization",
            stage_on_day.text[:300],
        )
        moved_level = client.post(
            f"/cultivation/habits/{raised['id']}/versions",
            json={"patch": {"current_level": 1}, "reason": "sneaky"},
        )
        check(
            "a passport edit cannot change the level of a streak ladder",
            moved_level.status_code == 409 and moved_level.json()["detail"] == cv.LEVEL_MOVE_REFUSED,
            moved_level.text[:200],
        )
        client.post(f"/cultivation/habits/{raised['id']}/archive")

        lowered, start_b = quit_ladder_habit("Lowered", 10)
        up_b = start_b + timedelta(days=6)
        stepped = client.post(
            f"/cultivation/habits/{lowered['id']}/level",
            json={"direction": "down", "reason": "easier", "effective_from": up_b.isoformat()},
        )
        stepped_out = stepped.json()
        check(
            "a step back on the day of the automatic level sticks and the streak restarts that day",
            stepped.status_code == 201
            and stepped_out["passport"]["current_level"] == 1
            and stepped_out["ladder"]["streak"] == 4
            and stepped_out["attempt"]["start"] == up_b.isoformat()
            and [(c["from"], c["to"], c["auto"]) for c in stepped_out["level_changes"]] == [(2, 1, False)]
            and stepped_out["level_changes"][0]["date"] == up_b.isoformat(),
            str((stepped_out["passport"]["current_level"], stepped_out["ladder"]["streak"], stepped_out["attempt"], stepped_out["level_changes"])),
        )
        client.post(f"/cultivation/habits/{lowered['id']}/archive")

        later, start_c = quit_ladder_habit("Later", 10)
        client.post(
            f"/cultivation/habits/{later['id']}/versions",
            json={"patch": {"description": "note"}, "reason": "edit", "effective_from": (start_c + timedelta(days=8)).isoformat()},
        )
        relapse = client.post(
            f"/cultivation/habits/{later['id']}/marks",
            json={"date": (start_c + timedelta(days=3)).isoformat(), "status": "fail", "reason": "slip"},
        )
        after_relapse = client.get(f"/cultivation/habits/{later['id']}").json()
        check(
            "a relapse added afterwards does not turn an earlier edit into a manual level up",
            relapse.status_code == 201
            and after_relapse["passport"]["current_level"] == 1
            and after_relapse["level_changes"] == []
            and after_relapse["attempt"]["start"] == start_c.isoformat(),
            str((after_relapse["level_changes"], after_relapse["attempt"])),
        )
        client.post(f"/cultivation/habits/{later['id']}/archive")

        lates = local_today - timedelta(days=20)
        tall = client.post(
            "/cultivation/habits",
            json={
                "kind": "quit",
                "reason": "three rungs",
                "effective_from": lates.isoformat(),
                "spec": {
                    "name": "Tall",
                    "stage": "formation",
                    "start_date": lates.isoformat(),
                    "levels": [{"name": "Base"}, {"streak_days": 7}, {"streak_days": 14}],
                    "current_level": 1,
                },
            },
        ).json()
        step_down = client.post(f"/cultivation/habits/{tall['id']}/level", json={"direction": "down", "reason": "easier"})
        for n in (5, 10, 15):
            client.post(
                f"/cultivation/habits/{tall['id']}/marks",
                json={"date": (lates + timedelta(days=n)).isoformat(), "status": "fail", "reason": "slip"},
            )
        tall_after = client.get(f"/cultivation/habits/{tall['id']}").json()
        check(
            "late relapses cannot turn a step back into a rise onto an automatic level",
            tall["passport"]["current_level"] == 3
            and step_down.status_code == 201
            and step_down.json()["passport"]["current_level"] == 2
            and tall_after["passport"]["current_level"] == 1
            and all(c["to"] < c["from"] or c["auto"] for c in tall_after["level_changes"]),
            str((tall_after["passport"]["current_level"], tall_after["level_changes"])),
        )
        client.post(f"/cultivation/habits/{tall['id']}/archive")

        switching, start_s = quit_ladder_habit("Switching", 10)
        manual_ladder = client.post(
            f"/cultivation/habits/{switching['id']}/versions",
            json={"patch": {"levels": [{"name": "Base"}, {"name": "Top"}]}, "reason": "manual ladder"},
        )
        manual_out = manual_ladder.json()
        check(
            "switching a streak ladder to a manual one keeps the level and begins no attempt",
            manual_ladder.status_code == 201
            and manual_out["passport"]["current_level"] == 2
            and manual_out["attempt"]["start"] == (start_s + timedelta(days=6)).isoformat()
            and [c["auto"] for c in manual_out["level_changes"]] == [True],
            manual_ladder.text[:300],
        )
        client.post(f"/cultivation/habits/{switching['id']}/archive")

        def refused_ladder(kind: str, rung: dict) -> int:
            return client.post(
                "/cultivation/habits",
                json={
                    "kind": kind,
                    "reason": "no streak here",
                    "spec": {"name": "Bad", "stage": "formation", "levels": [{"level": {}}, rung], "current_level": 1},
                },
            ).status_code

        check(
            "streak_days on a rung of any other kind is refused",
            refused_ladder("boolean", {"level": {}, "streak_days": 7}) == 422
            and refused_ladder("build", {"level": {"min_amount": 2}, "streak_days": 7}) == 422
            and refused_ladder("sleep", {"level": {"wake_by": "08:00"}, "streak_days": 7}) == 422
            and refused_ladder("quit", {"streak_days": 7.0}) == 422
            and refused_ladder("quit", {"streak_days": True}) == 422
            and refused_ladder("quit", {"streak_days": 7}) == 201,
        )
        sixth = TestClient(app)
        sixth.post(
            "/auth/register", json={"username": "sixth", "email": "sixth@example.com", "password": "sixth-password"}
        )
        carried = restore(sixth, client.get("/export/?data_type=all&format=json").json())
        carried_habit = next((h for h in sixth.get("/cultivation/habits").json() if h["name"] == "Slow"), None)
        carried_full = sixth.get(f"/cultivation/habits/{carried_habit['id']}").json() if carried_habit else {}
        check(
            "an export with streak rungs imports and keeps them",
            carried.status_code == 200
            and carried_full.get("passport", {}).get("levels") == [{"name": "Base"}, {"name": "Month", "streak_days": 30}]
            and carried_full["ladder"]["next_streak"] == 30,
            str(carried_full.get("passport")),
        )
        client.post(f"/cultivation/habits/{slow_out['id']}/archive")
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
