# solidworks-mcp demo transcript

Produced by `uv run python scripts/demo_build.py`, which spawns `python -m swmcp`
over stdio and speaks MCP to it - the same path any MCP client takes.

- tool calls: **55**
- behaved as expected: **55/55**

## Files written

- `demo_01_bracket.SLDPRT` - 75,058 bytes
- `demo_02_shaft.SLDPRT` - 63,066 bytes
- `demo_03_safety.SLDPRT` - 44,614 bytes
- `demo_03_safety_v002.SLDPRT` - 44,571 bytes (written by the versioning policy)

## Calls

### 1. `sw_system_info` - ok

SYS-002: version, ProgID and install root discovered, never hardcoded.

```json
{}
```

```json
{
  "info": {
    "attached": true,
    "attached_prog_id": "SldWorks.Application.34",
    "launched_by_this_server": false,
    "process_running": true,
    "install": {
      "found": true,
      "executable": "C:\\Program Files\\Dassault Systemes\\SOLIDWORKS 3DEXPERIENCE R2026x\\SOLIDWORKS\\sldworks.exe",
      "install_root": "C:\\Program Files\\Dassault Systemes\\SOLIDWORKS 3DEXPERIENCE R2026x\\SOLIDWORKS",
      "clsid": "{666aaee2-7a21-40fc-b768-2078840a88c3}",
      "registered_prog_ids": [
        "SldWorks.Application",
        "SldWorks.Application.34"
      ],
      "template_dirs": [
        "C:\\ProgramData\\SolidWorks\\SOLIDWORKS Inspection 2026 AddIn\\templates",
        "C:\\ProgramData\\SolidWorks\\SOLIDWORKS 2026\\templates"
      ],
      "notes": []
    },
    "constants": {
      "typelib_iid": "{4687F359-55D0-4CD3-B6CF-2EB42C11F989}",
      "typelib_major": 34,
      "enum_count": 983
    },
    "preference_overrides": {},
    "revision": "34.3.0",
    "major": 34,
    "year": 2026,
    "prog_id": "SldWorks.Application.34",
    "base_prog_id": "SldWorks.Application",
    "language": "english",
    "executable_path": "C:\\Program Files\\Dassault Systemes\\SOLIDWORKS 3DEXPERIENCE R2026x\\SOLIDWORKS",
    "active_document": {
      "title": "Part1",
      "path": null,
      "doc_type": "part",
      "doc_type_code": 1,
      "is_saved": false,
      "is_dirty": false,
      "configuration": "Default",
      "checkpointable": false,
      "opened_read_only": false,
      "warnings": [
        "This document has never been saved, so it cannot be checkpointed. Save it before making risky changes."
      ]
    }
  }
}
```

### 2. `sw_health` - ok

SYS-005: answers without queueing, so it still works while COM is busy.

```json
{
  "probe": false
}
```

```json
{
  "worker": {
    "thread_alive": true,
    "apartment": "STA",
    "thread_ident": 36412,
    "queue_depth": 0,
    "inflight": {
      "label": "sw_health",
      "elapsed_s": 0.0
    },
    "session_attached": true,
    "calls": {
      "total": 3,
      "failed": 0,
      "busy_retries": 0,
      "reattaches": 0,
      "latency_ms": {
        "sw_doc_list": {
          "p50": 210.48,
          "p95": 247.32
        },
        "sw_system_info": {
          "p50": 552.47,
          "p95": 552.47
        }
      }
    }
  }
}
```

### 3. `sw_capabilities` - ok

DISC-005: probed rather than assumed.

```json
{}
```

```json
{
  "capabilities": {
    "attach": true,
    "default_templates": {
      "part": "C:\\ProgramData\\SolidWorks\\SOLIDWORKS 2026\\templates\\Part.prtdot",
      "assembly": "C:\\ProgramData\\SolidWorks\\SOLIDWORKS 2026\\templates\\Assembly.asmdot",
      "drawing": "C:\\ProgramData\\SolidWorks\\SOLIDWORKS 2026\\templates\\Drawing.drwdot"
    },
    "templates_present": {
      "part": true,
      "assembly": true,
      "drawing": true
    },
    "constant_table": {
      "typelib_iid": "{4687F359-55D0-4CD3-B6CF-2EB42C11F989}",
      "typelib_major": 34,
      "enum_count": 983
    },
    "revision": "34.3.0"
  }
}
```

### 4. `sw_search_tools` - ok

DISC-001: searches the whole catalog, including tools above the active tier.

```json
{
  "query": "hole"
}
```

```json
{
  "matched": 1,
  "returned": 1,
  "active_tier": "all"
}
```

### 5. `sw_doc_new` - ok

Create a part from the template resolved off this machine's preferences.

```json
{
  "doc_type": "part"
}
```

### 6. `sw_doc_save` - ok

Save into the only allowed output root.

```json
{
  "output_path": "C:\\projects\\cad-mcp-comparisons\\solidworks-mcp\\demo-output\\demo_01_bracket.SLDPRT"
}
```

```json
{
  "saved_path": "C:\\projects\\cad-mcp-comparisons\\solidworks-mcp\\demo-output\\demo_01_bracket.SLDPRT"
}
```

### 7. `sw_sketch_start` - ok

SYS-007: 'front' is resolved by tree position, never by the English name.

```json
{
  "on": {
    "standard_plane": "front"
  }
}
```

```json
{
  "sketch_name": "Sketch1",
  "plane": "front"
}
```

### 8. `sw_sketch_add_geometry` - ok

One batched call; a rectangle comes back as its four real line segments.

```json
{
  "entities": [
    {
      "type": "rect_corner",
      "corner": [
        0,
        0
      ],
      "opposite": [
        100.0,
        60.0
      ]
    }
  ]
}
```

```json
{
  "created": [
    {
      "index": 1,
      "requested_type": "rect_corner",
      "sketch_local_id": "1:1",
      "type": "line",
      "construction": false,
      "length_m": 0.1
    },
    {
      "index": 1,
      "requested_type": "rect_corner",
      "sketch_local_id": "2:2",
      "type": "line",
      "construction": false,
      "length_m": 0.06
    },
    {
      "index": 1,
      "requested_type": "rect_corner",
      "sketch_local_id": "3:3",
      "type": "line",
      "construction": false,
      "length_m": 0.1
    },
    {
      "index": 1,
      "requested_type": "rect_corner",
      "sketch_local_id": "4:4",
      "type": "line",
      "construction": false,
      "length_m": 0.06
    }
  ],
  "failed": []
}
```

### 9. `sw_sketch_add_relations` - ok

CON-005: the result carries the solver state, so progress is measured.

