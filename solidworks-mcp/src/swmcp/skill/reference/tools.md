# Tool index

Generated from the catalog by `solidworks-mcp --write-artifacts`; do not edit.

115 operations. Call one from the shell with `python -m swmcp call <operation> '<json>'`, or from Python as `sw.<method>(...)`. `python -m swmcp describe <operation>` prints its full input schema.

Safety: **read** changes nothing. **mutation** changes the model and is checkpointed first. **side effect** writes a file, opens a document, or changes the UI. **confirm** means the call is refused unless it carries `confirm: true`.

Tier only decides which operations an MCP client is shown. The library and the CLI can call every operation at every tier.

## system

| Operation | Method | Tier | Safety | What it does |
|---|---|---|---|---|
| `sw_capabilities` | `capabilities` | extended | read | Probe what this installation can actually do — edition, add-ins, type libraries, and template availability — so a caller can branch on evidence rather than assuming a feature exists. |
| `sw_connect` | `connect` | core | side effect | Attach to a running SOLIDWORKS instance, optionally launching one. Reports the version, the ProgID that worked, and the active document. |
| `sw_health` | `health` | core | read | Report worker, session, and dependency health without needing an active document. The snapshot answers immediately even while a COM call is stuck, so a wedged worker can still be diagnosed. |
| `sw_resolve_names` | `resolve_names` | extended | read | Resolve standard plane names and document units for the target document, reporting both the display name and the locale-invariant type token so callers never string-match an English feature tree. |
| `sw_system_info` | `system_info` | core | read | Report the SOLIDWORKS version and service pack, COM registration, install location, session identity, active document, and constant-table provenance. |

## safety

| Operation | Method | Tier | Safety | What it does |
|---|---|---|---|---|
| `sw_audit_tail` | `audit_tail` | extended | read | Read the most recent entries from the append-only write audit, including the checkpoint each mutation was covered by. |
| `sw_checkpoint_create` | `checkpoint_create` | core | side effect | Snapshot a document so a later change can be rolled back. Prefers a SaveAs-Copy so unsaved session state is captured, and reports which method was used. |
| `sw_checkpoint_list` | `checkpoint_list` | core | read | List the snapshots available for a document, newest first, with sizes and times. |
| `sw_checkpoint_restore` | `checkpoint_restore` | core | destructive mutation, confirm | Restore a document from a checkpoint, overwriting its current contents. A snapshot of the present state is staged first, so restoring by mistake is itself reversible. |
| `sw_explain_error` | `explain_error` | extended | read | Explain an error code, an HRESULT, or a SOLIDWORKS status value, returning what it means and the concrete steps that address it. |
| `sw_path_policy` | `path_policy` | extended | read | Check a path against the output-root policy and the overwrite rules before using it, returning the normalized path and the non-clobbering name that would actually be written. |
| `sw_safe_execute` | `safe_execute` | core | destructive mutation, confirm | Run a sequence of operations under one checkpoint, check the declared invariants afterwards, and roll the whole thing back if any step fails or any invariant does not hold. |

## discovery

| Operation | Method | Tier | Safety | What it does |
|---|---|---|---|---|
| `sw_api_batch_invoke` | `api_batch_invoke` | advanced | read | Read several SOLIDWORKS API members in one round trip, applying the same read-only allowlist to each and reporting failures per call. |
| `sw_api_invoke` | `api_invoke` | advanced | read | Read a SOLIDWORKS API member on an allowlisted object. This is a research and diagnostics tool, not a substitute for the typed operations, and it refuses any member that would change state. |
| `sw_api_invoke_write` | `api_invoke_write` | debug | destructive mutation, confirm | Call a state-changing SOLIDWORKS API member directly. Development only: it is gated behind SWMCP_ENABLE_LOWLEVEL_WRITE, requires confirmation, is checkpointed and audited, and its effect is not verified beyond a before and after snapshot. |
| `sw_api_search` | `api_search` | extended | read | Search the SOLIDWORKS constants registered on this machine by name, so a caller can find the enum member a low-level call needs without guessing its value. |

