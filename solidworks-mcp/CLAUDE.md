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
- **A zero-by-zero drawing sheet makes SOLIDWORKS spin forever.**
  `ISldWorks::NewDocument(template, paperSize, width, height)` reads width and height
  *only* when `paperSize` is `swDwgPapersUserDefined` (12). Passing 12 with `0, 0` builds
  a sheet of zero area, and any view insertion then loops trying to auto-scale geometry
  to fit it — one core pegged, memory flat, forever. Pass a real `swDwgPaperSizes_e`
  and `Create3rdAngleViews2` returns `True` in half a second. `ISheet::GetProperties2`
  reports the sheet as `[paperSize, templateIn, scale1, scale2, firstAngle, width,
  height, sameCustomProp]`, so a degenerate sheet is visible in slots 5 and 6 the moment
  it is created — check them before blaming the view call.
- **Diagnose a hang by watching CPU, not the clock.** A spin holds one core with private
  bytes flat; a modal dialog idles at zero; the memory wall grows. Three restarts went
  into a dialog theory that the CPU numbers had already ruled out, and the real cause
  was in an argument I had passed myself.
- **A wedged COM call cannot be cancelled by killing the client.** When a probe times
  out, the call is still running inside SOLIDWORKS; pressing Escape dismisses a
  PropertyManager but does not retract it. The session needs restarting, and on this
  machine only the user can do that — so budget one restart per hanging experiment,
  and harvest everything you need in a single run.
- **`IDrawingDoc::GetFirstView` returns the sheet, not a view.** It reports
  `Type == swDrawingSheet` and a null referenced document; the real views follow it
  through `GetNextView`. `IDrawingDoc::GetViews` groups by sheet but returned views
  whose `GetName2` was `None` on this build, so the `GetFirstView` walk is the reliable
  traversal.
- **SOLIDWORKS writes an STL as `.STL`** whatever case the output path was spelled in.
  Windows resolves both spellings, so nothing fails and `target.is_file()` still passes
  — it is invisible until the directory is listed, or until a manifest naming the file
  is read somewhere that is not Windows. `sw_batch_export` records the name on disk and
  warns when it differs from the one asked for.
- **`IAssemblyDoc::GetComponents(False)` returns the tree flat, but not in tree order,
  and not stably.** Each component's `Name2` encodes its path (`sub-1/widget-2`) and
  `GetParent` gives the parent component with `None` at the top, so the structure is
  recoverable — but two assemblies built by the same sequence of inserts returned their
  top-level components in *different* orders. Anything numbering rows from that order
  produces a different answer per run. `sw_bom_export` sorts before numbering.
- **A component's configuration property set and its file-level set are different
  places, both routinely populated, and they disagree.** One part reported
  `Description = "FILE LEVEL"` at file level and `"CONFIG LEVEL"` in its configuration,
  and a property written with no configuration lands at file level *only* — so reading
  the configuration set alone (which is what a BOM table does) reports blanks. Resolve
  configuration-first, file-second, and report which set each value came from.
  `IConfiguration::Description` is *not* a part description: it defaults to the
  configuration's own name, so using it as a BOM column prints "Default" on every row.
- `ISldWorks::GetImportFileData` is a dead end on this build: `None` for Parasolid, ACIS,
  and STL, and for STEP an object whose only reachable property is `MapConfigurationData`.
  Import options go through **user preferences**, like the export ones.
- **Sketch inference moves the coordinates you gave it, and says nothing.** Geometry
  created through `ISketchManager` is snapped onto whatever is already nearby, so a
  batch of exact coordinates comes back subtly relocated: a chess set built through
  `sw_sketch_add_geometry` had a rook bore shift from R7 to R8 — thinning its crown wall
  from 3mm to 2mm — while every check the server made passed. `ISketchManager::AddToDB
  = True` places geometry in the database with no inferencing, which is what
  `auto_relations=false` sets. **Restore it in a `finally`, keyed to whether the write
  succeeded rather than whether the read did**: leaving it set changes how every sketch
  the user later draws by hand behaves, with nothing on screen to explain it. Never
  trust "the segment was created" as evidence of *where*; `sw_sketch_add_geometry`
  now reports a per-entity `deviation_mm` measured against the request.
