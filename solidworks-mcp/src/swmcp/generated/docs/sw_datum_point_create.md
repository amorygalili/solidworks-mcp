# sw_datum_point_create

Create reference points at a face centre, an edge centre, an intersection, a projected vertex, a sketch point, or spaced along a curve by distance, percentage, or even division.

| | |
|---|---|
| Tier | `core` |
| Domains | `datum` |
| Document precondition | `part_or_assembly` |
| Safety | `model_mutation` |
| Read-only | False |
| Destructive | False |
| Confirmation required | False |
| Auto-checkpointed | True |
| Idempotent | False |
| Timeout | 180s |
| Satisfies | `DAT-003` |

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
    "along_curve": {
      "default": "evenly",
      "description": "For 'along_curve': place by distance, by percentage, or evenly spaced.",
      "enum": [
        "distance",
        "percentage",
        "evenly"
      ],
      "title": "Along Curve",
      "type": "string"
    },
    "count": {
      "default": 1,
      "description": "How many points to distribute when along_curve is 'evenly'.",
      "maximum": 50,
      "minimum": 1,
      "title": "Count",
      "type": "integer"
    },
    "distance": {
      "anyOf": [
        {
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
          "description": "Length. A bare number is millimetres; or use '50mm' / '2in' / {'value': 2, 'unit': 'inch'}. Supported units: mm, cm, m, in, ft."
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Distance along the curve when along_curve is 'distance'.",
      "title": "Distance"
    },
    "document": {
      "$ref": "#/$defs/DocTarget",
      "description": "Which document to act on. Defaults to the active document."
    },
    "method": {
      "description": "What geometry the point is derived from. 'arc_center' needs a circular edge and lands on its centre; a straight edge is rejected by SOLIDWORKS, so use 'along_curve' with percentage 50 for an edge midpoint.",
      "enum": [
        "along_curve",
        "arc_center",
        "face_center",
        "face_vertex_projection",
        "intersection",
        "sketch_point"
      ],
      "title": "Method",
      "type": "string"
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
      "description": "Rename the point feature afterwards.",
      "title": "Name"
    },
    "percent": {
      "anyOf": [
        {
          "maximum": 100.0,
          "minimum": 0.0,
          "type": "number"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Percentage along the curve when along_curve is 'percentage'.",
      "title": "Percent"
    },
    "refs": {
      "description": "The edges, faces, vertices, or sketch points the point is built on.",
      "items": {
        "$ref": "#/$defs/EntityRef"
      },
      "maxItems": 8,
      "minItems": 1,
      "title": "Refs",
      "type": "array"
    }
  },
  "required": [
    "method"
  ],
  "title": "DatumPointCreateArgs",
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
    "count": {
      "title": "Count",
      "type": "integer"
    },
    "method": {
      "title": "Method",
      "type": "string"
    },
    "point_names": {
      "items": {
        "type": "string"
      },
      "title": "Point Names",
      "type": "array"
    },
    "rebuild_errors": {
      "items": {
        "type": "string"
      },
      "title": "Rebuild Errors",
      "type": "array"
    },
    "references": {
      "items": {
        "additionalProperties": true,
        "type": "object"
      },
      "title": "References",
      "type": "array"
    },
    "verification": {
      "$ref": "#/$defs/Verification"
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
    "count",
    "method"
  ],
  "title": "DatumPointCreateResult",
  "type": "object"
}
```
