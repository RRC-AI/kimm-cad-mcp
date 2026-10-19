# SPDX-License-Identifier: LGPL-2.1-or-later
# Copyright (C) 2026 Korea Institute of Machinery & Materials (KIMM)
"""Execute a declarative, whitelisted CAD plan in KIMM-CAD and export verified artifacts."""

from __future__ import annotations

import json
import math
import re
from pathlib import Path

import FreeCAD as App
import FreeCADGui as Gui
import Part


SUPPORTED_OPERATIONS = {
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
}
SUPPORTED_PROFILES = {"airfoil", "ellipse", "rectangle", "polygon"}
SUPPORTED_PROPERTY_TYPES = {"length", "float", "integer", "angle", "string"}


def _number(value, field: str, *, positive: bool = False, nonnegative: bool = False) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{field} must be numeric, not boolean.")
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be numeric.") from exc
    if not math.isfinite(result):
        raise ValueError(f"{field} must be finite.")
    if positive and result <= 0.0:
        raise ValueError(f"{field} must be positive.")
    if nonnegative and result < 0.0:
        raise ValueError(f"{field} must be nonnegative.")
    return result


def _integer(value, field: str, minimum: int = 1, maximum: int = 1000) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{field} must be an integer.")
    try:
        result = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be an integer.") from exc
    if result != float(value) or not minimum <= result <= maximum:
        raise ValueError(f"{field} must be an integer between {minimum} and {maximum}.")
    return result


def _vector(value, field: str) -> App.Vector:
    if not isinstance(value, (list, tuple)) or len(value) != 3:
        raise ValueError(f"{field} must contain exactly three coordinates.")
    return App.Vector(*[_number(component, field) for component in value])


def _safe_identifier(value: str, fallback: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_]+", "_", str(value).strip()).strip("_")
    return cleaned[:64] or fallback


def _require_shape(shapes: dict, source: str):
    key = str(source)
    if key not in shapes:
        raise ValueError(f"Unknown source object {key!r}; operations may reference only prior ids.")
    return shapes[key]


def _transform_local_point(origin: App.Vector, plane: str, u: float, v: float, angle_deg: float):
    angle = math.radians(angle_deg)
    rotated_u = u * math.cos(angle) - v * math.sin(angle)
    rotated_v = u * math.sin(angle) + v * math.cos(angle)
    if plane == "xy":
        return origin + App.Vector(rotated_u, rotated_v, 0.0)
    if plane == "xz":
        return origin + App.Vector(rotated_u, 0.0, rotated_v)
    if plane == "yz":
        return origin + App.Vector(0.0, rotated_u, rotated_v)
    raise ValueError("section plane must be xy, xz, or yz.")


def _airfoil_wire(section: dict):
    origin = _vector(section.get("origin", [0, 0, 0]), "section.origin")
    plane = str(section.get("plane", "yz")).lower()
    chord = _number(section.get("chord"), "section.chord", positive=True)
    thickness = _number(section.get("thickness"), "section.thickness", positive=True)
    angle = _number(section.get("rotation_deg", 0.0), "section.rotation_deg")
    point_count = _integer(section.get("point_count", 20), "section.point_count", 8, 64)
    upper = []
    lower = []
    for index in range(point_count + 1):
        x = 0.5 * (1.0 - math.cos(math.pi * index / point_count))
        polynomial = (
            0.2969 * math.sqrt(x)
            - 0.1260 * x
            - 0.3516 * x**2
            + 0.2843 * x**3
            - 0.1036 * x**4
        )
        half_thickness = 5.0 * thickness * polynomial
        chord_position = chord * (0.5 - x)
        upper.append(_transform_local_point(origin, plane, chord_position, half_thickness, angle))
        lower.append(_transform_local_point(origin, plane, chord_position, -half_thickness, angle))
    lower.reverse()
    upper_curve = Part.BSplineCurve()
    lower_curve = Part.BSplineCurve()
    upper_curve.interpolate(Points=upper)
    lower_curve.interpolate(Points=lower)
    wire = Part.Wire([upper_curve.toShape(), lower_curve.toShape()])
    if not wire.isClosed():
        raise RuntimeError("Generated airfoil section is not closed.")
    return wire


