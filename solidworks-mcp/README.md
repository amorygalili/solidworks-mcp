# solidworks-mcp

A typed, auditable MCP server for SOLIDWORKS, driven over COM from a dedicated STA
worker thread.

It implements the P0 foundation and a P1 modelling vertical from
[`docs/solidworks-target-requirements.md`](../docs/solidworks-target-requirements.md),
plus neutral-format exchange and an atomic mutate-and-validate workflow pulled forward
from P2: **111 operations covering all 112 in-scope requirements**, with coverage
reported honestly in `src/swmcp/generated/requirements_coverage.json` rather than
asserted.

The organising principle comes from the requirements document itself: *an operation is
not complete because a COM call returned without throwing*. Read-back verification,
checkpoints, audit, and honest partial-coverage reporting are structural here, and
enforced by tests rather than by discipline.

## Quick start

```bash
uv venv && uv pip install -e .
uv run python scripts/gen_swconst.py       # constants, read from your installed typelib
uv run solidworks-mcp --doctor             # install + session health
uv run solidworks-mcp                      # serve over stdio
```

MCP client configuration:

```json
{
  "mcpServers": {
    "solidworks": {
      "command": "uv",
      "args": ["run", "--directory", "C:/path/to/solidworks-mcp", "solidworks-mcp"],
      "env": { "SWMCP_ALLOWED_ROOTS": "C:/cad/work" }
    }
  }
}
```

`SWMCP_ALLOWED_ROOTS` is the one setting you must provide. With it unset, no file can
be written anywhere — the path guard fails closed by design.

## What makes it different

**Safety is a discriminated union, not a bag of booleans.** Every operation declares
itself `read`, `model_mutation{destructive}`, or `non_model_side_effect{destructive,
rationale}` — and a side effect cannot exist without a written rationale saying what
leaves the process. The booleans other layers want (`read_only`, `confirm_required`,
`auto_checkpoint`) are derived in exactly one function, so a destructive operation can
never drift out of its confirmation gate.

**Success is read back, not assumed.** Every model mutation returns a `verification`
block with before/after evidence and named checks. The catalog refuses to register a
mutation whose result type cannot carry one, so this is a type error rather than an
oversight.

**One STA thread owns every COM call.** SOLIDWORKS COM has thread affinity; serializing
with a lock alone leaves a cached proxy usable from the wrong apartment. Here a single
thread initializes the apartment once, receives jobs over a queue, and pumps the
message queue while idle. A mutation is attempted **at most once** — a retried extrude
would leave a second body behind — and a timeout says the outcome is *unknown* rather
than reporting a false failure.

**References carry every addressing mode at once.** A captured entity brings its
persistent reference, a semantic geometry fallback, a human label, and a paste-ready
`tool_args` dict. When two entities match equally well, resolution **returns both
candidates** instead of silently picking the first — the failure mode that puts an
automated fillet on the wrong edge.

**Errors carry next steps.** Every failure decodes to a stable code plus a
`remediation` list. SOLIDWORKS status codes are decoded from the type library
registered on your machine, so the names match your installed release.

## Configuration

| Variable | Default | Purpose |
|---|---|---|
| `SWMCP_ALLOWED_ROOTS` | *(none)* | Semicolon-separated roots for file **writes**. Empty means nothing may be written. |
| `SWMCP_TOOL_TIER` | `core` | Max tier registered: `core`, `extended`, `advanced`, `debug`, or `all`. |
| `SWMCP_CHECKPOINT_DEBOUNCE_SEC` | `45` | Reuse a snapshot taken within this window. |
| `SWMCP_CHECKPOINT_KEEP` | `50` | Snapshots retained per document. |
| `SWMCP_CHECKPOINT_DIR` | *(beside the document)* | Relocate `.checkpoints`. |
| `SWMCP_ALLOW_UNCHECKPOINTED` | `0` | Permit destructive edits to documents that cannot be snapshotted. |
| `SWMCP_AUDIT_PATH` | `./.mcp-audit/audit.jsonl` | Append-only write log. |
| `SWMCP_ENABLE_LOWLEVEL_WRITE` | `0` | Required for `sw_api_invoke_write`. |
| `SWMCP_CALL_TIMEOUT_S` | `300` | Per-call ceiling before `WORKER_OUTCOME_UNKNOWN`. |
| `SWMCP_RETRY_ATTEMPTS` | `3` | Bounded retry for **read-only** calls on a busy server. |
| `SWMCP_MAX_CANDIDATES` | `2000` | Cap on entities a reference resolution will search. |
| `SWMCP_REQUIREMENTS_DOC` | *(discovered)* | Override the backlog location. |

