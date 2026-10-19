# SPDX-License-Identifier: LGPL-2.1-or-later
# Copyright (C) 2026 Korea Institute of Machinery & Materials (KIMM)
"""Reload the project-local KIMM-CAD bridge without closing user documents."""

from __future__ import annotations

from pathlib import Path


def run():
    """Execute the current bridge bootstrap; it replaces only the prior polling timer."""
    project_root = Path(__file__).resolve().parents[1]
    bootstrap = project_root / "cad_bridge" / "bridge_bootstrap.py"
    namespace = {
        "__file__": str(bootstrap),
        "__name__": "kimm_cad_mcp_bridge_reload",
    }
    exec(compile(bootstrap.read_text(encoding="utf-8"), str(bootstrap), "exec"), namespace)
    return {"reloaded": True, "bootstrap_path": str(bootstrap)}
