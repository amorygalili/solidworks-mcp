# sw_interference_check

Find where components overlap, reporting each interference's volume and the components involved rather than a pass/fail verdict.

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
| Timeout | 600s |
| Partially satisfies | `MATE-008` |

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
    "ignore_hidden_bodies": {
      "default": false,
      "description": "Skip hidden bodies.",
      "title": "Ignore Hidden Bodies",
      "type": "boolean"
    },
    "include_multibody_part_interferences": {
      "default": false,
      "description": "Also report bodies of one multibody part interfering.",
      "title": "Include Multibody Part Interferences",
      "type": "boolean"
    },
    "treat_coincidence_as_interference": {
      "default": false,
      "description": "Count touching faces as interference. Off by default, as SOLIDWORKS has it.",
      "title": "Treat Coincidence As Interference",
      "type": "boolean"
    },
    "treat_subassemblies_as_components": {
      "default": false,
      "description": "Report a subassembly as one component rather than descending.",
      "title": "Treat Subassemblies As Components",
      "type": "boolean"
    }
  },
  "title": "InterferenceCheckArgs",
  "type": "object"
}
```

## Result schema

```json
{
  "additionalProperties": false,
  "properties": {
    "interference_count": {
      "title": "Interference Count",
      "type": "integer"
    },
    "interferences": {
      "items": {
        "additionalProperties": true,
        "type": "object"
      },
      "title": "Interferences",
      "type": "array"
    },
    "settings": {
      "additionalProperties": {
        "type": "boolean"
      },
      "title": "Settings",
      "type": "object"
    },
    "total_volume_mm3": {
      "default": 0.0,
      "title": "Total Volume Mm3",
      "type": "number"
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
    "interference_count"
  ],
  "title": "InterferenceCheckResult",
  "type": "object"
}
```
