from .directives import interpret_notes

HORIZON = 24
DEFAULT_GRID_PRICE = 12.0
DEFAULT_CAPACITY = 100.0
DEFAULT_INITIAL_SOC = 50.0
DEFAULT_MAX_POWER = 25.0
DEFAULT_MIN_ENERGY = 0.0
EPSILON = 1e-9
ROUND = 4


def _as_float(value, default, minimum=0.0):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return max(number, minimum)


def _number_of(value, default, low, high):
    value = _as_float(value, default)
    return max(low, min(high, value))


def _entry_number(entry, key, default, minimum=0.0):
    if isinstance(entry, dict):
        return _as_float(entry.get(key), default, minimum)
    return default


def _normalize_hours(payload):
    default_price = _as_float(payload.get("grid_price"), DEFAULT_GRID_PRICE)
    hours = []
    raw_hours = payload.get("hours")
    if isinstance(raw_hours, list) and any(
        isinstance(entry, dict) for entry in raw_hours
    ):
        for i in range(HORIZON):
            entry = raw_hours[i] if i < len(raw_hours) else {}
            hours.append(
                {
                    "demand_kwh": _entry_number(entry, "demand_kwh", 0.0),
                    "solar_kwh": _entry_number(entry, "solar_kwh", 0.0),
                    "tariff_bdt_per_kwh": _entry_number(
                        entry, "tariff_bdt_per_kwh", default_price
                    ),
                }
            )
        return hours

    load_profile = payload.get("load_profile") or []
    solar_profile = payload.get("solar_profile") or []
    price_profile = payload.get("grid_price_profile") or []
    for i in range(HORIZON):
        hours.append(
            {
                "demand_kwh": _as_float(
                    load_profile[i] if i < len(load_profile) else 0.0, 0.0
                ),
                "solar_kwh": _as_float(
                    solar_profile[i] if i < len(solar_profile) else 0.0, 0.0
                ),
                "tariff_bdt_per_kwh": _as_float(
                    price_profile[i] if i < len(price_profile) else default_price,
                    default_price,
                ),
            }
        )
    return hours


def _normalize_battery(payload):
    battery = payload.get("battery") or {}
    if "capacity_kwh" in battery:
        capacity = _as_float(battery.get("capacity_kwh"), DEFAULT_CAPACITY, 0.1)
        minimum = _as_float(battery.get("minimum_energy_kwh"), DEFAULT_MIN_ENERGY)
        minimum = min(minimum, capacity)
        initial = _as_float(battery.get("initial_energy_kwh"), capacity / 2)
        initial = max(minimum, min(initial, capacity))
        return {
            "capacity": capacity,
            "initial": initial,
            "minimum": minimum,
            "max_charge": _as_float(
                battery.get("max_charge_kwh_per_hour"), DEFAULT_MAX_POWER
            ),
            "max_discharge": _as_float(
                battery.get("max_discharge_kwh_per_hour"), DEFAULT_MAX_POWER
            ),
        }

    capacity = _as_float(battery.get("capacity"), DEFAULT_CAPACITY, 0.1)
    soc = _as_float(battery.get("soc"), DEFAULT_INITIAL_SOC)
    soc = max(0.0, min(soc, 100.0))
    max_power = _as_float(battery.get("max_power"), DEFAULT_MAX_POWER)
    return {
        "capacity": capacity,
        "initial": capacity * soc / 100.0,
        "minimum": DEFAULT_MIN_ENERGY,
        "max_charge": max_power,
        "max_discharge": max_power,
    }


def _hour_directives(interpretations, hour):
    solar_factor = 1.0
    no_charge = False
    no_discharge = False
    reserve = 0.0
    max_grid = None
    for item in interpretations:
        if not isinstance(item, dict) or not item.get("applies"):
            continue
        adjustment = item.get("structured_adjustment") or {}
        hours = adjustment.get("hours") or []
        if hour not in hours:
            continue
        directive = item.get("directive_type")
        if directive == "solar_reduction":
            solar_factor = _number_of(adjustment.get("factor"), 1.0, 0.0, 1.0)
        elif directive == "no_charge_window":
            no_charge = True
        elif directive == "no_discharge_window":
            no_discharge = True
        elif directive == "minimum_battery_reserve":
            reserve = max(reserve, _as_float(adjustment.get("reserve_kwh"), 0.0))
        elif directive == "max_grid_window":
            max_grid = _as_float(adjustment.get("max_grid_kwh"), 0.0)
    return {
        "solar_factor": solar_factor,
        "no_charge": no_charge,
        "no_discharge": no_discharge,
        "minimum": reserve,
        "max_grid": max_grid,
    }


