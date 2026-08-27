# sw_selection_get

Report what is currently selected in SOLIDWORKS, capturing a full reference for each item so the user can point at geometry instead of naming it.

| | |
|---|---|
| Tier | `core` |
| Domains | `selection`, `reference` |
| Document precondition | `any` |
| Safety | `read` |
| Read-only | True |
| Destructive | False |
| Confirmation required | False |
| Auto-checkpointed | False |
| Idempotent | True |
| Timeout | 120s |
| Satisfies | `REF-001` |

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
    "capture_references": {
      "default": true,
      "description": "Capture a full entity reference for each selection, ready to reuse.",
      "title": "Capture References",
      "type": "boolean"
    },
    "document": {
      "$ref": "#/$defs/DocTarget",
      "description": "Which document to act on. Defaults to the active document."
    }
  },
  "title": "SelectionGetArgs",
  "type": "object"
}
```

## Result schema

```json
{
  "additionalProperties": false,
  "properties": {
    "count": {
      "title": "Count",
      "type": "integer"
    },
    "hint": {
      "default": "Each selection carries tool_args that can be pasted into the next call's arguments verbatim.",
      "title": "Hint",
      "type": "string"
    },
    "selections": {
      "items": {
        "additionalProperties": true,
        "type": "object"
      },
      "title": "Selections",
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
  "required": [
    "count"
  ],
  "title": "SelectionGetResult",
  "type": "object"
}
```
