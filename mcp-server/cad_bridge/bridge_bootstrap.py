# SPDX-License-Identifier: LGPL-2.1-or-later
# Copyright (C) 2026 Korea Institute of Machinery & Materials (KIMM)
"""Runs inside KIMM-CAD and executes queued MCP commands on the GUI thread."""

from __future__ import annotations

import json
import builtins
import math
import os
import runpy
import shutil
import tempfile
import time
import traceback
from pathlib import Path

import FreeCAD as App
import FreeCADGui as Gui
import Import
import Part
from PySide6 import QtCore


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RUNTIME_DIR = PROJECT_ROOT / "runtime"
INBOX_DIR = RUNTIME_DIR / "inbox"
OUTBOX_DIR = RUNTIME_DIR / "outbox"
HEARTBEAT_PATH = RUNTIME_DIR / "heartbeat.json"
MODEL_DIR = PROJECT_ROOT / "models"
GENERATED_SCRIPTS_DIR = PROJECT_ROOT / "generated_scripts"


def _write_json(path: Path, value: dict) -> None:
    # A reader may briefly deny replacement on Windows. Keep the last complete
    # JSON intact on failure; the timer will retry without blocking the GUI.
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent,
            prefix=f".{path.name}.", suffix=".tmp", delete=False,
        ) as stream:
            temporary = Path(stream.name)
            json.dump(value, stream, ensure_ascii=False, indent=2)
        temporary.replace(path)
    finally:
        if temporary is not None:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass


def _active_document():
    return App.ActiveDocument or App.newDocument("KIMM_MCP_Model")


def _safe_name(value: str, fallback: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch == "_" else "_" for ch in value.strip())
    return cleaned[:80] or fallback


def _unique_document_name(preferred: str) -> str:
    base = _safe_name(preferred, "ImportedSTEP")
    candidate = base
    index = 2
    while candidate in App.listDocuments():
        candidate = f"{base[:70]}_{index}"
        index += 1
    return candidate


def _create_primitive(payload: dict) -> dict:
    doc = _active_document()
    shape = payload["shape"]
    params = payload["params"]
    default_names = {
        "box": "MCP_Box",
        "cylinder": "MCP_Cylinder",
        "sphere": "MCP_Sphere",
        "flange": "MCP_Flange",
    }
    name = _safe_name(payload.get("name", ""), default_names[shape])

    if shape == "box":
        obj = doc.addObject("Part::Box", name)
        obj.Length = params["length"]
        obj.Width = params["width"]
        obj.Height = params["height"]
    elif shape == "cylinder":
        obj = doc.addObject("Part::Cylinder", name)
        obj.Radius = params["radius"]
        obj.Height = params["height"]
    elif shape == "sphere":
        obj = doc.addObject("Part::Sphere", name)
        obj.Radius = params["radius"]
    elif shape == "flange":
        outer_diameter = params["outer_diameter"]
        inner_diameter = params["inner_diameter"]
        thickness = params["thickness"]
        if inner_diameter >= outer_diameter:
            raise ValueError("플랜지 내경은 외경보다 작아야 합니다.")
        outer = Part.makeCylinder(outer_diameter / 2.0, thickness)
        inner = Part.makeCylinder(inner_diameter / 2.0, thickness)
        obj = doc.addObject("Part::Feature", name)
        obj.Shape = outer.cut(inner)
        obj.addProperty("App::PropertyLength", "OuterDiameter", "Flange Dimensions")
        obj.addProperty("App::PropertyLength", "InnerDiameter", "Flange Dimensions")
        obj.addProperty("App::PropertyLength", "Thickness", "Flange Dimensions")
        obj.OuterDiameter = outer_diameter
        obj.InnerDiameter = inner_diameter
        obj.Thickness = thickness
    else:
        raise ValueError(f"지원하지 않는 형상: {shape}")

    obj.Label = name
    doc.recompute()
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    model_path = MODEL_DIR / "current_model.FCStd"
    step_path = MODEL_DIR / "current_model.step"
    if "FCStdPath" not in obj.PropertiesList:
        obj.addProperty("App::PropertyString", "FCStdPath", "Artifacts")
    if "StepPath" not in obj.PropertiesList:
        obj.addProperty("App::PropertyString", "StepPath", "Artifacts")
    obj.FCStdPath = str(model_path)
    obj.StepPath = str(step_path)
    doc.recompute()
    doc.saveAs(str(model_path))
    Part.export([obj], str(step_path))
    if not model_path.is_file() or model_path.stat().st_size == 0:
        raise RuntimeError("FCStd save validation failed.")
    if not step_path.is_file() or step_path.stat().st_size == 0:
        raise RuntimeError("STEP save validation failed.")
    shape_valid = bool(hasattr(obj, "Shape") and not obj.Shape.isNull() and obj.Shape.isValid())
    if not shape_valid:
        raise RuntimeError(f"Generated {shape} shape is invalid.")
    solid_count = len(obj.Shape.Solids)
    Gui.activeDocument().activeView().viewAxonometric()
    Gui.activeDocument().activeView().fitAll()
    return {
        "message": f"KIMM-CAD에 {shape} 형상을 생성했습니다.",
        "document": doc.Name,
        "object": obj.Name,
        "label": obj.Label,
        "shape": shape,
        "params": params,
        "model_path": str(model_path),
        "step_path": str(step_path),
        "solid_count": solid_count,
        "valid": shape_valid,
    }


