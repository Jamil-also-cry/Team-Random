import numpy as np
from scipy.optimize import linprog
from typing import List, Tuple
from models.schemas import (
    HourData,
    BatteryData,
    DirectiveInterpretationItem,
    DirectiveType,
    HourlyPlanItem,
    BatteryAction
)
from .validator import validate_final_schedule


def optimize_campus_energy(
    hours_input: List[HourData],
    battery: BatteryData,
    directives: List[DirectiveInterpretationItem]
) -> Tuple[List[HourlyPlanItem], float, float, float]:
    """
    Formulates and solves the exact 24-hour campus energy schedule via Linear Programming (SciPy linprog HiGHS).
    Decision variables per hour h (0..23):
      - grid[h] >= 0
      - solar_used[h] >= 0
      - charge[h] >= 0
      - discharge[h] >= 0
      - E_after[h] >= 0
    Total variables = 24 * 5 = 120.
    """
    N = 24
    GRID, SOLAR, CHG, DIS, E_AFT = 0, 1, 2, 3, 4
    n_vars_per_hour = 5
    total_vars = N * n_vars_per_hour

    def idx(hour: int, var_type: int) -> int:
        return hour * n_vars_per_hour + var_type

    # 1. Objective: Minimize Sum(grid[h] * tariff[h]) + small regularizer to encourage solar usage & avoid frivolous cycling
    c = np.zeros(total_vars)
    for h in range(N):
        c[idx(h, GRID)] = hours_input[h].tariff_bdt_per_kwh
        c[idx(h, SOLAR)] = -1e-5  # Prefer using solar over curtailment
        c[idx(h, CHG)] = 1e-6    # Tiny penalty to prevent simultaneous zero-sum charge-discharge
        c[idx(h, DIS)] = 1e-6

    # 2. Variable Bounds
    bounds = [(0, None) for _ in range(total_vars)]

    # Compute effective solar and active bounds
    effective_solar = [hours_input[h].solar_kwh for h in range(N)]
    active_min_reserve = [battery.minimum_energy_kwh for _ in range(N)]
    charge_max = [battery.max_charge_kwh_per_hour for _ in range(N)]
    discharge_max = [battery.max_discharge_kwh_per_hour for _ in range(N)]
    grid_max = [None for _ in range(N)]

    for d in directives:
        if not d.applies or not d.structured_adjustment or not d.structured_adjustment.hours:
            continue
        hrs = d.structured_adjustment.hours
        
        if d.directive_type == DirectiveType.SOLAR_REDUCTION and d.structured_adjustment.factor is not None:
            f = d.structured_adjustment.factor
            for h in hrs:
                effective_solar[h] = hours_input[h].solar_kwh * f

        elif d.directive_type == DirectiveType.MINIMUM_BATTERY_RESERVE and d.structured_adjustment.minimum_energy_kwh is not None:
            res = d.structured_adjustment.minimum_energy_kwh
            for h in hrs:
                active_min_reserve[h] = max(active_min_reserve[h], res)

        elif d.directive_type == DirectiveType.NO_CHARGE_WINDOW:
            for h in hrs:
                charge_max[h] = 0.0

        elif d.directive_type == DirectiveType.NO_DISCHARGE_WINDOW:
            for h in hrs:
                discharge_max[h] = 0.0

        elif d.directive_type == DirectiveType.MAX_GRID_WINDOW and d.structured_adjustment.max_grid_kwh is not None:
            cap = d.structured_adjustment.max_grid_kwh
            for h in hrs:
                grid_max[h] = cap if grid_max[h] is None else min(grid_max[h], cap)

    for h in range(N):
        bounds[idx(h, GRID)] = (0.0, grid_max[h])
        bounds[idx(h, SOLAR)] = (0.0, effective_solar[h])
        bounds[idx(h, CHG)] = (0.0, charge_max[h])
        bounds[idx(h, DIS)] = (0.0, discharge_max[h])
        bounds[idx(h, E_AFT)] = (active_min_reserve[h], battery.capacity_kwh)

    # 3. Equality Constraints (A_eq x = b_eq)
    # Equations per hour:
    # 1. Energy balance: grid + solar_used - charge + discharge = demand
    # 2. Battery state transition: E_after[h] - E_after[h-1] - charge[h] + discharge[h] = 0 (E_after[-1] = initial)
    # Plus End-of-day neutrality: E_after[23] = initial_energy_kwh
    n_eq = N * 2 + 1
    A_eq = np.zeros((n_eq, total_vars))
    b_eq = np.zeros(n_eq)

    row = 0
    # Energy balance
    for h in range(N):
        A_eq[row, idx(h, GRID)] = 1.0
        A_eq[row, idx(h, SOLAR)] = 1.0
        A_eq[row, idx(h, CHG)] = -1.0
        A_eq[row, idx(h, DIS)] = 1.0
        b_eq[row] = hours_input[h].demand_kwh
        row += 1

    # Battery transitions
    for h in range(N):
        A_eq[row, idx(h, E_AFT)] = 1.0
        A_eq[row, idx(h, CHG)] = -1.0
        A_eq[row, idx(h, DIS)] = 1.0
        if h == 0:
            b_eq[row] = battery.initial_energy_kwh
        else:
            A_eq[row, idx(h - 1, E_AFT)] = -1.0
            b_eq[row] = 0.0
        row += 1

    # End-of-day battery neutrality
    A_eq[row, idx(23, E_AFT)] = 1.0
    b_eq[row] = battery.initial_energy_kwh
    row += 1

    # 4. Solve LP using HiGHS
    res = linprog(c, A_eq=A_eq, b_eq=b_eq, bounds=bounds, method="highs")
    if not res.success:
        raise RuntimeError(f"Energy schedule optimization failed: {res.message}")

    solution = res.x
    hourly_plan: List[HourlyPlanItem] = []

    for h in range(N):
        g = float(solution[idx(h, GRID)])
        s = float(solution[idx(h, SOLAR)])
        chg = float(solution[idx(h, CHG)])
        dis = float(solution[idx(h, DIS)])
        e_aft = float(solution[idx(h, E_AFT)])

        # Clean numerical noise
        g = max(0.0, g)
        s = max(0.0, min(effective_solar[h], s))
        chg = max(0.0, chg)
        dis = max(0.0, dis)

        # Disambiguate battery action
        net_action = chg - dis
        if net_action > 1e-4:
            action = BatteryAction.CHARGE
            batt_kwh = chg
        elif net_action < -1e-4:
            action = BatteryAction.DISCHARGE
            batt_kwh = dis
        else:
            action = BatteryAction.IDLE
            batt_kwh = 0.0

        hourly_plan.append(
            HourlyPlanItem(
                hour=h,
                grid_kwh=round(g, 2),
                solar_used_kwh=round(s, 2),
                battery_action=action,
                battery_kwh=round(batt_kwh, 2),
                battery_energy_after_kwh=round(e_aft, 2)
            )
        )

    # Independent verification
    validate_final_schedule(hours_input, battery, directives, hourly_plan)

    # Recompute metrics exactly from the final plan
    total_grid = sum(p.grid_kwh for p in hourly_plan)
    total_cost = sum(p.grid_kwh * hours_input[h].tariff_bdt_per_kwh for h, p in enumerate(hourly_plan))
    peak_grid = max(p.grid_kwh for p in hourly_plan)

    return hourly_plan, round(total_grid, 2), round(total_cost, 2), round(peak_grid, 2)