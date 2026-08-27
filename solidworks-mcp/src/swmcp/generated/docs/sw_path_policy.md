# sw_path_policy

Check a path against the output-root policy and the overwrite rules before using it, returning the normalized path and the non-clobbering name that would actually be written.

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
| Satisfies | `SAFE-004`, `SAFE-008` |

## Input schema

```json
{
  "additionalProperties": false,
  "properties": {
    "intent": {
      "default": "output",
      "description": "'output' applies the allowed-roots policy; 'document_input' only normalizes.",
      "pattern": "^(output|document_input)$",
      "title": "Intent",
      "type": "string"
    },
    "overwrite": {
      "default": "version",
      "enum": [
        "forbid",
        "version",
        "allow"
      ],
      "title": "Overwrite",
      "type": "string"
    },
    "path": {
      "description": "A candidate path to evaluate.",
      "minLength": 1,
      "title": "Path",
      "type": "string"
    }
  },
  "required": [
    "path"
  ],
  "title": "PathPolicyArgs",
  "type": "object"
}
```

## Result schema

```json
{
  "additionalProperties": false,
  "properties": {
    "action": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "title": "Action"
    },
    "allowed": {
      "title": "Allowed",
      "type": "boolean"
    },
    "allowed_roots": {
      "items": {
        "type": "string"
      },
      "title": "Allowed Roots",
      "type": "array"
    },
    "exists": {
      "default": false,
      "title": "Exists",
      "type": "boolean"
    },
    "intent": {
      "title": "Intent",
      "type": "string"
    },
    "normalized": {
      "title": "Normalized",
      "type": "string"
    },
    "reason": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "title": "Reason"
    },
    "remediation": {
      "items": {
        "type": "string"
      },
      "title": "Remediation",
      "type": "array"
    },
    "resolved_write_path": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "title": "Resolved Write Path"
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
    "normalized",
    "intent",
    "allowed"
  ],
  "title": "PathPolicyResult",
  "type": "object"
}
```
