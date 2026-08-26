# Requirements for a new SolidWorks MCP/skill project

This is the recommended union backlog derived from all four projects. It is
written as an implementation checklist rather than a claim that every item is
equally mature in the source projects.

## Goal and product boundary

The target should expose typed, discoverable, auditable operations over the
SolidWorks API. A generic COM/API escape hatch is useful for research and rare
operations, but it should not be counted as feature coverage. Each common CAD
operation should have its own validated input schema, deterministic result
shape, safety classification, and read-back verification.

Three execution layers are useful:

1. **MCP primitives** — small typed operations such as create sketch, add line,
   set dimension, insert component, or add mate.
2. **Skill workflows** — multi-step engineering tasks such as a bracket, drawing
   package, BOM delivery, DFM review, or motion-study audit.
3. **Low-level API access** — allowlisted introspection/invoke for unsupported
   calls, diagnostics, and development. Writes must be separately enabled and
   audited.

## Priority model

| Priority | Meaning |
|---|---|
| **P0** | Required foundation before model-writing tools are safe and dependable. |
| **P1** | Core part creation/editing needed for a useful first release. |
| **P2** | Broad production workflow coverage: assemblies, drawings, delivery, and review. |
| **P3** | Advanced/specialized domains or lower-frequency parity features. |

| Priority | Requirement count | Domains |
|---|---:|---|
| P0 | 29 | System, safety, references, discovery |
| P1 | 57 | Documents, sketches, constraints, parameters, datum, part features, view |
| P2 | 47 | Assemblies, mates, motion, drawings, I/O, review |
| P3 | 19 | Advanced manufacturing, FEA, macros/libraries/URDF |
| **Total** | **152** | Stable requirement IDs; this total is coincidentally the same as FC's current tool count. |

## P0 — platform, safety, and reliable entity addressing

### Session and compatibility

- [ ] **SYS-001** Attach to a running SolidWorks instance and optionally start a
  visible instance.
- [ ] **SYS-002** Report installed SolidWorks version/service pack, COM
  registration, process/session identity, active document, and add-in/type-library
  availability.
- [ ] **SYS-003** Serialize all SolidWorks COM calls on one STA-compatible worker
  or session queue; reject accidental concurrent mutation.
- [ ] **SYS-004** Detect busy/rejected COM calls and implement bounded retry with
  useful error classification.
- [ ] **SYS-005** Provide health, latency, worker mutex/session, and dependency
  diagnostics without requiring an active document.
- [ ] **SYS-006** Normalize user units while preserving the SolidWorks API's
  internal meter/radian conventions. Support at least mm, cm, m, inch, and foot.
- [ ] **SYS-007** Resolve localized standard plane/view names and avoid assuming
  an English feature tree.

### Typed contracts and safety

- [ ] **SAFE-001** Give every operation a strict schema, bounded collection sizes,
  enum values, and finite/range checks for geometry inputs.
- [ ] **SAFE-002** Classify tools as read-only, model mutation, destructive model
  mutation, or non-model side effect.
- [ ] **SAFE-003** Require explicit confirmation for destructive operations and
  overwrites.
- [ ] **SAFE-004** Restrict input/output paths to configured roots, canonicalize
  paths, reject traversal, and distinguish existing inputs from new outputs.
- [ ] **SAFE-005** Checkpoint before risky mutations; list and restore checkpoints.
- [ ] **SAFE-006** Keep an append-only audit record for writes, including tool,
  normalized arguments, document, result, checkpoint, timestamp, and error.
- [ ] **SAFE-007** Support dry-run/preflight where the API allows it, especially
  for mates, selection, export, replacement, and delivery packaging.
- [ ] **SAFE-008** Use versioned output filenames or explicit overwrite policies;
  never silently replace engineering deliverables.
- [ ] **SAFE-009** Return stable error codes plus decoded SolidWorks save/open/
  rebuild/mate errors and actionable remediation.
- [ ] **SAFE-010** Do not advertise success until the operation is read back from
  the model, filesystem, or analysis result.

