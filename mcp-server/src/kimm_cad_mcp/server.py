# SPDX-License-Identifier: LGPL-2.1-or-later
# Copyright (C) 2026 Korea Institute of Machinery & Materials (KIMM)
"""MCP tools for verified, declarative KIMM-CAD modeling."""

from __future__ import annotations

import os
import re

from mcp.server.fastmcp import FastMCP

from .bridge_client import send_command
from .parser import parse_shape_request
from .strategy import select_generation_method


PLAN_OPERATIONS = (
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
)

CAD_PLAN_SCHEMA = {
    "purpose": "Compose arbitrary supported geometry without executing model-generated Python.",
    "units": "All coordinates, lengths, radii, and tolerances are millimetres; angles are degrees.",
    "top_level": {
        "name": "safe document name",
        "object_name": "safe final KIMM-CAD object name",
        "label": "display label",
        "artifact_stem": "safe FCStd/STEP/CAD-plan filename stem",
        "operations": "ordered list of 1 to 64 operations",
        "result": "id of the final operation",
        "properties": "optional typed metadata copied to the final object",
        "validation": "required expected topology, dimensions, and repetition counts",
    },
    "operations": {
        "box": {"required": ["id", "op", "length", "width", "height"], "optional": ["base", "axis"]},
        "cylinder": {"required": ["id", "op", "radius", "height"], "optional": ["base", "axis"]},
        "sphere": {"required": ["id", "op", "radius"], "optional": ["center"]},
        "cone": {"required": ["id", "op", "radius1", "radius2", "height"], "optional": ["base", "axis"]},
        "torus": {"required": ["id", "op", "major_radius", "minor_radius"], "optional": ["center", "axis"]},
        "polygon_prism": {
            "required": ["id", "op", "points:[[u,v],...]", "vector:[x,y,z]"],
            "optional": ["origin", "plane:xy|xz|yz", "rotation_deg"],
        },
        "loft": {
            "required": ["id", "op", "sections"],
            "optional": ["solid=true", "ruled=false"],
            "section_profiles": {
                "airfoil": ["origin", "plane", "chord", "thickness", "rotation_deg"],
                "ellipse": ["origin", "plane", "width", "height", "rotation_deg"],
                "rectangle": ["origin", "plane", "width", "height", "rotation_deg"],
                "polygon": ["origin", "plane", "points:[[u,v],...]", "rotation_deg"],
            },
        },
        "translate": {"required": ["id", "op", "source", "vector"]},
        "rotate": {"required": ["id", "op", "source", "angle_deg"], "optional": ["center", "axis"]},
        "polar_pattern": {
            "required": ["id", "op", "source", "count"],
            "optional": ["center", "axis", "total_angle_deg=360"],
        },
        "linear_pattern": {"required": ["id", "op", "source", "count", "step"]},
        "fuse": {"required": ["id", "op", "sources:[id,...]"], "optional": ["refine=true"]},
        "cut": {"required": ["id", "op", "base", "tools:[id,...]"], "optional": ["refine=true"]},
        "common": {"required": ["id", "op", "sources:[id,...]"], "optional": ["refine=true"]},
        "fillet": {"required": ["id", "op", "source", "radius"], "optional": ["edge_indices"]},
        "chamfer": {"required": ["id", "op", "source", "radius"], "optional": ["edge_indices"]},
    },
    "property": {
        "shape": {"name": "SafeName", "type": "length|float|integer|angle|string", "value": "value"},
        "optional": ["group"],
    },
    "validation": {
        "expected_solid_count": "positive integer; normally 1",
        "tolerance": "positive millimetre tolerance",
        "radial_diameter_xy": "optional diameter measured from the global Z axis",
        "bounding_box": "optional subset of {x,y,z} lengths",
        "pattern_counts": "optional {pattern_operation_id: expected_count}",
    },
    "rules": [
        "Operation ids must be unique safe identifiers.",
        "An operation may reference only ids created earlier in the same plan.",
        "Use loft for changing cross-sections and polar/linear pattern for repetition.",
        "Use fuse/cut/common for composition and set result to the final operation id.",
        "Declare every user-requested dimension as a typed property and validation target when measurable.",
        "Do not include Python, file paths, imports, expressions, or unlisted operations.",
    ],
    "execution": {
        "intermediate": "Call cad_execute_verified_plan with finalize=false for trial, probe, or intermediate plans.",
        "final": "Call cad_execute_verified_plan with finalize=true only for the final user-facing plan.",
    },
    "minimal_example": {
        "name": "VerifiedBox",
        "object_name": "BoxResult",
        "artifact_stem": "verified_box",
        "operations": [{"id": "body", "op": "box", "length": 40, "width": 30, "height": 20}],
        "result": "body",
        "properties": [
            {"name": "Length", "type": "length", "value": 40},
            {"name": "Width", "type": "length", "value": 30},
            {"name": "Height", "type": "length", "value": 20},
        ],
        "validation": {"expected_solid_count": 1, "bounding_box": {"x": 40, "y": 30, "z": 20}, "tolerance": 0.01},
    },
}


