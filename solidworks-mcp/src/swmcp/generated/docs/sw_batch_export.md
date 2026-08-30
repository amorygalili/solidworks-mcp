# sw_batch_export

Export many documents, configurations, sheets, and formats in one call, writing a JSON manifest that names every file with its size, timestamp, and SHA-256, and reporting each requested output as written, failed, or skipped.

| | |
|---|---|
| Tier | `core` |
| Domains | `exchange`, `document` |
| Document precondition | `none` |
| Safety | `non_model_side_effect` |
| Read-only | False |
| Destructive | False |
| Confirmation required | False |
| Auto-checkpointed | False |
| Idempotent | False |
| Timeout | 3600s |
| Side-effect rationale | Writes each export and a JSON manifest under an allowed output root, and opens the documents it was given. A document opened by this call is opened read-only and closed again afterwards; one that was already open is never closed. No model is modified. |
| Partially satisfies | `IO-004` |

## Input schema

```json
{
  "$defs": {
    "BatchExportItem": {
      "additionalProperties": false,
      "description": "One document, and every file to be written from it.\n\nFormats multiply with configurations: three formats and two configurations is six\nfiles, named so that a person can tell them apart without opening them.",
      "properties": {
        "configurations": {
          "anyOf": [
            {
              "items": {
                "type": "string"
              },
              "maxItems": 32,
              "type": "array"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Export each of these configurations rather than the active one. Parts and assemblies only; a drawing has no configurations of its own.",
          "title": "Configurations"
        },
        "formats": {
          "description": "Formats to write from this document. Neutral and mesh formats need a part or an assembly; PDF, DXF, and DWG need a drawing.",
          "items": {
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
          "maxItems": 13,
          "minItems": 1,
          "title": "Formats",
          "type": "array"
        },
        "name": {
          "anyOf": [
            {
              "maxLength": 120,
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Base filename for this item's outputs. Defaults to the document's own stem. The configuration, when there is one, is appended to it.",
          "title": "Name"
        },
        "sheets": {
          "anyOf": [
            {
              "items": {
                "type": "string"
              },
              "maxItems": 64,
              "type": "array"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Drawing sheets to export. Honoured for PDF only, exactly as in sw_drawing_export; for DXF and DWG the choice is reported as not applied rather than silently dropped.",
          "title": "Sheets"
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
          "description": "A SOLIDWORKS file to export. Opened if it is not already open, and closed again afterwards unless it was open before the batch started.",
          "title": "Source Path"
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
          "description": "Window title of a document already open. Refused if it is ambiguous.",
          "title": "Title"
        }
      },
      "required": [
        "formats"
      ],
      "title": "BatchExportItem",
      "type": "object"
    }
  },
  "additionalProperties": false,
  "description": "IO-004.\n\nThere is deliberately no ``document`` field. Every item addresses its own document,\nbecause a batch whose subject is \"whatever happens to be active\" is a batch that\ncannot be repeated.",
  "properties": {
    "close_opened": {
      "default": true,
      "description": "Close documents this call opened. Documents that were already open are never closed. A document the batch opens is opened read-only, which is what makes closing it safe; one SOLIDWORKS declines to close is reported rather than left unmentioned.",
      "title": "Close Opened",
      "type": "boolean"
    },
    "continue_on_error": {
      "default": true,
      "description": "Keep going when one output fails. False stops at the first failure, and the outputs not attempted are reported as skipped rather than omitted.",
      "title": "Continue On Error",
      "type": "boolean"
    },
    "items": {
      "description": "The documents to export, in the order they will be processed.",
      "items": {
        "$ref": "#/$defs/BatchExportItem"
      },
      "maxItems": 64,
      "minItems": 1,
      "title": "Items",
      "type": "array"
    },
    "manifest_path": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Where to write the JSON manifest. Defaults to batch_manifest.json in output_dir. The manifest obeys the same overwrite policy as the exports, so a re-run does not erase the record of the previous one.",
      "title": "Manifest Path"
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
    "output_dir": {
      "description": "Directory for every written file and, by default, the manifest. Must resolve under an allowed output root.",
      "minLength": 1,
      "title": "Output Dir",
      "type": "string"
    },
    "overwrite": {
      "default": "version",
      "description": "Applied to every written file and to the manifest. 'version' writes name_vNNN when the target exists (default), 'forbid' refuses and proposes a free name, 'allow' replaces the file.",
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
    },
    "stop_when_strained": {
      "default": true,
      "description": "Stop between items once SOLIDWORKS has reached the measured point where calls hang rather than fail. This is the wall, not the 'worth watching' reading sw_health reports \u2014 a slower-than-fresh session keeps working. The remaining outputs are reported as skipped, and the manifest still names everything already written.",
      "title": "Stop When Strained",
      "type": "boolean"
    }
  },
  "required": [
    "items",
    "output_dir"
  ],
  "title": "BatchExportArgs",
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
    },
    "BatchExportEntry": {
      "additionalProperties": false,
      "description": "One planned output. Every entry appears whatever became of it.",
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
          "title": "Configuration"
        },
        "document_type": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "'part', 'assembly', or 'drawing'. None when the document never resolved.",
          "title": "Document Type"
        },
        "duration_s": {
          "default": 0.0,
          "title": "Duration S",
          "type": "number"
        },
        "error": {
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
          "description": "The full error envelope for a failed output.",
          "title": "Error"
        },
        "format": {
          "title": "Format",
          "type": "string"
        },
        "index": {
          "description": "Position in the plan, counting from zero.",
          "title": "Index",
          "type": "integer"
        },
        "item_index": {
          "description": "Which item of the request this came from.",
          "title": "Item Index",
          "type": "integer"
        },
        "overwrite_action": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Overwrite Action"
        },
        "requested_path": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "The path asked for. None when the document never resolved to a name.",
          "title": "Requested Path"
        },
        "saved_path": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Where the file actually went. Differs when it was versioned.",
          "title": "Saved Path"
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
          "description": "SHA-256 of the written file. None for a file over 64 MB, or unwritten.",
          "title": "Sha256"
        },
        "sheets": {
          "items": {
            "type": "string"
          },
          "title": "Sheets",
          "type": "array"
        },
        "signature_detail": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Signature Detail"
        },
        "signature_verified": {
          "anyOf": [
            {
              "type": "boolean"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Whether the bytes matched the format's own signature, not merely that SaveAs returned.",
          "title": "Signature Verified"
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
        "source": {
          "description": "How the document was addressed: a path, a title, or 'active document'.",
          "title": "Source",
          "type": "string"
        },
        "status": {
          "enum": [
            "written",
            "failed",
            "skipped"
          ],
          "title": "Status",
          "type": "string"
        },
        "warnings": {
          "items": {
            "type": "string"
          },
          "title": "Warnings",
          "type": "array"
        }
      },
      "required": [
        "index",
        "item_index",
        "source",
        "format",
        "status"
      ],
      "title": "BatchExportEntry",
      "type": "object"
    }
  },
  "additionalProperties": false,
  "description": "IO-004.\n\n``artifacts`` holds the manifest alone, deliberately. The manifest is the artifact\nindex: it names every file with its size, timestamp, and hash, so repeating two\nhundred evidence records inline would say nothing the manifest does not, at two\nhundred times the size.",
  "properties": {
    "artifacts": {
      "items": {
        "$ref": "#/$defs/ArtifactEvidence"
      },
      "title": "Artifacts",
      "type": "array"
    },
    "documents_closed": {
      "items": {
        "type": "string"
      },
      "title": "Documents Closed",
      "type": "array"
    },
    "documents_left_open": {
      "description": "Documents this call opened but did not close, each with the reason.",
      "items": {
        "type": "string"
      },
      "title": "Documents Left Open",
      "type": "array"
    },
    "documents_opened": {
      "items": {
        "type": "string"
      },
      "title": "Documents Opened",
      "type": "array"
    },
    "entries": {
      "items": {
        "$ref": "#/$defs/BatchExportEntry"
      },
      "title": "Entries",
      "type": "array"
    },
    "manifest_path": {
      "title": "Manifest Path",
      "type": "string"
    },
    "manifest_sha256": {
      "title": "Manifest Sha256",
      "type": "string"
    },
    "output_dir": {
      "title": "Output Dir",
      "type": "string"
    },
    "stop_reason": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "title": "Stop Reason"
    },
    "stopped_early": {
      "default": false,
      "title": "Stopped Early",
      "type": "boolean"
    },
    "totals": {
      "additionalProperties": {
        "type": "integer"
      },
      "description": "planned, written, failed, and skipped. They always sum to planned.",
      "title": "Totals",
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
    "manifest_path",
    "manifest_sha256",
    "output_dir",
    "totals",
    "entries"
  ],
  "title": "BatchExportResult",
  "type": "object"
}
```