def _import_step(payload: dict) -> dict:
    raw_path = str(payload.get("step_path", "")).strip()
    if not raw_path:
        raise ValueError("step_path is required.")
    step_path = Path(raw_path).expanduser().resolve(strict=True)
    if step_path.suffix.lower() not in {".step", ".stp"}:
        raise ValueError("Only .step and .stp files can be imported.")
    if not step_path.is_file() or step_path.stat().st_size == 0:
        raise ValueError("The STEP source must be an existing non-empty file.")

    object_name = _safe_name(payload.get("object_name", ""), step_path.stem)
    doc = _active_document()
    App.setActiveDocument(doc.Name)
    existing_names = {obj.Name for obj in doc.Objects}
    Import.insert(str(step_path), doc.Name)
    doc.recompute()
    imported = [
        obj
        for obj in doc.Objects
        if obj.Name not in existing_names and hasattr(obj, "Shape") and not obj.Shape.isNull()
    ]
    if not imported:
        raise RuntimeError("STEP import produced no shape objects.")
    obj = max(imported, key=lambda candidate: (len(candidate.Shape.Solids), float(candidate.Shape.Volume)))
    shape = obj.Shape
    if shape.isNull():
        raise RuntimeError("Imported STEP shape is null.")
    if not shape.isValid():
        raise RuntimeError("Imported STEP shape is invalid.")

    obj.Label = object_name
    if "StepPath" not in obj.PropertiesList:
        obj.addProperty("App::PropertyString", "StepPath", "Artifacts")
    if "FCStdPath" not in obj.PropertiesList:
        obj.addProperty("App::PropertyString", "FCStdPath", "Artifacts")
    if "FCBakPath" not in obj.PropertiesList:
        obj.addProperty("App::PropertyString", "FCBakPath", "Artifacts")
    obj.StepPath = str(step_path)
    fcstd_path = step_path.with_suffix(".FCStd")
    fcbak_path = step_path.with_suffix(".FCBak")
    obj.FCStdPath = str(fcstd_path)
    obj.FCBakPath = str(fcbak_path)
    for document_obj in doc.Objects:
        if hasattr(document_obj, "ViewObject"):
            document_obj.ViewObject.Visibility = False
    obj.ViewObject.Visibility = True
    doc.recompute()
    doc.saveAs(str(fcstd_path))
    if not fcstd_path.is_file() or fcstd_path.stat().st_size == 0:
        raise RuntimeError("FCStd save validation failed after STEP import.")
    shutil.copy2(fcstd_path, fcbak_path)
    if not fcbak_path.is_file() or fcbak_path.stat().st_size == 0:
        raise RuntimeError("FCBak backup validation failed after STEP import.")

    gui_document = Gui.getDocument(doc.Name)
    if gui_document is None:
        raise RuntimeError("KIMM-CAD did not create a GUI document for the imported STEP.")
    gui_document.activeView().viewAxonometric()
    gui_document.activeView().fitAll()
    return {
        "message": "STEP file imported, validated, and displayed in KIMM-CAD.",
        "document": doc.Name,
        "object": obj.Name,
        "label": obj.Label,
        "step_path": str(step_path),
        "fcstd_path": str(fcstd_path),
        "fcbak_path": str(fcbak_path),
        "solid_count": len(shape.Solids),
        "valid": bool(shape.isValid()),
        "volume_mm3": float(shape.Volume),
        "visible": bool(obj.ViewObject.Visibility),
        "view": "axonometric_fit",
    }


