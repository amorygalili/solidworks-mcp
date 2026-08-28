# sw_view_capture

Save a PNG or BMP of the model at a requested size, after clearing the selection and fitting the view, and report the pixel size read back out of the written file.

| | |
|---|---|
| Tier | `core` |
| Domains | `view` |
| Document precondition | `part_or_assembly` |
| Safety | `non_model_side_effect` |
| Read-only | False |
| Destructive | False |
| Confirmation required | False |
| Auto-checkpointed | False |
| Idempotent | False |
| Timeout | 180s |
| Side-effect rationale | Writes an image file under an allowed output root, and changes the SOLIDWORKS viewport to take it. The file is reported with its size, timestamp, and SHA-256; the default overwrite policy never replaces one. |
| Satisfies | `VIEW-004` |

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
  "properties": {
    "clear_selection": {
      "default": true,
      "description": "Deselect first, so nothing is highlighted in the image.",
      "title": "Clear Selection",
      "type": "boolean"
    },
    "display_mode": {
      "anyOf": [
        {
          "enum": [
            "wireframe",
            "hidden_lines_removed",
            "hidden_lines_grayed",
            "shaded",
            "shaded_with_edges"
          ],
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "title": "Display Mode"
    },
    "document": {
      "$ref": "#/$defs/DocTarget",
      "description": "Which document to act on. Defaults to the active document."
    },
    "fit": {
      "default": true,
      "description": "Zoom to fit before capturing.",
      "title": "Fit",
      "type": "boolean"
    },
    "height": {
      "default": 960,
      "description": "Image height in pixels.",
      "maximum": 8192,
      "minimum": 64,
      "title": "Height",
      "type": "integer"
    },
    "orientation": {
      "anyOf": [
        {
          "enum": [
            "front",
            "back",
            "left",
            "right",
            "top",
            "bottom",
            "isometric",
            "dimetric",
            "trimetric"
          ],
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Orient the view before capturing. Omit to keep the current one.",
      "title": "Orientation"
    },
    "output_path": {
      "description": "Image destination under an allowed output root. The extension picks the format: .png or .bmp.",
      "title": "Output Path",
      "type": "string"
    },
    "overwrite": {
      "default": "version",
      "description": "'version' writes name_vNNN when the target exists (default), 'forbid' refuses and proposes a free name, 'allow' replaces the file.",
      "enum": [
        "forbid",
        "version",
        "allow"
      ],
      "title": "Overwrite",
      "type": "string"
    },
    "width": {
      "default": 1280,
      "description": "Image width in pixels.",
      "maximum": 8192,
      "minimum": 64,
      "title": "Width",
      "type": "integer"
    }
  },
  "required": [
    "output_path"
  ],
  "title": "ViewCaptureArgs",
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
    "actual_size": {
      "anyOf": [
        {
          "items": {
            "type": "integer"
          },
          "type": "array"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Pixel size read back out of the written file. SOLIDWORKS may not honour the request exactly, and the difference should be visible rather than assumed away.",
      "title": "Actual Size"
    },
    "artifacts": {
      "items": {
        "$ref": "#/$defs/ArtifactEvidence"
      },
      "title": "Artifacts",
      "type": "array"
    },
    "details": {
      "additionalProperties": true,
      "title": "Details",
      "type": "object"
    },
    "display_mode": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "title": "Display Mode"
    },
    "format": {
      "enum": [
        "png",
        "bmp"
      ],
      "title": "Format",
      "type": "string"
    },
    "method": {
      "description": "Which SOLIDWORKS call produced the file.",
      "title": "Method",
      "type": "string"
    },
    "orientation": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "title": "Orientation"
    },
    "overwrite_action": {
      "enum": [
        "create",
        "overwrite",
        "versioned"
      ],
      "title": "Overwrite Action",
      "type": "string"
    },
    "requested_size": {
      "items": {
        "type": "integer"
      },
      "title": "Requested Size",
      "type": "array"
    },
    "saved_path": {
      "title": "Saved Path",
      "type": "string"
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
    "saved_path",
    "format",
    "requested_size",
    "overwrite_action",
    "method"
  ],
  "title": "ViewCaptureResult",
  "type": "object"
}
```