## document

| Operation | Method | Tier | Safety | What it does |
|---|---|---|---|---|
| `sw_doc_activate` | `doc_activate` | core | side effect | Make an open document the active one, addressed by path or title. An ambiguous title is refused rather than resolved arbitrarily. |
| `sw_doc_close` | `doc_close` | core | destructive mutation, confirm | Close an open document. The handling of unsaved changes must be stated explicitly, because closing a dirty document silently would discard work. |
| `sw_doc_list` | `doc_list` | core | read | List every open document with its type, path, saved and dirty state, active configuration, and whether it can be checkpointed. |
| `sw_doc_new` | `doc_new` | core | side effect | Create a part, assembly, or drawing from an explicit template or the SOLIDWORKS default for that type. Reports which template was actually used. |
| `sw_doc_open` | `doc_open` | core | side effect | Open a SOLIDWORKS document from disk, decoding the load errors and warnings into names and remediation rather than returning raw status integers. |
| `sw_doc_rebuild` | `doc_rebuild` | core | mutation | Rebuild the document and report which features ended up in error or warning, so a rebuild that 'succeeded' with a broken tree is not mistaken for success. |
| `sw_doc_save` | `doc_save` | core | side effect | Save a document in place or to a new path, applying the overwrite policy so an existing deliverable is never replaced silently, and verifying the file on disk. |
| `sw_doc_undo` | `doc_undo` | extended | destructive mutation, confirm | Undo the last operations in SOLIDWORKS. Native undo is opportunistic and does not report what it reverted, so checkpoints remain the reliable way back. |

## selection

| Operation | Method | Tier | Safety | What it does |
|---|---|---|---|---|
| `sw_selection_get` | `selection_get` | core | read | Report what is currently selected in SOLIDWORKS, capturing a full reference for each item so the user can point at geometry instead of naming it. |
| `sw_selection_set` | `selection_set` | core | side effect | Set or clear the SOLIDWORKS selection from entity references or typed names. An empty reference list with clear_first simply clears the selection. |

## reference

| Operation | Method | Tier | Safety | What it does |
|---|---|---|---|---|
| `sw_probe_faces` | `probe_faces` | core | read | Find faces or edges by their geometry — type, radius, area, normal direction, or a point they contain — and return ranked references. This is how to narrow an ambiguous reference down to exactly one entity before acting on it. |
| `sw_probe_ray` | `probe_ray` | extended | read | Cast a ray into the model and capture a reference to the first face it hits. Useful when a face is easier to describe by where it is than by what it is. |
| `sw_ref_capture` | `ref_capture` | core | read | Capture durable references to the selected entities, emitting the persistent reference, a semantic geometry fallback, and paste-ready arguments together. |
| `sw_ref_resolve` | `ref_resolve` | core | read | Resolve a stored entity reference against the current model. Reports whether it resolved exactly or was healed by geometry matching, and returns every candidate rather than guessing when the match is ambiguous. |

## sketch

| Operation | Method | Tier | Safety | What it does |
|---|---|---|---|---|
| `sw_sketch_add_geometry` | `sketch_add_geometry` | core | mutation | Create sketch primitives in one batch — lines, centerlines, points, rectangles, circles, arcs, ellipses, polygons, slots, and splines. Each created segment comes back with a stable id for use in relations, dimensions, and deletes. |
| `sw_sketch_convert_entities` | `sketch_convert_entities` | extended | mutation | Project existing edges or faces into the active sketch, returning stable ids for the segments that were created. |
| `sw_sketch_create` | `sketch_create` | core | mutation | Open a sketch on a plane, draw a profile into it, and close it - the whole cadence in one call, reporting where every point landed and whether the profile closes. |
| `sw_sketch_delete` | `sketch_delete` | extended | destructive mutation, confirm | Delete sketch segments by their stable ids, reporting which ones were removed. |
| `sw_sketch_derive` | `sketch_derive` | extended | mutation | Copy an existing sketch onto another plane, optionally scaled, rotated, mirrored or moved, without re-transmitting its geometry. |
| `sw_sketch_exit` | `sketch_exit` | core | mutation | Close the sketch currently open for editing and optionally rebuild the model. |
| `sw_sketch_list` | `sketch_list` | core | read | List the document's sketches with their solver state, segment counts, and which one is currently open for editing. |
| `sw_sketch_modify` | `sketch_modify` | extended | destructive mutation, confirm | Move, rotate, scale, mirror, offset, or trim sketch geometry, reporting how many segments the operation affected and the resulting solver state. |
| `sw_sketch_set_construction` | `sketch_set_construction` | extended | mutation | Toggle segments between construction geometry and profile geometry. |
| `sw_sketch_start` | `sketch_start` | core | mutation | Open a new sketch on a standard plane, a named plane, or a planar face. Standard planes resolve by tree position, so a non-English SOLIDWORKS works. |
| `sw_sketch_text` | `sketch_text` | core | mutation | Draw sketch text, optionally running along a sketch segment, so engraving and embossing do not need a macro. Verified by counting the text back out. |

