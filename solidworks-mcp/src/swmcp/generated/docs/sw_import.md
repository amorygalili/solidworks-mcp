# sw_import

Import a STEP, IGES, Parasolid, ACIS, or STL file into a new document, then report the geometry that actually arrived — body counts, volume, and topology — rather than trusting that LoadFile4 returned.

| | |
|---|---|
| Tier | `core` |
| Domains | `exchange` |
| Document precondition | `none` |
| Safety | `non_model_side_effect` |
| Read-only | False |
| Destructive | False |
| Confirmation required | False |
| Auto-checkpointed | False |
| Idempotent | False |
| Timeout | 900s |
| Side-effect rationale | Reads a file and opens a new document in the session. The source file is not modified, and the import preferences it changes are restored afterwards. |
| Partially satisfies | `IO-001` |

## Input schema

```json
{
  "additionalProperties": false,
  "properties": {
    "close_gaps": {
      "default": true,
      "description": "Diagnostics: close gaps between faces.",
      "title": "Close Gaps",
      "type": "boolean"
    },
    "fix_faces": {
      "default": true,
      "description": "Diagnostics: repair faulty faces.",
      "title": "Fix Faces",
      "type": "boolean"
    },
    "format": {
      "anyOf": [
        {
          "enum": [
            "step",
            "iges",
            "parasolid",
            "acis",
            "stl"
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
    "input_path": {
      "description": "File to import. The extension selects the format unless 'format' says otherwise. The file is read, never written.",
      "minLength": 1,
      "title": "Input Path",
      "type": "string"
    },
    "knit": {
      "default": "form_solids",
      "description": "For STEP and IGES: sew the imported faces into solids, or leave them as separate surfaces. Not knitting a closed block yields one sheet body per face and no volume.",
      "enum": [
        "form_solids",
        "do_not_knit"
      ],
      "title": "Knit",
      "type": "string"
    },
    "mesh_body_type": {
      "default": "solid",
      "description": "For STL: what to build from the mesh. SOLIDWORKS defaults to 'graphics', which produces zero bodies and nothing measurable, so this defaults to 'solid' instead. A large mesh converts slowly, and 'graphics' remains the cheap choice when the file is only there to be looked at.",
      "enum": [
        "graphics",
        "surface",
        "solid"
      ],
      "title": "Mesh Body Type",
      "type": "string"
    },
    "mesh_unit": {
      "anyOf": [
        {
          "enum": [
            "mm",
            "cm",
            "m",
            "in",
            "ft"
          ],
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Unit to read an STL in. Mesh formats carry no unit of their own.",
      "title": "Mesh Unit"
    },
    "neutral_units": {
      "default": "file",
      "description": "For STEP and IGES: take the units from the file, or from the part template.",
      "enum": [
        "file",
        "template"
      ],
      "title": "Neutral Units",
      "type": "string"
    },
    "remove_bad_faces": {
      "default": false,
      "description": "Diagnostics: delete faces that cannot be repaired, leaving holes.",
      "title": "Remove Bad Faces",
      "type": "boolean"
    },
    "run_diagnostics": {
      "default": false,
      "description": "Run import diagnostics on the result, which tries to close gaps and repair faces. Reported by what it changed, not by what it returned.",
      "title": "Run Diagnostics",
      "type": "boolean"
    }
  },
  "required": [
    "input_path"
  ],
  "title": "ImportArgs",
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
    "body_count": {
      "title": "Body Count",
      "type": "integer"
    },
    "diagnostics": {
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
      "description": "What import diagnostics changed, if it was run: face counts before and after, not merely the value the call returned.",
      "title": "Diagnostics"
    },
    "document": {
      "additionalProperties": true,
      "description": "The new document the import created.",
      "title": "Document",
      "type": "object"
    },
    "edge_count": {
      "default": 0,
      "title": "Edge Count",
      "type": "integer"
    },
    "face_count": {
      "default": 0,
      "title": "Face Count",
      "type": "integer"
    },
    "format": {
      "title": "Format",
      "type": "string"
    },
    "geometry_found": {
      "description": "Whether the import produced any body this server can measure. False for a mesh brought in as graphics, which is a picture rather than geometry.",
      "title": "Geometry Found",
      "type": "boolean"
    },
    "settings": {
      "additionalProperties": true,
      "description": "The import preferences actually applied.",
      "title": "Settings",
      "type": "object"
    },
    "sheet_body_count": {
      "title": "Sheet Body Count",
      "type": "integer"
    },
    "solid_body_count": {
      "title": "Solid Body Count",
      "type": "integer"
    },
    "source_path": {
      "title": "Source Path",
      "type": "string"
    },
    "surface_area_mm2": {
      "anyOf": [
        {
          "type": "number"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "title": "Surface Area Mm2"
    },
    "volume_mm3": {
      "anyOf": [
        {
          "type": "number"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Total volume of the solid bodies. None when there are none.",
      "title": "Volume Mm3"
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
    "document",
    "format",
    "source_path",
    "geometry_found",
    "body_count",
    "solid_body_count",
    "sheet_body_count"
  ],
  "title": "ImportResult",
  "type": "object"
}
```