```json
{
  "relations": [
    {
      "type": "horizontal",
      "segment_ids": [
        "1:1"
      ]
    },
    {
      "type": "vertical",
      "segment_ids": [
        "2:2"
      ]
    }
  ]
}
```

```json
{
  "applied": 2,
  "failed": [],
  "sketch_state": {
    "status": "under_defined",
    "status_code": 2,
    "fully_defined": false,
    "over_defined": false,
    "relation_count": 5,
    "dangling_relations": [],
    "over_defining_relations": []
  }
}
```

### 10. `sw_sketch_add_dimensions` - ok

SYS-006: 100 is millimetres and '60mm' is parsed - one conversion boundary.

```json
{
  "dimensions": [
    {
      "type": "distance",
      "segment_ids": [
        "1:1"
      ],
      "value": 100.0,
      "place_at": [
        0.05,
        -0.02,
        0
      ]
    },
    {
      "type": "distance",
      "segment_ids": [
        "2:2"
      ],
      "value": "60mm",
      "place_at": [
        0.12,
        0.03,
        0
      ]
    }
  ]
}
```

```json
{
  "created": [
    {
      "index": 1,
      "type": "distance",
      "name": "D1@Sketch1@demo_01_bracket.Part",
      "before_value_m": 0.1,
      "after_value_m": 0.1,
      "driving": true
    },
    {
      "index": 2,
      "type": "distance",
      "name": "D2@Sketch1@demo_01_bracket.Part",
      "before_value_m": 0.06,
      "after_value_m": 0.06,
      "driving": true
    }
  ],
  "failed": [],
  "sketch_state": {
    "status": "fully_defined",
    "status_code": 3,
    "fully_defined": true,
    "over_defined": false,
    "relation_count": 7,
    "dangling_relations": [],
    "over_defining_relations": []
  }
}
```

### 11. `sw_sketch_diagnose` - ok

Read the solver state back independently of the call that changed it.

```json
{}
```

```json
{
  "sketch_state": {
    "status": "fully_defined",
    "status_code": 3,
    "fully_defined": true,
    "over_defined": false,
    "relation_count": 7,
    "dangling_relations": [],
    "over_defining_relations": []
  }
}
```

### 12. `sw_sketch_exit` - ok

```json
{}
```

```json
{
  "sketch_name": "Sketch1"
}
```

### 13. `sw_feature_extrude_boss` - ok

SAFE-010: expected 48000 mm3, verified by read-back.

```json
{
  "depth": 8.0,
  "name": "BasePlate"
}
```

```json
{
  "feature_name": "BasePlate",
  "body_count_before": 0,
  "body_count_after": 1,
  "volume_mm3_after": 47999.99999999999,
  "verification": {
    "read_back": true,
    "before": {
      "body_count": 0,
      "volume_m3": 0.0,
      "volume_mm3": 0.0,
      "surface_area_m2": 0.0,
      "surface_area_mm2": 0.0,
      "face_count": 0,
      "edge_count": 0,
      "feature_count": 18
    },
    "after": {
      "body_count": 1,
      "volume_m3": 4.7999999999999994e-05,
      "volume_mm3": 47999.99999999999,
      "surface_area_m2": 0.01456,
      "surface_area_mm2": 14560.0,
      "face_count": 6,
      "edge_count": 12,
      "feature_count": 19
    },
    "checks": [
      {
        "name": "feature_created",
        "passed": true,
        "detail": "BasePlate"
      },
      {
        "name": "geometry_changed",
        "passed": true,
        "detail": "material was added: volume 0.000 -> 48000.000 mm\u00b3, bodies 0 -> 1"
      },
      {
        "name": "model_has_a_body",
        "passed": true,
        "detail": "1 solid body(ies)"
      },
      {
        "name": "feature_has_no_error",
        "passed": true,
        "detail": "0"
      }
    ]
  }
}
```

### 14. `sw_measure` - ok

An independent measurement, not the feature's own claim of success.

```json
{}
```

```json
{
  "mass_properties": {
    "volume_m3": 4.7999999999999994e-05,
    "volume_mm3": 47999.99999999999,
    "surface_area_m2": 0.01456,
    "surface_area_mm2": 14560.0,
    "mass_kg": 4.7999999999999994e-05,
    "density_kg_m3": 1.0,
    "center_of_mass_mm": [
      50.0,
      30.0,
      4.0
    ]
  },
  "bounding_box": {
    "min_mm": [
      0.0,
      0.0,
      0.0
    ],
    "max_mm": [
      100.0,
      60.0,
      8.0
    ],
    "size_mm": [
      100.0,
      60.0,
      8.0
    ]
  },
  "topology": {
    "body_count": 1,
    "face_count": 6,
    "edge_count": 12,
    "feature_count": 19
  },
  "validity": {
    "has_volume": true,
    "features_in_error": []
  }
}
```

### 15. `sw_probe_faces` - ok

Find the top face by geometry rather than by a fragile face index.

```json
{
  "geometry_type": "planar_face",
  "area_min_mm2": 5940.0
}
```

```json
{
  "matched": 2
}
```

### 16. `sw_feature_hole` - ok

FEAT-012: confirmed by finding a cylindrical face, not by a return code.

