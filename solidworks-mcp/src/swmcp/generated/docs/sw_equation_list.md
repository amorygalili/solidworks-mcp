# sw_equation_list

List equations and global variables with their values, what each one reads, and any circular chain, so a parametric change can be planned before it is made.

| | |
|---|---|
| Tier | `core` |
| Domains | `parameter` |
| Document precondition | `part_or_assembly` |
| Safety | `read` |
| Read-only | True |
| Destructive | False |
| Confirmation required | False |
| Auto-checkpointed | False |
| Idempotent | True |
| Timeout | 120s |
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
    }
  },
  "additionalProperties": false,
  "properties": {
    "document": {
      "$ref": "#/$defs/DocTarget",
      "description": "Which document to act on. Defaults to the active document."
    },
    "include_dependencies": {
      "default": true,
      "description": "Also report which equations each one reads, and any circular chain. This is textual analysis of the equation strings, not a solver result.",
      "title": "Include Dependencies",
      "type": "boolean"
    }
  },
  "title": "EquationListArgs",
  "type": "object"
}
```

## Result schema

```json
{
  "additionalProperties": false,
  "properties": {
    "circular_references": {
      "description": "Each cycle found, as the chain of names in it.",
      "items": {
        "items": {
          "type": "string"
        },
        "type": "array"
      },
      "title": "Circular References",
      "type": "array"
    },
    "count": {
      "title": "Count",
      "type": "integer"
    },
    "document_length_unit": {
      "default": "unknown",
      "description": "The unit SOLIDWORKS reads a number that carries no unit of its own in. Equations are text evaluated in document units, so this is what '120' means here.",
      "title": "Document Length Unit",
      "type": "string"
    },
    "equations": {
      "items": {
        "additionalProperties": true,
        "type": "object"
      },
      "title": "Equations",
      "type": "array"
    },
    "global_variables": {
      "items": {
        "additionalProperties": true,
        "type": "object"
      },
      "title": "Global Variables",
      "type": "array"
    },
    "status": {
      "additionalProperties": true,
      "description": "Solver status as reported by SOLIDWORKS.",
      "title": "Status",
      "type": "object"
    },
    "unresolved_references": {
      "description": "Names an equation reads that no equation or dimension defines.",
      "items": {
        "additionalProperties": true,
        "type": "object"
      },
      "title": "Unresolved References",
      "type": "array"
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
    "count"
  ],
  "title": "EquationListResult",
  "type": "object"
}
```
