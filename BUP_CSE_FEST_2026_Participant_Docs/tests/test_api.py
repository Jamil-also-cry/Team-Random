"""
Django-based test suite for GridWise.

Re-uses the existing logic in optimizer/solver.py and optimizer/validator.py
unchanged. The HTTP layer is exercised via Django's test client instead of
FastAPI's ASGITransport so the suite works with pytest-django.
"""
import json
import os

import pytest
from django.test import Client

from models.schemas import BatteryData, HourData
from optimizer.solver import optimize_campus_energy
from optimizer.validator import (
    validate_and_guardrail_directive,
    validate_final_schedule,
)


PUBLIC_CASES_PATH = os.path.join(os.path.dirname(__file__), "public_cases.json")


def load_public_cases():
    if not os.path.exists(PUBLIC_CASES_PATH):
        return []
    with open(PUBLIC_CASES_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("cases", [])


# ---------- HTTP layer (Django test client) ----------

@pytest.mark.django_db
def test_health_endpoint():
    client = Client()
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.django_db
def test_optimize_energy_bad_payload_returns_400():
    client = Client()
    response = client.post(
        "/optimize-energy",
        data=json.dumps({"scenario_id": "bad"}),
        content_type="application/json",
    )
    assert response.status_code == 400


# ---------- Optimizer-level coverage (logic parity with FastAPI tests) ----------

def test_all_public_sample_cases_optimizer():
    """Verifies optimizer feasibility and correctness across all public cases."""
    cases = load_public_cases()
    assert len(cases) >= 1, "Public cases JSON should load."

    for case in cases:
        inp = case["input"]
        exp = case["expected_output"]

        battery = BatteryData(**inp["battery"])
        hours = [HourData(**h) for h in inp["hours"]]

        directives = [
            validate_and_guardrail_directive(d, i, battery)
            for i, d in enumerate(exp["directive_interpretation"])
        ]

        plan, total_grid, total_cost, peak_grid = optimize_campus_energy(
            hours, battery, directives
        )

        validate_final_schedule(hours, battery, directives, plan)

        exp_cost = exp["total_cost_bdt"]
        assert abs(total_cost - exp_cost) <= 2.0, (
            f"Case {case['id']} cost deviation: computed {total_cost}, expected {exp_cost}"
        )


def test_guardrail_rejections():
    battery = BatteryData(
        capacity_kwh=200,
        initial_energy_kwh=100,
        minimum_energy_kwh=30,
        max_charge_kwh_per_hour=50,
        max_discharge_kwh_per_hour=50,
    )

    # 1. Invalid directive type
    bad_type = {"directive_type": "alien_laser_mode", "hours": [12]}
    res1 = validate_and_guardrail_directive(bad_type, 0, battery)
    assert res1.directive_type.value == "no_op"
    assert res1.applies is False

    # 2. Hours out of bounds
    bad_hours = {
        "directive_type": "no_charge_window",
        "structured_adjustment": {"hours": [-5, 24, 99]},
    }
    res2 = validate_and_guardrail_directive(bad_hours, 1, battery)
    assert res2.directive_type.value == "no_op"

    # 3. Solar factor out of range clamp
    solar_bad = {
        "directive_type": "solar_reduction",
        "structured_adjustment": {"hours": [12, 13], "factor": 2.5},
    }
    res3 = validate_and_guardrail_directive(solar_bad, 2, battery)
    assert res3.directive_type.value == "solar_reduction"
    assert res3.structured_adjustment.factor == 1.0