### Selection and stable references

- [ ] **REF-001** Inspect and clear the current selection; select by typed name and
  selection mark.
- [ ] **REF-002** Resolve documents, components, configurations, features,
  sketches, bodies, faces, edges, vertices, planes, axes, points, and coordinate
  systems by a structured reference.
- [ ] **REF-003** Capture and resolve SolidWorks persistent references (for
  example through model-extension persist-reference APIs).
- [ ] **REF-004** Provide semantic fallback references using component path,
  feature ancestry, geometry type, location, direction, radius/area, and
  tolerances.
- [ ] **REF-005** Expose selection probes: ray-to-face, planar-face lookup,
  cylindrical-face lookup, feature faces, body ownership, and candidate mate
  entities.
- [ ] **REF-006** Detect stale/ambiguous references and return candidates rather
  than silently choosing the first face or edge.
- [ ] **REF-007** Make entity reference objects serializable so workflows can
  checkpoint and resume.

### Discovery and low-level access

- [ ] **DISC-001** Search the registered tool catalog by name, domain, tags, and
  description.
- [ ] **DISC-002** Search a local, version-tagged SolidWorks API reference and
  warn when the installed version differs.
- [ ] **DISC-003** Provide an allowlisted read-only API/property invoker and an
  efficient batch form for multi-call inspection.
- [ ] **DISC-004** Gate low-level writes behind a separate configuration flag,
  confirmation, path policy, audit, and checkpoint.
- [ ] **DISC-005** Provide a tool/worker capability probe so callers can branch on
  edition, license, add-in, API signature, and verified-version evidence.

## P1 — documents, sketches, parameters, and core part modeling

### Document lifecycle

- [ ] **DOC-001** Create part, assembly, and drawing documents from explicit or
  discovered templates.
- [ ] **DOC-002** Open SLDPRT, SLDASM, SLDDRW, and supported neutral formats with
  decoded warnings/errors and optional read-only mode.
- [ ] **DOC-003** List open documents; inspect type, title, path, saved/dirty state,
  active configuration/sheet, units, and custom properties.
- [ ] **DOC-004** Activate a document by path/title and reject ambiguous matches.
- [ ] **DOC-005** Save, Save As, close one, and close all with explicit dirty-file
  behavior.
- [ ] **DOC-006** Rebuild/force rebuild and report feature/rebuild errors.
- [ ] **DOC-007** Native undo/redo and availability status, in addition to durable
  checkpoints.

### Sketch creation and geometry

- [ ] **SK-001** Start a 2D sketch on a standard plane, named plane, planar face,
  or structured reference; exit a sketch and report active sketch state.
- [ ] **SK-002** List and inspect sketches, including geometry, constraints,
  construction state, fully-defined state, and transform/support.
- [ ] **SK-003** Create line, centerline, point, corner/center rectangle, circle,
  three-point/center arc, ellipse, regular polygon, straight/arc slot, and spline.
- [ ] **SK-004** Toggle construction geometry.
- [ ] **SK-005** Project/convert external geometry and return stable references to
  the created entities.
- [ ] **SK-006** Delete sketch geometry and delete constraints by stable index/id.
- [ ] **SK-007** Trim, extend, split, offset, mirror, move, rotate, scale, and
  pattern sketch entities.
- [ ] **SK-008** Create sketch text with font/alignment/path options so engraving,
  emboss, and wrap workflows do not require arbitrary macros.

### Sketch constraints and dimensions

- [ ] **CON-001** Add/remove horizontal, vertical, coincident, collinear, parallel,
  perpendicular, tangent, equal, concentric, midpoint, symmetric, fix, and merge
  relations.
- [ ] **CON-002** Add distance, horizontal distance, vertical distance, radius,
  diameter, angle, and arc-length dimensions.
- [ ] **CON-003** Set/read a dimension in caller units, including tolerance,
  equation/driven state, name, and configuration scope.
- [ ] **CON-004** Auto-dimension a sketch only under an explicit policy and report
  every dimension/relation created.
