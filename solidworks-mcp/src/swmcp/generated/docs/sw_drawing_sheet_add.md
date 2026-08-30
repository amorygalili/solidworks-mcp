# sw_drawing_sheet_add

Add a sheet with its own size, scale, and projection standard, measured back so a sheet of zero area is refused rather than left to hang the next view.

| | |
|---|---|
| Tier | `core` |
| Domains | `drawing` |
| Document precondition | `drawing` |
| Safety | `model_mutation` |
| Read-only | False |
| Destructive | False |
| Confirmation required | False |
| Auto-checkpointed | True |
| Idempotent | False |
| Timeout | 300s |
| Partially satisfies | `DRW-007` |

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
  "description": "DRW-007.",
  "properties": {
    "activate": {
      "default": true,
      "description": "Make the new sheet current.",
      "title": "Activate",
      "type": "boolean"
    },
    "document": {
      "$ref": "#/$defs/DocTarget",
      "description": "Which document to act on. Defaults to the active document."
    },
    "height": {
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
      "description": "Required for paper_size='custom'.",
      "title": "Height"
    },
    "name": {
      "description": "Name for the new sheet.",
      "minLength": 1,
      "title": "Name",
      "type": "string"
    },
    "paper_size": {
      "default": "a",
      "description": "Sheet size.",
      "enum": [
        "a",
        "a_vertical",
        "b",
        "c",
        "d",
        "e",
        "a4",
        "a4_vertical",
        "a3",
        "a2",
        "a1",
        "a0",
        "custom"
      ],
      "title": "Paper Size",
      "type": "string"
    },
    "projection": {
      "default": "third_angle",
      "enum": [
        "first_angle",
        "third_angle"
      ],
      "title": "Projection",
      "type": "string"
    },
    "scale": {
      "anyOf": [
        {
          "items": {
            "type": "number"
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
      "description": "[numerator, denominator].",
      "title": "Scale"
    },
    "width": {
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
      "description": "Required for paper_size='custom'.",
      "title": "Width"
    }
  },
  "required": [
    "name"
  ],
  "title": "DrawingSheetAddArgs",
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
    "active_sheet": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "title": "Active Sheet"
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
    "height_mm": {
      "title": "Height Mm",
      "type": "number"
    },
    "paper_size": {
      "title": "Paper Size",
      "type": "string"
    },
    "rebuild_errors": {
      "items": {
        "type": "string"
      },
      "title": "Rebuild Errors",
      "type": "array"
    },
    "scale": {
      "items": {
        "type": "number"
      },
      "title": "Scale",
      "type": "array"
    },
    "sheet_name": {
      "title": "Sheet Name",
      "type": "string"
    },
    "sheet_names": {
      "items": {
        "type": "string"
      },
      "title": "Sheet Names",
      "type": "array"
    },
    "sheets_after": {
      "title": "Sheets After",
      "type": "integer"
    },
    "sheets_before": {
      "title": "Sheets Before",
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
    },
    "width_mm": {
      "title": "Width Mm",
      "type": "number"
    }
  },
  "required": [
    "verification",
    "sheet_name",
    "paper_size",
    "width_mm",
    "height_mm",
    "scale",
    "sheets_before",
    "sheets_after"
  ],
  "title": "DrawingSheetAddResult",
  "type": "object"
}
```
