# sw_property_list

List custom properties at file level or per configuration, reporting both the raw definition and the evaluated value a drawing or BOM would print.

| | |
|---|---|
| Tier | `core` |
| Domains | `parameter` |
| Document precondition | `any` |
| Safety | `read` |
| Read-only | True |
| Destructive | False |
| Confirmation required | False |
| Auto-checkpointed | False |
| Idempotent | True |
| Timeout | 120s |
| Satisfies | `PAR-006` |

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
    "configuration": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Read this configuration's properties. Omit for the file-level set; use '*' for the file-level set plus every configuration.",
      "title": "Configuration"
    },
    "document": {
      "$ref": "#/$defs/DocTarget",
      "description": "Which document to act on. Defaults to the active document."
    }
  },
  "title": "PropertyListArgs",
  "type": "object"
}
```

## Result schema

```json
{
  "additionalProperties": false,
  "properties": {
    "configuration_properties": {
      "additionalProperties": {
        "items": {
          "additionalProperties": true,
          "type": "object"
        },
        "type": "array"
      },
      "title": "Configuration Properties",
      "type": "object"
    },
    "count": {
      "title": "Count",
      "type": "integer"
    },
    "file_properties": {
      "items": {
        "additionalProperties": true,
        "type": "object"
      },
      "title": "File Properties",
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
  "title": "PropertyListResult",
  "type": "object"
}
```
