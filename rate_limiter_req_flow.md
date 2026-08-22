# Request Flow: How a Request Becomes a 200 or a 429

Walks one request all the way from `curl` on your laptop to a response
back, and identifies exactly which code we wrote handles each step.

---

## The full path, end to end

```
curl / browser
      │  http://localhost:8000/api/ping/
      ▼
[Docker networking — already covered in learning.md]
      │  host port 8000 → web container's internal :8000
      ▼
Django's dev server (runserver) — accepts the TCP connection,
parses the raw HTTP request into a Django `request` object
      │
      ▼
MIDDLEWARE chain — request travels top → bottom through the list
      │
      ▼
RateLimiterMiddleware (first in the list — the very first thing
that runs on every request, before Django does anything else)
      │
      ├─ under limit ──► the other 7 built-in middlewares ──► URL routing
      │                  (config/urls.py) ──► view function ──► response
      │
      └─ over limit  ──► 429 JsonResponse, built right here — nothing
                          else runs at all: not the other middlewares,
                          not URL routing, not the view
      │
      ▼
Response travels back UP through whichever middlewares actually ran,
in reverse
      │
      ▼
Back through Docker's port mapping, back to curl/browser
```

The Docker part (host port → container, published ports, etc.) is
exactly what's already covered in `learning.md` — nothing new there.
What's new here is everything *after* the request lands inside Django.

---

## How Django actually "receives" the request

