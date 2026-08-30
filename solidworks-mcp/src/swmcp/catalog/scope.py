"""What this release claims to cover, and what proves each claim.

Coverage is checked rather than asserted: ``tests/test_catalog_integrity.py`` fails if
an in-scope requirement has no operation and no named platform proof, and
``generated/requirements_coverage.json`` reports partial coverage honestly instead of
counting a partially-implemented requirement as done.
"""

from __future__ import annotations

# All 29 P0 requirements, plus the P1 vertical needed to model and verify a real part.
IN_SCOPE_REQUIREMENTS: frozenset[str] = frozenset(
    {
        # P0 — session and compatibility
        "SYS-001", "SYS-002", "SYS-003", "SYS-004", "SYS-005", "SYS-006", "SYS-007",
        # P0 — typed contracts and safety
        "SAFE-001", "SAFE-002", "SAFE-003", "SAFE-004", "SAFE-005",
        "SAFE-006", "SAFE-007", "SAFE-008", "SAFE-009", "SAFE-010",
        # P0 — selection and stable references
        "REF-001", "REF-002", "REF-003", "REF-004", "REF-005", "REF-006", "REF-007",
        # P0 — discovery and low-level access
        "DISC-001", "DISC-002", "DISC-003", "DISC-004", "DISC-005",
        # P1 vertical — documents
        "DOC-001", "DOC-002", "DOC-003", "DOC-004", "DOC-005", "DOC-006", "DOC-007",
        # P1 vertical — sketches
        "SK-001", "SK-002", "SK-003", "SK-004", "SK-005", "SK-006", "SK-007",
        "SK-008",
        # P1 vertical — constraints and dimensions
        "CON-001", "CON-002", "CON-003", "CON-004", "CON-005",
        # P1 vertical — reference geometry
        "DAT-001", "DAT-002", "DAT-003", "DAT-004", "DAT-005",
        # P1 vertical — parameters, configurations, and metadata
        "PAR-001", "PAR-002", "PAR-003", "PAR-004", "PAR-005", "PAR-006",
        # Pulled forward from P2: export is how the model reaches anything else, and
        # an atomic sequence is what the safety layer has been building toward.
        "IO-001", "IO-002", "IO-003", "REV-006",
        # P2 — review. Inspection, caller-owned validation policy, a B-Rep hole
        # audit, and reports in both machine and human form.
        "REV-001", "REV-002", "REV-004", "REV-005", "REV-007",
        # P2 — assemblies. The first vertical of P2: insert, inspect, and set component
        # state. Transforms (ASM-004) and the rest of ASM are not claimed yet.
        "ASM-001", "ASM-002", "ASM-003",
        # P2 — mates. Add, inspect, probe, edit, and report how constrained each
        # component is. The exotic mate types are not claimed yet.
        "MATE-001", "MATE-002", "MATE-003", "MATE-004", "MATE-005", "MATE-006",
        "MATE-007", "MATE-008",
        # P2 — drawings. Sheets, views, imported model items, notes, a bill of
        # materials, a review that counts rather than judges, and per-sheet export.
        "DRW-001", "DRW-002", "DRW-003", "DRW-004", "DRW-005", "DRW-006",
        "DRW-007", "DRW-008", "DRW-009", "DRW-010",
        # P1 vertical — appearance and view
        "VIEW-001", "VIEW-002", "VIEW-003", "VIEW-004",
        # P1 vertical — core features, bodies, measurement
        "FEAT-001", "FEAT-002", "FEAT-003", "FEAT-004", "FEAT-005",
        "FEAT-006", "FEAT-007", "FEAT-010", "FEAT-013",
        "FEAT-009", "FEAT-011", "FEAT-014",
        "FEAT-012", "FEAT-015", "FEAT-016", "FEAT-018", "FEAT-019", "FEAT-020",
    }
)