- **`FeatureRevolve2` closes far more than "a revolve needs a closed profile" implies.**
  Three profiles written as deliberate failure fixtures all revolved on 2026 (34.3.0):
  a centerline lying exactly on the profile's closing edge; a 2mm gap between two points
  that both sit **on the axis** (a revolve closes its profile against the centerline —
  this is the ordinary way to draw one); and a 5mm *collinear* gap in the outer wall.
  So an open contour is only a fault where the axis cannot reach it, which is what
  `unsupported_loose_ends` decides. A real revolve *did* once fail on the first of those
  arrangements and succeed once the centerline was extended — that failure is still
  unexplained, and the likelier cause is an inference-induced gap in the same sketch
  rather than the overlap itself. The finding is reported last and hedged accordingly.
  `tests/live/test_live_sketch_fidelity.py` pins all three as passing, so a build that
  starts refusing one announces itself.
- **`GetStartPoint2` is not on `ISketchSegment`.** It lives on `ISketchLine` and
  `ISketchArc`; asking a spline for it raises `AttributeError`. That empty answer used
  to reach contour analysis as "no endpoints", which means *closed* — so every spline
  was counted as a ring and whatever it joined was left as a broken chain. A knight's
  head of three splines and three lines reported three closed contours and two open
  ones; the real profile had one closed contour and extruded first time.
  `ISketchSpline::GetPoints` answers instead: a flat array of three doubles per
  through-point, in sketch space, so the ends are the first and last triples. Measured
  on 2026 (34.3.0), a seven-point spline returns 21 doubles matching the coordinates it
  was drawn with. (`GetPoints2` returns point *objects*, not doubles.) The wider lesson
  is in `read_endpoints`: **"has no ends" and "would not say" must not share a return
  value.** Topology now carries `endpoints_read`, and `analyze_contours` reports
  `unreadable_segment_ids` rather than deciding closure for a segment that never spoke.
  Pinned by `tests/live/test_live_spline_contours.py`.
- **`swEndCondThroughAllBoth` (9) exists and does not do what its name says** — at least
  not as `T1` on a single-ended `FeatureCut4`. Measured on 2026 (34.3.0): a 10mm bore
  through a 40mm cube, sketched on the cube's own mid-plane, removed 1570mm³ against the
  3141mm³ the hole should be — exactly half, so it went one way and stopped at the sketch
  plane, behaving like plain `swEndCondThroughAll`. Both directions is a **double-ended
  feature with through-all on each**, which is what `through_all_both` now sends. The
  constant being present in the type library was not evidence it worked; a unit test
  asserting the enum resolves passed the whole time the cut was half-depth, and only the
  live volume check in `tests/live/test_live_spline_contours.py` caught it. Worth having
  at all because the alternative — a blind depth guessed larger than the material — still
  removes volume when the guess is short, so every verification here passes on a cut that
  stopped inside the part.

- **`swDelete_Children` and `swDelete_Absorbed` are independent bits (1 and 2), not two
  modes.** `sw_feature_delete` sent Children alone for `delete_children=true`, which
  removed the dependent features but *kept* the profile sketch the feature had absorbed
  — leaving an orphan that drew itself over the model and looked like a rendering bug.
  Deleting a feature should take the sketch it consumed, so `delete_children` now sends
  `Absorbed | Children`. The result reports `also_removed`, because a delete that takes
  more than it was asked for should name what.
- **`InsertAxis2` on two standard planes gives a patternable axis.** SOLIDWORKS will not
  pattern about a bare direction: `FeatureCircularPattern5` needs a real selectable
  axis, and the model's own X/Y/Z are not entities. The two standard planes that meet on
  that axis *are* selectable (Front is XY, Top is XZ, Right is YZ), and `InsertAxis2`
  turns any pair into a `RefAxis` that patterns accept — verified in
  `tests/live/test_live_ergonomics.py`. That is what `standard_axis` on
  `sw_feature_pattern` does, and it costs a feature in the tree, so the axis is named
  `swmcp_axis_<x|y|z>` and reused rather than created per call.
- **`probe_entities` walks edges as readily as faces**, and `RefMeasurements.length_m`
  comes back populated for them — which is what makes `edges={"min_length": …}` on
  `sw_feature_fillet` and `sw_feature_chamfer` possible without any new COM. Prefer
  extending `ProbeFilters` to writing another traversal: the predicate then selects
  exactly what probing for the same thing reports.
- **Only `SaveBMP` honours a requested pixel size.** `Extension.SaveAs` ignores width
  and height entirely and writes whatever the viewport is — every PNG request came back
  1204x771 on this machine, whatever was asked for. `sw_view_capture` therefore renders
  a PNG *through* `SaveBMP` at the requested size and re-encodes the bitmap with Pillow,
  which is lossless and, more to the point, a true render at that resolution rather than
  an upscale of a smaller one. If either step fails it falls back to `Extension.SaveAs`
  and says so in `details.fallback_reason`, because a wrong-size capture beats none.

