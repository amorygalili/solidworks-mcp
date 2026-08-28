# sw_equation_set

Add, update, or delete equations and global variables as a batch, reporting each item's outcome and the solver status the change left behind.

| | |
|---|---|
| Tier | `core` |
| Domains | `parameter` |
| Document precondition | `part_or_assembly` |
| Safety | `model_mutation` |
| Read-only | False |
| Destructive | False |
| Confirmation required | False |
| Auto-checkpointed | True |
| Idempotent | False |
| Timeout | 180s |
| Satisfies | `PAR-002` |

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
    "EquationSpec": {
      "additionalProperties": false,
      "description": "One edit to the equation list.",
      "properties": {
        "configuration_scope": {
          "default": "all",
          "description": "Which configurations the equation applies to. Anything but 'all' needs a part with more than one configuration - the API that scopes an equation works only on multi-configuration parts - and cannot be used for a global variable, which SOLIDWORKS requires to apply to every configuration.",
          "enum": [
            "all",
            "this",
            "specify"
          ],
          "title": "Configuration Scope",
          "type": "string"
        },
        "configurations": {
          "description": "Required when configuration_scope is 'specify'; name the current one too.",
          "items": {
            "type": "string"
          },
          "title": "Configurations",
          "type": "array"
        },
        "expression": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "The right-hand side, e.g. '\"Width\" * 2'. Required for add and update.",
          "title": "Expression"
        },
        "global_variable": {
          "default": false,
          "description": "Add as a global variable rather than a dimension equation.",
          "title": "Global Variable",
          "type": "boolean"
        },
        "name": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "The left-hand side, without quotes: a dimension like 'D1@Sketch1' or a global variable like 'Width'. Required for update and delete.",
          "title": "Name"
        },
        "operation": {
          "default": "add",
          "enum": [
            "add",
            "update",
            "delete"
          ],
          "title": "Operation",
          "type": "string"
        }
      },
      "title": "EquationSpec",
      "type": "object"
    }
  },
  "additionalProperties": false,
  "properties": {
    "document": {
      "$ref": "#/$defs/DocTarget",
      "description": "Which document to act on. Defaults to the active document."
    },
    "equations": {
      "items": {
        "$ref": "#/$defs/EquationSpec"
      },
      "maxItems": 200,
      "minItems": 1,
      "title": "Equations",
      "type": "array"
    },
    "preflight": {
      "default": false,
      "description": "Validate and report what would change, without touching the model.",
      "title": "Preflight",
      "type": "boolean"
    },
    "rebuild": {
      "default": true,
      "description": "Rebuild after applying, to pick up errors.",
      "title": "Rebuild",
      "type": "boolean"
    }
  },
  "required": [
    "equations"
  ],
  "title": "EquationSetArgs",
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
    "applied": {
      "title": "Applied",
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
    "circular_references": {
      "items": {
        "items": {
          "type": "string"
        },
        "type": "array"
      },
      "title": "Circular References",
      "type": "array"
    },
    "document_length_unit": {
      "default": "unknown",
      "description": "The unit SOLIDWORKS reads a number that carries no unit of its own in. Equations are text evaluated in document units, so this is what '120' means here.",
      "title": "Document Length Unit",
      "type": "string"
    },
    "failed": {
      "items": {
        "additionalProperties": true,
        "type": "object"
      },
      "title": "Failed",
      "type": "array"
    },
    "rebuild_errors": {
      "items": {
        "type": "string"
      },
      "title": "Rebuild Errors",
      "type": "array"
    },
    "status": {
      "additionalProperties": true,
      "title": "Status",
      "type": "object"
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
    "applied"
  ],
  "title": "EquationSetResult",
  "type": "object"
}
```
