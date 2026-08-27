# sw_feature_list

List the feature tree in order, with each feature's locale-invariant type token, suppression state, and decoded error, if any.

| | |
|---|---|
| Tier | `core` |
| Domains | `feature` |
| Document precondition | `part_or_assembly` |
| Safety | `read` |
| Read-only | True |
| Destructive | False |
| Confirmation required | False |
| Auto-checkpointed | False |
| Idempotent | True |
| Timeout | 180s |
| Satisfies | `FEAT-015` |

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
    "include_suppressed": {
      "default": true,
      "title": "Include Suppressed",
      "type": "boolean"
    },
    "types": {
      "description": "Filter by GetTypeName2 token, e.g. ['Extrusion', 'Fillet'].",
      "items": {
        "type": "string"
      },
      "maxItems": 50,
      "title": "Types",
      "type": "array"
    }
  },
  "title": "FeatureListArgs",
  "type": "object"
}
```

## Result schema

```json
{
  "additionalProperties": false,
  "properties": {
    "count": {
      "title": "Count",
      "type": "integer"
    },
    "features": {
      "items": {
        "additionalProperties": true,
        "type": "object"
      },
      "title": "Features",
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
  "title": "FeatureListResult",
  "type": "object"
}
```
