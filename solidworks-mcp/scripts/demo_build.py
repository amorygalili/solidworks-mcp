"""Drive the server as a real MCP client and leave verifiable files behind.

This is not a test double: it spawns ``python -m swmcp`` over stdio, does the MCP
handshake, and calls the published tools exactly the way any other MCP client would.
Everything it writes goes into ``demo-output/``, which is also the only allowed output
root for the run.

    uv run python scripts/demo_build.py

Neighbourly by construction: it records which documents were already open before it
started and closes only the ones it created itself, addressed by title.
"""

from __future__ import annotations

import asyncio
import json
import math
import os
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = REPO_ROOT / "demo-output"
CHECKPOINT_DIR = OUT_DIR / ".checkpoints"
CALL_TIMEOUT = 300.0

PLATE_X, PLATE_Y, PLATE_Z = 100.0, 60.0, 8.0
HOLE_DIA = 6.6
FILLET_R = 5.0

WINDOWS_DECOY = "C:\\Windows\\System32\\swmcp_should_never_exist.SLDPRT"

#: The global variable this demo drives a dimension with. Deliberately not
#: "Thickness": SOLIDWORKS reserves that name and Add2 refuses it outright, returning
#: -1, while "MyThickness", "Width", "Height", "Depth", "Length", "Radius" and "Angle"
#: are all accepted. The demo used to pick the one word that does not work.
DRIVER_NAME = "WallThickness"

#: SOLIDWORKS quotes the names an equation reads, so this is one string with
#: embedded double quotes rather than a formatting mistake.
EQUATION_EXPRESSION = f'"{DRIVER_NAME}" * 1.5'


class Demo:
    """A recording MCP client."""

    def __init__(self, session: Any) -> None:
        self.session = session
        self.steps: list[dict[str, Any]] = []
        self.failures: list[str] = []

    async def call(
        self,
        tool: str,
        args: dict[str, Any] | None = None,
        *,
        why: str = "",
        expect: str = "ok",
        highlight: tuple[str, ...] = (),
    ) -> dict[str, Any]:
        args = args or {}
        raw = await self.session.call_tool(tool, args, read_timeout_seconds=CALL_TIMEOUT)
        payload = json.loads(raw.content[0].text)

        ok = bool(payload.get("ok"))
        satisfied = ok if expect == "ok" else not ok
        code = None if ok else payload.get("error", {}).get("code")

        source = payload.get("result") if ok else payload.get("error", {})
        picked = {}
        for key in highlight:
            if isinstance(source, dict) and key in source:
                picked[key] = source[key]

        self.steps.append(
            {
                "tool": tool,
                "why": why,
                "args": args,
                "ok": ok,
                "expected": expect,
                "as_expected": satisfied,
                "error_code": code,
                "highlights": picked,
                "result": payload.get("result"),
                "error": payload.get("error"),
            }
        )

        mark = "OK " if satisfied else "!! "
        detail = code or ", ".join(f"{k}={_short(v)}" for k, v in picked.items())
        print(f"  {mark}{tool:<28} {detail}"[:170], flush=True)
        if not satisfied:
            self.failures.append(f"{tool}: expected {expect}, got {code or 'ok'}")
            if not ok:
                print(f"     {payload['error'].get('message')}", flush=True)
        return payload

    async def open_titles(self) -> set[str]:
        payload = await self.call("sw_doc_list")
        self.steps.pop()  # bookkeeping, not part of the narrative
        if not payload.get("ok"):
            return set()
        return {doc["title"] for doc in payload["result"]["documents"]}


def _short(value: Any) -> str:
    text = json.dumps(value, default=str)
    return text if len(text) <= 70 else text[:67] + "..."


def heading(title: str) -> None:
    print(f"\n=== {title} ===", flush=True)


# --------------------------------------------------------------------------- parts