- [ ] **CON-005** Validate under/over-defined state and dangling relations after
  every constraint batch.

### Parameters, configurations, and model metadata

- [ ] **PAR-001** List, read, and update named driving dimensions with before/
  after values and rebuild evidence.
- [ ] **PAR-002** Read and write equations/global variables, including dependency
  and circular-reference diagnostics.
- [ ] **PAR-003** List/create/copy/delete/rename configurations and set the active
  configuration.
- [ ] **PAR-004** Read and write configuration-specific dimension values and
  suppression states.
- [ ] **PAR-005** Import/export a parameter table (CSV/XLSX-neutral contract) and
  optionally connect it to a SolidWorks design table.
- [ ] **PAR-006** Read/write file-level and configuration-level custom properties,
  with evaluated and raw values.
- [ ] **PAR-007** Read/list display states and bind component appearance/visibility
  policies where appropriate.

### Reference geometry

- [ ] **DAT-001** List and inspect origin, standard/named planes, axes, points,
  coordinate systems, and temporary axes.
- [ ] **DAT-002** Create offset/angle/mid/three-point/tangent reference planes.
- [ ] **DAT-003** Create reference axes and points from structured entity inputs.
- [ ] **DAT-004** Create a coordinate system from origin and axis references and
  return its transform.
- [ ] **DAT-005** Rename, suppress, delete, and persistently reference datum
  features.

### Core features and bodies

- [ ] **FEAT-001** Boss extrude with blind, through-all, up-to-surface/body,
  mid-plane, two-direction, thin-feature, draft, merge, and feature-scope options.
- [ ] **FEAT-002** Cut extrude with the same applicable end conditions and scope.
- [ ] **FEAT-003** Revolved boss/base and revolved cut with axis reference,
  direction, angle, and thin options.
- [ ] **FEAT-004** Sweep boss/cut with profile, path, guide curves, orientation,
  twist, and merge/scope options.
- [ ] **FEAT-005** Loft/boundary boss and cut across multiple profiles, with guide
  curves, start/end constraints, closed/centerline options, and read-back.
- [ ] **FEAT-006** Fillet variants and chamfer variants using stable edge/face
  references, not implicit current selection.
- [ ] **FEAT-007** Linear, circular, curve-driven, sketch-driven, table-driven,
  fill, and variable patterns with skipped instances.
- [ ] **FEAT-008** Mirror features, faces, bodies, and whole parts.
- [ ] **FEAT-009** Shell and thicken with face removal, direction, multi-thickness,
  and failure diagnostics.
- [ ] **FEAT-010** Draft by neutral plane/parting line/step draft with face lists
  and direction.
- [ ] **FEAT-011** Rib with thickness, direction, draft, contour, and merge scope.
- [ ] **FEAT-012** Hole Wizard/simple-hole support for blind, through, tapped,
  counterbore, countersink, spotface, and compound holes, including standard,
  size, fit, thread, end condition, and position sketch.
- [ ] **FEAT-013** Straight/arc/semicircular slots and hole/slot patterns with
  datum-based position acceptance.
- [ ] **FEAT-014** Direct/composed primitive workflows for box, cylinder, sphere,
  cone/frustum, torus, wedge, prism, regular polygon extrusion, and helix/spring.
- [ ] **FEAT-015** Rename, list, inspect, edit definition, reorder when safe,
  suppress/unsuppress, and delete features.
- [ ] **FEAT-016** List solid/surface bodies and map each body to owning features,
  material, visibility, and mass properties.
- [ ] **FEAT-017** Combine bodies with add/subtract/common; copy/move/rotate/scale,
  mirror, split, intersect, delete/keep, and save/clone a body to a part.
- [ ] **FEAT-018** Create/knit/trim/extend/offset surfaces and convert face/wire
  inputs where the API supports a stable implementation.
- [ ] **FEAT-019** Measure and inspect bounding box, volume, area, mass, center of
  mass, inertia, density, topology counts, and validity/rebuild state.
