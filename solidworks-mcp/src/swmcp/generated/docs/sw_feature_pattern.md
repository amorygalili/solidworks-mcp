# sw_feature_pattern

Repeat features in a linear or circular pattern. Other pattern families are rejected by the schema rather than failing at runtime, so the tool never advertises coverage it does not have.

| | |
|---|---|
| Tier | `core` |
| Domains | `feature` |
| Document precondition | `part` |
| Safety | `model_mutation` |
| Read-only | False |
| Destructive | False |
| Confirmation required | False |
| Auto-checkpointed | True |
| Idempotent | False |
| Timeout | 300s |
| Partially satisfies | `FEAT-007` |

## Input schema

```json
{
  "$defs": {
    "DocTarget": {
      "additionalProperties": false,
      "description": "Which document an operation acts on.\n\nWith neither field set the active document is used. Naming both is refused rather\nthan silently preferring one.",
      "properties": {
        "path": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Full path of an already-open document. Takes precedence over title.",
          "title": "Path"
        },
        "title": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Window title of an open document. Refused if more than one matches.",
          "title": "Title"
        }
      },
      "title": "DocTarget",
      "type": "object"
    },
    "DocumentRef": {
      "additionalProperties": false,
      "properties": {
        "configuration": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Configuration"
        },
        "path": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Path"
        },
        "title": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Title"
        }
      },
      "title": "DocumentRef",
      "type": "object"
    },
    "EntityRef": {
      "additionalProperties": false,
      "description": "A reference to one SOLIDWORKS entity, in every addressing mode at once.",
      "properties": {
        "captured_at": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Captured At"
        },
        "document": {
          "$ref": "#/$defs/DocumentRef"
        },
        "kind": {
          "default": "unknown",
          "enum": [
            "face",
            "edge",
            "vertex",
            "body",
            "feature",
            "sketch",
            "sketch_segment",
            "plane",
            "axis",
            "point",
            "coordinate_system",
            "component",
            "unknown"
          ],
          "title": "Kind",
          "type": "string"
        },
        "label": {
          "default": "",
          "description": "A human sentence describing the entity.",
          "title": "Label",
          "type": "string"
        },
        "persistent": {
          "anyOf": [
            {
              "$ref": "#/$defs/PersistentRef"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "ref_version": {
          "default": 1,
          "title": "Ref Version",
          "type": "integer"
        },
        "select_hint": {
          "anyOf": [
            {
              "$ref": "#/$defs/SelectHint"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "semantic": {
          "$ref": "#/$defs/SemanticRef"
        },
        "warnings": {
          "items": {
            "type": "string"
          },
          "title": "Warnings",
          "type": "array"
        }
      },
      "title": "EntityRef",
      "type": "object"
    },
    "PersistentRef": {
      "additionalProperties": false,
      "properties": {
        "captured_revision": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Captured Revision"
        },
        "data_b64": {
          "title": "Data B64",
          "type": "string"
        },
        "scheme": {
          "default": "GetPersistReference3",
          "title": "Scheme",
          "type": "string"
        }
      },
      "required": [
        "data_b64"
      ],
      "title": "PersistentRef",
      "type": "object"
    },
    "RefMeasurements": {
      "additionalProperties": false,
      "description": "Geometry sampled at capture time, in API units (metres).",
      "properties": {
        "area_m2": {
          "anyOf": [
            {
              "type": "number"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Area M2"
        },
        "bbox_m": {
          "anyOf": [
            {
              "items": {
                "type": "number"
              },
              "type": "array"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "[xmin, ymin, zmin, xmax, ymax, zmax].",
          "title": "Bbox M"
        },
        "direction": {
          "anyOf": [
            {
              "items": {
                "type": "number"
              },
              "type": "array"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Plane normal, cylinder axis, or edge tangent at the midpoint.",
          "title": "Direction"
        },
        "length_m": {
          "anyOf": [
            {
              "type": "number"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Length M"
        },
        "point_m": {
          "anyOf": [
            {
              "items": {
                "type": "number"
              },
              "type": "array"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "A point on the entity: face centre, edge midpoint, or vertex.",
          "title": "Point M"
        },
        "radius_m": {
          "anyOf": [
            {
              "type": "number"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Radius M"
        }
      },
      "title": "RefMeasurements",
      "type": "object"
    },
    "RefTolerance": {
      "additionalProperties": false,
      "properties": {
        "angular_rad": {
          "default": 1e-06,
          "title": "Angular Rad",
          "type": "number"
        },
        "linear_m": {
          "default": 1e-06,
          "title": "Linear M",
          "type": "number"
        },
        "relative": {
          "default": 0.0001,
          "title": "Relative",
          "type": "number"
        }
      },
      "title": "RefTolerance",
      "type": "object"
    },
    "SelectHint": {
      "additionalProperties": false,
      "description": "Last-resort geometric re-pick information.",
      "properties": {
        "mark": {
          "default": 0,
          "title": "Mark",
          "type": "integer"
        },
        "ray_direction": {
          "anyOf": [
            {
              "items": {
                "type": "number"
              },
              "type": "array"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Ray Direction"
        },
        "ray_origin_m": {
          "anyOf": [
            {
              "items": {
                "type": "number"
              },
              "type": "array"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Ray Origin M"
        },
        "sw_select_type": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Sw Select Type"
        }
      },
      "title": "SelectHint",
      "type": "object"
    },
    "SemanticRef": {
      "additionalProperties": false,
      "description": "The fallback that survives when a persistent reference does not.",
      "properties": {
        "body_name": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Body Name"
        },
        "component_path": {
          "items": {
            "type": "string"
          },
          "title": "Component Path",
          "type": "array"
        },
        "feature_ancestry": {
          "description": "Display names, outermost last.",
          "items": {
            "type": "string"
          },
          "title": "Feature Ancestry",
          "type": "array"
        },
        "feature_type_names": {
          "description": "Locale-invariant GetTypeName2 tokens for the same ancestry.",
          "items": {
            "type": "string"
          },
          "title": "Feature Type Names",
          "type": "array"
        },
        "geometry_type": {
          "default": "unknown",
          "title": "Geometry Type",
          "type": "string"
        },
        "measurements": {
          "$ref": "#/$defs/RefMeasurements"
        },
        "signature": {
          "default": "",
          "description": "Hash of the rounded geometry.",
          "title": "Signature",
          "type": "string"
        },
        "tolerance": {
          "$ref": "#/$defs/RefTolerance"
        }
      },
      "title": "SemanticRef",
      "type": "object"
    }
  },
  "additionalProperties": false,
  "properties": {
    "angle": {
      "anyOf": [
        {
          "type": "number"
        },
        {
          "pattern": "^\\s*[+-]?(\\d+\\.?\\d*|\\.\\d+)([eE][+-]?\\d+)?\\s*\\S*\\s*$",
          "type": "string"
        },
        {
          "additionalProperties": false,
          "properties": {
            "unit": {
              "type": "string"
            },
            "value": {
              "type": "number"
            }
          },
          "required": [
            "value"
          ],
          "type": "object"
        }
      ],
      "default": 90.0,
      "description": "Total or per-instance angle for circular.",
      "title": "Angle"
    },
    "count": {
      "description": "Total instances including the original.",
      "maximum": 1000,
      "minimum": 2,
      "title": "Count",
      "type": "integer"
    },
    "direction_ref": {
      "anyOf": [
        {
          "$ref": "#/$defs/EntityRef"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Edge, axis, or planar face giving the first direction."
    },
    "document": {
      "$ref": "#/$defs/DocTarget",
      "description": "Which document to act on. Defaults to the active document."
    },
    "equal_spacing": {
      "default": true,
      "description": "Circular: spread instances evenly.",
      "title": "Equal Spacing",
      "type": "boolean"
    },
    "feature_names": {
      "description": "Features to repeat.",
      "items": {
        "type": "string"
      },
      "maxItems": 50,
      "minItems": 1,
      "title": "Feature Names",
      "type": "array"
    },
    "name": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "title": "Name"
    },
    "reverse": {
      "default": false,
      "title": "Reverse",
      "type": "boolean"
    },
    "second_count": {
      "default": 1,
      "maximum": 1000,
      "minimum": 1,
      "title": "Second Count",
      "type": "integer"
    },
    "second_direction_ref": {
      "anyOf": [
        {
          "$ref": "#/$defs/EntityRef"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    },
    "second_spacing": {
      "anyOf": [
        {
          "type": "number"
        },
        {
          "pattern": "^\\s*[+-]?(\\d+\\.?\\d*|\\.\\d+)([eE][+-]?\\d+)?\\s*\\S*\\s*$",
          "type": "string"
        },
        {
          "additionalProperties": false,
          "properties": {
            "unit": {
              "type": "string"
            },
            "value": {
              "type": "number"
            }
          },
          "required": [
            "value"
          ],
          "type": "object"
        }
      ],
      "default": 10.0,
      "description": "Length. A bare number is millimetres; or use '50mm' / '2in' / {'value': 2, 'unit': 'inch'}. Supported units: mm, cm, m, in, ft.",
      "title": "Second Spacing"
    },
    "spacing": {
      "anyOf": [
        {
          "type": "number"
        },
        {
          "pattern": "^\\s*[+-]?(\\d+\\.?\\d*|\\.\\d+)([eE][+-]?\\d+)?\\s*\\S*\\s*$",
          "type": "string"
        },
        {
          "additionalProperties": false,
          "properties": {
            "unit": {
              "type": "string"
            },
            "value": {
              "type": "number"
            }
          },
          "required": [
            "value"
          ],
          "type": "object"
        }
      ],
      "default": 10.0,
      "description": "Spacing for a linear pattern.",
      "title": "Spacing"
    },
    "standard_axis": {
      "anyOf": [
        {
          "enum": [
            "x",
            "y",
            "z"
          ],
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Shorthand for the model's own X, Y or Z axis, so patterning about the part's centreline does not need an EntityRef captured from geometry that may not exist yet. Resolved as the intersection of two standard planes; SOLIDWORKS can only pattern about a real axis, so a reference axis named 'swmcp_axis_<x|y|z>' is added to the tree the first time and reused after that. Give this or direction_ref, not both.",
      "title": "Standard Axis"
    },
    "type": {
      "description": "Only linear and circular are supported. Curve-driven, sketch-driven, table-driven, fill, and variable patterns are rejected here rather than failing at runtime.",
      "enum": [
        "linear",
        "circular"
      ],
      "title": "Type",
      "type": "string"
    }
  },
  "required": [
    "type",
    "feature_names",
    "count"
  ],
  "title": "PatternArgs",
  "type": "object"
}
```

