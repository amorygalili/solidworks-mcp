# sw_doc_new

Create a part, assembly, or drawing from an explicit template or the SOLIDWORKS default for that type. Reports which template was actually used.

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
| Idempotent | False |
| Timeout | 180s |
| Side-effect rationale | Creates a document in the SOLIDWORKS session and changes what is on screen. Nothing reaches disk until it is saved. |
| Satisfies | `DOC-001` |

## Input schema

```json
{
  "additionalProperties": false,
  "properties": {
    "activate": {
      "default": true,
      "description": "Make the new document active.",
      "title": "Activate",
      "type": "boolean"
    },
    "doc_type": {
      "description": "Which kind of document to create.",
      "enum": [
        "part",
        "assembly",
        "drawing"
      ],
      "title": "Doc Type",
      "type": "string"
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
      "description": "Explicit template file. When omitted the SOLIDWORKS default template for this document type is used, and the resolved path is reported back.",
      "title": "Template Path"
    }
  },
  "required": [
    "doc_type"
  ],
  "title": "DocNewArgs",
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
    }
  },
  "required": [
    "document",
    "template_used",
    "template_source"
  ],
  "title": "DocNewResult",
  "type": "object"
}
```
