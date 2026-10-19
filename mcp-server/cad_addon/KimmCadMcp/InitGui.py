# SPDX-License-Identifier: LGPL-2.1-or-later
# Copyright (C) 2026 Korea Institute of Machinery & Materials (KIMM)
"""Automatically start the project-local RPC bridge when KIMM-CAD GUI opens."""

from pathlib import Path
import KimmCadMcpLocator


addon_dir = Path(KimmCadMcpLocator.__file__).resolve().parent
project_marker = addon_dir / "project_path.txt"
project_root = (
    Path(project_marker.read_text(encoding="utf-8").lstrip("\ufeff").strip()).resolve()
    if project_marker.is_file()
    else addon_dir.parents[1]
)
bootstrap = project_root / "cad_bridge" / "bridge_bootstrap.py"
namespace = {
    "__file__": str(bootstrap),
    "__name__": "kimm_cad_mcp_bridge_autostart",
}
exec(compile(bootstrap.read_text(encoding="utf-8"), str(bootstrap), "exec"), namespace)
