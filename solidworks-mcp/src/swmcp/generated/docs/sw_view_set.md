# sw_view_set

Orient the viewport to a standard view, set the display mode, and zoom to fit, so a later capture shows the model rather than whatever was last on screen.

| | |
|---|---|
| Tier | `extended` |
| Domains | `view` |
| Document precondition | `part_or_assembly` |
| Safety | `non_model_side_effect` |
| Read-only | False |
| Destructive | False |
| Confirmation required | False |
| Auto-checkpointed | False |
| Idempotent | True |
| Timeout | 120s |
| Side-effect rationale | Changes what the SOLIDWORKS window displays and the view orientation stored with the document. No geometry, feature, or parameter is altered, but the application's visible state is, which a user watching the screen will see. |
| Satisfies | `VIEW-003` |

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
    "clear_selection": {
      "default": true,
      "description": "Deselect first, so highlighted geometry does not colour the view.",
      "title": "Clear Selection",
      "type": "boolean"
    },
    "display_mode": {
      "anyOf": [
        {
          "enum": [
            "wireframe",
            "hidden_lines_removed",
            "hidden_lines_grayed",
            "shaded",
            "shaded_with_edges"
          ],
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "How the model is drawn in the viewport.",
      "title": "Display Mode"
    },
    "document": {
      "$ref": "#/$defs/DocTarget",
      "description": "Which document to act on. Defaults to the active document."
    },
    "fit": {
      "default": true,
      "description": "Zoom to fit after orienting.",
      "title": "Fit",
      "type": "boolean"
    },
    "orientation": {
      "anyOf": [
        {
          "enum": [
            "front",
            "back",
            "left",
            "right",
            "top",
            "bottom",
            "isometric",
            "dimetric",
            "trimetric"
          ],
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Standard view to switch to.",
      "title": "Orientation"
    }
  },
  "title": "ViewSetArgs",
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
    "artifacts": {
      "items": {
        "$ref": "#/$defs/ArtifactEvidence"
      },
      "title": "Artifacts",
      "type": "array"
    },
    "display_mode": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "title": "Display Mode"
    },
    "fitted": {
      "title": "Fitted",
      "type": "boolean"
    },
    "orientation": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "title": "Orientation"
    },
    "selection_cleared": {
      "title": "Selection Cleared",
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
    "fitted",
    "selection_cleared"
  ],
  "title": "ViewSetResult",
  "type": "object"
}
```
