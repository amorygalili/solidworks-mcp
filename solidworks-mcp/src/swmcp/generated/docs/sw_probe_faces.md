# sw_probe_faces

Find faces or edges by their geometry — type, radius, area, normal direction, or a point they contain — and return ranked references. This is how to narrow an ambiguous reference down to exactly one entity before acting on it.

| | |
|---|---|
| Tier | `core` |
| Domains | `reference` |
| Document precondition | `part_or_assembly` |
| Safety | `read` |
| Read-only | True |
| Destructive | False |
| Confirmation required | False |
| Auto-checkpointed | False |
| Idempotent | True |
| Timeout | 300s |
| Satisfies | `REF-005`, `REF-006` |

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
    "area_max_mm2": {
      "anyOf": [
        {
          "minimum": 0,
          "type": "number"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Largest acceptable face area, in square millimetres.",
      "title": "Area Max Mm2"
    },
    "area_min_mm2": {
      "anyOf": [
        {
          "minimum": 0,
          "type": "number"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Smallest acceptable face area, in square millimetres.",
      "title": "Area Min Mm2"
    },
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
      "description": "Restrict to this body.",
      "title": "Body Name"
    },
    "contains_point": {
      "anyOf": [
        {
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
          "type": "array"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Keep only entities whose bounding box contains this point.",
      "title": "Contains Point"
    },
    "contains_tolerance": {
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
      "default": 1.0,
      "description": "Slack for contains_point.",
      "title": "Contains Tolerance"
    },
    "document": {
      "$ref": "#/$defs/DocTarget",
      "description": "Which document to act on. Defaults to the active document."
    },
    "entity_class": {
      "default": "face",
      "enum": [
        "face",
        "edge"
      ],
      "title": "Entity Class",
      "type": "string"
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
      "description": "Restrict to the faces or edges of this feature.",
      "title": "Feature Name"
    },
    "geometry_type": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "planar_face, cylindrical_face, conical_face, spherical_face, toroidal_face, bspline_face, line_edge, or circular_edge.",
      "title": "Geometry Type"
    },
    "limit": {
      "default": 50,
      "maximum": 500,
      "minimum": 1,
      "title": "Limit",
      "type": "integer"
    },
    "normal": {
      "anyOf": [
        {
          "items": {
            "type": "number"
          },
          "maxItems": 3,
          "minItems": 3,
          "type": "array"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Direction to match, e.g. [0,0,1] for upward-facing planes.",
      "title": "Normal"
    },
    "normal_within_deg": {
      "default": 5.0,
      "maximum": 180,
      "minimum": 0,
      "title": "Normal Within Deg",
      "type": "number"
    },
    "radius_max": {
      "anyOf": [
        {
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
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Largest acceptable radius.",
      "title": "Radius Max"
    },
    "radius_min": {
      "anyOf": [
        {
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
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Smallest acceptable radius.",
      "title": "Radius Min"
    }
  },
  "title": "ProbeFacesArgs",
  "type": "object"
}
```

## Result schema

```json
{
  "additionalProperties": false,
  "properties": {
    "candidates": {
      "items": {
        "additionalProperties": true,
        "type": "object"
      },
      "title": "Candidates",
      "type": "array"
    },
    "examined": {
      "title": "Examined",
      "type": "integer"
    },
    "hint": {
      "default": "Each candidate carries tool_args ready to paste. If more than one matches, add a filter rather than assuming the first is correct.",
      "title": "Hint",
      "type": "string"
    },
    "matched": {
      "title": "Matched",
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
    "examined",
    "matched"
  ],
  "title": "ProbeFacesResult",
  "type": "object"
}
```
