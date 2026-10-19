# SPDX-License-Identifier: LGPL-2.1-or-later
# Copyright (C) 2026 Korea Institute of Machinery & Materials (KIMM)
"""File-queue client for the bridge running inside KIMM-CAD."""

from __future__ import annotations

import json
import os
import subprocess
import time
import uuid
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
RUNTIME_DIR = PROJECT_ROOT / "runtime"
INBOX_DIR = RUNTIME_DIR / "inbox"
OUTBOX_DIR = RUNTIME_DIR / "outbox"
HEARTBEAT_PATH = RUNTIME_DIR / "heartbeat.json"
BOOTSTRAP_PATH = PROJECT_ROOT / "cad_bridge" / "bridge_bootstrap.py"


def find_kimm_cad() -> Path:
    configured = os.environ.get("KIMM_CAD_EXE")
    if configured:
        candidate = Path(configured).expanduser()
        if not candidate.is_file():
            raise FileNotFoundError(f"KIMM_CAD_EXE 실행 파일을 찾지 못했습니다: {candidate}")
        return candidate.resolve()
    candidates = [
        Path(os.environ.get("LOCALAPPDATA", "")) / "Programs/KIMM/KIMM-CAD V26/KIMM-CAD V26.exe",
        Path(os.environ.get("ProgramFiles", "C:/Program Files")) / "KIMM/KIMM-CAD V26/KIMM-CAD V26.exe",
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
    raise FileNotFoundError(
        "KIMM-CAD V26 실행 파일을 찾지 못했습니다. KIMM_CAD_EXE에 KIMM-CAD V26.exe 경로를 지정하세요."
    )


def bridge_alive(max_age_seconds: float = 3.0) -> bool:
    try:
        data = json.loads(HEARTBEAT_PATH.read_text(encoding="utf-8"))
        expected_root = find_kimm_cad().parent.resolve()
        actual_root = Path(data["product_root"]).resolve()
        return (
            os.path.normcase(str(actual_root)) == os.path.normcase(str(expected_root))
            and _pid_alive(int(data["pid"]))
            and time.time() - float(data["timestamp"]) <= max_age_seconds
        )
    except (OSError, TypeError, ValueError, KeyError, json.JSONDecodeError):
        return False


def _pid_alive(pid: int) -> bool:
    if os.name != "nt":
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False
    import ctypes

    process = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)
    if not process:
        return False
    ctypes.windll.kernel32.CloseHandle(process)
    return True


def ensure_bridge(timeout: float = 30.0) -> None:
    if bridge_alive():
        return
    exe = find_kimm_cad()
    subprocess.Popen(
        [str(exe)],
        cwd=str(exe.parent),
        creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
    )
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if bridge_alive():
            return
        time.sleep(0.25)
    raise TimeoutError(
        "KIMM-CAD 브리지가 시작되지 않았습니다. KIMM-CAD의 Python 콘솔/Report view에서 오류를 확인하세요."
    )


def send_command(operation: str, payload: dict[str, Any] | None = None, timeout: float = 20.0) -> dict[str, Any]:
    ensure_bridge()
    INBOX_DIR.mkdir(parents=True, exist_ok=True)
    OUTBOX_DIR.mkdir(parents=True, exist_ok=True)
    command_id = uuid.uuid4().hex
    command = {"id": command_id, "operation": operation, "payload": payload or {}}
    pending = INBOX_DIR / f".{command_id}.tmp"
    ready = INBOX_DIR / f"{command_id}.json"
    pending.write_text(json.dumps(command, ensure_ascii=False), encoding="utf-8")
    pending.replace(ready)

    response_path = OUTBOX_DIR / f"{command_id}.json"
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if response_path.exists():
            response = json.loads(response_path.read_text(encoding="utf-8"))
            response_path.unlink(missing_ok=True)
            if not response.get("ok"):
                raise RuntimeError(response.get("error", "KIMM-CAD 명령 실패"))
            return response
        time.sleep(0.05)
    raise TimeoutError(f"KIMM-CAD 응답 시간 초과: {operation}")
