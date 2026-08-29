# sw_asm_tree

List the assembly's components with path, configuration, quantity, suppression, lightweight, hidden, fixed, envelope, virtual, and broken-reference state.

| | |
|---|---|
| Tier | `core` |
| Domains | `assembly` |
| Document precondition | `assembly` |
| Safety | `read` |
| Read-only | True |
| Destructive | False |
| Confirmation required | False |
| Auto-checkpointed | False |
| Idempotent | True |
| Timeout | 300s |
| Satisfies | `ASM-002` |

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
    "max_depth": {
      "default": 16,
      "description": "Guard against a pathological nesting depth.",
      "maximum": 64,
      "minimum": 1,
      "title": "Max Depth",
      "type": "integer"
    },
    "top_level_only": {
      "default": false,
      "description": "List only the top level rather than walking subassemblies.",
      "title": "Top Level Only",
      "type": "boolean"
    }
  },
  "title": "AsmTreeArgs",
  "type": "object"
}
```

## Result schema

```json
{
  "additionalProperties": false,
  "properties": {
    "broken_references": {
      "description": "Referenced files that are not on disk where the assembly expects them.",
      "items": {
        "type": "string"
      },
      "title": "Broken References",
      "type": "array"
    },
    "component_count": {
      "title": "Component Count",
      "type": "integer"
    },
    "components": {
      "items": {
        "additionalProperties": true,
        "type": "object"
      },
      "title": "Components",
      "type": "array"
    },
    "quantities": {
      "additionalProperties": {
        "type": "integer"
      },
      "description": "Instance count per referenced file path.",
      "title": "Quantities",
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
    "component_count"
  ],
  "title": "AsmTreeResult",
  "type": "object"
}
```
