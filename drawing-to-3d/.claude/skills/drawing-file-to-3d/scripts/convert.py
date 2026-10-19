#!/usr/bin/env python
# SPDX-License-Identifier: LGPL-2.1-or-later
# Copyright (C) 2026 Korea Institute of Machinery & Materials (KIMM)
"""
Convert a 2D/3D drawing FILE to a 3D model (STEP + STL).

The point of this tool: read the drawing's *exact* vector geometry from the file
instead of eyeballing an image. Dimensions come straight from the file, so they are
never mis-read. The only judgement left is the 2D->3D operation (extrude vs revolve
and, for a flat part, the thickness) — which a single 2D view cannot contain.

Run with the LOCAL python (has ezdxf + cadquery; ifcopenshell optional):

  python convert.py part.dxf  --thickness 12
  python convert.py part.dxf  --revolve --axis x          # turned/rotational part
  python convert.py part.dwg  --thickness 8               # DWG -> DXF via ODA, then extrude
  python convert.py model.ifc                             # IFC is already 3D -> STL/STEP
  python convert.py draw.pdf  --thickness 5               # best-effort (vector PDF only)

Outputs <name>.step and <name>.stl to the converter project's output folder unless --out is given.

Formats:
  .dxf  full support  (cadquery importDXF assembles outer wire + holes)
  .dwg  converted to DXF first via ODA File Converter, then as DXF
  .ifc  already 3D; tessellated to STL (and STEP if FreeCAD is available)
  .pdf  best-effort: needs a *vector* PDF; raster/scanned PDFs won't work.
        Prefer converting PDF->DXF in a CAD tool, then run this on the DXF.
"""
import argparse, os, sys, subprocess, tempfile, glob, shutil
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve()
PROJECT_ROOT = next(
    (parent for parent in SCRIPT_PATH.parents if (parent / "변환.bat").is_file()),
    SCRIPT_PATH.parents[4],
)
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "output"

ODA_CANDIDATES = [
    r"C:\Program Files\ODA\ODAFileConverter 26.8.0\ODAFileConverter.exe",
    r"C:\Program Files\ODAFileConverter 26.8.0\ODAFileConverter.exe",
    r"C:\Program Files\ODAFileConverter\ODAFileConverter.exe",
]


def find_oda():
    for p in ODA_CANDIDATES:
        if os.path.exists(p):
            return p
    for pat in (r"C:\Program Files\ODA\ODAFileConverter*\ODAFileConverter.exe",
                r"C:\Program Files\ODAFileConverter*\ODAFileConverter.exe",
                r"C:\Program Files (x86)\ODA\ODAFileConverter*\ODAFileConverter.exe"):
        hits = glob.glob(pat)
        if hits:
            return hits[0]
    return None


def dwg_to_dxf(dwg_path):
    """Convert a DWG to DXF using the ODA File Converter (command-line mode)."""
    oda = find_oda()
    if not oda:
        sys.exit("ERROR: ODA File Converter not found — needed to read DWG. "
                 "Install it, or convert the DWG to DXF manually.")
    src = tempfile.mkdtemp(prefix="dwg_in_")
    dst = tempfile.mkdtemp(prefix="dxf_out_")
    shutil.copy(dwg_path, src)
    # ODAFileConverter <in> <out> <outver> <outtype> <recurse> <audit> [filter]
    subprocess.run([oda, src, dst, "ACAD2018", "DXF", "0", "1", "*.DWG"],
                   check=False)
    out = glob.glob(os.path.join(dst, "*.dxf")) + glob.glob(os.path.join(dst, "*.DXF"))
    if not out:
        sys.exit("ERROR: ODA conversion produced no DXF.")
    return out[0]


def _wire_poly(w, n=120):
    pts = []
    for i in range(n):
        p = w.positionAt(i / float(n))
        pts.append((p.x, p.y))
    return pts


def _point_in_poly(pt, poly):
    x, y = pt
    inside = False
    n = len(poly)
    j = n - 1
    for i in range(n):
        xi, yi = poly[i]
        xj, yj = poly[j]
        if ((yi > y) != (yj > y)) and \
           (x < (xj - xi) * (y - yi) / ((yj - yi) or 1e-12) + xi):
            inside = not inside
        j = i
    return inside


def _poly_area(poly):
    a = 0.0
    n = len(poly)
    for i in range(n):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % n]
        a += x1 * y2 - x2 * y1
    return abs(a) / 2.0


