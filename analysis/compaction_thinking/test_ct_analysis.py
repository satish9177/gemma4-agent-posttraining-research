"""Unit tests for ct_analysis.py on synthetic runs only (no real output is read).
Usage: python -I -B -X utf8 test_ct_analysis.py
"""
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ct_analysis as M  # noqa: E402


def mk_run(n, comps=(), err=(), think=None, key=("X", "A", "t")):
    """n completed calls at t = 10 i (2 s each). An attempt at position p sits between call p-1 and call p, with a
    summary request (no tools) at the same time. err: positions of failed attempts (no compaction)."""
    recs, attempts = [], []
    nm, ha = 2, 0
    for i in range(n):
        if i in comps or i in err:
            e = "boom" if i in err else None
            attempts.append({"arm": key[1], "task": key[2], "t0": 10 * i - 6, "t1": 10 * i - 1, "error": e})
            recs.append({"arm": key[1], "task": key[2], "t0": 10 * i - 6, "t1": 10 * i - 1, "has_tools": False,
                         "n_messages": 1, "hist_assistant": 0})
            if e is None:
                nm, ha = 8, 3
        th = 1 if think is None else think[i]
        recs.append({"arm": key[1], "task": key[2], "t0": 10 * i, "t1": 10 * i + 2, "has_tools": True,
                     "finish_reason": "tool_calls",
                     "n_messages": nm, "hist_assistant": ha, "hist_with_reasoning": ha,
                     "reasoning_chars": 100 if th else 0})
        nm, ha = nm + 2, ha + 1
    return M.Run(key, recs, attempts)


