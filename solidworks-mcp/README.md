# solidworks-mcp

A typed, auditable MCP server for SOLIDWORKS, driven over COM from a dedicated STA
worker thread.

It implements the P0 foundation and a P1 modelling vertical from
[`docs/solidworks-target-requirements.md`](../docs/solidworks-target-requirements.md),
plus neutral-format export and an atomic mutate-and-validate workflow pulled forward
from P2: **79 operations covering all 78 in-scope requirements**, with coverage
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
| sketch | start, exit, list, add geometry, set construction, delete, convert, modify |
| constraint | add relations, add dimensions, diagnose, dimension list/set, auto-dimension |
| datum | list, create plane, axis, point, coordinate system |
| feature / body / measure | extrude boss/cut, revolve, sweep, loft, fillet, chamfer, pattern, hole, shell, rib, primitives, list, edit, delete, body list, measure |
| parameter | equation list/set, configuration list/create/activate/delete, property list/set, parameter table export/import |
| view | set orientation and display mode, capture a PNG or BMP preview |
| exchange | export STEP, IGES, STL, 3MF, OBJ, PLY, Parasolid, SAT, VRML, PDF, DXF, DWG |
| review | safe execute: run a sequence under one checkpoint and roll it back if an invariant fails |

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
uv run pytest                       # 371 tests, no SOLIDWORKS needed
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
the machine and fails on any arity mismatch — 3,322 members checked here with none. It
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

## Known limitations

These are declared in `src/swmcp/catalog/scope.py` and reported in the generated
coverage file, rather than left for a user to discover:

- **`FEAT-007` (patterns)** — linear and circular only. Curve-driven, sketch-driven,
  table-driven, fill, and variable patterns are rejected by the schema, not at runtime.
- **`SK-007` (sketch editing)** — move, rotate, scale, mirror, offset, and trim.
  Extend, split, and sketch pattern are not implemented.
- **`REF-005` (probes)** — face, edge, planar, cylindrical, body-ownership, and ray
  probes. Candidate *mate* entities need the assembly domain, which is P2.
- **`FEAT-005` (loft)** — loft boss and cut across two or more profiles, with guide
  curves, a centerline, the closed-loop option, start/end tangency, and thin walls. The
  *boundary* feature is a different API (`InsertNetBlend`) and is not implemented.
- **`FEAT-009` (shell)** — one wall thickness, with faces removed to open the shell.
  Multi-thickness shells and the thicken feature are not implemented.
- **`FEAT-014` (primitives)** — box, cylinder, sphere, cone, frustum, torus, wedge, and
  prism, each built as an ordinary sketch and boss so the tree stays editable. Helix
  and spring are not implemented.
- **`PAR-004` (per-configuration values)** — dimension values are read and written per
  configuration. Per-configuration *feature suppression* is not; `sw_feature_edit`
  suppresses in the active configuration.
- **`IO-003` (export options)** — tessellation quality, mesh unit, binary or ASCII, and
  the STEP protocol, with every written file verified against its format signature.
  Exporting a selected subset of bodies is not implemented.
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

Export (`IO-002`, `IO-003`) and the atomic mutate-and-validate workflow (`REV-006`)
are pulled forward from P2 because a model that cannot leave SOLIDWORKS, and a sequence
that can end half-applied, both undercut everything else. The rest of P2 and P3 —
assemblies, mates, motion, drawings, import, sheet metal, weldments, simulation — are
not implemented.
