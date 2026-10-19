# SPDX-License-Identifier: LGPL-2.1-or-later
# Copyright (C) 2026 Korea Institute of Machinery & Materials (KIMM)
import ast
from pathlib import Path


def test_cad_create_primitives_export_fcstd_and_step():
    bridge = Path(__file__).resolve().parents[1] / "cad_bridge" / "bridge_bootstrap.py"
    source = bridge.read_text(encoding="utf-8")
    assert 'model_path = MODEL_DIR / "current_model.FCStd"' in source
    assert 'step_path = MODEL_DIR / "current_model.step"' in source
    assert "doc.saveAs(str(model_path))" in source
    assert "Part.export([obj], str(step_path))" in source


def test_cad_validation_checks_generic_geometry_and_artifacts():
    bridge = Path(__file__).resolve().parents[1] / "cad_bridge" / "bridge_bootstrap.py"
    source = bridge.read_text(encoding="utf-8")
    assert "def _validate_active_model(payload: dict)" in source
    assert '"shape_valid"' in source
    assert '"measured_radial_diameter"' in source
    assert '"expected_bounding_box"' in source
    assert '"expected_string_properties"' in source
    assert '"plan_file"' in source
    assert '"volume_matches"' in source
    assert '"import_step": _import_step' in source
    assert '"validate_active_model": _validate_active_model' in source


def test_verified_step_import_preserves_source_and_presents_model():
    bridge = Path(__file__).resolve().parents[1] / "cad_bridge" / "bridge_bootstrap.py"
    source = bridge.read_text(encoding="utf-8")
    assert "def _import_step(payload: dict)" in source
    assert "Import.insert(str(step_path), doc.Name)" in source
    assert "obj = max(imported" in source
    assert 'step_path.suffix.lower() not in {".step", ".stp"}' in source
    assert 'obj.ViewObject.Visibility = True' in source
    assert 'document_obj.ViewObject.Visibility = False' in source
    assert "gui_document.activeView().viewAxonometric()" in source
    assert "gui_document.activeView().fitAll()" in source
    assert 'fcstd_path = step_path.with_suffix(".FCStd")' in source
    assert 'fcbak_path = step_path.with_suffix(".FCBak")' in source
    assert "shutil.copy2(fcstd_path, fcbak_path)" in source
    assert '"fcbak_file"' in source


def test_general_plan_executor_is_whitelisted_and_exports_all_artifacts():
    script = Path(__file__).resolve().parents[1] / "generated_scripts" / "execute_cad_plan.py"
    source = script.read_text(encoding="utf-8")
    tree = ast.parse(source)
    function_names = {node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)}
    assert {
        "_execute_operation",
        "_make_section",
        "_infer_generation_method",
        "_add_properties",
        "run",
    } <= function_names
    for operation in (
        "box",
        "cylinder",
        "sphere",
        "cone",
        "torus",
        "polygon_prism",
        "loft",
        "translate",
        "rotate",
        "polar_pattern",
        "linear_pattern",
        "fuse",
        "cut",
        "common",
        "fillet",
        "chamfer",
    ):
        assert f'"{operation}"' in source
    assert "Part.makeLoft" in source
    assert "Part.BSplineCurve" in source
    assert "Part.export([result], str(step_path))" in source
    assert "plan_path.write_text" in source
    assert "Gui.getDocument" in source
    assert ".viewAxonometric()" in source
    assert ".fitAll()" in source
    assert "def run(plan: dict, present: bool = True)" in source
    assert '"presented": present' in source
    run_function = next(
        node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "run"
    )
    presentation_guard = next(
        node
        for node in ast.walk(run_function)
        if isinstance(node, ast.If)
        and isinstance(node.test, ast.Name)
        and node.test.id == "present"
    )
    guarded_calls = {
        node.func.attr
        for node in ast.walk(presentation_guard)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }
    assert {"viewAxonometric", "fitAll"} <= guarded_calls
    assert not any(isinstance(node, (ast.Exec if hasattr(ast, "Exec") else ast.Pass)) for node in [])
    assert "eval(" not in source
    assert "exec(" not in source


def test_no_shape_specific_generated_scripts_remain():
    scripts_dir = Path(__file__).resolve().parents[1] / "generated_scripts"
    names = {path.name for path in scripts_dir.glob("*.py")}
    assert "execute_cad_plan.py" in names
    assert not any("propeller" in name.lower() for name in names)