async def part_one_bracket(demo: Demo) -> Path:
    """The modelling vertical, checked against arithmetic at every step."""
    target = OUT_DIR / "demo_01_bracket.SLDPRT"
    heading("Part 1 - bracket: sketch, dimension, extrude, hole, pattern, fillet")

    await demo.call(
        "sw_doc_new",
        {"doc_type": "part"},
        why="Create a part from the template resolved off this machine's preferences.",
        highlight=("title", "doc_type"),
    )
    await demo.call(
        "sw_doc_save",
        {"output_path": str(target)},
        why="Save into the only allowed output root.",
        highlight=("saved_path", "artifact"),
    )
    await demo.call(
        "sw_sketch_start",
        {"on": {"standard_plane": "front"}},
        why="SYS-007: 'front' is resolved by tree position, never by the English name.",
        highlight=("sketch_name", "plane"),
    )

    added = await demo.call(
        "sw_sketch_add_geometry",
        {"entities": [{"type": "rect_corner", "corner": [0, 0], "opposite": [PLATE_X, PLATE_Y]}]},
        why="One batched call; a rectangle comes back as its four real line segments.",
        highlight=("created", "failed"),
    )
    ids = (
        [entry["sketch_local_id"] for entry in added["result"]["created"]]
        if added.get("ok")
        else []
    )

    if len(ids) >= 2:
        await demo.call(
            "sw_sketch_add_relations",
            {
                "relations": [
                    {"type": "horizontal", "segment_ids": [ids[0]]},
                    {"type": "vertical", "segment_ids": [ids[1]]},
                ]
            },
            why="CON-005: the result carries the solver state, so progress is measured.",
            highlight=("applied", "failed", "sketch_state"),
        )
        await demo.call(
            "sw_sketch_add_dimensions",
            {
                "dimensions": [
                    {
                        "type": "distance",
                        "segment_ids": [ids[0]],
                        "value": PLATE_X,
                        "place_at": [0.05, -0.02, 0],
                    },
                    {
                        "type": "distance",
                        "segment_ids": [ids[1]],
                        "value": "60mm",
                        "place_at": [0.12, 0.03, 0],
                    },
                ]
            },
            why="SYS-006: 100 is millimetres and '60mm' is parsed - one conversion boundary.",
            highlight=("created", "failed", "sketch_state"),
        )
        await demo.call(
            "sw_sketch_diagnose",
            why="Read the solver state back independently of the call that changed it.",
            highlight=("sketch_state",),
        )

    await demo.call("sw_sketch_exit", highlight=("sketch_name",))

    await demo.call(
        "sw_feature_extrude_boss",
        {"depth": PLATE_Z, "name": "BasePlate"},
        why=f"SAFE-010: expected {PLATE_X * PLATE_Y * PLATE_Z:.0f} mm3, verified by read-back.",
        highlight=(
            "feature_name",
            "body_count_before",
            "body_count_after",
            "volume_mm3_after",
            "verification",
        ),
    )

    measured = await demo.call(
        "sw_measure",
        why="An independent measurement, not the feature's own claim of success.",
        highlight=("mass_properties", "bounding_box", "topology", "validity"),
    )
    if measured.get("ok"):
        volume = measured["result"]["mass_properties"]["volume_mm3"]
        expected = PLATE_X * PLATE_Y * PLATE_Z
        if abs(volume - expected) > 1e-3:
            demo.failures.append(f"plate volume {volume} != {expected}")

    await _drill_pattern_and_round(demo)

    await demo.call(
        "sw_feature_list",
        why="The finished tree, with every feature's error code read back.",
        highlight=("count",),
    )
    await demo.call("sw_body_list", highlight=("count", "bodies"))
    await demo.call(
        "sw_doc_save",
        {"output_path": str(target), "overwrite": "allow", "confirm": True},
        why="overwrite='allow' is the one save path that needs confirmation.",
        highlight=("saved_path", "artifact"),
    )
    await _publish_the_bracket(demo)
    return target


