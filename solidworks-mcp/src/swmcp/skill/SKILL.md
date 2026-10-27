---
name: solidworks
description: Drive the local SOLIDWORKS session over COM. Use it to create and edit parts, sketches, features, assemblies, mates and drawings, and to measure, review, capture and export (STEP, STL, PDF and more). Every change is checkpointed and verified by reading the model back. Use when the user wants something modelled, inspected, measured or exported in SOLIDWORKS on this Windows machine.
---

# SOLIDWORKS

Typed operations over one live SOLIDWORKS session. You reach them through the
`swmcp` Python package, either from the shell (one operation per command) or from a
Python script (many operations in one process). Both go through the same pipeline the
`solidworks-mcp` MCP server uses: argument validation, the output-path policy, the
confirmation gate, automatic checkpoints, an audit log, and read-back verification.

## Running it

In this file, `swpy` stands for this Python interpreter:

<!-- swmcp:launcher -->
`python`

Not pinned yet. Here `python` means any interpreter that has the `solidworks-mcp`
package installed. Run `solidworks-mcp install-skill` to install this skill with the
interpreter path filled in.
<!-- /swmcp:launcher -->

Quote the path if it contains spaces. Forward slashes work in both Git Bash and
PowerShell.

## Shell or script?

**One operation from the shell.** Use this to inspect, or for a single change:

```bash
swpy -m swmcp call sw_doc_list
swpy -m swmcp call sw_health '{"probe": true}'
swpy -m swmcp call sw_export '{"output_path": "C:/cad/work/plate.step"}' --allowed-root C:/cad/work
```

It prints the same JSON payload an MCP client would get. Exit status **0** means the
operation succeeded and its read-back checks held. **1** means it failed: read `error.code`
and `error.remediation`. **2** means it *ran* but verification did not hold: the model
changed, but not as asked. Treat 2 as a failure and read `result.verification.checks`
and `result.warnings`. For a large argument object, use `@args.json`, or `-` to read
from stdin.

**A build of more than a few steps: write a Python script.** That is one process, one
attach, typed results, and exceptions on failure:

```python
from swmcp import OperationError, SolidWorks, VerificationFailed

OUT = "C:/cad/work"
with SolidWorks(allowed_roots=[OUT]) as sw:
    part = sw.doc_new(doc_type="part")
    sw.doc_save(output_path=f"{OUT}/plate.SLDPRT")
    sw.sketch_start(on={"standard_plane": "front"})
    sw.sketch_add_geometry(
        entities=[{"type": "rect_corner", "corner": [0, 0], "opposite": [100, 60]}],
        auto_relations=False,
    )
    sw.sketch_exit()
    sw.feature_extrude_boss(depth=8, name="BasePlate")

    volume = sw.measure().mass_properties["volume_mm3"]
    assert abs(volume - 100 * 60 * 8) < 1e-3, volume

    sw.export(output_path=f"{OUT}/plate.step")
```

Run it with `swpy build.py`. Each method is the operation's name without the `sw_`
prefix. `sw_import` is the one exception: its method is `import_`, because `import` is
a Python keyword. A method takes keywords, a dict, or the operation's args model, and
returns its result model. A failed operation raises `OperationError`, which has `.code`,
`.remediation` and `.envelope`. A mutation whose checks did not hold raises
`VerificationFailed`, which has `.result` and `.failed_checks`. Pass
`SolidWorks(strict=False)` to get those results back instead. Use
`sw.execute(name, args)` to get the raw outcome without any exception.

## Finding the right operation

- [reference/tools.md](reference/tools.md) lists every operation by domain, with its
  method name, tier and safety class. Start there.
- `swpy -m swmcp tools fillet edge` searches names, summaries and tags.
- `swpy -m swmcp describe sw_feature_fillet` prints the full input schema. Read it
  before your first call to an operation: unknown fields are refused, not ignored.

