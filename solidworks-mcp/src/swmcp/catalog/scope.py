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
        # P1 vertical — constraints and dimensions
        "CON-001", "CON-002", "CON-003", "CON-004", "CON-005",
        # P1 vertical — reference geometry
        "DAT-001", "DAT-002", "DAT-003", "DAT-004", "DAT-005",
        # P1 vertical — parameters, configurations, and metadata
        "PAR-001", "PAR-002", "PAR-003", "PAR-004", "PAR-005", "PAR-006",
        # Pulled forward from P2: export is how the model reaches anything else, and
        # an atomic sequence is what the safety layer has been building toward.
        "IO-002", "IO-003", "REV-006",
        # P1 vertical — appearance and view
        "VIEW-003", "VIEW-004",
        # P1 vertical — core features, bodies, measurement
        "FEAT-001", "FEAT-002", "FEAT-003", "FEAT-006", "FEAT-007",
        "FEAT-009", "FEAT-011", "FEAT-014",
        "FEAT-012", "FEAT-015", "FEAT-016", "FEAT-019",
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
    "FEAT-014": (
        "Box, cylinder, sphere, cone, frustum, torus, wedge, and prism, each built as "
        "an ordinary sketch and boss. Helix and spring are not implemented."
    ),
    "REF-005": (
        "Face, planar-face, cylindrical-face, feature-face, body-ownership, and ray probes "
        "are implemented. Candidate mate entities require the assembly domain (P2)."
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
    "SK-007": (
        "Move, rotate, scale, mirror, offset, and trim are implemented. Extend, split, "
        "and sketch pattern are not, and are rejected by the schema rather than failing "
        "at runtime."
    ),
}