- [ ] **FEAT-020** Assign/read part, body, and component materials and optional
  mass override with explicit units.

### Appearance and view

- [ ] **VIEW-001** Set/read document, body, feature, face, and component
  appearance; support colors, transparency, and named material values.
- [ ] **VIEW-002** Set component/body/feature visibility and display mode.
- [ ] **VIEW-003** Set front/back/left/right/top/bottom/isometric/trimetric/dimetric
  views, fit, zoom, and custom camera orientation/position.
- [ ] **VIEW-004** Capture a PNG/BMP preview at requested dimensions after clearing
  selection and fitting the model.
- [ ] **VIEW-005** Create/read exploded views and optionally export animation
  frames where stable.

## P2 — assemblies, drawings, import/export, and review

### Assembly components

- [ ] **ASM-001** Insert part/subassembly at a transform with chosen
  configuration and optional fixed state.
- [ ] **ASM-002** Return a recursive component tree with path, referenced
  configuration, quantity, suppression, lightweight, hidden, fixed, envelope,
  virtual, and broken-reference state.
- [ ] **ASM-003** Resolve lightweight components; suppress/unsuppress; fix/float;
  show/hide; and set referenced configuration.
- [ ] **ASM-004** Get/set/reset component transforms and align a component to a
  feature/reference.
- [ ] **ASM-005** Rename, replace one/many by path, make independent, dissolve,
  create subassembly, mirror, and copy with mates.
- [ ] **ASM-006** Create virtual components and save externally under an explicit
  path policy.
- [ ] **ASM-007** Report broken/external/in-context references and dependency
  paths before replacement or Pack and Go.

### Mates and kinematics

- [ ] **MATE-001** Coincident, concentric, distance, angle, parallel,
  perpendicular, tangent, width, symmetric, lock, gear, rack-and-pinion, screw,
  universal-joint, slot, cam, hinge, linear-coupler, path, and coordinate-system
  mate contracts where supported by the installed version/license.
- [ ] **MATE-002** Limit-distance and limit-angle mates with read/update of min,
  max, current value, flip/alignment, and units.
- [ ] **MATE-003** Mate standard/named planes, origins, axes, faces, edges,
  vertices, and component coordinate systems through structured references.
- [ ] **MATE-004** List mates and mate entities; inspect type, alignment,
  suppression, status/error, owning components, and values.
- [ ] **MATE-005** Probe/dry-run candidate mate entities before mutation and return
  likely failure reasons.
- [ ] **MATE-006** Rename, suppress/unsuppress, edit, delete one/range/all, and
  replay a mate sequence with checkpoint rollback.
- [ ] **MATE-007** Report remaining assembly degrees of freedom and probe angular/
  linear travel.
- [ ] **MATE-008** Run interference and clearance detection with component/body
  references and volume evidence.

### Motion Study

- [ ] **MOTION-001** Detect/load Motion Study support and enumerate studies.
- [ ] **MOTION-002** Create/configure a study with type, duration, frame rate, and
  result folder.
- [ ] **MOTION-003** Add constant-speed/variable rotary and linear motors using
  stable geometry references.
- [ ] **MOTION-004** Add gravity, forces, torques, springs, dampers, contact, and
  friction when supported and licensed.
- [ ] **MOTION-005** Calculate and optionally play the study; capture solver
  status and result timestamps.
- [ ] **MOTION-006** Inspect and validate study type, duration, motor/force/contact
  counts, stale/missing results, and requested outputs.
- [ ] **MOTION-007** Export plots/data/animation evidence under controlled paths.

### Drawings

- [ ] **DRW-001** Create a drawing from part/assembly using an explicit template,
  sheet size, projection standard, scale, units, and title-block/property mapping.
- [ ] **DRW-002** Add standard, projected, auxiliary, section, detail, broken-out,
  crop, relative, and exploded-model views with positions/scales.
- [ ] **DRW-003** List/inspect sheets and views, including referenced model/
  configuration, orientation, scale, outline, alignment, and display style.