async def _publish_the_bracket(demo: Demo) -> None:
    """A picture and two neutral files, so the result leaves SOLIDWORKS."""
    await demo.call(
        "sw_view_capture",
        {
            "output_path": str(OUT_DIR / "demo_01_bracket.png"),
            "orientation": "isometric",
            "width": 1280,
            "height": 960,
        },
        why="VIEW-004: the one piece of evidence JSON cannot carry. Open it and look.",
        highlight=("saved_path", "format", "requested_size", "actual_size", "method"),
    )
    await demo.call(
        "sw_export",
        {"output_path": str(OUT_DIR / "demo_01_bracket.step"), "step_protocol": "ap214"},
        why="IO-002: the written file is checked for its own ISO-10303-21 header.",
        highlight=("saved_path", "format", "signature_verified", "signature_detail", "settings"),
    )
    exported = await demo.call(
        "sw_export",
        {
            "output_path": str(OUT_DIR / "demo_01_bracket.stl"),
            "stl_binary": True,
            "stl_quality": "fine",
        },
        why="IO-003: a binary STL's triangle count is checked against its file size.",
        highlight=("saved_path", "signature_verified", "signature_detail", "size_bytes"),
    )
    if exported.get("ok") and not exported["result"]["signature_verified"]:
        demo.failures.append("the STL did not verify as an STL")


async def _drill_pattern_and_round(demo: Demo) -> None:
    """The half of the bracket that has to find its own references in the B-Rep."""
    probed = await demo.call(
        "sw_probe_faces",
        {"geometry_type": "planar_face", "area_min_mm2": PLATE_X * PLATE_Y * 0.99},
        why="Find the top face by geometry rather than by a fragile face index.",
        highlight=("matched",),
    )
    top_ref = None
    if probed.get("ok") and probed["result"]["candidates"]:
        top_ref = probed["result"]["candidates"][0]["tool_args"]["ref"]

    if top_ref is not None:
        await demo.call(
            "sw_feature_hole",
            {
                "face_ref": top_ref,
                "kind": "simple",
                "at": [20, 20, PLATE_Z],
                "diameter": HOLE_DIA,
                "through_all": True,
                "name": "MountingHole",
            },
            why="FEAT-012: confirmed by finding a cylindrical face, not by a return code.",
            highlight=("strategy_used", "holes_found", "volume_mm3_before", "volume_mm3_after"),
        )

    edges = await demo.call(
        "sw_probe_faces",
        {"entity_class": "edge", "geometry_type": "line_edge"},
        why="Edges for the pattern directions and the fillet, found by measurement.",
        highlight=("matched",),
    )
    long_edge = None
    short_edge = None
    vertical: list[dict[str, Any]] = []
    if edges.get("ok"):
        for candidate in edges["result"]["candidates"]:
            measurements = candidate["measurements"]
            length = measurements.get("length_m")
            if length is None:
                continue
            ref = candidate["tool_args"]["ref"]
            axis = measurements.get("direction") or [0.0, 0.0, 0.0]
            # The pattern runs along the edge's own direction, so pick the +X and +Y
            # edges: instances seeded from a hole near the origin then stay on the plate.
            if long_edge is None and abs(length - PLATE_X / 1000.0) < 1e-9 and axis[0] > 0.9:
                long_edge = ref
            if short_edge is None and abs(length - PLATE_Y / 1000.0) < 1e-9 and axis[1] > 0.9:
                short_edge = ref
            if abs(length - PLATE_Z / 1000.0) < 1e-9:
                vertical.append(ref)

    if long_edge and short_edge:
        await demo.call(
            "sw_feature_pattern",
            {
                "type": "linear",
                "feature_names": ["MountingHole"],
                "direction_ref": long_edge,
                "count": 2,
                "spacing": 60,
                "second_direction_ref": short_edge,
                "second_count": 2,
                "second_spacing": 20,
                "name": "HolePattern",
            },
            why="FEAT-007 is claimed only partially - linear and circular - and the "
            "schema says so rather than failing at runtime.",
            highlight=("feature_name", "instances_requested", "volume_mm3_after"),
        )
        found = await demo.call(
            "sw_probe_faces",
            {
                "geometry_type": "cylindrical_face",
                "radius_min": HOLE_DIA / 2 - 0.05,
                "radius_max": HOLE_DIA / 2 + 0.05,
            },
            why="Four holes must be findable in the B-Rep, or the pattern did not happen.",
            highlight=("matched",),
        )
        if found.get("ok") and found["result"]["matched"] < 4:
            demo.failures.append(f"expected 4 holes, the probe found {found['result']['matched']}")

    if len(vertical) >= 4:
        await demo.call(
            "sw_feature_fillet",
            {"refs": vertical[:4], "radius": FILLET_R},
            why="Rounding four corners must remove material; the check is arithmetic.",
            highlight=("edges_selected", "volume_mm3_before", "volume_mm3_after", "verification"),
        )


