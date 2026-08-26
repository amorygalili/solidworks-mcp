# CAD capability matrix

See [README](README.md) for the **M/L/G/R/—** legend and the source-of-truth
rules. Cells intentionally distinguish a dedicated MCP contract from a library
function or generic code execution.

## Architecture and operational envelope

| Capability | FC | SKILL | ALISAM | JAY |
|---|---|---|---|---|
| CAD backend | FreeCAD Python API over embedded/socket/XML-RPC bridge | SolidWorks COM through Python; also CAD-free OCCT/open-format helpers | SolidWorks COM through Python/pywin32 | SolidWorks COM through a serialized .NET worker |
| Dedicated MCP surface | **M** 152 tools | **M** 40 tools | **M** 25 tools | **M** 142 tools at default `all` tier |
| Broad fallback | **G** arbitrary Python in FreeCAD | **L** extensive Python library/skill workflows | **G** arbitrary Python with `sw`, `doc`, and automation objects | **G** allowlisted single/batch API invoke; writes separately gated |
| Concurrency model | Bridge-dependent | Calls serialized by an `RLock` | Single local automation instance | Serialized worker/session; persistent-worker option |
| Safety/recovery model | Transactions, undo/redo, validation, safe execute | Typed inputs, path/versioning rules, review reports, evidence gates | Error dictionaries and logging; arbitrary executor remains high risk | Path allowlist, tool tiers, confirmations, auto-checkpoints, restore, audit log |
| API/docs discovery | Version/environment and FreeCAD Python executor | Capability probe and API-lookup guidance | Installation/version discovery | Local API docs search/resource, error explanation, tool search, allowlisted invoke |

## Session and document lifecycle

| Operation | FC | SKILL | ALISAM | JAY |
|---|---|---|---|---|
| Connect/start/status/version/health | **M** connection status, FreeCAD version/environment | **M** connect and health check | **M** connect and installation info | **M** status and COM diagnostics |
| New part | **M** new generic document/body | **M** new part | **M** new part | **M** new document |
| New assembly | FreeCAD project has no dedicated assembly contract | **M** | **M** | **M** |
| New drawing | No dedicated drawing document workflow | **M** | **L** library method only | **M** drawing from model |
| List/open/activate documents | **M** list, active, open | **M** open; active state returned | **M** list/open/info | **M** list/open/activate/inspect |
| Save/Save As/close/close all | **M** | **M** | **M** | **M** |
| Rebuild/recompute | **M** | **L** used inside workflows | Rebuild occurs inside features; no dedicated tool | **M** |
| Undo/redo | **M** | **R** roadmap only | **R** roadmap only | Checkpoint/restore rather than native undo/redo |
| Checkpoint/restore/audit | Validation-based undo only | Versioned artifacts and review evidence | — | **M** checkpoint, list/restore, confirm-and-save, audit log |
| Pack and Go/dependency bundle | — | **M** | **R** roadmap | **M** |

## Sketches, parameters, and reference geometry

