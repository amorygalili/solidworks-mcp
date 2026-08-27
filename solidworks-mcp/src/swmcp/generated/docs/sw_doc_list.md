# sw_doc_list

List every open document with its type, path, saved and dirty state, active configuration, and whether it can be checkpointed.

| | |
|---|---|
| Tier | `core` |
| Domains | `document` |
| Document precondition | `none` |
| Safety | `read` |
| Read-only | True |
| Destructive | False |
| Confirmation required | False |
| Auto-checkpointed | False |
| Idempotent | True |
| Timeout | 120s |
| Satisfies | `DOC-003` |

## Input schema

```json
{
  "additionalProperties": false,
  "properties": {},
  "title": "DocListArgs",
  "type": "object"
}
```

## Result schema

```json
{
  "additionalProperties": false,
  "properties": {
    "active": {
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
      "title": "Active"
    },
    "documents": {
      "items": {
        "additionalProperties": true,
        "type": "object"
      },
      "title": "Documents",
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
  "title": "DocListResult",
  "type": "object"
}
```
