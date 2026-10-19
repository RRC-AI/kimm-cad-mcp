# SPDX-License-Identifier: LGPL-2.1-or-later
# Copyright (C) 2026 Korea Institute of Machinery & Materials (KIMM)
import json
import os
import time
from pathlib import Path

from kimm_cad_mcp import bridge_client


def test_bridge_alive(tmp_path, monkeypatch):
    heartbeat = tmp_path / "heartbeat.json"
    product_root = tmp_path / "KIMM-CAD V26"
    product_root.mkdir()
    launcher = product_root / "KIMM-CAD V26.exe"
    launcher.touch()
    heartbeat.write_text(
        json.dumps({"timestamp": time.time(), "pid": os.getpid(), "product_root": str(product_root)}),
        encoding="utf-8",
    )
    monkeypatch.setattr(bridge_client, "HEARTBEAT_PATH", heartbeat)
    monkeypatch.setattr(bridge_client, "find_kimm_cad", lambda: launcher)
    assert bridge_client.bridge_alive()


def test_bridge_rejects_another_cad_instance(tmp_path, monkeypatch):
    launcher = tmp_path / "V26" / "KIMM-CAD V26.exe"
    launcher.parent.mkdir()
    launcher.touch()
    heartbeat = tmp_path / "heartbeat.json"
    heartbeat.write_text(
        json.dumps({"timestamp": time.time(), "pid": os.getpid(), "product_root": str(tmp_path / "V25")}),
        encoding="utf-8",
    )
    monkeypatch.setattr(bridge_client, "HEARTBEAT_PATH", heartbeat)
    monkeypatch.setattr(bridge_client, "find_kimm_cad", lambda: launcher)
    assert not bridge_client.bridge_alive()


def test_find_kimm_cad_uses_v26_launcher(tmp_path, monkeypatch):
    launcher = tmp_path / "Programs" / "KIMM" / "KIMM-CAD V26" / "KIMM-CAD V26.exe"
    launcher.parent.mkdir(parents=True)
    launcher.touch()
    monkeypatch.delenv("KIMM_CAD_EXE", raising=False)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    assert bridge_client.find_kimm_cad() == launcher.resolve()


def test_ensure_bridge_launches_v26_launcher_without_legacy_options(tmp_path, monkeypatch):
    launcher = tmp_path / "KIMM-CAD V26.exe"
    launcher.touch()
    calls = []
    alive = iter((False, True))
    monkeypatch.setattr(bridge_client, "find_kimm_cad", lambda: launcher)
    monkeypatch.setattr(bridge_client, "bridge_alive", lambda: next(alive))
    monkeypatch.setattr(bridge_client.subprocess, "Popen", lambda args, **kwargs: calls.append((args, kwargs)))
    bridge_client.ensure_bridge(timeout=1)
    assert calls[0][0] == [str(launcher)]
    assert Path(calls[0][1]["cwd"]) == launcher.parent
