# Source-audited project inventories

This document records the exact, current MCP surface of each project. It also
calls out useful library/skill operations that are implemented but are not
registered as dedicated MCP tools.

## 1. FreeCAD Robust MCP Server (`FC`)

### Scope and source

- Registration entry point: `freecad-addon-robust-mcp-server/src/freecad_mcp/tools/__init__.py`
- Tool implementations: `freecad-addon-robust-mcp-server/src/freecad_mcp/tools/*.py`
- Current source count: **152 MCP tools**
- Documentation note: `docs/MCP_TOOLS_REFERENCE.md` reports 85 tools and is
  stale relative to current source.

The server can run through embedded, socket, or XML-RPC bridges. Its generic
`execute_python` tool makes most FreeCAD Python APIs reachable, but the list
below contains only dedicated MCP contracts.

### Exact tool inventory

**Documents (7):**

`list_documents`, `get_active_document`, `create_document`, `open_document`,
`save_document`, `close_document`, `recompute_document`.

**Execution and environment (5):**

`execute_python`, `get_freecad_version`, `get_connection_status`,
`get_console_output`, `get_mcp_server_environment`.

**General objects, Part geometry, and selection (40):**

`list_objects`, `inspect_object`, `create_object`, `create_box`,
`create_cylinder`, `create_sphere`, `create_cone`, `create_torus`,
`create_wedge`, `create_helix`, `edit_object`, `delete_object`,
`boolean_operation`, `set_placement`, `scale_object`, `rotate_object`,
`copy_object`, `mirror_object`, `get_selection`, `set_selection`,
`clear_selection`, `create_line`, `create_plane`, `create_ellipse`,
`create_prism`, `create_regular_polygon`, `shell_object`, `offset_3d`,
`slice_shape`, `section_shape`, `make_compound`, `explode_compound`,
`fuse_all`, `common_all`, `make_wire`, `make_face`, `extrude_shape`,
`revolve_shape`, `part_loft`, `part_sweep`.

`boolean_operation` covers fuse/union, cut/subtract, and common/intersection.
The separate multi-object operations are `fuse_all` and `common_all`.

**Part Design and Sketcher (49):**

`create_partdesign_body`, `create_sketch`, `add_sketch_rectangle`,
`add_sketch_circle`, `pad_sketch`, `pocket_sketch`, `fillet_edges`,
`chamfer_edges`, `revolution_sketch`, `groove_sketch`, `create_hole`,
`linear_pattern`, `polar_pattern`, `mirrored_feature`, `add_sketch_line`,
`add_sketch_arc`, `add_sketch_point`, `loft_sketches`, `sweep_sketch`,
`create_datum_plane`, `create_datum_line`, `create_datum_point`,
`draft_feature`, `thickness_feature`, `subtractive_loft`,
`subtractive_pipe`, `add_sketch_ellipse`, `add_sketch_polygon`,
`add_sketch_slot`, `add_sketch_bspline`, `add_sketch_constraint`,
`constrain_horizontal`, `constrain_vertical`, `constrain_coincident`,
`constrain_parallel`, `constrain_perpendicular`, `constrain_tangent`,
`constrain_equal`, `constrain_distance`, `constrain_distance_x`,
`constrain_distance_y`, `constrain_radius`, `constrain_angle`,
`constrain_fix`, `add_external_geometry`, `delete_sketch_geometry`,
`delete_sketch_constraint`, `get_sketch_info`, `toggle_construction`.

The generic constraint tool is supplemented by typed convenience tools. The
feature set includes additive and subtractive extrude, revolve, loft, and sweep,
plus hole, fillet, chamfer, draft, thickness, datum, pattern, and mirror features.

**Import/export (7):**

`export_step`, `export_stl`, `export_3mf`, `export_obj`, `export_iges`,
`import_step`, `import_stl`.

**View, UI, history, and parts library (18):**

`get_screenshot`, `set_view_angle`, `list_workbenches`,
`activate_workbench`, `fit_all`, `set_object_visibility`, `set_display_mode`,
`set_object_color`, `zoom_in`, `zoom_out`, `set_camera_position`, `undo`,
`redo`, `get_undo_redo_status`, `list_parts_library`,
`insert_part_from_library`, `get_console_log`, `recompute`.

**Macros (6):**

`list_macros`, `run_macro`, `create_macro`, `read_macro`, `delete_macro`,
`create_macro_from_template`.

**Spreadsheet and parametric binding (10):**

