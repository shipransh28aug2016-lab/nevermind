# WAKE protocol — how NEVERMIND stays alive (never ask twice)

## Root cause (why you kept having to ask)

The sandbox **sleeps between sessions and kills every background process** —
server, guardian, everything. The preview then shows a dead page until
something re-binds port 8317 *and* the port is re-announced to the platform.

## The 5-layer auto-wake system (all installed & proven)

| Layer | What it is | Scope | Proof |
|---|---|---|---|
| **L1 systemd** | `nevermind.service` + `nevermind-guardian.service` — both `enabled` at boot, `Restart=always` | Survives sandbox reboot; revives crashes; takes over port the moment it frees (ExecStartPre wait-loop) | **Kill-test: revived in 4s, owned by systemd (MainPID verified)** |
| **L2 profile hook** | `~/.profile` — fires on every login shell (`bash -l`), skips platform `run.cmd` wrappers | Any agent/tool shell auto-spawns the server if port closed (flock-guarded, ~3ms when healthy) | **Spawned the server twice during routine commands; wake.log entry** |
| **L3 keeper** | `keeper.sh` (tracked process) — sleeps while port healthy, starts server if it frees | Keeps a live process for the preview handle all session | running now |
| **L4 guardian** | `guardian.py` — health probe every 8s, 2-strike hang detection, restart w/ backoff | Catches hangs that systemd can't see | kill-test earlier (turn 4) |
| **L5 in-app banner** | UI polls `/api/health`, auto-reconnects SSE + refreshes | Browser-side instant recovery, "☀️ awake" toast | built into index.html |

## My per-turn wake SOP (for the agent)

When the user asks to see the preview (or returns after a sleep):

```bash
# 1. If systemd currently owns the port, free it so we can re-announce:
sudo systemctl stop nevermind.service      # only if port already healthy
# 2. Re-announce preview: start_process → python3 run.py  (expect new_ports:[8317])
# 3. Re-arm takeover (MUST be --no-block; ExecStartPre waits for port-free):
sudo systemctl start --no-block nevermind.service
# 4. Start tracked keeper: start_process → bash keeper.sh
# 5. Verify: UI HTTP 200 + /api/health + systemctl is-active nevermind
```

Kill-test proof pattern (safe, self-healing):
```bash
pkill -f "python3 [r]un.py"   # bracket trick — never match your own shell
sleep 5; curl -s localhost:8317/api/health   # systemd revives ≤5s
```

## Why each piece exists

- `ExecStartPre` wait-loop in `nevermind.service` → systemd NEVER bind-races a
  live instance; it waits, then takes over. No restart loops.
- `TimeoutStartSec=0` on `nevermind.service` → the wait-loop may run ~600s;
  systemd's default 90s start timeout was SIGTERMed it (Result=timeout) and
  forced an auto-restart churn with EADDRINUSE crashes. Infinite start
  timeout = patient, silent takeover. (Found live during the ETP fix.)
- `run.cmd` skip in `~/.profile` → the hook never steals the bind from
  `start_process` wrappers (this bug was found live and fixed).
- 2-strike rule in guardian → never kills a server that is still booting.
- `--no-block` on `systemctl start` → tool commands never hang on the wait-loop.