def _build_hour_directives(interpretations, battery_minimum):
    directives = []
    for h in range(HORIZON):
        base = _hour_directives(interpretations, h)
        base["minimum"] = max(battery_minimum, base["minimum"])
        directives.append(base)
    return directives


def _effective_minimum(directives, h):
    return directives[h]["minimum"]


def _after_array(battery, charge, discharge):
    energy = battery["initial"]
    after = [0.0] * HORIZON
    for h in range(HORIZON):
        energy += charge[h] - discharge[h]
        after[h] = energy
    return after


def _energy_before(battery, charge, discharge, h):
    energy = battery["initial"]
    for i in range(h):
        energy += charge[i] - discharge[i]
    return energy


def _neutrality_add(battery, directives, charge, discharge, grid, grid_topup, tariff, needed):
    candidate = [
        h
        for h in range(HORIZON)
        if not directives[h]["no_charge"]
        and charge[h] < battery["max_charge"]
        and (
            directives[h]["max_grid"] is None
            or grid[h] < directives[h]["max_grid"]
        )
    ]
    candidate.sort(key=lambda h: tariff[h])
    for h in candidate:
        if needed <= EPSILON:
            break
        before = _energy_before(battery, charge, discharge, h)
        headroom = battery["capacity"] - before
        charge_head = battery["max_charge"] - charge[h]
        if directives[h]["max_grid"] is not None:
            slack = directives[h]["max_grid"] - grid[h]
        else:
            slack = float("inf")
        inc = min(needed, headroom, charge_head, max(slack, 0.0))
        if inc <= EPSILON:
            continue
        charge[h] += inc
        grid[h] += inc
        grid_topup[h] += inc
        after = _after_array(battery, charge, discharge)
        valid = all(
            after[i] <= battery["capacity"] + EPSILON
            and after[i] >= directives[i]["minimum"] - EPSILON
            for i in range(HORIZON)
        )
        if not valid:
            charge[h] -= inc
            grid[h] -= inc
            grid_topup[h] -= inc
            continue
        needed -= inc
    return needed


def _neutrality_remove(battery, directives, surplus_charge, grid_topup, charge, discharge, grid, excess):
    candidate = [h for h in range(HORIZON) if grid_topup[h] > 0]
    for h in candidate:
        if excess <= EPSILON:
            break
        dec = min(excess, grid_topup[h])
        if dec <= EPSILON:
            continue
        charge[h] -= dec
        grid[h] -= dec
        grid_topup[h] -= dec
        after = _after_array(battery, charge, discharge)
        valid = all(
            after[i] <= battery["capacity"] + EPSILON
            and after[i] >= directives[i]["minimum"] - EPSILON
            for i in range(HORIZON)
        )
        if not valid:
            charge[h] += dec
            grid[h] += dec
            grid_topup[h] += dec
            continue
        excess -= dec
    for h in sorted(
        [h for h in range(HORIZON) if surplus_charge[h] > 0], reverse=True
    ):
        if excess <= EPSILON:
            break
        dec = min(excess, surplus_charge[h])
        if dec <= EPSILON:
            continue
        charge[h] -= dec
        surplus_charge[h] -= dec
        after = _after_array(battery, charge, discharge)
        valid = all(
            after[i] >= directives[i]["minimum"] - EPSILON
            and after[i] <= battery["capacity"] + EPSILON
            for i in range(HORIZON)
        )
        if not valid:
            charge[h] += dec
            surplus_charge[h] += dec
            continue
        excess -= dec
    return excess