Tiers only limit what an MCP client is shown. From the shell or a script, you can call
every operation.

## Rules that keep the session healthy

- **Writes go only under allowed roots.** Any `output_path` outside them is refused
  before SOLIDWORKS is touched. Pass `--allowed-root DIR` (repeatable), or
  `allowed_roots=[...]` in a script, or set `SWMCP_ALLOWED_ROOTS` (semicolon-separated).
  Use a directory the user named. Do not invent one.
- **Destructive operations need `confirm: true`.** The tool index marks them. Check
  that you have the right target before you confirm.
- **Units.** A bare number is millimetres or degrees. `"2in"` and
  `{"value": 2, "unit": "inch"}` also work. Results report in mm, degrees and kg.
- **Close only what you opened.** Run `sw_doc_list` before you start and note what was
  already open: those documents are the user's. Address documents explicitly with
  `{"document": {"title": ...}}`, never by "whatever is active". When you close a scratch
  document, send `"save_first": "discard", "confirm": true`.
- **Never kill or restart SOLIDWORKS.** It is the user's application, and on a
  3DEXPERIENCE-managed install only a person can start it again, because it waits on a
  sign-in. If it is not running, ask the user to launch it. `sw_health` answers even
  while SOLIDWORKS is down.
- **The first new document after SOLIDWORKS starts can take minutes.** Later ones take
  about 1.5 s. Do not treat that first slow call as a hang, and do not interrupt it. On
  a timeout, the CLI waits for the call to finish inside SOLIDWORKS before it exits.
- **If calls stall for minutes, ask the user what SOLIDWORKS is showing.** A modal
  dialog blocks every API call and looks exactly like a hang. Also check
  `sw_health {"probe": true}`: past about 11 GiB of private memory, the session slows
  and then stops answering, and only a restart fixes that.
- **`TEMPLATE_NOT_FOUND ... (got '')`** means the default part template preference is
  empty on this machine. Pass `template_path` to `sw_doc_new`, using a `.prtdot` the
  user points you to.

## An operation is done when the model says so

The return value is not the evidence. The model is.

- Read `warnings` on every result, and `verification.checks` on every mutation. A
  partial failure shows up there, not as an error.
- Verify by measurement. Compare `sw_measure` volumes, or bounding boxes, against
  arithmetic you did beforehand. A loft or spline surface is not an exact closed-form
  solid, so compare those with a relative tolerance.
- Sketch inference snaps new geometry onto nearby geometry without saying so. When
  coordinates must be exact, pass `auto_relations: false` to `sw_sketch_add_geometry`,
  and read each entity's `deviation_mm`.
- Before you extrude or cut a profile you built by hand, run `sw_sketch_diagnose` on it.
  It reports how many contours close, where the loose ends are, any self-intersections,
  and `major_arc_segment_ids`. A closed contour can still be the wrong one: an arc meant
  to sweep 88° that comes out at 272° shares both endpoints with the one you wanted.
  `sw_sketch_add_geometry` reports each arc's `sweep_deg`, so check it there.
- For spline or freeform bodies, use `sw_measure` with `bounding_box: "tight"`. The
  default box bounds the surfaces, so it can overstate the material by most of a
  millimetre.
- To cut through in both directions, use the `through_all_both` end condition.
- Entity references from `sw_ref_capture` are plain JSON, so you can keep them between
  commands and pass them back later. Each one carries several ways to find the entity
  again. When a rebuild has invalidated the exact reference, `sw_ref_resolve` falls
  back to the others and reports how far the entity drifted.
- Every mutation is checkpointed first, so `sw_checkpoint_list` and
  `sw_checkpoint_restore` are the way back. A document that has never been saved has
  no checkpoint, so save a new part early (`sw_doc_save`) to get that safety net.
- To make several changes atomically, use `sw_safe_execute`. It runs the steps under
  one checkpoint, checks your invariants, and rolls everything back if any of them fail.
