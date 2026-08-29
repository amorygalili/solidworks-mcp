# sw_mate_list

List the assembly's mates with type, alignment, flip, suppression, the components they join, and any limit range or driving value.

| | |
|---|---|
| Tier | `core` |
| Domains | `assembly` |
| Document precondition | `assembly` |
| Safety | `read` |
| Read-only | True |
| Destructive | False |
| Confirmation required | False |
| Auto-checkpointed | False |
| Idempotent | True |
| Timeout | 300s |
| Satisfies | `MATE-004` |

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
    }
  },
  "title": "MateListArgs",
  "type": "object"
}
```

## Result schema

```json
{
  "additionalProperties": false,
  "properties": {
    "mate_count": {
      "title": "Mate Count",
      "type": "integer"
    },
    "mates": {
      "items": {
        "additionalProperties": true,
        "type": "object"
      },
      "title": "Mates",
      "type": "array"
    },
    "suppressed_count": {
      "default": 0,
      "title": "Suppressed Count",
      "type": "integer"
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
    "mate_count"
  ],
  "title": "MateListResult",
  "type": "object"
}
```
