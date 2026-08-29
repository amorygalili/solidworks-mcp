# sw_sketch_text

Draw sketch text, optionally running along a sketch segment, so engraving and embossing do not need a macro. Verified by counting the text back out.

| | |
|---|---|
| Tier | `core` |
| Domains | `sketch` |
| Document precondition | `part_or_assembly` |
| Safety | `model_mutation` |
| Read-only | False |
| Destructive | False |
| Confirmation required | False |
| Auto-checkpointed | True |
| Idempotent | False |
| Timeout | 180s |
| Partially satisfies | `SK-008` |

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
    }
  },
  "additionalProperties": false,
  "description": "SK-008. Font is deliberately absent \u2014 see the handler for why.",
  "properties": {
    "alignment": {
      "default": "left",
      "enum": [
        "left",
        "center",
        "right",
        "justified"
      ],
      "title": "Alignment",
      "type": "string"
    },
    "at": {
      "description": "Start of the text block. Ignored when the text follows a path.",
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
      "title": "At",
      "type": "array"
    },
    "char_spacing": {
      "default": 100,
      "description": "Percentage spacing between characters. SOLIDWORKS ignores it when alignment is 'justified'.",
      "maximum": 10000,
      "minimum": 1,
      "title": "Char Spacing",
      "type": "integer"
    },
    "document": {
      "$ref": "#/$defs/DocTarget",
      "description": "Which document to act on. Defaults to the active document."
    },
    "flip_vertical": {
      "default": false,
      "title": "Flip Vertical",
      "type": "boolean"
    },
    "mirror_horizontal": {
      "default": false,
      "title": "Mirror Horizontal",
      "type": "boolean"
    },
    "path_segment_id": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Sketch segment in this sketch for the text to run along. Alignment and flip only mean anything with a path; without one the text sits horizontally.",
      "title": "Path Segment Id"
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
      "description": "Sketch to draw into. Defaults to the open one.",
      "title": "Sketch Name"
    },
    "text": {
      "description": "The characters to draw.",
      "maxLength": 1000,
      "minLength": 1,
      "title": "Text",
      "type": "string"
    },
    "width_factor": {
      "default": 100,
      "description": "Percentage width of each character.",
      "maximum": 1667,
      "minimum": 6,
      "title": "Width Factor",
      "type": "integer"
    }
  },
  "required": [
    "text"
  ],
  "title": "SketchTextArgs",
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
    "alignment": {
      "title": "Alignment",
      "type": "string"
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
    "on_path": {
      "title": "On Path",
      "type": "boolean"
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
    "text": {
      "title": "Text",
      "type": "string"
    },
    "text_segment_count": {
      "title": "Text Segment Count",
      "type": "integer"
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
    "text",
    "on_path",
    "text_segment_count",
    "alignment",
    "sketch_state"
  ],
  "title": "SketchTextResult",
  "type": "object"
}
```
