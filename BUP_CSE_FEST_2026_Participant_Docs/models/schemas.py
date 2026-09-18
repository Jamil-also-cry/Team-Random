from typing import List, Optional, Union
from enum import Enum
from pydantic import BaseModel, Field, field_validator


class DirectiveType(str, Enum):
    SOLAR_REDUCTION = "solar_reduction"
    MINIMUM_BATTERY_RESERVE = "minimum_battery_reserve"
    NO_CHARGE_WINDOW = "no_charge_window"
    NO_DISCHARGE_WINDOW = "no_discharge_window"
    MAX_GRID_WINDOW = "max_grid_window"
    NO_OP = "no_op"


class BatteryAction(str, Enum):
    CHARGE = "charge"
    DISCHARGE = "discharge"
    IDLE = "idle"


class HourData(BaseModel):
    hour: int = Field(..., ge=0, le=23, description="Unique hour integer from 0 to 23")
    demand_kwh: float = Field(..., ge=0.0, description="Campus demand in kWh")
    solar_kwh: float = Field(..., ge=0.0, description="Base solar generation available in kWh")
    tariff_bdt_per_kwh: float = Field(..., ge=0.0, description="Grid tariff in BDT per kWh")


class BatteryData(BaseModel):
    capacity_kwh: float = Field(..., gt=0.0, description="Maximum energy capacity")
    initial_energy_kwh: float = Field(..., ge=0.0, description="Starting energy level at hour 0")
    minimum_energy_kwh: float = Field(..., ge=0.0, description="Base minimum reserve level")
    max_charge_kwh_per_hour: float = Field(..., ge=0.0, description="Maximum charge rate per hour")
    max_discharge_kwh_per_hour: float = Field(..., ge=0.0, description="Maximum discharge rate per hour")


class OptimizeRequest(BaseModel):
    scenario_id: str = Field(..., min_length=1, description="Unique synthetic scenario identifier")
    operator_notes: List[str] = Field(..., min_length=1, max_length=3, description="1 to 3 operator notes")
    hours: List[HourData] = Field(..., min_length=24, max_length=24, description="Exactly 24 hourly data entries")
    battery: BatteryData = Field(..., description="Battery parameters")

    @field_validator("hours")
    @classmethod
    def validate_hours_sequence(cls, v: List[HourData]) -> List[HourData]:
        extracted = [h.hour for h in v]
        if extracted != list(range(24)):
            raise ValueError("hours array must contain exactly 24 entries with hours ordered 0 through 23")
        return v


class DirectiveAdjustment(BaseModel):
    hours: Optional[List[int]] = None
    factor: Optional[float] = None
    minimum_energy_kwh: Optional[float] = None
    max_grid_kwh: Optional[float] = None


class DirectiveInterpretationItem(BaseModel):
    note_index: int = Field(..., ge=0, description="Index of the operator note")
    applies: bool = Field(..., description="True if directive applies, False only for no_op")
    directive_type: DirectiveType = Field(..., description="Recognized directive type")
    structured_adjustment: Optional[DirectiveAdjustment] = Field(
        default=None, description="Adjustment payload, null for no_op"
    )
    explanation: str = Field(..., min_length=1, description="Brief explanation of the interpretation")


class HourlyPlanItem(BaseModel):
    hour: int = Field(..., ge=0, le=23)
    grid_kwh: float = Field(..., ge=0.0)
    solar_used_kwh: float = Field(..., ge=0.0)
    battery_action: BatteryAction
    battery_kwh: float = Field(..., ge=0.0)
    battery_energy_after_kwh: float = Field(..., ge=0.0)


class OptimizeResponse(BaseModel):
    scenario_id: str
    directive_interpretation: List[DirectiveInterpretationItem]
    hourly_plan: List[HourlyPlanItem]
    total_grid_kwh: float
    total_cost_bdt: float
    peak_grid_kwh: float
    plan_summary: str


class HealthResponse(BaseModel):
    status: str = "ok"