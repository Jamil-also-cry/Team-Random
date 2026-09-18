from typing import Dict, Any, List
from models.schemas import (
    BatteryData,
    DirectiveInterpretationItem,
    DirectiveType,
    DirectiveAdjustment,
    HourlyPlanItem,
    HourData,
    BatteryAction
)


def validate_and_guardrail_directive(
    raw: Dict[str, Any],
    expected_index: int,
    battery: BatteryData
) -> DirectiveInterpretationItem:
    """
    Rigorous deterministic guardrail that validates LLM extraction:
    - Verifies allowed directive enum
    - Validates start-inclusive, end-exclusive 0-23 hours
    - Validates factor between 0.0 and 1.0
    - Enforces applies == False <=> directive_type == 'no_op'
    - Clamps reserve to capacity
    """
    raw_type_str = str(raw.get("directive_type", "no_op")).lower().strip()
    explanation = str(raw.get("explanation", "Processed directive."))

    # Check if known type
    try:
        d_type = DirectiveType(raw_type_str)
    except ValueError:
        return DirectiveInterpretationItem(
            note_index=expected_index,
            applies=False,
            directive_type=DirectiveType.NO_OP,
            structured_adjustment=None,
            explanation="Unrecognized directive type mapped to no_op."
        )

    if d_type == DirectiveType.NO_OP:
        return DirectiveInterpretationItem(
            note_index=expected_index,
            applies=False,
            directive_type=DirectiveType.NO_OP,
            structured_adjustment=None,
            explanation=explanation
        )

    adj_raw = raw.get("structured_adjustment")
    if not isinstance(adj_raw, dict):
        return DirectiveInterpretationItem(
            note_index=expected_index,
            applies=False,
            directive_type=DirectiveType.NO_OP,
            structured_adjustment=None,
            explanation="Missing adjustment payload for active directive; converted to no_op."
        )

    raw_hours = adj_raw.get("hours", [])
    if not isinstance(raw_hours, list):
        raw_hours = []

    # Filter and validate hours
    clean_hours: List[int] = []
    for h in raw_hours:
        try:
            h_int = int(h)
            if 0 <= h_int <= 23:
                clean_hours.append(h_int)
        except (ValueError, TypeError):
            pass
    clean_hours = sorted(list(set(clean_hours)))

    if not clean_hours:
        return DirectiveInterpretationItem(
            note_index=expected_index,
            applies=False,
            directive_type=DirectiveType.NO_OP,
            structured_adjustment=None,
            explanation="No valid hours specified; defaulted to no_op."
        )

    adjustment = DirectiveAdjustment(hours=clean_hours)

    if d_type == DirectiveType.SOLAR_REDUCTION:
        factor = adj_raw.get("factor")
        try:
            factor_val = float(factor)
            factor_val = max(0.0, min(1.0, factor_val))
        except (ValueError, TypeError):
            factor_val = 1.0
        adjustment.factor = round(factor_val, 4)

    elif d_type == DirectiveType.MINIMUM_BATTERY_RESERVE:
        min_e = adj_raw.get("minimum_energy_kwh")
        try:
            min_e_val = float(min_e)
            min_e_val = max(0.0, min(battery.capacity_kwh, min_e_val))
        except (ValueError, TypeError):
            min_e_val = battery.minimum_energy_kwh
        adjustment.minimum_energy_kwh = round(min_e_val, 2)

    elif d_type == DirectiveType.MAX_GRID_WINDOW:
        max_g = adj_raw.get("max_grid_kwh")
        try:
            max_g_val = float(max_g)
            max_g_val = max(0.0, max_g_val)
        except (ValueError, TypeError):
            max_g_val = 1000.0
        adjustment.max_grid_kwh = round(max_g_val, 2)

    return DirectiveInterpretationItem(
        note_index=expected_index,
        applies=True,
        directive_type=d_type,
        structured_adjustment=adjustment,
        explanation=explanation
    )