| Operation | FC | SKILL | ALISAM | JAY |
|---|---|---|---|---|
| Sketch on standard plane | **M** | **L** | **M** | **M** |
| Sketch on face | **M** face attachment | **L** script/API composition | **M** coordinate-selected face | **M/G** selection/persist-reference plus sketch |
| Enter/exit/status/list sketches | **M** create/info | **L** start/end/current | **M** close/status | **M** create/exit/list |
| Line/rectangle/circle | **M** | **L** | **M** | **M** |
| Arc/ellipse/polygon/slot | **M** all four | **L** arc, polygon, slot; spline too | **M** arc/polygon | No dedicated arc/ellipse/polygon/slot tool |
| Point/B-spline/spline | **M** point and B-spline | **L** spline | — | — |
| Centerline/construction geometry | **M** toggle construction | **L** relations/centerline patterns in scripts | **L** centerline method | — |
| Delete sketch geometry/constraint | **M** | — | — | Feature deletion only |
| External/projected geometry | **M** | Semantic entity references support composition | — | Persist references and selection support composition |
| Geometric constraints | **M** horizontal, vertical, coincident, parallel, perpendicular, tangent, equal, fix | **L** generic `add_sketch_relation` | — | — |
| Dimensional constraints | **M** distance, X/Y distance, radius, angle | **L** add/auto-dimension and named-dimension update | — | **M** list/set dimensions and circle diameter |
| Equations/global variables | Spreadsheet expressions and aliases | **L/R** named parameters; design-table family is reference-only | — | **M** read equations; no dedicated equation writer |
| Design tables/configurations | Spreadsheet-driven model parameters | **R** configurations/design tables reference-only | — | **M** list/copy configurations and set component configuration |
| Datum/reference plane, axis, point, coordinate system | **M** datum plane/line/point and plane primitive | **L** entity-reference helpers | Standard planes only | **M** list reference geometry, offset plane, coordinate system, URDF frame |
| Persistent/semantic entity references | FreeCAD object/subelement names | **L** semantic signatures and resolution | Face coordinates/edge indexes; fragile | **M** persist-reference capture/select plus probes |

## Part and solid modeling

| Operation | FC | SKILL | ALISAM | JAY |
|---|---|---|---|---|
| Box/cylinder | **M** direct primitives | **M** basic part | **M** by sketch + extrude | **M** by sketch + boss; demo part helper |
| Sphere/cone/torus/wedge | **M** direct primitives | **L** can be composed with revolve/other APIs; not dedicated | **G** only | **G** allowlisted API/composition only |
| Helix | **M** | — | **G** | **G** |
| 2D/3D line, plane, ellipse, prism, polygon primitives | **M** | Sketch equivalents partly **L** | Sketch line/polygon **M** | Sketch line **M**; plane creation limited to offset plane |
| Boss extrude/pad | **M** | **L** (plus basic-part MCP) | **M** | **M** |
| Cut extrude/pocket/through-all | **M** | **L** | **M** | **M** |
| Mid-plane/bidirectional extrusion | Symmetric/reversed pad options | **L** midplane | **M** bidirectional | Depends on extrude schema/API invoke |
| Revolve boss/cut | **M** revolution and groove | **L** boss revolve | **R/G** roadmap or executor | **G** invoke only |
| Sweep/loft | **M** additive, subtractive, and Part variants | **L/M** Part scripts plus dedicated OCCT loft/surface MCP | **R/G** roadmap or executor | **G** invoke only |
| Fillet/chamfer | **M** | **L** | **M** selected edges | **M** |
| Hole/Hole Wizard | **M** parametric hole/thread options | **M** blind, through, counterbore, countersink, slot; **L** Hole Wizard/thread subskill | **R/G** roadmap or executor | **G** invoke; no dedicated hole tool |
| Rib | — | **L** | **R/G** roadmap or executor | **G** |
| Draft/taper | **M** | Advanced-geometry/mold review discusses draft; no dedicated SW feature tool | **R/G** | **G** |
| Shell/thickness/thicken | **M** shell and thickness | **L/M** shell script and structured OCCT thicken | **R/G** | **G** |
| Linear/circular pattern | **M** | **L** | **R/G** roadmap or executor | **M** |
| Feature/body mirror | **M** | **L** | **R/G** roadmap or executor | **M** feature, component, and part-file mirror |
| Copy/clone body or object | **M** | Script/API composition | **G** | **M** clone solid-body part |
| Boolean add/subtract/common | **M** pairwise and multi-object | CAD-free fusion/hole cuts; no dedicated SW MCP boolean | **G** | **M** multi-body combine |
| Shell offset, slice, section | **M** offset/slice/section | Structured OCCT thicken/geometry review only | **G** | **G** |
| Compound/group and explode | **M** compound/explode | Assembly composition, not topological compound | **G** | Exploded view **M**; no FreeCAD-style compound |
| Wire/face construction | **M** | OCCT structured geometry paths | **G** | **G** |
| Delete/rename/suppress feature | **M** delete object/edit properties | Library workflows; not dedicated MCP | — | **M** delete, rename, suppress/unsuppress |
| Mass/material | Shape inspection/validation can return geometry data | Appearance is **M**; materials partly **L** | — | **M** mass, component mass, material, mass override |
| Bounding boxes and measurements | Inspect/validate object | **M/L** structured geometry measurements and review | Document/feature info only | **M** document/component/feature boxes and distance |

