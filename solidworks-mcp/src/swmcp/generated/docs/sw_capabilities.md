# sw_capabilities

Probe what this installation can actually do — edition, add-ins, type libraries, and template availability — so a caller can branch on evidence rather than assuming a feature exists.

| | |
|---|---|
| Tier | `extended` |
| Domains | `system`, `discovery` |
| Document precondition | `none` |
| Safety | `read` |
| Read-only | True |
| Destructive | False |
| Confirmation required | False |
| Auto-checkpointed | False |
| Idempotent | True |
| Timeout | 60s |
| Satisfies | `DISC-005` |

## Input schema

```json
{
  "additionalProperties": false,
  "properties": {},
  "title": "CapabilitiesArgs",
  "type": "object"
}
```

## Result schema

```json
{
  "additionalProperties": false,
  "properties": {
    "capabilities": {
      "additionalProperties": true,
      "title": "Capabilities",
      "type": "object"
    },
    "evidence": {
      "additionalProperties": true,
      "description": "What was actually checked, so a claim can be traced to a probe.",
      "title": "Evidence",
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
    "capabilities",
    "evidence"
  ],
  "title": "CapabilitiesResult",
  "type": "object"
}
```