async def part_two_shaft(demo: Demo) -> Path:
    """A revolve, so the demo is not only extrusions."""
    target = OUT_DIR / "demo_02_shaft.SLDPRT"
    heading("Part 2 - stepped shaft: revolve about a sketch centerline")

    await demo.call("sw_doc_new", {"doc_type": "part"}, highlight=("title",))
    await demo.call("sw_doc_save", {"output_path": str(target)}, highlight=("saved_path",))
    await demo.call(
        "sw_sketch_start", {"on": {"standard_plane": "front"}}, highlight=("sketch_name",)
    )
    await demo.call(
        "sw_sketch_add_geometry",
        {
            "entities": [
                {"type": "centerline", "start": [0, 0], "end": [70, 0]},
                {"type": "line", "start": [0, 0], "end": [0, 15]},
                {"type": "line", "start": [0, 15], "end": [40, 15]},
                {"type": "line", "start": [40, 15], "end": [40, 10]},
                {"type": "line", "start": [40, 10], "end": [70, 10]},
                {"type": "line", "start": [70, 10], "end": [70, 0]},
                {"type": "line", "start": [70, 0], "end": [0, 0]},
            ]
        },
        why="A closed profile plus the axis centerline, in one COM round trip.",
        highlight=("created", "failed"),
    )
    await demo.call("sw_sketch_exit", highlight=("sketch_name",))

    expected = math.pi * (15**2 * 40 + 10**2 * 30)
    revolved = await demo.call(
        "sw_feature_revolve",
        {"angle": 360, "name": "Shaft"},
        why=f"Two cylinders: pi*(15^2*40 + 10^2*30) = {expected:.1f} mm3.",
        highlight=("feature_name", "body_count_after", "volume_mm3_after", "verification"),
    )
    if revolved.get("ok"):
        volume = revolved["result"].get("volume_mm3_after")
        if volume is not None and abs(volume - expected) / expected > 1e-4:
            demo.failures.append(f"shaft volume {volume:.1f} != {expected:.1f}")

    await demo.call("sw_measure", highlight=("mass_properties", "bounding_box", "topology"))
    await demo.call(
        "sw_doc_save",
        {"output_path": str(target), "overwrite": "allow", "confirm": True},
        highlight=("saved_path",),
    )
    return target