## constraint

| Operation | Method | Tier | Safety | What it does |
|---|---|---|---|---|
| `sw_dimension_list` | `dimension_list` | core | read | List driving dimensions with their names and values in the requested unit, optionally as they stand in one configuration, so a parametric change can address a dimension by name rather than by position. |
| `sw_dimension_set` | `dimension_set` | core | mutation | Change a named driving dimension in the active configuration, in all of them, or in named ones, reporting the value before and after plus any rebuild errors the change caused. |
| `sw_sketch_add_dimensions` | `sketch_add_dimensions` | core | mutation | Add driving dimensions to sketch segments in one batch and optionally set their values. Always returns the resulting solver state, so reaching fully defined is verifiable rather than assumed. |
| `sw_sketch_add_relations` | `sketch_add_relations` | core | mutation | Add geometric relations to sketch segments in one batch. Reports each relation individually and always returns the resulting solver state, so an over-defined sketch is visible immediately rather than at the next rebuild. |
| `sw_sketch_auto_dimension` | `sketch_auto_dimension` | advanced | destructive mutation, confirm | Fully define a sketch automatically under an explicit policy, reporting every dimension it created. The policy has no default because auto-dimensioning adds constraints the caller did not choose. |
| `sw_sketch_diagnose` | `sketch_diagnose` | core | read | Report a sketch's solver state and its profile topology: fully or under defined, over-defining relations, dangling relations, how many segments are still free, and how many closed contours the sketch actually holds — with the coordinates of any gap that stops one closing. |

## datum

| Operation | Method | Tier | Safety | What it does |
|---|---|---|---|---|
| `sw_datum_axis_create` | `datum_axis_create` | core | mutation | Create a reference axis from one line, two planes, two points, a cylindrical face, or a point and a plane, and read back the axis that was actually made. |
| `sw_datum_csys_create` | `datum_csys_create` | core | mutation | Create a coordinate system from an origin and axis references, and return the transform SOLIDWORKS actually built: rotation, origin position, and scale. |
| `sw_datum_list` | `datum_list` | core | read | List the document's reference geometry — planes, axes, points, and coordinate systems — with their locale-invariant type tokens and capture-ready references. |
| `sw_datum_plane_create` | `datum_plane_create` | core | mutation | Create a reference plane by offset, angle, midplane, three points, or tangency, and read back the plane that was actually created. |
| `sw_datum_point_create` | `datum_point_create` | core | mutation | Create reference points at a face centre, an edge centre, an intersection, a projected vertex, a sketch point, or spaced along a curve by distance, percentage, or even division. |

## feature