def _status() -> dict:
    doc = App.ActiveDocument
    product_root = os.environ.get("KIMM_CAD_ROOT")
    manifest = Path(product_root) / "build-manifest.json" if product_root else None
    product_version = None
    if manifest and manifest.is_file():
        try:
            product_version = json.loads(manifest.read_text(encoding="utf-8")).get("version")
        except (OSError, ValueError):
            pass
    return {
        "connected": True,
        "document": doc.Name if doc else None,
        "objects": [obj.Name for obj in doc.Objects] if doc else [],
        "kimm_cad_version": product_version,
        "freecad_runtime_version": App.Version(),
        "product_root": str(Path(product_root).resolve()) if product_root else None,
        "project_root": str(PROJECT_ROOT),
    }


def _property_number(obj, name: str):
    if name not in obj.PropertiesList:
        return None
    value = getattr(obj, name)
    return float(value.Value if hasattr(value, "Value") else value)


def _validate_active_model(payload: dict) -> dict:
    doc = App.ActiveDocument
    checks = []

    def add_check(name: str, passed: bool, actual=None, expected=None) -> None:
        checks.append(
            {
                "name": name,
                "passed": bool(passed),
                "actual": actual,
                "expected": expected,
            }
        )

    if doc is None:
        add_check("active_document", False, None, "an open KIMM-CAD document")
        return {"passed": False, "checks": checks, "document": None, "object": None}

    requested_name = str(payload.get("object_name", "")).strip()
    shape_objects = [obj for obj in doc.Objects if hasattr(obj, "Shape")]
    target = doc.getObject(requested_name) if requested_name else None
    if target is None and shape_objects:
        visible = [obj for obj in shape_objects if bool(obj.ViewObject.Visibility)]
        target = visible[-1] if visible else shape_objects[-1]
    if target is None or not hasattr(target, "Shape"):
        add_check("shape_object", False, requested_name or None, "an object with Shape")
        return {
            "passed": False,
            "checks": checks,
            "document": doc.Name,
            "object": requested_name or None,
        }

    shape = target.Shape
    shape_not_null = not shape.isNull()
    add_check("shape_not_null", shape_not_null, shape_not_null, True)
    if not shape_not_null:
        return {
            "passed": False,
            "checks": checks,
            "document": doc.Name,
            "object": target.Name,
        }

    shape_valid = bool(shape.isValid())
    solid_count = len(shape.Solids)
    expected_solid_count = int(payload.get("expected_solid_count", 1))
    volume = float(shape.Volume)
    bbox = shape.BoundBox
    vertices = list(shape.Vertexes)
    measured_radial_diameter = (
        2.0 * max(math.hypot(vertex.Point.x, vertex.Point.y) for vertex in vertices)
        if vertices
        else 0.0
    )
    cylindrical_faces = []
    for face in shape.Faces:
        surface = face.Surface
        if hasattr(surface, "Radius"):
            cylindrical_faces.append(
                {
                    "radius": float(surface.Radius),
                    "z_length": float(face.BoundBox.ZLength),
                }
            )

    add_check("shape_valid", shape_valid, shape_valid, True)
    add_check("solid_count", solid_count == expected_solid_count, solid_count, expected_solid_count)
    add_check("positive_volume", math.isfinite(volume) and volume > 0.0, volume, "> 0")
    expected_volume = float(payload.get("expected_volume_mm3", 0.0))
    if expected_volume > 0:
        volume_tolerance = float(payload.get("volume_tolerance_mm3", 0.01))
        if volume_tolerance <= 0:
            raise ValueError("Volume tolerance must be positive.")
        add_check(
            "volume_matches",
            abs(volume - expected_volume) <= volume_tolerance,
            volume,
            expected_volume,
        )
    visible = bool(target.ViewObject.Visibility)
    add_check("visibility", visible, visible, True)

    tolerance = float(payload.get("tolerance", 1.0))
    if tolerance <= 0:
        raise ValueError("Validation tolerance must be positive.")

    legacy_expected_properties = {
        "OverallDiameter": float(payload.get("expected_overall_diameter", 0.0)),
        "HubDiameter": float(payload.get("expected_hub_diameter", 0.0)),
        "HubThickness": float(payload.get("expected_hub_thickness", 0.0)),
        "BladeRootWidth": float(payload.get("expected_blade_root_width", 0.0)),
        "BladeTipWidth": float(payload.get("expected_blade_tip_width", 0.0)),
        "BladeThickness": float(payload.get("expected_blade_thickness", 0.0)),
        "Pitch": float(payload.get("expected_pitch", 0.0)),
        "BladeCount": float(payload.get("expected_blade_count", 0.0)),
    }
    property_aliases = {
        "length": "Length",
        "width": "Width",
        "height": "Height",
        "radius": "Radius",
        "outer_diameter": "OuterDiameter",
        "inner_diameter": "InnerDiameter",
        "thickness": "Thickness",
    }
    generic_properties = payload.get("expected_properties", {}) or {}
    if not isinstance(generic_properties, dict):
        raise ValueError("expected_properties must be an object of dimension names and values.")
    for property_name, expected in legacy_expected_properties.items():
        if expected <= 0:
            continue
        actual = _property_number(target, property_name)
        add_check(
            f"property_{property_name}",
            actual is not None and abs(actual - expected) <= tolerance,
            actual,
            expected,
        )
    for supplied_name, supplied_value in generic_properties.items():
        property_name = property_aliases.get(str(supplied_name), str(supplied_name))
        expected = float(supplied_value)
        actual = _property_number(target, property_name)
        add_check(
            f"property_{property_name}",
            actual is not None and abs(actual - expected) <= tolerance,
            actual,
            expected,
        )

    expected_string_properties = payload.get("expected_string_properties", {}) or {}
    if not isinstance(expected_string_properties, dict):
        raise ValueError("expected_string_properties must be an object of property names and values.")
    for property_name, expected in expected_string_properties.items():
        actual = str(getattr(target, str(property_name), "")).strip()
        expected_text = str(expected).strip()
        add_check(
            f"property_{property_name}",
            actual.casefold() == expected_text.casefold(),
            actual,
            expected_text,
        )

    expected_overall_diameter = legacy_expected_properties["OverallDiameter"]
    expected_radial_diameter = float(payload.get("expected_radial_diameter", 0.0))
    radial_target = expected_radial_diameter or expected_overall_diameter
    if radial_target > 0:
        add_check(
            "measured_radial_diameter",
            abs(measured_radial_diameter - radial_target) <= tolerance,
            measured_radial_diameter,
            radial_target,
        )

    expected_bounding_box = payload.get("expected_bounding_box", {}) or {}
    if not isinstance(expected_bounding_box, dict):
        raise ValueError("expected_bounding_box must be an object with x, y, or z values.")
    actual_bounding_box = {
        "x": float(bbox.XLength),
        "y": float(bbox.YLength),
        "z": float(bbox.ZLength),
    }
    for axis, expected in expected_bounding_box.items():
        if axis not in actual_bounding_box:
            raise ValueError("expected_bounding_box keys must be x, y, or z.")
        expected_value = float(expected)
        add_check(
            f"bounding_box_{axis}",
            abs(actual_bounding_box[axis] - expected_value) <= tolerance,
            actual_bounding_box[axis],
            expected_value,
        )

    expected_hub_diameter = legacy_expected_properties["HubDiameter"]
    expected_hub_thickness = legacy_expected_properties["HubThickness"]
    if expected_hub_diameter > 0:
        expected_radius = expected_hub_diameter / 2.0
        matching_hub_faces = [
            face
            for face in cylindrical_faces
            if abs(face["radius"] - expected_radius) <= tolerance
        ]
        add_check(
            "measured_hub_radius",
            bool(matching_hub_faces),
            [face["radius"] for face in matching_hub_faces],
            expected_radius,
        )
        if expected_hub_thickness > 0:
            matching_heights = [face["z_length"] for face in matching_hub_faces]
            add_check(
                "measured_hub_thickness",
                any(abs(height - expected_hub_thickness) <= tolerance for height in matching_heights),
                matching_heights,
                expected_hub_thickness,
            )

    step_path = str(getattr(target, "StepPath", "")).strip()
    fcstd_path = str(getattr(target, "FCStdPath", doc.FileName or "")).strip()
    plan_path = str(getattr(target, "PlanPath", "")).strip()
    fcbak_path = str(getattr(target, "FCBakPath", "")).strip()
    if bool(payload.get("require_step_file", True)):
        step_file = Path(step_path) if step_path else None
        step_ok = bool(step_file and step_file.is_file() and step_file.stat().st_size > 0)
        add_check(
            "step_file",
            step_ok,
            {"path": step_path or None, "size": step_file.stat().st_size if step_ok else 0},
            "existing non-empty STEP file",
        )
    fcstd_file = Path(fcstd_path) if fcstd_path else None
    fcstd_ok = bool(fcstd_file and fcstd_file.is_file() and fcstd_file.stat().st_size > 0)
    add_check(
        "fcstd_file",
        fcstd_ok,
        {"path": fcstd_path or None, "size": fcstd_file.stat().st_size if fcstd_ok else 0},
        "existing non-empty FCStd file",
    )
    if bool(payload.get("require_backup_file", False)):
        fcbak_file = Path(fcbak_path) if fcbak_path else None
        fcbak_ok = bool(fcbak_file and fcbak_file.is_file() and fcbak_file.stat().st_size > 0)
        add_check(
            "fcbak_file",
            fcbak_ok,
            {"path": fcbak_path or None, "size": fcbak_file.stat().st_size if fcbak_ok else 0},
            "existing non-empty FCBak file",
        )
    if bool(payload.get("require_plan_file", False)):
        plan_file = Path(plan_path) if plan_path else None
        plan_ok = bool(plan_file and plan_file.is_file() and plan_file.stat().st_size > 0)
        add_check(
            "plan_file",
            plan_ok,
            {"path": plan_path or None, "size": plan_file.stat().st_size if plan_ok else 0},
            "existing non-empty CAD plan JSON file",
        )

    return {
        "passed": all(check["passed"] for check in checks),
        "document": doc.Name,
        "object": target.Name,
        "checks": checks,
        "geometry": {
            "solid_count": solid_count,
            "face_count": len(shape.Faces),
            "edge_count": len(shape.Edges),
            "vertex_count": len(shape.Vertexes),
            "volume_mm3": volume,
            "bounding_box_mm": actual_bounding_box,
            "measured_radial_diameter_mm": measured_radial_diameter,
            "cylindrical_faces": cylindrical_faces,
        },
        "artifacts": {
            "fcstd_path": fcstd_path or None,
            "fcbak_path": fcbak_path or None,
            "step_path": step_path or None,
            "plan_path": plan_path or None,
        },
    }


