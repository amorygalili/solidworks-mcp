# sw_drawing_export

Export a drawing, or chosen sheets of it, to PDF, DXF, or DWG, verifying the written file against the format's own signature and reporting what was on the drawing when it was written.

| | |
|---|---|
| Tier | `core` |
| Domains | `drawing`, `exchange` |
| Document precondition | `drawing` |
| Safety | `non_model_side_effect` |
| Read-only | False |
| Destructive | False |
| Confirmation required | False |
| Auto-checkpointed | False |
| Idempotent | False |
| Timeout | 600s |
| Side-effect rationale | Writes a drawing file under an allowed output root, and optionally a PNG preview beside it. The file is reported with its size, timestamp, and SHA-256. Nothing in the model changes. |
| Partially satisfies | `DRW-009` |

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
  "description": "DRW-009.",
  "properties": {
    "document": {
      "$ref": "#/$defs/DocTarget",
      "description": "Which document to act on. Defaults to the active document."
    },
    "output_path": {
      "description": "Where to write the file. The extension picks the format.",
      "minLength": 1,
      "title": "Output Path",
      "type": "string"
    },
    "overwrite": {
      "default": "version",
      "description": "What to do when the file exists. 'version' writes _v002 alongside.",
      "enum": [
        "version",
        "replace",
        "fail"
      ],
      "title": "Overwrite",
      "type": "string"
    },
    "preview_path": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Optional PNG to capture alongside the export, so a person can see what was written. DRW-010: the counts are not a substitute for looking at it.",
      "title": "Preview Path"
    },
    "sheets": {
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
      "description": "Sheet names to export. Omit for every sheet. Only PDF honours a selection; for DXF and DWG SOLIDWORKS writes the active sheet and the choice is reported as not applied rather than silently ignored.",
      "title": "Sheets"
    }
  },
  "required": [
    "output_path"
  ],
  "title": "DrawingExportArgs",
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
    "format": {
      "title": "Format",
      "type": "string"
    },
    "overwrite_action": {
      "title": "Overwrite Action",
      "type": "string"
    },
    "preview_path": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "title": "Preview Path"
    },
    "review": {
      "additionalProperties": true,
      "description": "Counts of what was on the drawing when it was exported.",
      "title": "Review",
      "type": "object"
    },
    "saved_path": {
      "title": "Saved Path",
      "type": "string"
    },
    "sheets_exported": {
      "description": "'all', 'current', or 'specified' - what SOLIDWORKS was actually told.",
      "title": "Sheets Exported",
      "type": "string"
    },
    "sheets_requested": {
      "items": {
        "type": "string"
      },
      "title": "Sheets Requested",
      "type": "array"
    },
    "signature_detail": {
      "title": "Signature Detail",
      "type": "string"
    },
    "signature_verified": {
      "title": "Signature Verified",
      "type": "boolean"
    },
    "size_bytes": {
      "title": "Size Bytes",
      "type": "integer"
    },
    "visual_review_required": {
      "default": true,
      "description": "Always true. A verified PDF header is not a correct drawing.",
      "title": "Visual Review Required",
      "type": "boolean"
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
    "overwrite_action",
    "size_bytes",
    "signature_verified",
    "signature_detail",
    "sheets_exported"
  ],
  "title": "DrawingExportResult",
  "type": "object"
}
```