```json
{
  "face_ref": {
    "ref_version": 1,
    "kind": "face",
    "label": "",
    "document": {
      "path": "C:\\projects\\cad-mcp-comparisons\\solidworks-mcp\\demo-output\\demo_01_bracket.SLDPRT",
      "title": "demo_01_bracket.SLDPRT",
      "configuration": "Default"
    },
    "persistent": {
      "scheme": "GetPersistReference3",
      "data_b64": "OEoAAAMAAAD//v8AAAAAAP//AQALAG1vRmFjZVJlZl9jAQAAAAAAAAAGAAAAAAIAAAAAAAB9w5QlrUmyVH3DlCWtSbJUAAD//wEAFABtb0VuZEZhY2VTdXJmSWRSZXBfYwAA//8BAAYAbW9GUl9j//8BAA0AbW9FeHRPYmplY3RfY///AQARAG1vQ1N0cmluZ0hhbmRsZV9j//7/UUMAOgBcAHAAcgBvAGoAZQBjAHQAcwBcAGMAYQBkAC0AbQBjAHAALQBjAG8AbQBwAGEAcgBpAHMAbwBuAHMAXABzAG8AbABpAGQAdwBvAHIAawBzAC0AbQBjAHAAXABkAGUAbQBvAC0AbwB1AHQAcAB1AHQAXABkAGUAbQBvAF8AMAAxAF8AYgByAGEAYwBrAGUAdAAuAFMATABEAFAAUgBUAAmA//7/D2QAZQBtAG8AXwAwADEAXwBiAHIAYQBjAGsAZQB0AAIAAK+NkGr//v8A//7/AP/+/wAAAAAAAAAAAAAAAAAAAAAAAAD//v8HRABlAGYAYQB1AGwAdAAAAAAAAAAAAAAAAAAAAAAAIgAAALuNkGoBAAAAAAAAAP//AQAXAG1vRnJvbVNrdEVudFN1cmZJZFJlcF9jAAAFgAgAIgAAALuNkGoEAAAADIAAAAWACAAiAAAAu42QagEAAAAMgAAABYAIACIAAAC7jZBqAgAAAAyAAAAFgAgAIgAAALuNkGoDAAAAAAAAAAAAAAAAADhKAAAAAAAAAAAAAA=="
    },
    "semantic": {
      "component_path": [],
      "feature_ancestry": [
        "BasePlate"
      ],
      "feature_type_names": [
        "Extrusion"
      ],
      "geometry_type": "planar_face",
      "body_name": "BasePlate",
      "measurements": {
        "point_m": [
          0.05,
          0.03,
          0.008
        ],
        "direction": [
          0.0,
          0.0,
          -1.0
        ],
        "area_m2": 0.006,
        "bbox_m": [
          0.0,
          0.0,
          0.008,
          0.1,
          0.06,
          0.008
        ]
      },
      "signature": "1cbbb42d216696a315aa",
      "tolerance": {
        "linear_m": 1e-06,
        "angular_rad": 1e-06,
        "relative": 0.0001
      }
    },
    "warnings": []
  },
  "kind": "simple",
  "at": [
    20,
    20,
    8.0
  ],
  "diameter": 6.6,
  "through_all": true,
  "name": "MountingHole"
}
```

```json
{
  "strategy_used": "cut_extrude",
  "holes_found": 1,
  "volume_mm3_before": 47999.99999999999,
  "volume_mm3_after": 47726.30444801925
}
```

### 17. `sw_probe_faces` - ok

Edges for the pattern directions and the fillet, found by measurement.

```json
{
  "entity_class": "edge",
  "geometry_type": "line_edge"
}
```

```json
{
  "matched": 12
}
```

### 18. `sw_feature_pattern` - ok

FEAT-007 is claimed only partially - linear and circular - and the schema says so rather than failing at runtime.

```json
{
  "type": "linear",
  "feature_names": [
    "MountingHole"
  ],
  "direction_ref": {
    "ref_version": 1,
    "kind": "edge",
    "label": "",
    "document": {
      "path": "C:\\projects\\cad-mcp-comparisons\\solidworks-mcp\\demo-output\\demo_01_bracket.SLDPRT",
      "title": "demo_01_bracket.SLDPRT",
      "configuration": "Default"
    },
    "persistent": {
      "scheme": "GetPersistReference3",
      "data_b64": "OEoAAAMAAAD//v8AAAAAAP//AQALAG1vRWRnZVJlZl9jAQAAAAAAAAAEAAAAAAMAAAAAAAB9w5QlrUmyVH3DlCWtSbJUAAD//wEAFABtb0VuZEZhY2VTdXJmSWRSZXBfYwAA//8BAAYAbW9GUl9j//8BAA0AbW9FeHRPYmplY3RfY///AQARAG1vQ1N0cmluZ0hhbmRsZV9j//7/UUMAOgBcAHAAcgBvAGoAZQBjAHQAcwBcAGMAYQBkAC0AbQBjAHAALQBjAG8AbQBwAGEAcgBpAHMAbwBuAHMAXABzAG8AbABpAGQAdwBvAHIAawBzAC0AbQBjAHAAXABkAGUAbQBvAC0AbwB1AHQAcAB1AHQAXABkAGUAbQBvAF8AMAAxAF8AYgByAGEAYwBrAGUAdAAuAFMATABEAFAAUgBUAAmA//7/D2QAZQBtAG8AXwAwADEAXwBiAHIAYQBjAGsAZQB0AAIAAK+NkGr//v8A//7/AP/+/wAAAAAAAAAAAAAAAAAAAAAAAAD//v8HRABlAGYAYQB1AGwAdAAAAAAAAAAAAAAAAAAAAAAAIgAAALuNkGoBAAAAAAAAAP//AQAXAG1vRnJvbVNrdEVudFN1cmZJZFJlcF9jAAAFgAgAIgAAALuNkGoBAAAADIAAAAWACAAiAAAAu42QagQAAAAMgAAABYAIACIAAAC7jZBqAgAAAAAAAAAAAAAAOEoAAAAAAAA="
    },
    "semantic": {
      "component_path": [],
      "feature_ancestry": [],
      "feature_type_names": [],
      "geometry_type": "line_edge",
      "body_name": "MountingHole",
      "measurements": {
        "point_m": [
          0.05,
          0.0,
          0.008
        ],
        "direction": [
          1.0,
          0.0,
          0.0
        ],
        "length_m": 0.1
      },
      "signature": "e5d177050ed750a09389",
      "tolerance": {
        "linear_m": 1e-06,
        "angular_rad": 1e-06,
        "relative": 0.0001
      }
    },
    "warnings": []
  },
  "count": 2,
  "spacing": 60,
  "second_direction_ref": {
    "ref_version": 1,
    "kind": "edge",
    "label": "",
    "document": {
      "path": "C:\\projects\\cad-mcp-comparisons\\solidworks-mcp\\demo-output\\demo_01_bracket.SLDPRT",
      "title": "demo_01_bracket.SLDPRT",
      "configuration": "Default"
    },
    "persistent": {
      "scheme": "GetPersistReference3",
      "data_b64": "OEoAAAMAAAD//v8AAAAAAP//AQALAG1vRWRnZVJlZl9jAQAAAAAAAAAEAAAAAAMAAAAAAAB9w5QlrUmyVH3DlCWtSbJUAAD//wEAFABtb0VuZEZhY2VTdXJmSWRSZXBfYwAA//8BAAYAbW9GUl9j//8BAA0AbW9FeHRPYmplY3RfY///AQARAG1vQ1N0cmluZ0hhbmRsZV9j//7/UUMAOgBcAHAAcgBvAGoAZQBjAHQAcwBcAGMAYQBkAC0AbQBjAHAALQBjAG8AbQBwAGEAcgBpAHMAbwBuAHMAXABzAG8AbABpAGQAdwBvAHIAawBzAC0AbQBjAHAAXABkAGUAbQBvAC0AbwB1AHQAcAB1AHQAXABkAGUAbQBvAF8AMAAxAF8AYgByAGEAYwBrAGUAdAAuAFMATABEAFAAUgBUAAmA//7/D2QAZQBtAG8AXwAwADEAXwBiAHIAYQBjAGsAZQB0AAIAAK+NkGr//v8A//7/AP/+/wAAAAAAAAAAAAAAAAAAAAAAAAD//v8HRABlAGYAYQB1AGwAdAAAAAAAAAAAAAAAAAAAAAAAIgAAALuNkGoBAAAAAAAAAP//AQAXAG1vRnJvbVNrdEVudFN1cmZJZFJlcF9jAAAFgAgAIgAAALuNkGoCAAAADIAAAAWACAAiAAAAu42QagEAAAAMgAAABYAIACIAAAC7jZBqAwAAAAAAAAAAAAAAOEoAAAAAAAA="
    },
    "semantic": {
      "component_path": [],
      "feature_ancestry": [],
      "feature_type_names": [],
      "geometry_type": "line_edge",
      "body_name": "MountingHole",
      "measurements": {
        "point_m": [
          0.1,
          0.03,
          0.008
        ],
        "direction": [
          0.0,
          1.0,
          0.0
        ],
        "length_m": 0.06
      },
      "signature": "d406506980b469740d4d",
      "tolerance": {
        "linear_m": 1e-06,
        "angular_rad": 1e-06,
        "relative": 0.0001
      }
    },
    "warnings": []
  },
  "second_count": 2,
  "second_spacing": 20,
  "name": "HolePattern"
}
```