- [ ] **DRW-004** Import model items/dimensions and create drawing dimensions with
  placement, tolerances, precision, arrows, and formatting.
- [ ] **DRW-005** Create center marks/lines, hole callouts, datum symbols, GD&T,
  surface-finish, weld, balloon, revision, and general note annotations.
- [ ] **DRW-006** Create/update BOM, hole, revision, weldment cut-list, and general
  tables; inspect their rows/cells and component links.
- [ ] **DRW-007** Create additional sheets, change format/template, reorder views,
  and manage layer/line/font standards.
- [ ] **DRW-008** Inspect dimensions, notes, tables, dangling annotations, overlaps,
  clipping, empty views, and missing required views/callouts.
- [ ] **DRW-009** Export each sheet and full drawing to PDF/DXF/DWG/image and
  generate preview plus machine-readable review evidence.
- [ ] **DRW-010** Keep drawing visual acceptance human-reviewable; do not claim
  that approximate annotation bounding boxes prove a production drawing.

### Import/export and delivery

- [ ] **IO-001** Import STEP, IGES, Parasolid, STL, and OBJ/mesh reference with
  options and import diagnostics.
- [ ] **IO-002** Export native/neutral formats as applicable: STEP, IGES,
  Parasolid, STL, 3MF, OBJ, GLB, BREP, DXF, DWG, PDF, PNG/BMP, and SVG.
- [ ] **IO-003** Expose tessellation/quality/unit/body-selection settings for mesh
  and neutral export and verify file type, size, timestamp, and reopen when
  feasible.
- [ ] **IO-004** Batch export multiple models/configurations/sheets/formats with a
  manifest, hashes, per-item status, and no silent overwrite.
- [ ] **IO-005** Export sheet-metal flat-pattern DXF with bend/sketch options and
  verify that a real flat pattern exists.
- [ ] **IO-006** Native Pack and Go with drawings, simulation results, Toolbox,
  external references, prefix/suffix/flatten options, dependency audit, and
  fallback policy.
- [ ] **IO-007** Export a component/property BOM CSV and a traceability matrix;
  retain a warning that it is a precursor until checked against a native BOM.
- [ ] **IO-008** Optionally provide CAD-free open-format writing, but keep it in a
  separate backend that never fabricates SLDPRT/SLDASM/SLDDRW.

### Inspection, validation, and evidence

- [ ] **REV-001** Inspect document, feature tree, sketches, bodies, configurations,
  equations, dimensions, properties, components, mates, sheets, views, and
  external references without mutation.
- [ ] **REV-002** Validate rebuild state, invalid geometry, zero/negative volume,
  topology changes, missing references, suppressed/dangling features, and dirty
  state.
- [ ] **REV-003** Capture before/after geometry measurements and previews for
  mutations.
- [ ] **REV-004** Inspect holes/slots by B-Rep geometry and compare quantity,
  diameter/segments, depth, axis, and datum position against acceptance criteria.
- [ ] **REV-005** Produce structured JSON plus human-readable Markdown review
  reports with pass/warn/block outcomes and source artifact hashes.
- [ ] **REV-006** Provide an atomic `safe_execute` workflow: checkpoint, mutate,
  rebuild, validate selected invariants, and roll back on failure.
- [ ] **REV-007** Make review policies caller-supplied and domain-specific; a file
  existence check is not an engineering validation.

## P3 — specialized and parity capabilities

### Advanced geometry and manufacturing

- [ ] **ADV-001** Surface loft/boundary/sweep/fill, knit, trim, extend, offset,
  ruled surface, freeform, and thicken with continuity and curvature evidence.
- [ ] **ADV-002** Discrete G0/G1/G2 and minimum-curvature-radius checks, clearly
  labeled as sampling rather than proof of global quality/self-intersection.
- [ ] **ADV-003** Mold draft analysis, parting-line/surface plan, shut-off/core/
  cavity references, tooling direction, and shrinkage; distinguish plan validation
  from actual core/cavity authoring.