def _clear() -> dict:
    doc = _active_document()
    removed = len(doc.Objects)
    for obj in list(doc.Objects):
        doc.removeObject(obj.Name)
    doc.recompute()
    if doc.FileName:
        doc.save()
    return {"message": f"객체 {removed}개를 삭제했습니다.", "removed": removed, "document": doc.Name}


def _run_generated_script(payload: dict) -> dict:
    script_name = payload.get("script", "")
    script_path = (GENERATED_SCRIPTS_DIR / script_name).resolve()
    scripts_root = GENERATED_SCRIPTS_DIR.resolve()
    if not script_path.is_relative_to(scripts_root) or script_path.suffix.lower() != ".py":
        raise ValueError("generated_scripts 폴더의 Python 파일만 실행할 수 있습니다.")
    if not script_path.is_file():
        raise FileNotFoundError(f"생성 스크립트를 찾을 수 없습니다: {script_path}")
    namespace = runpy.run_path(str(script_path), run_name="kimm_cad_generated_script")
    runner = namespace.get("run")
    if not callable(runner):
        raise ValueError("생성 스크립트에 호출 가능한 run() 함수가 필요합니다.")
    result = runner(**payload.get("arguments", {}))
    return {
        "message": "Generated CAD script executed successfully.",
        "script_path": str(script_path),
        "result": result,
    }


