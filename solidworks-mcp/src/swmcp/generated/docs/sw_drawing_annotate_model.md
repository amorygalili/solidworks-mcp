# sw_drawing_annotate_model

Import model dimensions and annotations into the drawing's views, reporting each one that arrived rather than assuming the import found anything.

| | |
|---|---|
| Tier | `core` |
| Domains | `drawing` |
| Document precondition | `drawing` |
| Safety | `model_mutation` |
| Read-only | False |
| Destructive | False |
| Confirmation required | False |
| Auto-checkpointed | True |
| Idempotent | False |
| Timeout | 300s |
| Partially satisfies | `DRW-004` |

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
  "description": "DRW-004.",
  "properties": {
    "all_views": {
      "default": true,
      "description": "Import into every view, not just the selected one.",
      "title": "All Views",
      "type": "boolean"
    },
    "document": {
      "$ref": "#/$defs/DocTarget",
      "description": "Which document to act on. Defaults to the active document."
    },
    "eliminate_duplicates": {
      "default": true,
      "description": "Drop duplicate dimensions.",
      "title": "Eliminate Duplicates",
      "type": "boolean"
    },
    "hidden_feature_dimensions": {
      "default": false,
      "description": "Include dimensions from hidden features.",
      "title": "Hidden Feature Dimensions",
      "type": "boolean"
    },
    "kinds": {
      "description": "Which model items to import.",
      "items": {
        "enum": [
          "dimensions",
          "notes",
          "datums",
          "geometric_tolerances",
          "cosmetic_threads",
          "surface_finishes",
          "welds",
          "axes",
          "planes",
          "points"
        ],
        "type": "string"
      },
      "maxItems": 10,
      "minItems": 1,
      "title": "Kinds",
      "type": "array"
    },
    "use_sketch_placement": {
      "default": false,
      "description": "Place dimensions where the sketch had them.",
      "title": "Use Sketch Placement",
      "type": "boolean"
    }
  },
  "title": "DrawingAnnotateModelArgs",
  "type": "object"
}
```

## Result schema

```json
{
  "$defs": {
    "Check": {
      "additionalProperties": false,
      "description": "One named invariant asserted after a mutation.",
      "properties": {
        "detail": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Detail"
        },
        "name": {
          "title": "Name",
          "type": "string"
        },
        "passed": {
          "title": "Passed",
          "type": "boolean"
        }
      },
      "required": [
        "name",
        "passed"
      ],
      "title": "Check",
      "type": "object"
    },
    "CheckpointRecord": {
      "additionalProperties": false,
      "description": "What the auto-checkpoint layer did before a mutation ran.",
      "properties": {
        "checkpoint_path": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Checkpoint Path"
        },
        "created_utc": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Created Utc"
        },
        "method": {
          "description": "Never optional: the caller must be able to tell a real snapshot from a skipped one. 'file_copy' does not capture unsaved session state.",
          "enum": [
            "save_as_copy",
            "file_copy",
            "skipped",
            "reused"
          ],
          "title": "Method",
          "type": "string"
        },
        "reason": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Why the checkpoint was skipped or reused.",
          "title": "Reason"
        },
        "size_bytes": {
          "anyOf": [
            {
              "type": "integer"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Size Bytes"
        },
        "source_path": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Source Path"
        }
      },
      "required": [
        "method"
      ],
      "title": "CheckpointRecord",
      "type": "object"
    },
    "Verification": {
      "additionalProperties": false,
      "description": "Evidence that a mutation actually happened, read back out of the model.",
      "properties": {
        "after": {
          "additionalProperties": true,
          "title": "After",
          "type": "object"
        },
        "before": {
          "additionalProperties": true,
          "title": "Before",
          "type": "object"
        },
        "checks": {
          "description": "At least one invariant must be asserted.",
          "items": {
            "$ref": "#/$defs/Check"
          },
          "minItems": 1,
          "title": "Checks",
          "type": "array"
        },
        "read_back": {
          "description": "True only when the post-state was re-read from SOLIDWORKS, not assumed.",
          "title": "Read Back",
          "type": "boolean"
        }
      },
      "required": [
        "read_back",
        "checks"
      ],
      "title": "Verification",
      "type": "object"
    }
  },
  "additionalProperties": false,
  "properties": {
    "annotations": {
      "items": {
        "additionalProperties": true,
        "type": "object"
      },
      "title": "Annotations",
      "type": "array"
    },
    "annotations_after": {
      "title": "Annotations After",
      "type": "integer"
    },
    "annotations_before": {
      "title": "Annotations Before",
      "type": "integer"
    },
    "checkpoint": {
      "anyOf": [
        {
          "$ref": "#/$defs/CheckpointRecord"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Populated by the dispatch pipeline, not by handlers."
    },
    "imported": {
      "title": "Imported",
      "type": "integer"
    },
    "kinds": {
      "items": {
        "type": "string"
      },
      "title": "Kinds",
      "type": "array"
    },
    "rebuild_errors": {
      "items": {
        "type": "string"
      },
      "title": "Rebuild Errors",
      "type": "array"
    },
    "verification": {
      "$ref": "#/$defs/Verification"
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
    "verification",
    "imported",
    "annotations_before",
    "annotations_after"
  ],
  "title": "DrawingAnnotateModelResult",
  "type": "object"
}
```