| Operation | Method | Tier | Safety | What it does |
|---|---|---|---|---|
| `sw_body_primitive` | `body_primitive` | core | mutation | Build a box, cylinder, sphere, cone, frustum, torus, wedge, or prism as an ordinary sketch and boss, and check the measured volume against the closed-form volume its dimensions imply. |
| `sw_feature_chamfer` | `feature_chamfer` | core | mutation | Bevel edges or faces with an equal-distance or angle-distance chamfer, using stable entity references. |
| `sw_feature_delete` | `feature_delete` | extended | destructive mutation, confirm | Delete a feature, optionally with its dependents, and verify it is gone from the tree. |
| `sw_feature_draft` | `feature_draft` | core | mutation | Taper faces by a draft angle from a neutral plane, a parting line, or as a step draft, verified by measuring the material the taper added or removed. |
| `sw_feature_edit` | `feature_edit` | extended | mutation | Rename a feature or change its suppression state, verified by reading it back. |
| `sw_feature_extrude_boss` | `feature_extrude_boss` | core | mutation | Create a boss or base extrude from a sketch profile, with blind, through-all, up-to, or mid-plane end conditions, draft, and merge control. Verifies the body count and volume actually changed. |
| `sw_feature_extrude_cut` | `feature_extrude_cut` | core | mutation | Cut material with an extruded sketch profile, with the same end conditions as a boss extrude. Verifies that volume actually decreased. |
| `sw_feature_fillet` | `feature_fillet` | core | mutation | Round edges or faces with a constant-radius fillet, addressing them through stable entity references rather than whatever happens to be selected. |
| `sw_feature_hole` | `feature_hole` | core | mutation | Place a hole on a face. Reports which strategy was actually used, and never silently downgrades a tapped or counterbored hole to a plain cut when Hole Wizard is unavailable. Counts the resulting cylindrical faces as evidence. |
| `sw_feature_list` | `feature_list` | core | read | List the feature tree in order, with each feature's locale-invariant type token, suppression state, and decoded error, if any. |
| `sw_feature_loft` | `feature_loft` | core | mutation | Loft between two or more closed profiles in the order given, with optional guide curves, a centerline, a closed loop, and start/end tangency. |
| `sw_feature_pattern` | `feature_pattern` | core | mutation | Repeat features in a linear or circular pattern. Other pattern families are rejected by the schema rather than failing at runtime, so the tool never advertises coverage it does not have. |
| `sw_feature_revolve` | `feature_revolve` | core | mutation | Revolve a sketch profile about an axis to add or remove material. Boss and cut share one tool because their option sets are identical. |
| `sw_feature_rib` | `feature_rib` | extended | mutation | Thicken an open sketch into a rib against the existing solid, reporting the material it added so a rib that missed the body is visible immediately. |
| `sw_feature_shell` | `feature_shell` | core | mutation | Hollow a solid to a wall thickness, optionally opening it by removing named faces, and verify that material was actually removed. |
| `sw_feature_sweep` | `feature_sweep` | core | mutation | Sweep a closed profile along a path, with optional guide curves, profile orientation, twist, and thin-wall options, verified by measuring the result. |
| `sw_surface_create` | `surface_create` | core | mutation | Create a surface body by filling a closed sketch, offsetting faces, extending surface edges, or knitting touching surfaces, verified by counting sheet bodies. |

## body

| Operation | Method | Tier | Safety | What it does |
|---|---|---|---|---|
| `sw_body_list` | `body_list` | core | read | List the solid and surface bodies with their owning features, material, visibility, face and edge counts, and mass properties. |

## measure

| Operation | Method | Tier | Safety | What it does |
|---|---|---|---|---|
| `sw_measure` | `measure` | core | read | Measure the model, a body, a feature, or a single face: bounding box, volume, surface area, mass, centre of mass, topology counts, and rebuild validity. |

## assembly

