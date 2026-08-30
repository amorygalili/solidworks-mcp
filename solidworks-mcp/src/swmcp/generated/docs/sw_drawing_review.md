# sw_drawing_review

Count and locate a drawing's views, dimensions, notes, tables, and dangling annotations against caller-supplied minimums. Never a substitute for a person reading the drawing.

| | |
|---|---|
| Tier | `core` |
| Domains | `drawing`, `review` |
| Document precondition | `drawing` |
| Safety | `read` |
| Read-only | True |
| Destructive | False |
| Confirmation required | False |
| Auto-checkpointed | False |
| Idempotent | True |
| Timeout | 300s |
| Satisfies | `DRW-010` |
| Partially satisfies | `DRW-008` |

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
  "description": "DRW-008. The policy is the caller's; the measurements are this tool's.",
  "properties": {
    "document": {
      "$ref": "#/$defs/DocTarget",
      "description": "Which document to act on. Defaults to the active document."
    },
    "require_dimensions": {
      "default": 0,
      "description": "Fewest dimensions the drawing should carry.",
      "maximum": 500,
      "minimum": 0,
      "title": "Require Dimensions",
      "type": "integer"
    },
    "require_sheet_format": {
      "default": false,
      "description": "Treat a sheet with no format as a finding.",
      "title": "Require Sheet Format",
      "type": "boolean"
    },
    "require_views": {
      "default": 1,
      "description": "Fewest views each sheet should carry.",
      "maximum": 50,
      "minimum": 0,
      "title": "Require Views",
      "type": "integer"
    }
  },
  "title": "DrawingReviewArgs",
  "type": "object"
}
```

## Result schema

```json
{
  "additionalProperties": false,
  "properties": {
    "annotation_count": {
      "title": "Annotation Count",
      "type": "integer"
    },
    "dangling_count": {
      "title": "Dangling Count",
      "type": "integer"
    },
    "dimension_count": {
      "title": "Dimension Count",
      "type": "integer"
    },
    "findings": {
      "items": {
        "additionalProperties": true,
        "type": "object"
      },
      "title": "Findings",
      "type": "array"
    },
    "note_count": {
      "title": "Note Count",
      "type": "integer"
    },
    "passed": {
      "title": "Passed",
      "type": "boolean"
    },
    "sheet_count": {
      "title": "Sheet Count",
      "type": "integer"
    },
    "table_count": {
      "title": "Table Count",
      "type": "integer"
    },
    "view_count": {
      "title": "View Count",
      "type": "integer"
    },
    "visual_review_required": {
      "default": true,
      "description": "Always true. This counts and positions annotations; it does not and cannot judge whether the drawing reads correctly to an engineer.",
      "title": "Visual Review Required",
      "type": "boolean"
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
    "passed",
    "sheet_count",
    "view_count",
    "annotation_count",
    "dimension_count",
    "note_count",
    "table_count",
    "dangling_count"
  ],
  "title": "DrawingReviewResult",
  "type": "object"
}
```
