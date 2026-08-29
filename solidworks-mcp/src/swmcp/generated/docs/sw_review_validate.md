# sw_review_validate

Judge the document against caller-supplied rules and return pass, warn, or block findings, each naming what was read to reach it.

| | |
|---|---|
| Tier | `core` |
| Domains | `review` |
| Document precondition | `any` |
| Safety | `read` |
| Read-only | True |
| Destructive | False |
| Confirmation required | False |
| Auto-checkpointed | False |
| Idempotent | True |
| Timeout | 600s |
| Satisfies | `REV-002`, `REV-007` |

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
    "policy": {
      "$ref": "#/$defs/ReviewPolicy",
      "description": "Rules to apply. Defaults are conservative."
    }
  },
  "title": "ReviewValidateArgs",
  "type": "object"
}
```

## Result schema

```json
{
  "$defs": {
    "ReviewFinding": {
      "additionalProperties": false,
      "properties": {
        "detail": {
          "title": "Detail",
          "type": "string"
        },
        "name": {
          "title": "Name",
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
        "source": {
          "description": "What was read to reach this, so a reader can re-check it.",
          "title": "Source",
          "type": "string"
        }
      },
      "required": [
        "name",
        "outcome",
        "detail",
        "source"
      ],
      "title": "ReviewFinding",
      "type": "object"
    }
  },
  "additionalProperties": false,
  "properties": {
    "blocked": {
      "default": 0,
      "title": "Blocked",
      "type": "integer"
    },
    "findings": {
      "items": {
        "$ref": "#/$defs/ReviewFinding"
      },
      "title": "Findings",
      "type": "array"
    },
    "outcome": {
      "description": "The worst outcome among the findings.",
      "enum": [
        "pass",
        "warn",
        "block"
      ],
      "title": "Outcome",
      "type": "string"
    },
    "passed": {
      "default": 0,
      "title": "Passed",
      "type": "integer"
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
    "outcome"
  ],
  "title": "ReviewValidateResult",
  "type": "object"
}
```
