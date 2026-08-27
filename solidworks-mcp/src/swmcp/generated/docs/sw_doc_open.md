# sw_doc_open

Open a SOLIDWORKS document from disk, decoding the load errors and warnings into names and remediation rather than returning raw status integers.

| | |
|---|---|
| Tier | `core` |
| Domains | `document` |
| Document precondition | `none` |
| Safety | `non_model_side_effect` |
| Read-only | False |
| Destructive | False |
| Confirmation required | False |
| Auto-checkpointed | False |
| Idempotent | True |
| Timeout | 300s |
| Side-effect rationale | Loads a document into the session, which can build an import feature tree and take a write lock on the file. The source file is not modified. |
| Satisfies | `DOC-002` |

## Input schema

```json
{
  "additionalProperties": false,
  "properties": {
    "configuration": {
      "default": "",
      "description": "Configuration to activate on open.",
      "title": "Configuration",
      "type": "string"
    },
    "open_read_only": {
      "default": false,
      "description": "Open without taking a write lock on the file.",
      "title": "Open Read Only",
      "type": "boolean"
    },
    "path": {
      "description": "Full path of the document to open.",
      "minLength": 1,
      "title": "Path",
      "type": "string"
    },
    "silent": {
      "default": true,
      "description": "Suppress SOLIDWORKS dialogs during load.",
      "title": "Silent",
      "type": "boolean"
    }
  },
  "required": [
    "path"
  ],
  "title": "DocOpenArgs",
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
      "anyOf": [
        {
          "additionalProperties": true,
          "type": "object"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "title": "Document"
    },
    "load_errors": {
      "additionalProperties": true,
      "title": "Load Errors",
      "type": "object"
    },
    "load_warnings": {
      "additionalProperties": true,
      "title": "Load Warnings",
      "type": "object"
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
  "title": "DocOpenResult",
  "type": "object"
}
```
