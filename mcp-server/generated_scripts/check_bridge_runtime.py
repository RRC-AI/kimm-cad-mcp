# SPDX-License-Identifier: LGPL-2.1-or-later
# Copyright (C) 2026 Korea Institute of Machinery & Materials (KIMM)
"""Read-only snapshot used to verify the bridge repair without changing models."""

import builtins
import FreeCAD as App
import FreeCADGui as Gui


def run():
    bridge = getattr(builtins, "KIMM_CAD_MCP_BRIDGE", None)
    return {
        "documents": {
            name: {"label": doc.Label, "file": doc.FileName,
                   "objects": [obj.Name for obj in doc.Objects]}
            for name, doc in App.listDocuments().items()
        },
        "active_document": App.ActiveDocument.Name if App.ActiveDocument else None,
        "maximized": Gui.getMainWindow().isMaximized(),
        "timer_active": bool(bridge and bridge.timer.isActive()),
        "repair_loaded": hasattr(bridge, "_io_failures"),
        "io_failures": list(getattr(bridge, "_io_failures", {})),
    }
