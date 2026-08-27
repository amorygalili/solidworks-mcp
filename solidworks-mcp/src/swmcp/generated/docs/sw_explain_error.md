# sw_explain_error

Explain an error code, an HRESULT, or a SOLIDWORKS status value, returning what it means and the concrete steps that address it.

| | |
|---|---|
| Tier | `extended` |
| Domains | `safety`, `discovery` |
| Document precondition | `none` |
| Safety | `read` |
| Read-only | True |
| Destructive | False |
| Confirmation required | False |
| Auto-checkpointed | False |
| Idempotent | True |
| Timeout | 120s |
| Satisfies | `SAFE-009` |

## Input schema

```json
{
  "additionalProperties": false,
  "properties": {
    "code": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "An error code such as PATH_NOT_ALLOWED.",
      "title": "Code"
    },
    "hresult": {
      "anyOf": [
        {
          "type": "integer"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "A raw HRESULT, signed or unsigned.",
      "title": "Hresult"
    },
    "sw_enum": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "A SOLIDWORKS enum name, e.g. swFileLoadError_e.",
      "title": "Sw Enum"
    },
    "sw_value": {
      "anyOf": [
        {
          "type": "integer"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "A value within sw_enum.",
      "title": "Sw Value"
    }
  },
  "title": "ExplainErrorArgs",
  "type": "object"
}
```

## Result schema

```json
{
  "additionalProperties": false,
  "properties": {
    "explanations": {
      "items": {
        "additionalProperties": true,
        "type": "object"
      },
      "title": "Explanations",
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
  "title": "ExplainErrorResult",
  "type": "object"
}
```
