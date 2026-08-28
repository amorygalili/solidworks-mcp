# sw_export

Export the model to a neutral format with explicit tessellation, unit, and protocol settings, then verify the written file against that format's own signature rather than trusting that SaveAs returned.

| | |
|---|---|
| Tier | `core` |
| Domains | `exchange` |
| Document precondition | `part_or_assembly` |
| Safety | `non_model_side_effect` |
| Read-only | False |
| Destructive | False |
| Confirmation required | False |
| Auto-checkpointed | False |
| Idempotent | False |
| Timeout | 600s |
| Side-effect rationale | Writes a file under an allowed output root, and temporarily changes the SOLIDWORKS export preferences it needs, restoring them afterwards. The file is reported with its size, timestamp, and SHA-256. |
| Satisfies | `IO-002` |
| Partially satisfies | `IO-003` |

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
    "configuration": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Export this configuration rather than the active one.",
      "title": "Configuration"
    },
    "document": {
      "$ref": "#/$defs/DocTarget",
      "description": "Which document to act on. Defaults to the active document."
    },
    "format": {
      "anyOf": [
        {
          "enum": [
            "step",
            "iges",
            "stl",
            "3mf",
            "obj",
            "ply",
            "parasolid_text",
            "parasolid_binary",
            "sat",
            "vrml",
            "pdf",
            "dxf",
            "dwg"
          ],
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Override the format implied by the extension. Must agree with it.",
      "title": "Format"
    },
    "mesh_unit": {
      "default": "mm",
      "description": "Unit written into mesh formats, which carry no unit of their own.",
      "enum": [
        "mm",
        "cm",
        "m",
        "in",
        "ft"
      ],
      "title": "Mesh Unit",
      "type": "string"
    },
    "output_path": {
      "description": "Destination under an allowed output root. The extension selects the format unless 'format' says otherwise.",
      "title": "Output Path",
      "type": "string"
    },
    "overwrite": {
      "default": "version",
      "description": "'version' writes name_vNNN when the target exists (default), 'forbid' refuses and proposes a free name, 'allow' replaces the file.",
      "enum": [
        "forbid",
        "version",
        "allow"
      ],
      "title": "Overwrite",
      "type": "string"
    },
    "step_protocol": {
      "default": "ap214",
      "description": "STEP application protocol.",
      "enum": [
        "ap203",
        "ap214",
        "ap242"
      ],
      "title": "Step Protocol",
      "type": "string"
    },
    "stl_binary": {
      "default": true,
      "description": "Write STL as binary rather than ASCII.",
      "title": "Stl Binary",
      "type": "boolean"
    },
    "stl_quality": {
      "default": "fine",
      "description": "Mesh tessellation quality for STL, 3MF, OBJ, and PLY.",
      "enum": [
        "coarse",
        "fine"
      ],
      "title": "Stl Quality",
      "type": "string"
    }
  },
  "required": [
    "output_path"
  ],
  "title": "ExportArgs",
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
    "format": {
      "title": "Format",
      "type": "string"
    },
    "overwrite_action": {
      "enum": [
        "create",
        "overwrite",
        "versioned"
      ],
      "title": "Overwrite Action",
      "type": "string"
    },
    "save_error": {
      "additionalProperties": true,
      "title": "Save Error",
      "type": "object"
    },
    "save_warning": {
      "additionalProperties": true,
      "title": "Save Warning",
      "type": "object"
    },
    "saved_path": {
      "title": "Saved Path",
      "type": "string"
    },
    "settings": {
      "additionalProperties": true,
      "description": "The export settings actually applied.",
      "title": "Settings",
      "type": "object"
    },
    "signature_detail": {
      "title": "Signature Detail",
      "type": "string"
    },
    "signature_verified": {
      "description": "Whether the written file's own header matched the format claimed. False means the format has no signature this server can check, not that the file is wrong \u2014 the reason is in signature_detail.",
      "title": "Signature Verified",
      "type": "boolean"
    },
    "size_bytes": {
      "title": "Size Bytes",
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
    "saved_path",
    "format",
    "overwrite_action",
    "size_bytes",
    "signature_verified",
    "signature_detail"
  ],
  "title": "ExportResult",
  "type": "object"
}
```