## Result schema

```json
{
  "$defs": {
    "Check": {
      "additionalProperties": false,
      "description": "One named invariant asserted after a mutation.",
      "properties": {
        "detail": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Detail"
        },
        "name": {
          "title": "Name",
          "type": "string"
        },
        "passed": {
          "title": "Passed",
          "type": "boolean"
        }
      },
      "required": [
        "name",
        "passed"
      ],
      "title": "Check",
      "type": "object"
    },
    "CheckpointRecord": {
      "additionalProperties": false,
      "description": "What the auto-checkpoint layer did before a mutation ran.",
      "properties": {
        "checkpoint_path": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Checkpoint Path"
        },
        "created_utc": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Created Utc"
        },
        "method": {
          "description": "Never optional: the caller must be able to tell a real snapshot from a skipped one. 'file_copy' does not capture unsaved session state.",
          "enum": [
            "save_as_copy",
            "file_copy",
            "skipped",
            "reused"
          ],
          "title": "Method",
          "type": "string"
        },
        "reason": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Why the checkpoint was skipped or reused.",
          "title": "Reason"
        },
        "size_bytes": {
          "anyOf": [
            {
              "type": "integer"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Size Bytes"
        },
        "source_path": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Source Path"
        }
      },
      "required": [
        "method"
      ],
      "title": "CheckpointRecord",
      "type": "object"
    },
    "Verification": {
      "additionalProperties": false,
      "description": "Evidence that a mutation actually happened, read back out of the model.",
      "properties": {
        "after": {
          "additionalProperties": true,
          "title": "After",
          "type": "object"
        },
        "before": {
          "additionalProperties": true,
          "title": "Before",
          "type": "object"
        },
        "checks": {
          "description": "At least one invariant must be asserted.",
          "items": {
            "$ref": "#/$defs/Check"
          },
          "minItems": 1,
          "title": "Checks",
          "type": "array"
        },
        "read_back": {
          "description": "True only when the post-state was re-read from SOLIDWORKS, not assumed.",
          "title": "Read Back",
          "type": "boolean"
        }
      },
      "required": [
        "read_back",
        "checks"
      ],
      "title": "Verification",
      "type": "object"
    }
  },
  "additionalProperties": false,
  "properties": {
    "axis_name": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "The reference axis the pattern turned about, when standard_axis resolved one. Named so a later call reuses it instead of adding another.",
      "title": "Axis Name"
    },
    "axis_was_created": {
      "default": false,
      "description": "True when this call added that axis to the feature tree. A shorthand that changes the tree should say so rather than let the caller find it later.",
      "title": "Axis Was Created",
      "type": "boolean"
    },
    "body_count_after": {
      "title": "Body Count After",
      "type": "integer"
    },
    "body_count_before": {
      "title": "Body Count Before",
      "type": "integer"
    },
    "checkpoint": {
      "anyOf": [
        {
          "$ref": "#/$defs/CheckpointRecord"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Populated by the dispatch pipeline, not by handlers."
    },
    "feature_name": {
      "title": "Feature Name",
      "type": "string"
    },
    "instances_requested": {
      "title": "Instances Requested",
      "type": "integer"
    },
    "pattern_type": {
      "title": "Pattern Type",
      "type": "string"
    },
    "rebuild_errors": {
      "items": {
        "type": "string"
      },
      "title": "Rebuild Errors",
      "type": "array"
    },
    "verification": {
      "$ref": "#/$defs/Verification"
    },
    "volume_mm3_after": {
      "anyOf": [
        {
          "type": "number"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "title": "Volume Mm3 After"
    },
    "volume_mm3_before": {
      "anyOf": [
        {
          "type": "number"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "title": "Volume Mm3 Before"
    },
    "warnings": {
      "description": "Non-fatal problems the caller should see (degraded evidence, fallbacks used).",
      "items": {
        "type": "string"
      },
      "title": "Warnings",
      "type": "array"
    }
  },
  "required": [
    "verification",
    "feature_name",
    "pattern_type",
    "instances_requested",
    "body_count_before",
    "body_count_after"
  ],
  "title": "PatternResult",
  "type": "object"
}
```
