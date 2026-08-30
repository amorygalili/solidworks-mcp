# sw_drawing_new

Create a drawing with an explicit template, sheet size, scale, and projection standard, reading the sheet back so a degenerate one is caught at creation.

| | |
|---|---|
| Tier | `core` |
| Domains | `drawing`, `document` |
| Document precondition | `none` |
| Safety | `non_model_side_effect` |
| Read-only | False |
| Destructive | False |
| Confirmation required | False |
| Auto-checkpointed | False |
| Idempotent | False |
| Timeout | 300s |
| Side-effect rationale | Creates a drawing document in the SOLIDWORKS session and changes what is on screen. Nothing reaches disk until it is saved. |
| Partially satisfies | `DRW-001` |

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
  "description": "DRW-001.",
  "properties": {
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
      "description": "Sheet height. Required for paper_size='custom'.",
      "title": "Height"
    },
    "model_path": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Part or assembly the drawing is for. Omit to use the active document. The model is only recorded here; views are added with sw_drawing_view_add.",
      "title": "Model Path"
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
      "description": "Projection standard for projected views.",
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
      "description": "Sheet scale as [numerator, denominator], e.g. [1, 2] for 1:2.",
      "title": "Scale"
    },
    "sheet_name": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Rename the first sheet.",
      "title": "Sheet Name"
    },
    "template_path": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Explicit drawing template. Omitted means the SOLIDWORKS default.",
      "title": "Template Path"
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
      "description": "Sheet width. Required for paper_size='custom'.",
      "title": "Width"
    }
  },
  "title": "DrawingNewArgs",
  "type": "object"
}
```

## Result schema

```json
{
  "$defs": {
    "ArtifactEvidence": {
      "additionalProperties": false,
      "description": "Proof that a file the operation claims to have written actually exists.",
      "properties": {
        "exists": {
          "title": "Exists",
          "type": "boolean"
        },
        "modified_utc": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Modified Utc"
        },
        "path": {
          "title": "Path",
          "type": "string"
        },
        "sha256": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Sha256"
        },
        "size_bytes": {
          "title": "Size Bytes",
          "type": "integer"
        }
      },
      "required": [
        "path",
        "exists",
        "size_bytes"
      ],
      "title": "ArtifactEvidence",
      "type": "object"
    }
  },
  "additionalProperties": false,
  "properties": {
    "artifacts": {
      "items": {
        "$ref": "#/$defs/ArtifactEvidence"
      },
      "title": "Artifacts",
      "type": "array"
    },
    "document": {
      "additionalProperties": true,
      "title": "Document",
      "type": "object"
    },
    "height_mm": {
      "title": "Height Mm",
      "type": "number"
    },
    "paper_size": {
      "title": "Paper Size",
      "type": "string"
    },
    "projection": {
      "title": "Projection",
      "type": "string"
    },
    "scale": {
      "items": {
        "type": "number"
      },
      "title": "Scale",
      "type": "array"
    },
    "sheet_format": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "The sheet format in use, or null when there is none.",
      "title": "Sheet Format"
    },
    "sheet_name": {
      "title": "Sheet Name",
      "type": "string"
    },
    "template_source": {
      "enum": [
        "explicit",
        "default_preference"
      ],
      "title": "Template Source",
      "type": "string"
    },
    "template_used": {
      "title": "Template Used",
      "type": "string"
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
    "document",
    "sheet_name",
    "paper_size",
    "width_mm",
    "height_mm",
    "scale",
    "projection",
    "template_used",
    "template_source"
  ],
  "title": "DrawingNewResult",
  "type": "object"
}
```
