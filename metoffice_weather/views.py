# health/views.py
from django.http import JsonResponse
from django.db import connections
from django.db.utils import OperationalError
from django.core.cache import cache
import sys

def health_check(request):
    """
    Health check endpoint.
    Returns 200 if the app is healthy, otherwise 503.
    """
    status = {
        "status": "healthy",
        "checks": {}
    }
    overall_healthy = True

    try:
        cache.set("health_check_key", "ok", timeout=2)
        if cache.get("health_check_key") == "ok":
            status["checks"]["cache"] = "ok"
        else:
            status["checks"]["cache"] = "error: cache read failed"
            overall_healthy = False
    except Exception as e:
        status["checks"]["cache"] = f"error: {str(e)}"
        overall_healthy = False

    http_status = 200 if overall_healthy else 503
    status["overall"] = "healthy" if overall_healthy else "unhealthy"

    return JsonResponse(status, status=http_status)