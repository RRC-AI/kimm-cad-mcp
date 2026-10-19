---
name: drawing-file-to-3d
description: >-
  Convert a 2D/3D drawing FILE (DXF, DWG, IFC, or vector PDF) into a 3D solid model
  (STEP + STL) by parsing the file's exact vector geometry with Python — not by eyeballing
  an image. Use this whenever the user provides or points to a .dxf / .dwg / .ifc / .pdf
  drawing file and wants a 3D model, says "이거 3D로 만들어줘", "도면 파일 3D 변환", "convert
  this DXF/DWG/IFC to STEP/STL", or asks to generate a Python script that turns a CAD drawing
  file into a 3D format. Prefer this over interpreting a drawing *image*: a file carries exact
  dimensions, so they are never mis-read. Do NOT use this for a photo/screenshot of a drawing
  (no vector data) — that needs image interpretation instead.
---

# Drawing file → 3D model (via exact geometry)

Read the drawing's **real vector geometry from the file** and build a 3D solid from it. This
removes the biggest failure mode of working from a drawing *image* — mis-reading dimensions
or shapes by eye. The numbers come straight from the file.

What a file **cannot** contain (and so is the only thing you must source elsewhere): a single
2D view has no depth. So you still decide the **2D→3D operation** — *extrude* (flat parts, by a
thickness) vs *revolve* (turned/rotational parts, around an axis). Get that from the drawing's
*other* views / title block if present, otherwise ask the user once. Everything else (outline,
holes, radii, exact sizes) is taken verbatim from the file.

## Setup (already provisioned on this machine; verify if elsewhere)

- **Local Python 3.11** with `ezdxf` (DXF parsing) and `cadquery` (build + STEP/STL export):
  `python -m pip install ezdxf cadquery`. For IFC: `pip install ifcopenshell`. For PDF:
  `pip install pymupdf`.
- **ODA File Converter** (for DWG→DXF) — installed at `C:\Program Files\ODAFileConverter*`.
- The converter runs on the **local python** (`python`), not the FreeCAD-embedded one.

## Workflow

1. **Identify the file format** from the extension and confirm it's *vector* (not a scan).
2. **Decide the 2D→3D operation** (the one judgement a 2D file can't encode):
   - Flat / plate / bracket → **extrude**; needs a thickness. Look for it in the drawing's
     side/front view or a `t`/thickness note; if truly absent, ask the user for the thickness.
   - Turned / rotational (pulley, shaft, bushing, wheel) → **revolve** the half-section
     around its axis. The half-profile must lie on one side of the axis in the DXF.
   - 3D BIM (IFC) → already 3D; just convert.
3. **Run the converter** `scripts/convert.py` with the local python:
   ```
   python scripts/convert.py part.dxf  --thickness 12
   python scripts/convert.py part.dxf  --revolve --axis x
   python scripts/convert.py part.dwg  --thickness 8        # DWG auto-converted via ODA
   python scripts/convert.py model.ifc                       # IFC → STL
   python scripts/convert.py draw.pdf  --thickness 5 --pdf-scale 1.0   # vector PDF
   ```
   By default it writes `<name>.step` and `<name>.stl` to the converter project's
   `output` directory, regardless of where the input drawing is stored. Use `--out`
   only when the user explicitly requests another destination. See `--help` for all flags.
4. **Verify** — the script prints the solid's bounding box; check it against the drawing's
   overall dimensions. To inspect the result in KIMM-CAD V26, use the verified MCP STEP
   import described in `references/verify-in-kimmcad.md`.
5. **Deliver** the `.step` (editable/portable) and `.stl` (mesh/print) with clickable links.
   Confirm both files are non-empty under `<converter-project>/output` before reporting completion.

## Format support

| Format | How | Reliability |
|---|---|---|
| **.dxf** | `cadquery.importers.importDXF` assembles the outer wire + holes; extrude or revolve | High — exact geometry |
| **.dwg** | ODA File Converter → DXF, then as DXF | High (needs ODA installed) |
| **.ifc** | `ifcopenshell` tessellates the existing 3D BIM geometry → STL | High; STEP needs FreeCAD |
| **.pdf** | *Vector* PDFs only: `pymupdf` extracts the line/curve paths → DXF → extrude/revolve. Set `--pdf-scale` (points→mm). | Medium — needs scale check; raster/scanned PDFs unsupported |

## Notes & honesty

- A multi-view mechanical DXF contains *all* views (top/front/side) as flat geometry in one
  file; auto-picking the right profile to extrude/revolve isn't fully automatic. If the DXF
  has several disjoint loops, identify the intended profile (usually one view) before building,
  or isolate it. When unsure which loop is the profile, say so rather than guessing.
- `--thickness` and the revolve axis are the few inputs not derivable from a single 2D view —
  source them from another view or the user, never invent them silently.
- The exact outline, holes, and radii are taken from the file; do not "redraw" them by eye.
- **PDF caveats**: (1) only *vector* PDFs carry geometry — a scanned/photo PDF has none and
  fails cleanly. (2) PDF coords are in points and the true scale is often lost; always check
  the printed bbox against a known dimension and re-run with `--pdf-scale` to calibrate.
  (3) circles/arcs are stored as Bézier curves and come out as fine polygons (faceted) —
  functional, but not true arcs; prefer DXF/DWG when exact circular features matter.

## Equipment and product drawings

`convert.py` converts a selected vector profile into one solid; it does not infer an entire
assembly or unseen internal parts from a product drawing. If the user wants an assembly,
identify the externally dimensioned parts from the drawing and use the KIMM-CAD V26 MCP's
`cad_get_plan_schema` and `cad_execute_verified_plan` for parts that fit its supported
operations. Each plan produces one verified object and document. See
`references/assembly-in-kimmcad.md` for the scope and limits of this workflow. State clearly
which dimensions came from the drawing and which representative shapes need confirmation.

## Files

- `scripts/convert.py` — the CLI converter (DXF/DWG/IFC/PDF). Run with local python.
- `references/verify-in-kimmcad.md` — load the output STEP into KIMM-CAD to inspect it.
- `references/assembly-in-kimmcad.md` — scope for equipment modeling with V26 verified plans.
