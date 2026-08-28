# sw_safe_execute

Run a sequence of operations under one checkpoint, check the declared invariants afterwards, and roll the whole thing back if any step fails or any invariant does not hold.

| | |
|---|---|
| Tier | `core` |
| Domains | `safety`, `review` |
| Document precondition | `part_or_assembly` |
| Safety | `model_mutation` |
| Read-only | False |
| Destructive | True |
| Confirmation required | True |
| Auto-checkpointed | True |
| Idempotent | False |
| Timeout | 900s |
| Checkpoint | Always fresh: the debounce is bypassed, because this operation restores its own snapshot. |
| Satisfies | `REV-006` |

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
    "Invariants": {
      "additionalProperties": false,
      "description": "What must be true when the sequence finishes.\n\nAn empty set of invariants is allowed and means \"run these steps atomically\"; the\nper-step verification still applies, and a step that fails still triggers rollback.",
      "properties": {
        "body_count": {
          "anyOf": [
            {
              "minimum": 0,
              "type": "integer"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Exact number of solid bodies required at the end.",
          "title": "Body Count"
        },
        "face_count": {
          "anyOf": [
            {
              "minimum": 0,
              "type": "integer"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Exact face count required.",
          "title": "Face Count"
        },
        "forbid_features": {
          "description": "Features that must not exist afterwards.",
          "items": {
            "type": "string"
          },
          "maxItems": 100,
          "title": "Forbid Features",
          "type": "array"
        },
        "max_volume_mm3": {
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
          "title": "Max Volume Mm3"
        },
        "min_volume_mm3": {
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
          "title": "Min Volume Mm3"
        },
        "no_features_in_error": {
          "default": true,
          "description": "Every feature must rebuild without an error code.",
          "title": "No Features In Error",
          "type": "boolean"
        },
        "no_rebuild_errors": {
          "default": true,
          "description": "The final rebuild must report no failure.",
          "title": "No Rebuild Errors",
          "type": "boolean"
        },
        "require_features": {
          "description": "Features that must exist afterwards.",
          "items": {
            "type": "string"
          },
          "maxItems": 100,
          "title": "Require Features",
          "type": "array"
        },
        "volume_change": {
          "anyOf": [
            {
              "enum": [
                "increase",
                "decrease",
                "unchanged"
              ],
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "How the volume must have moved across the whole sequence.",
          "title": "Volume Change"
        }
      },
      "title": "Invariants",
      "type": "object"
    },
    "Step": {
      "additionalProperties": false,
      "description": "One operation in the sequence, named exactly as it would be called directly.",
      "properties": {
        "args": {
          "additionalProperties": true,
          "description": "That operation's own arguments.",
          "title": "Args",
          "type": "object"
        },
        "label": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "A name for this step in the report. Defaults to the tool name.",
          "title": "Label"
        },
        "tool": {
          "description": "Operation name, e.g. 'sw_feature_fillet'.",
          "minLength": 1,
          "title": "Tool",
          "type": "string"
        }
      },
      "required": [
        "tool"
      ],
      "title": "Step",
      "type": "object"
    }
  },
  "additionalProperties": false,
  "properties": {
    "confirm": {
      "const": true,
      "description": "Must be true. This operation is destructive: it can discard model state or overwrite a file.",
      "title": "Confirm",
      "type": "boolean"
    },
    "document": {
      "$ref": "#/$defs/DocTarget",
      "description": "Which document to act on. Defaults to the active document."
    },
    "invariants": {
      "$ref": "#/$defs/Invariants"
    },
    "rebuild": {
      "default": true,
      "description": "Force a rebuild before checking invariants.",
      "title": "Rebuild",
      "type": "boolean"
    },
    "rollback_on_failure": {
      "default": true,
      "description": "Restore the checkpoint if any step fails or any invariant does not hold. Turning this off keeps a partial result, which is occasionally what you want when debugging a sequence.",
      "title": "Rollback On Failure",
      "type": "boolean"
    },
    "steps": {
      "items": {
        "$ref": "#/$defs/Step"
      },
      "maxItems": 50,
      "minItems": 1,
      "title": "Steps",
      "type": "array"
    },
    "stop_on_error": {
      "default": true,
      "description": "Stop at the first failing step rather than trying the rest.",
      "title": "Stop On Error",
      "type": "boolean"
    }
  },
  "required": [
    "steps",
    "confirm"
  ],
  "title": "SafeExecuteArgs",
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
    "completed": {
      "title": "Completed",
      "type": "integer"
    },
    "invariants_checked": {
      "items": {
        "additionalProperties": true,
        "type": "object"
      },
      "title": "Invariants Checked",
      "type": "array"
    },
    "invariants_held": {
      "title": "Invariants Held",
      "type": "boolean"
    },
    "rebuild_errors": {
      "items": {
        "type": "string"
      },
      "title": "Rebuild Errors",
      "type": "array"
    },
    "rollback": {
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
      "description": "Evidence for the restore, when one happened.",
      "title": "Rollback"
    },
    "rolled_back": {
      "title": "Rolled Back",
      "type": "boolean"
    },
    "step_results": {
      "items": {
        "additionalProperties": true,
        "type": "object"
      },
      "title": "Step Results",
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
    "completed",
    "invariants_held",
    "rolled_back"
  ],
  "title": "SafeExecuteResult",
  "type": "object"
}
```
