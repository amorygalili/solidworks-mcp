# sw_dimension_list

List driving dimensions with their names and values in the requested unit, so a parametric change can address a dimension by name rather than by position.

| | |
|---|---|
| Tier | `core` |
| Domains | `constraint`, `sketch` |
| Document precondition | `part_or_assembly` |
| Safety | `read` |
| Read-only | True |
| Destructive | False |
| Confirmation required | False |
| Auto-checkpointed | False |
| Idempotent | True |
| Timeout | 180s |
| Satisfies | `CON-003` |

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
    "sketch_name": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Restrict to one sketch. Omit for every driving dimension.",
      "title": "Sketch Name"
    },
    "unit": {
      "default": "mm",
      "description": "Unit to report lengths in.",
      "title": "Unit",
      "type": "string"
    }
  },
  "title": "DimensionListArgs",
  "type": "object"
}
```

## Result schema

```json
{
  "additionalProperties": false,
  "properties": {
    "dimensions": {
      "items": {
        "additionalProperties": true,
        "type": "object"
      },
      "title": "Dimensions",
      "type": "array"
    },
    "unit": {
      "title": "Unit",
      "type": "string"
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
    "unit"
  ],
  "title": "DimensionListResult",
  "type": "object"
}
```