Only `core` tools are registered by default, to keep a client's tool list small.
`sw_search_tools` searches the **whole** catalog regardless, and tells you which tier a
hidden operation needs.

## Units

Lengths accept three forms, all normalized to the API's metres in one module:

```jsonc
{"depth": 50}                          // a bare number is millimetres
{"depth": "2in"}                       // mm, cm, m, in, ft
{"depth": {"value": 2, "unit": "inch"}}
```

Angles default to degrees and accept `"45deg"`, `"1.57rad"`, or `{"value": 0.25,
"unit": "turn"}`.

## Tool surface

| Domain | Operations |
|---|---|
| system | connect, system info, health, capabilities, resolve names |
| safety | checkpoint create/list/restore, audit tail, explain error, path policy |
| discovery | search tools, API search, API invoke, batch invoke, gated write |
| document | new, open, list, activate, save, close, rebuild, undo |
| selection / reference | selection get/set, ref capture/resolve, probe faces, probe ray |
| sketch | start, exit, list, add geometry (lines, arcs, slots, splines), text, set construction, delete, convert, modify |
| constraint | add relations, add dimensions, diagnose, dimension list/set, auto-dimension |
| datum | list, create plane, axis, point, coordinate system |
| feature / body / measure | extrude boss/cut, revolve, sweep, loft, draft, fillet, chamfer, pattern, hole, shell, rib, primitives, list, edit, delete, body list, measure |
| parameter | equation list/set, configuration list/create/activate/delete, property list/set, parameter table export/import |
| view | set orientation and display mode, capture a PNG or BMP preview, get/set appearance, hide or show bodies and datums |
| material | assign a part material and read the density and mass it produces |
| surface | create a surface by planar fill, offset, extend, or knit |
| exchange | export STEP, IGES, STL, 3MF, OBJ, PLY, Parasolid, SAT, VRML, PDF, DXF, DWG; import STEP, IGES, Parasolid, SAT, STL with diagnostics |
| assembly | insert a component, walk the component tree, set suppression, fixed state, visibility, and configuration, add/list/edit/delete mates, probe candidate mate entities and judge a pair before building it, report how constrained each component is, check interference |
| drawing | create a drawing and add sheets with explicit template, size, scale, and projection standard; place model and standard-three views; import model dimensions; add notes and centre marks; insert a bill of materials read back cell by cell; list sheets and views; review counts against caller-supplied minimums; export a drawing or chosen sheets to PDF, DXF, or DWG with the written file verified against its own signature |
| review | inspect a document, validate it against caller-supplied policy, audit holes in the B-Rep, write JSON and Markdown reports, safe execute: run a sequence under one checkpoint and roll it back if an invariant fails |

Per-tool reference with full JSON schemas: `src/swmcp/generated/docs/`.

## Demo

```bash
uv run python scripts/demo_build.py
```

Spawns `python -m swmcp` over stdio, does the MCP handshake, and drives the published
tools the way any MCP client would — no test harness in the path. It builds six parts
in `demo-output/` and writes `DEMO-TRANSCRIPT.md` (every call, its arguments, and the
evidence returned) plus `demo-log.json` with the full payloads.

