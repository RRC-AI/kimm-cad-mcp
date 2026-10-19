# Equipment modeling with KIMM-CAD V26

Some drawings are a **product spec sheet** (e.g. a Toshiba AC outdoor unit, "Chassis: 550H"):
the drawing gives only the **external dimensions and a parts list / labels**, not a single
extrudable profile. The user usually wants the *whole unit with its internal components*
modeled as a multi-part assembly (casing + fan + motor + compressor + coil + …), not just the
outer box — and wants to **watch it build up, one component at a time, in KIMM-CAD**.

Use this mode when: the drawing is a labelled product (HVAC unit, pump, motor, valve, gearbox)
with named parts, and the user asks to "draw the panel/unit" or points at a component list.

## How

1. **Read the external dimensions from the drawing** (W × D × H, key Ø's, mounting) exactly —
   these are real and must match. Render a crop of the DXF/PDF to *see* the unit if needed
   (`ezdxf.addons.drawing` + matplotlib, dark background so white lines show).
2. **List the components** from the drawing's labels + standard knowledge of that product.
   (AC outdoor unit → casing (shell), base plate, partition/fan orifice, axial fan, fan motor,
   compressor, accumulator, condenser coil (L), electrical box, service valves.)
3. **Get the V26 plan schema** with `cad_get_plan_schema`. For a supported part, submit a
   separate `cad_execute_verified_plan` with its dimensions and validation targets.
   Each call creates one verified object, document, FCStd, STEP, and plan JSON.
4. **Check each result** for shape validity, bounding box, solid count, artifact files,
   and a connected V26 status. Use `finalize=false` for intermediate work and
   `finalize=true` for the final plan.
5. The current plan tool does not combine separate documents into a native multi-part
   assembly or set individual colours and transparency. Use an explicit V26 assembly
   workflow if one assembled file is required.

## Starter component catalogs (build these by default)

Use the drawing's labels first; fall back to these standard part lists for the equipment type.
Include the internals by default — the shell alone is not the deliverable for a product drawing.

- **AC outdoor unit** (e.g. Toshiba chassis): casing (shell, transparent), base plate,
  partition / fan orifice, axial fan (hub + blades), fan motor (+ bracket), compressor
  (vertical cylinder + dome), accumulator (thin vertical cylinder), condenser coil (L-shaped
  back+side), electrical box (top of machine bay), service valves (front-bottom).
- **Centrifugal pump**: volute casing (shell), impeller, shaft, mechanical seal, bearing
  housing, drive motor, base/feet, suction & discharge flanges.
- **Electric motor**: frame/housing (shell), stator core, rotor + shaft, two end bells,
  terminal box, cooling fan + fan cover, feet.
- **Gearbox / reducer**: housing (shell), input shaft + pinion, output shaft + gear, bearings,
  top cover, oil fill/drain plugs, mounting feet.
- **Tank / vessel**: shell, dished heads (top/bottom), nozzles/flanges, support legs/skirt,
  manway.

For any equipment not listed: name the obvious functional parts (what moves the fluid/air/power,
what drives it, what contains it, what connects it) and build those. Keep names in the object
tree matching the drawing's terminology.

Do not send arbitrary Python or unsupported geometry through the V26 MCP. The plan schema
defines the operations this distribution can automate.

## Honesty

External sizes come from the drawing and must match; internal component **shapes and exact
positions are representative** (built from product knowledge, since a spec sheet doesn't
contain them). Say so, and offer to refine any component against a real detail dimension.
