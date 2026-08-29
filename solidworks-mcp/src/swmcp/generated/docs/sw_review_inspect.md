# sw_review_inspect

Gather the document's feature tree, sketches, bodies, configurations, mass, and metadata into one payload, so a review is one call rather than eight.

| | |
|---|---|
| Tier | `core` |
| Domains | `review` |
| Document precondition | `any` |
| Safety | `read` |
| Read-only | True |
| Destructive | False |
| Confirmation required | False |
| Auto-checkpointed | False |
| Idempotent | True |
| Timeout | 600s |
| Partially satisfies | `REV-001` |

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
    "max_items": {
      "default": 200,
      "description": "Cap per section, so one huge model cannot produce an unusable payload.",
      "maximum": 5000,
      "minimum": 1,
      "title": "Max Items",
      "type": "integer"
    },
    "sections": {
      "description": "Sections to include. Empty means every section that applies.",
      "items": {
        "enum": [
          "document",
          "features",
          "sketches",
          "bodies",
          "configurations",
          "equations",
          "dimensions",
          "properties",
          "components",
          "mass"
        ],
        "type": "string"
      },
      "title": "Sections",
      "type": "array"
    }
  },
  "title": "ReviewInspectArgs",
  "type": "object"
}
```

## Result schema

```json
{
  "additionalProperties": false,
  "properties": {
    "document": {
      "additionalProperties": true,
      "title": "Document",
      "type": "object"
    },
    "sections": {
      "additionalProperties": true,
      "title": "Sections",
      "type": "object"
    },
    "truncated": {
      "description": "Sections cut short by max_items.",
      "items": {
        "type": "string"
      },
      "title": "Truncated",
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
  "title": "ReviewInspectResult",
  "type": "object"
}
```
