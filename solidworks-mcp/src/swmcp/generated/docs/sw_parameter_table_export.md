# sw_parameter_table_export

Write every driving dimension, equation, and custom property to a CSV that the import tool reads back, so a design's parameters can be reviewed or edited outside SOLIDWORKS.

| | |
|---|---|
| Tier | `extended` |
| Domains | `parameter` |
| Document precondition | `part_or_assembly` |
| Safety | `non_model_side_effect` |
| Read-only | False |
| Destructive | False |
| Confirmation required | False |
| Auto-checkpointed | False |
| Idempotent | False |
| Timeout | 180s |
| Side-effect rationale | Writes a CSV file under an allowed output root. Nothing in the model changes, but a file leaves the process and is reported with its size, timestamp, and SHA-256. |
| Satisfies | `PAR-005` |

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
      "description": "Read values from this configuration.",
      "title": "Configuration"
    },
    "document": {
      "$ref": "#/$defs/DocTarget",
      "description": "Which document to act on. Defaults to the active document."
    },
    "include": {
      "items": {
        "enum": [
          "dimensions",
          "equations",
          "properties"
        ],
        "type": "string"
      },
      "minItems": 1,
      "title": "Include",
      "type": "array"
    },
    "output_path": {
      "description": "CSV destination. Must be under an allowed output root.",
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
    "unit": {
      "default": "mm",
      "enum": [
        "mm",
        "cm",
        "m",
        "in",
        "ft"
      ],
      "title": "Unit",
      "type": "string"
    }
  },
  "required": [
    "output_path"
  ],
  "title": "ParameterTableExportArgs",
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
    "kinds": {
      "additionalProperties": {
        "type": "integer"
      },
      "title": "Kinds",
      "type": "object"
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
    "row_count": {
      "title": "Row Count",
      "type": "integer"
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
    "row_count",
    "saved_path",
    "overwrite_action"
  ],
  "title": "ParameterTableExportResult",
  "type": "object"
}
```