def _http_port() -> int:
    raw = os.environ.get("KIMM_CAD_MCP_PORT", "8012")
    try:
        port = int(raw)
    except ValueError as exc:
        raise ValueError(f"KIMM_CAD_MCP_PORT must be an integer, got {raw!r}.") from exc
    if not 1 <= port <= 65535:
        raise ValueError(f"KIMM_CAD_MCP_PORT must be between 1 and 65535, got {port}.")
    return port


mcp = FastMCP(
    "kimm-cad",
    instructions=(
        "Operate KIMM-CAD through verified declarative plans. Use millimetres, call "
        "cad_get_plan_schema before composing unfamiliar or complex geometry, never execute "
        "model-generated Python, and never call cad_clear without an explicit user request. "
        "For trial or intermediate plans call cad_execute_verified_plan with finalize=false; "
        "use finalize=true only for the final user-facing plan so the camera is fitted once."
    ),
    host=os.environ.get("KIMM_CAD_MCP_HOST", "127.0.0.1"),
    port=_http_port(),
    streamable_http_path="/mcp",
)


def _validated_workflow(creation: dict, validation_payload: dict, workflow: list[str]) -> dict:
    validation = send_command("validate_active_model", validation_payload, timeout=30.0)
    if not validation.get("passed"):
        failed = [check for check in validation.get("checks", []) if not check.get("passed")]
        raise RuntimeError(f"KIMM-CAD validation failed: {failed}")
    status = send_command("status")
    return {
        "passed": True,
        "workflow": workflow,
        "creation": creation,
        "validation": validation,
        "status": status,
    }


def _validate_plan_structure(plan: dict) -> None:
    if not isinstance(plan, dict):
        raise ValueError("plan must be a JSON object.")
    operations = plan.get("operations")
    if not isinstance(operations, list) or not 1 <= len(operations) <= 64:
        raise ValueError("plan.operations must contain 1 to 64 operations.")
    known_ids = set()
    for index, operation in enumerate(operations):
        if not isinstance(operation, dict):
            raise ValueError(f"plan.operations[{index}] must be an object.")
        operation_id = str(operation.get("id", ""))
        operation_name = str(operation.get("op", "")).lower()
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,63}", operation_id):
            raise ValueError(f"plan.operations[{index}].id is invalid.")
        if operation_id in known_ids:
            raise ValueError(f"Duplicate operation id {operation_id!r}.")
        if operation_name not in PLAN_OPERATIONS:
            raise ValueError(f"Unsupported operation {operation_name!r}.")
        known_ids.add(operation_id)
    if str(plan.get("result", "")) not in known_ids:
        raise ValueError("plan.result must reference an operation id.")
    validation = plan.get("validation")
    if not isinstance(validation, dict) or "expected_solid_count" not in validation:
        raise ValueError("plan.validation must include expected_solid_count.")


def _plan_properties(plan: dict) -> tuple[dict[str, float], dict[str, str]]:
    numeric: dict[str, float] = {}
    strings: dict[str, str] = {}
    for index, spec in enumerate(plan.get("properties", []) or []):
        if not isinstance(spec, dict):
            raise ValueError(f"plan.properties[{index}] must be an object.")
        name = str(spec.get("name", ""))
        kind = str(spec.get("type", "")).lower()
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,63}", name):
            raise ValueError(f"plan.properties[{index}].name is invalid.")
        if kind == "string":
            strings[name] = str(spec.get("value", ""))
        elif kind in {"length", "float", "integer", "angle"}:
            numeric[name] = float(spec.get("value"))
        else:
            raise ValueError(f"plan.properties[{index}].type is unsupported.")
    return numeric, strings


