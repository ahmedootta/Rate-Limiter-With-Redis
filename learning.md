# Docker Learning Notes

A running cheat sheet: command → what it actually does. Organized by
topic so it's easy to revise, not a chronological log of the session.
Only contains things we've actually run and verified.

---

## Why containers at all, if ports alone already separate apps on one IP?

Simple answer: **ports only separate network traffic. Containers
separate everything else too** — and that's the actual problem Docker
solves. New container IPs aren't the goal, they're just a side effect of
that full isolation.

- **Apps need different *everything*, not just a different port.** App A
  might need Python 3.9 + old libraries, App B needs Python 3.12 + newer
  ones. You can't install two conflicting versions of the same library
  on one shared OS. Each container gets its own private filesystem and
  libraries — the port difference is incidental.
- **Every app can keep its own default port, unmodified.** Most apps
  hardcode a "standard" port (Redis wants 6379, Postgres wants 5432).
  Without containers, running two Redis instances means manually
  reconfiguring one of them. With containers, both use 6379 internally
  with zero config changes, because each lives in its own private
  network, unaware the other exists. *This* is the real reason
  containers get their own IP — so the app inside never has to change.
- **A crashed or compromised app can't see the rest of the system.**
  Two apps just running side-by-side on one host can see each other's
  files and processes. A container can't see outside its own namespace.
- **You can stop, restart, upgrade, or scale one app without touching
  the others** — nothing is shared, so nothing about App A changes when
  you redeploy App B.

---

## Docker Engine vs a Hypervisor — how isolation is actually built

A **hypervisor** (VMware, VirtualBox, etc.) gives each VM a *fake
computer* — virtual CPU, virtual disk, virtual everything — and boots a
full separate OS kernel on top of it. That's why VMs are heavy and slow
to start: each one is a whole second computer.

The **Docker Engine** (`dockerd`) does something cheaper: it doesn't
virtualize hardware at all. Every container runs on the **same real
Linux kernel** as your host. Isolation instead comes from two kernel
features Docker automates for you on every `docker run`:

- **Namespaces — control what a process can *see*.** A namespace wraps
  a process in its own private view of one kind of resource: its own
  process list (can't see other containers' processes), its own network
  stack (its own IP/interfaces — this is exactly what gave the Redis
  container its own `172.17.0.2` earlier), its own filesystem mounts,
  its own hostname. The process thinks it's alone on the machine.
- **cgroups (control groups) — control how much a process can *use*.**
  A cgroup caps and tracks resource usage — CPU, memory, disk/network
  I/O — per container. This is what stops one container from hogging
  all the RAM and starving everything else (`docker run --memory=512m`
  is a cgroup limit).