def validate_final_schedule(
    hours_input: List[HourData],
    battery: BatteryData,
    directives: List[DirectiveInterpretationItem],
    plan: List[HourlyPlanItem],
    tolerance: float = 0.05
) -> None:
    """
    Independent replay validator verifying:
    - 24 hours (0..23)
    - Effective solar curtailment/reduction
    - Energy balance
    - Battery capacity & reserve limits
    - Charging & discharging rate limits
    - End-of-day battery neutrality
    """
    if len(plan) != 24:
        raise ValueError(f"Plan must have exactly 24 hours, received {len(plan)}")

    # Precalculate effective solar and limits per hour
    effective_solar = [h.solar_kwh for h in hours_input]
    active_min_reserve = [battery.minimum_energy_kwh for _ in range(24)]
    charge_forbidden = [False] * 24
    discharge_forbidden = [False] * 24
    grid_caps = [None] * 24

    for d in directives:
        if not d.applies or not d.structured_adjustment or not d.structured_adjustment.hours:
            continue
        hrs = d.structured_adjustment.hours
        
        if d.directive_type == DirectiveType.SOLAR_REDUCTION and d.structured_adjustment.factor is not None:
            f = d.structured_adjustment.factor
            for hr in hrs:
                effective_solar[hr] = hours_input[hr].solar_kwh * f

        elif d.directive_type == DirectiveType.MINIMUM_BATTERY_RESERVE and d.structured_adjustment.minimum_energy_kwh is not None:
            res = d.structured_adjustment.minimum_energy_kwh
            for hr in hrs:
                active_min_reserve[hr] = max(active_min_reserve[hr], res)

        elif d.directive_type == DirectiveType.NO_CHARGE_WINDOW:
            for hr in hrs:
                charge_forbidden[hr] = True

        elif d.directive_type == DirectiveType.NO_DISCHARGE_WINDOW:
            for hr in hrs:
                discharge_forbidden[hr] = True

        elif d.directive_type == DirectiveType.MAX_GRID_WINDOW and d.structured_adjustment.max_grid_kwh is not None:
            cap = d.structured_adjustment.max_grid_kwh
            for hr in hrs:
                grid_caps[hr] = cap if grid_caps[hr] is None else min(grid_caps[hr], cap)

    current_soc = battery.initial_energy_kwh

    for hr in range(24):
        p = plan[hr]
        inp = hours_input[hr]

        if p.hour != hr:
            raise ValueError(f"Hour mismatch at index {hr}: expected {hr}, got {p.hour}")

        if p.solar_used_kwh > effective_solar[hr] + tolerance:
            raise ValueError(f"Hour {hr}: Solar used {p.solar_used_kwh} exceeds effective solar {effective_solar[hr]}")

        if grid_caps[hr] is not None and p.grid_kwh > grid_caps[hr] + tolerance:
            raise ValueError(f"Hour {hr}: Grid {p.grid_kwh} exceeds directive cap {grid_caps[hr]}")

        # Action consistency
        if p.battery_action == BatteryAction.CHARGE:
            if charge_forbidden[hr] and p.battery_kwh > tolerance:
                raise ValueError(f"Hour {hr}: Charge action attempted during no_charge_window")
            if p.battery_kwh > battery.max_charge_kwh_per_hour + tolerance:
                raise ValueError(f"Hour {hr}: Charge {p.battery_kwh} exceeds max charge rate {battery.max_charge_kwh_per_hour}")
            expected_after = current_soc + p.battery_kwh
            supplied_from_batt = 0.0
            added_to_batt = p.battery_kwh

        elif p.battery_action == BatteryAction.DISCHARGE:
            if discharge_forbidden[hr] and p.battery_kwh > tolerance:
                raise ValueError(f"Hour {hr}: Discharge action attempted during no_discharge_window")
            if p.battery_kwh > battery.max_discharge_kwh_per_hour + tolerance:
                raise ValueError(f"Hour {hr}: Discharge {p.battery_kwh} exceeds max discharge rate {battery.max_discharge_kwh_per_hour}")
            expected_after = current_soc - p.battery_kwh
            supplied_from_batt = p.battery_kwh
            added_to_batt = 0.0

        else:  # IDLE
            if p.battery_kwh > tolerance:
                raise ValueError(f"Hour {hr}: Idle action must have 0 battery_kwh, got {p.battery_kwh}")
            expected_after = current_soc
            supplied_from_batt = 0.0
            added_to_batt = 0.0

        # State transitions
        if abs(p.battery_energy_after_kwh - expected_after) > tolerance:
            raise ValueError(f"Hour {hr}: Battery energy transition error. Got {p.battery_energy_after_kwh}, expected {expected_after}")

        if p.battery_energy_after_kwh > battery.capacity_kwh + tolerance:
            raise ValueError(f"Hour {hr}: Battery energy exceeds capacity {battery.capacity_kwh}")

        if p.battery_energy_after_kwh < active_min_reserve[hr] - tolerance:
            raise ValueError(f"Hour {hr}: Battery energy below minimum reserve {active_min_reserve[hr]}")

        # Energy balance: grid + solar_used + discharge = demand + charge
        lhs = p.grid_kwh + p.solar_used_kwh + supplied_from_batt
        rhs = inp.demand_kwh + added_to_batt
        if abs(lhs - rhs) > tolerance:
            raise ValueError(f"Hour {hr}: Energy balance violated: LHS={lhs} != RHS={rhs}")

        current_soc = p.battery_energy_after_kwh

    # End of day neutrality
    if abs(current_soc - battery.initial_energy_kwh) > tolerance:
        raise ValueError(f"End-of-day battery neutrality failed: final {current_soc} != initial {battery.initial_energy_kwh}")