# sw_ref_capture

Capture durable references to the selected entities, emitting the persistent reference, a semantic geometry fallback, and paste-ready arguments together.

| | |
|---|---|
| Tier | `core` |
| Domains | `reference` |
| Document precondition | `any` |
| Safety | `read` |
| Read-only | True |
| Destructive | False |
| Confirmation required | False |
| Auto-checkpointed | False |
| Idempotent | True |
| Timeout | 120s |
| Satisfies | `REF-002`, `REF-003`, `REF-004`, `REF-007` |

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
    "from_selection": {
      "default": true,
      "description": "Capture references for the current UI selection.",
      "title": "From Selection",
      "type": "boolean"
    },
    "selection_index": {
      "anyOf": [
        {
          "minimum": 1,
          "type": "integer"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Capture only this 1-based selection.",
      "title": "Selection Index"
    }
  },
  "title": "RefCaptureArgs",
  "type": "object"
}
```

## Result schema

```json
{
  "additionalProperties": false,
  "properties": {
    "references": {
      "items": {
        "additionalProperties": true,
        "type": "object"
      },
      "title": "References",
      "type": "array"
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
  "title": "RefCaptureResult",
  "type": "object"
}
```