**Analogy:** a hypervisor builds each guest a separate house from
scratch — own foundation, own walls, own utilities (own kernel). Docker
instead gives each guest their own *room* inside the **same** house
(shared kernel): namespaces are the walls and locked door (what you can
see/reach), cgroups are the utility meter on that room (how much power/
water it's allowed to draw). Cheaper and much faster to set up than
building a whole new house per guest — which is exactly why containers
start in milliseconds and VMs take tens of seconds.

---

## Core Concepts

- **Docker daemon (`dockerd`)** — the background process that does the
  real work: builds images, starts/stops containers, manages networks
  and volumes. It's always running in the background, separate from any
  command you type.
- **Docker CLI (`docker`)** — just a client. Every `docker ...` command
  you type gets sent to the daemon over a socket (a local file the two
  processes use to talk to each other, e.g.
  `~/.docker/desktop/docker.sock` on this machine, since we're using
  Docker Desktop). If the daemon isn't running, the socket has nothing
  listening on it and every command fails with
  *"Cannot connect to the Docker daemon"* — even though the CLI binary
  itself is installed and works fine.
- **Image vs Container** — an *image* is a read-only template (a
  filesystem + metadata) built once. A *container* is a running (or
  stopped) instance of an image — same relationship as a class and an
  object. You can start many containers from one image.

### What's inside an image, layer by layer

An image is a stack of read-only filesystem layers, plus metadata on
top describing how to run it:

```
┌───────────────────────────────────────────────────┐
│ Metadata (instructions, not files):                  │
│   default command, exposed ports, env vars,          │
│   working directory                                  │
├───────────────────────────────────────────────────┤
│ App layer — your own code                            │
│   (middleware.py, manage.py, ...)                     │
├───────────────────────────────────────────────────┤
│ Dependencies layer                                    │
│   (whatever got installed on top: Django, redis-py,   │
│    Redis's own server binary, ...)                     │
├───────────────────────────────────────────────────┤
│ Base layer — minimal OS userspace files               │
│   (a lightweight distro's /bin, /etc, glibc, a package │
│    manager — just enough files for programs to run)    │
└───────────────────────────────────────────────────┘
```

Notably absent from that stack: a kernel. Every layer here is just
files — binaries, libraries, config, your code. No image ever ships a
kernel; every container that runs from it borrows the one real kernel
the host already has running.

### Why does that make containers lightweight?

Compare it to a VM. A VM image has to include an entire second
operating system — kernel, boot loader, device drivers, the works —
because it's booting what is effectively a whole separate computer.
Starting one means going through a real boot sequence and reserving
fixed chunks of CPU/RAM up front. That's minutes-to-seconds of work and
gigabytes of disk.

Starting a container skips almost all of that:
- **No kernel to bundle or boot** — it reuses the host's, already
  running, so "starting a container" is never "starting an OS."
- **No boot sequence at all** — the kernel just creates a namespace +
  cgroup, mounts the image's layers as that container's filesystem, and
  directly runs your app's process. That's the entire startup.
- **Layers are shared, not duplicated** — if ten images all start from
  the same base layer (e.g. `python:3.12-slim`), that layer is stored
  on disk exactly once and reused by all of them; each running
  container just gets one thin writable layer on top for its own
  changes.

Net effect: an image is a few file layers, and a container is a process
that the kernel already knows how to fence off (namespaces) and meter
(cgroups) — nothing has to be built or booted first. That's the entire
reason containers start in milliseconds while VMs take tens of seconds.

---

## Daemon / Environment Commands

| Command | What it does |
|---|---|
| `docker --version` | Prints the installed CLI version. Doesn't need the daemon running — it's a static check of the local binary. |
| `docker compose version` | Prints the installed Docker Compose plugin version (same idea, no daemon needed). |
| `docker info` | Asks the **daemon** for a summary of its state (server version, number of containers/images, storage driver, etc.). This one *does* need the daemon running, so it's a good "is Docker actually alive" check. |
| `systemctl --user start docker-desktop` | Starts the Docker Desktop background service (which runs the daemon) via systemd, the Linux service manager. `--user` means it's managed under your user session, not system-wide. |
| `systemctl --user status docker-desktop` | Shows whether that service is currently active/running or inactive/dead, without starting or stopping it. |

---

## Images & Containers

### Redis — done ✅

```
docker run -d --name rate-limiter-redis -p 6379:6379 redis:7-alpine
```

| Part | What it does |
|---|---|
| `docker run` | Create **and** start a new container from an image. |
| `-d` | Detached — runs in the background, hands the terminal back immediately. |
| `--name rate-limiter-redis` | Names the container so later commands (`docker logs`, `docker stop`) can target it by name instead of a random one. |
| `-p 6379:6379` | Publishes host port 6379 → container port 6379 (installs the iptables DNAT rule from the Networking section). |
| `redis:7-alpine` | The image to run — already local, so it started instantly with no download. |

Confirmed via `docker ps`:

```
CONTAINER ID   IMAGE            STATUS         PORTS                     NAMES
d2a82bc5ff38   redis:7-alpine   Up             0.0.0.0:6379->6379/tcp    rate-limiter-redis
```

`docker run` printed the new container's full ID to the terminal on
success (the short form `d2a82bc5ff38` above is the same ID, just
truncated for display — `docker ps` always shows the short version).

### Django — next up

*(to be filled in once the Django image is built and its container is running)*

---

## Development Workflow: Where Do Your Actual Files Live?

Your observation is correct: "install the stack globally, code locally,
write a Dockerfile at the very end" barely uses containers *during*
development — Docker only shows up right before shipping. The
alternative — developing *inside* a container from day one — uses a
tool you've already seen: the **bind mount**. Below is exactly what
happens, step by step, treating the container as the genuinely isolated
device it actually is.

### The story: developing React inside a container, step by step

**Setup:** an empty folder on your laptop, `~/my-react-app`. Goal:
build a React app without ever installing Node on your laptop itself.

**Step 1 — Open a shell *inside* the isolated device**

First, on your host, you'd actually be sitting inside the project
folder before typing anything Docker-related:

```
cd ~/my-react-app
docker run -it --rm -v "$(pwd)":/app -w /app --name react-dev node:20 bash
```

The mapping you're looking for **is** in the command — it's just not a
literal, hardcoded path. `-v "$(pwd)":/app` means "bind-mount `<host
path>:<container path>`," and `$(pwd)` is a piece of *shell*
substitution, not something Docker understands: your terminal runs
`pwd` (which just prints "what directory am I sitting in right now")
*before* Docker ever sees the command, and swaps in that literal text.
So because you `cd`'d into `~/my-react-app` first, `$(pwd)` silently
expands to `/home/you/my-react-app`, and the command Docker actually
receives is effectively:

```
docker run -it --rm -v /home/you/my-react-app:/app -w /app --name react-dev node:20 bash
```

`$(pwd)` is just a convenience so you don't have to type the full path
by hand — it always means "wherever my terminal currently is." Writing
it out explicitly, `-v ~/my-react-app:/app`, would do the exact same
thing without relying on your current directory at all — that version
makes the mapping visible at a glance, which is probably clearer while
you're still building the mental model.

`-it` attaches your terminal to a live shell running *inside* that
container — a genuinely separate device from the OS's point of view: its
own process list, its own network stack, its own filesystem root, all
the isolation from the "Docker Engine vs a Hypervisor" section earlier.
Proof: run `hostname` at that prompt — it prints a random container ID,
not your laptop's real hostname. Every command you type from here on
executes *inside* that isolated device, not on your laptop.

**Step 2 — Install React 18.3 — where do these files physically land?**

At that prompt: `npm install react@18.3.1`.

The question: does this write bytes onto the container's own private
"hard disk," or onto your laptop's real one? **It depends entirely on
which path you're writing to:**

- We're sitting in `/app` (via `-w /app`), and `/app` is bind-mounted to
  `~/my-react-app` on your host (that's what `-v "$(pwd)":/app` set up
  in Step 1). So `npm install` creates `/app/node_modules` — and because
  `/app` is a live window onto your host folder, not a copy,
  `node_modules` appears on your **actual laptop disk**, inside
  `~/my-react-app/node_modules`, in real time. Open a totally separate
  terminal on your host, outside Docker entirely, and those exact files
  are sitting right there.
- Compare that to a global install landing *outside* `/app` — e.g.
  `npm install -g some-tool`, which writes to a system path like
  `/usr/lib/node_modules`. That path was never bind-mounted, so it's
  written only into the container's own private writable layer — a
  layer that exists solely for this one container, invisible to your
  host, and gone the instant the container is removed.

So yes, a container does have something like its own hard disk: its
filesystem is the read-only image layers (Node.js, pre-baked into
`node:20`) plus one thin writable layer created just for *this*
container. Anything you install normally lands there — private,
disposable. A bind mount punches a hole through that private disk at
one specific path and replaces it with a direct, live connection to a
real folder on your host's real disk. Same command, two entirely
different destinations, depending only on the path.

**What if you delete the container while developing?**

`node_modules` and the React version you installed live inside `/app`,
which is your host folder — so `docker rm react-dev` (or `--rm` cleaning
up automatically on exit) doesn't touch them at all. They're still
sitting on your laptop's real disk. Only things written *outside* `/app`
— that hypothetical global tool — vanish with the container.

**What if you delete the files on your *host* while the container is running?**

The opposite direction: delete `~/my-react-app/node_modules` from your
laptop, in a normal terminal, while the container's dev server is still
running — since `/app` inside the container *is* that same folder, not
a copy, it goes empty on the container's side too, instantly. The
running process would likely crash with "module not found," because its
files just vanished from under it in real time. There's no independent
backup on either side — one folder, viewed from two places at once.

**Q: What actually lets you delete a container and rebuild it with everything the same — the bind mount, the image, all of it?**

It's two separate jobs, not one — and they get confused because they
both feel like "the container remembering who it was":

- **`docker build` only owns what's *inside the image*** — the base,
  whatever got `RUN`/`COPY`'d in via the Dockerfile. Same Dockerfile in,
  same image content out, every time.
- **`docker run` owns everything about how a container gets *started*
  from that image** — the bind mount path (`-v`), which port gets
  published (`-p`), the container's name (`--name`), env vars. None of
  that lives in the Dockerfile — a Dockerfile has never seen `-v`, `-p`,
  or `--name`; those aren't Dockerfile instructions at all, they're
  flags you type at run time.

| | `docker build` | `docker run` |
|---|---|---|
| Reads | A Dockerfile | An image (already built) |
| Produces | A new image | A new container |
| Remembers | Image contents (base, deps, code, default command) | Nothing — every flag is typed fresh, each time |

So if you `docker rm` a container today and `docker build` again
tomorrow, you get an identical *image* — but you'd still have to
remember and retype the entire `docker run -v ... -p ... --name ...`
command by hand to get an identical *container*. Nothing about `docker
run`'s flags is saved anywhere by default.

**Q: Is that what `docker-compose.yml` is for — running many containers together with one command instead of several separate `docker run`s?**

Yes, that's its most common use: one file lists several services (say,
your Django app + Redis), each with its own image/build, mounts, ports,
env vars — and `docker compose up` starts all of them together,
automatically networked so they can reach each other by name (the
"same building" idea from the Networking section). It replaces running
several separate `docker run` commands by hand, one per container.

**Q: Is there a file for a *standalone*, single container to remember its whole recipe — image, mounts, ports, env vars — the same way?**

Yes — `docker-compose.yml` isn't limited to multiple containers at all.
Nothing stops you from writing one with a single service in it, purely
so the full `docker run` recipe is saved in a file instead of your
memory or shell history:

```yaml
services:
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
```

`docker compose up` here starts exactly one container — same effect as
the `docker run -p 6379:6379 redis:7-alpine` we typed by hand earlier,
just saved and repeatable. Compose gets associated with "multiple
containers" mainly because that's where it earns its keep the most
(automatic networking between services), but "remember my run recipe"
is a perfectly normal reason to reach for it even solo. (The lighter
alternative some people use instead, for a single container, is just
saving the `docker run` command itself in a small shell script — works,
but isn't as standardized or portable as Compose.)

**Q: If different apps all get developed this same way — a shell inside a container, physical files routed correctly via a bind mount — how do they all run with the *same* command, `docker run`?**

Because `docker run` isn't actually specific to any app at all — it's a
completely generic instruction: *"start a container from this image,
and execute whatever command I tell you (or its default)."* It has no
idea what React, Django, or Redis even are. Everything that makes one
invocation become a React dev server and another become a database is
carried entirely in the **arguments**, not the verb:

```
docker run -v "$(pwd)":/app -w /app -p 3000:3000 node:20        npm run dev        ← React
docker run -v "$(pwd)":/app -w /app -p 8000:8000 python:3.12     python manage.py runserver 0.0.0.0:8000   ← Django
docker run -p 6379:6379                                          redis:7-alpine                            ← Redis (default CMD, nothing extra needed)
```

Same shape every time — `docker run [flags] <image> [command]` — but
two things fully decide "which app": **which image** (that's what
determines what tools/runtime even exist inside — Node vs. Python vs.
Redis's own binary), and **which command actually executes** at
startup (either one you type explicitly, like `npm run dev`, or the
image's own baked-in default, like Redis's `redis-entrypoint.sh`).
`docker run` itself is just the generic launcher — closer to how the
English word "run" means something completely different in "run a
script" vs. "run a marathon" purely because of the object, not the
verb. Once the image and the bind-mounted files are both set up
correctly, `docker run` doesn't need to be "different" per app — it was
never app-specific to begin with.

**Is that genericness something we configure, or is it built into Docker itself?**

Split down the middle — two different layers:

- **Built into Docker, fixed, not something we touch:** the *shape* of
  the command — `docker run [OPTIONS] IMAGE [COMMAND]` — and the rule
  that if you don't type a `COMMAND` at the end, Docker falls back to
  running whatever the image's own default (its `CMD`/`ENTRYPOINT`) is.
  That parsing behavior is part of the Docker Engine itself, identical
  for every image that has ever existed.
- **Configured by us (or whoever built the image):** everything that
  fills in that generic shape. Which image gets used, what that image's
  *default* command is (decided by whoever wrote its Dockerfile — us,
  for our own images, or the Redis maintainers for `redis:7-alpine`),
  and whether we override that default with our own command at the end
  of `docker run`, plus every flag (`-v`, `-p`, `--name`, ...).

So Docker guarantees the *mechanism* — "take an image, run a command,
fall back to the image's default if none is given." It has no opinion
at all about *what* that command or image should be — that part is
100% on us.

**Follow-up questions on that global-install example (`/usr/lib/node_modules`)**

**0 — Does the container's private layer take real, physical space on
my host, and does deletion only happen on *remove*, not *stop*?**

Yes to both. That private writable layer is real bytes, sitting on your
host's actual disk somewhere Docker manages for you — it's not virtual
or free. And the distinction between *stop* and *remove* matters a lot
here:
- `docker stop` just ends the running process (like closing an app) —
  the container object and its entire private layer stay on disk,
  completely untouched. `docker start` later brings it right back,
  contents intact.
- `docker rm` (removing it) is what actually deletes that private layer
  for good. So the cascade you're describing is real, but it's tied to
  **removal, not stopping** — a stopped container is dormant, not gone.

And you're right that nothing about this is "displayed" from inside the
container — a process running inside has no way to tell, just by
looking, whether a given folder is a bind mount to your host or part of
its own private layer. Both just look like ordinary directories from
the inside; the difference only exists in how Docker set the path up
before the container ever started.

**1 — How much disk space does a container actually get, and is it configurable?**

By default: no fixed amount at all. A container's private layer can
grow to use as much space as is free in Docker's storage area on the
host (on this machine, technically "the host" is Docker Desktop's VM —
recall the earlier VM-hop section — so really it's however much of that
VM's virtual disk is free, which you can resize in **Docker Desktop →
Settings → Resources**).

It *can* be capped per-container with `docker run --storage-opt
size=2G ...`, but this only works with specific storage drivers/
filesystems and isn't enabled in most default setups (including typical
Docker Desktop installs) — so in practice, almost nobody sets
per-container disk limits day to day. The thing people actually
configure is the overall pool size (the VM's disk, on Desktop), not
individual containers.

**2 — Without a bind mount, is a container's terminal really the only way in?**

Correct, with one more option worth knowing:
- `docker exec -it react-dev bash` → open a shell inside the *already
  running* container and browse normally with `cd`/`ls` — exactly what
  you described.
- `docker cp react-dev:/usr/lib/node_modules ./some-local-folder` →
  copies files out of (or into) a container's filesystem directly from
  your host, without needing an interactive shell at all.

Both of these go *through Docker*, though — neither one is a normal
host file path, because none was ever created for that location.
That's really the whole point of a bind mount: it's the thing that
*creates* a host-reachable path in the first place. Without one, the
files still physically exist somewhere on your host's disk, but there's
no supported, stable path to them directly — Docker treats that as its
own private implementation detail, not something meant to be reached
except through Docker's own commands.

**Step 3 — The code files themselves: exact same question**

Whether `src/App.jsx` was generated by `npm create vite@latest .` inside
the container, or hand-written by you in VS Code on your host — same
mechanism. `src/` sits inside `/app`, which is bind-mounted, so the file
is physically on your laptop's disk, git-trackable, editable by any
tool on your host. The container had no special role in "storing" it;
it just happened to be the process running at the moment the file
appeared.

- Delete the container → `src/App.jsx` still exists on your laptop, untouched.
- Delete `src/App.jsx` from your host → gone from the container's view
  too, instantly.

**The one rule underneath all of it:** anything written inside a
bind-mounted path is physically on the host, always — regardless of
whether the container or you did the writing. Anything written outside
that path exists only in the container's own private, disposable layer.

### The vital difference between a Python venv and a container

One sentence: **a venv changes *which files* `python` reads. A
container changes *what machine* the process believes it's running on.**

- **venv** — a folder holding a private copy of the Python interpreter
  plus installed packages, and "activating" it just changes your
  shell's `PATH` so `python`/`pip` point there instead of the system
  copies. Same OS, same kernel, same process list, same network — it
  isolates exactly one thing: which library versions get imported.
- **container** — real OS-level isolation via kernel namespaces +
  cgroups: its own process list, its own network stack/IP, its own
  filesystem root, kernel-enforced resource limits. It isolates
  practically the entire runtime environment, not just one language's
  packages — and can even run a completely different Linux distro's
  userland than the host, something a venv could never do.

A venv is a small trick inside one shared environment. A container is
closer to a separate environment that only shares the kernel.

### Dockerfile vs. the commands you just typed by hand

Everything in the story above — opening the shell, typing
`npm install react@18.3.1`, typing `npm create vite@latest .` — was you
doing setup steps manually, live, one at a time. A Dockerfile is
nothing more than **those exact same steps, written down so Docker
replays them automatically**, instead of you sitting there typing:

```dockerfile
FROM node:20
WORKDIR /app
RUN npm install react@18.3.1
COPY . .
CMD ["npm", "run", "dev"]
```

`docker build` reads this top to bottom and runs each line exactly like
you'd type it into that shell yourself — except it saves the result as
a new, reusable image afterward, instead of that state disappearing the
moment you exit the container. The manual story above taught you *what
actually happens on disk* when each step runs; the Dockerfile just
automates the same actions so nobody has to retype them by hand.

### Then how do you run this on a machine that only has Docker installed?

The bind-mount setup only works because your source files physically
exist on *this* machine — you can't hand someone a `docker run -v ...`
command pointing at a folder that doesn't exist on their computer.

To actually ship it, the Dockerfile's `COPY` instruction bakes the code
into the image at build time, instead of borrowing it live from a
mount:

```dockerfile
FROM node:20
WORKDIR /app
COPY . .
RUN npm install
RUN npm run build
CMD ["npm", "start"]
```

`docker build -t my-react-app .` bakes your code and dependencies
permanently into a new image. Push that image to a registry, and *any*
machine with only Docker installed can run:

```
docker pull my-react-app
docker run -p 3000:3000 my-react-app
```

No Node, no source folder needed there — the image already contains
everything, because `COPY` baked it in permanently, instead of the
container reaching out to a mount that only exists on your laptop.

**In one line:** bind mount = fast local dev, code stays live and
editable on your host. `COPY` in a Dockerfile = a durable, portable
image you can actually ship anywhere. Same two tools, aimed at
different goals.

### The same "where do the files live" question, for a database: volumes

A database container raises the same question, for a different reason —
not code you edit, but *data* the database engine writes to disk
internally (e.g. Postgres writes to `/var/lib/postgresql/data` inside
its own container).

Run it plain, with nothing extra:

```
docker run -d --name mydb postgres
```

Its data lives *only* inside that one container's own writable layer.
The moment you `docker rm mydb`, every row you ever inserted is gone —
permanently.

A **volume** fixes exactly this — storage Docker manages *outside* any
single container's lifecycle:

```
docker run -d --name mydb -v pgdata:/var/lib/postgresql/data postgres
```

`pgdata` is a **named volume** — Docker owns real storage for it
somewhere on the host, and you never need to know exactly where.
Postgres, inside the container, still just writes to
`/var/lib/postgresql/data` like normal — it has no idea a volume is
involved. But because that path is backed by the volume instead of the
container's own throwaway layer, the data survives container removal.
Delete `mydb`, start a fresh container with the *same*
`-v pgdata:/var/lib/postgresql/data`, and every table comes back exactly
as it was.

**The difference from the React bind mount, in one line:** with
source code, the mount exists so *you* keep editing files with your
normal tools while the container just runs them. With a database, the
volume exists purely for *persistence* — you never hand-edit those data
files; the only goal is that they outlive any single container.

### What is a Dockerfile, at the simplest level? (the generalized recap)

Stepping back from the React story to the general idea: a Dockerfile is
just a **plain text file with a numbered list of steps** — a recipe
card. Each line is one plain instruction telling Docker what to do to
build an image:

1. Start from some base (e.g. "a minimal Linux that already has
   Node — or Python — on it")
2. Copy your project's files into it
3. Install whatever your project needs
4. Say what command should run when a container starts from it

**Analogy:** the Dockerfile is the recipe card. `docker build` is
cooking that recipe *once* — the result is a dish you can store (the
image). `docker run` is serving *one plate* of that stored dish (a
container). You can serve as many plates as you like from the same
cooked batch — each one a separate, independent container, all from
following the same recipe once.

### The commands — your instinct is right

Basically every Docker command falls into one of two buckets:

- **Commands that create something new:**
  - `docker build` → follows a Dockerfile's steps, produces a new image
  - `docker run` → starts a new container from an image (building one
    first if you're running your own Dockerfile, or just using an
    existing one like we did for Redis)
- **Commands that manage or observe things that already exist:**
  - `docker ps` → list running containers
  - `docker stop` / `docker start` → pause / resume a container without
    deleting it
  - `docker logs` → see a container's output
  - `docker rm` → delete a stopped container

So yes — that's exactly it: it's either "make a new image/container,"
or "do something to a container that's already there."

---

## Networking

### "If VS Code (or anything else) already runs a server on port 6379, is starting the Redis container forbidden? How does my physical NIC even know port 6379 belongs to Docker?"

Short answer: **your NIC doesn't know anything about Docker, and yes,
it's forbidden — you can't have two things on the same host port at
once, Docker or not.**

The NIC's job is dumb on purpose: it just moves raw electrical/radio
signals into bytes and hands them up to the kernel. It has zero concept
of "port 6379 belongs to Docker" — ports don't exist at the NIC layer at
all, they're a transport-layer (TCP) concept handled entirely in
software, several layers above the NIC.

The real mechanism is **port ownership at the kernel level**:

```
                 YOUR LAPTOP'S KERNEL
  ┌─────────────────────────────────────────────────────────┐
  │                                                            │
  │   A port number (host, TCP) can be "claimed" by exactly    │
  │   ONE listener at a time. Doesn't matter what kind:        │
  │                                                            │
  │     • a native process calling bind() directly             │
  │       (redis-server, a VS Code dev server task, etc.)      │
  │     • docker-proxy / iptables DNAT rule, installed the      │
  │       moment you run `docker run -p 6379:6379 ...`          │
  │                                                            │
  │   Whichever one asks FIRST gets it. Whoever asks SECOND     │
  │   fails immediately — that's why `docker run -p 6379:6379`  │
  │   errors out with "port is already allocated" /             │
  │   "bind: address already in use" if something's already      │
  │   sitting on 6379.                                          │
  │                                                            │
  └─────────────────────────────────────────────────────────┘
```

So there's no per-packet "this one's for Docker" tag. The moment you ran
`docker run -p 6379:6379 redis`, Docker went and grabbed ownership of
host port 6379 in the kernel's routing/socket tables (via an iptables
DNAT rule, backed by a small process called `docker-proxy` that actually
holds the socket open). From that point on, *any* packet that arrives
addressed to `myIP:6379` gets handed to whatever currently owns that
port — the NIC never had to "know" it was Docker, ownership was decided
once, in advance, at bind time.

**Practical takeaway:** if something else is already using 6379 (a local
Redis install, a dev server VS Code spun up, anything), you have two
options:
- Stop that other process first, then run the container normally, or
- Map the container to a different host port and keep both running:
  `docker run -d --name rate-limiter-redis -p 6380:6379 redis:7-alpine`
  — now Redis-in-a-container is reached via `localhost:6380`, while
  whatever's on 6379 stays untouched. (Note only the *host* side changes
  here — the container still thinks it's listening on 6379 internally,
  because that's its own private namespace.)

### Scenario: someone outside your laptop hits `myIP:6379`

Two things have to be true before Docker even gets involved:
1. Your laptop's real IP (`myIP`) has to be reachable from wherever the
   request originates — same LAN, or your home router forwarding a
   public port to your laptop if it's coming from the internet. That's
   OS/router-level, Docker has no say in it.
2. Your laptop's firewall has to allow inbound traffic on 6379.

Once the packet actually lands on your laptop's **real, physical**
network card, here's the simplified flow — this is correct:

```
[Request] → [Kernel] → [iptables DNAT rule] → [dest rewritten to
             CONTAINER_IP:PORT] → [docker0 switch] → [Container]
```

Walking through each hop:

1. **Request → Kernel** — the packet physically arrives on your NIC; the
   kernel's network stack picks it up. This happens *before* any routing
   decision is made.
2. **iptables** — the kernel processes the packet through netfilter's
   `PREROUTING` chain (in the `nat` table), which happens right at the
   start, before the kernel has even decided where to route the packet.
   Docker inserted a DNAT rule here the moment you ran `-p 6379:6379`.
3. **Destination rewritten** — that rule literally rewrites the packet's
   destination-address field in place: `myIP:6379` becomes
   `172.17.0.2:6379` (the container's private IP). The packet is now,
   as far as the rest of the kernel is concerned, addressed straight at
   the container.
4. **docker0 switch** — *now* the kernel makes its routing decision,
   based on the *new* destination. `172.17.0.2` belongs to the
   `docker0` bridge's subnet, so the kernel hands the packet to that
   bridge interface. `docker0` acts like a real L2 switch: it resolves
   `172.17.0.2` to a MAC address (ARP) and forwards the frame out the
   specific virtual cable (veth) that leads to that container's network
   namespace — exactly like a physical switch delivering a frame to the
   right port.
5. **Container** — the packet arrives on the container's own `eth0`
   inside its private namespace, and `redis-server` (bound to
   `0.0.0.0:6379` *inside* that namespace) finally accepts it.

So the request never *directly* hits Redis's port. It hits your laptop's
real NIC, gets its destination rewritten in-flight, and only then gets
switched to the container. Redis itself has no idea it's being reached
"from outside" — as far as it's concerned, a connection just came in on
its bridge network, same as if another container on your laptop called
it.

### Where does `docker-proxy` fit into that flow?

It *doesn't* sit on the packet path drawn above — that whole flow is
kernel-only (netfilter + bridge), no extra process involved, which is
why it's fast. `docker-proxy` solves a different problem, sitting off to
the side:

```
docker run -p 6379:6379 redis   ← at STARTUP, not per-packet
        │
        ▼
Docker asks the kernel: bind(0.0.0.0:6379) via docker-proxy
        │
        ├─ nobody else owns it  → success → docker-proxy holds the socket
        │                                    open (as a placeholder) AND
        │                                    the iptables DNAT rule above
        │                                    gets installed
        │
        └─ something already bound it (VS Code's server, native redis,
           an earlier container) → EADDRINUSE → `docker run` fails with
           "port is already allocated"
```

Two jobs, both happening once at container-start, not per-request:
1. **Real port reservation** — `docker-proxy` is the process that
   actually calls `bind()` on the host port. That's what makes the
   "port already allocated" error possible at all — see the next
   question, iptables rules alone can't produce that error.
2. **Loopback / same-machine edge case ("hairpin NAT")** — when a
   request to `127.0.0.1:6379` originates from *the same machine* the
   container is on, pure kernel DNAT can struggle to route the reply
   back cleanly. `docker-proxy`, being a real listening process, just
   accepts that local connection directly and manually relays bytes
   into the container, sidestepping the tricky routing case entirely.

For traffic actually coming from outside (LAN/internet, the scenario
above), the iptables DNAT path handles it directly — `docker-proxy`'s
open socket mostly just sits there reserving the port and is not
usually on the hot path for that traffic.

### "For every new process on any port, does the kernel check iptables to decide success or failure?"

No — and this is worth being precise about, because it's two *separate*
gatekeeping systems, not one:

| Layer | What it governs | What enforces exclusivity |
|---|---|---|
| **Socket / `bind()` layer** | "Is anything already listening on host port 6379?" | The kernel's socket table. Exactly one listener per `(protocol, IP, port)` — a second `bind()` call gets `EADDRINUSE`. **This is the real gatekeeper.** |
| **iptables / netfilter rules** | "If a packet arrives for port 6379, where should it be redirected?" | Nothing enforces uniqueness here — you *could* have overlapping DNAT rules; the kernel just applies the first match. Rules don't "own" anything. |

So a new process (native or containerized) trying to grab port 6379
never consults iptables to ask permission — it calls `bind()`, and the
kernel's socket table either grants it or returns `EADDRINUSE`. iptables
rules are consulted *later*, per-packet, purely for "where do I send
this" — not for "who's allowed to claim this port." That's exactly why
Docker needs `docker-proxy` to do a real `bind()` in the first place:
an iptables rule alone wouldn't stop a second process from also binding
6379, and wouldn't give you a clean error either.

### "Does Docker have one network, so no two containers can ever use the same port?"

No — it's the opposite of what that implies. Two separate things are
being mixed together here, and they have different rules:

- **Container-internal port** (what the process inside the container
  binds to, e.g. `:6379`) — this lives inside that container's own
  network namespace. It is completely isolated. Ten different Redis
  containers can each bind `:6379` internally with zero conflict,
  because none of them can even see each other's namespace.
- **Host port** (the left side of `-p host:container`) — this is a real
  socket on your laptop's actual network stack. Your laptop can only
  have *one* process/mapping owning port 6379 at a time — that's a
  regular OS constraint, nothing Docker-specific. This is the only
  place a real collision can happen.

```
   Network A: "rate-limiter-net"        Network B: "other-app-net"
   bridge, subnet 172.18.0.0/16         bridge, subnet 172.19.0.0/16
  ┌─────────────────────────┐         ┌─────────────────────────┐
  │ container: redis-1       │         │ container: redis-2       │
  │ internal IP 172.18.0.2    │         │ internal IP 172.19.0.2    │
  │ listens on :6379 (fine)   │         │ listens on :6379 (fine)   │
  │                            │         │                           │
  │ published → host :6379    │         │ published → host :6380    │
  └─────────────────────────┘         └─────────────────────────┘
         ▲                                     ▲
         │                                     │
   host port 6379 (taken)               host port 6380 (taken)
```

Both containers happily use container-port `6379` — no conflict, because
that's namespace-local. The only rule is you can't publish **two
different containers to the same host port** — so `redis-2` gets mapped
to host `6380` instead, or bound to a different host IP.

### "Can Docker make many networks, with IP restrictions per network?"

First, two terms this answer leans on:

- **Subnet** — just a defined *range* of IP addresses that belong
  together, written like `172.18.0.0/16` (every address from
  `172.18.0.0` to `172.18.255.255`). Devices inside the same subnet can
  reach each other directly; devices in *different* subnets need
  something in between to connect them.
- **Bridge** — a *virtual network switch*. A real switch is the box you
  plug multiple computers' cables into so they can talk to each other;
  a Docker bridge (`docker0`, or any custom one) is the software version
  of that box, and each container gets a virtual cable (`veth`) plugged
  into it.

**Analogy:** think of a Docker network as one apartment building.
- The **subnet** is the building's address range — every room number
  that exists in that building (e.g. rooms 1–254, matching
  `172.18.0.1`–`172.18.0.254`).
- The **bridge** is the building's internal hallway/wiring — the shared
  thing that actually lets room 2 knock on room 5's door directly,
  without leaving the building.
- A *second* Docker network is a completely separate building across
  town, with its own room numbers and its own hallway. A resident in
  Building A can't just walk to Building B — there's no hallway
  connecting them — unless you explicitly give a resident a key to both
  buildings (attaching one container to two networks).

**What "without leaving the building" actually means, in network terms:**
staying inside the same subnet means delivery happens by plain Layer-2
switching — the bridge just looks up a MAC address and forwards the
frame directly, no decision-making needed. "Leaving the building" means
crossing into a *different* subnet, which requires a router (Layer 3) to
decide how to get there — an extra hop, extra rules, extra latency.
Docker doesn't even build that road by default between two separate
bridge networks — they're simply unreachable from each other unless you
explicitly connect them.

**The benefit:** two things, for free —
- **Speed/simplicity** — same-network container-to-container traffic
  never needs a routing decision, just a direct switch lookup.
- **Isolation by default** — since there's no automatic road between
  networks, putting your database on its own network means nothing
  outside that network can reach it at all, without you writing a single
  firewall rule. Grouping related containers (e.g. an app + its own
  Redis) onto one network is how you keep them reachable to each other
  and invisible to everything else.

### How do you actually connect two containers that are on different networks?

There's no "connect Network A to Network B" command — networks
themselves never talk to each other. Instead, you attach a *container*
to an additional network:

```
docker network connect network-A container-2
```

Physically, this is exactly what it sounds like: Docker creates a brand
new `veth` cable, plugs one end into **Bridge A**, and plugs the other
end into a **new network port on `container-2`** (a second interface,
`eth1`, alongside its original `eth0`). Nothing about container-2's
original connection to Bridge B is touched — it now simply has two
cables instead of one:

```
   [container-2]
      eth0   eth1  ← two separate network cards now
       │      │
     veth    veth  ← "docker network connect" added this second cable
       │      │
  [Bridge B] [Bridge A]
  (Network B) (Network A)
```

And Bridge A is a switch — container-1 and container-2's new `eth1` are
just two ordinary devices plugged into the same switch, as peers:

```
   [container-1]              [container-2 : eth1]
        │                              │
      veth                           veth
        │                              │
        └───────────[ Bridge A ]───────┘
                    (Network A)
```

**Packet flow, container-1 → container-2:**

```
[container-1 code] → [container-1's veth] → [Bridge A]
   → (ARP-resolved MAC lookup) → [container-2's eth1 veth] → [container-2's app]
```

This is plain Layer-2 switching between two devices on the same switch —
identical to two containers that were on the same network from the
start. No host involved, no port published, no NAT rewrite.

This is also *why* it doesn't contradict "different subnets need a
router between them": no cross-subnet hop actually happens here.
Container-2's `eth1` is a genuinely separate network identity, fully
inside Network A, with its own IP — container-1 is just talking to a
same-subnet neighbor. Container-2's *other* card, `eth0` on Network B,
is never involved in that conversation at all.

If neither container gets a second cable — both stay strictly
single-homed, container-1 only ever on Bridge A, container-2 only ever
on Bridge B — then reaching across genuinely requires a Layer-3 router:
something with a leg in both subnets that receives a packet on one side
and re-sends it out the other. Docker doesn't build that between two of
its own separate bridges — they stay fully isolated, no route at all.
The only thing that *can* see both subnets is the **host itself** (every
Docker network gets its own gateway IP on the host), which is exactly
what the next section covers.

### Alternative: container-1 reaches container-2 via `host-IP:host-port` instead

This is what happens if you *don't* connect them, and container-2 was
simply started with `-p host-port:container-port` — container-1 just
hits the host's published port, the same way an outside client would.

```
[container-1 code: connect to hostIP:hostPort]
        │
        ▼
[container-1's veth] → [Network A bridge] → [Network A's gateway IP]
        │        (container-1's default route sends non-local traffic
        │         to its bridge's gateway — that IS the host)
        ▼
[HOST kernel network stack]  ← this is the exact same iptables DNAT
        │                       rule from the "outside request" scenario
        ▼   rewrites dest → container-2's private IP
[Network B bridge] → (ARP/MAC lookup) → [container-2's veth]
        │
        ▼
[container-2's app]
```

So container-1 exits through its *own* network's gateway (which is
really the host), lands in the host's kernel, and gets DNAT'd right back
down into Network B — same mechanism as a real outside client, just the
"outside" here is another container on the same machine. It's a round
trip out to the host and back in, versus the direct one-hop switch in
the `docker network connect` case above — it works, but it's the slower,
more roundabout path. (This is also exactly the kind of same-machine
"hairpin" traffic that `docker-proxy`, from the earlier section, exists
partly to handle cleanly.)

Yes, both are true:

- `docker network create <name>` makes a new isolated bridge network,
  each with its own private subnet (its own IP range) and its own
  virtual bridge. Containers on Network A cannot reach containers on
  Network B unless you explicitly attach a container to both. This is
  how you'd later isolate, say, a database network from a public-facing
  one.
- Within one network, container IPs are private and auto-assigned from
  that network's subnet — not something you normally hardcode.
- The `-p` flag also supports restricting *which host IP* a published
  port answers on:
  - `-p 6379:6379` → binds `0.0.0.0:6379`, reachable from anywhere that
    can route to your laptop (LAN, or the internet if your router
    forwards it).
  - `-p 127.0.0.1:6379:6379` → binds only the loopback interface, so
    it's reachable from your laptop only, never from outside — useful
    for things you don't want to expose at all.

### Is the VM hop specific to Docker Desktop, or does Docker always avoid the real host kernel?

Specific to Docker Desktop — **not** a universal Docker fact. It
depends entirely on what you installed:

- **Native Docker Engine on Linux** (installed via `apt`/`dnf` as
  `docker-ce`, no "Desktop" app) — no VM at all. Containers run directly
  against the host's real kernel, exactly as described in the namespaces
  + cgroups section earlier. This is the "true" Docker architecture —
  cheap, fast, no extra hop.
- **Docker Desktop on Mac or Windows** — a VM is *mandatory*, not
  optional. Containers require Linux kernel features (namespaces,
  cgroups), and macOS/Windows don't have a Linux kernel at all — so
  Docker Desktop has no choice but to boot a small real Linux VM
  somewhere just to have a Linux kernel to run containers against.
- **Docker Desktop on Linux (this machine)** — this is the odd one.
  Linux *already has* a real Linux kernel sitting right there, so
  technically no VM is needed. Docker Desktop uses one anyway — that's
  a deliberate product choice (consistency with the Mac/Windows
  versions, plus extra sandboxing of the whole Docker daemon away from
  the host), not a technical requirement.

So this machine's extra VM hop is a side effect of choosing **Docker
Desktop** specifically, not something inherent to Docker or to Linux. If
this same laptop instead had plain `docker-ce` installed (no Desktop
app), there'd be no VM — containers would sit directly on the real host
kernel, one hop shorter than the diagrams above.

---

## Compose

*(to be filled in when we move from separate `docker run` commands to `docker-compose.yml`)*
