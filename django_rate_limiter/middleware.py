import redis
from django.conf import settings
from django.http import JsonResponse


class RateLimiterMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        self.max_requests = getattr(settings, "RATE_LIMITER_MAX_REQUESTS", 5)
        self.window_seconds = getattr(settings, "RATE_LIMITER_WINDOW_SECONDS", 6)
        self.redis_client = redis.Redis(
            host=getattr(settings, "REDIS_HOST", "localhost"),
            port=getattr(settings, "REDIS_PORT", 6379),
        )

    def __call__(self, request):
        client_ip = self._get_client_ip(request)
        key = f"rate_limit:{client_ip}"

        count = self.redis_client.incr(key)
        if count == 1:
            self.redis_client.expire(key, self.window_seconds)

        if count > self.max_requests:
            return JsonResponse({"error": "Too many requests"}, status=429)

        return self.get_response(request)

    @staticmethod
    def _get_client_ip(request):
        forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        return request.META.get("REMOTE_ADDR")
