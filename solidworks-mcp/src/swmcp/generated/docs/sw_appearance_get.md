# sw_appearance_get

Read the colour, transparency, and shading of the document, a body, a feature, or a face, reporting whether the value is its own or inherited.

| | |
|---|---|
| Tier | `core` |
| Domains | `view` |
| Document precondition | `part_or_assembly` |
| Safety | `read` |
| Read-only | True |
| Destructive | False |
| Confirmation required | False |
| Auto-checkpointed | False |
| Idempotent | True |
| Timeout | 120s |
| Satisfies | `VIEW-001` |

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
    "body_name": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "title": "Body Name"
    },
    "document": {
      "$ref": "#/$defs/DocTarget",
      "description": "Which document to act on. Defaults to the active document."
    },
    "face_ref": {
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
      "title": "Face Ref"
    },
    "feature_name": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "title": "Feature Name"
    },
    "target": {
      "default": "document",
      "enum": [
        "document",
        "body",
        "feature",
        "face"
      ],
      "title": "Target",
      "type": "string"
    }
  },
  "title": "AppearanceGetArgs",
  "type": "object"
}
```

## Result schema

```json
{
  "additionalProperties": false,
  "properties": {
    "appearance": {
      "additionalProperties": {
        "type": "number"
      },
      "title": "Appearance",
      "type": "object"
    },
    "applied_to": {
      "title": "Applied To",
      "type": "string"
    },
    "inherited": {
      "default": false,
      "description": "True when the entity has no appearance of its own and shows the document's.",
      "title": "Inherited",
      "type": "boolean"
    },
    "target": {
      "title": "Target",
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
    "target",
    "applied_to"
  ],
  "title": "AppearanceGetResult",
  "type": "object"
}
```