async def part_three_safety(demo: Demo) -> Path:
    """The safety story: refusals, versioning, and a rollback that is re-measured."""
    target = OUT_DIR / "demo_03_safety.SLDPRT"
    heading("Part 3 - safety: refusals, overwrite policy, checkpoint rollback")

    await demo.call("sw_doc_new", {"doc_type": "part"}, highlight=("title",))
    await demo.call("sw_doc_save", {"output_path": str(target)}, highlight=("saved_path",))

    await demo.call(
        "sw_doc_save",
        {"output_path": WINDOWS_DECOY},
        why="SAFE-004: refused before the COM boundary, and the error names the env var.",
        expect="error",
        highlight=("code", "message", "remediation"),
    )
    await demo.call(
        "sw_doc_list",
        {"nope": 1},
        why="SAFE-001: an unknown key is a typo, so it is an error rather than ignored.",
        expect="error",
        highlight=("code", "context"),
    )

    await demo.call(
        "sw_sketch_start", {"on": {"standard_plane": "front"}}, highlight=("sketch_name",)
    )
    await demo.call(
        "sw_sketch_add_geometry",
        {"entities": [{"type": "rect_center", "center": [0, 0], "corner": [30, 20]}]},
        highlight=("created", "failed"),
    )
    await demo.call("sw_sketch_exit", highlight=("sketch_name",))
    await demo.call(
        "sw_feature_extrude_boss",
        {"depth": "10mm", "name": "Block"},
        highlight=("feature_name", "volume_mm3_after"),
    )
    await demo.call(
        "sw_doc_save",
        {"output_path": str(target), "overwrite": "allow", "confirm": True},
        highlight=("saved_path",),
    )

    versioned = await demo.call(
        "sw_doc_save",
        {"output_path": str(target), "save_as_copy": True},
        why="SAFE-008: the default policy versions rather than replacing a deliverable.",
        highlight=("saved_path", "overwrite_policy", "artifact"),
    )
    if versioned.get("ok") and Path(versioned["result"]["saved_path"]) == target:
        demo.failures.append("the default overwrite policy replaced the original file")

    snapshot = await demo.call(
        "sw_checkpoint_create",
        why="SAFE-005: a snapshot that states by which method it was taken.",
        highlight=("checkpoint",),
    )
    before = await demo.call("sw_measure", highlight=("mass_properties",))
    original = before["result"]["mass_properties"]["volume_mm3"] if before.get("ok") else None

    await demo.call(
        "sw_feature_delete",
        {"feature_name": "Block"},
        why="SAFE-003: destructive, so it is refused without confirm - before any COM call.",
        expect="error",
        highlight=("code", "remediation"),
    )
    still_there = await demo.call(
        "sw_body_list", why="The body is still here; the refusal was real.", highlight=("count",)
    )
    if still_there.get("ok") and still_there["result"]["count"] != 1:
        demo.failures.append("the refused delete still changed the model")

    await demo.call(
        "sw_feature_delete",
        {"feature_name": "Block", "confirm": True, "delete_children": True},
        why="Now destroy it on purpose.",
        highlight=("deleted", "verification"),
    )
    emptied = await demo.call("sw_body_list", highlight=("count",))
    if emptied.get("ok") and emptied["result"]["count"] != 0:
        demo.failures.append("the confirmed delete did not remove the body")

    await demo.call(
        "sw_doc_save",
        {"output_path": str(target), "overwrite": "allow", "confirm": True},
        why="Persist the damage, so the rollback has something real to undo.",
        highlight=("saved_path",),
    )

    if snapshot.get("ok"):
        await demo.call(
            "sw_checkpoint_restore",
            {
                "checkpoint_path": snapshot["result"]["checkpoint"]["checkpoint_path"],
                "confirm": True,
            },
            why="Restoring is itself reversible: it snapshots the current state first.",
            highlight=("reopened", "pre_restore_checkpoint", "restored_path"),
        )
        recovered = await demo.call(
            "sw_measure",
            why="The proof: the model measures what it measured before the delete.",
            highlight=("mass_properties",),
        )
        if recovered.get("ok") and original is not None:
            now = recovered["result"]["mass_properties"]["volume_mm3"]
            if abs(now - original) > 1e-6:
                demo.failures.append(f"rollback measured {now}, expected {original}")

    await demo.call("sw_checkpoint_list", highlight=("count",))
    await demo.call(
        "sw_audit_tail",
        {"limit": 10},
        why="SAFE-006: every non-read operation is on the append-only log.",
        highlight=("count", "entries"),
    )
    return target