- [ ] **ADV-004** Sheet-metal base flange/tab, edge/miter flange, hem, jog, bend,
  unfold/fold, corner relief, forming tool, gauge/K-factor, and flat-pattern
  validation/export.
- [ ] **ADV-005** Weldment 3D sketch, structural member, trim/extend, gusset, end
  cap, weld bead, cut-list update, and cut-list property/BOM export.
- [ ] **ADV-006** Engrave/emboss/deboss/wrap sketch text on planar/cylindrical
  faces, covering the FreeCAD ShapeString workflows.
- [ ] **ADV-007** Routing authoring for pipes/tubes/electrical routes only after
  type-library, add-in, and license evidence; include route endpoints, segments,
  fittings, bend radii, supports, clearance, and BOM.
- [ ] **ADV-008** Supplier-profile DFM rules for machining, sheet metal, laser
  cutting, FDM, and SLA with explicit missing-evidence blocking.

### Simulation/FEA

- [ ] **FEA-001** Preflight installed SolidWorks Simulation and/or allowlisted
  external solvers without arbitrary process execution.
- [ ] **FEA-002** Structured linear static study: materials, shells/solids/beams,
  connectors/contact, fixtures, loads, mesh, solve, and result extraction.
- [ ] **FEA-003** Constrained nonlinear/static plasticity/contact workflows only
  where inputs and solver support are explicit.
- [ ] **FEA-004** Mesh convergence across multiple levels using displacement,
  stress, strain, contact penetration, and pressure metrics as applicable.
- [ ] **FEA-005** Extract displacement, stress, strain, factor-of-safety/contact
  data and plots with units, mesh statistics, solver logs, and provenance.
- [ ] **FEA-006** Always mark FEA as review-required and never describe it as
  certification or proof of safety.

### Macros, reusable libraries, and downstream robotics

- [ ] **AUTO-001** List/read/create/run/delete versioned macros only if macro
  execution is needed; validate language/module structure and apply an allowlist
  or explicit high-risk gate.
- [ ] **AUTO-002** Reusable parts/features library with search, metadata,
  insertion, configuration choice, transform, and dependency checks.
- [ ] **AUTO-003** Natural-language brief to a structured parametric plan with
  assumptions, unresolved engineering inputs, operation DAG, and review gates.
- [ ] **AUTO-004** URDF readiness: component tree, named link frames/joint axes,
  transforms, inertial properties, joint/mate limits, and missing-reference report.
- [ ] **AUTO-005** Add link coordinate systems, export versioned meshes/package
  manifest, and generate URDF with validation.

## FreeCAD-to-SolidWorks crosswalk

Every dedicated FC tool is covered below either individually or in a coherent
group. The right column identifies the SolidWorks concept the new project should
expose; it does not imply one-to-one API signatures.