```json
{
  "feature_name": "HolePattern",
  "instances_requested": 4,
  "volume_mm3_after": 46905.21779207701
}
```

### 19. `sw_probe_faces` - ok

Four holes must be findable in the B-Rep, or the pattern did not happen.

```json
{
  "geometry_type": "cylindrical_face",
  "radius_min": 3.25,
  "radius_max": 3.3499999999999996
}
```

```json
{
  "matched": 4
}
```

### 20. `sw_feature_fillet` - ok

Rounding four corners must remove material; the check is arithmetic.

```json
{
  "refs": [
    {
      "ref_version": 1,
      "kind": "edge",
      "label": "",
      "document": {
        "path": "C:\\projects\\cad-mcp-comparisons\\solidworks-mcp\\demo-output\\demo_01_bracket.SLDPRT",
        "title": "demo_01_bracket.SLDPRT",
        "configuration": "Default"
      },
      "persistent": {
        "scheme": "GetPersistReference3",
        "data_b64": "OEoAAAMAAAD//v8AAAAAAP//AQALAG1vRWRnZVJlZl9jAQAAAAAAAAAEAAAAAAMAAAAAAAB9w5QlrUmyVH3DlCWtSbJUAAD//wEAFwBtb0Zyb21Ta3RFbnRTdXJmSWRSZXBfYwAA//8BAAYAbW9GUl9j//8BAA0AbW9FeHRPYmplY3RfY///AQARAG1vQ1N0cmluZ0hhbmRsZV9j//7/UUMAOgBcAHAAcgBvAGoAZQBjAHQAcwBcAGMAYQBkAC0AbQBjAHAALQBjAG8AbQBwAGEAcgBpAHMAbwBuAHMAXABzAG8AbABpAGQAdwBvAHIAawBzAC0AbQBjAHAAXABkAGUAbQBvAC0AbwB1AHQAcAB1AHQAXABkAGUAbQBvAF8AMAAxAF8AYgByAGEAYwBrAGUAdAAuAFMATABEAFAAUgBUAAmA//7/D2QAZQBtAG8AXwAwADEAXwBiAHIAYQBjAGsAZQB0AAIAAK+NkGr//v8A//7/AP/+/wAAAAAAAAAAAAAAAAAAAAAAAAD//v8HRABlAGYAYQB1AGwAdAAAAAAAAAAAAAAAAAAAAAAAIgAAALuNkGoBAAAAA4AAAAWACAAiAAAAu42QagQAAAD//wEAFABtb0VuZEZhY2VTdXJmSWRSZXBfYwAABYAIACIAAAC7jZBqAQAAAAAAAAAOgAAABYAIACIAAAC7jZBqAAAAAAAAAAAAAAAAAAAAADhKAAAAAAAA"
      },
      "semantic": {
        "component_path": [],
        "feature_ancestry": [],
        "feature_type_names": [],
        "geometry_type": "line_edge",
        "body_name": "MountingHole",
        "measurements": {
          "point_m": [
            0.0,
            0.0,
            0.004
          ],
          "direction": [
            0.0,
            0.0,
            -1.0
          ],
          "length_m": 0.008
        },
        "signature": "ed73036d33addd29c1c2",
        "tolerance": {
          "linear_m": 1e-06,
          "angular_rad": 1e-06,
          "relative": 0.0001
        }
      },
      "warnings": []
    },
    {
      "ref_version": 1,
      "kind": "edge",
      "label": "",
      "document": {
        "path": "C:\\projects\\cad-mcp-comparisons\\solidworks-mcp\\demo-output\\demo_01_bracket.SLDPRT",
        "title": "demo_01_bracket.SLDPRT",
        "configuration": "Default"
      },
      "persistent": {
        "scheme": "GetPersistReference3",
        "data_b64": "OEoAAAMAAAD//v8AAAAAAP//AQALAG1vRWRnZVJlZl9jAQAAAAAAAAAEAAAAAAMAAAAAAAB9w5QlrUmyVH3DlCWtSbJUAAD//wEAFwBtb0Zyb21Ta3RFbnRTdXJmSWRSZXBfYwAA//8BAAYAbW9GUl9j//8BAA0AbW9FeHRPYmplY3RfY///AQARAG1vQ1N0cmluZ0hhbmRsZV9j//7/UUMAOgBcAHAAcgBvAGoAZQBjAHQAcwBcAGMAYQBkAC0AbQBjAHAALQBjAG8AbQBwAGEAcgBpAHMAbwBuAHMAXABzAG8AbABpAGQAdwBvAHIAawBzAC0AbQBjAHAAXABkAGUAbQBvAC0AbwB1AHQAcAB1AHQAXABkAGUAbQBvAF8AMAAxAF8AYgByAGEAYwBrAGUAdAAuAFMATABEAFAAUgBUAAmA//7/D2QAZQBtAG8AXwAwADEAXwBiAHIAYQBjAGsAZQB0AAIAAK+NkGr//v8A//7/AP/+/wAAAAAAAAAAAAAAAAAAAAAAAAD//v8HRABlAGYAYQB1AGwAdAAAAAAAAAAAAAAAAAAAAAAAIgAAALuNkGoCAAAAA4AAAAWACAAiAAAAu42QagEAAAD//wEAFABtb0VuZEZhY2VTdXJmSWRSZXBfYwAABYAIACIAAAC7jZBqAQAAAAAAAAAOgAAABYAIACIAAAC7jZBqAAAAAAAAAAAAAAAAAAAAADhKAAAAAAAA"
      },
      "semantic": {
        "component_path": [],
        "feature_ancestry": [],
        "feature_type_names": [],
        "geometry_type": "line_edge",
        "body_name": "MountingHole",
        "measurements": {
          "point_m": [
            0.1,
            0.0,
            0.004
          ],
          "direction": [
            0.0,
            0.0,
            -1.0
          ],
          "length_m": 0.008
        },
        "signature": "fb0a7daa7ef651ae7fb6",
        "tolerance": {
          "linear_m": 1e-06,
          "angular_rad": 1e-06,
          "relative": 0.0001
        }
      },
      "warnings": []
    },
    {
      "ref_version": 1,
      "kind": "edge",
      "label": "",
      "document": {
        "path": "C:\\projects\\cad-mcp-comparisons\\solidworks-mcp\\demo-output\\demo_01_bracket.SLDPRT",
        "title": "demo_01_bracket.SLDPRT",
        "configuration": "Default"
      },
      "persistent": {
        "scheme": "GetPersistReference3",
        "data_b64": "OEoAAAMAAAD//v8AAAAAAP//AQALAG1vRWRnZVJlZl9jAQAAAAAAAAAEAAAAAAMAAAAAAAB9w5QlrUmyVH3DlCWtSbJUAAD//wEAFwBtb0Zyb21Ta3RFbnRTdXJmSWRSZXBfYwAA//8BAAYAbW9GUl9j//8BAA0AbW9FeHRPYmplY3RfY///AQARAG1vQ1N0cmluZ0hhbmRsZV9j//7/UUMAOgBcAHAAcgBvAGoAZQBjAHQAcwBcAGMAYQBkAC0AbQBjAHAALQBjAG8AbQBwAGEAcgBpAHMAbwBuAHMAXABzAG8AbABpAGQAdwBvAHIAawBzAC0AbQBjAHAAXABkAGUAbQBvAC0AbwB1AHQAcAB1AHQAXABkAGUAbQBvAF8AMAAxAF8AYgByAGEAYwBrAGUAdAAuAFMATABEAFAAUgBUAAmA//7/D2QAZQBtAG8AXwAwADEAXwBiAHIAYQBjAGsAZQB0AAIAAK+NkGr//v8A//7/AP/+/wAAAAAAAAAAAAAAAAAAAAAAAAD//v8HRABlAGYAYQB1AGwAdAAAAAAAAAAAAAAAAAAAAAAAIgAAALuNkGoDAAAAA4AAAAWACAAiAAAAu42QagIAAAD//wEAFABtb0VuZEZhY2VTdXJmSWRSZXBfYwAABYAIACIAAAC7jZBqAQAAAAAAAAAOgAAABYAIACIAAAC7jZBqAAAAAAAAAAAAAAAAAAAAADhKAAAAAAAA"
      },
      "semantic": {
        "component_path": [],
        "feature_ancestry": [],
        "feature_type_names": [],
        "geometry_type": "line_edge",
        "body_name": "MountingHole",
        "measurements": {
          "point_m": [
            0.1,
            0.06,
            0.004
          ],
          "direction": [
            0.0,
            0.0,
            -1.0
          ],
          "length_m": 0.008
        },
        "signature": "dffc3bba52c62dd6300a",
        "tolerance": {
          "linear_m": 1e-06,
          "angular_rad": 1e-06,
          "relative": 0.0001
        }
      },
      "warnings": []
    },
    {
      "ref_version": 1,
      "kind": "edge",
      "label": "",
      "document": {
        "path": "C:\\projects\\cad-mcp-comparisons\\solidworks-mcp\\demo-output\\demo_01_bracket.SLDPRT",
        "title": "demo_01_bracket.SLDPRT",
        "configuration": "Default"
      },
      "persistent": {
        "scheme": "GetPersistReference3",
        "data_b64": "OEoAAAMAAAD//v8AAAAAAP//AQALAG1vRWRnZVJlZl9jAQAAAAAAAAAEAAAAAAMAAAAAAAB9w5QlrUmyVH3DlCWtSbJUAAD//wEAFwBtb0Zyb21Ta3RFbnRTdXJmSWRSZXBfYwAA//8BAAYAbW9GUl9j//8BAA0AbW9FeHRPYmplY3RfY///AQARAG1vQ1N0cmluZ0hhbmRsZV9j//7/UUMAOgBcAHAAcgBvAGoAZQBjAHQAcwBcAGMAYQBkAC0AbQBjAHAALQBjAG8AbQBwAGEAcgBpAHMAbwBuAHMAXABzAG8AbABpAGQAdwBvAHIAawBzAC0AbQBjAHAAXABkAGUAbQBvAC0AbwB1AHQAcAB1AHQAXABkAGUAbQBvAF8AMAAxAF8AYgByAGEAYwBrAGUAdAAuAFMATABEAFAAUgBUAAmA//7/D2QAZQBtAG8AXwAwADEAXwBiAHIAYQBjAGsAZQB0AAIAAK+NkGr//v8A//7/AP/+/wAAAAAAAAAAAAAAAAAAAAAAAAD//v8HRABlAGYAYQB1AGwAdAAAAAAAAAAAAAAAAAAAAAAAIgAAALuNkGoEAAAAA4AAAAWACAAiAAAAu42QagMAAAD//wEAFABtb0VuZEZhY2VTdXJmSWRSZXBfYwAABYAIACIAAAC7jZBqAQAAAAAAAAAOgAAABYAIACIAAAC7jZBqAAAAAAAAAAAAAAAAAAAAADhKAAAAAAAA"
      },
      "semantic": {
        "component_path": [],
        "feature_ancestry": [],
        "feature_type_names": [],
        "geometry_type": "line_edge",
        "body_name": "MountingHole",
        "measurements": {
          "point_m": [
            0.0,
            0.06,
            0.004
          ],
          "direction": [
            0.0,
            0.0,
            -1.0
          ],
          "length_m": 0.008
        },
        "signature": "bbedfb64eeb8ab177a37",
        "tolerance": {
          "linear_m": 1e-06,
          "angular_rad": 1e-06,
          "relative": 0.0001
        }
      },
      "warnings": []
    }
  ],
  "radius": 5.0
}
```