async def part_four_parametric(demo: Demo) -> Path:
    """A part driven by names rather than by geometry."""
    target = OUT_DIR / "demo_04_parametric.SLDPRT"
    heading("Part 4 - parametric: primitives, equations, configurations, properties")

    await demo.call("sw_doc_new", {"doc_type": "part"}, highlight=("title",))
    await demo.call("sw_doc_save", {"output_path": str(target)}, highlight=("saved_path",))

    await demo.call(
        "sw_body_primitive",
        {"kind": "box", "width": 80, "depth": 50, "height": 20, "name": "Body"},
        why="FEAT-014: an ordinary sketch and boss, checked against 80*50*20 mm3.",
        highlight=(
            "kind",
            "method",
            "expected_volume_mm3",
            "volume_mm3_after",
            "volume_error_ratio",
        ),
    )
    await demo.call(
        "sw_body_primitive",
        {"kind": "cylinder", "radius": 12, "height": 30, "at": [0, 45], "name": "Boss"},
        why="A second primitive, placed clear of the first so both survive.",
        highlight=("kind", "expected_volume_mm3", "volume_mm3_after"),
    )

    dimensions = await demo.call(
        "sw_dimension_list",
        why="PAR-001: every driving dimension, sketch and feature alike, by name.",
        highlight=("unit", "dimensions"),
    )
    driving = None
    if dimensions.get("ok"):
        for entry in dimensions["result"]["dimensions"]:
            if entry["owner"] == "Body" and entry.get("value_mm"):
                driving = entry["name"]
                break

    if driving:
        await demo.call(
            "sw_equation_set",
            {
                "equations": [
                    {
                        "operation": "add",
                        "name": DRIVER_NAME,
                        # Unit-suffixed: an equation is text, and SOLIDWORKS reads a
                        # bare number in document units, which is inches here.
                        "expression": "20mm",
                        "global_variable": True,
                    },
                    {"operation": "add", "name": driving, "expression": EQUATION_EXPRESSION},
                ]
            },
            why="PAR-002: a global variable now drives one of the box's dimensions.",
            highlight=("applied", "failed", "status", "circular_references"),
        )
        await demo.call(
            "sw_equation_list",
            why="Read the equations back, with what each one reads and any cycle.",
            highlight=("count", "equations", "global_variables", "circular_references"),
        )
        await demo.call(
            "sw_equation_set",
            {
                "equations": [
                    {"operation": "update", "name": DRIVER_NAME, "expression": "30mm"}
                ]
            },
            why="One value changed; the geometry follows.",
            highlight=("applied", "failed"),
        )
        await demo.call(
            "sw_measure",
            why="The proof that the equation drove real geometry.",
            highlight=("mass_properties", "bounding_box"),
        )

    await demo.call(
        "sw_config_create",
        {"name": "Heavy", "activate": True},
        why="PAR-003: a variant, confirmed by reading the configuration list back.",
        highlight=("name", "count_before", "count_after", "active"),
    )
    await demo.call("sw_config_list", highlight=("count", "active", "configurations"))
    await demo.call(
        "sw_property_set",
        {
            "properties": [
                {"name": "PartNumber", "value": "DEMO-004"},
                {"name": "Material", "value": "6061-T6"},
                {"name": "Revision", "value": "A"},
            ]
        },
        why="PAR-006: metadata a BOM would print, written and read back.",
        highlight=("written", "failed", "verification"),
    )
    await demo.call(
        "sw_property_list",
        {"configuration": "*"},
        why="Raw and evaluated values, file level and per configuration.",
        highlight=("count", "file_properties"),
    )
    await demo.call(
        "sw_parameter_table_export",
        {"output_path": str(OUT_DIR / "demo_04_parameters.csv")},
        why="PAR-005: every parameter in one CSV, editable outside SOLIDWORKS.",
        highlight=("saved_path", "row_count", "kinds"),
    )
    await demo.call(
        "sw_doc_save",
        {"output_path": str(target), "overwrite": "allow", "confirm": True},
        highlight=("saved_path",),
    )
    return target