def build_from_dxf(dxf_path, thickness, revolve, axis, tol=0.01):
    """Build a solid from ALL closed contours in the DXF, with correct nesting.

    Uses even-odd containment so every internal feature is honoured:
    outermost loop -> solid, a loop inside it -> hole, a loop inside that -> solid
    island, and so on. Multiple separate regions each become their own solid. This
    fixes the failure where only the outer boundary survives and inner features are
    dropped or wrongly cut.
    """
    import cadquery as cq
    from cadquery import Solid, Vector

    wp = cq.importers.importDXF(dxf_path, tol=tol)
    wires = [w for w in wp.wires().vals() if w.IsClosed()]
    if not wires:
        sys.exit("ERROR: no closed profile found "
                 "(internal features must be closed loops).")

    polys = [_wire_poly(w) for w in wires]
    area = [_poly_area(pl) for pl in polys]
    cent = [(sum(p[0] for p in pl) / len(pl),
             sum(p[1] for p in pl) / len(pl)) for pl in polys]

    def contains(j, i):
        # loop j contains loop i  (j must be larger and hold i's centroid)
        return area[j] > area[i] and _point_in_poly(cent[i], polys[j])

    depth = [sum(1 for j in range(len(wires)) if j != i and contains(j, i))
             for i in range(len(wires))]

    pairs = []
    for i, w in enumerate(wires):
        if depth[i] % 2 == 0:                       # material (outer or island)
            holes = [wires[j] for j in range(len(wires))
                     if depth[j] == depth[i] + 1 and contains(i, j)]
            pairs.append((w, holes))

    axmap = {"x": (Vector(0, 0, 0), Vector(1, 0, 0)),
             "y": (Vector(0, 0, 0), Vector(0, 1, 0)),
             "z": (Vector(0, 0, 0), Vector(0, 0, 1))}
    solids = []
    for outer, holes in pairs:
        if revolve:
            a0, a1 = axmap[axis]
            solids.append(Solid.revolve(outer, holes, 360.0, a0, a1))
        else:
            solids.append(Solid.extrudeLinear(outer, holes, Vector(0, 0, thickness)))
    result = solids[0]
    for s in solids[1:]:
        result = result.fuse(s)
    print("profiles: %d solid region(s), %d hole(s)"
          % (len(pairs), sum(len(h) for _, h in pairs)))
    return cq.Workplane(obj=result)


def export_cq(solid, outbase, want):
    import cadquery as cq
    made = []
    if want in ("step", "both"):
        cq.exporters.export(solid, outbase + ".step"); made.append(outbase + ".step")
    if want in ("stl", "both"):
        cq.exporters.export(solid, outbase + ".stl"); made.append(outbase + ".stl")
    bb = solid.val().BoundingBox()
    print("solid bbox  X=%.2f  Y=%.2f  Z=%.2f" % (bb.xlen, bb.ylen, bb.zlen))
    return made


def convert_ifc(ifc_path, outbase, want):
    """IFC is already 3D BIM geometry — tessellate to STL."""
    try:
        import ifcopenshell, ifcopenshell.geom
    except ImportError:
        sys.exit("ERROR: ifcopenshell not installed (pip install ifcopenshell).")
    import numpy as np
    f = ifcopenshell.open(ifc_path)
    settings = ifcopenshell.geom.settings()
    verts_all, faces_all, offset = [], [], 0
    for prod in f.by_type("IfcProduct"):
        if not getattr(prod, "Representation", None):
            continue
        try:
            shape = ifcopenshell.geom.create_shape(settings, prod)
        except Exception:
            continue
        v = shape.geometry.verts
        idx = shape.geometry.faces
        for i in range(0, len(v), 3):
            verts_all.append((v[i], v[i + 1], v[i + 2]))
        for i in range(0, len(idx), 3):
            faces_all.append((idx[i] + offset, idx[i + 1] + offset, idx[i + 2] + offset))
        offset += len(v) // 3
    if not faces_all:
        sys.exit("ERROR: no geometry produced from IFC.")
    stl = outbase + ".stl"
    with open(stl, "w") as fp:
        fp.write("solid ifc\n")
        for a, b, c in faces_all:
            fp.write("facet normal 0 0 0\n outer loop\n")
            for vi in (a, b, c):
                fp.write("  vertex %f %f %f\n" % verts_all[vi])
            fp.write(" endloop\nendfacet\n")
        fp.write("endsolid ifc\n")
    print("IFC -> STL  (%d triangles)" % len(faces_all))
    return [stl]


def _bez(a, b, c, d, t):
    mt = 1 - t
    return mt**3 * a + 3 * mt * mt * t * b + 3 * mt * t * t * c + t**3 * d