def _sampled_closed_wire(section: dict, profile: str):
    origin = _vector(section.get("origin", [0, 0, 0]), "section.origin")
    plane = str(section.get("plane", "xy")).lower()
    angle = _number(section.get("rotation_deg", 0.0), "section.rotation_deg")
    points = []
    if profile == "ellipse":
        width = _number(section.get("width"), "section.width", positive=True)
        height = _number(section.get("height"), "section.height", positive=True)
        count = _integer(section.get("point_count", 32), "section.point_count", 12, 96)
        for index in range(count):
            parameter = 2.0 * math.pi * index / count
            points.append(
                _transform_local_point(
                    origin,
                    plane,
                    0.5 * width * math.cos(parameter),
                    0.5 * height * math.sin(parameter),
                    angle,
                )
            )
    elif profile == "rectangle":
        width = _number(section.get("width"), "section.width", positive=True)
        height = _number(section.get("height"), "section.height", positive=True)
        for u, v in (
            (-width / 2.0, -height / 2.0),
            (width / 2.0, -height / 2.0),
            (width / 2.0, height / 2.0),
            (-width / 2.0, height / 2.0),
        ):
            points.append(_transform_local_point(origin, plane, u, v, angle))
    else:
        raw_points = section.get("points")
        if not isinstance(raw_points, list) or not 3 <= len(raw_points) <= 128:
            raise ValueError("polygon section points must contain 3 to 128 [u, v] pairs.")
        for index, pair in enumerate(raw_points):
            if not isinstance(pair, (list, tuple)) or len(pair) != 2:
                raise ValueError(f"section.points[{index}] must be [u, v].")
            points.append(
                _transform_local_point(
                    origin,
                    plane,
                    _number(pair[0], f"section.points[{index}][0]"),
                    _number(pair[1], f"section.points[{index}][1]"),
                    angle,
                )
            )
    points.append(points[0])
    return Part.makePolygon(points)


def _make_section(section: dict):
    if not isinstance(section, dict):
        raise ValueError("Each Loft section must be an object.")
    profile = str(section.get("profile", "")).lower()
    if profile not in SUPPORTED_PROFILES:
        raise ValueError(f"Unsupported section profile {profile!r}.")
    return _airfoil_wire(section) if profile == "airfoil" else _sampled_closed_wire(section, profile)


