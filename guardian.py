#!/usr/bin/env python3
"""Wake-up Guardian — keeps the NEVERMIND server alive forever.

Watchdog loop:
  1. Ping /api/health every few seconds
  2. Process alive but hung  → terminate + restart
  3. Process dead            → restart
  4. Never give up (with backoff after repeated failures)

Run: python3 guardian.py
Log: data/guardian.log
"""
import os
import subprocess
import sys
import time
import urllib.request

PORT = 8317
BASE = os.path.dirname(os.path.abspath(__file__))
HEALTH = f"http://127.0.0.1:{PORT}/api/health"
LOG = os.path.join(BASE, "data", "guardian.log")
SERVER_LOG = os.path.join(BASE, "data", "server.log")
CHECK_SEC = 8
START_RETRIES_BACKOFF = 30  # seconds to wait after repeated failed starts


def log(msg: str) -> None:
    line = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    print(line, flush=True)
    try:
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass


def healthy() -> bool:
    try:
        with urllib.request.urlopen(HEALTH, timeout=3) as r:
            return r.status == 200
    except Exception:
        return False


def server_pids() -> list:
    try:
        out = subprocess.check_output(["pgrep", "-f", "python3 run.py"], text=True)
        return [p for p in out.split() if p.strip()]
    except subprocess.CalledProcessError:
        return []


def start_server() -> bool:
    log("WAKING server → python3 run.py")
    try:
        out = open(SERVER_LOG, "a")
        subprocess.Popen(
            [sys.executable, "run.py"],
            cwd=BASE,
            stdout=out,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
    except Exception as e:
        log(f"spawn failed: {e}")
        return False
    for _ in range(40):  # up to 20s to bind
        time.sleep(0.5)
        if healthy():
            log("server AWAKE and healthy ✅")
            return True
    log("server started but not yet healthy ⚠️ (will keep watching)")
    return False


def main() -> None:
    log(f"Guardian online — watching port {PORT} (check every {CHECK_SEC}s)")
    fail_streak = 0
    unhealthy_streak = 0
    while True:
        try:
            if healthy():
                unhealthy_streak = 0
                if fail_streak:
                    log("recovered after failures ✅")
                fail_streak = 0
            else:
                unhealthy_streak += 1
                # 2-strike rule: never kill/spawn on a single failed probe —
                # protects boot races where systemd/server is still starting
                if unhealthy_streak < 2:
                    time.sleep(CHECK_SEC)
                    continue
                pids = server_pids()
                if pids:
                    log(f"server unresponsive for {unhealthy_streak} checks "
                        f"(pids={pids}) → terminating hung process")
                    subprocess.run(["pkill", "-f", "python3 run.py"],
                                   stdout=subprocess.DEVNULL,
                                   stderr=subprocess.DEVNULL)
                    time.sleep(1.5)
                ok = start_server()
                unhealthy_streak = 0
                if not ok:
                    fail_streak += 1
                    if fail_streak >= 3:
                        log(f"{fail_streak} consecutive wake failures → backing off "
                            f"{START_RETRIES_BACKOFF}s")
                        time.sleep(START_RETRIES_BACKOFF)
        except Exception as e:  # guardian itself must never die
            log(f"guardian error (self-healed): {e}")
        time.sleep(CHECK_SEC)


if __name__ == "__main__":
    main()
