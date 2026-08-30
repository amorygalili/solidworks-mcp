# sw_mate_probe

List the entities in an assembly that could take a given mate, or judge one pair before creating it. The verdict is a prediction from geometry, not a SOLIDWORKS ruling.

| | |
|---|---|
| Tier | `core` |
| Domains | `assembly` |
| Document precondition | `assembly` |
| Safety | `read` |
| Read-only | True |
| Destructive | False |
| Confirmation required | False |
| Auto-checkpointed | False |
| Idempotent | True |
| Timeout | 300s |
| Satisfies | `REF-005` |
| Partially satisfies | `MATE-005` |

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
  "description": "MATE-005. Either list candidate entities, or judge one specific pair.\n\nPassing ``refs`` switches the tool from listing candidates to judging that pair.",
  "properties": {
    "components": {
      "anyOf": [
        {
          "items": {
            "type": "string"
          },
          "maxItems": 64,
          "type": "array"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Restrict candidates to these component instance names, as sw_asm_tree reports them, e.g. ['bracket-1'].",
      "title": "Components"
    },
    "document": {
      "$ref": "#/$defs/DocTarget",
      "description": "Which document to act on. Defaults to the active document."
    },
    "entity_class": {
      "default": "face",
      "description": "Which kind of entity to list as a candidate.",
      "enum": [
        "face",
        "edge"
      ],
      "title": "Entity Class",
      "type": "string"
    },
    "limit": {
      "default": 25,
      "description": "Most candidates to return.",
      "maximum": 200,
      "minimum": 1,
      "title": "Limit",
      "type": "integer"
    },
    "mate_type": {
      "anyOf": [
        {
          "enum": [
            "coincident",
            "concentric",
            "perpendicular",
            "parallel",
            "tangent",
            "distance",
            "angle",
            "lock"
          ],
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "The mate being considered. With refs, this is what gets judged; without them, only entities that could take this mate are listed.",
      "title": "Mate Type"
    },
    "refs": {
      "anyOf": [
        {
          "items": {
            "$ref": "#/$defs/EntityRef"
          },
          "maxItems": 2,
          "minItems": 2,
          "type": "array"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Two entities to judge as a mate pair. Omit to list candidate entities instead.",
      "title": "Refs"
    }
  },
  "title": "MateProbeArgs",
  "type": "object"
}
```

## Result schema

```json
{
  "additionalProperties": false,
  "description": "What the probe could establish, kept separate from what it only predicts.\n\n``feasible`` is a *prediction* and ``proven`` is therefore always false: SOLIDWORKS\nexposes no validate-only mate call, so the only conclusive test is building the\nmate. ``resolved`` and ``different_components`` are measured, not predicted.",
  "properties": {
    "also_possible": {
      "description": "Other mate types this pair could take.",
      "items": {
        "type": "string"
      },
      "title": "Also Possible",
      "type": "array"
    },
    "candidates": {
      "description": "Candidate mode: mateable entities, each with paste-ready tool_args.",
      "items": {
        "additionalProperties": true,
        "type": "object"
      },
      "title": "Candidates",
      "type": "array"
    },
    "different_components": {
      "anyOf": [
        {
          "type": "boolean"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Pair mode: whether the two entities are on two components.",
      "title": "Different Components"
    },
    "entities": {
      "description": "Pair mode: what each reference resolved to.",
      "items": {
        "additionalProperties": true,
        "type": "object"
      },
      "title": "Entities",
      "type": "array"
    },
    "examined": {
      "default": 0,
      "title": "Examined",
      "type": "integer"
    },
    "feasible": {
      "anyOf": [
        {
          "type": "boolean"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Pair mode: whether the mate is predicted to build.",
      "title": "Feasible"
    },
    "matched": {
      "default": 0,
      "title": "Matched",
      "type": "integer"
    },
    "mate_type": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "title": "Mate Type"
    },
    "mode": {
      "enum": [
        "candidates",
        "pair"
      ],
      "title": "Mode",
      "type": "string"
    },
    "proven": {
      "default": false,
      "description": "Always false. A prediction from entity geometry, never a SOLIDWORKS verdict; sw_safe_execute is how to get a conclusive answer with rollback.",
      "title": "Proven",
      "type": "boolean"
    },
    "reasons": {
      "description": "Why the mate is predicted to fail, most specific first.",
      "items": {
        "type": "string"
      },
      "title": "Reasons",
      "type": "array"
    },
    "resolved": {
      "anyOf": [
        {
          "type": "boolean"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Pair mode: whether both references still resolve.",
      "title": "Resolved"
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
    "mode"
  ],
  "title": "MateProbeResult",
  "type": "object"
}
```