def _create_verified_basic_shape_workflow(request: str, name: str) -> dict:
    parsed = parse_shape_request(request)
    creation = send_command(
        "create_primitive",
        {"shape": parsed.shape, "params": parsed.params, "name": name.strip()},
    )
    result = _validated_workflow(
        creation,
        {
            "object_name": creation.get("object", ""),
            "expected_solid_count": 1,
            "expected_properties": parsed.params,
            "tolerance": 0.01,
            "require_step_file": True,
        },
        ["create", "validate", "status"],
    )
    result["capability"] = f"basic_shape:{parsed.shape}"
    result["dimensions_mm"] = parsed.params
    return result


@mcp.tool()
def cad_get_capabilities() -> dict:
    """List the verified basic-shape and general declarative-plan capabilities."""
    return {
        "basic_shapes": {
            "box": ["length", "width", "height"],
            "cylinder": ["radius or diameter", "height"],
            "sphere": ["radius or diameter"],
            "flange": ["outer_diameter", "inner_diameter", "thickness"],
        },
        "basic_shape_tool": "cad_create_verified_basic_shape",
        "general_geometry": {
            "schema_tool": "cad_get_plan_schema",
            "execution_tool": "cad_execute_verified_plan",
            "presentation_control": (
                "Use finalize=false for intermediate plans and finalize=true only for the final plan."
            ),
            "operations": list(PLAN_OPERATIONS),
            "profiles": ["airfoil", "ellipse", "rectangle", "polygon"],
        },
        "file_display": {
            "tool": "cad_import_verified_step",
            "formats": ["STEP", "STP"],
            "behavior": "Import the exact source shape, save FCStd and FCBak beside it, validate it, make it visible, and fit an axonometric view.",
        },
        "artifacts": ["FCStd", "STEP", "CAD plan JSON"],
        "completion_contract": [
            "shape is non-null and valid",
            "expected solid and pattern counts match",
            "volume is positive",
            "requested properties and measurable dimensions match within tolerance",
            "object remains visible in KIMM-CAD",
            "FCStd, STEP, and CAD plan files exist and are non-empty",
            "final connected KIMM-CAD status is returned",
        ],
        "safety": "Only whitelisted declarative operations execute; arbitrary Python is rejected.",
    }


@mcp.tool()
def cad_get_plan_schema() -> dict:
    """Return the complete schema for composing general verified CAD plans.

    Call this before creating unfamiliar, multi-part, repeated, Boolean, swept, or
    Loft-based geometry. Build a plan from the user's explicit dimensions and then pass
    that plan unchanged to cad_execute_verified_plan.
    """
    return CAD_PLAN_SCHEMA


@mcp.tool()
def cad_execute_verified_plan(plan: dict, finalize: bool = True) -> dict:
    """Execute and validate a CAD plan; fit the view only when finalize is true.

    The plan may combine whitelisted primitives, Loft sections, transforms, patterns,
    Booleans, fillets, and chamfers. It cannot contain Python or arbitrary commands.
    Use finalize=False for trial, probe, or intermediate plans, and finalize=True only
    for the final user-facing plan so KIMM-CAD does not repeatedly resize the view.
    Do not report completion unless this tool returns top-level passed=true.
    """
    _validate_plan_structure(plan)
    numeric_properties, string_properties = _plan_properties(plan)
    creation = send_command(
        "run_generated_script",
        {
            "script": "execute_cad_plan.py",
            "arguments": {"plan": plan, "present": finalize},
        },
        timeout=180.0,
    )
    created = creation.get("result", {})
    plan_validation = plan["validation"]
    result = _validated_workflow(
        creation,
        {
            "object_name": created.get("object", ""),
            "expected_solid_count": int(plan_validation["expected_solid_count"]),
            "expected_radial_diameter": float(plan_validation.get("radial_diameter_xy", 0.0)),
            "expected_bounding_box": plan_validation.get("bounding_box", {}) or {},
            "expected_properties": numeric_properties,
            "expected_string_properties": string_properties,
            "tolerance": float(plan_validation.get("tolerance", 1.0)),
            "require_step_file": True,
            "require_plan_file": True,
        },
        ["analyze", "execute_plan", "validate", "status"],
    )
    result["capability"] = "general_declarative_cad_plan"
    result["plan_summary"] = {
        "name": plan.get("name"),
        "operation_count": len(plan["operations"]),
        "operation_types": [str(operation["op"]).lower() for operation in plan["operations"]],
        "result": plan["result"],
    }
    result["finalized"] = finalize
    return result


