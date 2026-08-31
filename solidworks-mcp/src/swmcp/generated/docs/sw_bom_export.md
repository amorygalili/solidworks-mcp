# sw_bom_export

Write a component and property bill of materials to CSV, with a traceability matrix naming every instance behind each quantity and whether each property value came from the configuration or the file. Labelled a precursor, always.

| | |
|---|---|
| Tier | `core` |
| Domains | `exchange`, `assembly` |
| Document precondition | `assembly` |
| Safety | `non_model_side_effect` |
| Read-only | False |
| Destructive | False |
| Confirmation required | False |
| Auto-checkpointed | False |
| Idempotent | False |
| Timeout | 600s |
| Side-effect rationale | Writes one or two CSV files under an allowed output root, each reported with its size, timestamp, and SHA-256. If a configuration is named it is activated to read quantities from and the previous one is restored. No model is modified. |
| Partially satisfies | `IO-007` |

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
  "description": "IO-007.",
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
      "description": "Activate this configuration of the assembly first, and restore the previous one afterwards. Quantities depend on it, because a configuration can suppress components.",
      "title": "Configuration"
    },
    "document": {
      "$ref": "#/$defs/DocTarget",
      "description": "Which document to act on. Defaults to the active document."
    },
    "include_excluded": {
      "default": false,
      "description": "Count components flagged 'Exclude from bill of materials'. Off by default for the same reason, and they are likewise still listed in the matrix.",
      "title": "Include Excluded",
      "type": "boolean"
    },
    "include_suppressed": {
      "default": false,
      "description": "Count suppressed components in the quantities. SOLIDWORKS' own BOM does not, so the default matches it; either way every instance appears in the matrix with its state, so nothing disappears without a record.",
      "title": "Include Suppressed",
      "type": "boolean"
    },
    "matrix": {
      "default": true,
      "description": "Write the traceability matrix. Turning it off leaves the quantities in the BOM unattributable, so it is on by default.",
      "title": "Matrix",
      "type": "boolean"
    },
    "matrix_path": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "CSV destination for the traceability matrix, one row per component instance. Defaults to the BOM path with '_traceability' before the extension. Pass matrix=false to skip it.",
      "title": "Matrix Path"
    },
    "max_depth": {
      "default": 16,
      "description": "How far down the component tree to walk.",
      "maximum": 64,
      "minimum": 1,
      "title": "Max Depth",
      "type": "integer"
    },
    "output_path": {
      "description": "CSV destination for the bill of materials. Must be under an allowed root.",
      "minLength": 1,
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
    "properties": {
      "anyOf": [
        {
          "items": {
            "type": "string"
          },
          "maxItems": 40,
          "type": "array"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Property columns, in this order. Omit to discover them: the union of every property name found on any component, sorted. A named property that no component has still gets a column, so a template stays stable across runs.",
      "title": "Properties"
    },
    "shape": {
      "default": "parts_only",
      "description": "'parts_only' rolls every part in the tree up by part number, 'top_level_only' lists only the assembly's direct children, 'indented' keeps the levels and numbers them 1, 1.1, 1.2, 2.",
      "enum": [
        "parts_only",
        "top_level_only",
        "indented"
      ],
      "title": "Shape",
      "type": "string"
    }
  },
  "required": [
    "output_path"
  ],
  "title": "BomExportArgs",
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
    "BomLine": {
      "additionalProperties": false,
      "description": "One rolled-up line of the bill of materials.",
      "properties": {
        "configuration": {
          "title": "Configuration",
          "type": "string"
        },
        "document_type": {
          "title": "Document Type",
          "type": "string"
        },
        "file_name": {
          "title": "File Name",
          "type": "string"
        },
        "item_number": {
          "title": "Item Number",
          "type": "string"
        },
        "part_number": {
          "title": "Part Number",
          "type": "string"
        },
        "part_number_source": {
          "description": "Which SOLIDWORKS rule produced the part number, decoded from swBOMPartNumberSource_e rather than assumed.",
          "title": "Part Number Source",
          "type": "string"
        },
        "path": {
          "title": "Path",
          "type": "string"
        },
        "properties": {
          "additionalProperties": {
            "type": "string"
          },
          "title": "Properties",
          "type": "object"
        },
        "quantity": {
          "title": "Quantity",
          "type": "integer"
        }
      },
      "required": [
        "item_number",
        "part_number",
        "part_number_source",
        "configuration",
        "quantity",
        "document_type",
        "file_name",
        "path"
      ],
      "title": "BomLine",
      "type": "object"
    }
  },
  "additionalProperties": false,
  "description": "IO-007.\n\n``precursor`` is hard-wired true and says so in ``warnings`` as well. This is\ncomputed from the component tree, and a native SOLIDWORKS BOM applies rules this\ntool does not implement.",
  "properties": {
    "artifacts": {
      "items": {
        "$ref": "#/$defs/ArtifactEvidence"
      },
      "title": "Artifacts",
      "type": "array"
    },
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
    "counted_instances": {
      "description": "Instances that contributed to a quantity, after exclusions.",
      "title": "Counted Instances",
      "type": "integer"
    },
    "excluded_instances": {
      "description": "Instances left out of the quantities. Each is still in the matrix.",
      "title": "Excluded Instances",
      "type": "integer"
    },
    "instance_count": {
      "title": "Instance Count",
      "type": "integer"
    },
    "line_count": {
      "title": "Line Count",
      "type": "integer"
    },
    "lines": {
      "items": {
        "$ref": "#/$defs/BomLine"
      },
      "title": "Lines",
      "type": "array"
    },
    "matrix_path": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "title": "Matrix Path"
    },
    "overwrite_action": {
      "title": "Overwrite Action",
      "type": "string"
    },
    "precursor": {
      "default": true,
      "description": "Always true. This is computed from the component tree, not read from a SOLIDWORKS BOM table, and is not a checked bill of materials until somebody has compared it with a native one.",
      "title": "Precursor",
      "type": "boolean"
    },
    "property_columns": {
      "items": {
        "type": "string"
      },
      "title": "Property Columns",
      "type": "array"
    },
    "property_sources": {
      "additionalProperties": {
        "type": "integer"
      },
      "description": "How many values came from each place: 'configuration', 'file', 'absent'. A column that is entirely 'file' on a configured assembly is worth a look.",
      "title": "Property Sources",
      "type": "object"
    },
    "saved_path": {
      "title": "Saved Path",
      "type": "string"
    },
    "shape": {
      "title": "Shape",
      "type": "string"
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
    "overwrite_action",
    "shape",
    "line_count",
    "instance_count",
    "counted_instances",
    "excluded_instances"
  ],
  "title": "BomExportResult",
  "type": "object"
}
```
