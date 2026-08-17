# Django Rate Limiter — Project Plan

Ahmed Fadl | Backend Career Plan | Updated August 2026

## The Big Picture

This effort produces two connected things:

| # | Project | What it is |
|---|---------|------------|
| 1 | **django-rate-limiter** (this repo) | A reusable Django middleware package, containerized for development, published to PyPI. Anyone can `pip install` it and drop it into any Django project. |
| 2 | **Full Stack App** (separate repo, built later) | A real Django + React application that consumes `django-rate-limiter` as an actual dependency, proving the package works in a production-like context. |

**The connection:** the full stack app installs *your own* package from PyPI —
`pip install django-rate-limiter` — the same way any other developer would.
That's the proof the package is real, usable, and production-tested.

**The learning goals driving this project:**
- Get hands-on with Docker (local dev, multi-container apps, images)
- Learn a real deployment workflow end-to-end, on free-tier infrastructure
- Ship a reusable package other projects can actually depend on
- Produce a resume-ready, portfolio-ready project with a live demo

---

## What the Rate Limiter Package Does

- Tracks incoming requests per client IP using Redis
- After N requests within a time window (e.g. 6 seconds), the middleware
  returns `HTTP 429 Too Many Requests`
- Counters expire automatically after the time window (Redis `EXPIRE`)
- Fully configurable via Django settings

```python
RATE_LIMITER_MAX_REQUESTS = 5
RATE_LIMITER_WINDOW_SECONDS = 6
```

- Any Django project adds it in one line:

```python
MIDDLEWARE = [
    "django_rate_limiter.middleware.RateLimiterMiddleware",
    ...
]
```

---

## Current Focus: Docker-First Local Development

We are building this **right now, with Docker from day one** — no local Redis
install, no local Python version juggling. Local dev happens entirely through
`docker-compose`.

Planned local stack:

```
docker-compose.yml
  services:
    web    → Django app (Dockerfile, hot-reload volume mount)
    redis  → official redis image, exposed for the middleware to hit
```

Workflow:
- `docker compose up` brings up Django + Redis together
- Django container talks to Redis over the compose network (`redis://redis:6379`)
- Tests (pytest) run inside the web container, against the same Redis
- No dependency on the host machine beyond Docker itself

This also sets up the containers we'll reuse later for the CI/CD pipeline and
the deployment image, so the Dockerfile written now is the same one that
ships.

---

## Roadmap

### Month 1 — Build & Publish the Package

**Week 1-2: Core Middleware**
- Django project scaffolded, running via `docker-compose up` (Django + Redis containers)
- `middleware.py` with `RateLimiterMiddleware`:
  - Read client IP from `request.META`
  - `INCR` + `EXPIRE` in Redis to count requests per IP within the window
  - Over limit → `JsonResponse` with status 429
  - Under limit → pass the request through
- Pytest coverage:
  - Under limit → 200
  - Over limit → 429
  - After expiry window → counter resets
- Configurable via Django settings (`RATE_LIMITER_MAX_REQUESTS`, `RATE_LIMITER_WINDOW_SECONDS`)

**Week 3: Package & Publish to PyPI**

```
django-rate-limiter/
  django_rate_limiter/
    __init__.py
    middleware.py
  tests/
    test_middleware.py
  setup.py
  README.md
  LICENSE (MIT)
  Dockerfile
  docker-compose.yml
  .github/workflows/ci.yml
```

`setup.py` essentials:
- name: `django-rate-limiter`
- version: `0.1.0`
- install_requires: `Django>=3.2`, `redis>=4.0`
- author: Ahmed Fadl

`README.md` must include:
- One-liner: what it does
- `pip install django-rate-limiter`
- 3-line usage in `settings.py`
- Configuration options table
- Live demo URL
- Badges: tests passing, PyPI version, MIT license

Publish:
```
pip install build twine
python -m build
twine upload dist/*
```

**Week 4: Deploy Demo + CI/CD**
- Deploy a standalone demo (free-tier host — see Deployment Plan below):
  - `GET /api/ping/`
  - Hit it 5 times fast → see a live 429 response
- GitHub Actions CI/CD:
  - On every push: run pytest (inside the same Docker image used locally)
  - On push to `main` + green: auto-deploy demo
  - README badge: tests passing
- Dockerfile + docker-compose.yml are the ones from local dev — no drift
  between "what I ran on my machine" and "what's deployed"

### Month 2 — Full Stack App (uses the package)

**Concept:** a Django + React app that installs `django-rate-limiter` as a
real dependency, exactly like any other developer would. Candidate idea:
Personal Task Manager or URL Shortener (small enough to ship fast, real
enough to show full-stack skill).