`spreadsheet_create`, `spreadsheet_set_cell`, `spreadsheet_get_cell`,
`spreadsheet_set_alias`, `spreadsheet_get_aliases`, `spreadsheet_clear_cell`,
`spreadsheet_bind_property`, `spreadsheet_get_cell_range`,
`spreadsheet_import_csv`, `spreadsheet_export_csv`.

**Validation and guarded execution (4):**

`validate_object`, `validate_document`, `undo_if_invalid`, `safe_execute`.

**Draft text (6):**

`draft_shapestring`, `draft_list_fonts`, `draft_shapestring_to_sketch`,
`draft_shapestring_to_face`, `draft_text_on_surface`,
`draft_extrude_shapestring`.

### SolidWorks-relevant lessons

The most important transferable capabilities are the typed sketch constraints,
datum creation, feature-level loft/sweep/revolve/draft/thickness operations,
multi-body booleans, topology inspection, text/engraving workflow,
spreadsheet-to-property binding, validation with automatic rollback, view
control, selection, undo/redo, and macro lifecycle. Their SolidWorks equivalents
are mapped in the target requirements document.

## 2. SolidWorks Automation Skill (`SKILL`)

### Scope and source

- MCP implementation: `solidworks-automation-skill/mcp-server/server.py`
- Skill entry point: `solidworks-automation-skill/SKILL.md`
- Capability registry: `solidworks-automation-skill/capabilities.yaml`
- Python operations: `solidworks-automation-skill/scripts/*.py`
- Subskills: `solidworks-automation-skill/subskills/*`
- Current source count: **40 MCP tools**

This is much larger than its MCP surface. It combines a skill, Python library,
headless geometry/review services, drawing subskill, automation workbench, and
MCP wrapper. The sections below deliberately separate direct MCP tools from
library/skill operations.

### Exact MCP inventory

**CAD-free/open engineering services (12):**

| Tool | Operation |
|---|---|
| `cadstudio_write_open_format` | Write `.cadstudio.json`, STEP, IGES, BREP, STL, OBJ, GLB, DXF, SVG, PDF, and PNG without SolidWorks/AutoCAD. |
| `cadstudio_build_dxf_preview_scene` | Convert an existing DXF to a safe PreviewScene JSON. |
| `cadstudio_check_dfm` | DFM risk checks for machining, sheet metal, laser cutting, and 3D printing. |
| `cadstudio_check_routing` | Review neutral routing topology, bend radii, clearance, supports, and BOM. |
| `cadstudio_routing_preflight` | Probe Routing type library, add-in registration, and license evidence. |
| `cadstudio_fea_preflight` | Discover approved CalculiX/Elmer solvers. |
| `cadstudio_prepare_fea` | Generate a versioned CalculiX input deck from a structured request. |
| `cadstudio_run_fea` | Run a structured request through an approved local solver. |
| `cadstudio_run_fea_convergence` | Run 3–8 meshes and compare displacement/stress convergence. |
| `cadstudio_review_advanced_geometry` | Validate advanced surface/mold plans and produce pilot/blocked evidence. |
| `cadstudio_create_ocp_loft` | Create and reopen a parameterized OCCT loft. |
| `cadstudio_create_ocp_surface` | Create whitelisted smooth loft, sweep, knit, or thicken geometry. |

**SolidWorks session and documents (9):**

`solidworks_connect`, `solidworks_health_check`, `solidworks_new_document`,
`solidworks_create_basic_part`, `solidworks_open_document`,
`solidworks_add_component`, `solidworks_set_component_fixed`,
`solidworks_save_document`, `solidworks_close_documents`.

`solidworks_new_document` supports part, assembly, and drawing documents.
`solidworks_create_basic_part` is limited to a box or cylinder.

**Assembly mates (3):**

`solidworks_add_coincident_mate`, `solidworks_add_distance_mate`,
`solidworks_add_concentric_mate`.

**Appearance, model data, export, and delivery (8):**

`solidworks_set_appearance`, `solidworks_export_active`,
`solidworks_update_dimension`, `solidworks_set_custom_properties`,
`solidworks_batch_export_files`, `solidworks_export_assembly_bom`,
`solidworks_pack_and_go`, `solidworks_review_active`.

The export tool supports STEP, STL, IGES, Parasolid, PDF, and DXF.

**Drawings (3):**

`solidworks_generate_drawing`, `solidworks_review_drawing`,
`solidworks_inspect_drawing`.

**Holes and slots (2):**

`solidworks_create_hole_feature`, `solidworks_inspect_hole_features`.

