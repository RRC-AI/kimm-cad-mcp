# SPDX-License-Identifier: LGPL-2.1-or-later
# Copyright (C) 2026 Korea Institute of Machinery & Materials (KIMM)
from pathlib import Path


def test_server_exposes_general_plan_capability_and_verified_workflows():
    server = Path(__file__).resolve().parents[1] / "src" / "kimm_cad_mcp" / "server.py"
    source = server.read_text(encoding="utf-8")
    assert "PLAN_OPERATIONS" in source
    assert "CAD_PLAN_SCHEMA" in source
    assert "def cad_get_plan_schema()" in source
    assert "def cad_execute_verified_plan(plan: dict, finalize: bool = True)" in source
    assert '"present": finalize' in source
    assert "finalize=false" in source
    assert "def cad_create_verified_basic_shape(" in source
    assert "def cad_import_verified_step(" in source
    assert '"import_step"' in source
    assert '"require_backup_file": True' in source
    assert 'result["fcbak_path"]' in source
    assert "def cad_validate_active_model(" in source
    assert '"execute_cad_plan.py"' in source
    assert '"require_plan_file": True' in source
    assert "arbitrary Python is rejected" in source
    assert "def cad_create_three_blade_propeller(" not in source
    assert "PROPELLER_PRESETS" not in source
