# sw_audit_tail

Read the most recent entries from the append-only write audit, including the checkpoint each mutation was covered by.

| | |
|---|---|
| Tier | `extended` |
| Domains | `safety` |
| Document precondition | `none` |
| Safety | `read` |
| Read-only | True |
| Destructive | False |
| Confirmation required | False |
| Auto-checkpointed | False |
| Idempotent | True |
| Timeout | 120s |
| Satisfies | `SAFE-006` |

## Input schema

```json
{
  "additionalProperties": false,
  "properties": {
    "failures_only": {
      "default": false,
      "title": "Failures Only",
      "type": "boolean"
    },
    "limit": {
      "default": 20,
      "maximum": 200,
      "minimum": 1,
      "title": "Limit",
      "type": "integer"
    },
    "tool": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Only entries for this operation.",
      "title": "Tool"
    }
  },
  "title": "AuditTailArgs",
  "type": "object"
}
```

## Result schema

```json
{
  "additionalProperties": false,
  "properties": {
    "audit_path": {
      "title": "Audit Path",
      "type": "string"
    },
    "entries": {
      "items": {
        "additionalProperties": true,
        "type": "object"
      },
      "title": "Entries",
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
    "audit_path"
  ],
  "title": "AuditTailResult",
  "type": "object"
}
```