The create tool supports blind, through, counterbore, countersink, and
semicircular-slot workflows; the inspector reads B-Rep segments and optional
position-acceptance evidence.

**Motion Study (3):**

`solidworks_add_rotary_motor`, `solidworks_inspect_motion_studies`,
`solidworks_validate_motion_study`.

### Implemented library/skill operations without dedicated MCP tools

These are real Python functions or routed subskill workflows, but consumers must
use the skill/library entry point or add wrappers.

**Sketch and part modeling (`scripts/sw_part.py`):**

`start_sketch`, `end_sketch`, `sketch`, `current_sketch_name`, `sketch_line`,
`sketch_rectangle`, `sketch_corner_rectangle`, `sketch_circle`, `sketch_arc`,
`sketch_polygon`, `sketch_slot`, `sketch_spline`, `auto_dimension_sketch`,
`add_dimension`, `add_sketch_relation`, `extrude_boss`, `extrude_cut`,
`extrude_midplane`, `revolve_boss`, `fillet`, `chamfer`, `linear_pattern`,
`circular_pattern`, `shell`, `mirror_feature`, `hole_wizard`, `rib`.

**Hole helpers (`scripts/sw_hole_features.py`):**

`create_blind_hole`, `create_through_hole`, `create_counterbore_hole`,
`create_countersink_hole`, `create_semicircular_slot`, `create_hole_pattern`.

**Assembly (`scripts/sw_assembly.py`):**

Component add/resolve/model/feature/entity lookup; feature-entity selection;
checked `AddMate5`; concentric, coincident, distance, parallel, gear, and revolute
mates; component transforms; component list/search; suppress/unsuppress/replace;
mate summaries; and interference detection.

**Motion (`scripts/sw_motion.py`):**

Motion add-in/type-library discovery; study-manager lookup; study creation;
constant-speed rotary motors by direct entity or cylinders; calculate/play;
study summary; and result validation/freshness checks.

**Appearance (`scripts/sw_appearance.py`):**

Document, feature, and component appearance; palette application; named
appearances; material-property retrieval; and read-back verification.

**Export/data/delivery:**

- `scripts/sw_export.py`: STEP, STL, IGES, Parasolid, PDF, DXF, flat-pattern DXF,
  batch export, and multi-format batch export.
- `scripts/sw_document_data.py`: inspect configurations, update named dimensions,
  read custom properties, and set file/configuration properties.
- `scripts/sw_delivery.py`: collect/export assembly BOM, traceability, Pack and Go
  audit matrix, and Pack and Go.
- `scripts/sw_import_mesh_reference.py`: configure mesh import and import an
  OBJ/STL reference.
- `scripts/sw_entity_reference.py`: geometry signatures and semantic-reference
  creation/resolution.

**Review (`scripts/sw_review.py`):**

Drawing/PDF/BMP inspection; standard views and zoom-to-fit; preview capture;
model summaries; coaxial-hole grouping; hole-position acceptance; geometry
measurements; structured review reports; evaluation; and Markdown summaries.

**Subskills:**

| Subskill | Checked-in status | Additional scope |
|---|---|---|
| `solidworks-vibecad` | experimental | Natural-language brief to parametric design plan and review gate. |
| `solidworks-fillet-chamfer-cnc` | stable | CNC brackets/mounts, holes, slots, pockets, and multiple finish features. |
| `solidworks-threaded-holes` | stable | M3–M12 threaded holes, tap drills, mouth chamfers, properties, STEP delivery. |
| `solidworks-engineering-drawing` | pilot | GB/T first-angle part/assembly drawings, dimensions, hole tables, BOM, PDF/BMP evidence. |
| `autocad-automation` | mixed/gated | DXF/DWG-related drafting and review; not a SolidWorks capability. |

### Capability registry status that must not be mistaken for full authoring

The registry marks configurations/design tables, sheet metal, and weldments as
`reference_only`. Native Routing authoring is blocked without add-in/license
evidence. Mold support validates a plan but does not generate core/cavity solids.
Surface and FEA functions are pilot workflows with explicit engineering-review
requirements. These remain requirements for a comprehensive future server, not
fully delivered capabilities.

## 3. SolidWorks MCP by alisam (`ALISAM`)

### Scope and source

- Registration: `Solidworks-MCP-alisam/solidworks_mcp/server.py`
- Automation: `Solidworks-MCP-alisam/solidworks_mcp/automation/*.py`
- Current source count: **25 MCP tools**
- Documentation note: the README advertises 22 tools and is stale.

### Exact MCP inventory

