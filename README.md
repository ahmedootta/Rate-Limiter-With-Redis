# django-rate-limiter

A planned reusable Django middleware package: rate-limits incoming requests per
client IP using Redis, returning `HTTP 429 Too Many Requests` once a request count
exceeds a configurable threshold within a time window (counters auto-expire via
Redis `EXPIRE`). Meant to be `pip install`-able and dropped into any Django project
in one line, e.g.:

```python
RATE_LIMITER_MAX_REQUESTS = 5
RATE_LIMITER_WINDOW_SECONDS = 6
```

## Status

**Planning stage — no code yet.** This repo currently holds the project plan and a
running Docker/deployment learning log rather than an implementation. See
`PLAN.md` for the full scope (including a companion full-stack demo app that will
depend on this package once published to PyPI) and `learning.md` for Docker/Redis
notes collected along the way.
