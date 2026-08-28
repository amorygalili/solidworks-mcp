# sw_config_list

List the document's configurations with their parent, derived state, rebuild state, and which one is active, so a variant can be addressed by name.

| | |
|---|---|
| Tier | `core` |
| Domains | `parameter` |
| Document precondition | `part_or_assembly` |
| Safety | `read` |
| Read-only | True |
| Destructive | False |
| Confirmation required | False |
| Auto-checkpointed | False |
| Idempotent | True |
| Timeout | 120s |
| Satisfies | `PAR-003` |

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
    },
    "include_properties": {
      "default": false,
      "description": "Include each configuration's custom properties.",
      "title": "Include Properties",
      "type": "boolean"
    }
  },
  "title": "ConfigListArgs",
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
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "title": "Active"
    },
    "configurations": {
      "items": {
        "additionalProperties": true,
        "type": "object"
      },
      "title": "Configurations",
      "type": "array"
    },
    "count": {
      "title": "Count",
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
    "count"
  ],
  "title": "ConfigListResult",
  "type": "object"
}
```
