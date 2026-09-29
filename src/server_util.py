"""Port helpers for the local web UI."""

from __future__ import annotations

import os
import socket
import subprocess
import sys


def can_bind(host: str, port: int) -> bool:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((host, port))
        return True
    except OSError:
        return False
    finally:
        sock.close()


def free_port_on_windows(port: int) -> list[int]:
    """Stop processes listening on *port*. Returns PIDs that were targeted."""
    if sys.platform != "win32":
        return []
    script = (
        f"$p = Get-NetTCPConnection -LocalPort {port} -State Listen -ErrorAction SilentlyContinue "
        "| Select-Object -ExpandProperty OwningProcess -Unique; "
        "if ($p) { $p | ForEach-Object { $_ } }"
    )
    result = subprocess.run(
        ["powershell", "-NoProfile", "-Command", script],
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    pids: list[int] = []
    for line in result.stdout.splitlines():
        line = line.strip()
        if line.isdigit():
            pids.append(int(line))
    stopped: list[int] = []
    current = os.getpid()
    for pid in pids:
        if pid == current:
            continue
        print(f"[server] Stopping stale process PID {pid} on port {port}…")
        subprocess.run(
            ["taskkill", "/PID", str(pid), "/F"],
            capture_output=True,
            check=False,
        )
        stopped.append(pid)
    return stopped


def ensure_port_available(host: str, port: int, *, auto_free: bool = True) -> None:
    import time

    if can_bind(host, port):
        return

    print(f"[server] Port {port} is already in use on {host}.", flush=True)
    if auto_free:
        for attempt in range(3):
            freed = free_port_on_windows(port)
            if freed:
                print(
                    f"[server] Stopped PID(s) on port {port}: {', '.join(map(str, freed))}",
                    flush=True,
                )
            time.sleep(1.0)
            if can_bind(host, port):
                print(f"[server] Port {port} is ready.", flush=True)
                return
            print(f"[server] Port {port} still busy (retry {attempt + 1}/3)…", flush=True)

    raise RuntimeError(
        f"Port {port} is in use. Stop the old Discovery Engine server, then run:\n"
        f"  py -3 -m src.web_app\n"
        f"PowerShell: Get-NetTCPConnection -LocalPort {port} | "
        f"ForEach-Object {{ Stop-Process -Id $_.OwningProcess -Force }}"
    )