# Requirements satisfied by infrastructure rather than by any single tool. Each names
# the test that proves it, so "covered by the architecture" is never an empty claim.
PLATFORM_REQUIREMENTS: dict[str, str] = {
    "SYS-003": "tests/test_worker.py::test_all_com_calls_share_one_sta_thread",
    "SYS-004": "tests/test_worker.py::test_a_busy_read_is_retried_with_backoff",
    "SYS-006": "tests/test_units.py::test_every_supported_length_form_reaches_meters",
    "SAFE-001": "tests/test_catalog_integrity.py::test_every_args_model_is_strict",
    "SAFE-002": "tests/test_safety_projection.py::test_projection_covers_every_variant",
    "SAFE-003": "tests/test_dispatch_pipeline.py::test_destructive_requires_confirm",
    "SAFE-004": "tests/test_path_guard.py::test_output_paths_fail_closed_when_no_roots_configured",
    "SAFE-006": "tests/test_audit.py::test_entries_are_appended_never_rewritten",
    "SAFE-007": "tests/test_dispatch_pipeline.py::test_preflight_skips_mutation",
    "SAFE-010": "tests/test_catalog_integrity.py::test_mutations_return_verification",
    "DISC-001": "tests/test_dispatch_pipeline.py::test_search_tools_sees_untiered_ops",
}

