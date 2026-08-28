# sw_health

Report worker, session, and dependency health without needing an active document. The snapshot answers immediately even while a COM call is stuck, so a wedged worker can still be diagnosed.

| | |
|---|---|
| Tier | `core` |
| Domains | `system`, `safety` |
| Document precondition | `none` |
| Safety | `read` |
| Read-only | True |
| Destructive | False |
| Confirmation required | False |
| Auto-checkpointed | False |
| Idempotent | True |
| Timeout | 30s |
| Satisfies | `SYS-005` |

## Input schema

```json
{
  "additionalProperties": false,
  "properties": {
    "probe": {
      "default": false,
      "description": "Also make a live COM call to confirm SOLIDWORKS answers. Off by default so the snapshot still returns while the worker is wedged.",
      "title": "Probe",
      "type": "boolean"
    }
  },
  "title": "HealthArgs",
  "type": "object"
}
```

## Result schema

```json
{
  "additionalProperties": false,
  "properties": {
    "healthy": {
      "title": "Healthy",
      "type": "boolean"
    },
    "issues": {
      "items": {
        "type": "string"
      },
      "title": "Issues",
      "type": "array"
    },
    "probe": {
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
      "title": "Probe"
    },
    "process": {
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
      "description": "What the SOLIDWORKS process is costing, read through WMI rather than COM so it still answers when every COM call is blocked.",
      "title": "Process"
    },
    "warnings": {
      "description": "Non-fatal problems the caller should see (degraded evidence, fallbacks used).",
      "items": {
        "type": "string"
      },
      "title": "Warnings",
      "type": "array"
    },
    "worker": {
      "additionalProperties": true,
      "title": "Worker",
      "type": "object"
    }
  },
  "required": [
    "healthy",
    "worker"
  ],
  "title": "HealthResult",
  "type": "object"
}
```