def _execute_operation(operation: dict, shapes: dict, metrics: dict):
    op = str(operation.get("op", "")).lower()
    if op not in SUPPORTED_OPERATIONS:
        raise ValueError(f"Unsupported CAD operation {op!r}.")

    if op == "box":
        return Part.makeBox(
            _number(operation.get("length"), "length", positive=True),
            _number(operation.get("width"), "width", positive=True),
            _number(operation.get("height"), "height", positive=True),
            _vector(operation.get("base", [0, 0, 0]), "base"),
            _vector(operation.get("axis", [0, 0, 1]), "axis"),
        )
    if op == "cylinder":
        return Part.makeCylinder(
            _number(operation.get("radius"), "radius", positive=True),
            _number(operation.get("height"), "height", positive=True),
            _vector(operation.get("base", [0, 0, 0]), "base"),
            _vector(operation.get("axis", [0, 0, 1]), "axis"),
        )
    if op == "sphere":
        return Part.makeSphere(
            _number(operation.get("radius"), "radius", positive=True),
            _vector(operation.get("center", [0, 0, 0]), "center"),
        )
    if op == "cone":
        return Part.makeCone(
            _number(operation.get("radius1"), "radius1", nonnegative=True),
            _number(operation.get("radius2"), "radius2", nonnegative=True),
            _number(operation.get("height"), "height", positive=True),
            _vector(operation.get("base", [0, 0, 0]), "base"),
            _vector(operation.get("axis", [0, 0, 1]), "axis"),
        )
    if op == "torus":
        return Part.makeTorus(
            _number(operation.get("major_radius"), "major_radius", positive=True),
            _number(operation.get("minor_radius"), "minor_radius", positive=True),
            _vector(operation.get("center", [0, 0, 0]), "center"),
            _vector(operation.get("axis", [0, 0, 1]), "axis"),
        )
    if op == "polygon_prism":
        section = {
            "profile": "polygon",
            "origin": operation.get("origin", [0, 0, 0]),
            "plane": operation.get("plane", "xy"),
            "rotation_deg": operation.get("rotation_deg", 0.0),
            "points": operation.get("points"),
        }
        face = Part.Face(_make_section(section))
        return face.extrude(_vector(operation.get("vector"), "vector"))
    if op == "loft":
        raw_sections = operation.get("sections")
        if not isinstance(raw_sections, list) or not 2 <= len(raw_sections) <= 32:
            raise ValueError("loft.sections must contain 2 to 32 section objects.")
        sections = [_make_section(section) for section in raw_sections]
        return Part.makeLoft(
            sections,
            bool(operation.get("solid", True)),
            bool(operation.get("ruled", False)),
        )
    if op == "translate":
        shape = _require_shape(shapes, operation.get("source")).copy()
        shape.translate(_vector(operation.get("vector"), "vector"))
        return shape
    if op == "rotate":
        shape = _require_shape(shapes, operation.get("source")).copy()
        shape.rotate(
            _vector(operation.get("center", [0, 0, 0]), "center"),
            _vector(operation.get("axis", [0, 0, 1]), "axis"),
            _number(operation.get("angle_deg"), "angle_deg"),
        )
        return shape
    if op == "polar_pattern":
        source = _require_shape(shapes, operation.get("source"))
        count = _integer(operation.get("count"), "count", 2, 100)
        total_angle = _number(operation.get("total_angle_deg", 360.0), "total_angle_deg")
        center = _vector(operation.get("center", [0, 0, 0]), "center")
        axis = _vector(operation.get("axis", [0, 0, 1]), "axis")
        copies = []
        for index in range(count):
            copy = source.copy()
            copy.rotate(center, axis, index * total_angle / count)
            copies.append(copy)
        result = copies[0]
        for copy in copies[1:]:
            result = result.fuse(copy)
        metrics["patterns"].append({"id": operation["id"], "count": count, "kind": op})
        return result
    if op == "linear_pattern":
        source = _require_shape(shapes, operation.get("source"))
        count = _integer(operation.get("count"), "count", 2, 100)
        step = _vector(operation.get("step"), "step")
        copies = []
        for index in range(count):
            copy = source.copy()
            copy.translate(App.Vector(step.x * index, step.y * index, step.z * index))
            copies.append(copy)
        result = copies[0]
        for copy in copies[1:]:
            result = result.fuse(copy)
        metrics["patterns"].append({"id": operation["id"], "count": count, "kind": op})
        return result
    if op in {"fuse", "common"}:
        sources = operation.get("sources")
        if not isinstance(sources, list) or len(sources) < 2:
            raise ValueError(f"{op}.sources must contain at least two prior ids.")
        result = _require_shape(shapes, sources[0]).copy()
        for source in sources[1:]:
            other = _require_shape(shapes, source)
            result = result.fuse(other) if op == "fuse" else result.common(other)
        return result.removeSplitter() if bool(operation.get("refine", True)) else result
    if op == "cut":
        result = _require_shape(shapes, operation.get("base")).copy()
        tools = operation.get("tools", [])
        if isinstance(tools, str):
            tools = [tools]
        if not isinstance(tools, list) or not tools:
            raise ValueError("cut.tools must contain at least one prior id.")
        for tool in tools:
            result = result.cut(_require_shape(shapes, tool))
        return result.removeSplitter() if bool(operation.get("refine", True)) else result
    if op in {"fillet", "chamfer"}:
        shape = _require_shape(shapes, operation.get("source")).copy()
        radius = _number(operation.get("radius"), "radius", positive=True)
        raw_indices = operation.get("edge_indices")
        if raw_indices is None:
            edges = list(shape.Edges)
        else:
            if not isinstance(raw_indices, list) or not raw_indices:
                raise ValueError("edge_indices must be a non-empty list of one-based indices.")
            edges = [shape.Edges[_integer(value, "edge index", 1, len(shape.Edges)) - 1] for value in raw_indices]
        return shape.makeFillet(radius, edges) if op == "fillet" else shape.makeChamfer(radius, edges)
    raise AssertionError(f"Unhandled operation {op}")


def _infer_generation_method(operations: list[dict]) -> tuple[str, str]:
    names = {str(operation.get("op", "")).lower() for operation in operations}
    if "loft" in names:
        return "python_loft_sweep", "The plan contains varying cross-sections or curved surfaces."
    if names & {"polar_pattern", "linear_pattern", "fuse", "cut", "common"}:
        return "python_pattern", "The plan contains repetition or Boolean composition."
    return "parameter_template", "The plan contains regular parameterized solids."


