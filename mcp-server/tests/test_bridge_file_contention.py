# SPDX-License-Identifier: LGPL-2.1-or-later
# Copyright (C) 2026 Korea Institute of Machinery & Materials (KIMM)
"""Exercise the GUI bridge's file queue without importing the CAD engine."""

import ast
from contextlib import contextmanager
import ctypes
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import traceback

import pytest


@pytest.fixture
def bridge_env(tmp_path):
    source = Path(__file__).resolve().parents[1] / "cad_bridge" / "bridge_bootstrap.py"
    tree = ast.parse(source.read_text(encoding="utf-8"))
    definitions = [node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.ClassDef))
                   and node.name in {"_write_json", "Bridge"}]
    clock = SimpleNamespace(now=0.0)
    warnings, messages, calls = [], [], []

    class Timer:
        def __init__(self, parent):
            self.timeout = SimpleNamespace(connect=lambda callback: None)

        def start(self, interval):
            self.interval = interval

    qt = SimpleNamespace(QObject=object, QTimer=Timer, Slot=lambda: lambda f: f)
    env = dict(json=json, tempfile=tempfile, Path=Path, os=os, traceback=traceback,
               time=SimpleNamespace(monotonic=lambda: clock.now, time=lambda: clock.now),
               QtCore=qt, App=SimpleNamespace(Console=SimpleNamespace(
                   PrintWarning=warnings.append, PrintMessage=messages.append)),
               INBOX_DIR=tmp_path / "inbox", OUTBOX_DIR=tmp_path / "outbox",
               MODEL_DIR=tmp_path / "models", HEARTBEAT_PATH=tmp_path / "heartbeat.json")

    def execute(command):
        calls.append(command)
        return {"connected": True}

    env["_execute"] = execute
    exec(compile(ast.Module(body=definitions, type_ignores=[]), str(source), "exec"), env)
    instance = env["Bridge"]()
    return SimpleNamespace(env=env, bridge=instance, clock=clock, warnings=warnings,
                           messages=messages, calls=calls, root=tmp_path)


def enqueue(ctx, name="test"):
    path = ctx.env["INBOX_DIR"] / f"{name}.json"
    path.write_text(json.dumps({"id": name, "operation": "status"}), encoding="utf-8")
    return path