| FreeCAD operations | SolidWorks-equivalent requirement |
|---|---|
| `list_documents`, `get_active_document`, `create_document`, `open_document`, `save_document`, `close_document`, `recompute_document` | `DOC-001`–`DOC-006`: `ISldWorks`/`IModelDoc2` lifecycle, activation, save/close, rebuild. |
| `get_freecad_version`, `get_connection_status`, `get_mcp_server_environment`, `get_console_output` | `SYS-001`–`SYS-005`: version/session/worker/diagnostic status and logs. |
| `execute_python` | `DISC-003`–`DISC-004`: prefer allowlisted SolidWorks API invoke; an arbitrary executor, if retained, is a separately gated development feature. |
| `list_objects`, `inspect_object`, `create_object`, `edit_object`, `delete_object` | Typed feature/body/sketch/reference inspection and lifecycle (`REV-001`, `FEAT-015`–`FEAT-016`); do not expose arbitrary COM object construction as the primary API. |
| `create_box`, `create_cylinder`, `create_sphere`, `create_cone`, `create_torus`, `create_wedge`, `create_prism`, `create_regular_polygon` | `FEAT-014`: deterministic sketch + boss/revolve workflows with returned feature/body references. |
| `create_helix` | `FEAT-014`: helix/spiral feature with pitch/height/revolution/taper/handedness and axis/sketch reference. |
| `create_line`, `create_plane`, `create_ellipse` | `SK-003` and `DAT-002`: sketch/3D line where applicable, reference plane, ellipse. |
| `boolean_operation`, `fuse_all`, `common_all` | `FEAT-017`: multi-body Combine Add/Subtract/Common with deterministic target/tool bodies. |
| `set_placement`, `rotate_object`, `scale_object`, `copy_object`, `mirror_object` | `FEAT-017` for bodies/features and `ASM-004`–`ASM-005` for components. Preserve transform matrices and units. |
| `shell_object`, `offset_3d`, `slice_shape`, `section_shape` | `FEAT-009`, `FEAT-017`, `FEAT-018`: shell/thicken, offset surface/body, split/intersect/section inspection. |
| `make_compound`, `explode_compound` | SolidWorks multi-body grouping/save-bodies and assembly/subassembly/exploded-view workflows (`FEAT-016`–`FEAT-017`, `ASM-005`, `VIEW-005`). |
| `make_wire`, `make_face` | `FEAT-018`: curve/wire and planar/bounded surface construction with closed-loop validation. |
| `extrude_shape`, `revolve_shape`, `part_loft`, `part_sweep` | `FEAT-001`, `FEAT-003`–`FEAT-005`, including solid/surface and additive/subtractive variants. |
| `get_selection`, `set_selection`, `clear_selection` | `REF-001` plus stable structured selections and marks. |
| `create_partdesign_body` | Part/multi-body context and active-body selection under `FEAT-016`. |
| `create_sketch`, `get_sketch_info` | `SK-001`–`SK-002`. |
| `add_sketch_line`, `add_sketch_rectangle`, `add_sketch_circle`, `add_sketch_arc`, `add_sketch_point`, `add_sketch_ellipse`, `add_sketch_polygon`, `add_sketch_slot`, `add_sketch_bspline` | `SK-003`: typed `ISketchManager` geometry operations. |
| `toggle_construction`, `add_external_geometry`, `delete_sketch_geometry` | `SK-004`–`SK-007`: construction, converted/projected entities, delete/edit operations. |
| `add_sketch_constraint`, `constrain_horizontal`, `constrain_vertical`, `constrain_coincident`, `constrain_parallel`, `constrain_perpendicular`, `constrain_tangent`, `constrain_equal`, `constrain_fix` | `CON-001` and `CON-005`: typed sketch relations with solver-state verification. |
| `constrain_distance`, `constrain_distance_x`, `constrain_distance_y`, `constrain_radius`, `constrain_angle` | `CON-002`–`CON-005`: display dimensions and relation state with units/tolerances. |
| `delete_sketch_constraint` | `CON-001`/`SK-006`: delete relation/dimension by stable sketch-local id. |
| `pad_sketch`, `pocket_sketch` | `FEAT-001`–`FEAT-002`: boss/cut extrudes and end conditions. |
| `revolution_sketch`, `groove_sketch` | `FEAT-003`: revolved boss/base and revolved cut. |
| `loft_sketches`, `sweep_sketch`, `subtractive_loft`, `subtractive_pipe` | `FEAT-004`–`FEAT-005`: sweep/loft boss, cut, and surface forms. |
| `fillet_edges`, `chamfer_edges` | `FEAT-006`: stable edge/face references and variant options. |
| `create_hole` | `FEAT-012`–`FEAT-013`: Hole Wizard, thread data, center positions, and B-Rep read-back. |
| `linear_pattern`, `polar_pattern` | `FEAT-007`: linear and circular patterns; extend to other SolidWorks pattern families. |
| `mirrored_feature` | `FEAT-008`. |
| `create_datum_plane`, `create_datum_line`, `create_datum_point` | `DAT-001`–`DAT-005`: reference plane/axis/point and persistent references. |
| `draft_feature`, `thickness_feature` | `FEAT-009`–`FEAT-010`: thicken/shell and draft. |
| `spreadsheet_create`, cell/alias/range tools, `spreadsheet_bind_property`, CSV import/export | `PAR-001`–`PAR-005`: equations/global variables, configurations/design tables, custom neutral parameter table. |
| `get_screenshot`, standard view/fit/zoom/camera tools | `VIEW-003`–`VIEW-004`: named/custom views and deterministic preview capture. |
| visibility/display/color tools | `VIEW-001`–`VIEW-002`: document/body/feature/face/component appearance and visibility. |
| `undo`, `redo`, `get_undo_redo_status` | `DOC-007`, supplemented by durable checkpoints. |
| `list_workbenches`, `activate_workbench` | No direct SolidWorks workbench equivalent; replace with document/edit-mode/add-in capability state under `SYS-002`/`DISC-005`. |
| `list_parts_library`, `insert_part_from_library` | `AUTO-002`: reusable library search and component/feature insertion. |
| `list_macros`, `run_macro`, `create_macro`, `read_macro`, `delete_macro`, `create_macro_from_template` | `AUTO-001`: optional guarded VBA/VSTA macro lifecycle. |
| `validate_object`, `validate_document`, `undo_if_invalid`, `safe_execute` | `REV-002` and `REV-006`: rebuild/geometry/invariant validation with checkpoint rollback. |
| ShapeString/font/sketch/face/surface/extrusion text tools | `SK-008` and `ADV-006`: sketch text, wrap, engrave, emboss, and deboss. |
| STEP/STL import/export and 3MF/OBJ/IGES export | `IO-001`–`IO-003`: use SolidWorks translators where supported and verify artifacts. |

