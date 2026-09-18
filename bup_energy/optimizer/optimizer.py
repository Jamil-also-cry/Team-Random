DEFAULT_CAPACITY = 100.0
DEFAULT_SOC = 50.0
DEFAULT_MAX_POWER = 25.0
DEFAULT_EFFICIENCY = 0.9
DEFAULT_GRID_PRICE = 12.0
DEFAULT_HORIZON = 24


def _as_float(value, default, minimum=0.0):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return max(number, minimum)


def _as_list(value, length, default):
    result = []
    for i in range(length):
        item = value[i] if isinstance(value, list) and i < len(value) else default
        result.append(_as_float(item, default))
    return result


def _list_length(value, default):
    if isinstance(value, list):
        return len(value)
    return default


def optimize_energy(payload):
    grid_price_value = _as_float(payload.get("grid_price"), DEFAULT_GRID_PRICE)
    horizon = max(
        _list_length(payload.get("grid_price_profile"), DEFAULT_HORIZON),
        _list_length(payload.get("solar_profile"), DEFAULT_HORIZON),
        _list_length(payload.get("load_profile"), DEFAULT_HORIZON),
    )
    grid_price_profile = _as_list(
        payload.get("grid_price_profile"), horizon, grid_price_value
    )
    solar_profile = _as_list(payload.get("solar_profile"), horizon, 0.0)
    load_profile = _as_list(payload.get("load_profile"), horizon, 0.0)

    battery = payload.get("battery") or {}
    capacity = _as_float(battery.get("capacity"), DEFAULT_CAPACITY, 0.1)
    soc = _as_float(battery.get("soc"), DEFAULT_SOC, 0.0)
    soc = min(soc, 100.0)
    max_power = _as_float(battery.get("max_power"), DEFAULT_MAX_POWER)
    efficiency = _as_float(battery.get("efficiency"), DEFAULT_EFFICIENCY)
    efficiency = max(min(efficiency, 1.0), 0.1)

    horizon = max(
        len(grid_price_profile), len(solar_profile), len(load_profile)
    )

    energy = capacity * soc / 100.0
    charge_threshold = grid_price_value / efficiency

    schedule = []
    discharged_total = 0.0
    charged_total = 0.0
    solar_used = 0.0
    solar_exported = 0.0
    grid_import = 0.0
    total_cost = 0.0

    for price, solar, load in zip(
        grid_price_profile, solar_profile, load_profile
    ):
        step = {
            "price": round(price, 4),
            "demand": round(load, 4),
            "solar": round(solar, 4),
        }
        step["solar_to_load"] = round(min(solar, load), 4)
        solar_to_load = step["solar_to_load"]
        solar_used += solar_to_load
        remaining_demand = max(load - solar_to_load, 0.0)
        surplus_solar = max(solar - solar_to_load, 0.0)
        space = capacity - energy
        charge_limit = min(max_power, space)
        battery_charge = min(surplus_solar, charge_limit)
        if battery_charge > 0:
            energy += battery_charge
            charged_total += battery_charge
            space -= battery_charge
            charge_limit = min(max_power, space)
        surplus_solar -= battery_charge
        solar_exported += surplus_solar

        discharge_limit = min(max_power, energy)
        battery_discharge = 0.0
        if remaining_demand > 0 and price > charge_threshold:
            battery_discharge = min(remaining_demand, discharge_limit)
            energy -= battery_discharge
            discharged_total += battery_discharge
            remaining_demand -= battery_discharge

        grid = remaining_demand
        if grid > 0:
            grid_import += grid
            total_cost += grid * price

        step["battery_charge"] = round(battery_charge, 4)
        step["battery_discharge"] = round(battery_discharge, 4)
        step["grid"] = round(grid, 4)
        step["battery_soc"] = round(energy / capacity * 100, 2)
        schedule.append(step)

    return {
        "server": "SuryaGrid",
        "horizon_hours": horizon,
        "summary": {
            "total_demand": round(sum(load_profile), 4),
            "total_solar": round(sum(solar_profile), 4),
            "solar_used": round(solar_used, 4),
            "solar_exported": round(solar_exported, 4),
            "battery_charged": round(charged_total, 4),
            "battery_discharged": round(discharged_total, 4),
            "grid_import": round(grid_import, 4),
            "total_cost": round(total_cost, 4),
            "final_battery_soc": round(energy / capacity * 100, 2),
        },
        "schedule": schedule,
    }