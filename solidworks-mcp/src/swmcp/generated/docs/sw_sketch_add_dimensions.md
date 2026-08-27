# sw_sketch_add_dimensions

Add driving dimensions to sketch segments in one batch and optionally set their values. Always returns the resulting solver state, so reaching fully defined is verifiable rather than assumed.

| | |
|---|---|
| Tier | `core` |
| Domains | `constraint`, `sketch` |
| Document precondition | `part_or_assembly` |
| Safety | `model_mutation` |
| Read-only | False |
| Destructive | False |
| Confirmation required | False |
| Auto-checkpointed | True |
| Idempotent | False |
| Timeout | 300s |
| Satisfies | `CON-002`, `CON-005` |

## Input schema

```json
{
  "$defs": {
    "DimensionSpec": {
      "additionalProperties": false,
      "properties": {
        "angle_value": {
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
              "description": "Angle. A bare number is degrees; or use '45deg' / '1.57rad' / {'value': 45, 'unit': 'degrees'}."
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Target angle for angle dimensions.",
          "title": "Angle Value"
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
          "description": "Rename the dimension after creating it.",
          "title": "Name"
        },
        "place_at": {
          "anyOf": [
            {
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
              "maxItems": 3,
              "minItems": 3,
              "type": "array"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Where to put the dimension annotation.",
          "title": "Place At"
        },
        "segment_ids": {
          "items": {
            "type": "string"
          },
          "maxItems": 3,
          "minItems": 1,
          "title": "Segment Ids",
          "type": "array"
        },
        "type": {
          "enum": [
            "distance",
            "horizontal_distance",
            "vertical_distance",
            "radius",
            "diameter",
            "angle",
            "arc_length"
          ],
          "title": "Type",
          "type": "string"
        },
        "value": {
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
          "description": "Target value. Omit to dimension without driving a change.",
          "title": "Value"
        }
      },
      "required": [
        "type",
        "segment_ids"
      ],
      "title": "DimensionSpec",
      "type": "object"
    },
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
    }
  },
  "additionalProperties": false,
  "properties": {
    "dimensions": {
      "items": {
        "$ref": "#/$defs/DimensionSpec"
      },
      "maxItems": 200,
      "minItems": 1,
      "title": "Dimensions",
      "type": "array"
    },
    "document": {
      "$ref": "#/$defs/DocTarget",
      "description": "Which document to act on. Defaults to the active document."
    },
    "preflight": {
      "default": false,
      "description": "Validate inputs and report what would happen, without changing the model.",
      "title": "Preflight",
      "type": "boolean"
    },
    "sketch_name": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "title": "Sketch Name"
    }
  },
  "required": [
    "dimensions"
  ],
  "title": "SketchAddDimensionsArgs",
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
    "created": {
      "items": {
        "additionalProperties": true,
        "type": "object"
      },
      "title": "Created",
      "type": "array"
    },
    "failed": {
      "items": {
        "additionalProperties": true,
        "type": "object"
      },
      "title": "Failed",
      "type": "array"
    },
    "rebuild_errors": {
      "items": {
        "type": "string"
      },
      "title": "Rebuild Errors",
      "type": "array"
    },
    "sketch_state": {
      "$ref": "#/$defs/SketchState"
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
    "sketch_state"
  ],
  "title": "SketchAddDimensionsResult",
  "type": "object"
}
```
