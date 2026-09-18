"""
Standalone probe (no Django / no pytest) that runs the optimizer over the 10
public sample cases and compares results to the reference expected_output.

This intentionally mirrors what tests/test_api.py::test_all_public_sample_cases_optimizer
already does at the optimizer level (skipping the LLM by feeding the reference
directive_interpretation directly through the guardrail), and adds deeper
diff diagnostics.
"""
from __future__ import annotations

import json
import os
import sys
import time
import traceback
from typing import Any, Dict, List, Tuple

HERE = os.path.dirname(os.path.abspath(__file__))
PUBLIC_CASES_PATH = os.path.join(HERE, "tests", "public_cases.json")

# Ensure project importable
sys.path.insert(0, HERE)

from models.schemas import BatteryData, HourData
from optimizer.solver import optimize_campus_energy
from optimizer.validator import (
    validate_and_guardrail_directive,
    validate_final_schedule,
)

TOL_COST = 2.0          # matches in-repo test
TOL_GRID = 0.05         # energy/numeric tolerance
TOL_TOTAL_GRID = 0.05
TOL_PEAK = 0.05


def load_cases() -> List[Dict[str, Any]]:
    with open(PUBLIC_CASES_PATH, "r", encoding="utf-8") as f:
        return json.load(f).get("cases", [])


def hour_diff(got: Dict[str, Any], ref: Dict[str, Any]) -> Dict[str, float]:
    """Compute per-hour absolute differences."""
    return {
        "hour": got["hour"],
        "grid_kwh": round(got["grid_kwh"] - ref["grid_kwh"], 4),
        "solar_used_kwh": round(got["solar_used_kwh"] - ref["solar_used_kwh"], 4),
        "battery_kwh": round(got["battery_kwh"] - ref["battery_kwh"], 4),
        "battery_energy_after_kwh": round(
            got["battery_energy_after_kwh"] - ref["battery_energy_after_kwh"], 4
        ),
        "battery_action_eq": got["battery_action"] == ref["battery_action"],
    }


def summarize_case(case: Dict[str, Any], got_metrics: Tuple[float, float, float],
                   plan: List[Dict[str, Any]], err: str | None) -> Dict[str, Any]:
    exp = case["expected_output"]
    total_grid, total_cost, peak_grid = got_metrics
    return {
        "id": case["id"],
        "label": case.get("label", ""),
        "expected": {
            "total_grid_kwh": exp["total_grid_kwh"],
            "total_cost_bdt": exp["total_cost_bdt"],
            "peak_grid_kwh": exp["peak_grid_kwh"],
        },
        "got": {
            "total_grid_kwh": round(total_grid, 2),
            "total_cost_bdt": round(total_cost, 2),
            "peak_grid_kwh": round(peak_grid, 2),
        },
        "diffs": {
            "total_grid_kwh": round(total_grid - exp["total_grid_kwh"], 4),
            "total_cost_bdt": round(total_cost - exp["total_cost_bdt"], 4),
            "peak_grid_kwh": round(peak_grid - exp["peak_grid_kwh"], 4),
        },
        "hour_count_got": len(plan),
        "hour_count_ref": len(exp["hourly_plan"]),
        "error": err,
    }


