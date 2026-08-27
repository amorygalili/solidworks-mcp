# sw_system_info

Report the SOLIDWORKS version and service pack, COM registration, install location, session identity, active document, and constant-table provenance.

| | |
|---|---|
| Tier | `core` |
| Domains | `system` |
| Document precondition | `none` |
| Safety | `read` |
| Read-only | True |
| Destructive | False |
| Confirmation required | False |
| Auto-checkpointed | False |
| Idempotent | True |
| Timeout | 120s |
| Satisfies | `SYS-002` |

## Input schema

```json
{
  "additionalProperties": false,
  "properties": {},
  "title": "SystemInfoArgs",
  "type": "object"
}
```

## Result schema

```json
{
  "additionalProperties": false,
  "properties": {
    "info": {
      "additionalProperties": true,
      "description": "Version, ProgID, install, constants table, and active document.",
      "title": "Info",
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
  "required": [
    "info"
  ],
  "title": "SystemInfoResult",
  "type": "object"
}
```
