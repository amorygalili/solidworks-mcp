# sw_appearance_set

Set the colour, transparency, and shading of the document, a body, a feature, or a face, changing only the values given and reading the result back.

| | |
|---|---|
| Tier | `core` |
| Domains | `view` |
| Document precondition | `part_or_assembly` |
| Safety | `non_model_side_effect` |
| Read-only | False |
| Destructive | False |
| Confirmation required | False |
| Auto-checkpointed | False |
| Idempotent | True |
| Timeout | 180s |
| Side-effect rationale | Changes how the model is displayed and is stored in the document. No geometry, feature, or dimension is created, changed, or removed. |
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
    "ambient": {
      "anyOf": [
        {
          "maximum": 1.0,
          "minimum": 0.0,
          "type": "number"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "title": "Ambient"
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
      "description": "Required when target is 'body'.",
      "title": "Body Name"
    },
    "color": {
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
      "description": "RGB, each 0.0-1.0. Omit to leave the colour alone.",
      "title": "Color"
    },
    "diffuse": {
      "anyOf": [
        {
          "maximum": 1.0,
          "minimum": 0.0,
          "type": "number"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "title": "Diffuse"
    },
    "document": {
      "$ref": "#/$defs/DocTarget",
      "description": "Which document to act on. Defaults to the active document."
    },
    "emission": {
      "anyOf": [
        {
          "maximum": 1.0,
          "minimum": 0.0,
          "type": "number"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "title": "Emission"
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
      "description": "Entity reference to a face; required when target is 'face'.",
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
      "description": "Required when target is 'feature'.",
      "title": "Feature Name"
    },
    "shininess": {
      "anyOf": [
        {
          "maximum": 1.0,
          "minimum": 0.0,
          "type": "number"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "title": "Shininess"
    },
    "specular": {
      "anyOf": [
        {
          "maximum": 1.0,
          "minimum": 0.0,
          "type": "number"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "title": "Specular"
    },
    "target": {
      "default": "document",
      "description": "What the appearance is applied to.",
      "enum": [
        "document",
        "body",
        "feature",
        "face"
      ],
      "title": "Target",
      "type": "string"
    },
    "transparency": {
      "anyOf": [
        {
          "maximum": 1.0,
          "minimum": 0.0,
          "type": "number"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "0 is opaque, 1 is fully transparent.",
      "title": "Transparency"
    }
  },
  "title": "AppearanceSetArgs",
  "type": "object"
}
```

## Result schema

```json
{
  "$defs": {
    "ArtifactEvidence": {
      "additionalProperties": false,
      "description": "Proof that a file the operation claims to have written actually exists.",
      "properties": {
        "exists": {
          "title": "Exists",
          "type": "boolean"
        },
        "modified_utc": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Modified Utc"
        },
        "path": {
          "title": "Path",
          "type": "string"
        },
        "sha256": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Sha256"
        },
        "size_bytes": {
          "title": "Size Bytes",
          "type": "integer"
        }
      },
      "required": [
        "path",
        "exists",
        "size_bytes"
      ],
      "title": "ArtifactEvidence",
      "type": "object"
    }
  },
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
    "artifacts": {
      "items": {
        "$ref": "#/$defs/ArtifactEvidence"
      },
      "title": "Artifacts",
      "type": "array"
    },
    "changed": {
      "items": {
        "type": "string"
      },
      "title": "Changed",
      "type": "array"
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
  "title": "AppearanceResult",
  "type": "object"
}
```
