# sw_connect

Attach to a running SOLIDWORKS instance, optionally launching one. Reports the version, the ProgID that worked, and the active document.

| | |
|---|---|
| Tier | `core` |
| Domains | `system` |
| Document precondition | `none` |
| Safety | `non_model_side_effect` |
| Read-only | False |
| Destructive | False |
| Confirmation required | False |
| Auto-checkpointed | False |
| Idempotent | True |
| Timeout | 240s |
| Side-effect rationale | With start_if_missing=true this launches SLDWORKS.exe, a visible desktop process. Attaching alone changes nothing. |
| Satisfies | `SYS-001` |

## Input schema

```json
{
  "additionalProperties": false,
  "properties": {
    "start_if_missing": {
      "default": false,
      "description": "Launch SOLIDWORKS if no instance is running. Off by default because starting it is slow and visible on the user's desktop.",
      "title": "Start If Missing",
      "type": "boolean"
    },
    "visible": {
      "default": true,
      "description": "Show the SOLIDWORKS window when launching it.",
      "title": "Visible",
      "type": "boolean"
    }
  },
  "title": "ConnectArgs",
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
    "active_document": {
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
      "title": "Active Document"
    },
    "artifacts": {
      "items": {
        "$ref": "#/$defs/ArtifactEvidence"
      },
      "title": "Artifacts",
      "type": "array"
    },
    "attached": {
      "title": "Attached",
      "type": "boolean"
    },
    "launched": {
      "description": "Whether this call started the SOLIDWORKS process.",
      "title": "Launched",
      "type": "boolean"
    },
    "prog_id": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "title": "Prog Id"
    },
    "revision": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "title": "Revision"
    },
    "warnings": {
      "description": "Non-fatal problems the caller should see (degraded evidence, fallbacks used).",
      "items": {
        "type": "string"
      },
      "title": "Warnings",
      "type": "array"
    },
    "year": {
      "anyOf": [
        {
          "type": "integer"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "title": "Year"
    }
  },
  "required": [
    "attached",
    "launched"
  ],
  "title": "ConnectResult",
  "type": "object"
}
```
