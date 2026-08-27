# solidworks-mcp

A typed, auditable MCP server for SOLIDWORKS, driven over COM from a dedicated STA
worker thread.

It implements the P0 foundation and a P1 modelling vertical from
[`docs/solidworks-target-requirements.md`](../docs/solidworks-target-requirements.md):
**57 operations covering all 59 in-scope requirements**, with coverage reported
honestly in `src/swmcp/generated/requirements_coverage.json` rather than asserted.

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
| datum | list, create plane |
| feature / body / measure | extrude boss/cut, revolve, fillet, chamfer, pattern, hole, list, edit, delete, body list, measure |

Per-tool reference with full JSON schemas: `src/swmcp/generated/docs/`.

## Demo

```bash
uv run python scripts/demo_build.py
```

Spawns `python -m swmcp` over stdio, does the MCP handshake, and drives the published
tools the way any MCP client would — no test harness in the path. It builds three parts
in `demo-output/` and writes `DEMO-TRANSCRIPT.md` (every call, its arguments, and the
evidence returned) plus `demo-log.json` with the full payloads.

| File | What it proves |
|---|---|
| `demo_01_bracket.SLDPRT` | Sketch → relations → dimensions (fully defined) → 8 mm extrude measuring exactly 48 000 mm³ → a Ø6.6 hole found in the B-Rep → a 2×2 pattern verified by probing four cylindrical faces → a fillet on four edges |
| `demo_02_shaft.SLDPRT` | A revolve about a sketch centerline, measuring 37 699.112 mm³ against π·(15²·40 + 10²·30) |
| `demo_03_safety.SLDPRT` | A write outside the roots refused, an unknown argument refused, a delete refused without `confirm`, the versioning policy writing `_v002` instead of replacing a file, and a checkpoint restore that re-measures identically after the feature was really deleted |

`SWMCP_ALLOWED_ROOTS` is set to `demo-output/` for the run, so that folder is the only
place the server can write. Documents already open are recorded first and left alone;
only the documents the run created are closed, addressed by title.

## Development

```bash
uv run pytest                       # ~200 tests, no SOLIDWORKS needed
uv run pytest -m live               # against a running SOLIDWORKS; writes only to .scratch/
uv run ruff check src tests scripts
uv run solidworks-mcp --check-artifacts
uv run python scripts/gen_swconst.py --check
```

The headless suite covers the path guard, unit normalization, checkpoint policy, audit,
error decoding, COM marshalling, the STA worker, and catalog integrity — all against
fake COM doubles that reproduce the real pathologies (a property that is also a method,
by-ref out-parameters that arrive two different ways, a localized error message).

Two structural guards are worth knowing about before editing:

- `tests/test_no_second_source_of_truth.py` scans `src/` and fails on a second copy of
  anything that must live in one place: safety booleans outside `catalog/projection.py`,
  a unit conversion outside `units.py`, a hardcoded ProgID, a hardcoded install path, a
  bare `except`, or classification by localized error text.
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
- **`SYS-007` (localization)** — implemented structurally through locale-invariant
  `GetTypeName2` tokens and ordinal plane position rather than an alias table. Only an
  English SOLIDWORKS was available, so regression on a localized tree is outstanding.
- **Hole Wizard** — availability is probed rather than assumed. A counterbored or
  tapped hole fails with an explanation when Toolbox is unavailable; it is never
  silently downgraded to a plain cut.
- **3DEXPERIENCE-managed documents** — a document with no local file path cannot be
  snapshotted. Non-destructive edits proceed with a warning; destructive ones are
  refused unless `SWMCP_ALLOW_UNCHECKPOINTED=1`.

P2 and P3 domains from the backlog — assemblies, mates, motion, drawings, import and
export, sheet metal, weldments, simulation — are not implemented.