```json
{
  "edges_selected": 4,
  "volume_mm3_before": 46905.21779207701,
  "volume_mm3_after": 46733.53632279497,
  "verification": {
    "read_back": true,
    "before": {
      "body_count": 1,
      "volume_m3": 4.6905217792077015e-05,
      "volume_mm3": 46905.21779207701,
      "surface_area_m2": 0.014949808816457421,
      "surface_area_mm2": 14949.808816457422,
      "face_count": 10,
      "edge_count": 20,
      "feature_count": 22
    },
    "after": {
      "body_count": 1,
      "volume_m3": 4.6733536322794974e-05,
      "volume_mm3": 46733.53632279497,
      "surface_area_m2": 0.014838215861424099,
      "surface_area_mm2": 14838.2158614241,
      "face_count": 14,
      "edge_count": 32,
      "feature_count": 23
    },
    "checks": [
      {
        "name": "feature_created",
        "passed": true,
        "detail": "Fillet1"
      },
      {
        "name": "geometry_changed",
        "passed": true,
        "detail": "faces 10 -> 14, volume 46905.218 -> 46733.536 mm\u00b3"
      },
      {
        "name": "feature_has_no_error",
        "passed": true,
        "detail": "0"
      }
    ]
  }
}
```

### 21. `sw_feature_list` - ok