async def part_five_atomic(demo: Demo) -> Path:
    """One checkpoint around a whole sequence, and a rollback when it does not hold."""
    target = OUT_DIR / "demo_05_atomic.SLDPRT"
    heading("Part 5 - atomic: a sequence that rolls itself back")

    await demo.call("sw_doc_new", {"doc_type": "part"}, highlight=("title",))
    await demo.call("sw_doc_save", {"output_path": str(target)}, highlight=("saved_path",))
    await demo.call(
        "sw_body_primitive",
        {"kind": "box", "width": 60, "depth": 40, "height": 20, "name": "Block"},
        highlight=("expected_volume_mm3", "volume_mm3_after"),
    )
    await demo.call(
        "sw_doc_save",
        {"output_path": str(target), "overwrite": "allow", "confirm": True},
        why="A saved document is a checkpointable one, which is what rollback needs.",
        highlight=("saved_path",),
    )

    baseline = await demo.call("sw_measure", highlight=("mass_properties",))
    original = (
        baseline["result"]["mass_properties"]["volume_mm3"] if baseline.get("ok") else None
    )

    await demo.call(
        "sw_safe_execute",
        {
            "steps": [
                {"tool": "sw_feature_shell", "args": {"thickness": 2}, "label": "hollow it"},
                {"tool": "sw_measure", "label": "check the result"},
            ],
            "invariants": {"body_count": 1, "volume_change": "decrease"},
            "confirm": True,
        },
        why="REV-006: a sequence whose invariants hold is kept.",
        highlight=("completed", "invariants_held", "invariants_checked", "rolled_back"),
    )

    # The kept sequence hollowed the block, so the model is legitimately smaller now.
    # A rollback undoes *its own* sequence, not every edit ever made, so this is the
    # figure the recovery below has to match - comparing against the original volume
    # would be asking the rollback to undo the shell as well.
    before_failure = await demo.call(
        "sw_measure",
        why="The starting point the next sequence will be rolled back to.",
        highlight=("mass_properties",),
    )
    if before_failure.get("ok"):
        original = before_failure["result"]["mass_properties"]["volume_mm3"]

    rolled = await demo.call(
        "sw_safe_execute",
        {
            "steps": [
                {
                    "tool": "sw_feature_delete",
                    "args": {
                        "feature_name": "Block",
                        "confirm": True,
                        "delete_children": True,
                    },
                    "label": "destroy the model",
                },
            ],
            # Deleting the block cannot leave a body, so this invariant must fail.
            "invariants": {"body_count": 1},
            "confirm": True,
        },
        why="The same machinery with an invariant it cannot meet: everything is undone.",
        highlight=("completed", "invariants_held", "rolled_back", "rollback", "warnings"),
    )
    if rolled.get("ok") and not rolled["result"]["rolled_back"]:
        demo.failures.append("the failing sequence was not rolled back")

    recovered = await demo.call(
        "sw_measure",
        why="The proof: the model measures exactly what it did before the sequence ran.",
        highlight=("mass_properties",),
    )
    if recovered.get("ok") and original is not None:
        now = recovered["result"]["mass_properties"]["volume_mm3"]
        if abs(now - original) > 1e-6:
            demo.failures.append(f"after rollback the model measures {now}, expected {original}")

    await demo.call(
        "sw_doc_save",
        {"output_path": str(target), "overwrite": "allow", "confirm": True},
        highlight=("saved_path",),
    )
    return target


async def session_probes(demo: Demo) -> None:
    heading("Session - what the server discovered about this machine")
    await demo.call(
        "sw_system_info",
        why="SYS-002: version, ProgID and install root discovered, never hardcoded.",
        highlight=("info",),
    )
    await demo.call(
        "sw_health",
        {"probe": False},
        why="SYS-005: answers without queueing, so it still works while COM is busy.",
        highlight=("status", "worker"),
    )
    await demo.call(
        "sw_capabilities", why="DISC-005: probed rather than assumed.", highlight=("capabilities",)
    )
    await demo.call(
        "sw_search_tools",
        {"query": "hole"},
        why="DISC-001: searches the whole catalog, including tools above the active tier.",
        highlight=("matched", "returned", "active_tier"),
    )


# ---------------------------------------------------------------------- transcript


def write_transcript(demo: Demo, files: list[Path]) -> Path:
    held = sum(1 for step in demo.steps if step["as_expected"])
    lines = [
        "# solidworks-mcp demo transcript",
        "",
        "Produced by `uv run python scripts/demo_build.py`, which spawns `python -m swmcp`",
        "over stdio and speaks MCP to it - the same path any MCP client takes.",
        "",
        f"- tool calls: **{len(demo.steps)}**",
        f"- behaved as expected: **{held}/{len(demo.steps)}**",
        "",
        "## Files written",
        "",
    ]
    for path in files:
        if path.exists():
            lines.append(f"- `{path.name}` - {path.stat().st_size:,} bytes")
    for pattern in ("demo_*.png", "demo_*.step", "demo_*.stl", "demo_*.csv"):
        for extra in sorted(OUT_DIR.glob(pattern)):
            lines.append(f"- `{extra.name}` - {extra.stat().st_size:,} bytes")
    for extra in sorted(OUT_DIR.glob("*_v0*.SLDPRT")):
        lines.append(
            f"- `{extra.name}` - {extra.stat().st_size:,} bytes (written by the versioning policy)"
        )
    lines += ["", "## Calls", ""]

    for index, step in enumerate(demo.steps, 1):
        verdict = "ok" if step["ok"] else f"refused: {step['error_code']}"
        flag = "" if step["as_expected"] else "  **UNEXPECTED**"
        lines.append(f"### {index}. `{step['tool']}` - {verdict}{flag}")
        if step["why"]:
            lines += ["", step["why"]]
        lines += ["", "```json", json.dumps(step["args"], indent=2, default=str), "```", ""]
        shown = step["highlights"] or ({} if step["ok"] else step["error"])
        if shown:
            body = json.dumps(shown, indent=2, default=str)
            if len(body) > 2000:
                body = body[:2000] + "\n... (truncated; the full payload is in demo-log.json)"
            lines += ["```json", body, "```", ""]

    path = OUT_DIR / "DEMO-TRANSCRIPT.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    (OUT_DIR / "demo-log.json").write_text(
        json.dumps({"steps": demo.steps, "failures": demo.failures}, indent=2, default=str),
        encoding="utf-8",
    )
    return path


