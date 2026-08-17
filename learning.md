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

*(to be filled in as we create the Redis and Django containers)*

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

### One more wrinkle specific to this machine

We're running **Docker Desktop**, not the native Linux Docker engine.
Docker Desktop actually runs the daemon and all containers inside a
small Linux VM, even on Linux — so there's technically one more hop
(laptop → Desktop's VM → bridge → container) between "physical NIC" and
the bridge network shown above. The port-forwarding logic is the same
concept, Docker Desktop just also proxies the port from the VM boundary
back out to your real laptop NIC so it's transparent to us.

---

## Compose

*(to be filled in when we move from separate `docker run` commands to `docker-compose.yml`)*
