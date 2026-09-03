# sw_sketch_derive

Copy an existing sketch onto another plane, optionally scaled, rotated, mirrored or moved, without re-transmitting its geometry.

| | |
|---|---|
| Tier | `extended` |
| Domains | `sketch` |
| Document precondition | `part_or_assembly` |
| Safety | `model_mutation` |
| Read-only | False |
| Destructive | False |
| Confirmation required | False |
| Auto-checkpointed | True |
| Idempotent | False |
| Timeout | 300s |
| Satisfies | `SK-001`, `SK-003`, `SK-004` |

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
    },
    "SketchPlaneTarget": {
      "additionalProperties": false,
      "description": "Where a sketch goes. Exactly one of these should be given.",
      "properties": {
        "plane_name": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "A named reference plane.",
          "title": "Plane Name"
        },
        "ref": {
          "anyOf": [
            {
              "$ref": "#/$defs/EntityRef"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "A planar face or datum plane."
        },
        "standard_plane": {
          "anyOf": [
            {
              "enum": [
                "front",
                "top",
                "right"
              ],
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Resolved by position in the feature tree and the locale-invariant RefPlane token, so a non-English SOLIDWORKS works without an alias table.",
          "title": "Standard Plane"
        }
      },
      "title": "SketchPlaneTarget",
      "type": "object"
    }
  },
  "additionalProperties": false,
  "properties": {
    "about": {
      "description": "The fixed point for scale, rotation and mirror. Sketch origin by default.",
      "items": {
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
      "maxItems": 2,
      "minItems": 2,
      "title": "About",
      "type": "array"
    },
    "detail": {
      "default": "auto",
      "description": "How much to say about each created segment. 'full' describes every one; 'compact' returns only the handle, type and index; 'auto' (the default) is full up to 60 segments and compact beyond that. Handles are always returned, so relations, dimensions and deletes can still address the geometry. Entities that landed off their requested coordinates keep full detail in every mode.",
      "enum": [
        "auto",
        "full",
        "compact"
      ],
      "title": "Detail",
      "type": "string"
    },
    "document": {
      "$ref": "#/$defs/DocTarget",
      "description": "Which document to act on. Defaults to the active document."
    },
    "exit_sketch": {
      "default": true,
      "description": "Close the sketch when the geometry is in.",
      "title": "Exit Sketch",
      "type": "boolean"
    },
    "include_construction": {
      "default": true,
      "description": "Carry construction geometry across as construction.",
      "title": "Include Construction",
      "type": "boolean"
    },
    "mirror": {
      "anyOf": [
        {
          "enum": [
            "x",
            "y"
          ],
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Mirror across the named sketch axis through 'about'. This reverses every arc's direction, which is done for you: leaving it alone would rebuild each arc as its own complement, with identical endpoints and no complaint.",
      "title": "Mirror"
    },
    "on": {
      "$ref": "#/$defs/SketchPlaneTarget",
      "description": "Where the derived sketch goes."
    },
    "rebuild": {
      "default": true,
      "description": "Rebuild the model on exiting.",
      "title": "Rebuild",
      "type": "boolean"
    },
    "rotate": {
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
      "default": 0,
      "description": "Rotation about 'about'.",
      "title": "Rotate"
    },
    "scale": {
      "default": 1.0,
      "description": "Uniform scale about 'about'. Only uniform: a non-uniform scale turns a circle into an ellipse and an arc into a curve with no arc_center spec, so the derived sketch could not be expressed at all.",
      "exclusiveMinimum": 0,
      "title": "Scale",
      "type": "number"
    },
    "source_sketch": {
      "description": "The sketch to copy geometry from. It is read, never modified.",
      "title": "Source Sketch",
      "type": "string"
    },
    "translate": {
      "description": "Applied last, after mirror, scale and rotation.",
      "items": {
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
      "maxItems": 2,
      "minItems": 2,
      "title": "Translate",
      "type": "array"
    }
  },
  "required": [
    "source_sketch",
    "on"
  ],
  "title": "SketchDeriveArgs",
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
    "SketchState": {
      "additionalProperties": false,
      "description": "CON-005, carried on every relation and dimension result so it cannot be skipped.",
      "properties": {
        "dangling_relations": {
          "items": {
            "additionalProperties": true,
            "type": "object"
          },
          "title": "Dangling Relations",
          "type": "array"
        },
        "fully_defined": {
          "title": "Fully Defined",
          "type": "boolean"
        },
        "over_defined": {
          "title": "Over Defined",
          "type": "boolean"
        },
        "over_defining_relations": {
          "items": {
            "additionalProperties": true,
            "type": "object"
          },
          "title": "Over Defining Relations",
          "type": "array"
        },
        "relation_count": {
          "title": "Relation Count",
          "type": "integer"
        },
        "status": {
          "description": "fully_defined, under_defined, over_defined, or no_solution.",
          "title": "Status",
          "type": "string"
        },
        "status_code": {
          "title": "Status Code",
          "type": "integer"
        }
      },
      "required": [
        "status",
        "status_code",
        "fully_defined",
        "over_defined",
        "relation_count"
      ],
      "title": "SketchState",
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
    "contours": {
      "additionalProperties": true,
      "title": "Contours",
      "type": "object"
    },
    "created": {
      "items": {
        "additionalProperties": true,
        "type": "object"
      },
      "title": "Created",
      "type": "array"
    },
    "created_compacted": {
      "default": false,
      "title": "Created Compacted",
      "type": "boolean"
    },
    "created_total": {
      "default": 0,
      "title": "Created Total",
      "type": "integer"
    },
    "exited": {
      "default": false,
      "title": "Exited",
      "type": "boolean"
    },
    "failed": {
      "items": {
        "additionalProperties": true,
        "type": "object"
      },
      "title": "Failed",
      "type": "array"
    },
    "frame": {
      "anyOf": [
        {
          "additionalProperties": true,
          "type": "object"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Where this sketch's own axes point in model space: the origin, the model direction of sketch +X and +Y, the plane normal, and a 'maps' sentence stating it in words. Without this, which way a sketch coordinate runs in the model has to be guessed and then confirmed from a finished body's bounding box.",
      "title": "Frame"
    },
    "max_deviation_mm": {
      "anyOf": [
        {
          "type": "number"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "title": "Max Deviation Mm"
    },
    "plane": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "title": "Plane"
    },
    "rebuild_errors": {
      "items": {
        "type": "string"
      },
      "title": "Rebuild Errors",
      "type": "array"
    },
    "sketch_name": {
      "title": "Sketch Name",
      "type": "string"
    },
    "sketch_state": {
      "$ref": "#/$defs/SketchState"
    },
    "skipped": {
      "description": "Source segments that have no lossless primitive spec - an ellipse, a parabola, sketch text. Named rather than dropped, because a derived sketch quietly missing a segment is a profile that will not close.",
      "items": {
        "additionalProperties": true,
        "type": "object"
      },
      "title": "Skipped",
      "type": "array"
    },
    "source_sketch": {
      "title": "Source Sketch",
      "type": "string"
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
    "sketch_name",
    "source_sketch",
    "sketch_state"
  ],
  "title": "SketchDeriveResult",
  "type": "object"
}
```
