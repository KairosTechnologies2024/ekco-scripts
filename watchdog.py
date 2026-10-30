#!/usr/bin/env python3
"""
External watchdog for EKCO Docker services.

Polls `docker compose ps` every 30 seconds. If any service is unhealthy
(frozen script, stale heartbeat) or exited (crashed), it restarts that
service automatically.

Run this on the host machine (outside Docker):
    python watchdog.py

Prerequisites:
- Docker Desktop must be running
- docker compose must be available on PATH
- Run from the directory containing docker-compose.yml
"""

import subprocess
import time
import sys
import os
from datetime import datetime

COMPOSE_FILE = "docker-compose.yml"
POLL_INTERVAL = 30  # seconds between checks
LOG_FILE = "watchdog.log"


def log(message):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] {message}"
    print(line, flush=True)
    try:
        with open(LOG_FILE, "a") as f:
            f.write(line + "\n")
    except Exception:
        pass


def run_cmd(args):
    """Run a command and return (returncode, stdout, stderr)."""
    try:
        result = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=30,
        )
        return result.returncode, result.stdout.strip(), result.stderr.strip()
    except subprocess.TimeoutExpired:
        return -1, "", "command timed out"
    except Exception as e:
        return -1, "", str(e)


def get_service_status():
    """
    Return a dict: {service_name: (status, health)}
    Parses `docker compose ps --format json` output.
    """
    rc, stdout, stderr = run_cmd(
        ["docker", "compose", "-f", COMPOSE_FILE, "ps", "--format", "json"]
    )
    if rc != 0:
        log(f"ERROR: docker compose ps failed: {stderr}")
        return {}

    import json

    services = {}
    if not stdout:
        return services

    # docker compose ps --format json outputs one JSON object per line
    for line in stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
            name = obj.get("Name", "")
            state = obj.get("State", "")
            health = obj.get("Health", "")
            services[name] = (state, health)
        except json.JSONDecodeError:
            continue

    return services


def restart_service(service_name):
    log(f"Restarting unhealthy/exited service: {service_name}")
    rc, stdout, stderr = run_cmd(
        ["docker", "compose", "-f", COMPOSE_FILE, "restart", service_name]
    )
    if rc == 0:
        log(f"Successfully restarted {service_name}")
    else:
        log(f"ERROR restarting {service_name}: {stderr}")


def main():
    if not os.path.exists(COMPOSE_FILE):
        log(f"ERROR: {COMPOSE_FILE} not found. Run this from the project directory.")
        sys.exit(1)

    log(f"External watchdog started. Polling every {POLL_INTERVAL}s.")
    log(f"Watching compose file: {COMPOSE_FILE}")

    while True:
        services = get_service_status()

        if not services:
            log("No services found or unable to query Docker. Retrying...")
        else:
            for name, (state, health) in sorted(services.items()):
                # Health is "healthy", "unhealthy", or "" (no healthcheck)
                # State is "running", "exited", "restarting", etc.
                needs_restart = False
                reason = ""

                if health == "unhealthy":
                    needs_restart = True
                    reason = "unhealthy (stale heartbeat or frozen)"
                elif state != "running":
                    needs_restart = True
                    reason = f"state is '{state}' (crashed or stopped)"

                if needs_restart:
                    log(f"Service '{name}' needs restart: {reason}")
                    restart_service(name)
                else:
                    log(f"Service '{name}' OK (state={state}, health={health})")

        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log("Watchdog stopped by user.")