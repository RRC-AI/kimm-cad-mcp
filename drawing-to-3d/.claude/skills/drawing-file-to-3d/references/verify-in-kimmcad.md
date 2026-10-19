# Verifying the converted model in KIMM-CAD V26

After `convert.py` writes a STEP, two checks:

## 1. Bounding box vs the drawing (quick, numeric)

The converter prints `solid bbox X=.. Y=.. Z=..`. Compare against the drawing's overall
dimensions (outer length/width/diameter and the extrude thickness or revolve length). A
mismatch means the wrong profile/loop was used or the wrong operation/thickness.

## 2. Load the STEP in KIMM-CAD V26 (visual)

With `kimm-cad-mcp_share` installed and connected to V26, call `cad_import_verified_step`
with the absolute STEP path and a descriptive object name. The tool imports the exact STEP,
checks the solid and volume, saves FCStd and FCBak beside it, and displays it in V26.
Confirm `passed=true`, `status.connected=true`, and `status.kimm_cad_version` begins with
`V26`.

Do the DXF/DWG/PDF/IFC conversion with standalone `convert.py`. The V26 MCP step is for
inspection and validation of a completed STEP model.
