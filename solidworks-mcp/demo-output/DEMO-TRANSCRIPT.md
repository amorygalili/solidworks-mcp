# solidworks-mcp demo transcript

Produced by `uv run python scripts/demo_build.py`, which spawns `python -m swmcp`
over stdio and speaks MCP to it - the same path any MCP client takes.

- tool calls: **113**
- behaved as expected: **113/113**

## Files written

- `demo_01_bracket.SLDPRT` - 74,438 bytes
- `demo_02_shaft.SLDPRT` - 63,219 bytes
- `demo_03_safety.SLDPRT` - 43,882 bytes
- `demo_04_parametric.SLDPRT` - 91,765 bytes
- `demo_05_atomic.SLDPRT` - 48,829 bytes
- `demo_06_datum.SLDPRT` - 73,924 bytes
- `demo_01_bracket.png` - 145,097 bytes
- `demo_06_datum.png` - 173,807 bytes
- `demo_01_bracket.step` - 45,575 bytes
- `demo_01_bracket.STL` - 37,484 bytes
- `demo_04_parameters.csv` - 450 bytes
- `demo_03_safety_v002.SLDPRT` - 44,409 bytes (written by the versioning policy)

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
    "active_document": null
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
    "thread_ident": 28276,
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
          "p50": 13.23,
          "p95": 50.54
        },
        "sw_system_info": {
          "p50": 397.23,
          "p95": 397.23
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
    "api_table": {
      "typelib_iid": "{83A33D31-27C5-11CE-BFD4-00400513BB57}",
      "typelib_major": 34,
      "interface_count": 29,
      "member_count": 3999
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
  "matched": 2,
  "returned": 2,
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
      "data_b64": "OEoAAAMAAAD//v8AAAAAAP//AQALAG1vRmFjZVJlZl9jAQAAAAAAAAAGAAAAAAIAAAAAAAB9w5QlrUmyVH3DlCWtSbJUAAD//wEAFABtb0VuZEZhY2VTdXJmSWRSZXBfYwAA//8BAAYAbW9GUl9j//8BAA0AbW9FeHRPYmplY3RfY///AQARAG1vQ1N0cmluZ0hhbmRsZV9j//7/UUMAOgBcAHAAcgBvAGoAZQBjAHQAcwBcAGMAYQBkAC0AbQBjAHAALQBjAG8AbQBwAGEAcgBpAHMAbwBuAHMAXABzAG8AbABpAGQAdwBvAHIAawBzAC0AbQBjAHAAXABkAGUAbQBvAC0AbwB1AHQAcAB1AHQAXABkAGUAbQBvAF8AMAAxAF8AYgByAGEAYwBrAGUAdAAuAFMATABEAFAAUgBUAAmA//7/D2QAZQBtAG8AXwAwADEAXwBiAHIAYQBjAGsAZQB0AAIAAKnwkWr//v8A//7/AP/+/wAAAAAAAAAAAAAAAAAAAAAAAAD//v8HRABlAGYAYQB1AGwAdAAAAAAAAAAAAAAAAAAAAAAAIgAAAMbwkWoBAAAAAAAAAP//AQAXAG1vRnJvbVNrdEVudFN1cmZJZFJlcF9jAAAFgAgAIgAAAMbwkWoEAAAADIAAAAWACAAiAAAAxvCRagEAAAAMgAAABYAIACIAAADG8JFqAgAAAAyAAAAFgAgAIgAAAMbwkWoDAAAAAAAAAAAAAAAAADhKAAAAAAAAAAAAAA=="
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
      "data_b64": "OEoAAAMAAAD//v8AAAAAAP//AQALAG1vRWRnZVJlZl9jAQAAAAAAAAAEAAAAAAMAAAAAAAB9w5QlrUmyVH3DlCWtSbJUAAD//wEAFABtb0VuZEZhY2VTdXJmSWRSZXBfYwAA//8BAAYAbW9GUl9j//8BAA0AbW9FeHRPYmplY3RfY///AQARAG1vQ1N0cmluZ0hhbmRsZV9j//7/UUMAOgBcAHAAcgBvAGoAZQBjAHQAcwBcAGMAYQBkAC0AbQBjAHAALQBjAG8AbQBwAGEAcgBpAHMAbwBuAHMAXABzAG8AbABpAGQAdwBvAHIAawBzAC0AbQBjAHAAXABkAGUAbQBvAC0AbwB1AHQAcAB1AHQAXABkAGUAbQBvAF8AMAAxAF8AYgByAGEAYwBrAGUAdAAuAFMATABEAFAAUgBUAAmA//7/D2QAZQBtAG8AXwAwADEAXwBiAHIAYQBjAGsAZQB0AAIAAKnwkWr//v8A//7/AP/+/wAAAAAAAAAAAAAAAAAAAAAAAAD//v8HRABlAGYAYQB1AGwAdAAAAAAAAAAAAAAAAAAAAAAAIgAAAMbwkWoBAAAAAAAAAP//AQAXAG1vRnJvbVNrdEVudFN1cmZJZFJlcF9jAAAFgAgAIgAAAMbwkWoBAAAADIAAAAWACAAiAAAAxvCRagQAAAAMgAAABYAIACIAAADG8JFqAgAAAAAAAAAAAAAAOEoAAAAAAAA="
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
      "data_b64": "OEoAAAMAAAD//v8AAAAAAP//AQALAG1vRWRnZVJlZl9jAQAAAAAAAAAEAAAAAAMAAAAAAAB9w5QlrUmyVH3DlCWtSbJUAAD//wEAFABtb0VuZEZhY2VTdXJmSWRSZXBfYwAA//8BAAYAbW9GUl9j//8BAA0AbW9FeHRPYmplY3RfY///AQARAG1vQ1N0cmluZ0hhbmRsZV9j//7/UUMAOgBcAHAAcgBvAGoAZQBjAHQAcwBcAGMAYQBkAC0AbQBjAHAALQBjAG8AbQBwAGEAcgBpAHMAbwBuAHMAXABzAG8AbABpAGQAdwBvAHIAawBzAC0AbQBjAHAAXABkAGUAbQBvAC0AbwB1AHQAcAB1AHQAXABkAGUAbQBvAF8AMAAxAF8AYgByAGEAYwBrAGUAdAAuAFMATABEAFAAUgBUAAmA//7/D2QAZQBtAG8AXwAwADEAXwBiAHIAYQBjAGsAZQB0AAIAAKnwkWr//v8A//7/AP/+/wAAAAAAAAAAAAAAAAAAAAAAAAD//v8HRABlAGYAYQB1AGwAdAAAAAAAAAAAAAAAAAAAAAAAIgAAAMbwkWoBAAAAAAAAAP//AQAXAG1vRnJvbVNrdEVudFN1cmZJZFJlcF9jAAAFgAgAIgAAAMbwkWoCAAAADIAAAAWACAAiAAAAxvCRagEAAAAMgAAABYAIACIAAADG8JFqAwAAAAAAAAAAAAAAOEoAAAAAAAA="
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
        "data_b64": "OEoAAAMAAAD//v8AAAAAAP//AQALAG1vRWRnZVJlZl9jAQAAAAAAAAAEAAAAAAMAAAAAAAB9w5QlrUmyVH3DlCWtSbJUAAD//wEAFwBtb0Zyb21Ta3RFbnRTdXJmSWRSZXBfYwAA//8BAAYAbW9GUl9j//8BAA0AbW9FeHRPYmplY3RfY///AQARAG1vQ1N0cmluZ0hhbmRsZV9j//7/UUMAOgBcAHAAcgBvAGoAZQBjAHQAcwBcAGMAYQBkAC0AbQBjAHAALQBjAG8AbQBwAGEAcgBpAHMAbwBuAHMAXABzAG8AbABpAGQAdwBvAHIAawBzAC0AbQBjAHAAXABkAGUAbQBvAC0AbwB1AHQAcAB1AHQAXABkAGUAbQBvAF8AMAAxAF8AYgByAGEAYwBrAGUAdAAuAFMATABEAFAAUgBUAAmA//7/D2QAZQBtAG8AXwAwADEAXwBiAHIAYQBjAGsAZQB0AAIAAKnwkWr//v8A//7/AP/+/wAAAAAAAAAAAAAAAAAAAAAAAAD//v8HRABlAGYAYQB1AGwAdAAAAAAAAAAAAAAAAAAAAAAAIgAAAMbwkWoBAAAAA4AAAAWACAAiAAAAxvCRagQAAAD//wEAFABtb0VuZEZhY2VTdXJmSWRSZXBfYwAABYAIACIAAADG8JFqAQAAAAAAAAAOgAAABYAIACIAAADG8JFqAAAAAAAAAAAAAAAAAAAAADhKAAAAAAAA"
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
        "data_b64": "OEoAAAMAAAD//v8AAAAAAP//AQALAG1vRWRnZVJlZl9jAQAAAAAAAAAEAAAAAAMAAAAAAAB9w5QlrUmyVH3DlCWtSbJUAAD//wEAFwBtb0Zyb21Ta3RFbnRTdXJmSWRSZXBfYwAA//8BAAYAbW9GUl9j//8BAA0AbW9FeHRPYmplY3RfY///AQARAG1vQ1N0cmluZ0hhbmRsZV9j//7/UUMAOgBcAHAAcgBvAGoAZQBjAHQAcwBcAGMAYQBkAC0AbQBjAHAALQBjAG8AbQBwAGEAcgBpAHMAbwBuAHMAXABzAG8AbABpAGQAdwBvAHIAawBzAC0AbQBjAHAAXABkAGUAbQBvAC0AbwB1AHQAcAB1AHQAXABkAGUAbQBvAF8AMAAxAF8AYgByAGEAYwBrAGUAdAAuAFMATABEAFAAUgBUAAmA//7/D2QAZQBtAG8AXwAwADEAXwBiAHIAYQBjAGsAZQB0AAIAAKnwkWr//v8A//7/AP/+/wAAAAAAAAAAAAAAAAAAAAAAAAD//v8HRABlAGYAYQB1AGwAdAAAAAAAAAAAAAAAAAAAAAAAIgAAAMbwkWoCAAAAA4AAAAWACAAiAAAAxvCRagEAAAD//wEAFABtb0VuZEZhY2VTdXJmSWRSZXBfYwAABYAIACIAAADG8JFqAQAAAAAAAAAOgAAABYAIACIAAADG8JFqAAAAAAAAAAAAAAAAAAAAADhKAAAAAAAA"
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
        "data_b64": "OEoAAAMAAAD//v8AAAAAAP//AQALAG1vRWRnZVJlZl9jAQAAAAAAAAAEAAAAAAMAAAAAAAB9w5QlrUmyVH3DlCWtSbJUAAD//wEAFwBtb0Zyb21Ta3RFbnRTdXJmSWRSZXBfYwAA//8BAAYAbW9GUl9j//8BAA0AbW9FeHRPYmplY3RfY///AQARAG1vQ1N0cmluZ0hhbmRsZV9j//7/UUMAOgBcAHAAcgBvAGoAZQBjAHQAcwBcAGMAYQBkAC0AbQBjAHAALQBjAG8AbQBwAGEAcgBpAHMAbwBuAHMAXABzAG8AbABpAGQAdwBvAHIAawBzAC0AbQBjAHAAXABkAGUAbQBvAC0AbwB1AHQAcAB1AHQAXABkAGUAbQBvAF8AMAAxAF8AYgByAGEAYwBrAGUAdAAuAFMATABEAFAAUgBUAAmA//7/D2QAZQBtAG8AXwAwADEAXwBiAHIAYQBjAGsAZQB0AAIAAKnwkWr//v8A//7/AP/+/wAAAAAAAAAAAAAAAAAAAAAAAAD//v8HRABlAGYAYQB1AGwAdAAAAAAAAAAAAAAAAAAAAAAAIgAAAMbwkWoDAAAAA4AAAAWACAAiAAAAxvCRagIAAAD//wEAFABtb0VuZEZhY2VTdXJmSWRSZXBfYwAABYAIACIAAADG8JFqAQAAAAAAAAAOgAAABYAIACIAAADG8JFqAAAAAAAAAAAAAAAAAAAAADhKAAAAAAAA"
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
        "data_b64": "OEoAAAMAAAD//v8AAAAAAP//AQALAG1vRWRnZVJlZl9jAQAAAAAAAAAEAAAAAAMAAAAAAAB9w5QlrUmyVH3DlCWtSbJUAAD//wEAFwBtb0Zyb21Ta3RFbnRTdXJmSWRSZXBfYwAA//8BAAYAbW9GUl9j//8BAA0AbW9FeHRPYmplY3RfY///AQARAG1vQ1N0cmluZ0hhbmRsZV9j//7/UUMAOgBcAHAAcgBvAGoAZQBjAHQAcwBcAGMAYQBkAC0AbQBjAHAALQBjAG8AbQBwAGEAcgBpAHMAbwBuAHMAXABzAG8AbABpAGQAdwBvAHIAawBzAC0AbQBjAHAAXABkAGUAbQBvAC0AbwB1AHQAcAB1AHQAXABkAGUAbQBvAF8AMAAxAF8AYgByAGEAYwBrAGUAdAAuAFMATABEAFAAUgBUAAmA//7/D2QAZQBtAG8AXwAwADEAXwBiAHIAYQBjAGsAZQB0AAIAAKnwkWr//v8A//7/AP/+/wAAAAAAAAAAAAAAAAAAAAAAAAD//v8HRABlAGYAYQB1AGwAdAAAAAAAAAAAAAAAAAAAAAAAIgAAAMbwkWoEAAAAA4AAAAWACAAiAAAAxvCRagMAAAD//wEAFABtb0VuZEZhY2VTdXJmSWRSZXBfYwAABYAIACIAAADG8JFqAQAAAAAAAAAOgAAABYAIACIAAADG8JFqAAAAAAAAAAAAAAAAAAAAADhKAAAAAAAA"
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
  "volume_mm3_before": 46905.21779207703,
  "volume_mm3_after": 46733.53632279498,
  "verification": {
    "read_back": true,
    "before": {
      "body_count": 1,
      "volume_m3": 4.690521779207703e-05,
      "volume_mm3": 46905.21779207703,
      "surface_area_m2": 0.014949808816457421,
      "surface_area_mm2": 14949.808816457422,
      "face_count": 10,
      "edge_count": 20,
      "feature_count": 22
    },
    "after": {
      "body_count": 1,
      "volume_m3": 4.673353632279498e-05,
      "volume_mm3": 46733.53632279498,
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

### 24. `sw_view_capture` - ok

VIEW-004: the one piece of evidence JSON cannot carry. Open it and look.

```json
{
  "output_path": "C:\\projects\\cad-mcp-comparisons\\solidworks-mcp\\demo-output\\demo_01_bracket.png",
  "orientation": "isometric",
  "width": 1280,
  "height": 960
}
```

```json
{
  "saved_path": "C:\\projects\\cad-mcp-comparisons\\solidworks-mcp\\demo-output\\demo_01_bracket.png",
  "format": "png",
  "requested_size": [
    1280,
    960
  ],
  "actual_size": [
    1248,
    771
  ],
  "method": "Extension.SaveAs"
}
```

### 25. `sw_export` - ok

IO-002: the written file is checked for its own ISO-10303-21 header.

```json
{
  "output_path": "C:\\projects\\cad-mcp-comparisons\\solidworks-mcp\\demo-output\\demo_01_bracket.step",
  "step_protocol": "ap214"
}
```

```json
{
  "saved_path": "C:\\projects\\cad-mcp-comparisons\\solidworks-mcp\\demo-output\\demo_01_bracket.step",
  "format": "step",
  "signature_verified": true,
  "signature_detail": "STEP part 21 header found",
  "settings": {
    "step_protocol": "ap214"
  }
}
```

### 26. `sw_export` - ok

IO-003: a binary STL's triangle count is checked against its file size.

```json
{
  "output_path": "C:\\projects\\cad-mcp-comparisons\\solidworks-mcp\\demo-output\\demo_01_bracket.stl",
  "stl_binary": true,
  "stl_quality": "fine"
}
```

```json
{
  "saved_path": "C:\\projects\\cad-mcp-comparisons\\solidworks-mcp\\demo-output\\demo_01_bracket.stl",
  "signature_verified": true,
  "signature_detail": "binary STL: 748 triangles, and 84 + 50*n == 37484 bytes",
  "size_bytes": 37484
}
```

### 27. `sw_doc_new` - ok

```json
{
  "doc_type": "part"
}
```

### 28. `sw_doc_save` - ok

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

### 29. `sw_sketch_start` - ok

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

### 30. `sw_sketch_add_geometry` - ok

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

### 31. `sw_sketch_exit` - ok

```json
{}
```

```json
{
  "sketch_name": "Sketch1"
}
```

### 32. `sw_feature_revolve` - ok

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

### 33. `sw_measure` - ok

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

### 34. `sw_doc_save` - ok

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

### 35. `sw_doc_new` - ok

```json
{
  "doc_type": "part"
}
```

### 36. `sw_doc_save` - ok

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

### 37. `sw_doc_save` - refused: PATH_NOT_ALLOWED

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

### 38. `sw_doc_list` - refused: INVALID_ARGUMENTS

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
        "loc": [
          "nope"
        ],
        "type": "extra_forbidden",
        "msg": "Extra inputs are not permitted",
        "input": 1
      }
    ]
  }
}
```

### 39. `sw_sketch_start` - ok

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

### 40. `sw_sketch_add_geometry` - ok

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

### 41. `sw_sketch_exit` - ok

```json
{}
```

```json
{
  "sketch_name": "Sketch1"
}
```

### 42. `sw_feature_extrude_boss` - ok

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

### 43. `sw_doc_save` - ok

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

### 44. `sw_doc_save` - ok

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

### 45. `sw_checkpoint_create` - ok

SAFE-005: a snapshot that states by which method it was taken.

```json
{}
```

```json
{
  "checkpoint": {
    "method": "save_as_copy",
    "checkpoint_path": "C:\\projects\\cad-mcp-comparisons\\solidworks-mcp\\demo-output\\.checkpoints\\demo_03_safety_20260828_203717.SLDPRT",
    "source_path": "C:\\projects\\cad-mcp-comparisons\\solidworks-mcp\\demo-output\\demo_03_safety.SLDPRT",
    "reason": null,
    "created_utc": "2026-08-28T20:37:18.221882+00:00",
    "size_bytes": 43882
  }
}
```

### 46. `sw_measure` - ok

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

### 47. `sw_feature_delete` - refused: CONFIRM_REQUIRED

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

### 48. `sw_body_list` - ok

The body is still here; the refusal was real.

```json
{}
```

```json
{
  "count": 1
}
```

### 49. `sw_feature_delete` - ok

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

### 50. `sw_body_list` - ok

```json
{}
```

```json
{
  "count": 0
}
```

### 51. `sw_doc_save` - ok

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

### 52. `sw_checkpoint_restore` - ok

Restoring is itself reversible: it snapshots the current state first.

```json
{
  "checkpoint_path": "C:\\projects\\cad-mcp-comparisons\\solidworks-mcp\\demo-output\\.checkpoints\\demo_03_safety_20260828_203717.SLDPRT",
  "confirm": true
}
```

```json
{
  "reopened": true,
  "pre_restore_checkpoint": "C:\\projects\\cad-mcp-comparisons\\solidworks-mcp\\demo-output\\.checkpoints\\demo_03_safety_pre_restore_20260828_203741.SLDPRT"
}
```

### 53. `sw_measure` - ok

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
      0.0,
      0.0,
      5.0
    ]
  }
}
```