- **A closed contour is not a valid one, and endpoints cannot tell you which.** A
  centre-point arc and its complement share a centre, a radius and *both endpoints* —
  so `arc_center` honouring the `direction` it was given produces, for a wrong guess, a
  272 degree arc where an 88 degree fillet was meant, and every reading the server had
  reported it healthy: one closed contour, `max_deviation_mm` 0.0, all checks green.
  The cut then failed with a bare `EXTRUDE_FAILED` whose remediation named neither the
  segment nor the cause, and suggested `reverse=true` for a `through_all_both` cut that
  reaches both ways already. Found on an involute gear tooth space; two attempts went
  into end conditions before **arc length over radius** gave it away — a 0.76 mm fillet
  reporting 3.61 mm of length is 272 degrees, not 88.

  Three things came out of it. `describe_segment` reports `sweep_deg` and `radius_mm`,
  so the distinguishing number is stated rather than left to be derived.
  `segment_topology` carries a flattened `polyline` per segment — where a segment
  *goes*, not just where it ends — and `find_self_intersections` tests those for
  crossings, which is a fault wholly independent of closure. And the extrude
  remediation is conditioned on the end condition, because suggesting `reverse` for a
  symmetric cut sends the caller to re-run the same failure. Arc and spline geometry is
  read **only after `GetType` says so**: `GetCenterPoint2` and `GetRadius` are
  `ISketchArc` members and `GetPoints` is a spline's, the same split that
  `GetStartPoint2` has. Pinned by `tests/live/test_live_sketch_validity.py` and
  `tests/test_sketch_self_intersection.py`, both built from the profile that failed.

- **`ISketch::ModelToSketchTransform` is named for the direction it does not give
  you.** Its `ArrayData` is sixteen bare doubles with no documented layout. Measured:
  slots 0-8 are a **row-major** 3x3, 9-11 a translation in metres, 12 the scale, 13-15
  unused — and the mapping that reproduces reality is

      model = R . (sketch - t)

  so the array read this way is the *sketch to model* transform, despite the name. Both
  halves had to be measured separately before they could be trusted together: the
  standard planes give rotation with `t = 0`, a plane offset from Front gives
  translation with `R = I`, and only a plane offset from **Top** exercises both at once.
  That last case is what makes it a measurement rather than an assumed composition —
  the four mapped corners of a known rectangle landed exactly on the extruded body's
  box, `[0,30,0]->[10,35,20]`. Note the translation is stored **negated**: reading slot
  11 as the answer puts an offset sketch on the wrong side of the model. The payoff is
  that a line drawn `(0,0)->(0,-20)` on Top can be *reported* as running along model
  `+Z` instead of guessed and then confirmed from a finished body. `sketch_frame` in
  `sketching.py`; pinned in `tests/test_sketch_frame.py` against these arrays.

- **`IBody2::GetBodyBox` bounds the surfaces, not the material.** On a spline body whose
  apex was specified at exactly 10.000mm it reported **10.843455mm** — 0.84mm of
  material that is not there — while `GetExtremePoint` reported 10.000mm. On analytic
  geometry the two agree to the micron: a cylinder r=10 and a 10x5x20 box measured
  identically both ways. So this cannot be corrected by a blanket fudge; it has to be
  measured per body, which is why `bounding_box="tight"` is opt-in at six calls per body
  against one. This is the fault that reported a helical gear as 47.48mm across a
  46.57mm OD. Two traps: `GetExtremePoint` comes back as **four** values through
  pywin32 — its own success flag, then the point, so the coordinates are slots 1-3 — and
  `IModelDocExtension::GetBoundingBox`, the obvious alternative, is **not available on
  this build** at all, returning `None` for every option value.

- **pywin32's property-versus-method split goes both ways, on the same object.**
  `GetBodyBox` must be called (`body.GetBodyBox()`); `GetSketchSegments`, `GetTitle`,
  `GetPathName` and `GetDocumentCount` must **not** be. Guessing either way raises
  `TypeError: 'tuple'/'method'/'int' object is not callable` — which reads like a bug in
  your logic rather than a marshalling detail, and cost two probe rounds here. Never
  hand-roll these in a probe: `try_com_member` already resolves both forms, and using it
  is the difference between a probe that harvests everything in one run and one that
  dies halfway with the session warm and the document open.