def pdf_to_dxf(pdf_path, scale, page_index=0, output_dir=None):
    """Extract VECTOR geometry from a PDF into a DXF (then handled as DXF).

    Works only on vector PDFs (CAD exports). PDF coords are in points and the
    origin is top-left, so we y-flip and apply `scale` (points -> mm). PDFs often
    lose true scale — verify the printed bbox against a known dimension and re-run
    with --pdf-scale if needed.
    """
    try:
        import fitz  # pymupdf
    except ImportError:
        sys.exit("ERROR: pymupdf not installed (pip install pymupdf).")
    import ezdxf
    d = fitz.open(pdf_path)
    pg = d[page_index]
    H = pg.rect.height
    drawings = pg.get_drawings()
    if not drawings:
        sys.exit("ERROR: no vector geometry in PDF (scanned/raster PDF?). "
                 "Convert it to DXF in a CAD tool first.")
    doc = ezdxf.new("R2010"); msp = doc.modelspace()

    def XY(p):
        return (p.x * scale, (H - p.y) * scale)

    nseg = 0
    for path in drawings:
        pts = []
        for it in path["items"]:
            k = it[0]
            if k == "l":
                a, b = it[1], it[2]
                if not pts:
                    pts.append(XY(a))
                pts.append(XY(b)); nseg += 1
            elif k == "c":
                p0, c1, c2, p1 = it[1], it[2], it[3], it[4]
                if not pts:
                    pts.append(XY(p0))
                for i in range(1, 13):
                    t = i / 12.0
                    x = _bez(p0.x, c1.x, c2.x, p1.x, t)
                    y = _bez(p0.y, c1.y, c2.y, p1.y, t)
                    pts.append((x * scale, (H - y) * scale))
                nseg += 1
            elif k == "re":
                r = it[1]
                msp.add_lwpolyline(
                    [XY(fitz.Point(r.x0, r.y0)), XY(fitz.Point(r.x1, r.y0)),
                     XY(fitz.Point(r.x1, r.y1)), XY(fitz.Point(r.x0, r.y1))],
                    close=True)
                nseg += 4
        if len(pts) >= 2:
            msp.add_lwpolyline(pts, close=bool(path.get("closePath")))
    destination = Path(output_dir) if output_dir else Path(pdf_path).resolve().parent
    destination.mkdir(parents=True, exist_ok=True)
    out = str(destination / f"{Path(pdf_path).stem}_frompdf.dxf")
    doc.saveas(out)
    print("PDF vector -> DXF: %s  (%d segments, scale=%.4f)" % (out, nseg, scale))
    return out


def main():
    ap = argparse.ArgumentParser(description="Drawing file -> 3D (STEP/STL)")
    ap.add_argument("input")
    ap.add_argument("--thickness", type=float, default=10.0,
                    help="extrude thickness for flat parts (mm)")
    ap.add_argument("--revolve", action="store_true",
                    help="revolve the profile 360 deg (turned/rotational parts)")
    ap.add_argument("--axis", choices=["x", "y", "z"], default="x",
                    help="revolve axis (default x)")
    ap.add_argument("--out", default=None, help="output basename (no extension)")
    ap.add_argument("--format", choices=["step", "stl", "both"], default="both")
    ap.add_argument("--pdf-scale", type=float, default=1.0,
                    help="points->mm scale for PDF input (verify vs a known dimension)")
    args = ap.parse_args()

    inp = args.input
    ext = os.path.splitext(inp)[1].lower()
    DEFAULT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    outbase = str(Path(args.out).expanduser().resolve()) if args.out else str(DEFAULT_OUTPUT_DIR / Path(inp).stem)

    if ext == ".dwg":
        inp = dwg_to_dxf(inp); ext = ".dxf"
        print("DWG converted to DXF:", inp)

    if ext == ".dxf":
        solid = build_from_dxf(inp, args.thickness, args.revolve, args.axis)
        made = export_cq(solid, outbase, args.format)
    elif ext == ".ifc":
        made = convert_ifc(inp, outbase, args.format)
    elif ext == ".pdf":
        inp = pdf_to_dxf(inp, args.pdf_scale, output_dir=DEFAULT_OUTPUT_DIR); ext = ".dxf"
        solid = build_from_dxf(inp, args.thickness, args.revolve, args.axis)
        made = export_cq(solid, outbase, args.format)
    else:
        sys.exit("Unsupported file type: " + ext)

    print("WROTE:", ", ".join(made))


if __name__ == "__main__":
    main()
    # CadQuery/OCP can crash during Windows interpreter teardown after a
    # successful DXF import. Artifacts are closed by the exporters before this
    # point, so flush diagnostics and skip only the faulty teardown path.
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(0)
