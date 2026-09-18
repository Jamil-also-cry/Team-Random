import json

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

from . import optimizer


@csrf_exempt
def optimize_energy_view(request):
    if request.method != "POST":
        return JsonResponse(
            {"error": "Only POST is allowed", "server": "SuryaGrid"},
            status=405,
        )

    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse(
            {"error": "Request body must be valid JSON", "server": "SuryaGrid"},
            status=400,
        )

    if not isinstance(payload, dict):
        return JsonResponse(
            {"error": "Request body must be a JSON object", "server": "SuryaGrid"},
            status=400,
        )

    result = optimizer.optimize_energy(payload)
    return JsonResponse(result)