def _execute(command: dict) -> dict:
    handlers = {
        "create_primitive": _create_primitive,
        "import_step": _import_step,
        "run_generated_script": _run_generated_script,
        "validate_active_model": _validate_active_model,
        "status": lambda _: _status(),
        "clear": lambda _: _clear(),
    }
    operation = command["operation"]
    if operation not in handlers:
        raise ValueError(f"알 수 없는 명령: {operation}")
    return handlers[operation](command.get("payload", {}))


class Bridge(QtCore.QObject):
    def __init__(self):
        super().__init__()
        INBOX_DIR.mkdir(parents=True, exist_ok=True)
        OUTBOX_DIR.mkdir(parents=True, exist_ok=True)
        MODEL_DIR.mkdir(parents=True, exist_ok=True)
        self._polling = False
        self._last_heartbeat = float("-inf")
        self._io_failures = {}
        self._pending_response = None
        self.timer = QtCore.QTimer(self)
        self.timer.timeout.connect(self.poll)
        self.timer.start(200)
        # Do not poll during construction: reloading from a queued command must
        # let the previous bridge acknowledge that command before this one runs.

    def _io_failed(self, operation, exc):
        now = time.monotonic()
        failure = self._io_failures.setdefault(operation, {"since": now, "warned": False})
        if not failure["warned"] and now - failure["since"] >= 3.0:
            App.Console.PrintWarning(
                f"KIMM-CAD MCP: {operation} 파일 접근이 지연되어 자동 재시도 중입니다: {exc}\n"
            )
            failure["warned"] = True

    def _io_recovered(self, operation):
        failure = self._io_failures.pop(operation, None)
        if failure and failure["warned"]:
            App.Console.PrintMessage(f"KIMM-CAD MCP: {operation} 파일 접근이 복구되었습니다.\n")

    def _flush_response(self):
        pending = self._pending_response
        if pending is None:
            return True
        try:
            if not pending["published"]:
                _write_json(OUTBOX_DIR / f'{pending["path"].stem}.json', pending["result"])
                pending["published"] = True
            pending["path"].unlink(missing_ok=True)
        except OSError as exc:
            self._io_failed("response", exc)
            return False
        self._io_recovered("response")
        self._pending_response = None
        return True

    @QtCore.Slot()
    def poll(self):
        if self._polling:
            return
        self._polling = True
        try:
            now = time.monotonic()
            if now - self._last_heartbeat >= 1.0:
                try:
                    _write_json(HEARTBEAT_PATH, {
                        "timestamp": time.time(),
                        "pid": os.getpid(),
                        "product_root": os.environ.get("KIMM_CAD_ROOT"),
                    })
                except OSError as exc:
                    self._io_failed("heartbeat", exc)
                else:
                    self._last_heartbeat = now
                    self._io_recovered("heartbeat")
            if not self._flush_response():
                return
            for command_path in sorted(INBOX_DIR.glob("*.json")):
                command_id = command_path.stem
                try:
                    source = command_path.read_text(encoding="utf-8")
                except OSError as exc:
                    self._io_failed("command", exc)
                    return
                self._io_recovered("command")
                try:
                    command = json.loads(source)
                    result = {"ok": True, "id": command_id, **_execute(command)}
                except Exception as exc:
                    result = {"ok": False, "id": command_id, "error": str(exc), "traceback": traceback.format_exc()}
                # Preserve a completed command's result during file contention.
                # Never rerun a modelling operation merely to retry its reply.
                self._pending_response = {"path": command_path, "result": result, "published": False}
                if not self._flush_response():
                    return
        finally:
            self._polling = False


try:
    previous_bridge = getattr(builtins, "KIMM_CAD_MCP_BRIDGE", None)
    if previous_bridge is not None:
        previous_bridge.timer.stop()
    KIMM_CAD_MCP_BRIDGE = Bridge()
    builtins.KIMM_CAD_MCP_BRIDGE = KIMM_CAD_MCP_BRIDGE
    print(f"KIMM-CAD MCP bridge ready: {PROJECT_ROOT}")
except Exception:
    traceback.print_exc()
    raise
