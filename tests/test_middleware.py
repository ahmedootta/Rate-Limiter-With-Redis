import time

import pytest
import redis
from django.conf import settings
from django.test import override_settings

TEST_KEY = "rate_limit:127.0.0.1"  # Django's test client's default REMOTE_ADDR


@pytest.fixture(autouse=True)
def clear_rate_limit_key():
    client = redis.Redis(host=settings.REDIS_HOST, port=settings.REDIS_PORT)
    client.delete(TEST_KEY)
    yield
    client.delete(TEST_KEY)


@override_settings(RATE_LIMITER_MAX_REQUESTS=3, RATE_LIMITER_WINDOW_SECONDS=6)
def test_requests_under_limit_return_200(client):
    for _ in range(3):
        response = client.get("/api/ping/")
        assert response.status_code == 200


@override_settings(RATE_LIMITER_MAX_REQUESTS=3, RATE_LIMITER_WINDOW_SECONDS=6)
def test_requests_over_limit_return_429(client):
    for _ in range(3):
        client.get("/api/ping/")

    response = client.get("/api/ping/")

    assert response.status_code == 429


@override_settings(RATE_LIMITER_MAX_REQUESTS=1, RATE_LIMITER_WINDOW_SECONDS=1)
def test_counter_resets_after_window_expires(client):
    assert client.get("/api/ping/").status_code == 200
    assert client.get("/api/ping/").status_code == 429

    time.sleep(1.5)

    assert client.get("/api/ping/").status_code == 200
