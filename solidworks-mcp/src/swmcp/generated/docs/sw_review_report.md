# sw_review_report

Run a policy review and write it as both machine-readable JSON and a human-readable Markdown table, each finding attributed to what it read.

| | |
|---|---|
| Tier | `core` |
| Domains | `review` |
| Document precondition | `any` |
| Safety | `non_model_side_effect` |
| Read-only | False |
| Destructive | False |
| Confirmation required | False |
| Auto-checkpointed | False |
| Idempotent | False |
| Timeout | 600s |
| Side-effect rationale | Writes two report files under an allowed output root. The model is only read; nothing in the document changes. |
| Partially satisfies | `REV-005` |

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
    "ReviewPolicy": {
      "additionalProperties": false,
      "description": "The rules a review applies. REV-007: the caller owns these, not the server.\n\nEvery field is a rule the caller can turn on, off, or tune. A default set is\nsupplied so a bare call still means something, but nothing here is a rule this\nserver insists on \u2014 a check that cannot be disabled is a policy pretending to be a\nfact.",
      "properties": {
        "forbid_dangling_relations": {
          "default": true,
          "description": "Sketch relations pointing at deleted geometry fail.",
          "title": "Forbid Dangling Relations",
          "type": "boolean"
        },
        "forbid_suppressed_features": {
          "default": false,
          "description": "Suppressed features fail the review.",
          "title": "Forbid Suppressed Features",
          "type": "boolean"
        },
        "forbid_zero_volume": {
          "default": true,
          "description": "A model with no volume is almost always a failed build.",
          "title": "Forbid Zero Volume",
          "type": "boolean"
        },
        "max_volume_mm3": {
          "anyOf": [
            {
              "type": "number"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Upper bound on total volume.",
          "title": "Max Volume Mm3"
        },
        "min_volume_mm3": {
          "anyOf": [
            {
              "type": "number"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Lower bound on total volume.",
          "title": "Min Volume Mm3"
        },
        "require_bodies_min": {
          "anyOf": [
            {
              "type": "integer"
            },
            {
              "type": "null"
            }
          ],
          "default": 1,
          "description": "Fewest solid bodies the model must have. None to skip.",
          "title": "Require Bodies Min"
        },
        "require_fully_defined_sketches": {
          "default": false,
          "description": "Every sketch must be fully defined.",
          "title": "Require Fully Defined Sketches",
          "type": "boolean"
        },
        "require_material": {
          "default": false,
          "description": "The part must have a material assigned.",
          "title": "Require Material",
          "type": "boolean"
        },
        "require_no_feature_errors": {
          "default": true,
          "description": "Any feature reporting an error code fails the review.",
          "title": "Require No Feature Errors",
          "type": "boolean"
        },
        "severity": {
          "additionalProperties": {
            "enum": [
              "pass",
              "warn",
              "block"
            ],
            "type": "string"
          },
          "description": "Override the outcome of a named check, e.g. {'sketches_fully_defined': 'warn'}. Names are the check names in the result.",
          "title": "Severity",
          "type": "object"
        }
      },
      "title": "ReviewPolicy",
      "type": "object"
    }
  },
  "additionalProperties": false,
  "properties": {
    "document": {
      "$ref": "#/$defs/DocTarget",
      "description": "Which document to act on. Defaults to the active document."
    },
    "output_path": {
      "description": "Where to write the report. The extension picks the format: .md for Markdown, .json for JSON. Both are written either way, side by side.",
      "title": "Output Path",
      "type": "string"
    },
    "overwrite": {
      "default": "version",
      "enum": [
        "forbid",
        "version",
        "allow"
      ],
      "title": "Overwrite",
      "type": "string"
    },
    "policy": {
      "$ref": "#/$defs/ReviewPolicy"
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
      "description": "Heading for the Markdown report.",
      "title": "Title"
    }
  },
  "required": [
    "output_path"
  ],
  "title": "ReviewReportArgs",
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
    "blocked": {
      "default": 0,
      "title": "Blocked",
      "type": "integer"
    },
    "finding_count": {
      "title": "Finding Count",
      "type": "integer"
    },
    "json_path": {
      "title": "Json Path",
      "type": "string"
    },
    "markdown_path": {
      "title": "Markdown Path",
      "type": "string"
    },
    "outcome": {
      "enum": [
        "pass",
        "warn",
        "block"
      ],
      "title": "Outcome",
      "type": "string"
    },
    "warned": {
      "default": 0,
      "title": "Warned",
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
    "markdown_path",
    "json_path",
    "outcome",
    "finding_count"
  ],
  "title": "ReviewReportResult",
  "type": "object"
}
```