@contextmanager
def windows_reader_without_delete_share(path):
    """Reproduce an external reader denying atomic rename on Windows."""
    from ctypes import wintypes

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    create = kernel.CreateFileW
    create.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                       wintypes.LPVOID, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
    create.restype = wintypes.HANDLE
    close = kernel.CloseHandle
    close.argtypes = [wintypes.HANDLE]
    close.restype = wintypes.BOOL
    handle = create(str(path), 0x80000000, 0x1 | 0x2, None, 3, 0x80, None)
    if handle == ctypes.c_void_p(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        yield
    finally:
        close(handle)


def test_heartbeat_writes_once_per_second_but_commands_poll_immediately(bridge_env):
    ctx = bridge_env
    assert not ctx.env["HEARTBEAT_PATH"].exists()  # no recursive poll on reload
    ctx.bridge.poll()
    for tick in range(1, 5):
        ctx.clock.now = tick * 0.2
        enqueue(ctx, str(tick))
        ctx.bridge.poll()
        assert json.loads(ctx.env["HEARTBEAT_PATH"].read_text())["timestamp"] == 0
    assert len(ctx.calls) == 4
    ctx.clock.now = 1.0
    ctx.bridge.poll()
    assert json.loads(ctx.env["HEARTBEAT_PATH"].read_text())["timestamp"] == 1.0


@pytest.mark.skipif(os.name != "nt", reason="Windows file sharing semantics")
def test_real_windows_lock_preserves_json_and_recovers_without_blocking_commands(bridge_env):
    ctx = bridge_env
    heartbeat = ctx.env["HEARTBEAT_PATH"]
    ctx.bridge.poll()
    command = enqueue(ctx)
    with windows_reader_without_delete_share(heartbeat):
        # The old replace call fails exactly as it does in the live error log.
        old_temp = heartbeat.with_suffix(".tmp")
        old_temp.write_text('{"timestamp": 999}')
        with pytest.raises(PermissionError):
            old_temp.replace(heartbeat)
        old_temp.unlink()
        ctx.clock.now = 1.0
        ctx.bridge.poll()
        assert len(ctx.calls) == 1
        assert not command.exists()
        assert json.loads(heartbeat.read_text())["timestamp"] == 0
        assert not ctx.warnings
        assert not list(ctx.root.glob("*.tmp"))
    ctx.clock.now = 1.2
    ctx.bridge.poll()
    assert json.loads(heartbeat.read_text())["timestamp"] == 1.2
    assert not ctx.bridge._io_failures


def test_persistent_failure_warns_once_and_reports_recovery(bridge_env):
    ctx = bridge_env
    write = ctx.env["_write_json"]

    def denied(path, value):
        if path == ctx.env["HEARTBEAT_PATH"]:
            raise PermissionError("denied")
        write(path, value)

    ctx.env["_write_json"] = denied
    for tick in range(500):
        ctx.clock.now = tick * 0.2
        ctx.bridge.poll()
    assert len(ctx.warnings) == 1
    ctx.env["_write_json"] = write
    ctx.bridge.poll()
    assert len(ctx.messages) == 1
    assert not ctx.bridge._io_failures


def test_response_write_retry_never_reexecutes_command(bridge_env):
    ctx = bridge_env
    write = ctx.env["_write_json"]
    command = enqueue(ctx)

    def denied(path, value):
        if path.parent == ctx.env["OUTBOX_DIR"]:
            raise PermissionError("response locked")
        write(path, value)

    ctx.env["_write_json"] = denied
    for _ in range(5):
        ctx.bridge.poll()
    assert len(ctx.calls) == 1
    assert command.exists()
    ctx.env["_write_json"] = write
    ctx.bridge.poll()
    assert not command.exists()
    assert len(ctx.calls) == 1
    assert json.loads((ctx.env["OUTBOX_DIR"] / "test.json").read_text())["ok"]


def test_cleanup_retry_does_not_republish_consumed_reply(bridge_env, monkeypatch):
    ctx = bridge_env
    command = enqueue(ctx)
    unlink = Path.unlink

    def denied(path, *args, **kwargs):
        if path == command:
            raise PermissionError("command still open")
        return unlink(path, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", denied)
    ctx.bridge.poll()
    reply = ctx.env["OUTBOX_DIR"] / "test.json"
    reply.unlink()
    ctx.bridge.poll()
    assert not reply.exists()
    monkeypatch.setattr(Path, "unlink", unlink)
    ctx.bridge.poll()
    assert not command.exists()
    assert not reply.exists()
    assert len(ctx.calls) == 1


def test_reentrant_poll_does_not_execute_same_command_twice(bridge_env):
    ctx = bridge_env
    enqueue(ctx)

    def execute(command):
        ctx.calls.append(command)
        ctx.bridge.poll()
        return {"connected": True}

    ctx.env["_execute"] = execute
    ctx.bridge.poll()
    assert len(ctx.calls) == 1


def test_command_error_is_still_returned_with_traceback(bridge_env):
    ctx = bridge_env
    enqueue(ctx)

    def execute(command):
        raise ValueError("invalid geometry")

    ctx.env["_execute"] = execute
    ctx.bridge.poll()
    reply = json.loads((ctx.env["OUTBOX_DIR"] / "test.json").read_text())
    assert not reply["ok"]
    assert reply["error"] == "invalid geometry"
    assert "ValueError" in reply["traceback"]


def test_command_read_contention_defers_execution(bridge_env, monkeypatch):
    ctx = bridge_env
    command = enqueue(ctx)
    read = Path.read_text

    def denied(path, *args, **kwargs):
        if path == command:
            raise PermissionError("command locked")
        return read(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", denied)
    ctx.bridge.poll()
    assert not ctx.calls
    assert command.exists()
    monkeypatch.setattr(Path, "read_text", read)
    ctx.bridge.poll()
    assert len(ctx.calls) == 1
    assert not command.exists()