| Operation | Method | Tier | Safety | What it does |
|---|---|---|---|---|
| `sw_asm_component_set` | `asm_component_set` | core | mutation | Change one component's suppression, fixed state, visibility, or referenced configuration, reading each back rather than trusting the call. |
| `sw_asm_insert` | `asm_insert` | core | mutation | Insert a part or subassembly into the open assembly at a position, with an optional configuration and fixed state, verified by finding it in the tree. |
| `sw_asm_tree` | `asm_tree` | core | read | List the assembly's components with path, configuration, quantity, suppression, lightweight, hidden, fixed, envelope, virtual, and broken-reference state. |
| `sw_interference_check` | `interference_check` | core | read | Find where components overlap, reporting each interference's volume and the components involved rather than a pass/fail verdict. |
| `sw_mate_add` | `mate_add` | core | mutation | Mate two entities with a coincident, concentric, parallel, perpendicular, tangent, distance, angle, or lock mate, verified by reading the mate back. |
| `sw_mate_delete` | `mate_delete` | extended | destructive mutation, confirm | Delete one mate and verify it is gone from the mate list. Removing a mate can let components move, so it requires confirmation. |
| `sw_mate_dof` | `mate_dof` | core | read | Report how constrained each component is and which mates hold it, so an under-constrained component is named rather than discovered when it moves. |
| `sw_mate_edit` | `mate_edit` | extended | mutation | Rename a mate or change its suppression, verified by reading the mate list back rather than trusting the call. |
| `sw_mate_list` | `mate_list` | core | read | List the assembly's mates with type, alignment, flip, suppression, the components they join, and any limit range or driving value. |
| `sw_mate_probe` | `mate_probe` | core | read | List the entities in an assembly that could take a given mate, or judge one pair before creating it. The verdict is a prediction from geometry, not a SOLIDWORKS ruling. |

## drawing

| Operation | Method | Tier | Safety | What it does |
|---|---|---|---|---|
| `sw_drawing_annotate_model` | `drawing_annotate_model` | core | mutation | Import model dimensions and annotations into the drawing's views, reporting each one that arrived rather than assuming the import found anything. |
| `sw_drawing_export` | `drawing_export` | core | side effect | Export a drawing, or chosen sheets of it, to PDF, DXF, or DWG, verifying the written file against the format's own signature and reporting what was on the drawing when it was written. |
| `sw_drawing_list` | `drawing_list` | core | read | List a drawing's sheets and views with size, scale, projection, and each view's type, position, outline, referenced model, and configuration. |
| `sw_drawing_new` | `drawing_new` | core | side effect | Create a drawing with an explicit template, sheet size, scale, and projection standard, reading the sheet back so a degenerate one is caught at creation. |
| `sw_drawing_note_add` | `drawing_note_add` | core | mutation | Add a general note or a centre mark to the active sheet, verified by finding the annotation on the sheet afterwards with its type and position. |
| `sw_drawing_review` | `drawing_review` | core | read | Count and locate a drawing's views, dimensions, notes, tables, and dangling annotations against caller-supplied minimums. Never a substitute for a person reading the drawing. |
| `sw_drawing_sheet_add` | `drawing_sheet_add` | core | mutation | Add a sheet with its own size, scale, and projection standard, measured back so a sheet of zero area is refused rather than left to hang the next view. |
| `sw_drawing_table_add` | `drawing_table_add` | core | mutation | Insert a bill of materials on the active sheet and read every cell back, so the table's contents are the evidence rather than the call having returned. |
| `sw_drawing_view_add` | `drawing_view_add` | core | mutation | Place a model view or a standard three-view arrangement on the active sheet, verified by reading each created view's position, scale, and referenced model. |

## exchange

| Operation | Method | Tier | Safety | What it does |
|---|---|---|---|---|
| `sw_batch_export` | `batch_export` | core | side effect | Export many documents, configurations, sheets, and formats in one call, writing a JSON manifest that names every file with its size, timestamp, and SHA-256, and reporting each requested output as written, failed, or skipped. |
| `sw_bom_export` | `bom_export` | core | side effect | Write a component and property bill of materials to CSV, with a traceability matrix naming every instance behind each quantity and whether each property value came from the configuration or the file. Labelled a precursor, always. |
| `sw_export` | `export` | core | side effect | Export the model to a neutral format with explicit tessellation, unit, and protocol settings, then verify the written file against that format's own signature rather than trusting that SaveAs returned. |
| `sw_import` | `import_` | core | side effect | Import a STEP, IGES, Parasolid, ACIS, or STL file into a new document, then report the geometry that actually arrived — body counts, volume, and topology — rather than trusting that LoadFile4 returned. |

