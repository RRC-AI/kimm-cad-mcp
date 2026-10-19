# SPDX-License-Identifier: LGPL-2.1-or-later
# Copyright (C) 2026 Korea Institute of Machinery & Materials (KIMM)
"""Opt-in live check; preserves all open models and only exercises status IPC."""

import ctypes
from ctypes import wintypes
import json
from pathlib import Path
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def send_command(operation, payload=None):
    # Diagnostics must never relaunch the application if a user closes it.
    command_id = uuid.uuid4().hex
    pending = ROOT / "runtime/inbox" / f".{command_id}.tmp"
    ready = pending.with_name(f"{command_id}.json")
    pending.write_text(json.dumps({"id": command_id, "operation": operation,
                                   "payload": payload or {}}), encoding="utf-8")
    pending.replace(ready)
    reply = ROOT / "runtime/outbox" / ready.name
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        if reply.exists():
            result = json.loads(reply.read_text(encoding="utf-8"))
            reply.unlink()
            if not result.get("ok"):
                raise RuntimeError(result)
            return result
        time.sleep(0.05)
    raise TimeoutError(f"Live verification got no response: {operation}")


def snapshot():
    return send_command("run_generated_script", {"script": "check_bridge_runtime.py"})["result"]


def main():
    output = ROOT / "runtime" / "diagnostics" / "heartbeat-fix-20261009"
    output.mkdir(parents=True, exist_ok=True)
    log = Path.home() / "AppData/Local/Programs/KIMM/KIMM-CAD V26/logs/FreeCAD.log"
    offset = log.stat().st_size
    before = snapshot()
    (output / "live-before.json").write_text(json.dumps(before, indent=2), encoding="utf-8")
    reloaded = send_command("run_generated_script", {"script": "reload_cad_bridge.py"})
    after_reload = snapshot()
    assert after_reload["repair_loaded"] and after_reload["timer_active"]
    heartbeat = ROOT / "runtime" / "heartbeat.json"
    initial = json.loads(heartbeat.read_text())
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    create = kernel.CreateFileW
    create.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                       wintypes.LPVOID, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
    create.restype = wintypes.HANDLE
    close = kernel.CloseHandle
    close.argtypes = [wintypes.HANDLE]
    close.restype = wintypes.BOOL
    handle = create(str(heartbeat), 0x80000000, 0x1 | 0x2, None, 3, 0x80, None)
    if handle == ctypes.c_void_p(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        # Status reads continue during a real Windows lock, without touching CAD.
        latencies = []
        started = time.monotonic()
        while time.monotonic() - started < 1.8:
            t0 = time.monotonic()
            assert send_command("status")["connected"]
            latencies.append(time.monotonic() - t0)
        locked = snapshot()
        assert "heartbeat" in locked["io_failures"]
    finally:
        close(handle)
    time.sleep(1.2)
    after = snapshot()
    fresh = json.loads(heartbeat.read_text())
    assert after["documents"] == before["documents"]
    assert after["active_document"] == before["active_document"]
    assert after["maximized"] == before["maximized"]
    assert after["timer_active"] and not after["io_failures"]
    assert fresh["timestamp"] > initial["timestamp"]
    with log.open("rb") as stream:
        stream.seek(offset)
        added_log = stream.read().decode("utf-8", errors="replace")
    assert "Traceback" not in added_log and "PermissionError" not in added_log
    result = {"passed": True, "before": before, "after": after,
              "reload": reloaded["result"], "status_requests_during_lock": len(latencies),
              "max_status_response_seconds": max(latencies),
              "heartbeat_recovered": True, "new_error_tracebacks": 0}
    (output / "live-verification.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    (output / "verification.log").write_text(added_log, encoding="utf-8")
    print(json.dumps({key: value for key, value in result.items()
                      if key not in {"before", "after", "reload"}}, ensure_ascii=False))


if __name__ == "__main__":
    main()
