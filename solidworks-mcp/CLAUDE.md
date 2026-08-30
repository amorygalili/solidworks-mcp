# solidworks-mcp — working notes

## Testing: match the gate to the change

Live tests drive a real SOLIDWORKS over COM. The full live suite takes **~90 minutes**,
and that cost is concentrated rather than spread — so running everything by reflex wastes
most of an hour to re-prove code nobody touched.

### The gates, cheapest first

| # | Command | Cost | When |
|---|---|---|---|
| 1 | `uv run pytest` | ~6s, no SOLIDWORKS | **Always.** Schemas, decode logic, catalog integrity. Most mistakes die here for free. |
| 2 | A probe script (see below) | ~2 min | Before writing any handler against an unfamiliar API call. |
| 3 | `uv run pytest -m live tests/live/test_live_<yours>.py` | ~3-5 min | The module you added or changed. |
| 4 | `uv run pytest -m "live and not slow"` | the quick live pass | When you touched shared code and want breadth cheaply. |
| 5 | `uv run pytest -m live` | **~90 min** | Release-grade gate only. **Ask the user before starting it.** |

### Do not start the full live suite on your own

Gate 5 is a ~90-minute commitment and it monopolises the user's SOLIDWORKS while it runs.
Run it only when the user asks for it or approves it. If you believe a change warrants it,
say so and let them decide — do not launch it and report afterwards.

For an **additive** change — a new `@op` handler plus its schemas, touching no shared code
— gates 1-3 are the honest gate. Reach for 4 or 5 when you change shared infrastructure:
`dispatch.py`, `com/worker.py`, `com/session.py`, `refs/`, `safety/`, or `units.py`.

### Where the 90 minutes actually goes

Measured from `.scratch/audit.jsonl`, which records a duration for every call:

| tool | calls | avg | share of run |
|---|---|---|---|
| `sw_feature_pattern` | 8 | **257s** | 21.6% |
| `sw_body_primitive` | 27 | **66s** | 18.8% |
| `sw_feature_extrude_boss` | 170 | 6.6s | 11.9% |
| `sw_doc_new` / `close` / `save` | 942 | ~1.7s | 17% |

**35 calls consume 40% of the suite.** Both offenders live in modules already marked
`slow` (`test_live_features.py`, `test_live_solid.py`), which is why the quick pass is
worth reaching for. Before optimising anything here, read the audit log rather than
guessing — it is the reason those numbers exist.

### Writing a live module that stays cheap

- **Scope the document fixture to the module, not the function.** A `sw_doc_new` plus
  `sw_doc_close` is ~6s, so a function-scoped part fixture pays that per test. The datum
  module cost 10.5 min for 13 tests largely because its plate fixture rebuilt the plate
  every time. Build the shared body once and have tests add to it.
- **Avoid `sw_feature_pattern` and `sw_body_primitive`** unless the test is about them.
  `sw_feature_extrude_boss` reaches the same geometry at 6.6s instead of 257s.
- **Verify by measurement, not by return value.** Compare a volume against arithmetic the
  test knew in advance. "The call returned" is not evidence — see below.
- **A module-scoped *file* fixture needs its own subdirectory.** The autouse cleanup in
  `tests/live/conftest.py` sweeps `swmcp_*.step`, `swmcp_*.stl` and friends out of the
  scratch root after *every* test, which deletes a module's exported fixtures after the
  first one runs. `test_live_import.py` writes them to `scratch_root/import_fixtures/`
  instead and clears that directory itself.
- **A shared document couples the tests in it.** That is the price of module scope, and
  it is worth paying, but keep each test's geometry and feature names distinct, and
  isolate a test onto its own document when it genuinely needs a clean tree — with a
  comment saying what you ruled out first, so the isolation reads as a finding rather
  than as a way of turning a red test green. `test_live_sweep_loft.py` has a worked
  example.
- **Do not treat an `ok` payload as success.** Results carry `warnings` and a
  `verification` block, and a partial failure shows up there rather than as an error. A
  helper that ignores them can build a test on geometry that was never created —
  `sw_sketch_add_geometry` reported `1 of 1 entities failed` for minutes before a test
  helper was taught to look.

## Probe before you write a handler

The type library says what exists and with what arity. It cannot say what a call *means*,
what it returns, or what it quietly requires, and that gap is where this project's real
bugs have lived. Before implementing against an unfamiliar call, write a throwaway probe
under the scratchpad that drives it on a real document and prints what came back.

Probing has already caught, in code that looked correct:

- `InsertReferencePoint` returns a **one-element tuple** through pywin32, not the
  `IFeature` it documents.
- `swRefPointCenterEdge` is the **arc** centre and is refused on a straight edge, despite
  reading like "the centre of an edge".
- `InsertProtrusionSwept4` still works but is obsolete from 2018; the supported
  `CreateDefinition(swFmSweep)` route is also ~45% faster.
- A **loft between two circles is not an exact frustum** — it is a B-spline surface, and
  measured 0.0036% under the closed-form volume. Compare loft volumes with a relative
  tolerance.