def optimize_energy(payload):
    scenario_id = payload.get("scenario_id", "") or ""
    hours = _normalize_hours(payload)
    battery = _normalize_battery(payload)

    interpretations = payload.get("directive_interpretation")
    if interpretations is None:
        interpretations = interpret_notes(payload.get("operator_notes"))
    interpretations = interpretations or []

    demand = [h["demand_kwh"] for h in hours]
    solar = [h["solar_kwh"] for h in hours]
    tariff = [h["tariff_bdt_per_kwh"] for h in hours]

    directives = _build_hour_directives(interpretations, battery["minimum"])
    effective_solar = [
        solar[h] * directives[h]["solar_factor"] for h in range(HORIZON)
    ]

    avg_tariff = sum(tariff) / HORIZON

    total_want = 0.0
    for h in range(HORIZON):
        if tariff[h] >= avg_tariff and not directives[h]["no_discharge"]:
            leftover = max(demand[h] - effective_solar[h], 0.0)
            total_want += min(leftover, battery["max_discharge"])
    topup_budget = max(
        0.0, total_want - max(0.0, battery["initial"] - battery["minimum"])
    )

    energy = battery["initial"]
    grid = [0.0] * HORIZON
    solar_used = [0.0] * HORIZON
    charge = [0.0] * HORIZON
    surplus_charge = [0.0] * HORIZON
    grid_topup = [0.0] * HORIZON
    discharge = [0.0] * HORIZON

    for h in range(HORIZON):
        price = tariff[h]
        eff_solar = effective_solar[h]
        directive_h = directives[h]

        solar_to_load = min(eff_solar, demand[h])
        solar_used[h] = solar_to_load
        remaining = max(demand[h] - solar_to_load, 0.0)
        surplus = max(eff_solar - solar_to_load, 0.0)

        headroom = battery["capacity"] - energy
        charge_now = 0.0
        if not directive_h["no_charge"] and surplus > 0 and headroom > 0:
            charge_now = min(surplus, battery["max_charge"], headroom)
            energy += charge_now
            headroom -= charge_now
            topup_budget = max(0.0, topup_budget - charge_now)
        charge[h] = charge_now

        disch = 0.0
        if not directive_h["no_discharge"] and remaining > 0 and price >= avg_tariff:
            headroom_down = energy - directive_h["minimum"]
            if headroom_down > 0:
                disch = min(remaining, battery["max_discharge"], headroom_down)
                energy -= disch
                remaining -= disch
        discharge[h] = disch

        cap = directive_h["max_grid"]
        grid[h] = remaining
        if cap is not None and cap >= 0:
            grid[h] = min(remaining, cap)

        top = 0.0
        if (
            not directive_h["no_charge"]
            and price < avg_tariff
            and topup_budget > 0
            and headroom > 0
        ):
            charge_head = battery["max_charge"] - charge[h]
            slack = (
                max(0.0, cap - grid[h]) if cap is not None else float("inf")
            )
            top = min(topup_budget, headroom, charge_head, slack)
            if top > 0:
                energy += top
                grid[h] += top
                charge[h] += top
                grid_topup[h] += top
                topup_budget -= top

        surplus_charge[h] = charge[h] - grid_topup[h]

    battery_after = _after_array(battery, charge, discharge)

    needed = max(0.0, battery["initial"] - battery_after[HORIZON - 1])
    if needed > EPSILON:
        _neutrality_add(
            battery, directives, charge, discharge, grid, grid_topup, tariff, needed
        )
    excess = max(0.0, battery_after[HORIZON - 1] - battery["initial"])
    if excess > EPSILON:
        _neutrality_remove(
            battery,
            directives,
            surplus_charge,
            grid_topup,
            charge,
            discharge,
            grid,
            excess,
        )

    battery_after = _after_array(battery, charge, discharge)

    hourly_plan = []
    for h in range(HORIZON):
        if charge[h] > EPSILON:
            action = "charge"
            moved = charge[h]
        elif discharge[h] > EPSILON:
            action = "discharge"
            moved = discharge[h]
        else:
            action = "idle"
            moved = 0.0
        hourly_plan.append(
            {
                "hour": h,
                "grid_kwh": round(grid[h], ROUND),
                "solar_used_kwh": round(solar_used[h], ROUND),
                "battery_action": action,
                "battery_kwh": round(moved, ROUND),
                "battery_energy_after_kwh": round(battery_after[h], ROUND),
                "demand_kwh": round(demand[h], ROUND),
                "solar_kwh": round(solar[h], ROUND),
                "tariff_bdt_per_kwh": round(tariff[h], ROUND),
                "battery_charge_kwh": round(charge[h], ROUND),
                "grid_charge_kwh": round(grid_topup[h], ROUND),
                "battery_discharge_kwh": round(discharge[h], ROUND),
            }
        )

    summary = {
        "total_grid_kwh": round(sum(grid), ROUND),
        "total_cost_bdt": round(sum(grid[h] * tariff[h] for h in range(HORIZON)), ROUND),
        "peak_grid_kwh": round(max(grid), ROUND),
        "solar_used_total": round(sum(solar_used), ROUND),
        "solar_curtailed_total": round(
            sum(max(solar[h] - effective_solar[h], 0.0) for h in range(HORIZON)),
            ROUND,
        ),
        "battery_charged_total": round(sum(charge), ROUND),
        "battery_discharged_total": round(sum(discharge), ROUND),
        "initial_battery_kwh": round(battery["initial"], ROUND),
        "final_battery_kwh": round(battery_after[HORIZON - 1], ROUND),
        "neutrality_delta_kwh": round(
            battery["initial"] - battery_after[HORIZON - 1], ROUND
        ),
    }

    return {
        "scenario_id": scenario_id,
        "server": "SuryaGrid",
        "directive_interpretation": interpretations,
        "hourly_plan": hourly_plan,
        "summary": summary,
    }