## material

| Operation | Method | Tier | Safety | What it does |
|---|---|---|---|---|
| `sw_material_get` | `material_get` | core | read | Read the part's material, the density SOLIDWORKS is actually using, and the mass that follows from it, plus any per-body material overrides. |
| `sw_material_set` | `material_set` | core | mutation | Assign a material to the part and prove it took by reading the material back and reporting the density and mass it now has. |

## parameter

| Operation | Method | Tier | Safety | What it does |
|---|---|---|---|---|
| `sw_config_activate` | `config_activate` | core | mutation | Switch the active configuration and read back which one is active afterwards, since a mis-typed name leaves the previous configuration in place. |
| `sw_config_create` | `config_create` | core | mutation | Create a configuration, optionally derived from an existing one, and read the configuration list back to confirm it exists. |
| `sw_config_delete` | `config_delete` | extended | destructive mutation, confirm | Delete a configuration. Destructive: the configuration's own dimension values and property overrides go with it, so it requires confirmation. |
| `sw_config_list` | `config_list` | core | read | List the document's configurations with their parent, derived state, rebuild state, and which one is active, so a variant can be addressed by name. |
| `sw_equation_list` | `equation_list` | core | read | List equations and global variables with their values, what each one reads, and any circular chain, so a parametric change can be planned before it is made. |
| `sw_equation_set` | `equation_set` | core | mutation | Add, update, or delete equations and global variables as a batch, reporting each item's outcome and the solver status the change left behind. |
| `sw_parameter_table_export` | `parameter_table_export` | extended | side effect | Write every driving dimension, equation, and custom property to a CSV that the import tool reads back, so a design's parameters can be reviewed or edited outside SOLIDWORKS. |
| `sw_parameter_table_import` | `parameter_table_import` | extended | mutation | Apply dimension values from a CSV written by the export tool, reporting every row's before and after value and leaving unchanged rows alone. |
| `sw_property_list` | `property_list` | core | read | List custom properties at file level or per configuration, reporting both the raw definition and the evaluated value a drawing or BOM would print. |
| `sw_property_set` | `property_set` | core | mutation | Write or delete custom properties at file level or in one configuration, and read every one of them back to confirm the value that was actually stored. |

## review

| Operation | Method | Tier | Safety | What it does |
|---|---|---|---|---|
| `sw_review_holes` | `review_holes` | core | read | Audit holes by their B-Rep geometry — cylindrical faces grouped by diameter, with axis and position — and compare them against expected counts. |
| `sw_review_inspect` | `review_inspect` | core | read | Gather the document's feature tree, sketches, bodies, configurations, mass, and metadata into one payload, so a review is one call rather than eight. |
| `sw_review_report` | `review_report` | core | side effect | Run a policy review and write it as both machine-readable JSON and a human-readable Markdown table, each finding attributed to what it read. |
| `sw_review_validate` | `review_validate` | core | read | Judge the document against caller-supplied rules and return pass, warn, or block findings, each naming what was read to reach it. |

## view

| Operation | Method | Tier | Safety | What it does |
|---|---|---|---|---|
| `sw_appearance_get` | `appearance_get` | core | read | Read the colour, transparency, and shading of the document, a body, a feature, or a face, reporting whether the value is its own or inherited. |
| `sw_appearance_set` | `appearance_set` | core | side effect | Set the colour, transparency, and shading of the document, a body, a feature, or a face, changing only the values given and reading the result back. |
| `sw_view_capture` | `view_capture` | core | side effect | Save a PNG or BMP of the model at a requested size, after clearing the selection and fitting the view, and report the pixel size read back out of the written file. |
| `sw_view_set` | `view_set` | extended | side effect | Orient the viewport to a standard view, set the display mode, and zoom to fit, so a later capture shows the model rather than whatever was last on screen. |
| `sw_visibility_set` | `visibility_set` | core | side effect | Hide or show a solid body, or blank a reference plane, axis, point, or sketch, verified by reading the visibility back rather than trusting the call. |