# Requirements whose scope is deliberately partial in this release, with the reason.
DECLARED_PARTIAL: dict[str, str] = {
    "FEAT-007": (
        "Linear and circular patterns only. Curve-driven, sketch-driven, table-driven, "
        "fill, and variable patterns are not implemented and are rejected by the schema "
        "rather than failing at runtime."
    ),
    "IO-001": (
        "STEP, IGES, Parasolid, and ACIS arrive as solids, and STL as a graphics, "
        "surface, or solid body — each verified by measuring what the import "
        "produced rather than by trusting that LoadFile4 returned. OBJ and other mesh "
        "formats are not implemented and are rejected by the schema rather than "
        "importing as something unexpected. Import diagnostics run and are reported by "
        "what they changed, but SOLIDWORKS exposes no per-file translator log, so a "
        "file that imports incompletely is diagnosed from the geometry rather than from "
        "a translator message. Multi-body files import as one document; splitting them "
        "into separate parts is not implemented."
    ),
    "IO-003": (
        "Tessellation quality, mesh unit, binary/ASCII, and the STEP protocol are "
        "exposed, and every written file is verified against its format signature. "
        "Exporting a selected subset of bodies is not implemented; the whole document "
        "is exported."
    ),
    "FEAT-009": (
        "Shell with a single wall thickness and face removal. Multi-thickness shells "
        "and the thicken feature are not implemented."
    ),
    "FEAT-013": (
        "Straight, centre-point straight, centre-point arc, and three-point arc slots, "
        "each with centre-to-centre or overall length. A semicircular slot is an arc "
        "slot spanning 180 degrees; SOLIDWORKS has no separate type for it. Patterning "
        "a slot goes through sw_feature_pattern once the slot is cut, so it inherits "
        "that tool's linear-and-circular limitation."
    ),
    "FEAT-014": (
        "Box, cylinder, sphere, cone, frustum, torus, wedge, and prism, each built as "
        "an ordinary sketch and boss. Helix and spring are not implemented."
    ),
    "SK-008": (
        "Sketch text with alignment, path following, mirroring, width factor, and "
        "character spacing. Font is not settable: InsertSketchText takes no font and "
        "SOLIDWORKS reads it from the document's text-format preference, so exposing it "
        "would mean changing a document-wide setting as a side effect of drawing one "
        "string. Emboss and wrap are separate features and are not implemented."
    ),
    "FEAT-018": (
        "Planar fill, offset (including a zero offset to copy faces), extend, and knit "
        "surfaces. Trimming is not implemented: SOLIDWORKS exposes no InsertTrimSurface, "
        "and InsertCutSurface cuts a solid with a surface rather than trimming one "
        "surface against another. Knit only sews surfaces that touch along an edge."
    ),
    "SYS-007": (
        "Implemented structurally via locale-invariant GetTypeName2 tokens and ordinal "
        "standard-plane position. Only an English SOLIDWORKS is installed locally, so "
        "regression on a localized feature tree is outstanding."
    ),
    "PAR-004": (
        "Configuration-specific dimension values are read and written through "
        "sw_dimension_list and sw_dimension_set. Per-configuration feature suppression "
        "is not implemented; sw_feature_edit suppresses in the active configuration."
    ),
    "ASM-001": (
        "Insert a part or subassembly at a position, with a chosen configuration and "
        "optional fixed state. Placing at an arbitrary *transform* is not implemented: "
        "AddComponent5 takes only X/Y/Z, and building a MathTransform for "
        "SetTransformAndSolve2 is impossible on this build because "
        "IMathUtility::CreateTransform answers 'Member not found' through IDispatch for "
        "every argument form, raw or cast. Orientation is left to mates."
    ),
    "FEAT-005": (
        "Loft boss and cut across two or more profiles, with guide curves, a "
        "centerline, the closed-loop option, start/end tangency, and thin-wall "
        "thickness. The boundary feature is a different API (InsertNetBlend) and is "
        "not implemented."
    ),
    "FEAT-020": (
        "Part-level material assignment and read-back, with the density and mass it "
        "produces. Per-body and per-component materials are not implemented, and mass "
        "override is not: IMassProperty on this build does not expose "
        "SetOverrideMassValue or OverrideMass through late binding, so a tool for it "
        "would have nothing to call."
    ),
    "MATE-001": (
        "Coincident, concentric, perpendicular, parallel, tangent, distance, angle, and "
        "lock mates — the types AddMate5 builds from exactly two selected entities. "
        "Width, symmetric, gear, rack-and-pinion, screw, universal joint, slot, cam, "
        "hinge, linear coupler, path, and coordinate-system mates need three or more "
        "selections or extra arguments and are rejected by the schema rather than "
        "failing at runtime."
    ),
    "MATE-002": (
        "Limit-distance and limit-angle mates are created with min and max, and "
        "sw_mate_list reports the range and the current value. Updating the limits of "
        "an existing mate is not implemented; the mate has to be recreated."
    ),
    "MATE-003": (
        "Faces, edges, vertices, planes, and axes are addressed through the same "
        "structured references as everywhere else. Component coordinate systems as mate "
        "references are untested and are not claimed."
    ),
    "DRW-004": (
        "Model dimensions and annotations are imported into the drawing's views, and "
        "every item that arrived is reported by walking the views before and after - "
        "InsertModelAnnotations3 returns nothing when it finds nothing, which is not the "
        "same as failing, so 'imported nothing' is reported as exactly that. Creating "
        "drawing dimensions directly, and setting tolerance, precision, arrow style, or "
        "text formatting on them, are not implemented."
    ),
    "DRW-005": (
        "General notes with placement, and centre marks on selected circular edges. "
        "Hole callouts, datum symbols, GD&T, surface-finish, weld, balloon, and revision "
        "annotations are not implemented; each needs its own symbol definition rather "
        "than text and a position."
    ),
    "DRW-006": (
        "A bill of materials in any of the four BOM types, read back cell by cell with "
        "DisplayedText so the contents are the evidence rather than the call having "
        "returned. Hole, revision, weldment cut-list, and general tables are not "
        "implemented, and neither is following a row back to the component it lists."
    ),
    "DRW-007": (
        "Additional sheets with their own size, scale, and projection standard, "
        "activated or not as asked, and measured back so a sheet of zero area is refused "
        "- NewSheet3 carries the same width/height trap as NewDocument. Changing an "
        "existing sheet's format or template, reordering views, and layer, line, and "
        "font standards are not implemented."
    ),
    "DRW-008": (
        "Views, dimensions, notes, tables, and dangling annotations are counted and "
        "located per sheet, and checked against caller-supplied minimums, with every "
        "finding attributed to the call it was read from. Overlap, clipping, and "
        "missing-callout detection are not implemented: they need annotation extents "
        "compared against each other, and DRW-010 is explicit that approximate bounding "
        "boxes must not be presented as proof a drawing is correct."
    ),
    "DRW-009": (
        "A drawing exports to PDF, DXF, or DWG, with the written file checked against "
        "that format's own signature and reported with size, timestamp, and SHA-256, "
        "plus counts of what was on the drawing when it was written. Sheet selection is "
        "PDF-only, because IExportPdfData is the only route to one - a sheet list given "
        "with DXF or DWG is reported as not applied rather than dropped silently. "
        "Exporting to an image goes through sw_view_capture, and a full delivery "
        "manifest across several drawings is IO-004, which is not implemented."
    ),
    "DRW-001": (
        "A drawing is created from an explicit or default template with a named sheet "
        "size, scale, and projection standard, and the sheet is measured back so a "
        "degenerate one is refused at creation. Units and title-block/property mapping "
        "are not implemented: the sheet format that carries a title block comes from the "
        "template, and NewDocument reports swDwgTemplateNone for the sheet it builds, so "
        "a drawing made here has no border or title block unless the template supplies "
        "one. That is reported as a warning rather than silently accepted."
    ),
    "DRW-002": (
        "Model views in any of the ten standard orientations, and the standard "
        "three-view arrangement in either projection standard, each verified by reading "
        "the created view's position, scale, referenced model, and configuration back. "
        "Section, detail, auxiliary, broken-out, crop, relative, and exploded views are "
        "not implemented: each needs a sketched profile or a parent view selection "
        "rather than a position, and they are rejected by the schema rather than failing "
        "at runtime."
    ),
    "MATE-005": (
        "Candidate mate entities are listed per component with the mate types each could "
        "take, and a specific pair is judged before it is built. Two halves of that "
        "verdict are measured — whether both references still resolve, and whether they "
        "sit on two different components — but whether the geometry can take the mate is "
        "*predicted* from entity type rather than ruled on by SOLIDWORKS. There is no "
        "validate-only mate call: AddMate5 has no dry-run flag, ForPositioningOnly moves "
        "the component, and IMateEntity2 exists only on a mate already built. "
        "sw_safe_execute is how to get a conclusive answer with rollback."
    ),
    "MATE-007": (
        "Per-component constrained status — fully, under, or over-constrained — with the "
        "mates holding each component, read from IComponent2::GetConstrainedStatus. "
        "Which axes remain free, and angular or linear travel along them, are not "
        "reported: IComponent2::GetRemainingDOFs answers swRemainingDofs_Unavailable on "
        "this build in every state probed, including through InvokeTypes with the twelve "
        "parameters declared [out], and including for the fixed root component that has "
        "its own enum value. The tool calls it anyway and reports what it said."
    ),
    "MATE-006": (
        "Rename, suppress, unsuppress, and delete one mate. Deleting a range or all "
        "mates at once, and replaying a mate sequence under a checkpoint, are not "
        "implemented — though sw_safe_execute already rolls back a sequence of any tools."
    ),
    "MATE-008": (
        "Interference detection, reporting each overlap's volume and the components "
        "involved. Clearance verification is a separate SOLIDWORKS manager "
        "(ClearanceVerificationManager) and is not implemented."
    ),
    "REV-001": (
        "Document, feature tree, sketches, bodies, configurations, components, and mass "
        "in one payload. Equations, dimensions, and custom properties still have their "
        "own tools and are not folded in here."
    ),
    "REV-004": (
        "Holes are audited from the B-Rep — cylindrical faces grouped by diameter, with "
        "axis and position — and compared against expected counts. Depth and "
        "datum-relative position are not measured, and slots are not audited."
    ),
    "REV-005": (
        "A policy review written as both JSON and Markdown, each finding attributed to "
        "what it read. The report covers the validation findings; it does not embed "
        "previews or a hole audit."
    ),
    "SK-007": (
        "Move, rotate, scale, mirror, offset, and trim are implemented. Extend, split, "
        "and sketch pattern are not, and are rejected by the schema rather than failing "
        "at runtime."
    ),
}