def _add_properties(result, properties: list[dict]) -> tuple[dict, dict]:
    numeric = {}
    strings = {}
    freecad_types = {
        "length": "App::PropertyLength",
        "float": "App::PropertyFloat",
        "integer": "App::PropertyInteger",
        "angle": "App::PropertyAngle",
        "string": "App::PropertyString",
    }
    for index, spec in enumerate(properties):
        if not isinstance(spec, dict):
            raise ValueError(f"properties[{index}] must be an object.")
        name = _safe_identifier(spec.get("name", ""), "")
        kind = str(spec.get("type", "")).lower()
        if not name or kind not in SUPPORTED_PROPERTY_TYPES:
            raise ValueError(f"Invalid property definition at index {index}.")
        group = str(spec.get("group", "Plan Properties"))[:80]
        result.addProperty(freecad_types[kind], name, group)
        if kind == "string":
            value = str(spec.get("value", ""))
            strings[name] = value
        elif kind == "integer":
            value = _integer(spec.get("value"), f"property {name}", -1000000, 1000000)
            numeric[name] = float(value)
        else:
            value = _number(spec.get("value"), f"property {name}")
            numeric[name] = value
        setattr(result, name, value)
    return numeric, strings


def run(plan: dict, present: bool = True):
    """Execute a declarative CAD plan without evaluating arbitrary Python."""
    if not isinstance(present, bool):
        raise ValueError("present must be a boolean.")
    if not isinstance(plan, dict):
        raise ValueError("plan must be an object.")
    operations = plan.get("operations")
    if not isinstance(operations, list) or not 1 <= len(operations) <= 64:
        raise ValueError("plan.operations must contain 1 to 64 operations.")
    result_id = str(plan.get("result", "")).strip()
    if not result_id:
        raise ValueError("plan.result must identify the final operation.")

    plan_name = _safe_identifier(plan.get("name", "CAD_Plan"), "CAD_Plan")
    document_name = f"MCP_Plan_{plan_name}"
    if document_name in App.listDocuments():
        App.closeDocument(document_name)
    doc = App.newDocument(document_name)
    App.setActiveDocument(document_name)

    shapes = {}
    metrics = {"patterns": []}
    for index, operation in enumerate(operations):
        if not isinstance(operation, dict):
            raise ValueError(f"operations[{index}] must be an object.")
        operation_id = str(operation.get("id", "")).strip()
        if not operation_id or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,63}", operation_id):
            raise ValueError(f"operations[{index}].id must be a safe identifier.")
        if operation_id in shapes:
            raise ValueError(f"Duplicate operation id {operation_id!r}.")
        operation["id"] = operation_id
        shape = _execute_operation(operation, shapes, metrics)
        if shape.isNull() or not shape.isValid():
            raise RuntimeError(f"Operation {operation_id!r} produced an invalid shape.")
        shapes[operation_id] = shape

    if result_id not in shapes:
        raise ValueError(f"plan.result references unknown operation {result_id!r}.")
    final_shape = shapes[result_id].removeSplitter()
    if final_shape.isNull() or not final_shape.isValid():
        raise RuntimeError("Final planned shape is invalid.")

    result_name = _safe_identifier(plan.get("object_name", "PlannedResult"), "PlannedResult")
    result = doc.addObject("Part::Feature", result_name)
    result.Label = str(plan.get("label", plan_name))[:120]
    result.Shape = final_shape
    numeric_properties, string_properties = _add_properties(result, plan.get("properties", []))
    result.addProperty("App::PropertyString", "GenerationMethod", "Construction")
    method, reason = _infer_generation_method(operations)
    result.GenerationMethod = method
    result.ViewObject.Visibility = True
    result.ViewObject.ShapeColor = (0.58, 0.76, 0.92)
    result.ViewObject.LineColor = (0.12, 0.16, 0.24)
    result.ViewObject.DisplayMode = "Shaded"
    doc.recompute()

    model_dir = Path(__file__).resolve().parents[1] / "models"
    model_dir.mkdir(parents=True, exist_ok=True)
    artifact_stem = _safe_identifier(plan.get("artifact_stem", plan_name), plan_name).lower()
    model_path = model_dir / f"{artifact_stem}.FCStd"
    step_path = model_dir / f"{artifact_stem}.step"
    plan_path = model_dir / f"{artifact_stem}.cadplan.json"
    result.addProperty("App::PropertyString", "FCStdPath", "Artifacts")
    result.addProperty("App::PropertyString", "StepPath", "Artifacts")
    result.addProperty("App::PropertyString", "PlanPath", "Artifacts")
    result.FCStdPath = str(model_path)
    result.StepPath = str(step_path)
    result.PlanPath = str(plan_path)
    doc.recompute()
    plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    doc.saveAs(str(model_path))
    Part.export([result], str(step_path))

    shape = result.Shape
    bbox = shape.BoundBox
    vertices = list(shape.Vertexes)
    radial_diameter = (
        2.0 * max(math.hypot(vertex.Point.x, vertex.Point.y) for vertex in vertices)
        if vertices
        else 0.0
    )
    validation = plan.get("validation", {}) or {}
    tolerance = _number(validation.get("tolerance", 1.0), "validation.tolerance", positive=True)
    expected_solid_count = _integer(
        validation.get("expected_solid_count", 1),
        "validation.expected_solid_count",
        1,
        100,
    )
    if len(shape.Solids) != expected_solid_count:
        raise RuntimeError(
            f"Solid-count validation failed: expected {expected_solid_count}, got {len(shape.Solids)}."
        )
    if shape.Volume <= 0.0:
        raise RuntimeError("Positive-volume validation failed.")
    expected_radial = _number(
        validation.get("radial_diameter_xy", 0.0), "validation.radial_diameter_xy", nonnegative=True
    )
    if expected_radial and abs(radial_diameter - expected_radial) > tolerance:
        raise RuntimeError(
            f"Radial-diameter validation failed: expected {expected_radial}, got {radial_diameter}."
        )
    expected_bbox = validation.get("bounding_box", {}) or {}
    if not isinstance(expected_bbox, dict):
        raise ValueError("validation.bounding_box must be an object.")
    actual_bbox = {"x": float(bbox.XLength), "y": float(bbox.YLength), "z": float(bbox.ZLength)}
    for axis, expected in expected_bbox.items():
        if axis not in actual_bbox:
            raise ValueError("validation.bounding_box keys must be x, y, or z.")
        expected_value = _number(expected, f"validation.bounding_box.{axis}", positive=True)
        if abs(actual_bbox[axis] - expected_value) > tolerance:
            raise RuntimeError(
                f"Bounding-box validation failed for {axis}: expected {expected_value}, "
                f"got {actual_bbox[axis]}."
            )
    expected_patterns = validation.get("pattern_counts", {}) or {}
    if not isinstance(expected_patterns, dict):
        raise ValueError("validation.pattern_counts must be an object.")
    actual_patterns = {entry["id"]: entry["count"] for entry in metrics["patterns"]}
    for pattern_id, expected in expected_patterns.items():
        expected_count = _integer(expected, f"validation.pattern_counts.{pattern_id}", 2, 100)
        if actual_patterns.get(pattern_id) != expected_count:
            raise RuntimeError(
                f"Pattern-count validation failed for {pattern_id}: expected {expected_count}, "
                f"got {actual_patterns.get(pattern_id)}."
            )
    for artifact_path in (model_path, step_path, plan_path):
        if not artifact_path.is_file() or artifact_path.stat().st_size == 0:
            raise RuntimeError(f"Artifact save validation failed: {artifact_path}")

    if present:
        gui_document = Gui.getDocument(doc.Name)
        gui_document.activeView().viewAxonometric()
        gui_document.activeView().fitAll()

    return {
        "generation_method": method,
        "generation_reason": reason,
        "document": doc.Name,
        "object": result.Name,
        "operation_count": len(operations),
        "operation_types": [str(operation["op"]).lower() for operation in operations],
        "patterns": metrics["patterns"],
        "solid_count": len(shape.Solids),
        "valid": bool(shape.isValid()),
        "visibility": bool(result.ViewObject.Visibility),
        "volume_mm3": float(shape.Volume),
        "bounding_box_mm": actual_bbox,
        "radial_diameter_xy_mm": radial_diameter,
        "numeric_properties": numeric_properties,
        "string_properties": string_properties,
        "fcstd_path": str(model_path),
        "step_path": str(step_path),
        "plan_path": str(plan_path),
        "presented": present,
    }
