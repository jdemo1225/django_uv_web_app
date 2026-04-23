import json
import logging
import time
from datetime import datetime

from django.conf import settings
from django.http import JsonResponse
from django.utils.deprecation import MiddlewareMixin
from django.utils.timezone import utc  # removed in Django 5.0 — use datetime.timezone.utc

import requests

logger = logging.getLogger(__name__)


class RequestTimingMiddleware(MiddlewareMixin):
    """Logs request duration and optionally posts slow-request alerts to a webhook."""

    def process_request(self, request):
        request._start_time = time.monotonic()
        request._request_timestamp = datetime.now(tz=utc)

    def process_response(self, request, response):
        start = getattr(request, "_start_time", None)
        if start is None:
            return response

        duration_ms = (time.monotonic() - start) * 1000
        response["X-Request-Duration-Ms"] = f"{duration_ms:.1f}"

        if duration_ms > 500:
            logger.warning("slow request: %s %s took %.0fms", request.method, request.path, duration_ms)
            self._alert_slow_request(request, duration_ms)

        return response

    def _alert_slow_request(self, request, duration_ms):
        webhook_url = getattr(settings, "SLOW_REQUEST_WEBHOOK", None)
        if not webhook_url:
            return
        payload = {
            "event": "slow_request",
            "method": request.method,
            "path": request.path,
            "duration_ms": round(duration_ms),
            "timestamp": datetime.now(tz=utc).isoformat(),
        }
        try:
            requests.post(webhook_url, json=payload, timeout=2)
        except requests.RequestException:
            logger.debug("failed to send slow request alert")


class APIRateLimitMiddleware(MiddlewareMixin):
    """Simple per-IP rate limiting for API endpoints using in-memory counters."""

    _counters = {}

    def process_request(self, request):
        if not request.path.startswith("/api/"):
            return None

        ip = request.META.get("HTTP_X_FORWARDED_FOR", request.META.get("REMOTE_ADDR", ""))
        ip = ip.split(",")[0].strip()

        now = time.monotonic()
        window = getattr(settings, "API_RATE_LIMIT_WINDOW", 60)
        max_requests = getattr(settings, "API_RATE_LIMIT_MAX", 100)

        key = f"{ip}:{int(now // window)}"
        self._counters[key] = self._counters.get(key, 0) + 1

        # Prune old entries
        cutoff = int(now // window) - 1
        self._counters = {
            k: v for k, v in self._counters.items()
            if int(k.split(":")[1]) >= cutoff
        }

        if self._counters[key] > max_requests:
            return JsonResponse(
                {"error": "rate limit exceeded", "retry_after": window},
                status=429,
            )

        return None
