# sw_review_holes

Audit holes by their B-Rep geometry — cylindrical faces grouped by diameter, with axis and position — and compare them against expected counts.

| | |
|---|---|
| Tier | `core` |
| Domains | `review` |
| Document precondition | `part_or_assembly` |
| Safety | `read` |
| Read-only | True |
| Destructive | False |
| Confirmation required | False |
| Auto-checkpointed | False |
| Idempotent | True |
| Timeout | 600s |
| Partially satisfies | `REV-004` |

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
    },
    "HoleExpectation": {
      "additionalProperties": false,
      "description": "One expected hole group, for comparing a model against an intent.",
      "properties": {
        "count": {
          "minimum": 1,
          "title": "Count",
          "type": "integer"
        },
        "diameter_mm": {
          "exclusiveMinimum": 0,
          "title": "Diameter Mm",
          "type": "number"
        },
        "tolerance_mm": {
          "default": 0.01,
          "description": "How far a measured diameter may differ and still match.",
          "minimum": 0.0,
          "title": "Tolerance Mm",
          "type": "number"
        }
      },
      "required": [
        "diameter_mm",
        "count"
      ],
      "title": "HoleExpectation",
      "type": "object"
    }
  },
  "additionalProperties": false,
  "properties": {
    "document": {
      "$ref": "#/$defs/DocTarget",
      "description": "Which document to act on. Defaults to the active document."
    },
    "expect": {
      "description": "Optional expected hole groups. Without these the tool only reports.",
      "items": {
        "$ref": "#/$defs/HoleExpectation"
      },
      "maxItems": 64,
      "title": "Expect",
      "type": "array"
    },
    "max_diameter_mm": {
      "anyOf": [
        {
          "exclusiveMinimum": 0,
          "type": "number"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Ignore cylindrical faces larger than this.",
      "title": "Max Diameter Mm"
    },
    "min_diameter_mm": {
      "anyOf": [
        {
          "exclusiveMinimum": 0,
          "type": "number"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Ignore cylindrical faces smaller than this.",
      "title": "Min Diameter Mm"
    }
  },
  "title": "ReviewHolesArgs",
  "type": "object"
}
```

## Result schema

```json
{
  "additionalProperties": false,
  "properties": {
    "groups": {
      "description": "Cylindrical faces grouped by diameter.",
      "items": {
        "additionalProperties": true,
        "type": "object"
      },
      "title": "Groups",
      "type": "array"
    },
    "hole_count": {
      "title": "Hole Count",
      "type": "integer"
    },
    "matched": {
      "items": {
        "additionalProperties": true,
        "type": "object"
      },
      "title": "Matched",
      "type": "array"
    },
    "outcome": {
      "default": "pass",
      "enum": [
        "pass",
        "warn",
        "block"
      ],
      "title": "Outcome",
      "type": "string"
    },
    "unmatched": {
      "description": "Expectations no measured group satisfied.",
      "items": {
        "additionalProperties": true,
        "type": "object"
      },
      "title": "Unmatched",
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
    "hole_count"
  ],
  "title": "ReviewHolesResult",
  "type": "object"
}
```
