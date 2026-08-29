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
        "IO-002", "IO-003", "REV-006",
        # P2 — assemblies. The first vertical of P2: insert, inspect, and set component
        # state. Transforms (ASM-004) and the rest of ASM are not claimed yet.
        "ASM-001", "ASM-002", "ASM-003",
        # P2 — mates. Add and inspect; editing and the exotic mate types are not
        # claimed yet.
        "MATE-001", "MATE-002", "MATE-003", "MATE-004",
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
    "REF-005": (
        "Face, planar-face, cylindrical-face, feature-face, body-ownership, and ray probes "
        "are implemented. Candidate mate entities require the assembly domain (P2)."
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
    "SK-007": (
        "Move, rotate, scale, mirror, offset, and trim are implemented. Extend, split, "
        "and sketch pattern are not, and are rejected by the schema rather than failing "
        "at runtime."
    ),
}