def main():
    fails = []

    def eq(name, got, want):
        if got != want:
            fails.append(f"{name}: got {got!r}, want {want!r}")

    # positions and events
    r = mk_run(20, comps=(10,))
    eq("attempt position", r.att_pos, [10])
    eq("first ok", r.first_ok(), 10)
    eq("event k3", M.event(r, 3), (10, None))
    eq("no compaction", M.event(mk_run(20), 3), (None, "no compaction"))
    eq("window incomplete", M.event(mk_run(20, comps=(2,)), 3), (None, "window incomplete"))
    eq("second compaction inside window", M.event(mk_run(20, comps=(10, 12)), 3),
       (None, "another compaction attempt inside the window"))
    eq("failed attempt inside window", M.event(mk_run(20, comps=(10,), err=(11,)), 3),
       (None, "another compaction attempt inside the window"))
    eq("second compaction outside window", M.event(mk_run(30, comps=(10, 13)), 3), (10, None))
    eq("first ok skips a failed attempt", mk_run(30, comps=(15,), err=(8,)).first_ok(), 15)

    # control windows
    u = mk_run(20)
    eq("uncompacted controls", [j for j in range(0, 21) if M.control_ok(u, j, 3)], list(range(3, 18)))
    c = mk_run(20, comps=(12,))
    eq("controls before a compaction only", [j for j in range(0, 21) if M.control_ok(c, j, 3)], list(range(3, 10)))
    f = mk_run(20, err=(12,))
    eq("failed attempt blocks only its window", [j for j in range(0, 21) if M.control_ok(f, j, 3)],
       list(range(3, 10)) + list(range(15, 18)))

    # difference in differences on planted data
    drop = [1] * 10 + [0] * 3 + [1] * 7
    ev_runs = [mk_run(20, comps=(10,), think=drop, key=("X", "A", f"e{i}")) for i in range(5)]
    ctl_runs = [mk_run(20, key=("X", "A", f"c{i}")) for i in range(5)]
    ev, ctl = M.unit_values(ev_runs + ctl_runs, 3, M.thinking)
    d = M.did(ev, ctl, {i: 1 for i in range(10)})
    eq("planted drop DiD", d["est"], -1.0)
    eq("planted drop parts", (d["event_pre"], d["event_post"], d["control_pre"], d["control_post"]),
       (1.0, 0.0, 1.0, 1.0))
    ev0, ctl0 = M.unit_values([mk_run(20, comps=(10,), key=("X", "A", f"e{i}")) for i in range(5)] + ctl_runs, 3,
                              M.thinking)
    eq("null DiD", M.did(ev0, ctl0, {i: 1 for i in range(10)})["est"], 0.0)
    trend = [mk_run(20, think=drop, key=("X", "A", f"c{i}")) for i in range(5)]
    evt, ctlt = M.unit_values(ev_runs + trend, 3, M.thinking)
    eq("phase effect removed by controls", M.did(evt, ctlt, {i: 1 for i in range(10)})["est"], 0.0)

    # matching
    eq("match +2", M.did({0: (10, (1.0, 0.0))}, {1: {12: (1.0, 1.0)}}, {0: 1, 1: 1})["est"], -1.0)
    m3 = M.did({0: (10, (1.0, 0.0))}, {1: {13: (1.0, 1.0)}}, {0: 1, 1: 1})
    eq("no match beyond 2", (m3["est"], m3["unmatched"]), (None, 1))
    eq("prefer j-1 over j+1", M.did({0: (10, (1.0, 0.0))}, {1: {9: (1.0, 1.0)}, 2: {11: (0.0, 1.0)}},
                                    {0: 1, 1: 1, 2: 1})["est"], -1.0)
    eq("weights count runs", M.did({0: (10, (1.0, 0.0)), 1: (10, (1.0, 1.0))}, {2: {10: (1.0, 1.0)}},
                                   {0: 3, 1: 1, 2: 1})["est"], -0.75)

    # bootstrap
    mixed = ev_runs + ctl_runs + [mk_run(20, comps=(10,), key=("X", "A", f"n{i}")) for i in range(5)]
    evm, ctlm = M.unit_values(mixed, 3, M.thinking)
    b1 = M.bootstrap(len(mixed), evm, ctlm, b=300)
    b2 = M.bootstrap(len(mixed), evm, ctlm, b=300)
    eq("bootstrap deterministic", b1, b2)
    est = M.did(evm, ctlm, {i: 1 for i in range(len(mixed))})["est"]
    eq("CI contains estimate", b1[0] <= est <= b1[1], True)

    # labels
    eq("label drop", M.label(-0.15, -0.25, -0.05), "THINKING DROPS AFTER COMPACTION")
    eq("label no drop", M.label(-0.02, -0.06, 0.02), "NO MEANINGFUL DROP")
    eq("label increase", M.label(0.05, 0.01, 0.09), "NO MEANINGFUL DROP")
    eq("label unclear wide", M.label(-0.05, -0.15, 0.05), "UNCLEAR")
    eq("label unclear small drop", M.label(-0.08, -0.12, -0.04), "UNCLEAR")
    eq("label unclear CI crosses 0", M.label(-0.12, -0.30, 0.03), "UNCLEAR")
    eq("label not evaluable", M.label(None, None, None), "NOT EVALUABLE")

    # structural checks, end to end, loading
    saved = (M.SETS, M.EXPECTED, M.ROOT)
    try:
        good = [mk_run(20, comps=(10,), key=("X", "A", "g1")), mk_run(20, key=("X", "A", "g2"))]
        led = [x for run in good for x in run.records]
        comps = [x for run in good for x in run.attempts]
        M.SETS, M.EXPECTED = {"X": ""}, {"X": (len(led), len(comps))}
        res = M.structural_checks({"X": (led, comps, good)})
        eq("checks pass", {k: v[0] for k, v in res.items()}, {"V1": True, "V2": True, "V3": True})
        M.EXPECTED = {"X": (len(led) + 1, len(comps))}
        eq("V1 count mismatch", M.structural_checks({"X": (led, comps, good)})["V1"][0], False)
        M.EXPECTED = {"X": (len(led), len(comps))}
        bad = mk_run(20, comps=(10,), key=("X", "A", "g1"))
        bad.calls[10]["n_messages"] = 99
        eq("V3 no drop", M.structural_checks({"X": (led, comps, [bad, good[1]])})["V3"][0], False)
        nosum = mk_run(20, comps=(10,), key=("X", "A", "g1"))
        nosum.records = [x for x in nosum.records if x.get("has_tools")]
        eq("V2 missing summary", M.structural_checks({"X": (led, comps, [nosum, good[1]])})["V2"][0], False)

        runs = ([mk_run(20, comps=(10,), think=drop, key=("X", "A", f"e{i}")) for i in range(30)]
                + [mk_run(20, key=("X", "A", f"c{i}")) for i in range(30)])
        out = M.analyze({"X": ([], [], runs)}, b=200)
        eq("end to end drop label", out["label"], "THINKING DROPS AFTER COMPACTION")
        eq("event study rows", len(out["event_study"]), len(M.OFFSETS))
        eq("event study offset 0", out["event_study"][5]["events_thinking_rate"], 0.0)
        eq("mechanism after", out["mechanism_k3"]["first_call_after"]["mean_hist_assistant"], 3.0)
        runs0 = ([mk_run(20, comps=(10,), key=("X", "A", f"e{i}")) for i in range(30)]
                 + [mk_run(20, key=("X", "A", f"c{i}")) for i in range(30)])
        eq("end to end null label", M.analyze({"X": ([], [], runs0)}, b=200)["label"], "NO MEANINGFUL DROP")
        eq("table renders", M.table(out).startswith("# Compaction-thinking analysis"), True)

        with tempfile.TemporaryDirectory() as td:
            M.ROOT = Path(td)
            (M.ROOT / "d").mkdir()
            (M.ROOT / "d" / "think_ledger.jsonl").write_text(json.dumps(
                {"arm": "A", "task": "t", "t0": 1, "t1": 2, "has_tools": True, "finish_reason": "stop",
                 "n_messages": 2, "hist_assistant": 0, "hist_with_reasoning": 0, "reasoning_chars": 5,
                 "reasoning_text": "x", "hist_reasoning_chars": 0}) + "\n", encoding="utf-8")
            (M.ROOT / "d" / "compactions.jsonl").write_text("", encoding="utf-8")
            led_s, _, runs_s = M.load("X", "d", strip=True)
            eq("strip removes reasoning fields", any(f in led_s[0] for f in M.REASONING_FIELDS), False)
            led_k, _, _ = M.load("X", "d", strip=False)
            eq("no strip keeps them", led_k[0]["reasoning_chars"], 5)
    finally:
        M.SETS, M.EXPECTED, M.ROOT = saved

    if fails:
        print("FAIL\n" + "\n".join(fails))
        return 1
    print("ALL PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