**Connection (2):** `connect_solidworks`, `get_solidworks_info`.

**Documents (7):** `create_new_part`, `create_new_assembly`, `open_document`,
`save_document`, `close_document`, `get_document_info`,
`list_open_documents`.

**Sketches (9):** `create_sketch`, `create_sketch_on_face`, `draw_line`,
`draw_circle`, `draw_rectangle`, `draw_arc`, `draw_polygon`, `close_sketch`,
`get_sketch_status`.

**Features (5):** `extrude_sketch`, `cut_extrude`, `fillet_edges`,
`chamfer_edges`, `list_features`.

**Utilities (2):** `set_units`, `execute_python`.

`execute_python` exposes the SolidWorks application as `sw`, the active model as
`doc`, and the automation facade as `automation`, so missing operations can be
scripted. This is broad but not typed, discoverable, or safely constrained.

### Library-only operations and roadmap caution

The automation modules also contain `create_new_drawing`, `exit_sketch`,
`draw_centerline`, and `select_edge`, none of which is a registered tool.
`DEVELOPMENT_ROADMAP.md` proposes revolve, sweep, loft, patterns, shell,
assemblies, drawings, simulation, undo/redo, screenshots, measurements, export,
and other operations. Those roadmap items are **not current capabilities** and
are used only as additional backlog evidence.

## 4. SolidWorks MCP by Jay (`JAY`)

### Scope and source

- Generated/typed catalog: `solidworks-mcp-jay/src/tool-spec/catalog.ts`
- Generated manifest: `solidworks-mcp-jay/tools/manifest.json`
- Manual registrations: `src/index.ts`, `src/tool-registry.ts`, and
  `src/tools/*.ts`
- Worker handlers: `workers/SolidWorksComWorker/Handlers/*.cs`
- Default current count: **142 MCP tools**

The default `SOLIDWORKS_MCP_TOOL_TIER=all` registers all 133 manifest tools:
18 core, 105 extended, 1 advanced, and 9 debug. A configured maximum tier can
expose fewer. The nine manual tools described later bring the default total to
142.

### Generated/manifest tool inventory (133)

**Documents, files, configuration, and safety:**

`solidworks_activate_document`, `solidworks_checkpoint_document`,
`solidworks_close_all_documents`, `solidworks_close_document`,
`solidworks_confirm_and_save`, `solidworks_diagnose_document`,
`solidworks_diagnose_part_save`, `solidworks_get_open_documents`,
`solidworks_inspect_document`, `solidworks_list_checkpoints`,
`solidworks_new_document`, `solidworks_open`, `solidworks_pack_and_go`,
`solidworks_rebuild_document`, `solidworks_restore_from_checkpoint`,
`solidworks_save_document`, `solidworks_add_configuration_copy`,
`solidworks_list_configurations`, `solidworks_list_display_states`,
`solidworks_set_custom_properties`, `solidworks_get_equations`,
`solidworks_list_dimensions`, `solidworks_set_dimension`.

**Sketch, selection, and reference geometry:**

`solidworks_create_sketch`, `solidworks_list_sketches`,
`solidworks_sketch_line`, `solidworks_sketch_rectangle`,
`solidworks_sketch_circle`, `solidworks_sketch_exit`,
`solidworks_set_sketch_circle_diameter`, `solidworks_get_selection`,
`solidworks_resolve_selection`, `solidworks_diagnose_selection`,
`solidworks_select_face_by_ray`, `solidworks_get_planar_face_index`,
`solidworks_get_persist_reference`, `solidworks_select_by_persist_reference`,
`solidworks_list_reference_geometry`, `solidworks_ensure_offset_plane`,
`solidworks_insert_coord_sys`.

**Part features, bodies, material, and geometry:**

`solidworks_demo_build_part`, `solidworks_feature_extrude_boss`,
`solidworks_feature_extrude_cut`, `solidworks_feature_fillet`,
`solidworks_feature_chamfer`, `solidworks_feature_linear_pattern`,
`solidworks_feature_circular_pattern`, `solidworks_feature_mirror`,
`solidworks_delete_feature`, `solidworks_rename_feature`,
`solidworks_set_feature_suppression`, `solidworks_list_features`,
`solidworks_list_bodies`, `solidworks_combine_bodies`,
`solidworks_clone_solid_body_part`, `solidworks_mirror_part_file`,
`solidworks_round_side_arms_from_circle`, `solidworks_get_part_feature_box`,
`solidworks_get_mass_properties`, `solidworks_get_material`,
`solidworks_set_material`, `solidworks_set_mass_override`.

