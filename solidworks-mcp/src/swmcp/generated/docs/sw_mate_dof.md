# sw_mate_dof

Report how constrained each component is and which mates hold it, so an under-constrained component is named rather than discovered when it moves.

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
| Partially satisfies | `MATE-007` |

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
  "description": "MATE-007.",
  "properties": {
    "components": {
      "anyOf": [
        {
          "items": {
            "type": "string"
          },
          "maxItems": 64,
          "type": "array"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Restrict the report to these component instance names.",
      "title": "Components"
    },
    "document": {
      "$ref": "#/$defs/DocTarget",
      "description": "Which document to act on. Defaults to the active document."
    }
  },
  "title": "MateDofArgs",
  "type": "object"
}
```

## Result schema

```json
{
  "additionalProperties": false,
  "properties": {
    "component_count": {
      "title": "Component Count",
      "type": "integer"
    },
    "components": {
      "items": {
        "additionalProperties": true,
        "type": "object"
      },
      "title": "Components",
      "type": "array"
    },
    "fully_constrained": {
      "default": 0,
      "title": "Fully Constrained",
      "type": "integer"
    },
    "over_constrained": {
      "default": 0,
      "title": "Over Constrained",
      "type": "integer"
    },
    "remaining_dofs_available": {
      "default": false,
      "description": "Whether IComponent2::GetRemainingDOFs answered on this build. When false, per-axis travel is not reported and the constrained status is all there is.",
      "title": "Remaining Dofs Available",
      "type": "boolean"
    },
    "under_constrained": {
      "default": 0,
      "title": "Under Constrained",
      "type": "integer"
    },
    "under_constrained_components": {
      "items": {
        "type": "string"
      },
      "title": "Under Constrained Components",
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
    "component_count"
  ],
  "title": "MateDofResult",
  "type": "object"
}
```