## Suggested initial MCP domains

A tool registry grouped this way is easier to search and permission than one
flat list:

`system`, `document`, `selection`, `reference`, `sketch`, `constraint`,
`parameter`, `configuration`, `datum`, `feature`, `body`, `measure`, `material`,
`appearance`, `view`, `assembly`, `mate`, `motion`, `drawing`, `import`, `export`,
`delivery`, `review`, `dfm`, `sheet-metal`, `weldment`, `routing`, `simulation`,
`surface`, `mold`, `macro`, and `urdf`.

## Definition of done for each operation

An operation is not complete merely because a COM call returned without throwing.
Each dedicated operation should satisfy the following checklist:

- [ ] Strict input and output schemas, units, enum values, defaults, and examples.
- [ ] Document-type and edit-context preconditions.
- [ ] Stable selection/reference inputs; no undocumented dependence on UI
  selection order.
- [ ] Version/API-signature handling for the supported SolidWorks matrix.
- [ ] Path, overwrite, confirmation, checkpoint, and audit policy.
- [ ] Rebuild and API error decoding.
- [ ] Read-back verification of the created/changed feature or artifact.
- [ ] Idempotency behavior and retry semantics documented.
- [ ] Unit tests without SolidWorks plus a real-machine regression fixture.
- [ ] Failure tests for missing document, wrong type, stale reference, invalid
  geometry, save failure, busy COM server, and unsupported version/license.
- [ ] Generated tool documentation and inclusion in tool/domain search.
- [ ] A workflow-level test when the primitive participates in a common task.

## Recommended implementation sequence

1. Build the P0 session worker, reference model, path policy, checkpoints, audit,
   and read-only inspection surface.
2. Implement P1 sketches/constraints/dimensions and the core feature set, because
   these enable deterministic parts without arbitrary scripts.
3. Add assembly components and the common mate set with probe/read-back/DOF
   diagnostics.
4. Add drawings, export/delivery, and structured review so created models can be
   validated and handed off.
5. Add configurations, richer patterns/features, Motion Study, sheet metal,
   weldments, routing, FEA, surfaces/molds, and URDF as separately gated domains.

This ordering captures the strongest ideas of the audited projects: FC's fine
modeling vocabulary, SKILL's engineering workflows and evidence gates, ALISAM's
simple approachable baseline, and JAY's typed SolidWorks worker, persistent
references, checkpoints, confirmations, path safety, and diagnostics.