- **A dead COM proxy answers some calls and refuses others.** After a SOLIDWORKS
  restart, `sw_connect` returned happily with `revision 34.3.0` while every
  `sw_doc_new` came back `COM_RPC_SERVER_UNAVAILABLE (0x800706BA)` — with SLDWORKS.exe
  alive, `Responding=True`, idle CPU, and no dialog on screen. The process was fine; the
  server's cached proxy was not. `sw_health --probe` had already said so quietly
  (`"answered": false`). **The diagnostic is a fresh process**: a standalone script that
  dispatches the ProgID and creates a document settles in seconds whether SOLIDWORKS or
  the client is at fault, and it is the difference between asking the user for a restart
  they do not need and restarting the server, which is what actually fixes it.

- **`swDisplayDimension` is not a member of `swUserPreferenceToggle_e`.** It reads like
  one and resolves to nothing. The display toggles that do exist, and that
  `sw_view_capture` switches off: `swDisplayPlanes` (5), `swDisplayAxes` (4),
  `swDisplayTemporaryAxes` (7), `swDisplayOrigins` (6), `swDisplayCoordSystems` (13),
  `swDisplayReferencePoints` (19), `swDisplayCurves` (195), `swDisplayDatums` (39),
  `swDisplaySketchPlanes` (664). `swDisplaySketches` (196) is deliberately left alone —
  an unconsumed sketch is content someone may be capturing on purpose.

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

## Warm the session before a live run

**The first `sw_doc_new` after SOLIDWORKS starts can take minutes. Every one after it
takes ~1.5s.** Measured here: a live module timed out at 90s inside its very first
`sw_doc_new`, and the identical test passed in 16s the moment the session had one
document behind it. The audit log's `p50` of 1452ms is the *warm* figure and hides this
completely, because a p50 over hundreds of calls cannot show a cost paid once.

This matters more than the wasted minute, because of what happens next:

- `pytest-timeout` fires at 120s (`pyproject.toml`), which kills the client **mid-COM
  call**. The call does not stop — it is running inside SOLIDWORKS.
- SOLIDWORKS then reported `Responding=False` with a part open and modified, recovered
  on its own once the client process was gone, and on the first occurrence **exited**:
  the next call returned `COM_RPC_SERVER_UNAVAILABLE` (0x800706BA).
- On this machine only the user can restart it, so that is a hard stop costing a
  relaunch and a sign-in.

So a cold first call does not merely fail slowly; it can take the session down and block
everything after it. Before starting any live module on a freshly launched SOLIDWORKS,
create and close one document — or run a single cheap test first and let it warm the
session. When a live run hangs early, check `Responding` and the CPU delta before
assuming the code is at fault:

```powershell
$p = Get-Process SLDWORKS; $c = $p.CPU; Start-Sleep 6; $p.Refresh()
"{0:N2} CPU-s in 6s, Responding={1}" -f ($p.CPU - $c), $p.Responding
```

Idle CPU with `Responding=False` is a block or a wait, not a spin — and after a killed
client it is very often just the client's own corpse holding a proxy.

### `swDefaultTemplatePart` is not File Locations

`sw_doc_new` without `template_path` reads the `swDefaultTemplate*` user preferences —
**Tools > Options > System Options > Default Templates**, which names three specific
files. That is a different setting from **File Locations > Document Templates**, which
is a directory list; setting the latter does not populate the former, and the error
`TEMPLATE_NOT_FOUND ... (got '')` means the former is empty. The error's own
remediation used to name File Locations, which is the setting that does *not* fix it.

**Correction to an earlier note here.** This section once said a long-lived server
process saw `''` while a freshly started process attached to the same SOLIDWORKS read
the preference correctly, and left process age as the suspected cause. Re-measured with
a standalone script: a brand-new process reads `''` as well, and goes on to create a
document perfectly well once handed a `template_path`. The preference is simply **not
set on this machine**, and the earlier apparent success was not reproduced. There is no
process-age effect to work around — a live module that must not depend on the
preference passes `template_path` explicitly, as `test_live_sketch_validity.py`,
`test_live_sketch_derive.py` and `test_live_measure_capture.py` all do.

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

**`strained` is not the wall.** `process_resources()` reports two readings and they mean
different things. `strained` (8 GiB, or 30 000 handles) is advisory — "worth watching",
which is all `sw_health` claims with it; a session at 9.6 GB is slower and entirely
usable, and an eleven-minute live module ran to completion there. `critical`
(`CRITICAL_PRIVATE_BYTES`, 11 GiB) is the measured wall. Anything that *acts* on the
reading rather than reporting it must use `critical`: `sw_batch_export` first keyed its
stop to `strained` and would have abandoned every multi-item batch on this machine after
one item, for a session that was working fine. There is deliberately no critical handle
count — the wall was measured in private bytes and inventing a handle figure would dress
a guess as a measurement.

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