### 54. `sw_checkpoint_list` - ok

```json
{}
```

### 55. `sw_audit_tail` - ok

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
      "timestamp": "2026-08-28T20:37:44.382802+00:00",
      "tool": "sw_checkpoint_restore",
      "ok": true,
      "destructive": true,
      "document": null,
      "args": {
        "checkpoint_path": "C:\\projects\\cad-mcp-comparisons\\solidworks-mcp\\demo-output\\.checkpoints\\demo_03_safety_20260828_203717.SLDPRT",
        "target_path": null,
        "confirm": true,
        "close_open_document": true,
        "reopen": true
      },
      "checkpoint_path": null,
      "checkpoint_method": "skipped",
      "error_code": null,
      "error_message": null,
      "duration_ms": 3754.42,
      "pid": 37388
    },
    {
      "timestamp": "2026-08-28T20:37:40.621527+00:00",
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
      "duration_ms": 978.29,
      "pid": 37388
    },
    {
      "timestamp": "2026-08-28T20:37:37.908547+00:00",
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
      "checkpoint_path": "C:\\projects\\cad-mcp-comparisons\\solidworks-mcp\\demo-output\\.checkpoints\\demo_03_safety_20260828_203730.SLDPRT",
      "checkpoint_method": "save_as_copy",
      "error_code": null,
      "error_message": null,
      "duration_ms": 7402.59,
      "pid": 37388
    },
    {
      "timestamp": "2026-08-28T20:37:26.444318+
... (truncated; the full payload is in demo-log.json)
```

### 56. `sw_doc_new` - ok

```json
{
  "doc_type": "part"
}
```

### 57. `sw_doc_save` - ok

```json
{
  "output_path": "C:\\projects\\cad-mcp-comparisons\\solidworks-mcp\\demo-output\\demo_04_parametric.SLDPRT"
}
```

```json
{
  "saved_path": "C:\\projects\\cad-mcp-comparisons\\solidworks-mcp\\demo-output\\demo_04_parametric.SLDPRT"
}
```

### 58. `sw_body_primitive` - ok

FEAT-014: an ordinary sketch and boss, checked against 80*50*20 mm3.

```json
{
  "kind": "box",
  "width": 80,
  "depth": 50,
  "height": 20,
  "name": "Body"
}
```

```json
{
  "kind": "box",
  "method": "extrude",
  "expected_volume_mm3": 80000.0,
  "volume_mm3_after": 80000.0,
  "volume_error_ratio": 0.0
}
```

### 59. `sw_body_primitive` - ok

A second primitive, placed clear of the first so both survive.

```json
{
  "kind": "cylinder",
  "radius": 12,
  "height": 30,
  "at": [
    0,
    45
  ],
  "name": "Boss"
}
```

```json
{
  "kind": "cylinder",
  "expected_volume_mm3": 13571.680263507906,
  "volume_mm3_after": 93571.68026350791
}
```

### 60. `sw_dimension_list` - ok

PAR-001: every driving dimension, sketch and feature alike, by name.

```json
{}
```

```json
{
  "unit": "mm",
  "dimensions": [
    {
      "name": "D1@Body@demo_04_parametric.Part",
      "owner": "Body",
      "value_m": 0.02,
      "driving": true,
      "applies_to_all_configurations": true,
      "tolerance_type": 0,
      "value_mm": 20.0
    },
    {
      "name": "D1@Boss@demo_04_parametric.Part",
      "owner": "Boss",
      "value_m": 0.03,
      "driving": true,
      "applies_to_all_configurations": true,
      "tolerance_type": 0,
      "value_mm": 30.0
    }
  ]
}
```

### 61. `sw_equation_set` - ok

PAR-002: a global variable now drives one of the box's dimensions.

```json
{
  "equations": [
    {
      "operation": "add",
      "name": "WallThickness",
      "expression": "20mm",
      "global_variable": true
    },
    {
      "operation": "add",
      "name": "D1@Body@demo_04_parametric.Part",
      "expression": "\"WallThickness\" * 1.5"
    }
  ]
}
```

```json
{
  "applied": 2,
  "failed": [],
  "status": {
    "code": -1,
    "code_note": "0 means the equations solved; the type library names no enum for this.",
    "disabled_count": 0,
    "automatic_solve_order": true,
    "automatic_rebuild": false,
    "linked_file": null
  },
  "circular_references": []
}
```

### 62. `sw_equation_list` - ok

Read the equations back, with what each one reads and any cycle.

```json
{}
```

```json
{
  "count": 2,
  "equations": [
    {
      "index": 1,
      "text": "\"D1@Body@demo_04_parametric.Part\" = \"WallThickness\" * 1.5",
      "name": "D1@Body@demo_04_parametric.Part",
      "expression": "\"WallThickness\" * 1.5",
      "value": 1.181102355,
      "global_variable": false,
      "suppressed": false,
      "reads": [
        "WallThickness"
      ]
    }
  ],
  "global_variables": [
    {
      "index": 0,
      "text": "\"WallThickness\" = 20mm",
      "name": "WallThickness",
      "expression": "20mm",
      "value": 0.78740157,
      "global_variable": true,
      "suppressed": false,
      "reads": []
    }
  ],
  "circular_references": []
}
```

### 63. `sw_equation_set` - ok

One value changed; the geometry follows.

```json
{
  "equations": [
    {
      "operation": "update",
      "name": "WallThickness",
      "expression": "30mm"
    }
  ]
}
```

```json
{
  "applied": 1,
  "failed": []
}
```

### 64. `sw_measure` - ok

The proof that the equation drove real geometry.

```json
{}
```

```json
{
  "mass_properties": {
    "volume_m3": 0.00019357167992750793,
    "volume_mm3": 193571.6799275079,
    "surface_area_m2": 0.022866725372978514,
    "surface_area_mm2": 22866.725372978515,
    "mass_kg": 0.00019357167992750793,
    "density_kg_m3": 1.0,
    "center_of_mass_mm": [
      -1.6398496435938887e-17,
      3.1550359643857555,
      21.974160633547072
    ]
  },
  "bounding_box": {
    "min_mm": [
      -40.0,
      -25.0,
      0.0
    ],
    "max_mm": [
      40.0,
      57.0,
      44.99999991599999
    ],
    "size_mm": [
      80.0,
      82.0,
      44.99999991599999
    ]
  }
}
```

### 65. `sw_config_create` - ok

PAR-003: a variant, confirmed by reading the configuration list back.

```json
{
  "name": "Heavy",
  "activate": true
}
```

```json
{
  "name": "Heavy",
  "count_before": 1,
  "count_after": 2,
  "active": "Heavy"
}
```

### 66. `sw_config_list` - ok

```json
{}
```

```json
{
  "count": 2,
  "active": "Heavy",
  "configurations": [
    {
      "name": "Default",
      "readable": true,
      "comment": "",
      "description": "Default",
      "alternate_name": "",
      "derived": false,
      "parent": null,
      "needs_rebuild": false,
      "suppress_new_features": true,
      "property_count": 0
    },
    {
      "name": "Heavy",
      "readable": true,
      "comment": "",
      "description": "Heavy",
      "alternate_name": "",
      "derived": false,
      "parent": null,
      "needs_rebuild": false,
      "suppress_new_features": false,
      "property_count": 0
    }
  ]
}
```

### 67. `sw_property_set` - ok

PAR-006: metadata a BOM would print, written and read back.

```json
{
  "properties": [
    {
      "name": "PartNumber",
      "value": "DEMO-004"
    },
    {
      "name": "Material",
      "value": "6061-T6"
    },
    {
      "name": "Revision",
      "value": "A"
    }
  ]
}
```

```json
{
  "written": [
    "PartNumber",
    "Material",
    "Revision"
  ],
  "failed": [],
  "verification": {
    "read_back": true,
    "before": {
      "property_count": 0,
      "names": []
    },
    "after": {
      "property_count": 3,
      "names": [
        "Material",
        "PartNumber",
        "Revision"
      ]
    },
    "checks": [
      {
        "name": "every_item_applied",
        "passed": true,
        "detail": "all items applied"
      },
      {
        "name": "written_values_read_back",
        "passed": true,
        "detail": "3 value(s) match what was sent"
      },
      {
        "name": "deleted_properties_are_gone",
        "passed": true,
        "detail": "deleted: []"
      }
    ]
  }
}
```

### 68. `sw_property_list` - ok

Raw and evaluated values, file level and per configuration.

```json
{
  "configuration": "*"
}
```

```json
{
  "count": 3,
  "file_properties": [
    {
      "name": "PartNumber",
      "raw": "DEMO-004",
      "evaluated": null,
      "type_code": 30,
      "type": "swCustomInfoText"
    },
    {
      "name": "Material",
      "raw": "6061-T6",
      "evaluated": null,
      "type_code": 30,
      "type": "swCustomInfoText"
    },
    {
      "name": "Revision",
      "raw": "A",
      "evaluated": null,
      "type_code": 30,
      "type": "swCustomInfoText"
    }
  ]
}
```

### 69. `sw_parameter_table_export` - ok

PAR-005: every parameter in one CSV, editable outside SOLIDWORKS.

```json
{
  "output_path": "C:\\projects\\cad-mcp-comparisons\\solidworks-mcp\\demo-output\\demo_04_parameters.csv"
}
```

```json
{
  "saved_path": "C:\\projects\\cad-mcp-comparisons\\solidworks-mcp\\demo-output\\demo_04_parameters.csv",
  "row_count": 7,
  "kinds": {
    "dimension": 2,
    "global_variable": 1,
    "equation": 1,
    "property": 3
  }
}
```

### 70. `sw_doc_save` - ok

```json
{
  "output_path": "C:\\projects\\cad-mcp-comparisons\\solidworks-mcp\\demo-output\\demo_04_parametric.SLDPRT",
  "overwrite": "allow",
  "confirm": true
}
```

```json
{
  "saved_path": "C:\\projects\\cad-mcp-comparisons\\solidworks-mcp\\demo-output\\demo_04_parametric.SLDPRT"
}
```

### 71. `sw_doc_new` - ok

```json
{
  "doc_type": "part"
}
```

### 72. `sw_doc_save` - ok

```json
{
  "output_path": "C:\\projects\\cad-mcp-comparisons\\solidworks-mcp\\demo-output\\demo_05_atomic.SLDPRT"
}
```

```json
{
  "saved_path": "C:\\projects\\cad-mcp-comparisons\\solidworks-mcp\\demo-output\\demo_05_atomic.SLDPRT"
}
```

### 73. `sw_body_primitive` - ok

```json
{
  "kind": "box",
  "width": 60,
  "depth": 40,
  "height": 20,
  "name": "Block"
}
```

```json
{
  "expected_volume_mm3": 47999.99999999999,
  "volume_mm3_after": 47999.99999999999
}
```

### 74. `sw_doc_save` - ok

A saved document is a checkpointable one, which is what rollback needs.

```json
{
  "output_path": "C:\\projects\\cad-mcp-comparisons\\solidworks-mcp\\demo-output\\demo_05_atomic.SLDPRT",
  "overwrite": "allow",
  "confirm": true
}
```

```json
{
  "saved_path": "C:\\projects\\cad-mcp-comparisons\\solidworks-mcp\\demo-output\\demo_05_atomic.SLDPRT"
}
```

### 75. `sw_measure` - ok

```json
{}
```

```json
{
  "mass_properties": {
    "volume_m3": 4.7999999999999994e-05,
    "volume_mm3": 47999.99999999999,
    "surface_area_m2": 0.008799999999999999,
    "surface_area_mm2": 8800.0,
    "mass_kg": 4.7999999999999994e-05,
    "density_kg_m3": 1.0,
    "center_of_mass_mm": [
      -1.5440704767656508e-16,
      0.0,
      10.0
    ]
  }
}
```

### 76. `sw_safe_execute` - ok

REV-006: a sequence whose invariants hold is kept.

```json
{
  "steps": [
    {
      "tool": "sw_feature_shell",
      "args": {
        "thickness": 2
      },
      "label": "hollow it"
    },
    {
      "tool": "sw_measure",
      "label": "check the result"
    }
  ],
  "invariants": {
    "body_count": 1,
    "volume_change": "decrease"
  },
  "confirm": true
}
```

```json
{
  "completed": 2,
  "invariants_held": true,
  "invariants_checked": [
    {
      "invariant": "body_count",
      "held": true,
      "wanted": 1,
      "found": 1
    },
    {
      "invariant": "volume_change",
      "held": true,
      "wanted": "decrease",
      "found": "47999.99999999999 -> 15743.99999999998 mm\u00b3"
    },
    {
      "invariant": "no_features_in_error",
      "held": true,
      "wanted": "no feature errors",
      "found": []
    },
    {
      "invariant": "no_rebuild_errors",
      "held": true,
      "wanted": "a clean rebuild",
      "found": []
    }
  ],
  "rolled_back": false
}
```

### 77. `sw_measure` - ok

The starting point the next sequence will be rolled back to.

```json
{}
```

```json
{
  "mass_properties": {
    "volume_m3": 1.5743999999999994e-05,
    "volume_mm3": 15743.999999999995,
    "surface_area_m2": 0.015776000000000002,
    "surface_area_mm2": 15776.000000000002,
    "mass_kg": 1.5743999999999994e-05,
    "density_kg_m3": 1.0,
    "center_of_mass_mm": [
      -8.406307038140529e-16,
      0.0,
      10.0
    ]
  }
}
```

### 78. `sw_safe_execute` - ok

The same machinery with an invariant it cannot meet: everything is undone.

```json
{
  "steps": [
    {
      "tool": "sw_feature_delete",
      "args": {
        "feature_name": "Block",
        "confirm": true,
        "delete_children": true
      },
      "label": "destroy the model"
    }
  ],
  "invariants": {
    "body_count": 1
  },
  "confirm": true
}
```

```json
{
  "completed": 1,
  "invariants_held": false,
  "rolled_back": true,
  "rollback": {
    "restored_from": "C:\\projects\\cad-mcp-comparisons\\solidworks-mcp\\demo-output\\.checkpoints\\demo_05_atomic_20260828_204051.SLDPRT",
    "restored_to": "C:\\projects\\cad-mcp-comparisons\\solidworks-mcp\\demo-output\\demo_05_atomic.SLDPRT",
    "pre_restore_checkpoint": "C:\\projects\\cad-mcp-comparisons\\solidworks-mcp\\demo-output\\.checkpoints\\demo_05_atomic_pre_restore_20260828_204113.SLDPRT",
    "reopened": true,
    "checkpoint_method": "save_as_copy"
  },
  "warnings": [
    "invariants that did not hold: ['body_count']",
    "The model was rolled back to the checkpoint taken before this call.",
    "Read-back verification did not hold: invariants_held (body_count: wanted 1, found 0)"
  ]
}
```

### 79. `sw_measure` - ok

The proof: the model measures exactly what it did before the sequence ran.

```json
{}
```

```json
{
  "mass_properties": {
    "volume_m3": 1.574399999999999e-05,
    "volume_mm3": 15743.99999999999,
    "surface_area_m2": 0.015776000000000002,
    "surface_area_mm2": 15776.000000000002,
    "mass_kg": 1.574399999999999e-05,
    "density_kg_m3": 1.0,
    "center_of_mass_mm": [
      0.0,
      0.0,
      10.0
    ]
  }
}
```

### 80. `sw_doc_save` - ok

```json
{
  "output_path": "C:\\projects\\cad-mcp-comparisons\\solidworks-mcp\\demo-output\\demo_05_atomic.SLDPRT",
  "overwrite": "allow",
  "confirm": true
}
```

```json
{
  "saved_path": "C:\\projects\\cad-mcp-comparisons\\solidworks-mcp\\demo-output\\demo_05_atomic.SLDPRT"
}
```

### 81. `sw_doc_new` - ok

```json
{
  "doc_type": "part"
}
```

### 82. `sw_doc_save` - ok

```json
{
  "output_path": "C:\\projects\\cad-mcp-comparisons\\solidworks-mcp\\demo-output\\demo_06_datum.SLDPRT"
}
```

```json
{
  "saved_path": "C:\\projects\\cad-mcp-comparisons\\solidworks-mcp\\demo-output\\demo_06_datum.SLDPRT"
}
```

### 83. `sw_sketch_start` - ok

```json
{
  "on": {
    "standard_plane": "front"
  }
}
```

### 84. `sw_sketch_add_geometry` - ok

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

### 85. `sw_sketch_exit` - ok

```json
{}
```

### 86. `sw_feature_extrude_boss` - ok

```json
{
  "depth": 8.0,
  "name": "BasePlate"
}
```

```json
{
  "volume_mm3_after": 47999.99999999999
}
```

### 87. `sw_sketch_start` - ok

```json
{
  "on": {
    "standard_plane": "front"
  }
}
```

### 88. `sw_sketch_add_geometry` - ok

```json
{
  "entities": [
    {
      "type": "circle",
      "center": [
        50.0,
        30.0
      ],
      "radius": 10
    }
  ]
}
```

### 89. `sw_sketch_exit` - ok

```json
{}
```

### 90. `sw_feature_extrude_cut` - ok

```json
{
  "end_condition": "through_all",
  "reverse": true,
  "name": "Bore"
}
```

```json
{
  "volume_mm3_before": 47999.99999999999,
  "volume_mm3_after": 45486.725877128156
}
```

### 91. `sw_datum_axis_create` - ok

DAT-003: an axis where two standard planes intersect.

```json
{
  "method": "two_planes",
  "standard_planes": [
    "front",
    "right"
  ],
  "name": "SpinAxis"
}
```

```json
{
  "axis_name": "SpinAxis",
  "method": "two_planes",
  "verification": {
    "read_back": true,
    "before": {
      "feature_count": 21
    },
    "after": {
      "feature_count": 22,
      "type_name": "RefAxis"
    },
    "checks": [
      {
        "name": "axis_created",
        "passed": true,
        "detail": "SpinAxis"
      },
      {
        "name": "feature_tree_grew",
        "passed": true,
        "detail": "21 -> 22 features"
      }
    ]
  }
}
```

### 92. `sw_datum_plane_create` - ok

DAT-002: an offset plane, which is by definition parallel to its reference.

```json
{
  "method": "offset",
  "standard_plane": "front",
  "distance": 25,
  "name": "Parallel"
}
```

```json
{
  "plane_name": "Parallel"
}
```

### 93. `sw_datum_list` - ok

```json
{}
```

```json
{
  "axes": [
    {
      "name": "SpinAxis",
      "type_name": "RefAxis",
      "suppressed": false,
      "ref": {
        "ref_version": 1,
        "kind": "axis",
        "label": "axis",
        "document": {
          "path": "C:\\projects\\cad-mcp-comparisons\\solidworks-mcp\\demo-output\\demo_06_datum.SLDPRT",
          "title": "demo_06_datum.SLDPRT",
          "configuration": "Default"
        },
        "persistent": {
          "scheme": "GetPersistReference3",
          "data_b64": "OEoAAAEAAAD//v8AAAAAACkAAAA="
        },
        "semantic": {
          "component_path": [],
          "feature_ancestry": [],
          "feature_type_names": [],
          "geometry_type": "axis",
          "measurements": {},
          "signature": "e6abc90a93a96c553f22",
          "tolerance": {
            "linear_m": 1e-06,
            "angular_rad": 1e-06,
            "relative": 0.0001
          }
        },
        "select_hint": {
          "sw_select_type": "AXIS",
          "mark": 0
        },
        "captured_at": "2026-08-28T20:43:02.463558+00:00",
        "warnings": []
      },
      "tool_args": {
        "ref": {
          "ref_version": 1,
          "kind": "axis",
          "label": "",
          "document": {
            "path": "C:\\projects\\cad-mcp-comparisons\\solidworks-mcp\\demo-output\\demo_06_datum.SLDPRT",
            "title": "demo_06_datum.SLDPRT",
            "configuration": "Default"
          },
          "persistent": {
            "scheme": "GetPersistReference3",
            "data_b64": "OEoAAAEAAAD//v8AAAAAACkAAAA="
          },
          "semantic": {
            "component_path": [],
            "feature_ancestry": [],
            "feature_type_names": [],
            "geometry_type": "axis",
            "measurements": {},
            "signature": "e6abc90a93a96c553f22",
            "tolerance": {
              "linear_m": 1e-06,
              "angular_rad": 1e-06,
              "relative": 0.0001
            }
          },
   
... (truncated; the full payload is in demo-log.json)
```

### 94. `sw_datum_axis_create` - refused: AXIS_CREATE_FAILED

Parallel planes never intersect. SOLIDWORKS reports that by returning false and leaving the tree alone - the exact shape of a silent success. The tool reads the tree back and refuses instead.

```json
{
  "method": "two_planes",
  "standard_planes": [
    "front"
  ],
  "refs": [
    {
      "ref_version": 1,
      "kind": "plane",
      "label": "",
      "document": {
        "path": "C:\\projects\\cad-mcp-comparisons\\solidworks-mcp\\demo-output\\demo_06_datum.SLDPRT",
        "title": "demo_06_datum.SLDPRT",
        "configuration": "Default"
      },
      "persistent": {
        "scheme": "GetPersistReference3",
        "data_b64": "OEoAAAEAAAD//v8AAAAAACsAAAA="
      },
      "semantic": {
        "component_path": [],
        "feature_ancestry": [],
        "feature_type_names": [],
        "geometry_type": "plane",
        "measurements": {},
        "signature": "14fb357ed3a104b0cffd",
        "tolerance": {
          "linear_m": 1e-06,
          "angular_rad": 1e-06,
          "relative": 0.0001
        }
      },
      "warnings": []
    }
  ]
}
```

```json
{
  "code": "AXIS_CREATE_FAILED",
  "category": "solidworks",
  "message": "SOLIDWORKS could not create a two_planes axis from those references.",
  "context": {
    "method": "two_planes",
    "insert_axis_returned": false,
    "created_type": null
  },
  "remediation": [
    "Check the references suit the method: 'two_planes' needs two non-parallel planes, 'cyl_face' one cylindrical or conical face.",
    "Use sw_probe_faces to pick the face or edge precisely."
  ],
  "doc_link": "swmcp://errors/AXIS_CREATE_FAILED"
}
```

### 95. `sw_datum_list` - ok

```json
{}
```

```json
{
  "axes": [
    {
      "name": "SpinAxis",
      "type_name": "RefAxis",
      "suppressed": false,
      "ref": {
        "ref_version": 1,
        "kind": "axis",
        "label": "axis",
        "document": {
          "path": "C:\\projects\\cad-mcp-comparisons\\solidworks-mcp\\demo-output\\demo_06_datum.SLDPRT",
          "title": "demo_06_datum.SLDPRT",
          "configuration": "Default"
        },
        "persistent": {
          "scheme": "GetPersistReference3",
          "data_b64": "OEoAAAEAAAD//v8AAAAAACkAAAA="
        },
        "semantic": {
          "component_path": [],
          "feature_ancestry": [],
          "feature_type_names": [],
          "geometry_type": "axis",
          "measurements": {},
          "signature": "e6abc90a93a96c553f22",
          "tolerance": {
            "linear_m": 1e-06,
            "angular_rad": 1e-06,
            "relative": 0.0001
          }
        },
        "select_hint": {
          "sw_select_type": "AXIS",
          "mark": 0
        },
        "captured_at": "2026-08-28T20:43:21.231377+00:00",
        "warnings": []
      },
      "tool_args": {
        "ref": {
          "ref_version": 1,
          "kind": "axis",
          "label": "",
          "document": {
            "path": "C:\\projects\\cad-mcp-comparisons\\solidworks-mcp\\demo-output\\demo_06_datum.SLDPRT",
            "title": "demo_06_datum.SLDPRT",
            "configuration": "Default"
          },
          "persistent": {
            "scheme": "GetPersistReference3",
            "data_b64": "OEoAAAEAAAD//v8AAAAAACkAAAA="
          },
          "semantic": {
            "component_path": [],
            "feature_ancestry": [],
            "feature_type_names": [],
            "geometry_type": "axis",
            "measurements": {},
            "signature": "e6abc90a93a96c553f22",
            "tolerance": {
              "linear_m": 1e-06,
              "angular_rad": 1e-06,
              "relative": 0.0001
            }
          },
   
... (truncated; the full payload is in demo-log.json)
```

### 96. `sw_probe_faces` - ok

Find the bore's circular edge and a 100 mm straight edge by measurement.

```json
{
  "entity_class": "edge",
  "limit": 100
}
```

```json
{
  "matched": 14
}
```

### 97. `sw_datum_point_create` - ok

DAT-003: a point at the centre of the bore.

```json
{
  "method": "arc_center",
  "refs": [
    {
      "ref_version": 1,
      "kind": "edge",
      "label": "",
      "document": {
        "path": "C:\\projects\\cad-mcp-comparisons\\solidworks-mcp\\demo-output\\demo_06_datum.SLDPRT",
        "title": "demo_06_datum.SLDPRT",
        "configuration": "Default"
      },
      "persistent": {
        "scheme": "GetPersistReference3",
        "data_b64": "OEoAAAMAAAD//v8AAAAAAP//AQALAG1vRWRnZVJlZl9jAQAAAAAAAAAEAAAAAAMAAAAAAAB9w5QlrUmyVH3DlCWtSbJUAAD//wEAGwBtb0Zyb21Ta3RFbnQzSW50U3VyZklkUmVwX2MAAP//AQAGAG1vRlJfY///AQANAG1vRXh0T2JqZWN0X2P//wEAEQBtb0NTdHJpbmdIYW5kbGVfY//+/09DADoAXABwAHIAbwBqAGUAYwB0AHMAXABjAGEAZAAtAG0AYwBwAC0AYwBvAG0AcABhAHIAaQBzAG8AbgBzAFwAcwBvAGwAaQBkAHcAbwByAGsAcwAtAG0AYwBwAFwAZABlAG0AbwAtAG8AdQB0AHAAdQB0AFwAZABlAG0AbwBfADAANgBfAGQAYQB0AHUAbQAuAFMATABEAFAAUgBUAAmA//7/DWQAZQBtAG8AXwAwADYAXwBkAGEAdAB1AG0AAgAAgPKRav/+/wD//v8A//7/AAAAAAAAAAAAAAAAAAAAAAAAAP/+/wdEAGUAZgBhAHUAbAB0AAAAAAAAAAAAAAAAAAAAAAAoAAAAsPKRagEAAAD/////AAAAAP//AQAUAG1vRW5kRmFjZVN1cmZJZFJlcF9jAAAFgAgAIAAAAJXykWoBAAAAAAAAAAyAAAAFgAgAIAAAAJXykWoBAAAAAAAAAAyAAAAFgAgAIAAAAJXykWoBAAAAAAAAAAAAAAAAAAAAOEoAAAAAAAA="
      },
      "semantic": {
        "component_path": [],
        "feature_ancestry": [],
        "feature_type_names": [],
        "geometry_type": "circular_edge",
        "body_name": "Bore",
        "measurements": {
          "point_m": [
            0.05,
            0.03,
            0.008
          ],
          "direction": [
            0.0,
            0.0,
            1.0
          ],
          "radius_m": 0.010000000000000002,
          "length_m": 0.0
        },
        "signature": "b07974dc2e6cd9d4275c",
        "tolerance": {
          "linear_m": 1e-06,
          "angular_rad": 1e-06,
          "relative": 0.0001
        }
      },
      "warnings": []
    }
  ],
  "name": "BoreCentre"
}
```

```json
{
  "point_names": [
    "BoreCentre"
  ],
  "count": 1,
  "verification": {
    "read_back": true,
    "before": {
      "feature_count": 23
    },
    "after": {
      "feature_count": 24,
      "points_created": 1
    },
    "checks": [
      {
        "name": "point_created",
        "passed": true,
        "detail": "BoreCentre"
      },
      {
        "name": "feature_tree_grew",
        "passed": true,
        "detail": "23 -> 24 features"
      },
      {
        "name": "every_point_is_addressable",
        "passed": true,
        "detail": "1 of 1 came back capture-ready"
      }
    ]
  }
}
```

### 98. `sw_datum_point_create` - refused: POINT_CREATE_FAILED

swRefPointCenterEdge reads like 'the centre of an edge' and is really the arc centre: SOLIDWORKS refuses it on a straight edge. The remediation names the mode that does work.

```json
{
  "method": "arc_center",
  "refs": [
    {
      "ref_version": 1,
      "kind": "edge",
      "label": "",
      "document": {
        "path": "C:\\projects\\cad-mcp-comparisons\\solidworks-mcp\\demo-output\\demo_06_datum.SLDPRT",
        "title": "demo_06_datum.SLDPRT",
        "configuration": "Default"
      },
      "persistent": {
        "scheme": "GetPersistReference3",
        "data_b64": "OEoAAAMAAAD//v8AAAAAAP//AQALAG1vRWRnZVJlZl9jAQAAAAAAAAAEAAAAAAMAAAAAAAB9w5QlrUmyVH3DlCWtSbJUAAD//wEAFABtb0VuZEZhY2VTdXJmSWRSZXBfYwAA//8BAAYAbW9GUl9j//8BAA0AbW9FeHRPYmplY3RfY///AQARAG1vQ1N0cmluZ0hhbmRsZV9j//7/T0MAOgBcAHAAcgBvAGoAZQBjAHQAcwBcAGMAYQBkAC0AbQBjAHAALQBjAG8AbQBwAGEAcgBpAHMAbwBuAHMAXABzAG8AbABpAGQAdwBvAHIAawBzAC0AbQBjAHAAXABkAGUAbQBvAC0AbwB1AHQAcAB1AHQAXABkAGUAbQBvAF8AMAA2AF8AZABhAHQAdQBtAC4AUwBMAEQAUABSAFQACYD//v8NZABlAG0AbwBfADAANgBfAGQAYQB0AHUAbQACAACA8pFq//7/AP/+/wD//v8AAAAAAAAAAAAAAAAAAAAAAAAA//7/B0QAZQBmAGEAdQBsAHQAAAAAAAAAAAAAAAAAAAAAACAAAACV8pFqAQAAAAAAAAD//wEAFwBtb0Zyb21Ta3RFbnRTdXJmSWRSZXBfYwAABYAIACAAAACV8pFqAwAAAAyAAAAFgAgAIAAAAJXykWoCAAAADIAAAAWACAAgAAAAlfKRagQAAAAAAAAAAAAAADhKAAAAAAAA"
      },
      "semantic": {
        "component_path": [],
        "feature_ancestry": [],
        "feature_type_names": [],
        "geometry_type": "line_edge",
        "body_name": "Bore",
        "measurements": {
          "point_m": [
            0.05,
            0.06,
            0.008
          ],
          "direction": [
            -1.0,
            0.0,
            0.0
          ],
          "length_m": 0.1
        },
        "signature": "f189251d483d7a5a81cb",
        "tolerance": {
          "linear_m": 1e-06,
          "angular_rad": 1e-06,
          "relative": 0.0001
        }
      },
      "warnings": []
    }
  ]
}
```

```json
{
  "code": "POINT_CREATE_FAILED",
  "category": "solidworks",
  "message": "SOLIDWORKS could not create a arc_center reference point.",
  "context": {
    "method": "arc_center",
    "along_curve": "evenly"
  },
  "remediation": [
    "'arc_center' needs a circular edge; for the midpoint of a straight edge use 'along_curve' with along_curve='percentage' and percent=50.",
    "'face_center' needs a face, 'along_curve' needs an edge, and 'intersection' needs entities that actually cross."
  ],
  "doc_link": "swmcp://errors/POINT_CREATE_FAILED"
}
```

### 99. `sw_datum_point_create` - ok

DAT-003: three points spaced evenly along the 100 mm edge.

```json
{
  "method": "along_curve",
  "along_curve": "evenly",
  "count": 3,
  "refs": [
    {
      "ref_version": 1,
      "kind": "edge",
      "label": "",
      "document": {
        "path": "C:\\projects\\cad-mcp-comparisons\\solidworks-mcp\\demo-output\\demo_06_datum.SLDPRT",
        "title": "demo_06_datum.SLDPRT",
        "configuration": "Default"
      },
      "persistent": {
        "scheme": "GetPersistReference3",
        "data_b64": "OEoAAAMAAAD//v8AAAAAAP//AQALAG1vRWRnZVJlZl9jAQAAAAAAAAAEAAAAAAMAAAAAAAB9w5QlrUmyVH3DlCWtSbJUAAD//wEAFABtb0VuZEZhY2VTdXJmSWRSZXBfYwAA//8BAAYAbW9GUl9j//8BAA0AbW9FeHRPYmplY3RfY///AQARAG1vQ1N0cmluZ0hhbmRsZV9j//7/T0MAOgBcAHAAcgBvAGoAZQBjAHQAcwBcAGMAYQBkAC0AbQBjAHAALQBjAG8AbQBwAGEAcgBpAHMAbwBuAHMAXABzAG8AbABpAGQAdwBvAHIAawBzAC0AbQBjAHAAXABkAGUAbQBvAC0AbwB1AHQAcAB1AHQAXABkAGUAbQBvAF8AMAA2AF8AZABhAHQAdQBtAC4AUwBMAEQAUABSAFQACYD//v8NZABlAG0AbwBfADAANgBfAGQAYQB0AHUAbQACAACA8pFq//7/AP/+/wD//v8AAAAAAAAAAAAAAAAAAAAAAAAA//7/B0QAZQBmAGEAdQBsAHQAAAAAAAAAAAAAAAAAAAAAACAAAACV8pFqAQAAAAAAAAD//wEAFwBtb0Zyb21Ta3RFbnRTdXJmSWRSZXBfYwAABYAIACAAAACV8pFqAwAAAAyAAAAFgAgAIAAAAJXykWoCAAAADIAAAAWACAAgAAAAlfKRagQAAAAAAAAAAAAAADhKAAAAAAAA"
      },
      "semantic": {
        "component_path": [],
        "feature_ancestry": [],
        "feature_type_names": [],
        "geometry_type": "line_edge",
        "body_name": "Bore",
        "measurements": {
          "point_m": [
            0.05,
            0.06,
            0.008
          ],
          "direction": [
            -1.0,
            0.0,
            0.0
          ],
          "length_m": 0.1
        },
        "signature": "f189251d483d7a5a81cb",
        "tolerance": {
          "linear_m": 1e-06,
          "angular_rad": 1e-06,
          "relative": 0.0001
        }
      },
      "warnings": []
    }
  ]
}
```

```json
{
  "point_names": [
    "Point2",
    "Point3",
    "Point4"
  ],
  "count": 3
}
```

### 100. `sw_datum_csys_create` - ok

DAT-004: a reference point exposes no position, so this is the only read-back SOLIDWORKS offers. The bore was sketched at (50, 30) on a 8 mm plate, so the answer is known before the call is made.

```json
{
  "origin": {
    "ref_version": 1,
    "kind": "point",
    "label": "",
    "document": {
      "path": "C:\\projects\\cad-mcp-comparisons\\solidworks-mcp\\demo-output\\demo_06_datum.SLDPRT",
      "title": "demo_06_datum.SLDPRT",
      "configuration": "Default"
    },
    "persistent": {
      "scheme": "GetPersistReference3",
      "data_b64": "OEoAAAEAAAD//v8AAAAAACwAAAA="
    },
    "semantic": {
      "component_path": [],
      "feature_ancestry": [],
      "feature_type_names": [],
      "geometry_type": "point",
      "measurements": {},
      "signature": "084e8444a2b5df4fe125",
      "tolerance": {
        "linear_m": 1e-06,
        "angular_rad": 1e-06,
        "relative": 0.0001
      }
    },
    "warnings": []
  },
  "name": "BoreFrame"
}
```

```json
{
  "csys_name": "BoreFrame",
  "transform": {
    "rotation": [
      [
        1.0,
        0.0,
        0.0
      ],
      [
        0.0,
        1.0,
        0.0
      ],
      [
        0.0,
        0.0,
        1.0
      ]
    ],
    "translation_mm": [
      50.0,
      30.0,
      8.0
    ],
    "scale": 1.0
  },
  "verification": {
    "read_back": true,
    "before": {
      "feature_count": 27
    },
    "after": {
      "feature_count": 28,
      "translation_mm": [
        50.0,
        30.0,
        8.0
      ]
    },
    "checks": [
      {
        "name": "coordinate_system_created",
        "passed": true,
        "detail": "BoreFrame"
      },
      {
        "name": "feature_tree_grew",
        "passed": true,
        "detail": "27 -> 28 features"
      },
      {
        "name": "transform_read_back",
        "passed": true,
        "detail": "origin at [50.0, 30.0, 8.0] mm"
      }
    ]
  }
}
```

### 101. `sw_feature_edit` - ok

DAT-005: rename, read back out of the tree.

```json
{
  "feature_name": "SpinAxis",
  "rename_to": "MainAxis"
}
```

```json
{
  "feature_name": "MainAxis",
  "renamed_to": "MainAxis",
  "verification": {
    "read_back": true,
    "before": {
      "name": "SpinAxis",
      "type": "RefAxis",
      "suppressed": false,
      "error_code": 0,
      "error_name": null,
      "created_at": "8/28/2026 4:42:38 PM"
    },
    "after": {
      "name": "MainAxis",
      "type": "RefAxis",
      "suppressed": false,
      "error_code": 0,
      "error_name": null,
      "created_at": "8/28/2026 4:42:38 PM"
    },
    "checks": [
      {
        "name": "rename_applied",
        "passed": true,
        "detail": "SpinAxis -> MainAxis"
      },
      {
        "name": "suppression_applied",
        "passed": true,
        "detail": "suppressed=False"
      }
    ]
  }
}
```

### 102. `sw_feature_edit` - ok

DAT-005: suppress.

```json
{
  "feature_name": "Parallel",
  "suppress": true
}
```

```json
{
  "suppressed": true,
  "verification": {
    "read_back": true,
    "before": {
      "name": "Parallel",
      "type": "RefPlane",
      "suppressed": false,
      "error_code": 0,
      "error_name": null,
      "created_at": "8/28/2026 4:42:49 PM"
    },
    "after": {
      "name": "Parallel",
      "type": "RefPlane",
      "suppressed": true,
      "error_code": 0,
      "error_name": null,
      "created_at": "8/28/2026 4:42:49 PM"
    },
    "checks": [
      {
        "name": "rename_applied",
        "passed": true,
        "detail": "Parallel -> Parallel"
      },
      {
        "name": "suppression_applied",
        "passed": true,
        "detail": "suppressed=True"
      }
    ]
  }
}
```

### 103. `sw_datum_list` - ok

```json
{}
```

```json
{
  "planes": [
    {
      "name": "Front Plane",
      "type_name": "RefPlane",
      "suppressed": false,
      "ref": {
        "ref_version": 1,
        "kind": "plane",
        "label": "plane",
        "document": {
          "path": "C:\\projects\\cad-mcp-comparisons\\solidworks-mcp\\demo-output\\demo_06_datum.SLDPRT",
          "title": "demo_06_datum.SLDPRT",
          "configuration": "Default"
        },
        "persistent": {
          "scheme": "GetPersistReference3",
          "data_b64": "OEoAAAEAAAD//v8AAAAAAAIAAAA="
        },
        "semantic": {
          "component_path": [],
          "feature_ancestry": [],
          "feature_type_names": [],
          "geometry_type": "plane",
          "measurements": {},
          "signature": "14fb357ed3a104b0cffd",
          "tolerance": {
            "linear_m": 1e-06,
            "angular_rad": 1e-06,
            "relative": 0.0001
          }
        },
        "select_hint": {
          "sw_select_type": "PLANE",
          "mark": 0
        },
        "captured_at": "2026-08-28T20:45:01.907229+00:00",
        "warnings": []
      },
      "tool_args": {
        "ref": {
          "ref_version": 1,
          "kind": "plane",
          "label": "",
          "document": {
            "path": "C:\\projects\\cad-mcp-comparisons\\solidworks-mcp\\demo-output\\demo_06_datum.SLDPRT",
            "title": "demo_06_datum.SLDPRT",
            "configuration": "Default"
          },
          "persistent": {
            "scheme": "GetPersistReference3",
            "data_b64": "OEoAAAEAAAD//v8AAAAAAAIAAAA="
          },
          "semantic": {
            "component_path": [],
            "feature_ancestry": [],
            "feature_type_names": [],
            "geometry_type": "plane",
            "measurements": {},
            "signature": "14fb357ed3a104b0cffd",
            "tolerance": {
              "linear_m": 1e-06,
              "angular_rad": 1e-06,
              "relative": 0.0001
            }
    
... (truncated; the full payload is in demo-log.json)
```

### 104. `sw_feature_edit` - ok

DAT-005: and unsuppress, so the saved file still shows the plane.

```json
{
  "feature_name": "Parallel",
  "suppress": false
}
```

```json
{
  "suppressed": false
}
```

### 105. `sw_datum_list` - ok

DAT-001: every datum, with its type token and a capture-ready reference.

```json
{}
```

```json
{
  "planes": [
    {
      "name": "Front Plane",
      "type_name": "RefPlane",
      "suppressed": false,
      "ref": {
        "ref_version": 1,
        "kind": "plane",
        "label": "plane",
        "document": {
          "path": "C:\\projects\\cad-mcp-comparisons\\solidworks-mcp\\demo-output\\demo_06_datum.SLDPRT",
          "title": "demo_06_datum.SLDPRT",
          "configuration": "Default"
        },
        "persistent": {
          "scheme": "GetPersistReference3",
          "data_b64": "OEoAAAEAAAD//v8AAAAAAAIAAAA="
        },
        "semantic": {
          "component_path": [],
          "feature_ancestry": [],
          "feature_type_names": [],
          "geometry_type": "plane",
          "measurements": {},
          "signature": "14fb357ed3a104b0cffd",
          "tolerance": {
            "linear_m": 1e-06,
            "angular_rad": 1e-06,
            "relative": 0.0001
          }
        },
        "select_hint": {
          "sw_select_type": "PLANE",
          "mark": 0
        },
        "captured_at": "2026-08-28T20:45:24.944552+00:00",
        "warnings": []
      },
      "tool_args": {
        "ref": {
          "ref_version": 1,
          "kind": "plane",
          "label": "",
          "document": {
            "path": "C:\\projects\\cad-mcp-comparisons\\solidworks-mcp\\demo-output\\demo_06_datum.SLDPRT",
            "title": "demo_06_datum.SLDPRT",
            "configuration": "Default"
          },
          "persistent": {
            "scheme": "GetPersistReference3",
            "data_b64": "OEoAAAEAAAD//v8AAAAAAAIAAAA="
          },
          "semantic": {
            "component_path": [],
            "feature_ancestry": [],
            "feature_type_names": [],
            "geometry_type": "plane",
            "measurements": {},
            "signature": "14fb357ed3a104b0cffd",
            "tolerance": {
              "linear_m": 1e-06,
              "angular_rad": 1e-06,
              "relative": 0.0001
            }
    
... (truncated; the full payload is in demo-log.json)
```

### 106. `sw_view_capture` - ok

Reference geometry is easier to believe when you can see it.

```json
{
  "output_path": "C:\\projects\\cad-mcp-comparisons\\solidworks-mcp\\demo-output\\demo_06_datum.png",
  "orientation": "isometric",
  "width": 1280,
  "height": 960
}
```

```json
{
  "saved_path": "C:\\projects\\cad-mcp-comparisons\\solidworks-mcp\\demo-output\\demo_06_datum.png",
  "actual_size": [
    1248,
    771
  ]
}
```

### 107. `sw_doc_save` - ok

```json
{
  "output_path": "C:\\projects\\cad-mcp-comparisons\\solidworks-mcp\\demo-output\\demo_06_datum.SLDPRT",
  "overwrite": "allow",
  "confirm": true
}
```

```json
{
  "saved_path": "C:\\projects\\cad-mcp-comparisons\\solidworks-mcp\\demo-output\\demo_06_datum.SLDPRT"
}
```

### 108. `sw_doc_close` - ok

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

### 109. `sw_doc_close` - ok

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

### 110. `sw_doc_close` - ok

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

### 111. `sw_doc_close` - ok

Addressed by title; never 'whatever happens to be active'.

```json
{
  "document": {
    "title": "demo_04_parametric.SLDPRT"
  },
  "save_first": "discard",
  "confirm": true
}
```

### 112. `sw_doc_close` - ok

Addressed by title; never 'whatever happens to be active'.

```json
{
  "document": {
    "title": "demo_05_atomic.SLDPRT"
  },
  "save_first": "discard",
  "confirm": true
}
```

### 113. `sw_doc_close` - ok

Addressed by title; never 'whatever happens to be active'.

```json
{
  "document": {
    "title": "demo_06_datum.SLDPRT"
  },
  "save_first": "discard",
  "confirm": true
}
```