- `IBody2::GetMassProperties` **changes what its slots mean by body type**. The documented
  layout is the solid one. For a *sheet* body, slot 3 holds the area and slot 4 the
  perimeter — so reading the solid layout off a surface reported a 40 × 30 mm plane as
  1 200 000 mm³ of material. Nothing in the type library says this; it took a circle and
  two rectangles of equal area to prove which slot was which.
- `ISldWorks::LoadFile4` returns a document and leaves its `Errors` out-parameter at 0
  whether or not the import produced anything, and **on failure it leaves the previously
  active document active**. Identify an imported document by difference against the open
  set, never by reading `ActiveDoc` afterwards.
- **Drawing views spin rather than fail.** `CreateDrawViewFromModelView3` and
  `Create3rdAngleViews2` both peg one core forever on this build. Creating the drawing
  *document* works fine, so the failure arrives one call later than you would expect.
  Diagnose this class of hang by watching CPU, not the clock: steady CPU with flat
  private bytes is a spin, a modal dialog idles at zero, and the memory wall grows.
  Measuring that first would have saved three SOLIDWORKS restarts spent on a dialog
  theory the CPU numbers had already ruled out.
- **A wedged COM call cannot be cancelled by killing the client.** When a probe times
  out, the call is still running inside SOLIDWORKS; pressing Escape dismisses a
  PropertyManager but does not retract it. The session needs restarting, and on this
  machine only the user can do that — so budget one restart per hanging experiment and
  make each attempt count. Harvest everything you need in a single run.
- `ISldWorks::GetImportFileData` is a dead end on this build: `None` for Parasolid, ACIS,
  and STL, and for STEP an object whose only reachable property is `MapConfigurationData`.
  Import options go through **user preferences**, like the export ones.

If you call an interface that `src/swmcp/generated/swapi.json` does not cover, add it to
`INTERFACES` in `scripts/gen_swapi.py` and re-run that script plus
`scripts/fetch_api_docs.py`, so the new surface is arity-checked and documented like the
rest. `fetch_api_docs.py` reads its interface list *from* `swapi.json`, so there is only
one list to update.

## An operation is not done because COM returned

`SAFE-010` is structural: a `model_mutation` must return a `MutationResult` carrying
read-back evidence. When you add a tool, ask what could be read back out of the model to
prove it worked, and assert *that*. Where SOLIDWORKS offers no direct read-back — a
reference point has no position — find an indirect one, as `sw_datum_csys_create` does by
reporting the transform of a system built on the point.

## Coverage claims are checked, not asserted

`src/swmcp/catalog/scope.py` declares what this release claims. If a requirement is only
partly implemented, use `partially_satisfies` **and** add the reason to `DECLARED_PARTIAL`;
the tests fail if a declared limitation never reaches the generated coverage file, or if
the README's headline counts drift from the catalog. After changing the catalog, run
`uv run solidworks-mcp --write-artifacts`.

## SOLIDWORKS session health

A session driven through a few hundred documents accumulates memory and handles it never
gives back. Past ~11.6 GB private bytes, calls slow from 3s to 15s and then stop returning
— which looks like a hung test but is not. Check with `sw_health` or:

```powershell
Get-Process SLDWORKS | Select-Object @{n='PrivMB';e={[int]($_.PrivateMemorySize64/1MB)}}, Handles
```

A full live run plus a demo build is enough to reach that state. Restarting SOLIDWORKS is
the fix, but it is the user's application — ask before killing it, and check first whether
any document open in it is theirs rather than a scratch file.

### Restarting it: not from sldworks.exe

This install is 3DEXPERIENCE-managed, and such a build **refuses to start** from
`sldworks.exe` or from COM activation — COM resolves the ProgID's `LocalServer32` to
exactly that executable, so `com.Dispatch(progid)` fails with `CO_E_SERVER_EXEC_FAILURE`,
and starting the exe directly puts a modal dialog on the user's screen: *"SOLIDWORKS
Design must be launched from the 3DEXPERIENCE Platform."*

**Nor from the Platform shortcut, unattended.** Running it starts `CATSTART` and
`SWXDesktopLauncher`, which raise a 3DEXPERIENCE **login window** and wait for a human —
SOLIDWORKS never starts until someone signs in. `SwSession._launch` therefore detects a
managed install (by `CATSTART.exe` in a sibling platform tree) and *refuses* with
`SOLIDWORKS_PLATFORM_LAUNCH_REQUIRED` rather than spawning anything. There is no
automated restart on this machine: **ask the user to launch SOLIDWORKS** from

```powershell
Start-Process "C:\Users\Public\Desktop\SOLIDWORKS Design.lnk"
```

and sign in. `sw_health` and `sw_system_info` answer while it is stopped, so they are how
to confirm it is back.

**A modal dialog looks exactly like a hung session, and is not the memory wall.** One live
run stalled for ~8 hours this way. The two are distinguishable from the audit log: memory
exhaustion degrades progressively and never recovers, while a dialog stalls completely and
then returns to normal speed the moment it is dismissed. That run showed a 56-minute
`sw_doc_close`, then silence, then 1.6s calls — so it was a dialog, and the fix was on the
user's screen rather than in the code. If calls hang for minutes, ask the user what
SOLIDWORKS is showing before waiting it out.