## Assemblies and motion

| Operation | FC | SKILL | ALISAM | JAY |
|---|---|---|---|---|
| Component tree/list/BOM precursor | Parts library is not an assembly model | **L/M** component APIs and BOM export | New assembly only | **M** tree, references, BOM |
| Insert/add component | Library-part insertion only | **M** | — | **M** |
| Fix/float, visibility, resolve lightweight | Object visibility only | **M/L** fix/float, suppress/unsuppress | — | **M** fix/unfix, visibility, resolve lightweight |
| Rename/replace/independent/dissolve/subassembly | — | **L** replace/suppress | — | **M** all listed operations |
| Component transforms/alignment | Object placement/rotate/scale | **L** transform APIs | — | **M** get/set/reset/transform and feature alignment |
| Coincident mate | — | **M/L** | — | **M** |
| Distance mate | — | **M/L** | — | **M** |
| Concentric mate | — | **M/L** | — | No named concentric tool; tangent and entity-level/low-level routes exist |
| Parallel/perpendicular mate | — | Parallel **L** | — | **M** |
| Width/tangent/plane/origin/coordinate-system mates | — | — | — | **M** |
| Limit-angle mate and travel probe | — | Revolute workflow **L** | — | **M** create/read/set and probe travel |
| Gear/revolute joint | — | **L** | — | Limit-angle/coordinate workflows; no named gear-mate tool |
| Mate list/entities/debug/dry-run/delete/suppress | — | **L** mate summary | — | **M** extensive diagnostic and lifecycle surface |
| Degrees of freedom | — | Required as review evidence but no dedicated MCP | — | **M** |
| Interference detection | Boolean common can approximate body overlap | **L** | — | **M** |
| Exploded view | — | — | — | **M** |
| Motion study create/rotary motor/run/audit | — | **M** | — | Mate travel probes only; no Motion Study tool |

## Drawings, appearance, view, and review

| Operation | FC | SKILL | ALISAM | JAY |
|---|---|---|---|---|
| Create drawing from model | — | **M** spec-driven workflow | **L** blank drawing method | **M** |
| Standard/model views | 3D standard views **M** | **M/L** drawing workflow and review | — | **M** add standard drawing views/list sheet views |
| Dimensions/annotations/notes/tables | Sketch constraints only | **M/L** dimension insertion, chains, notes, BOM/hole tables via drawing subskill | — | List dimensions and sheet views; no rich drawing annotation writer |
| Drawing structural inspection | — | **M** sheets, views, dimensions, notes, tables | — | **M** sheet views; general inspection via document tools |
| Drawing visual review/PDF evidence | Screenshot **M** but no drawing-specific review | **M** | — | PDF/PNG export **M**, no dedicated visual review contract |
| 3D screenshot/preview | **M** PNG screenshot | **M** BMP previews/review report | **R** roadmap screenshot | **M** PNG export |
| Standard camera views/fit/zoom/custom camera | **M** | **L** review scripts set views/fit | **R** roadmap | Drawing standard views; limited 3D view control |
| Visibility/display mode/color | **M** | **M/L** document/component/feature appearance and palettes | — | **M** component visibility; material but no general display-mode tool |
| Workbench/UI mode control | **M** list/activate FreeCAD workbench | — | — | — |
| Geometry/document validation | **M** object/document validation and undo-if-invalid | **M** geometry, file, delivery, drawing, hole, and motion review | Diagnostics only | **M** diagnostics, measurements, interferences, broken refs, probes |