@mcp.tool()
def cad_analyze(request: str) -> dict:
    """Analyze a CAD request and choose a template, pattern, or Loft/Sweep plan."""
    return select_generation_method(request).to_dict()


@mcp.tool()
def cad_create(request: str, name: str = "") -> dict:
    """Compatibility alias that creates and verifies a supported basic shape."""
    return _create_verified_basic_shape_workflow(request, name)


@mcp.tool()
def cad_create_verified_basic_shape(request: str, name: str = "") -> dict:
    """Create, export, validate, and display a box, cylinder, sphere, or flange."""
    return _create_verified_basic_shape_workflow(request, name)


@mcp.tool()
def cad_import_verified_step(
    step_path: str,
    object_name: str = "",
    expected_solid_count: int = 1,
    expected_volume_mm3: float = 0.0,
    volume_tolerance_mm3: float = 0.01,
) -> dict:
    """Import the exact STEP file into KIMM-CAD, display it, and independently validate it.

    The source must be an existing non-empty local .step or .stp file. The imported
    object remains visible, the view is set to axonometric and fitted, and FCStd and FCBak
    files are saved beside the STEP source. Do not report completion unless this tool returns
    top-level passed=true.
    """
    if expected_solid_count < 1:
        raise ValueError("expected_solid_count must be a positive integer.")
    if expected_volume_mm3 < 0:
        raise ValueError("expected_volume_mm3 cannot be negative.")
    if volume_tolerance_mm3 <= 0:
        raise ValueError("volume_tolerance_mm3 must be positive.")

    creation = send_command(
        "import_step",
        {
            "step_path": step_path,
            "object_name": object_name.strip(),
        },
        timeout=600.0,
    )
    result = _validated_workflow(
        creation,
        {
            "object_name": creation.get("object", ""),
            "expected_solid_count": expected_solid_count,
            "expected_volume_mm3": expected_volume_mm3,
            "volume_tolerance_mm3": volume_tolerance_mm3,
            "tolerance": 0.01,
            "require_step_file": True,
            "require_backup_file": True,
        },
        ["import_step", "display", "validate", "status"],
    )
    result["capability"] = "verified_step_import"
    result["source_step_path"] = creation.get("step_path")
    result["fcstd_path"] = creation.get("fcstd_path")
    result["fcbak_path"] = creation.get("fcbak_path")
    return result


@mcp.tool()
def cad_validate_active_model(
    object_name: str = "",
    expected_solid_count: int = 1,
    expected_radial_diameter: float = 0.0,
    expected_bounding_box: dict[str, float] | None = None,
    expected_properties: dict[str, float] | None = None,
    expected_string_properties: dict[str, str] | None = None,
    expected_volume_mm3: float = 0.0,
    volume_tolerance_mm3: float = 0.01,
    tolerance: float = 1.0,
    require_step_file: bool = True,
    require_backup_file: bool = False,
) -> dict:
    """Independently validate active geometry, generic properties, dimensions, and artifacts."""
    return send_command(
        "validate_active_model",
        {
            "object_name": object_name.strip(),
            "expected_solid_count": expected_solid_count,
            "expected_radial_diameter": expected_radial_diameter,
            "expected_bounding_box": expected_bounding_box or {},
            "expected_properties": expected_properties or {},
            "expected_string_properties": expected_string_properties or {},
            "expected_volume_mm3": expected_volume_mm3,
            "volume_tolerance_mm3": volume_tolerance_mm3,
            "tolerance": tolerance,
            "require_step_file": require_step_file,
            "require_backup_file": require_backup_file,
        },
        timeout=30.0,
    )


@mcp.tool()
def cad_status() -> dict:
    """Return KIMM-CAD connection and active-document status."""
    return send_command("status")


@mcp.tool()
def cad_clear() -> dict:
    """Remove every object from the active document, only on explicit user request."""
    return send_command("clear")


def main() -> None:
    transport = os.environ.get("KIMM_CAD_MCP_TRANSPORT", "stdio").strip().lower()
    if transport not in {"stdio", "sse", "streamable-http"}:
        raise ValueError("KIMM_CAD_MCP_TRANSPORT must be stdio, sse, or streamable-http.")
    mcp.run(transport=transport)


if __name__ == "__main__":
    main()