`runserver` (started by our Dockerfile's `CMD`, and overridden the same
way in `docker-compose.yml`'s `command:`) is a simple built-in web
server. Its only jobs are: accept the raw TCP connection, read the raw
HTTP bytes off the wire, and turn them into a Django `HttpRequest`
Python object — line, headers, IP, body, all parsed into one object.
That object is then what gets handed, one middleware at a time, down
the `MIDDLEWARE` list in `config/settings.py`.

---

## The middleware chain, concretely

Our current list, in order:

```python
MIDDLEWARE = [
    'django_rate_limiter.middleware.RateLimiterMiddleware',   # ← ours, first
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]
```

Each middleware is really just a wrapper around "the rest of the
chain." Picture it like nested envelopes: ours now wraps
`SecurityMiddleware`, which wraps `SessionMiddleware`, and so on, down
to the view at the very center. Concretely, each one does some setup,
then calls `self.get_response(request)` — which is just "hand it to
whatever's next" — and whatever that call *returns* is this
middleware's own response too, usually unmodified.

Because ours is placed **first**, it's the very first thing that runs
on every request — before Django has done *anything* else: no session
lookup, no CSRF processing, no auth. If we reject here, none of that
work ever happens.

### Why first, not last?

This used to be last, closest to the view — and that was worth
questioning: placing it last meant every rejected request still paid
for all seven built-in middlewares' work *before* we ever checked
Redis. That's wasted work on requests we were always going to refuse.
Moved to first, an abusive request gets rejected before Django does
anything else at all — the efficient placement under real load.

One trade-off worth knowing about the move: previously, even a 429
response still passed back out through all seven built-in middlewares
(so e.g. `SecurityMiddleware` could still attach its response headers
to it). Now that we're first, a 429 we return skips *all* of them
entirely in both directions — nothing before us exists anymore to
process it on the way out. For a plain JSON 429 that's a fine trade,
but it's the kind of detail worth remembering if a later middleware's
behavior (security headers, CORS, etc.) ever needs to apply even to
rejected requests.

The one scenario where "first" would be the *wrong* call: rate-limiting
by the *authenticated user* instead of raw IP, which needs
`AuthenticationMiddleware` to have already populated `request.user` —
only true if positioned *after* it. Our middleware only ever reads the
raw IP, so that doesn't apply here.

---

## Walkthrough 1 — under the limit

1. Request enters. `RateLimiterMiddleware.__call__` runs **first**,
   before any built-in middleware:
   - Gets the client IP.
   - `redis_client.incr("rate_limit:<ip>")` → still under `RATE_LIMITER_MAX_REQUESTS`.
   - Calls `self.get_response(request)` — passing the request onward.
2. "Onward" now means the seven built-in middlewares run, one by one
   (session lookup, CSRF, auth, etc.), each just passing the request
   further along.
3. Then **URL routing**: Django takes the request path (`/api/ping/`)
   and matches it against `urlpatterns` in `config/urls.py`, finds
   `path('api/ping/', ping)`, and calls the `ping(request)` view
   function.
4. `ping()` returns `JsonResponse({'status': 'ok'})`.
5. That response bubbles back up through the seven built-in middlewares
   in reverse (each may attach things like security headers), then
   back through our middleware — `return self.get_response(request)`
   just hands it along unmodified — then out through the dev server,
   back to `curl` as a real `200`.

## Walkthrough 2 — over the limit

1. Same as above through the first check — but this time
   `redis_client.incr(...)` returns a count *above*
   `RATE_LIMITER_MAX_REQUESTS`.
2. Instead of calling `self.get_response(request)`, we build and
   `return` a `JsonResponse({'error': 'Too many requests'}, status=429)`
   **directly, right here.**
3. Because `self.get_response` was never called, and ours is the very
   first middleware, **nothing else runs at all** — not the other
   seven middlewares, not URL routing, not `ping()`. The request stops
   dead at this one check.
4. The 429 we built goes straight back out through the dev server to
   `curl` — no other middleware ever touches it, in either direction.

---

## The window mechanism: how "5 requests / 6 seconds" actually plays out over time

The two walkthroughs above show one request at a time. Here's the same
IP making several requests in a row, with `RATE_LIMITER_MAX_REQUESTS=5`,
`RATE_LIMITER_WINDOW_SECONDS=6`:

```
t=0.0s  request 1 → INCR → count=1 → count==1, so EXPIRE key 6s
                                       (key now dies at t=6.0s)         → 200
t=0.5s  request 2 → INCR → count=2   (EXPIRE untouched)                → 200
t=1.0s  request 3 → INCR → count=3                                     → 200
t=1.2s  request 4 → INCR → count=4                                     → 200
t=1.5s  request 5 → INCR → count=5   (5 > 5 is false — still allowed)  → 200
t=1.6s  request 6 → INCR → count=6   (6 > 5)                           → 429
t=3.0s  request 7 → INCR → count=7   (still same key, same window)     → 429
  ...   every request from here until t=6.0s keeps getting 429
t=6.0s  Redis deletes the key itself — its TTL simply ran out.
        No Django code runs at this moment; Redis does this entirely
        on its own, in the background.
t=6.1s  request 8 → INCR on a key that no longer exists → Redis treats
                     this as brand new → count=1 → EXPIRE resets a
                     *fresh* 6-second window starting now             → 200
```

Two details worth noticing:

- **`EXPIRE` is only ever set when `count == 1`.** If we refreshed the
  TTL on *every* request instead, an attacker sending requests fast
  enough could keep the window alive indefinitely — the count would
  never reset, and a client that briefly went over the limit could stay
  blocked forever. Setting it only once guarantees the window always
  ends exactly `window_seconds` after the *first* request in a burst,
  no matter how much traffic follows.
- **The window is per-IP and starts at that IP's first request** — not
  aligned to the clock (not "every 6 seconds on the dot"). Two
  different IPs each get their own independent key (`rate_limit:<ip>`)
  and their own independently-timed window.

**Honest limitation worth knowing (a fixed-window counter):** because
each window starts fresh from its first request, a client could send 5
requests right before `t=6.0s`, then 5 more right after — getting close
to *double* the intended rate in a short burst straddling the boundary.
This is a known trade-off of the simple "fixed window counter" approach
used here. A "sliding window" or "token bucket" algorithm avoids that
edge case, at the cost of a more involved Redis data structure (e.g. a
sorted set of timestamps instead of one counter) — worth knowing as a
follow-up, not something this implementation needs to solve right now.

---

## What code was actually necessary, and where it plugs in

| File | What it's responsible for in this flow |
|---|---|
| `django_rate_limiter/middleware.py` | The `RateLimiterMiddleware` class itself — the one link in the chain that can short-circuit everything after it. |
| `config/settings.py` — `MIDDLEWARE` list | The literal wiring: without adding our class here, Django never puts it in the chain at all, and every request would just reach `ping()` directly. |
| `config/settings.py` — `REDIS_HOST` / `REDIS_PORT` / `RATE_LIMITER_*` | What the middleware reads in `__init__` to know *which* Redis to talk to and *what* the limits are — this is where the Docker Compose `environment:` values from earlier actually get consumed. |
| `config/urls.py` — `path('api/ping/', ping)` | Gives URL routing something to match *if* the request ever makes it past the middleware — the thing being protected, not the protection itself. |

Nothing here is Docker-specific — this whole chain would work identically if Django were running directly on a laptop with a local Redis install. Docker's only job (covered in `learning.md`) was getting the request to Django's front door in the first place.