def run_case(case: Dict[str, Any]) -> Dict[str, Any]:
    inp = case["input"]
    exp = case["expected_output"]

    battery = BatteryData(**inp["battery"])
    hours = [HourData(**h) for h in inp["hours"]]

    # Use the reference directive_interpretation -> guardrail (same as the in-repo test).
    directives = [
        validate_and_guardrail_directive(d, i, battery)
        for i, d in enumerate(exp["directive_interpretation"])
    ]

    t0 = time.perf_counter()
    try:
        plan, total_grid, total_cost, peak_grid = optimize_campus_energy(
            hours, battery, directives
        )
        validate_final_schedule(hours, battery, directives, plan)
        elapsed_ms = (time.perf_counter() - t0) * 1000
        err = None
    except Exception as exc:  # pragma: no cover - diagnostic
        elapsed_ms = (time.perf_counter() - t0) * 1000
        return {
            "id": case["id"],
            "label": case.get("label", ""),
            "expected": {},
            "got": {},
            "diffs": {},
            "hour_count_got": 0,
            "hour_count_ref": 0,
            "error": f"{type(exc).__name__}: {exc}",
            "trace": traceback.format_exc(limit=4),
            "elapsed_ms": round(elapsed_ms, 2),
        }

    summary = summarize_case(case, (total_grid, total_cost, peak_grid),
                             [p.model_dump() for p in plan], None)
    summary["elapsed_ms"] = round(elapsed_ms, 2)
    summary["plan_dump"] = [p.model_dump() for p in plan]

    cost_ok = abs(total_cost - exp["total_cost_bdt"]) <= TOL_COST
    grid_ok = abs(total_grid - exp["total_grid_kwh"]) <= TOL_TOTAL_GRID
    peak_ok = abs(peak_grid - exp["peak_grid_kwh"]) <= TOL_PEAK
    summary["pass"] = cost_ok and grid_ok and peak_ok and err is None

    # per-hour diff stats
    ref_plan = exp["hourly_plan"]
    diffs = [hour_diff(p.model_dump(), r) for p, r in zip(plan, ref_plan)]
    summary["hour_diffs"] = diffs
    summary["hour_diffs_max_abs"] = {
        "grid_kwh": max(abs(d["grid_kwh"]) for d in diffs),
        "solar_used_kwh": max(abs(d["solar_used_kwh"]) for d in diffs),
        "battery_kwh": max(abs(d["battery_kwh"]) for d in diffs),
        "battery_energy_after_kwh": max(
            abs(d["battery_energy_after_kwh"]) for d in diffs
        ),
    }
    summary["hour_diffs_action_matches"] = all(d["battery_action_eq"] for d in diffs)
    return summary


def main() -> int:
    cases = load_cases()
    print(f"Loaded {len(cases)} public cases from {PUBLIC_CASES_PATH}\n")

    all_pass = True
    summaries: List[Dict[str, Any]] = []
    for c in cases:
        s = run_case(c)
        summaries.append(s)
        status = "PASS" if s.get("pass") and not s.get("error") else "FAIL"
        if not (s.get("pass") and not s.get("error")):
            all_pass = False
        print(f"[{status}] {s['id']:<10} {s.get('label','')} "
              f"({s.get('elapsed_ms',0):.1f} ms)")
        if "diffs" in s and s["diffs"]:
            d = s["diffs"]
            e = s["expected"]; g = s["got"]
            print(f"           expected grid={e['total_grid_kwh']}  "
                  f"cost={e['total_cost_bdt']}  peak={e['peak_grid_kwh']}")
            print(f"           got       grid={g['total_grid_kwh']}  "
                  f"cost={g['total_cost_bdt']}  peak={g['peak_grid_kwh']}")
            print(f"           diffs     d_grid={d['total_grid_kwh']:+}  "
                  f"d_cost={d['total_cost_bdt']:+}  d_peak={d['peak_grid_kwh']:+}")
            if "hour_diffs_max_abs" in s:
                hm = s["hour_diffs_max_abs"]
                print(f"           max|hour-diff| "
                      f"grid={hm['grid_kwh']}  "
                      f"solar={hm['solar_used_kwh']}  "
                      f"batt={hm['battery_kwh']}  "
                      f"soc={hm['battery_energy_after_kwh']}  "
                      f"actions_match={s['hour_diffs_action_matches']}")
        if s.get("error"):
            print(f"           ERROR: {s['error']}")

    out_path = os.path.join(HERE, "_public_cases_report.json")
    # Drop bulky plan_dump from saved report (keeps diffs).
    compact = []
    for s in summaries:
        s2 = {k: v for k, v in s.items() if k != "plan_dump" and k != "trace"}
        compact.append(s2)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(compact, f, indent=2)
    print(f"\nReport: {out_path}")
    print(f"Overall: {'ALL PASS' if all_pass else 'FAILURES PRESENT'}")
    return 0 if all_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