| File | What it proves |
|---|---|
| `demo_01_bracket.SLDPRT` | Sketch → relations → dimensions (fully defined) → 8 mm extrude measuring exactly 48 000 mm³ → a Ø6.6 hole found in the B-Rep → a 2×2 pattern verified by probing four cylindrical faces → a fillet on four edges |
| `demo_02_shaft.SLDPRT` | A revolve about a sketch centerline, measuring 37 699.112 mm³ against π·(15²·40 + 10²·30) |
| `demo_03_safety.SLDPRT` | A write outside the roots refused, an unknown argument refused, a delete refused without `confirm`, the versioning policy writing `_v002` instead of replacing a file, and a checkpoint restore that re-measures identically after the feature was really deleted |
| `demo_04_parametric.SLDPRT` | A global variable driving a dimension through an equation, configurations created and activated, custom properties written, and the parameter table exported to `demo_04_parameters.csv` |
| `demo_05_atomic.SLDPRT` | One sequence kept because its invariants held, and a second rolled back because they could not — the model measuring exactly what it did before the failed sequence ran |
| `demo_06_datum.SLDPRT` | A reference axis at two planes' intersection and the parallel-plane axis that is refused rather than invented; a point at a bore centre and three spaced along an edge; and a coordinate system whose transform reports the bore centre the demo sketched, which is the only position read-back a reference point has |

`SWMCP_ALLOWED_ROOTS` is set to `demo-output/` for the run, so that folder is the only
place the server can write. Documents already open are recorded first and left alone;
only the documents the run created are closed, addressed by title.

## Development

```bash
uv run pytest                       # 643 tests, no SOLIDWORKS needed
uv run pytest -m live tests/live/test_live_sketch.py   # one module: minutes
uv run pytest -m "live and not slow"  # the quick live pass
uv run pytest -m live               # the FULL live suite: ~90 minutes
uv run ruff check src tests scripts
uv run solidworks-mcp --check-artifacts
uv run python scripts/gen_swconst.py --check
uv run python scripts/gen_swapi.py --check
uv run python scripts/fetch_api_docs.py          # vendor the offline API reference
uv run python scripts/fetch_api_docs.py --check  # does it still match this install?
```

### Which tests to run

The full live suite takes about **90 minutes**, and the cost is concentrated rather than
spread: measured from the audit log, `sw_feature_pattern` (8 calls at 257s) and
`sw_body_primitive` (27 calls at 66s) are 40% of the run between them. Both live in
modules marked `slow`, so the quick pass skips them.

So match the gate to the change rather than running everything by reflex. The headless
suite is 6 seconds and catches most mistakes. For a change that only adds a tool — a new
handler and its schemas, touching no shared code — the honest gate is the headless suite
plus the one live module that covers it. Save the full run for changes to `dispatch.py`,
the STA worker, the session, references, safety, or units, and for release-grade checks.

`CLAUDE.md` carries the same policy for coding agents working in this repo, along with
the per-tool timing table and the rule that a live module should scope its document
fixture to the module rather than paying `sw_doc_new` and `sw_doc_close` per test.

### The offline API reference