**Measurements and geometry probes:**

`solidworks_measure`, `solidworks_measure_distance`,
`solidworks_get_component_box`, `solidworks_get_feature_box`,
`solidworks_component_mass_properties`, `solidworks_probe_feature_faces`,
`solidworks_probe_part_feature_geometry`.

**Assembly components and diagnostics:**

`solidworks_insert_component`, `solidworks_list_components`, `solidworks_list_bom`,
`solidworks_get_component_references`, `solidworks_get_component_transform`,
`solidworks_set_component_transform`, `solidworks_reset_component_transform`,
`solidworks_transform_component`, `solidworks_align_component_to_feature`,
`solidworks_set_component_fixed`, `solidworks_unfix_all_components`,
`solidworks_set_component_visible`, `solidworks_set_component_configuration`,
`solidworks_rename_component`, `solidworks_replace_component_path`,
`solidworks_replace_components_by_path`, `solidworks_make_component_independent`,
`solidworks_dissolve_component`, `solidworks_create_subassembly`,
`solidworks_copy_with_mates`, `solidworks_mirror_component`,
`solidworks_resolve_lightweight`, `solidworks_list_broken_references`,
`solidworks_list_interferences`, `solidworks_assembly_diagnostics`,
`solidworks_get_assembly_degrees_of_freedom`,
`solidworks_export_link_transforms`, `solidworks_explode_view`.

**Mates:**

`solidworks_list_mates`, `solidworks_list_mate_entities`,
`solidworks_debug_mate_entities`, `solidworks_mate_coincident`,
`solidworks_mate_distance`, `solidworks_mate_parallel`,
`solidworks_mate_perpendicular`, `solidworks_mate_tangent`,
`solidworks_mate_width`, `solidworks_mate_limit_angle`,
`solidworks_get_mate_limit_angle`, `solidworks_set_mate_limit_angle`,
`solidworks_mate_planes`, `solidworks_mate_component_origin`,
`solidworks_mate_coord_sys`, `solidworks_mate_record_macro`,
`solidworks_mate_replay_sequence`, `solidworks_mate_probe`,
`solidworks_mate_try_coincident`, `solidworks_mate_try_distance`,
`solidworks_mate_try_parallel`, `solidworks_mate_try_perpendicular`,
`solidworks_mate_try_width`, `solidworks_delete_mate`,
`solidworks_delete_all_mates`, `solidworks_delete_mates_in_range`,
`solidworks_set_mate_suppression`, `solidworks_probe_angle_travel`.

Material get/set is tagged for both part/component and mate/assembly domains in
the manifest but is listed once above.

**Drawings and export/import:**

`solidworks_create_drawing_from_model`, `solidworks_add_standard_views`,
`solidworks_list_sheet_views`, `solidworks_export`, `solidworks_import_step`.

`solidworks_export` supports STEP, STL, PDF, and PNG under allowed roots.

**Diagnostics and error support:**

`solidworks_diagnose_com`, `solidworks_explain_error`.

**URDF package worker tool:**

`solidworks_export_urdf_package`.

### Manually registered MCP tools (9)

| Tool | Purpose |
|---|---|
| `solidworks_search_tools` | Search the active tier by tool name, tag, domain, or description. |
| `solidworks_search_api_docs` | Search the local SolidWorks API reference index. |
| `solidworks_invoke` | Invoke one allowlisted API member; writes require a separate environment gate. |
| `solidworks_batch_invoke` | Run up to 50 allowlisted calls in one worker session. |
| `solidworks_urdf_readiness` | Inspect assembly reference geometry and mate names needed for URDF. |
| `solidworks_add_urdf_frame` | Add a named part coordinate system for a URDF link. |
| `solidworks_generate_urdf` | Generate URDF from an exported CAD package without calling SolidWorks. |
| `solidworks_audit_log_recent` | Read recent write-tool audit entries. |
| `solidworks_status` | Report COM attach, version, active document, MCP version, and docs-version warning. |

### Safety and implementation notes

The 133 manifest tools classify 50 as read-only and 83 as mutating. Thirty-six
are marked destructive and confirmation-required. Paths are constrained to
allowed roots, destructive tools require `confirm: true`, many mutations create
checkpoints, and non-read operations are audited. Persist references and probing
tools reduce reliance on unstable face/edge indexes.

The manifest descriptions for some extended tools are mechanically derived and
terse. Their presence proves registration and a worker command path, not the same
level of validation as a core tool or a real-machine regression.
