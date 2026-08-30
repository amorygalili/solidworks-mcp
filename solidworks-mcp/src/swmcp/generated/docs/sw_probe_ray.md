# sw_probe_ray

Cast a ray into the model and capture a reference to the first face it hits. Useful when a face is easier to describe by where it is than by what it is.

| | |
|---|---|
| Tier | `extended` |
| Domains | `reference` |
| Document precondition | `part_or_assembly` |
| Safety | `read` |
| Read-only | True |
| Destructive | False |
| Confirmation required | False |
| Auto-checkpointed | False |
| Idempotent | True |
| Timeout | 180s |
| Satisfies | `REF-005` |

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
    "direction": {
      "description": "Ray direction [x, y, z]; need not be normalized.",
      "items": {
        "type": "number"
      },
      "maxItems": 3,
      "minItems": 3,
      "title": "Direction",
      "type": "array"
    },
    "document": {
      "$ref": "#/$defs/DocTarget",
      "description": "Which document to act on. Defaults to the active document."
    },
    "origin": {
      "description": "Ray start point [x, y, z].",
      "items": {
        "anyOf": [
          {
            "type": "number"
          },
          {
            "pattern": "^\\s*[+-]?(\\d+\\.?\\d*|\\.\\d+)([eE][+-]?\\d+)?\\s*\\S*\\s*$",
            "type": "string"
          },
          {
            "additionalProperties": false,
            "properties": {
              "unit": {
                "type": "string"
              },
              "value": {
                "type": "number"
              }
            },
            "required": [
              "value"
            ],
            "type": "object"
          }
        ],
        "description": "Length. A bare number is millimetres; or use '50mm' / '2in' / {'value': 2, 'unit': 'inch'}. Supported units: mm, cm, m, in, ft."
      },
      "maxItems": 3,
      "minItems": 3,
      "title": "Origin",
      "type": "array"
    },
    "radius": {
      "anyOf": [
        {
          "type": "number"
        },
        {
          "pattern": "^\\s*[+-]?(\\d+\\.?\\d*|\\.\\d+)([eE][+-]?\\d+)?\\s*\\S*\\s*$",
          "type": "string"
        },
        {
          "additionalProperties": false,
          "properties": {
            "unit": {
              "type": "string"
            },
            "value": {
              "type": "number"
            }
          },
          "required": [
            "value"
          ],
          "type": "object"
        }
      ],
      "default": 2.0,
      "description": "Hit radius around the ray.",
      "title": "Radius"
    }
  },
  "required": [
    "origin",
    "direction"
  ],
  "title": "ProbeRayArgs",
  "type": "object"
}
```

## Result schema

```json
{
  "additionalProperties": false,
  "properties": {
    "hit": {
      "title": "Hit",
      "type": "boolean"
    },
    "reference": {
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
      "title": "Reference"
    },
    "tool_args": {
      "additionalProperties": true,
      "title": "Tool Args",
      "type": "object"
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
    "hit"
  ],
  "title": "ProbeRayResult",
  "type": "object"
}
```