**Backend (Django)**
- Separate repo/project from the package itself
- `pip install django-rate-limiter`, wired into `MIDDLEWARE`
- REST API via Django REST Framework:
  - Auth (Django built-in + DRF TokenAuth)
  - CRUD endpoints for the app's core feature
  - Rate limiting applied to all API endpoints via the middleware
  - PostgreSQL as the database
- Optional stretch: Celery + Redis for background tasks (e.g. email
  notifications), sharing the same Redis instance as the rate limiter

**Frontend (React)**
- Separate app (Vite)
- Talks to the Django backend over REST
- Redux for state, Tailwind for styling

**Structure**
```
my-fullstack-app/
  backend/               Django project
    manage.py
    requirements.txt     includes django-rate-limiter
    myapp/
      views.py
      urls.py
      models.py
    settings.py
    Dockerfile
  frontend/              React project
    src/
    package.json
    Dockerfile
  docker-compose.yml     backend + frontend + Redis + PostgreSQL
```

**Making the rate limiter visible**
- `GET /api/status/`:
  - 200 with server status normally
  - 429 with retry-after time when the limit is hit
  - Frontend shows a live "requests remaining" counter
  - On 429, frontend shows a clear warning state
- This turns the rate limiter from a backend detail into something a
  recruiter can literally click and see working.

### Month 3 — Visibility + Certify

- Clean up GitHub READMEs on existing repos
- Portfolio site (GitHub Pages) linking both projects: package + full stack app,
  with links to PyPI, the live demo, and both GitHub repos
- AWS Cloud Practitioner cert (now grounded in real Docker/CI/CD/deployment experience)
- Resume update:
  - `django-rate-limiter`: PyPI link + live demo URL + GitHub badge
  - Full stack app: live URL + GitHub link
  - Skills evidenced: Redis, Docker, CI/CD, Celery, AWS — all real, not just listed

---

## Deployment Plan (Free Options)

Deployment target is free-tier hosting for both the package demo and the
full stack app. Concretely deciding *which* provider(s) — Railway, Render,
Fly.io, Vercel, etc. — and their current free-tier limits is a dedicated
follow-up discussion, since these offerings change often and deserve a
proper comparison rather than reusing possibly-stale assumptions from the
original plan. What's fixed: whatever we pick must run the same Docker image
built for local dev, so there's no "works in Docker, breaks in prod" gap.

## Packaging Plan (Reusable Across Projects)

The middleware is built to be dropped into *any* Django project, not just
the full stack app above:
- Installable via PyPI (`pip install django-rate-limiter`)
- Zero required config beyond adding it to `MIDDLEWARE`
- All behavior tunable via Django settings (`RATE_LIMITER_MAX_REQUESTS`,
  `RATE_LIMITER_WINDOW_SECONDS`)
- Only real dependency is a reachable Redis instance
- Versioned and tagged so downstream projects can pin a version

---

## Resume After 3 Months

**Experience**
- Onspec Engineering & Contracting (May 2025 – Present)
- Bookbee.net Part-Time (Aug 2025 – Present)
- Vultara Inc (Nov 2024 – Apr 2025)
- ITI Trainee (May 2024 – Oct 2024)

**Projects**
- `django-rate-limiter`: PyPI package + live demo + CI/CD + Docker
- Full Stack App (name TBD): Django + React, uses own rate limiter, deployed

**New skills (all real, all shipped):** Redis, Docker, CI/CD, PyPI
publishing, Celery, AWS Cloud Practitioner

---

## How to Talk About This in Interviews

> "I built a reusable Django middleware package for IP-based rate limiting
> using Redis, published it to PyPI, and then used it as a real dependency
> in my full stack application. So I've experienced both sides — building a
> library and consuming it as a developer. The package handles request
> tracking with Redis `INCR` and `EXPIRE`, returns 429 responses when the
> limit is hit, and is fully configurable via Django settings."

This one answer covers: Redis, Django, middleware, PyPI, deployment, full
stack thinking, and developer experience.

---

## Context Notes (for future sessions)

- Ahmed is a Software Engineer, Cairo, Egypt
- Stack: Python, Django, DRF, Node.js, React, PostgreSQL, MongoDB, Supabase,
  Redis, Pytest, Docker, CI/CD
- Working at: Onspec (ADNOC project) + Bookbee.net (part-time, present)
- Civil Engineering degree, not CS — patching the gap with an AWS cert
- Bookbee.net: experience only, not listed as a project (avoids redundancy)
- Bookbee uses Supabase Auth — Ahmed did not build JWT/OAuth manually there
- Key resume metric: 70s → 4ms search optimization at Onspec/ADNOC
- Fawry payment gateway at Bookbee = zero user complaints metric
- Staying focused on Django for now; FastAPI/Flask deferred
- This repo (`Rate-Limiter-With-Redis`) is the Month 1 package project; the
  full stack app is a separate repo to be created in Month 2
