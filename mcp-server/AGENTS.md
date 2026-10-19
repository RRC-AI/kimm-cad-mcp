# KIMM-CAD geometry generation policy

Analyze the requirements, complexity, repetition, and curved/twisted surfaces before creating any geometry.

## Select the generation method

- Use `parameter_template` for a single regular shape such as a box, cylinder, sphere, or simple flange.
- Use `python_pattern` when identical elements repeat. Create one reference element in a Python function, then place copies with a loop using rotation or an array.
- Use `python_loft_sweep` when the shape includes twist, varying cross-sections, or curved surfaces. Define multiple sections and construct the shape with Loft or Sweep in Python.
- If several rules apply, choose the most capable method in this order: `python_loft_sweep`, `python_pattern`, `parameter_template`.

## Python and verification requirements

- Save the exact Python source that is executed under `generated_scripts/`.
- After generation, verify requested dimensions, repetition count, solid count, and `Shape.isValid()`.
- If execution fails or the result is invalid, inspect the cause, update the saved source, and execute it again. Do not report completion until validation succeeds.
- At completion, set the result object's `Visibility` to `True`, call `document.recompute()`, switch to axonometric view, and call `fitAll()`.
- Report the selected method and reason, verified dimensions, repetition count, solid count, validity, visibility, and executed script path when Python is used.