## Import, export, manufacturing, and downstream workflows

| Operation | FC | SKILL | ALISAM | JAY |
|---|---|---|---|---|
| Native SolidWorks formats | Not applicable | **M** create/open/save SLDPRT/SLDASM/SLDDRW | **M** create/open/save | **M** open/save/create |
| STEP import/export | **M** both | Export **M**; headless write **M** | Open via generic document path; no dedicated export | **M** both |
| IGES import/export | Export **M** | Export/headless write **M** | — | — |
| Parasolid export | — | **M** | — | — |
| STL import/export | **M** both | Export/headless write **M** | — | Export **M** |
| OBJ/3MF/GLB/BREP | OBJ/3MF export **M** | Headless OBJ/GLB/BREP **M** and mesh-reference import **L** | — | — |
| DXF/SVG | — | DXF export and headless DXF/SVG **M** | — | — |
| PDF/PNG/image | Screenshot PNG **M** | PDF/PNG and review previews **M** | — | PDF/PNG export **M** |
| Batch export/hash manifest | — | **M** | — | Pack and Go/export tools; no explicit batch export tool |
| Parts/library insertion | **M** FreeCAD parts library | Component insertion **M** | — | Component insertion **M** |
| Custom properties | Generic object properties **M** | **M** file/config properties | — | **M** |
| Assembly BOM CSV | — | **M** | — | BOM precursor **M** |
| DFM checks | Object validity only | **M** machining, sheet metal, laser, and 3D-print risk rules | — | Interference/mass/measure primitives only |
| Sheet metal/flat pattern | — | **L/R** flat-pattern DXF helper; modeling is reference-only | **R** roadmap | — |
| Weldments/cut lists | — | **R** reference-only | **R** roadmap | — |
| Routing | — | **M/R** neutral review and native preflight; native authoring blocked | — | — |
| FEA/simulation | — | **M/R** structured CalculiX workflows; engineering review required | **R** roadmap | — |
| Advanced surfaces/mold | Loft/sweep/thickness **M**, not mold-specific | **M/R** structured OCCT surfaces and mold-plan validation; not full mold authoring | **R** roadmap | Low-level invoke only |
| Text/engraving/emboss | **M** ShapeString, face conversion, surface text, extrusion | — | **G** | **G** |
| Spreadsheet/CSV parameter control | **M** spreadsheet, aliases, property binding, CSV import/export | Named dimensions and design-table reference | — | Dimensions/configurations/equations, but no spreadsheet tool |
| URDF/robot export | — | — | — | **M** readiness, frame creation, package export, URDF generation, transforms |

## Main conclusions

1. **FC has the broadest direct part/sketch construction vocabulary.** Its
   constraints, primitive solids, topology operations, spreadsheets, validation,
   view control, and text-on-surface tools identify many SolidWorks-equivalent
   operations missing from the SolidWorks projects.
2. **SKILL has the broadest end-to-end engineering workflow vocabulary.** It
   covers drawings, evidence-based review, BOM/delivery, DFM, routing preflight,
   Motion Studies, and structured FEA, although many operations are library or
   pilot capabilities rather than dedicated MCP tools.
3. **ALISAM is useful as a minimal baseline.** It demonstrates a small natural
   modeling surface and a generic escape hatch, but has little assembly,
   drawing, safety, selection, inspection, or delivery coverage.
4. **JAY has the strongest typed SolidWorks assembly/diagnostic/safety surface.**
   Its gaps are most visible in rich sketch constraints, advanced feature
   creation, drawing annotations, manufacturing workflows, and native Motion
   Study/FEA operations.
5. A new project should combine FC's modeling granularity, SKILL's workflow and
   review gates, and JAY's typed contracts, persistent references, checkpoints,
   path safety, and auditability. The resulting backlog is in
   [SolidWorks target requirements](solidworks-target-requirements.md).