The finished tree, with every feature's error code read back.

```json
{}
```

```json
{
  "count": 23
}
```

### 22. `sw_body_list` - ok

```json
{}
```

```json
{
  "count": 1,
  "bodies": [
    {
      "name": "Fillet1",
      "type": "solidbody",
      "visible": true,
      "material": "",
      "face_count": 14,
      "edge_count": 32,
      "bounding_box_m": [
        0.0,
        0.0,
        0.0,
        0.1,
        0.06,
        0.008
      ],
      "owning_features": [
        "HolePattern",
        "BasePlate",
        "MountingHole",
        "Fillet1"
      ],
      "center_of_mass_m": [
        0.05,
        0.03,
        0.004
      ],
      "volume_m3": 4.6733536322794974e-05,
      "surface_area_m2": 0.014838215861424099,
      "mass_kg": 4.6733536322794974e-05
    }
  ]
}
```

### 23. `sw_doc_save` - ok

overwrite='allow' is the one save path that needs confirmation.

```json
{
  "output_path": "C:\\projects\\cad-mcp-comparisons\\solidworks-mcp\\demo-output\\demo_01_bracket.SLDPRT",
  "overwrite": "allow",
  "confirm": true
}
```

```json
{
  "saved_path": "C:\\projects\\cad-mcp-comparisons\\solidworks-mcp\\demo-output\\demo_01_bracket.SLDPRT"
}
```

### 24. `sw_doc_new` - ok

```json
{
  "doc_type": "part"
}
```

### 25. `sw_doc_save` - ok

```json
{
  "output_path": "C:\\projects\\cad-mcp-comparisons\\solidworks-mcp\\demo-output\\demo_02_shaft.SLDPRT"
}
```

```json
{
  "saved_path": "C:\\projects\\cad-mcp-comparisons\\solidworks-mcp\\demo-output\\demo_02_shaft.SLDPRT"
}
```

### 26. `sw_sketch_start` - ok

```json
{
  "on": {
    "standard_plane": "front"
  }
}
```

```json
{
  "sketch_name": "Sketch1"
}
```

### 27. `sw_sketch_add_geometry` - ok

A closed profile plus the axis centerline, in one COM round trip.

```json
{
  "entities": [
    {
      "type": "centerline",
      "start": [
        0,
        0
      ],
      "end": [
        70,
        0
      ]
    },
    {
      "type": "line",
      "start": [
        0,
        0
      ],
      "end": [
        0,
        15
      ]
    },
    {
      "type": "line",
      "start": [
        0,
        15
      ],
      "end": [
        40,
        15
      ]
    },
    {
      "type": "line",
      "start": [
        40,
        15
      ],
      "end": [
        40,
        10
      ]
    },
    {
      "type": "line",
      "start": [
        40,
        10
      ],
      "end": [
        70,
        10
      ]
    },
    {
      "type": "line",
      "start": [
        70,
        10
      ],
      "end": [
        70,
        0
      ]
    },
    {
      "type": "line",
      "start": [
        70,
        0
      ],
      "end": [
        0,
        0
      ]
    }
  ]
}
```

```json
{
  "created": [
    {
      "index": 1,
      "requested_type": "centerline",
      "sketch_local_id": "0:1",
      "type": "line",
      "construction": true,
      "length_m": 0.07
    },
    {
      "index": 2,
      "requested_type": "line",
      "sketch_local_id": "1:2",
      "type": "line",
      "construction": false,
      "length_m": 0.015
    },
    {
      "index": 3,
      "requested_type": "line",
      "sketch_local_id": "2:3",
      "type": "line",
      "construction": false,
      "length_m": 0.04
    },
    {
      "index": 4,
      "requested_type": "line",
      "sketch_local_id": "3:4",
      "type": "line",
      "construction": false,
      "length_m": 0.004999999999999999
    },
    {
      "index": 5,
      "requested_type": "line",
      "sketch_local_id": "4:5",
      "type": "line",
      "construction": false,
      "length_m": 0.030000000000000006
    },
    {
      "index": 6,
      "requested_type": "line",
      "sketch_local_id": "5:6",
      "type": "line",
      "construction": false,
      "length_m": 0.01
    },
    {
      "index": 7,
      "requested_type": "line",
      "sketch_local_id": "6:7",
      "type": "line",
      "construction": false,
      "length_m": 0.07
    }
  ],
  "failed": []
}
```

### 28. `sw_sketch_exit` - ok

```json
{}
```

```json
{
  "sketch_name": "Sketch1"
}
```

### 29. `sw_feature_revolve` - ok

Two cylinders: pi*(15^2*40 + 10^2*30) = 37699.1 mm3.

```json
{
  "angle": 360,
  "name": "Shaft"
}
```

```json
{
  "feature_name": "Shaft",
  "body_count_after": 1,
  "volume_mm3_after": 37699.11184307752,
  "verification": {
    "read_back": true,
    "before": {
      "body_count": 0,
      "volume_m3": 0.0,
      "volume_mm3": 0.0,
      "surface_area_m2": 0.0,
      "surface_area_mm2": 0.0,
      "face_count": 0,
      "edge_count": 0,
      "feature_count": 18
    },
    "after": {
      "body_count": 1,
      "volume_m3": 3.7699111843077517e-05,
      "volume_mm3": 37699.11184307752,
      "surface_area_m2": 0.007068583470577034,
      "surface_area_mm2": 7068.583470577034,
      "face_count": 5,
      "edge_count": 4,
      "feature_count": 19
    },
    "checks": [
      {
        "name": "geometry_changed",
        "passed": true,
        "detail": "material was added: volume 0.000 -> 37699.112 mm\u00b3, bodies 0 -> 1"
      },
      {
        "name": "model_has_a_body",
        "passed": true,
        "detail": "1 solid body(ies)"
      }
    ]
  }
}
```

