# django-rate-limiter

A Django middleware that rate-limits incoming requests per client IP using
Redis: once a client exceeds a configurable number of requests within a time
window, it gets `HTTP 429 Too Many Requests` until the window resets.
Counters live entirely in Redis (`INCR` + `EXPIRE`) — no database writes, no
extra app-level bookkeeping.

```python
MIDDLEWARE = [
    'django_rate_limiter.middleware.RateLimiterMiddleware',
    ...
]

RATE_LIMITER_MAX_REQUESTS = 5
RATE_LIMITER_WINDOW_SECONDS = 6
```

## Status

Working end to end as a Django app: middleware, demo endpoint, and a Docker
Compose setup running Django + Redis as separate containers. Not yet split
out into a standalone `pip install`-able package or published to PyPI — see
[`PLAN.md`](PLAN.md) for the full roadmap (packaging, PyPI, CI/CD, a
companion full-stack demo app, deployment).

## Quick start

Requires only Docker (no local Python/Redis install needed):

```bash
cp .env.example .env
docker compose build web
docker compose run --rm web django-admin startproject config .   # first time only
docker compose up
```

Then hit the demo endpoint:

```bash
curl http://localhost:8000/api/ping/
```

Fire it 6 times in a row (within the default 6-second window) and the 6th
call returns a `429`.

## Configuration

All of it lives in `.env` (see `.env.example` for the template — never
commit the real `.env`):

| Variable | Default | What it controls |
|---|---|---|
| `RATE_LIMITER_MAX_REQUESTS` | `5` | Requests allowed per client IP per window |
| `RATE_LIMITER_WINDOW_SECONDS` | `6` | Length of the rate-limit window, in seconds |
| `REDIS_HOST` | `localhost` | Redis hostname (Compose overrides this to `redis` inside containers) |
| `REDIS_PORT` | `6379` | Redis port |
| `SECRET_KEY` | dev fallback in `settings.py` | Django's secret key — set a real one outside of local dev |

## Project structure

```
django_rate_limiter/
  middleware.py       RateLimiterMiddleware — the actual rate limiter
config/                Django project (settings, URLs, WSGI/ASGI)
manage.py
Dockerfile             Builds the Django app's image
docker-compose.yml      Runs web (Django) + redis as separate containers
requirements.txt
.env.example            Template for local config — copy to .env
```

## How it works

`RateLimiterMiddleware` runs first in `MIDDLEWARE`, ahead of everything
else Django would normally do. For every request it:

1. Reads the client's IP.
2. `INCR`s a per-IP counter key in Redis.
3. On that key's *first* increment, sets a `window_seconds` expiry — so the
   window always ends exactly `window_seconds` after the first request in a
   burst, not on every request.
4. Over the limit → returns `429` immediately, before Django does anything
   else (URL routing, views, etc. never run).
5. Under the limit → passes the request through as normal.

For the full request-by-request walkthrough — including why the middleware
is ordered first, and an honest note on the fixed-window algorithm's
boundary-burst limitation — see
[`rate_limiter_req_flow.md`](rate_limiter_req_flow.md).

## Docs

- [`PLAN.md`](PLAN.md) — project roadmap: packaging, PyPI, CI/CD, the
  companion full-stack app, deployment
- [`learning.md`](learning.md) — running Docker/containers/networking notes
  collected while building this, organized as a glossary
- [`rate_limiter_req_flow.md`](rate_limiter_req_flow.md) — the Django
  request lifecycle through the middleware chain, in detail
