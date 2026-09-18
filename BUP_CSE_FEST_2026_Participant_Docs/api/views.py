"""
Django REST Framework views wrapping the GridWise pipeline.

The business logic from the previous FastAPI implementation is reused unchanged:
  - llm.interpreter.interpret_operator_notes  (Phase 1 + 2)
  - optimizer.solver.optimize_campus_energy    (Phase 3)
  - optimizer.validator.validate_final_schedule
  - utils.helpers.build_plan_summary           (Phase 4)
"""
import asyncio
import logging

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from models.schemas import OptimizeRequest, OptimizeResponse
from llm.interpreter import interpret_operator_notes
from optimizer.solver import optimize_campus_energy
from utils.helpers import build_plan_summary

from .serializers import OptimizeRequestSerializer

logger = logging.getLogger(__name__)


def _run_async(coro):
    """Run an async coroutine from a synchronous DRF view safely."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            return asyncio.run(coro)
        return loop.run_until_complete(coro)
    except RuntimeError:
        return asyncio.run(coro)


class HealthView(APIView):
    """Readiness endpoint for the judging harness."""

    def get(self, request):
        return Response({"status": "ok"}, status=status.HTTP_200_OK)


class OptimizeEnergyView(APIView):
    """
    POST /optimize-energy

    1. LLM parses operator notes into structured directives.
    2. Deterministic guardrails validate boundaries, types, and constraints.
    3. SciPy HiGHS LP optimizer finds the cost-minimal 24h schedule.
    4. Post-optimizer validator verifies 100% constraint satisfaction.
    """

    def post(self, request):
        serializer = OptimizeRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {"detail": f"Semantic constraint violation: {serializer.errors}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        data = serializer.validated_data

        try:
            payload = OptimizeRequest.model_validate(data)
        except ValueError as ve:
            return Response(
                {"detail": f"Semantic constraint violation: {ve}"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as exc:
            logger.exception("Failed to construct OptimizeRequest")
            return Response(
                {"detail": f"Invalid request payload: {exc}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            # Phase 1 & 2: LLM Interpretation & Guardrail Validation
            directives = _run_async(
                interpret_operator_notes(payload.operator_notes, payload.battery)
            )

            # Phase 3: Energy Optimization
            plan, total_grid, total_cost, peak_grid = optimize_campus_energy(
                hours_input=payload.hours,
                battery=payload.battery,
                directives=directives,
            )

            # Phase 4: Strategy Summary
            summary = build_plan_summary(directives, plan, total_cost)

            response = OptimizeResponse(
                scenario_id=payload.scenario_id,
                directive_interpretation=directives,
                hourly_plan=plan,
                total_grid_kwh=total_grid,
                total_cost_bdt=total_cost,
                peak_grid_kwh=peak_grid,
                plan_summary=summary,
            )
            return Response(response.model_dump(), status=status.HTTP_200_OK)

        except ValueError as ve:
            return Response(
                {"detail": f"Semantic constraint violation: {ve}"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception:
            logger.exception("Controlled internal failure during energy scheduling")
            return Response(
                {"detail": "Controlled internal failure during energy scheduling."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