### 30. `sw_measure` - ok

```json
{}
```

```json
{
  "mass_properties": {
    "volume_m3": 3.7699111843077517e-05,
    "volume_mm3": 37699.11184307752,
    "surface_area_m2": 0.007068583470577034,
    "surface_area_mm2": 7068.583470577034,
    "mass_kg": 3.7699111843077517e-05,
    "density_kg_m3": 1.0,
    "center_of_mass_mm": [
      28.75,
      9.829857954380521e-17,
      5.4981733586795745e-17
    ]
  },
  "bounding_box": {
    "min_mm": [
      0.0,
      -15.0,
      -15.0
    ],
    "max_mm": [
      70.0,
      15.0,
      15.0
    ],
    "size_mm": [
      70.0,
      30.0,
      30.0
    ]
  },
  "topology": {
    "body_count": 1,
    "face_count": 5,
    "edge_count": 4,
    "feature_count": 19
  }
}
```

### 31. `sw_doc_save` - ok

```json
{
  "output_path": "C:\\projects\\cad-mcp-comparisons\\solidworks-mcp\\demo-output\\demo_02_shaft.SLDPRT",
  "overwrite": "allow",
  "confirm": true
}
```

```json
{
  "saved_path": "C:\\projects\\cad-mcp-comparisons\\solidworks-mcp\\demo-output\\demo_02_shaft.SLDPRT"
}
```

### 32. `sw_doc_new` - ok

```json
{
  "doc_type": "part"
}
```

### 33. `sw_doc_save` - ok

```json
{
  "output_path": "C:\\projects\\cad-mcp-comparisons\\solidworks-mcp\\demo-output\\demo_03_safety.SLDPRT"
}
```

```json
{
  "saved_path": "C:\\projects\\cad-mcp-comparisons\\solidworks-mcp\\demo-output\\demo_03_safety.SLDPRT"
}
```

### 34. `sw_doc_save` - refused: PATH_NOT_ALLOWED

SAFE-004: refused before the COM boundary, and the error names the env var.

```json
{
  "output_path": "C:\\Windows\\System32\\swmcp_should_never_exist.SLDPRT"
}
```

```json
{
  "code": "PATH_NOT_ALLOWED",
  "message": "Refusing to write 'C:\\\\Windows\\\\System32\\\\swmcp_should_never_exist.SLDPRT': the path is not under any allowed root.",
  "remediation": [
    "Choose an output path under one of the allowed roots listed in context.",
    "Or widen SWMCP_ALLOWED_ROOTS if this location is genuinely intended."
  ]
}
```

### 35. `sw_doc_list` - refused: INVALID_ARGUMENTS

SAFE-001: an unknown key is a typo, so it is an error rather than ignored.

```json
{
  "nope": 1
}
```

```json
{
  "code": "INVALID_ARGUMENTS",
  "context": {
    "errors": [
      {
        "type": "extra_forbidden",
        "loc": [
          "nope"
        ],
        "msg": "Extra inputs are not permitted",
        "input": 1
      }
    ]
  }
}
```

### 36. `sw_sketch_start` - ok

```json
{
  "on": {
    "standard_plane": "front"
  }
}
```

```json
{
  "sketch_name": "Sketch1"
}
```

### 37. `sw_sketch_add_geometry` - ok

```json
{
  "entities": [
    {
      "type": "rect_center",
      "center": [
        0,
        0
      ],
      "corner": [
        30,
        20
      ]
    }
  ]
}
```

```json
{
  "created": [
    {
      "index": 1,
      "requested_type": "rect_center",
      "sketch_local_id": "1:1",
      "type": "line",
      "construction": false,
      "length_m": 0.06
    },
    {
      "index": 1,
      "requested_type": "rect_center",
      "sketch_local_id": "2:2",
      "type": "line",
      "construction": false,
      "length_m": 0.04
    },
    {
      "index": 1,
      "requested_type": "rect_center",
      "sketch_local_id": "3:3",
      "type": "line",
      "construction": false,
      "length_m": 0.06
    },
    {
      "index": 1,
      "requested_type": "rect_center",
      "sketch_local_id": "4:4",
      "type": "line",
      "construction": false,
      "length_m": 0.04
    },
    {
      "index": 1,
      "requested_type": "rect_center",
      "sketch_local_id": "5:5",
      "type": "line",
      "construction": true,
      "length_m": 0.07211102550927981
    },
    {
      "index": 1,
      "requested_type": "rect_center",
      "sketch_local_id": "6:6",
      "type": "line",
      "construction": true,
      "length_m": 0.07211102550927981
    }
  ],
  "failed": []
}
```

### 38. `sw_sketch_exit` - ok

```json
{}
```

```json
{
  "sketch_name": "Sketch1"
}
```

### 39. `sw_feature_extrude_boss` - ok

```json
{
  "depth": "10mm",
  "name": "Block"
}
```

```json
{
  "feature_name": "Block",
  "volume_mm3_after": 23999.999999999996
}
```

### 40. `sw_doc_save` - ok

```json
{
  "output_path": "C:\\projects\\cad-mcp-comparisons\\solidworks-mcp\\demo-output\\demo_03_safety.SLDPRT",
  "overwrite": "allow",
  "confirm": true
}
```

```json
{
  "saved_path": "C:\\projects\\cad-mcp-comparisons\\solidworks-mcp\\demo-output\\demo_03_safety.SLDPRT"
}
```

### 41. `sw_doc_save` - ok

SAFE-008: the default policy versions rather than replacing a deliverable.

```json
{
  "output_path": "C:\\projects\\cad-mcp-comparisons\\solidworks-mcp\\demo-output\\demo_03_safety.SLDPRT",
  "save_as_copy": true
}
```

```json
{
  "saved_path": "C:\\projects\\cad-mcp-comparisons\\solidworks-mcp\\demo-output\\demo_03_safety_v002.SLDPRT"
}
```

### 42. `sw_checkpoint_create` - ok

SAFE-005: a snapshot that states by which method it was taken.

```json
{}
```

```json
{
  "checkpoint": {
    "method": "save_as_copy",
    "checkpoint_path": "C:\\projects\\cad-mcp-comparisons\\solidworks-mcp\\demo-output\\.checkpoints\\demo_03_safety_20260827_192035.SLDPRT",
    "source_path": "C:\\projects\\cad-mcp-comparisons\\solidworks-mcp\\demo-output\\demo_03_safety.SLDPRT",
    "reason": null,
    "created_utc": "2026-08-27T19:20:35.696745+00:00",
    "size_bytes": 44614
  }
}
```