# ---------------------------------------------------------------------------- main


async def sweep_previous_run(sweeper: Demo) -> None:
    """Close leftovers from an earlier run, then clear the folder.

    Deleting a file while SOLIDWORKS still has the document open leaves a live document
    pointing at a path that no longer exists, and the next save then lands on a
    different document than the caller thinks. So the documents go first, addressed by
    their own titles - nothing else in the session is touched.
    """
    stale = sorted(title for title in await sweeper.open_titles() if title.startswith("demo_0"))
    for title in stale:
        await sweeper.call(
            "sw_doc_close",
            {"document": {"title": title}, "save_first": "discard", "confirm": True},
        )
    sweeper.steps.clear()
    sweeper.failures.clear()
    if stale:
        print(f"closed leftovers from an earlier run: {stale}", flush=True)

    patterns = ("demo_*.SLDPRT", "demo_*.png", "demo_*.step", "demo_*.stl", "demo_*.csv")
    stale_files = [path for pattern in patterns for path in OUT_DIR.glob(pattern)]
    for path in (*stale_files, *CHECKPOINT_DIR.glob("demo_*.SLDPRT")):
        try:
            path.unlink()
        except OSError as exc:
            print(f"could not remove {path.name}: {exc}", flush=True)


async def run() -> int:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    environment = {
        **os.environ,
        "SWMCP_TOOL_TIER": "all",
        "SWMCP_ALLOWED_ROOTS": str(OUT_DIR),
        "SWMCP_AUDIT_PATH": str(OUT_DIR / "audit.jsonl"),
        "SWMCP_CHECKPOINT_DEBOUNCE_SEC": "0",
    }
    parameters = StdioServerParameters(
        command=sys.executable, args=["-m", "swmcp"], env=environment, cwd=str(REPO_ROOT)
    )

    print(f"output root: {OUT_DIR}", flush=True)
    async with stdio_client(parameters) as (read, write), ClientSession(read, write) as session:
        await session.initialize()
        tools = (await session.list_tools()).tools
        print(f"handshake ok: {len(tools)} tools published", flush=True)

        demo = Demo(session)
        await sweep_previous_run(Demo(session))
        pre_existing = await demo.open_titles()
        print(f"already open (left alone): {sorted(pre_existing) or 'nothing'}", flush=True)

        await session_probes(demo)
        files = [
            await part_one_bracket(demo),
            await part_two_shaft(demo),
            await part_three_safety(demo),
            await part_four_parametric(demo),
            await part_five_atomic(demo),
        ]

        heading("Cleanup - closing only what this run created")
        for title in sorted(await demo.open_titles() - pre_existing):
            await demo.call(
                "sw_doc_close",
                {"document": {"title": title}, "save_first": "discard", "confirm": True},
                why="Addressed by title; never 'whatever happens to be active'.",
                highlight=("closed", "title"),
            )

        transcript = write_transcript(demo, files)

    print(f"\ntranscript: {transcript}", flush=True)
    if demo.failures:
        print("\nchecks that did not hold:", file=sys.stderr)
        for failure in demo.failures:
            print(f"  - {failure}", file=sys.stderr)
        return 1
    print("every check held", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(run()))
