# sw_visibility_set

Hide or show a solid body, or blank a reference plane, axis, point, or sketch, verified by reading the visibility back rather than trusting the call.

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
| Idempotent | True |
| Timeout | 180s |
| Side-effect rationale | Changes what is drawn and is stored in the document. Hidden geometry is still present and still measured; nothing is created or removed. |
| Satisfies | `VIEW-002` |

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
    "document": {
      "$ref": "#/$defs/DocTarget",
      "description": "Which document to act on. Defaults to the active document."
    },
    "name": {
      "description": "Body or feature name.",
      "minLength": 1,
      "title": "Name",
      "type": "string"
    },
    "target": {
      "description": "Bodies hide through IBody2; reference geometry and sketches blank.",
      "enum": [
        "body",
        "feature"
      ],
      "title": "Target",
      "type": "string"
    },
    "visible": {
      "description": "True to show, false to hide.",
      "title": "Visible",
      "type": "boolean"
    }
  },
  "required": [
    "target",
    "name",
    "visible"
  ],
  "title": "VisibilitySetArgs",
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
    "method": {
      "description": "Which SOLIDWORKS call was used, since they differ by type.",
      "title": "Method",
      "type": "string"
    },
    "name": {
      "title": "Name",
      "type": "string"
    },
    "target": {
      "title": "Target",
      "type": "string"
    },
    "visible": {
      "title": "Visible",
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
    "target",
    "name",
    "visible",
    "method"
  ],
  "title": "VisibilitySetResult",
  "type": "object"
}
```
