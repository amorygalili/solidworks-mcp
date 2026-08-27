# sw_datum_list

List the document's reference geometry — planes, axes, points, and coordinate systems — with their locale-invariant type tokens and capture-ready references.

| | |
|---|---|
| Tier | `core` |
| Domains | `datum`, `reference` |
| Document precondition | `part_or_assembly` |
| Safety | `read` |
| Read-only | True |
| Destructive | False |
| Confirmation required | False |
| Auto-checkpointed | False |
| Idempotent | True |
| Timeout | 180s |
| Satisfies | `DAT-001` |

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
    }
  },
  "title": "DatumListArgs",
  "type": "object"
}
```

## Result schema

```json
{
  "additionalProperties": false,
  "properties": {
    "axes": {
      "items": {
        "additionalProperties": true,
        "type": "object"
      },
      "title": "Axes",
      "type": "array"
    },
    "coordinate_systems": {
      "items": {
        "additionalProperties": true,
        "type": "object"
      },
      "title": "Coordinate Systems",
      "type": "array"
    },
    "origin": {
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
      "title": "Origin"
    },
    "planes": {
      "items": {
        "additionalProperties": true,
        "type": "object"
      },
      "title": "Planes",
      "type": "array"
    },
    "points": {
      "items": {
        "additionalProperties": true,
        "type": "object"
      },
      "title": "Points",
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
  "title": "DatumListResult",
  "type": "object"
}
```