The type library says what exists and with how many arguments. It cannot say what a
call means, what it returns, or what it quietly requires — and that gap is where this
project's real bugs have lived. `scripts/fetch_api_docs.py` vendors
[offline-solidworks-api-docs](https://github.com/pedropaulovc/offline-solidworks-api-docs)
into `reference/swapi-docs/`, curated to exactly the interfaces `swapi.json` lists.

It is **gitignored, deliberately**: the content is Dassault's SOLIDWORKS API Help,
marked for personal and educational use, and the upstream repository carries no license,
so it is fetched rather than redistributed here.

`--check` cross-checks every vendored signature against the type library registered on
the machine and fails on any arity mismatch — 3,358 members checked here with none. It
is the difference between "the docs say 2026" and "the docs describe this install."

Two things it settled that probing had answered correctly but explained wrongly:

- `IFeatureManager::InsertRib` is declared `void`. Its `None` return is the signature,
  not a failure, and reading it as one reported `RIB_FAILED` for a rib that had built.
- `IEquationMgr::SetEquationAndConfigurationOption` "modifies only equations added
  using `Add3`", and `Add3` "only works for parts having multiple configurations".
  Both -1 returns were documented behaviour rather than a broken API, and one of them
  had cost a working feature — configuration-scoped equations — that is now restored.

And two the docs did not settle, where only probing the running install would do. Both
came out of building the reference-geometry tools:

- `IFeatureManager::InsertReferencePoint` is documented as returning an `IFeature`.
  Through `pywin32` it returns a **one-element tuple** containing one. Treating that
  tuple as the feature makes every call look successful right up until `.Name` raises,
  so `sw_datum_point_create` unwraps it once, at the call site.
- `swRefPointCenterEdge` reads like "the centre of an edge" and is in fact the *arc*
  centre: SOLIDWORKS refuses it on a straight edge. The schema therefore calls it
  `arc_center`, and the failure points at `along_curve` with `percent: 50` — which is
  how you actually get an edge midpoint.

Neither is visible from the type library, which knows only names and arity, nor from
the API help, which describes the C# binding. A reference point also has no position to
read back, so the tools verify one the only way SOLIDWORKS allows: a coordinate system
built on the point reports where it landed, and the live suite checks that against
geometry it measured beforehand.

A live run is inherently serial — one SOLIDWORKS, one STA thread — and SOLIDWORKS itself
dominates the clock. Measured over a full run: `sw_doc_new` averages 3.6s and
`sw_doc_close` 3.2s, so the per-test document costs about seven seconds before any
modelling happens. The audit log records a duration for every call, which makes
`.scratch/audit.jsonl` the place to look before optimising anything here.

**Restart SOLIDWORKS between long runs.** A session driven through a few hundred
document create/close cycles accumulates private bytes and handles it never gives back.
Observed on this machine after roughly 300 documents: 11.6 GB private memory, 44,662
handles, calls slowing from 3s to 15s and then not returning at all. `sw_health` reads
those figures from WMI — which keeps answering while every COM call is blocked — and
says so plainly rather than leaving you with a timeout and no explanation.

The headless suite covers the path guard, unit normalization, checkpoint policy, audit,
error decoding, COM marshalling, the STA worker, and catalog integrity — all against
fake COM doubles that reproduce the real pathologies (a property that is also a method,
by-ref out-parameters that arrive two different ways, a localized error message).

Two structural guards are worth knowing about before editing:

- `tests/test_no_second_source_of_truth.py` scans `src/` and fails on a second copy of
  anything that must live in one place: safety booleans outside `catalog/projection.py`,
  a unit conversion outside `units.py`, a hardcoded ProgID, a hardcoded install path, a
  bare `except`, or classification by localized error text.
- `tests/test_api_versions.py` checks every SOLIDWORKS call this package makes against
  `sldworks.tlb`: that the member exists on the installed release, and that the call
  site passes a declared number of arguments. `FeatureCircularPattern5` takes fourteen;
  passing thirteen returns "Parameter not optional", which names neither the member nor
  the count. The call list is found by walking this package's own source, so it cannot
  drift from what the code does.
- `tests/test_catalog_integrity.py` enforces the requirements document's definition of
  done across the whole catalog at once — strict schemas, verification on mutations,
  artifact evidence on side effects, confirmation on destructive operations, and a
  traceable requirement id on every tool.

Generated artifacts (`src/swmcp/generated/`) are derived from the catalog by a pure
function, and drift is a test failure, not a separate script you have to remember.

## Verified environment

Built and live-tested against **SOLIDWORKS 2026 (3DEXPERIENCE R2026x)**, revision
34.3.0, Python 3.13, `pywin32`, on Windows 11.

Install discovery reads the registry rather than globbing `Program Files`: this machine
installs to `Dassault Systemes/SOLIDWORKS 3DEXPERIENCE R2026x/SOLIDWORKS`, not the
`SOLIDWORKS Corp` path every comparable project assumes.

**A 3DEXPERIENCE-managed install cannot be started automatically at all**, and the
server says so rather than trying. COM activation resolves the ProgID to the executable
in `LocalServer32` — `sldworks.exe` — and a managed build refuses to start that way: the
caller gets `CO_E_SERVER_EXEC_FAILURE` and the user gets a modal dialog demanding a
Platform launch. That dialog then blocks every subsequent API call, so the visible
symptom is a hung session rather than a failed launch.

Going through the Platform does not rescue it. Running the Platform shortcut starts
`CATSTART` and `SWXDesktopLauncher`, which raise a **3DEXPERIENCE login window and wait
for a human**; SOLIDWORKS never appears until someone signs in. An automated launch would
burn its whole timeout and leave a login prompt on the user's desktop — the same harm as
the direct launch, arrived at more slowly. So `sw_connect` with `start_if_missing`
detects a managed install by the `CATSTART.exe` beside it and **refuses in a second**
with `SOLIDWORKS_PLATFORM_LAUNCH_REQUIRED`, naming the shortcut to run. Nothing is
spawned, and a test asserts that nothing ever will be.

`sw_system_info` and `sw_capabilities` report the `launch_mode` — `com_activation` or
`platform_manual` — so a caller can branch before trying. Both, along with `sw_health`,
`sw_explain_error`, `sw_path_policy`, `sw_audit_tail`, and `sw_api_search`, answer while
SOLIDWORKS is **stopped**: the dispatcher attaches only for operations that need a
session, so the diagnostics that exist to explain a missing or wedged SOLIDWORKS are
reachable when it is missing or wedged.

## Known limitations

These are declared in `src/swmcp/catalog/scope.py` and reported in the generated
coverage file, rather than left for a user to discover:

- **`FEAT-007` (patterns)** — linear and circular only. Curve-driven, sketch-driven,
  table-driven, fill, and variable patterns are rejected by the schema, not at runtime.
- **`SK-007` (sketch editing)** — move, rotate, scale, mirror, offset, and trim.
  Extend, split, and sketch pattern are not implemented.
- **`ASM-001` (component insert)** — insert at a position, with a chosen configuration
  and optional fixed state. Placing at an arbitrary *transform* is not implemented:
  `AddComponent5` takes only X/Y/Z, and building a `MathTransform` for
  `SetTransformAndSolve2` is impossible on this build — `IMathUtility::CreateTransform`
  answers "Member not found" through IDispatch for every argument form, raw or cast,
  and `TranslateComponent` takes no arguments and starts the interactive move tool.
  Orientation is left to mates.
- **`FEAT-005` (loft)** — loft boss and cut across two or more profiles, with guide
  curves, a centerline, the closed-loop option, start/end tangency, and thin walls. The
  *boundary* feature is a different API (`InsertNetBlend`) and is not implemented.
- **`FEAT-020` (materials)** — part-level assignment and read-back, with the density
  and mass that follow. Per-body and per-component materials are not implemented, and
  neither is mass override: `IMassProperty` on this build does not expose
  `SetOverrideMassValue` or `OverrideMass` through late binding, so a tool for it would
  have nothing to call.
- **`REV-001` (inspection)** — document, feature tree, sketches, bodies,
  configurations, components, and mass in one payload. Equations, dimensions, and
  custom properties keep their own tools and are not folded in.
- **`REV-004` (hole audit)** — holes are counted from the B-Rep, grouped by diameter,
  with axis and position, and compared against expected counts. Depth and
  datum-relative position are not measured, and slots are not audited.
- **`REV-005` (reports)** — a policy review written as both JSON and Markdown, each
  finding attributed to what it read. The report covers validation findings; it does
  not embed previews or the hole audit.
- **`DRW-004` (model items)** — model dimensions and annotations are imported
  into the views, and every item that arrived is reported by walking the views
  before and after. `InsertModelAnnotations3` returns nothing when it finds
  nothing, which is not the same as failing, so "imported nothing" is reported
  as exactly that. Creating drawing dimensions directly, and setting tolerance,
  precision, arrow style, or text formatting, are not implemented.
- **`DRW-005` (annotations)** — general notes with placement, and centre marks on
  selected circular edges. Hole callouts, datum symbols, GD&T, surface-finish,
  weld, balloon, and revision annotations are not implemented; each needs its own
  symbol definition rather than text and a position.
- **`DRW-006` (tables)** — a bill of materials in any of the four BOM types, read
  back cell by cell with `DisplayedText` so the contents are the evidence rather
  than the call having returned. Hole, revision, weldment cut-list, and general
  tables are not implemented, and neither is following a row back to the
  component it lists.
- **`DRW-007` (sheets)** — additional sheets with their own size, scale, and
  projection standard, activated or not as asked, and measured back so a sheet of
  zero area is refused — `NewSheet3` carries the same width/height trap as
  `NewDocument`. Changing an existing sheet's format, reordering views, and layer,
  line, and font standards are not implemented.
- **`DRW-008` (drawing review)** — views, dimensions, notes, tables, and dangling
  annotations counted and located per sheet against caller-supplied minimums,
  every finding attributed to the call it was read from. Overlap, clipping, and
  missing-callout detection are not implemented: they need annotation extents
  compared against each other, and `DRW-010` is explicit that approximate
  bounding boxes must not be presented as proof a drawing is correct — which is
  why `sw_drawing_review` sets `visual_review_required` unconditionally and says
  in its own warnings that a person still has to look at it.
- **`DRW-009` (drawing export)** — PDF, DXF, or DWG, with the written file checked
  against that format's own signature and reported with size, timestamp, and
  SHA-256, plus counts of what was on the drawing when it was written. Sheet
  selection is **PDF-only**, because `IExportPdfData` is the only route to one — a
  sheet list given with DXF or DWG is reported as not applied rather than dropped
  silently. Images go through `sw_view_capture`, and a delivery manifest across
  several drawings is `IO-004`, which is not implemented.
- **`DRW-001` (drawing creation)** — an explicit or default template, a named
  sheet size, scale, and projection standard, with the sheet measured back so a
  degenerate one is refused at creation rather than hanging the next call. Units
  and title-block/property mapping are not implemented: the sheet format that
  carries a title block comes from the template, and `NewDocument` reports
  `swDwgTemplateNone` for the sheet it builds — so a drawing made here has no
  border or title block unless the template supplies one, and that is returned as
  a warning rather than passed over.
- **`DRW-002` (drawing views)** — model views in any of the ten standard
  orientations, and the standard three-view arrangement in either projection
  standard, each verified by reading the created view's position, scale,
  referenced model, and configuration back out of the sheet. Section, detail,
  auxiliary, broken-out, crop, relative, and exploded views are not implemented:
  each needs a sketched profile or a parent-view selection rather than a
  position, and they are rejected by the schema rather than failing at runtime.
- **`MATE-005` (mate probe)** — candidate mate entities are listed per component
  with the mate types each could take, and a specific pair is judged before it is
  built. Two halves of that verdict are *measured* — whether both references still
  resolve, and whether they sit on two different components — but whether the
  geometry can take the mate is *predicted* from entity type, never ruled on by
  SOLIDWORKS. There is no validate-only mate call: `AddMate5` has no dry-run flag,
  `ForPositioningOnly` moves the component, and `IMateEntity2` — where SOLIDWORKS
  keeps its own answer — exists only on a mate already built. So `proven` is always
  false, and `sw_safe_execute` is how to get a conclusive answer with rollback.
- **`MATE-007` (degrees of freedom)** — per-component constrained status, with the
  mates holding each component, read from `IComponent2::GetConstrainedStatus`.
  Which axes remain free, and travel along them, are not reported:
  `IComponent2::GetRemainingDOFs` answers `swRemainingDofs_Unavailable` on this
  build in every state probed — no mates, after a forced rebuild, after a mate,
  component selected and unselected — including through `InvokeTypes` with all
  twelve parameters declared `[out]`, and including for the fixed root component
  that has its own enum value. The tool calls it anyway and reports what it said.
- **`MATE-006` (mate editing)** — rename, suppress, unsuppress, and delete one mate.
  Deleting a range or all mates at once, and replaying a mate sequence under a
  checkpoint, are not implemented — though `sw_safe_execute` already rolls back a
  sequence of any tools.
- **`MATE-008` (interference)** — interference detection with each overlap's volume and
  the components involved. Clearance verification is a separate SOLIDWORKS manager
  (`ClearanceVerificationManager`) and is not implemented.
- **`MATE-001` (mate types)** — coincident, concentric, perpendicular, parallel,
  tangent, distance, angle, and lock: the types `AddMate5` builds from exactly two
  selected entities. Width, symmetric, gear, rack-and-pinion, screw, universal joint,
  slot, cam, hinge, linear coupler, path, and coordinate-system mates need three or
  more selections or extra arguments, and are rejected by the schema rather than
  failing at runtime.
- **`MATE-002` (limit mates)** — limit-distance and limit-angle mates are created with
  min and max, and `sw_mate_list` reports the range and current value. Updating an
  existing mate's limits is not implemented; recreate the mate.
- **`MATE-003` (mate references)** — faces, edges, vertices, planes, and axes go through
  the same structured references as everything else. Component coordinate systems as
  mate references are untested and not claimed.
- **`SK-008` (sketch text)** — alignment, path following, mirroring, width factor, and
  character spacing. Font is not settable: `InsertSketchText` takes no font and
  SOLIDWORKS reads it from the document's text-format preference, so exposing it would
  mean changing a document-wide setting as a side effect of drawing one string. Emboss
  and wrap are separate features and are not implemented.
- **`FEAT-018` (surfaces)** — planar fill, offset (a zero offset copies faces), extend,
  and knit. Trimming is not implemented: SOLIDWORKS exposes no `InsertTrimSurface`, and
  `InsertCutSurface` cuts a solid *with* a surface rather than trimming one surface
  against another. Knit only sews surfaces that touch along an edge.
- **`FEAT-009` (shell)** — one wall thickness, with faces removed to open the shell.
  Multi-thickness shells and the thicken feature are not implemented.
- **`FEAT-013` (slots)** — straight, centre-point straight, centre-point arc, and
  three-point arc slots, each with centre-to-centre or overall length. A semicircular
  slot is an arc slot spanning 180°; SOLIDWORKS has no separate type for it. Patterning
  a slot goes through `sw_feature_pattern` once it is cut, so it inherits that tool's
  linear-and-circular limitation.
- **`FEAT-014` (primitives)** — box, cylinder, sphere, cone, frustum, torus, wedge, and
  prism, each built as an ordinary sketch and boss so the tree stays editable. Helix
  and spring are not implemented.
- **`PAR-004` (per-configuration values)** — dimension values are read and written per
  configuration. Per-configuration *feature suppression* is not; `sw_feature_edit`
  suppresses in the active configuration.
- **`IO-003` (export options)** — tessellation quality, mesh unit, binary or ASCII, and
  the STEP protocol, with every written file verified against its format signature.
  Exporting a selected subset of bodies is not implemented.
- **`IO-001` (import)** — STEP, IGES, Parasolid, and ACIS arrive as solids, and STL as a
  graphics, surface, or solid body, each verified by measuring what the import produced.
  OBJ and other mesh formats are not implemented. Import diagnostics run and are
  reported by what they changed, but SOLIDWORKS exposes no per-file translator log, so an
  incomplete import is diagnosed from the geometry rather than from a message.
  Multi-body files import as one document; splitting them into separate parts is not
  implemented.
- **`SYS-007` (localization)** — implemented structurally through locale-invariant
  `GetTypeName2` tokens and ordinal plane position rather than an alias table. Only an
  English SOLIDWORKS was available, so regression on a localized tree is outstanding.
- **Hole Wizard** — availability is probed rather than assumed. A counterbored or
  tapped hole fails with an explanation when Toolbox is unavailable; it is never
  silently downgraded to a plain cut.
- **Mirror (`FEAT-008`) and combine (`FEAT-017`) are not implemented.** Both were
  written, and neither works on SOLIDWORKS 2026 SP3.0: `InsertMirrorFeature2` and
  `InsertCombineFeature` return nothing for every argument combination tried, which
  `src/swmcp/handlers/solid.py` records in full so the next attempt starts ahead. They
  were removed rather than shipped, because a tool that reports success it cannot back
  up is the failure mode this whole project exists to avoid.
- **3DEXPERIENCE-managed documents** — a document with no local file path cannot be
  snapshotted. Non-destructive edits proceed with a warning; destructive ones are
  refused unless `SWMCP_ALLOW_UNCHECKPOINTED=1`.

Export (`IO-002`, `IO-003`), import (`IO-001`), and the atomic mutate-and-validate
workflow (`REV-006`) were pulled forward from P2 because a model that cannot leave
SOLIDWORKS or come back into it, and a sequence that can end half-applied, both undercut
everything else. P2 proper starts with assemblies, mates, and drawings: `ASM-001` to `ASM-003`
cover inserting a component, walking the tree, and setting component state, and
`MATE-001` to `MATE-008` cover adding, listing, probing, editing, and deleting mates,
reporting how constrained each component is, and detecting interference. Component
transforms (`ASM-004`), the rest of the assembly domain (`ASM-005` to `ASM-007`), and
The rest of P2 and P3 — motion, delivery, sheet metal, weldments, simulation — are
not implemented.