### 43. `sw_measure` - ok

```json
{}
```

```json
{
  "mass_properties": {
    "volume_m3": 2.3999999999999997e-05,
    "volume_mm3": 23999.999999999996,
    "surface_area_m2": 0.006799999999999999,
    "surface_area_mm2": 6799.999999999999,
    "mass_kg": 2.3999999999999997e-05,
    "density_kg_m3": 1.0,
    "center_of_mass_mm": [
      -1.5440704767656508e-16,
      0.0,
      5.0
    ]
  }
}
```

### 44. `sw_feature_delete` - refused: CONFIRM_REQUIRED

SAFE-003: destructive, so it is refused without confirm - before any COM call.

```json
{
  "feature_name": "Block"
}
```

```json
{
  "code": "CONFIRM_REQUIRED",
  "remediation": [
    "Re-send the request with confirm=true once you are sure."
  ]
}
```

### 45. `sw_body_list` - ok

The body is still here; the refusal was real.

```json
{}
```

```json
{
  "count": 1
}
```

### 46. `sw_feature_delete` - ok

Now destroy it on purpose.

```json
{
  "feature_name": "Block",
  "confirm": true,
  "delete_children": true
}
```

```json
{
  "deleted": true,
  "verification": {
    "read_back": true,
    "before": {
      "feature_count": 19
    },
    "after": {
      "feature_count": 18
    },
    "checks": [
      {
        "name": "feature_removed",
        "passed": true,
        "detail": "Block is gone"
      },
      {
        "name": "tree_shrank",
        "passed": true,
        "detail": "19 -> 18 features"
      }
    ]
  }
}
```

### 47. `sw_body_list` - ok

```json
{}
```

```json
{
  "count": 0
}
```

### 48. `sw_doc_save` - ok

Persist the damage, so the rollback has something real to undo.

```json
{
  "output_path": "C:\\projects\\cad-mcp-comparisons\\solidworks-mcp\\demo-output\\demo_03_safety.SLDPRT",
  "overwrite": "allow",
  "confirm": true
}
```

```json
{
  "saved_path": "C:\\projects\\cad-mcp-comparisons\\solidworks-mcp\\demo-output\\demo_03_safety.SLDPRT"
}
```

### 49. `sw_checkpoint_restore` - ok

Restoring is itself reversible: it snapshots the current state first.

```json
{
  "checkpoint_path": "C:\\projects\\cad-mcp-comparisons\\solidworks-mcp\\demo-output\\.checkpoints\\demo_03_safety_20260827_192035.SLDPRT",
  "confirm": true
}
```

```json
{
  "reopened": true,
  "pre_restore_checkpoint": "C:\\projects\\cad-mcp-comparisons\\solidworks-mcp\\demo-output\\.checkpoints\\demo_03_safety_pre_restore_20260827_192044.SLDPRT"
}
```

### 50. `sw_measure` - ok

The proof: the model measures what it measured before the delete.

```json
{}
```

```json
{
  "mass_properties": {
    "volume_m3": 2.3999999999999997e-05,
    "volume_mm3": 23999.999999999996,
    "surface_area_m2": 0.006799999999999999,
    "surface_area_mm2": 6799.999999999999,
    "mass_kg": 2.3999999999999997e-05,
    "density_kg_m3": 1.0,
    "center_of_mass_mm": [
      -1.5440704767656508e-16,
      0.0,
      5.0
    ]
  }
}
```

### 51. `sw_checkpoint_list` - ok

```json
{}
```

### 52. `sw_audit_tail` - ok

SAFE-006: every non-read operation is on the append-only log.

```json
{
  "limit": 10
}
```

```json
{
  "entries": [
    {
      "timestamp": "2026-08-27T19:20:45.851073+00:00",
      "tool": "sw_checkpoint_restore",
      "ok": true,
      "destructive": true,
      "document": null,
      "args": {
        "checkpoint_path": "C:\\projects\\cad-mcp-comparisons\\solidworks-mcp\\demo-output\\.checkpoints\\demo_03_safety_20260827_192035.SLDPRT",
        "target_path": null,
        "confirm": true,
        "close_open_document": true,
        "reopen": true
      },
      "checkpoint_path": null,
      "checkpoint_method": "skipped",
      "error_code": null,
      "error_message": null,
      "duration_ms": 1989.6,
      "pid": 15324
    },
    {
      "timestamp": "2026-08-27T19:20:43.856797+00:00",
      "tool": "sw_doc_save",
      "ok": true,
      "destructive": false,
      "document": null,
      "args": {
        "document": {
          "path": null,
          "title": null
        },
        "output_path": "C:\\projects\\cad-mcp-comparisons\\solidworks-mcp\\demo-output\\demo_03_safety.SLDPRT",
        "overwrite": "allow",
        "save_as_copy": false,
        "confirm": true
      },
      "checkpoint_path": null,
      "checkpoint_method": null,
      "error_code": null,
      "error_message": null,
      "duration_ms": 460.67,
      "pid": 15324
    },
    {
      "timestamp": "2026-08-27T19:20:42.868292+00:00",
      "tool": "sw_feature_delete",
      "ok": true,
      "destructive": true,
      "document": null,
      "args": {
        "document": {
          "path": null,
          "title": null
        },
        "feature_name": "Block",
        "delete_children": true,
        "confirm": true
      },
      "checkpoint_path": "C:\\projects\\cad-mcp-comparisons\\solidworks-mcp\\demo-output\\.checkpoints\\demo_03_safety_20260827_192040.SLDPRT",
      "checkpoint_method": "save_as_copy",
      "error_code": null,
      "error_message": null,
      "duration_ms": 2488.7,
      "pid": 15324
    },
    {
      "timestamp": "2026-08-27T19:20:38.925989+00
... (truncated; the full payload is in demo-log.json)
```

### 53. `sw_doc_close` - ok

Addressed by title; never 'whatever happens to be active'.

```json
{
  "document": {
    "title": "demo_01_bracket.SLDPRT"
  },
  "save_first": "discard",
  "confirm": true
}
```

### 54. `sw_doc_close` - ok

Addressed by title; never 'whatever happens to be active'.

```json
{
  "document": {
    "title": "demo_02_shaft.SLDPRT"
  },
  "save_first": "discard",
  "confirm": true
}
```

### 55. `sw_doc_close` - ok

Addressed by title; never 'whatever happens to be active'.

```json
{
  "document": {
    "title": "demo_03_safety.SLDPRT"
  },
  "save_first": "discard",
  "confirm": true
}
```

