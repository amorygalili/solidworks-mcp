# sw_doc_save

Save a document in place or to a new path, applying the overwrite policy so an existing deliverable is never replaced silently, and verifying the file on disk.

| | |
|---|---|
| Tier | `core` |
| Domains | `document` |
| Document precondition | `any` |
| Safety | `non_model_side_effect` |
| Read-only | False |
| Destructive | False |
| Confirmation required | False |
| Auto-checkpointed | False |
| Idempotent | False |
| Timeout | 300s |
| Side-effect rationale | Writes a CAD file to disk. The default 'version' overwrite policy never replaces an existing file, so the write is additive; replacing one requires overwrite='allow' plus confirm=true, gated inside the handler. |
| Satisfies | `DOC-005`, `SAFE-008` |

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
    "confirm": {
      "default": false,
      "description": "Required only when overwrite='allow'. The default 'version' policy cannot replace an existing file, so it needs no confirmation.",
      "title": "Confirm",
      "type": "boolean"
    },
    "document": {
      "$ref": "#/$defs/DocTarget",
      "description": "Which document to act on. Defaults to the active document."
    },
    "output_path": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Save-as destination. Must be under an allowed output root. Omit to save the document in place, which requires it to have been saved before.",
      "title": "Output Path"
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
    "save_as_copy": {
      "default": false,
      "description": "Write a copy without repointing the open document at the new file.",
      "title": "Save As Copy",
      "type": "boolean"
    }
  },
  "title": "DocSaveArgs",
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
    "action": {
      "description": "create, overwrite, or versioned.",
      "title": "Action",
      "type": "string"
    },
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
    "save_errors": {
      "additionalProperties": true,
      "title": "Save Errors",
      "type": "object"
    },
    "save_warnings": {
      "additionalProperties": true,
      "title": "Save Warnings",
      "type": "object"
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
    "document",
    "saved_path",
    "action"
  ],
  "title": "DocSaveResult",
  "type": "object"
}
```
