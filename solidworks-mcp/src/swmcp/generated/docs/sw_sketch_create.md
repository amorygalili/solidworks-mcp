# sw_sketch_create

Open a sketch on a plane, draw a profile into it, and close it - the whole cadence in one call, reporting where every point landed and whether the profile closes.

| | |
|---|---|
| Tier | `core` |
| Domains | `sketch` |
| Document precondition | `part_or_assembly` |
| Safety | `model_mutation` |
| Read-only | False |
| Destructive | False |
| Confirmation required | False |
| Auto-checkpointed | True |
| Idempotent | False |
| Timeout | 300s |
| Satisfies | `SK-001`, `SK-003`, `SK-004` |

## Input schema

```json
{
  "$defs": {
    "Arc3PointEntity": {
      "additionalProperties": false,
      "properties": {
        "construction": {
          "default": false,
          "description": "Create as construction geometry rather than profile geometry.",
          "title": "Construction",
          "type": "boolean"
        },
        "end": {
          "items": {
            "anyOf": [
              {
                "type": "number"
              },
              {
                "pattern": "^\\s*[+-]?(\\d+\\.?\\d*|\\.\\d+)([eE][+-]?\\d+)?\\s*\\S*\\s*$",
                "type": "string"
              },
              {
                "additionalProperties": false,
                "properties": {
                  "unit": {
                    "type": "string"
                  },
                  "value": {
                    "type": "number"
                  }
                },
                "required": [
                  "value"
                ],
                "type": "object"
              }
            ],
            "description": "Length. A bare number is millimetres; or use '50mm' / '2in' / {'value': 2, 'unit': 'inch'}. Supported units: mm, cm, m, in, ft."
          },
          "maxItems": 2,
          "minItems": 2,
          "title": "End",
          "type": "array"
        },
        "start": {
          "items": {
            "anyOf": [
              {
                "type": "number"
              },
              {
                "pattern": "^\\s*[+-]?(\\d+\\.?\\d*|\\.\\d+)([eE][+-]?\\d+)?\\s*\\S*\\s*$",
                "type": "string"
              },
              {
                "additionalProperties": false,
                "properties": {
                  "unit": {
                    "type": "string"
                  },
                  "value": {
                    "type": "number"
                  }
                },
                "required": [
                  "value"
                ],
                "type": "object"
              }
            ],
            "description": "Length. A bare number is millimetres; or use '50mm' / '2in' / {'value': 2, 'unit': 'inch'}. Supported units: mm, cm, m, in, ft."
          },
          "maxItems": 2,
          "minItems": 2,
          "title": "Start",
          "type": "array"
        },
        "through": {
          "items": {
            "anyOf": [
              {
                "type": "number"
              },
              {
                "pattern": "^\\s*[+-]?(\\d+\\.?\\d*|\\.\\d+)([eE][+-]?\\d+)?\\s*\\S*\\s*$",
                "type": "string"
              },
              {
                "additionalProperties": false,
                "properties": {
                  "unit": {
                    "type": "string"
                  },
                  "value": {
                    "type": "number"
                  }
                },
                "required": [
                  "value"
                ],
                "type": "object"
              }
            ],
            "description": "Length. A bare number is millimetres; or use '50mm' / '2in' / {'value': 2, 'unit': 'inch'}. Supported units: mm, cm, m, in, ft."
          },
          "maxItems": 2,
          "minItems": 2,
          "title": "Through",
          "type": "array"
        },
        "type": {
          "const": "arc_3pt",
          "default": "arc_3pt",
          "title": "Type",
          "type": "string"
        }
      },
      "required": [
        "start",
        "end",
        "through"
      ],
      "title": "Arc3PointEntity",
      "type": "object"
    },
    "ArcCenterEntity": {
      "additionalProperties": false,
      "properties": {
        "center": {
          "items": {
            "anyOf": [
              {
                "type": "number"
              },
              {
                "pattern": "^\\s*[+-]?(\\d+\\.?\\d*|\\.\\d+)([eE][+-]?\\d+)?\\s*\\S*\\s*$",
                "type": "string"
              },
              {
                "additionalProperties": false,
                "properties": {
                  "unit": {
                    "type": "string"
                  },
                  "value": {
                    "type": "number"
                  }
                },
                "required": [
                  "value"
                ],
                "type": "object"
              }
            ],
            "description": "Length. A bare number is millimetres; or use '50mm' / '2in' / {'value': 2, 'unit': 'inch'}. Supported units: mm, cm, m, in, ft."
          },
          "maxItems": 2,
          "minItems": 2,
          "title": "Center",
          "type": "array"
        },
        "construction": {
          "default": false,
          "description": "Create as construction geometry rather than profile geometry.",
          "title": "Construction",
          "type": "boolean"
        },
        "direction": {
          "default": "counterclockwise",
          "enum": [
            "clockwise",
            "counterclockwise"
          ],
          "title": "Direction",
          "type": "string"
        },
        "end": {
          "items": {
            "anyOf": [
              {
                "type": "number"
              },
              {
                "pattern": "^\\s*[+-]?(\\d+\\.?\\d*|\\.\\d+)([eE][+-]?\\d+)?\\s*\\S*\\s*$",
                "type": "string"
              },
              {
                "additionalProperties": false,
                "properties": {
                  "unit": {
                    "type": "string"
                  },
                  "value": {
                    "type": "number"
                  }
                },
                "required": [
                  "value"
                ],
                "type": "object"
              }
            ],
            "description": "Length. A bare number is millimetres; or use '50mm' / '2in' / {'value': 2, 'unit': 'inch'}. Supported units: mm, cm, m, in, ft."
          },
          "maxItems": 2,
          "minItems": 2,
          "title": "End",
          "type": "array"
        },
        "start": {
          "items": {
            "anyOf": [
              {
                "type": "number"
              },
              {
                "pattern": "^\\s*[+-]?(\\d+\\.?\\d*|\\.\\d+)([eE][+-]?\\d+)?\\s*\\S*\\s*$",
                "type": "string"
              },
              {
                "additionalProperties": false,
                "properties": {
                  "unit": {
                    "type": "string"
                  },
                  "value": {
                    "type": "number"
                  }
                },
                "required": [
                  "value"
                ],
                "type": "object"
              }
            ],
            "description": "Length. A bare number is millimetres; or use '50mm' / '2in' / {'value': 2, 'unit': 'inch'}. Supported units: mm, cm, m, in, ft."
          },
          "maxItems": 2,
          "minItems": 2,
          "title": "Start",
          "type": "array"
        },
        "type": {
          "const": "arc_center",
          "default": "arc_center",
          "title": "Type",
          "type": "string"
        }
      },
      "required": [
        "center",
        "start",
        "end"
      ],
      "title": "ArcCenterEntity",
      "type": "object"
    },
    "CenterlineEntity": {
      "additionalProperties": false,
      "properties": {
        "construction": {
          "default": false,
          "description": "Create as construction geometry rather than profile geometry.",
          "title": "Construction",
          "type": "boolean"
        },
        "end": {
          "items": {
            "anyOf": [
              {
                "type": "number"
              },
              {
                "pattern": "^\\s*[+-]?(\\d+\\.?\\d*|\\.\\d+)([eE][+-]?\\d+)?\\s*\\S*\\s*$",
                "type": "string"
              },
              {
                "additionalProperties": false,
                "properties": {
                  "unit": {
                    "type": "string"
                  },
                  "value": {
                    "type": "number"
                  }
                },
                "required": [
                  "value"
                ],
                "type": "object"
              }
            ],
            "description": "Length. A bare number is millimetres; or use '50mm' / '2in' / {'value': 2, 'unit': 'inch'}. Supported units: mm, cm, m, in, ft."
          },
          "maxItems": 2,
          "minItems": 2,
          "title": "End",
          "type": "array"
        },
        "start": {
          "items": {
            "anyOf": [
              {
                "type": "number"
              },
              {
                "pattern": "^\\s*[+-]?(\\d+\\.?\\d*|\\.\\d+)([eE][+-]?\\d+)?\\s*\\S*\\s*$",
                "type": "string"
              },
              {
                "additionalProperties": false,
                "properties": {
                  "unit": {
                    "type": "string"
                  },
                  "value": {
                    "type": "number"
                  }
                },
                "required": [
                  "value"
                ],
                "type": "object"
              }
            ],
            "description": "Length. A bare number is millimetres; or use '50mm' / '2in' / {'value': 2, 'unit': 'inch'}. Supported units: mm, cm, m, in, ft."
          },
          "maxItems": 2,
          "minItems": 2,
          "title": "Start",
          "type": "array"
        },
        "type": {
          "const": "centerline",
          "default": "centerline",
          "title": "Type",
          "type": "string"
        }
      },
      "required": [
        "start",
        "end"
      ],
      "title": "CenterlineEntity",
      "type": "object"
    },
    "CircleEntity": {
      "additionalProperties": false,
      "properties": {
        "center": {
          "items": {
            "anyOf": [
              {
                "type": "number"
              },
              {
                "pattern": "^\\s*[+-]?(\\d+\\.?\\d*|\\.\\d+)([eE][+-]?\\d+)?\\s*\\S*\\s*$",
                "type": "string"
              },
              {
                "additionalProperties": false,
                "properties": {
                  "unit": {
                    "type": "string"
                  },
                  "value": {
                    "type": "number"
                  }
                },
                "required": [
                  "value"
                ],
                "type": "object"
              }
            ],
            "description": "Length. A bare number is millimetres; or use '50mm' / '2in' / {'value': 2, 'unit': 'inch'}. Supported units: mm, cm, m, in, ft."
          },
          "maxItems": 2,
          "minItems": 2,
          "title": "Center",
          "type": "array"
        },
        "construction": {
          "default": false,
          "description": "Create as construction geometry rather than profile geometry.",
          "title": "Construction",
          "type": "boolean"
        },
        "radius": {
          "anyOf": [
            {
              "type": "number"
            },
            {
              "pattern": "^\\s*[+-]?(\\d+\\.?\\d*|\\.\\d+)([eE][+-]?\\d+)?\\s*\\S*\\s*$",
              "type": "string"
            },
            {
              "additionalProperties": false,
              "properties": {
                "unit": {
                  "type": "string"
                },
                "value": {
                  "type": "number"
                }
              },
              "required": [
                "value"
              ],
              "type": "object"
            }
          ],
          "description": "Length. A bare number is millimetres; or use '50mm' / '2in' / {'value': 2, 'unit': 'inch'}. Supported units: mm, cm, m, in, ft.",
          "title": "Radius"
        },
        "type": {
          "const": "circle",
          "default": "circle",
          "title": "Type",
          "type": "string"
        }
      },
      "required": [
        "center",
        "radius"
      ],
      "title": "CircleEntity",
      "type": "object"
    },
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
    "DocumentRef": {
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
          "title": "Configuration"
        },
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
          "title": "Title"
        }
      },
      "title": "DocumentRef",
      "type": "object"
    },
    "EllipseEntity": {
      "additionalProperties": false,
      "properties": {
        "center": {
          "items": {
            "anyOf": [
              {
                "type": "number"
              },
              {
                "pattern": "^\\s*[+-]?(\\d+\\.?\\d*|\\.\\d+)([eE][+-]?\\d+)?\\s*\\S*\\s*$",
                "type": "string"
              },
              {
                "additionalProperties": false,
                "properties": {
                  "unit": {
                    "type": "string"
                  },
                  "value": {
                    "type": "number"
                  }
                },
                "required": [
                  "value"
                ],
                "type": "object"
              }
            ],
            "description": "Length. A bare number is millimetres; or use '50mm' / '2in' / {'value': 2, 'unit': 'inch'}. Supported units: mm, cm, m, in, ft."
          },
          "maxItems": 2,
          "minItems": 2,
          "title": "Center",
          "type": "array"
        },
        "construction": {
          "default": false,
          "description": "Create as construction geometry rather than profile geometry.",
          "title": "Construction",
          "type": "boolean"
        },
        "major_axis_point": {
          "items": {
            "anyOf": [
              {
                "type": "number"
              },
              {
                "pattern": "^\\s*[+-]?(\\d+\\.?\\d*|\\.\\d+)([eE][+-]?\\d+)?\\s*\\S*\\s*$",
                "type": "string"
              },
              {
                "additionalProperties": false,
                "properties": {
                  "unit": {
                    "type": "string"
                  },
                  "value": {
                    "type": "number"
                  }
                },
                "required": [
                  "value"
                ],
                "type": "object"
              }
            ],
            "description": "Length. A bare number is millimetres; or use '50mm' / '2in' / {'value': 2, 'unit': 'inch'}. Supported units: mm, cm, m, in, ft."
          },
          "maxItems": 2,
          "minItems": 2,
          "title": "Major Axis Point",
          "type": "array"
        },
        "minor_axis_point": {
          "items": {
            "anyOf": [
              {
                "type": "number"
              },
              {
                "pattern": "^\\s*[+-]?(\\d+\\.?\\d*|\\.\\d+)([eE][+-]?\\d+)?\\s*\\S*\\s*$",
                "type": "string"
              },
              {
                "additionalProperties": false,
                "properties": {
                  "unit": {
                    "type": "string"
                  },
                  "value": {
                    "type": "number"
                  }
                },
                "required": [
                  "value"
                ],
                "type": "object"
              }
            ],
            "description": "Length. A bare number is millimetres; or use '50mm' / '2in' / {'value': 2, 'unit': 'inch'}. Supported units: mm, cm, m, in, ft."
          },
          "maxItems": 2,
          "minItems": 2,
          "title": "Minor Axis Point",
          "type": "array"
        },
        "type": {
          "const": "ellipse",
          "default": "ellipse",
          "title": "Type",
          "type": "string"
        }
      },
      "required": [
        "center",
        "major_axis_point",
        "minor_axis_point"
      ],
      "title": "EllipseEntity",
      "type": "object"
    },
    "EntityRef": {
      "additionalProperties": false,
      "description": "A reference to one SOLIDWORKS entity, in every addressing mode at once.",
      "properties": {
        "captured_at": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Captured At"
        },
        "document": {
          "$ref": "#/$defs/DocumentRef"
        },
        "kind": {
          "default": "unknown",
          "enum": [
            "face",
            "edge",
            "vertex",
            "body",
            "feature",
            "sketch",
            "sketch_segment",
            "plane",
            "axis",
            "point",
            "coordinate_system",
            "component",
            "unknown"
          ],
          "title": "Kind",
          "type": "string"
        },
        "label": {
          "default": "",
          "description": "A human sentence describing the entity.",
          "title": "Label",
          "type": "string"
        },
        "persistent": {
          "anyOf": [
            {
              "$ref": "#/$defs/PersistentRef"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "ref_version": {
          "default": 1,
          "title": "Ref Version",
          "type": "integer"
        },
        "select_hint": {
          "anyOf": [
            {
              "$ref": "#/$defs/SelectHint"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        },
        "semantic": {
          "$ref": "#/$defs/SemanticRef"
        },
        "warnings": {
          "items": {
            "type": "string"
          },
          "title": "Warnings",
          "type": "array"
        }
      },
      "title": "EntityRef",
      "type": "object"
    },
    "LineEntity": {
      "additionalProperties": false,
      "properties": {
        "construction": {
          "default": false,
          "description": "Create as construction geometry rather than profile geometry.",
          "title": "Construction",
          "type": "boolean"
        },
        "end": {
          "items": {
            "anyOf": [
              {
                "type": "number"
              },
              {
                "pattern": "^\\s*[+-]?(\\d+\\.?\\d*|\\.\\d+)([eE][+-]?\\d+)?\\s*\\S*\\s*$",
                "type": "string"
              },
              {
                "additionalProperties": false,
                "properties": {
                  "unit": {
                    "type": "string"
                  },
                  "value": {
                    "type": "number"
                  }
                },
                "required": [
                  "value"
                ],
                "type": "object"
              }
            ],
            "description": "Length. A bare number is millimetres; or use '50mm' / '2in' / {'value': 2, 'unit': 'inch'}. Supported units: mm, cm, m, in, ft."
          },
          "maxItems": 2,
          "minItems": 2,
          "title": "End",
          "type": "array"
        },
        "start": {
          "items": {
            "anyOf": [
              {
                "type": "number"
              },
              {
                "pattern": "^\\s*[+-]?(\\d+\\.?\\d*|\\.\\d+)([eE][+-]?\\d+)?\\s*\\S*\\s*$",
                "type": "string"
              },
              {
                "additionalProperties": false,
                "properties": {
                  "unit": {
                    "type": "string"
                  },
                  "value": {
                    "type": "number"
                  }
                },
                "required": [
                  "value"
                ],
                "type": "object"
              }
            ],
            "description": "Length. A bare number is millimetres; or use '50mm' / '2in' / {'value': 2, 'unit': 'inch'}. Supported units: mm, cm, m, in, ft."
          },
          "maxItems": 2,
          "minItems": 2,
          "title": "Start",
          "type": "array"
        },
        "type": {
          "const": "line",
          "default": "line",
          "title": "Type",
          "type": "string"
        }
      },
      "required": [
        "start",
        "end"
      ],
      "title": "LineEntity",
      "type": "object"
    },
    "PersistentRef": {
      "additionalProperties": false,
      "properties": {
        "captured_revision": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Captured Revision"
        },
        "data_b64": {
          "title": "Data B64",
          "type": "string"
        },
        "scheme": {
          "default": "GetPersistReference3",
          "title": "Scheme",
          "type": "string"
        }
      },
      "required": [
        "data_b64"
      ],
      "title": "PersistentRef",
      "type": "object"
    },
    "PointEntity": {
      "additionalProperties": false,
      "properties": {
        "at": {
          "items": {
            "anyOf": [
              {
                "type": "number"
              },
              {
                "pattern": "^\\s*[+-]?(\\d+\\.?\\d*|\\.\\d+)([eE][+-]?\\d+)?\\s*\\S*\\s*$",
                "type": "string"
              },
              {
                "additionalProperties": false,
                "properties": {
                  "unit": {
                    "type": "string"
                  },
                  "value": {
                    "type": "number"
                  }
                },
                "required": [
                  "value"
                ],
                "type": "object"
              }
            ],
            "description": "Length. A bare number is millimetres; or use '50mm' / '2in' / {'value': 2, 'unit': 'inch'}. Supported units: mm, cm, m, in, ft."
          },
          "maxItems": 2,
          "minItems": 2,
          "title": "At",
          "type": "array"
        },
        "construction": {
          "default": false,
          "description": "Create as construction geometry rather than profile geometry.",
          "title": "Construction",
          "type": "boolean"
        },
        "type": {
          "const": "point",
          "default": "point",
          "title": "Type",
          "type": "string"
        }
      },
      "required": [
        "at"
      ],
      "title": "PointEntity",
      "type": "object"
    },
    "PolygonEntity": {
      "additionalProperties": false,
      "properties": {
        "center": {
          "items": {
            "anyOf": [
              {
                "type": "number"
              },
              {
                "pattern": "^\\s*[+-]?(\\d+\\.?\\d*|\\.\\d+)([eE][+-]?\\d+)?\\s*\\S*\\s*$",
                "type": "string"
              },
              {
                "additionalProperties": false,
                "properties": {
                  "unit": {
                    "type": "string"
                  },
                  "value": {
                    "type": "number"
                  }
                },
                "required": [
                  "value"
                ],
                "type": "object"
              }
            ],
            "description": "Length. A bare number is millimetres; or use '50mm' / '2in' / {'value': 2, 'unit': 'inch'}. Supported units: mm, cm, m, in, ft."
          },
          "maxItems": 2,
          "minItems": 2,
          "title": "Center",
          "type": "array"
        },
        "circumradius": {
          "anyOf": [
            {
              "type": "number"
            },
            {
              "pattern": "^\\s*[+-]?(\\d+\\.?\\d*|\\.\\d+)([eE][+-]?\\d+)?\\s*\\S*\\s*$",
              "type": "string"
            },
            {
              "additionalProperties": false,
              "properties": {
                "unit": {
                  "type": "string"
                },
                "value": {
                  "type": "number"
                }
              },
              "required": [
                "value"
              ],
              "type": "object"
            }
          ],
          "description": "Length. A bare number is millimetres; or use '50mm' / '2in' / {'value': 2, 'unit': 'inch'}. Supported units: mm, cm, m, in, ft.",
          "title": "Circumradius"
        },
        "construction": {
          "default": false,
          "description": "Create as construction geometry rather than profile geometry.",
          "title": "Construction",
          "type": "boolean"
        },
        "inscribed": {
          "default": true,
          "title": "Inscribed",
          "type": "boolean"
        },
        "sides": {
          "maximum": 64,
          "minimum": 3,
          "title": "Sides",
          "type": "integer"
        },
        "type": {
          "const": "polygon",
          "default": "polygon",
          "title": "Type",
          "type": "string"
        }
      },
      "required": [
        "center",
        "circumradius",
        "sides"
      ],
      "title": "PolygonEntity",
      "type": "object"
    },
    "RectCenterEntity": {
      "additionalProperties": false,
      "properties": {
        "center": {
          "items": {
            "anyOf": [
              {
                "type": "number"
              },
              {
                "pattern": "^\\s*[+-]?(\\d+\\.?\\d*|\\.\\d+)([eE][+-]?\\d+)?\\s*\\S*\\s*$",
                "type": "string"
              },
              {
                "additionalProperties": false,
                "properties": {
                  "unit": {
                    "type": "string"
                  },
                  "value": {
                    "type": "number"
                  }
                },
                "required": [
                  "value"
                ],
                "type": "object"
              }
            ],
            "description": "Length. A bare number is millimetres; or use '50mm' / '2in' / {'value': 2, 'unit': 'inch'}. Supported units: mm, cm, m, in, ft."
          },
          "maxItems": 2,
          "minItems": 2,
          "title": "Center",
          "type": "array"
        },
        "construction": {
          "default": false,
          "description": "Create as construction geometry rather than profile geometry.",
          "title": "Construction",
          "type": "boolean"
        },
        "corner": {
          "items": {
            "anyOf": [
              {
                "type": "number"
              },
              {
                "pattern": "^\\s*[+-]?(\\d+\\.?\\d*|\\.\\d+)([eE][+-]?\\d+)?\\s*\\S*\\s*$",
                "type": "string"
              },
              {
                "additionalProperties": false,
                "properties": {
                  "unit": {
                    "type": "string"
                  },
                  "value": {
                    "type": "number"
                  }
                },
                "required": [
                  "value"
                ],
                "type": "object"
              }
            ],
            "description": "Length. A bare number is millimetres; or use '50mm' / '2in' / {'value': 2, 'unit': 'inch'}. Supported units: mm, cm, m, in, ft."
          },
          "maxItems": 2,
          "minItems": 2,
          "title": "Corner",
          "type": "array"
        },
        "type": {
          "const": "rect_center",
          "default": "rect_center",
          "title": "Type",
          "type": "string"
        }
      },
      "required": [
        "center",
        "corner"
      ],
      "title": "RectCenterEntity",
      "type": "object"
    },
    "RectCornerEntity": {
      "additionalProperties": false,
      "properties": {
        "construction": {
          "default": false,
          "description": "Create as construction geometry rather than profile geometry.",
          "title": "Construction",
          "type": "boolean"
        },
        "corner": {
          "items": {
            "anyOf": [
              {
                "type": "number"
              },
              {
                "pattern": "^\\s*[+-]?(\\d+\\.?\\d*|\\.\\d+)([eE][+-]?\\d+)?\\s*\\S*\\s*$",
                "type": "string"
              },
              {
                "additionalProperties": false,
                "properties": {
                  "unit": {
                    "type": "string"
                  },
                  "value": {
                    "type": "number"
                  }
                },
                "required": [
                  "value"
                ],
                "type": "object"
              }
            ],
            "description": "Length. A bare number is millimetres; or use '50mm' / '2in' / {'value': 2, 'unit': 'inch'}. Supported units: mm, cm, m, in, ft."
          },
          "maxItems": 2,
          "minItems": 2,
          "title": "Corner",
          "type": "array"
        },
        "opposite": {
          "items": {
            "anyOf": [
              {
                "type": "number"
              },
              {
                "pattern": "^\\s*[+-]?(\\d+\\.?\\d*|\\.\\d+)([eE][+-]?\\d+)?\\s*\\S*\\s*$",
                "type": "string"
              },
              {
                "additionalProperties": false,
                "properties": {
                  "unit": {
                    "type": "string"
                  },
                  "value": {
                    "type": "number"
                  }
                },
                "required": [
                  "value"
                ],
                "type": "object"
              }
            ],
            "description": "Length. A bare number is millimetres; or use '50mm' / '2in' / {'value': 2, 'unit': 'inch'}. Supported units: mm, cm, m, in, ft."
          },
          "maxItems": 2,
          "minItems": 2,
          "title": "Opposite",
          "type": "array"
        },
        "type": {
          "const": "rect_corner",
          "default": "rect_corner",
          "title": "Type",
          "type": "string"
        }
      },
      "required": [
        "corner",
        "opposite"
      ],
      "title": "RectCornerEntity",
      "type": "object"
    },
    "RefMeasurements": {
      "additionalProperties": false,
      "description": "Geometry sampled at capture time, in API units (metres).",
      "properties": {
        "area_m2": {
          "anyOf": [
            {
              "type": "number"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Area M2"
        },
        "bbox_m": {
          "anyOf": [
            {
              "items": {
                "type": "number"
              },
              "type": "array"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "[xmin, ymin, zmin, xmax, ymax, zmax].",
          "title": "Bbox M"
        },
        "direction": {
          "anyOf": [
            {
              "items": {
                "type": "number"
              },
              "type": "array"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Plane normal, cylinder axis, or edge tangent at the midpoint.",
          "title": "Direction"
        },
        "length_m": {
          "anyOf": [
            {
              "type": "number"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Length M"
        },
        "point_m": {
          "anyOf": [
            {
              "items": {
                "type": "number"
              },
              "type": "array"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "A point on the entity: face centre, edge midpoint, or vertex.",
          "title": "Point M"
        },
        "radius_m": {
          "anyOf": [
            {
              "type": "number"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Radius M"
        }
      },
      "title": "RefMeasurements",
      "type": "object"
    },
    "RefTolerance": {
      "additionalProperties": false,
      "properties": {
        "angular_rad": {
          "default": 1e-06,
          "title": "Angular Rad",
          "type": "number"
        },
        "linear_m": {
          "default": 1e-06,
          "title": "Linear M",
          "type": "number"
        },
        "relative": {
          "default": 0.0001,
          "title": "Relative",
          "type": "number"
        }
      },
      "title": "RefTolerance",
      "type": "object"
    },
    "SelectHint": {
      "additionalProperties": false,
      "description": "Last-resort geometric re-pick information.",
      "properties": {
        "mark": {
          "default": 0,
          "title": "Mark",
          "type": "integer"
        },
        "ray_direction": {
          "anyOf": [
            {
              "items": {
                "type": "number"
              },
              "type": "array"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Ray Direction"
        },
        "ray_origin_m": {
          "anyOf": [
            {
              "items": {
                "type": "number"
              },
              "type": "array"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Ray Origin M"
        },
        "sw_select_type": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Sw Select Type"
        }
      },
      "title": "SelectHint",
      "type": "object"
    },
    "SemanticRef": {
      "additionalProperties": false,
      "description": "The fallback that survives when a persistent reference does not.",
      "properties": {
        "body_name": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Body Name"
        },
        "component_path": {
          "items": {
            "type": "string"
          },
          "title": "Component Path",
          "type": "array"
        },
        "feature_ancestry": {
          "description": "Display names, outermost last.",
          "items": {
            "type": "string"
          },
          "title": "Feature Ancestry",
          "type": "array"
        },
        "feature_type_names": {
          "description": "Locale-invariant GetTypeName2 tokens for the same ancestry.",
          "items": {
            "type": "string"
          },
          "title": "Feature Type Names",
          "type": "array"
        },
        "geometry_type": {
          "default": "unknown",
          "title": "Geometry Type",
          "type": "string"
        },
        "measurements": {
          "$ref": "#/$defs/RefMeasurements"
        },
        "signature": {
          "default": "",
          "description": "Hash of the rounded geometry.",
          "title": "Signature",
          "type": "string"
        },
        "tolerance": {
          "$ref": "#/$defs/RefTolerance"
        }
      },
      "title": "SemanticRef",
      "type": "object"
    },
    "SketchPlaneTarget": {
      "additionalProperties": false,
      "description": "Where a sketch goes. Exactly one of these should be given.",
      "properties": {
        "plane_name": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "A named reference plane.",
          "title": "Plane Name"
        },
        "ref": {
          "anyOf": [
            {
              "$ref": "#/$defs/EntityRef"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "A planar face or datum plane."
        },
        "standard_plane": {
          "anyOf": [
            {
              "enum": [
                "front",
                "top",
                "right"
              ],
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Resolved by position in the feature tree and the locale-invariant RefPlane token, so a non-English SOLIDWORKS works without an alias table.",
          "title": "Standard Plane"
        }
      },
      "title": "SketchPlaneTarget",
      "type": "object"
    },
    "SlotArc3PointEntity": {
      "additionalProperties": false,
      "description": "An arc slot through three points on its centreline.",
      "properties": {
        "add_dimension": {
          "default": false,
          "description": "Add SOLIDWORKS' automatic slot dimension, expressed the way length_type says. Without this the slot is under-defined and length_type does nothing.",
          "title": "Add Dimension",
          "type": "boolean"
        },
        "construction": {
          "default": false,
          "description": "Create as construction geometry rather than profile geometry.",
          "title": "Construction",
          "type": "boolean"
        },
        "end": {
          "items": {
            "anyOf": [
              {
                "type": "number"
              },
              {
                "pattern": "^\\s*[+-]?(\\d+\\.?\\d*|\\.\\d+)([eE][+-]?\\d+)?\\s*\\S*\\s*$",
                "type": "string"
              },
              {
                "additionalProperties": false,
                "properties": {
                  "unit": {
                    "type": "string"
                  },
                  "value": {
                    "type": "number"
                  }
                },
                "required": [
                  "value"
                ],
                "type": "object"
              }
            ],
            "description": "Length. A bare number is millimetres; or use '50mm' / '2in' / {'value': 2, 'unit': 'inch'}. Supported units: mm, cm, m, in, ft."
          },
          "maxItems": 2,
          "minItems": 2,
          "title": "End",
          "type": "array"
        },
        "length_type": {
          "default": "center_to_center",
          "enum": [
            "center_to_center",
            "overall"
          ],
          "title": "Length Type",
          "type": "string"
        },
        "start": {
          "items": {
            "anyOf": [
              {
                "type": "number"
              },
              {
                "pattern": "^\\s*[+-]?(\\d+\\.?\\d*|\\.\\d+)([eE][+-]?\\d+)?\\s*\\S*\\s*$",
                "type": "string"
              },
              {
                "additionalProperties": false,
                "properties": {
                  "unit": {
                    "type": "string"
                  },
                  "value": {
                    "type": "number"
                  }
                },
                "required": [
                  "value"
                ],
                "type": "object"
              }
            ],
            "description": "Length. A bare number is millimetres; or use '50mm' / '2in' / {'value': 2, 'unit': 'inch'}. Supported units: mm, cm, m, in, ft."
          },
          "maxItems": 2,
          "minItems": 2,
          "title": "Start",
          "type": "array"
        },
        "through": {
          "description": "A point the slot centreline passes through.",
          "items": {
            "anyOf": [
              {
                "type": "number"
              },
              {
                "pattern": "^\\s*[+-]?(\\d+\\.?\\d*|\\.\\d+)([eE][+-]?\\d+)?\\s*\\S*\\s*$",
                "type": "string"
              },
              {
                "additionalProperties": false,
                "properties": {
                  "unit": {
                    "type": "string"
                  },
                  "value": {
                    "type": "number"
                  }
                },
                "required": [
                  "value"
                ],
                "type": "object"
              }
            ],
            "description": "Length. A bare number is millimetres; or use '50mm' / '2in' / {'value': 2, 'unit': 'inch'}. Supported units: mm, cm, m, in, ft."
          },
          "maxItems": 2,
          "minItems": 2,
          "title": "Through",
          "type": "array"
        },
        "type": {
          "const": "slot_3point_arc",
          "default": "slot_3point_arc",
          "title": "Type",
          "type": "string"
        },
        "width": {
          "anyOf": [
            {
              "type": "number"
            },
            {
              "pattern": "^\\s*[+-]?(\\d+\\.?\\d*|\\.\\d+)([eE][+-]?\\d+)?\\s*\\S*\\s*$",
              "type": "string"
            },
            {
              "additionalProperties": false,
              "properties": {
                "unit": {
                  "type": "string"
                },
                "value": {
                  "type": "number"
                }
              },
              "required": [
                "value"
              ],
              "type": "object"
            }
          ],
          "description": "Length. A bare number is millimetres; or use '50mm' / '2in' / {'value': 2, 'unit': 'inch'}. Supported units: mm, cm, m, in, ft.",
          "title": "Width"
        }
      },
      "required": [
        "start",
        "end",
        "through",
        "width"
      ],
      "title": "SlotArc3PointEntity",
      "type": "object"
    },
    "SlotArcEntity": {
      "additionalProperties": false,
      "description": "An arc slot swept about a centre point.\n\nA semicircular slot is this with ``start`` and ``end`` diametrically opposite the\ncentre; SOLIDWORKS has no separate semicircular slot type.",
      "properties": {
        "add_dimension": {
          "default": false,
          "description": "Add SOLIDWORKS' automatic slot dimension, expressed the way length_type says. Without this the slot is under-defined and length_type does nothing.",
          "title": "Add Dimension",
          "type": "boolean"
        },
        "center": {
          "items": {
            "anyOf": [
              {
                "type": "number"
              },
              {
                "pattern": "^\\s*[+-]?(\\d+\\.?\\d*|\\.\\d+)([eE][+-]?\\d+)?\\s*\\S*\\s*$",
                "type": "string"
              },
              {
                "additionalProperties": false,
                "properties": {
                  "unit": {
                    "type": "string"
                  },
                  "value": {
                    "type": "number"
                  }
                },
                "required": [
                  "value"
                ],
                "type": "object"
              }
            ],
            "description": "Length. A bare number is millimetres; or use '50mm' / '2in' / {'value': 2, 'unit': 'inch'}. Supported units: mm, cm, m, in, ft."
          },
          "maxItems": 2,
          "minItems": 2,
          "title": "Center",
          "type": "array"
        },
        "construction": {
          "default": false,
          "description": "Create as construction geometry rather than profile geometry.",
          "title": "Construction",
          "type": "boolean"
        },
        "direction": {
          "default": "counterclockwise",
          "enum": [
            "clockwise",
            "counterclockwise"
          ],
          "title": "Direction",
          "type": "string"
        },
        "end": {
          "items": {
            "anyOf": [
              {
                "type": "number"
              },
              {
                "pattern": "^\\s*[+-]?(\\d+\\.?\\d*|\\.\\d+)([eE][+-]?\\d+)?\\s*\\S*\\s*$",
                "type": "string"
              },
              {
                "additionalProperties": false,
                "properties": {
                  "unit": {
                    "type": "string"
                  },
                  "value": {
                    "type": "number"
                  }
                },
                "required": [
                  "value"
                ],
                "type": "object"
              }
            ],
            "description": "Length. A bare number is millimetres; or use '50mm' / '2in' / {'value': 2, 'unit': 'inch'}. Supported units: mm, cm, m, in, ft."
          },
          "maxItems": 2,
          "minItems": 2,
          "title": "End",
          "type": "array"
        },
        "length_type": {
          "default": "center_to_center",
          "enum": [
            "center_to_center",
            "overall"
          ],
          "title": "Length Type",
          "type": "string"
        },
        "start": {
          "items": {
            "anyOf": [
              {
                "type": "number"
              },
              {
                "pattern": "^\\s*[+-]?(\\d+\\.?\\d*|\\.\\d+)([eE][+-]?\\d+)?\\s*\\S*\\s*$",
                "type": "string"
              },
              {
                "additionalProperties": false,
                "properties": {
                  "unit": {
                    "type": "string"
                  },
                  "value": {
                    "type": "number"
                  }
                },
                "required": [
                  "value"
                ],
                "type": "object"
              }
            ],
            "description": "Length. A bare number is millimetres; or use '50mm' / '2in' / {'value': 2, 'unit': 'inch'}. Supported units: mm, cm, m, in, ft."
          },
          "maxItems": 2,
          "minItems": 2,
          "title": "Start",
          "type": "array"
        },
        "type": {
          "const": "slot_arc",
          "default": "slot_arc",
          "title": "Type",
          "type": "string"
        },
        "width": {
          "anyOf": [
            {
              "type": "number"
            },
            {
              "pattern": "^\\s*[+-]?(\\d+\\.?\\d*|\\.\\d+)([eE][+-]?\\d+)?\\s*\\S*\\s*$",
              "type": "string"
            },
            {
              "additionalProperties": false,
              "properties": {
                "unit": {
                  "type": "string"
                },
                "value": {
                  "type": "number"
                }
              },
              "required": [
                "value"
              ],
              "type": "object"
            }
          ],
          "description": "Length. A bare number is millimetres; or use '50mm' / '2in' / {'value': 2, 'unit': 'inch'}. Supported units: mm, cm, m, in, ft.",
          "title": "Width"
        }
      },
      "required": [
        "center",
        "start",
        "end",
        "width"
      ],
      "title": "SlotArcEntity",
      "type": "object"
    },
    "SlotCenterpointEntity": {
      "additionalProperties": false,
      "description": "A straight slot given its middle and one end, rather than both ends.",
      "properties": {
        "add_dimension": {
          "default": false,
          "description": "Add SOLIDWORKS' automatic slot dimension, expressed the way length_type says. Without this the slot is under-defined and length_type does nothing.",
          "title": "Add Dimension",
          "type": "boolean"
        },
        "center": {
          "items": {
            "anyOf": [
              {
                "type": "number"
              },
              {
                "pattern": "^\\s*[+-]?(\\d+\\.?\\d*|\\.\\d+)([eE][+-]?\\d+)?\\s*\\S*\\s*$",
                "type": "string"
              },
              {
                "additionalProperties": false,
                "properties": {
                  "unit": {
                    "type": "string"
                  },
                  "value": {
                    "type": "number"
                  }
                },
                "required": [
                  "value"
                ],
                "type": "object"
              }
            ],
            "description": "Length. A bare number is millimetres; or use '50mm' / '2in' / {'value': 2, 'unit': 'inch'}. Supported units: mm, cm, m, in, ft."
          },
          "maxItems": 2,
          "minItems": 2,
          "title": "Center",
          "type": "array"
        },
        "construction": {
          "default": false,
          "description": "Create as construction geometry rather than profile geometry.",
          "title": "Construction",
          "type": "boolean"
        },
        "end": {
          "items": {
            "anyOf": [
              {
                "type": "number"
              },
              {
                "pattern": "^\\s*[+-]?(\\d+\\.?\\d*|\\.\\d+)([eE][+-]?\\d+)?\\s*\\S*\\s*$",
                "type": "string"
              },
              {
                "additionalProperties": false,
                "properties": {
                  "unit": {
                    "type": "string"
                  },
                  "value": {
                    "type": "number"
                  }
                },
                "required": [
                  "value"
                ],
                "type": "object"
              }
            ],
            "description": "Length. A bare number is millimetres; or use '50mm' / '2in' / {'value': 2, 'unit': 'inch'}. Supported units: mm, cm, m, in, ft."
          },
          "maxItems": 2,
          "minItems": 2,
          "title": "End",
          "type": "array"
        },
        "length_type": {
          "default": "center_to_center",
          "enum": [
            "center_to_center",
            "overall"
          ],
          "title": "Length Type",
          "type": "string"
        },
        "type": {
          "const": "slot_centerpoint",
          "default": "slot_centerpoint",
          "title": "Type",
          "type": "string"
        },
        "width": {
          "anyOf": [
            {
              "type": "number"
            },
            {
              "pattern": "^\\s*[+-]?(\\d+\\.?\\d*|\\.\\d+)([eE][+-]?\\d+)?\\s*\\S*\\s*$",
              "type": "string"
            },
            {
              "additionalProperties": false,
              "properties": {
                "unit": {
                  "type": "string"
                },
                "value": {
                  "type": "number"
                }
              },
              "required": [
                "value"
              ],
              "type": "object"
            }
          ],
          "description": "Length. A bare number is millimetres; or use '50mm' / '2in' / {'value': 2, 'unit': 'inch'}. Supported units: mm, cm, m, in, ft.",
          "title": "Width"
        }
      },
      "required": [
        "center",
        "end",
        "width"
      ],
      "title": "SlotCenterpointEntity",
      "type": "object"
    },
    "SlotStraightEntity": {
      "additionalProperties": false,
      "description": "A straight slot between two centre points.",
      "properties": {
        "add_dimension": {
          "default": false,
          "description": "Add SOLIDWORKS' automatic slot dimension, expressed the way length_type says. Without this the slot is under-defined and length_type does nothing.",
          "title": "Add Dimension",
          "type": "boolean"
        },
        "construction": {
          "default": false,
          "description": "Create as construction geometry rather than profile geometry.",
          "title": "Construction",
          "type": "boolean"
        },
        "end": {
          "items": {
            "anyOf": [
              {
                "type": "number"
              },
              {
                "pattern": "^\\s*[+-]?(\\d+\\.?\\d*|\\.\\d+)([eE][+-]?\\d+)?\\s*\\S*\\s*$",
                "type": "string"
              },
              {
                "additionalProperties": false,
                "properties": {
                  "unit": {
                    "type": "string"
                  },
                  "value": {
                    "type": "number"
                  }
                },
                "required": [
                  "value"
                ],
                "type": "object"
              }
            ],
            "description": "Length. A bare number is millimetres; or use '50mm' / '2in' / {'value': 2, 'unit': 'inch'}. Supported units: mm, cm, m, in, ft."
          },
          "maxItems": 2,
          "minItems": 2,
          "title": "End",
          "type": "array"
        },
        "length_type": {
          "default": "center_to_center",
          "enum": [
            "center_to_center",
            "overall"
          ],
          "title": "Length Type",
          "type": "string"
        },
        "start": {
          "items": {
            "anyOf": [
              {
                "type": "number"
              },
              {
                "pattern": "^\\s*[+-]?(\\d+\\.?\\d*|\\.\\d+)([eE][+-]?\\d+)?\\s*\\S*\\s*$",
                "type": "string"
              },
              {
                "additionalProperties": false,
                "properties": {
                  "unit": {
                    "type": "string"
                  },
                  "value": {
                    "type": "number"
                  }
                },
                "required": [
                  "value"
                ],
                "type": "object"
              }
            ],
            "description": "Length. A bare number is millimetres; or use '50mm' / '2in' / {'value': 2, 'unit': 'inch'}. Supported units: mm, cm, m, in, ft."
          },
          "maxItems": 2,
          "minItems": 2,
          "title": "Start",
          "type": "array"
        },
        "type": {
          "const": "slot_straight",
          "default": "slot_straight",
          "title": "Type",
          "type": "string"
        },
        "width": {
          "anyOf": [
            {
              "type": "number"
            },
            {
              "pattern": "^\\s*[+-]?(\\d+\\.?\\d*|\\.\\d+)([eE][+-]?\\d+)?\\s*\\S*\\s*$",
              "type": "string"
            },
            {
              "additionalProperties": false,
              "properties": {
                "unit": {
                  "type": "string"
                },
                "value": {
                  "type": "number"
                }
              },
              "required": [
                "value"
              ],
              "type": "object"
            }
          ],
          "description": "Length. A bare number is millimetres; or use '50mm' / '2in' / {'value': 2, 'unit': 'inch'}. Supported units: mm, cm, m, in, ft.",
          "title": "Width"
        }
      },
      "required": [
        "start",
        "end",
        "width"
      ],
      "title": "SlotStraightEntity",
      "type": "object"
    },
    "SplineEntity": {
      "additionalProperties": false,
      "properties": {
        "construction": {
          "default": false,
          "description": "Create as construction geometry rather than profile geometry.",
          "title": "Construction",
          "type": "boolean"
        },
        "points": {
          "items": {
            "items": {
              "anyOf": [
                {
                  "type": "number"
                },
                {
                  "pattern": "^\\s*[+-]?(\\d+\\.?\\d*|\\.\\d+)([eE][+-]?\\d+)?\\s*\\S*\\s*$",
                  "type": "string"
                },
                {
                  "additionalProperties": false,
                  "properties": {
                    "unit": {
                      "type": "string"
                    },
                    "value": {
                      "type": "number"
                    }
                  },
                  "required": [
                    "value"
                  ],
                  "type": "object"
                }
              ],
              "description": "Length. A bare number is millimetres; or use '50mm' / '2in' / {'value': 2, 'unit': 'inch'}. Supported units: mm, cm, m, in, ft."
            },
            "maxItems": 2,
            "minItems": 2,
            "type": "array"
          },
          "maxItems": 200,
          "minItems": 2,
          "title": "Points",
          "type": "array"
        },
        "type": {
          "const": "spline",
          "default": "spline",
          "title": "Type",
          "type": "string"
        }
      },
      "required": [
        "points"
      ],
      "title": "SplineEntity",
      "type": "object"
    }
  },
  "additionalProperties": false,
  "description": "Open a sketch, draw a profile, and close it - the whole cadence in one call.\n\nStarting a sketch, adding geometry and exiting are three separate operations\nbecause they are three separate things, but almost nobody wants them apart: every\nprofile in a part is that exact sequence, and on a serialized COM thread the two\nextra round trips buy nothing. Building six chess pieces took about sixty calls,\nmost of them this pattern.",
  "properties": {
    "auto_relations": {
      "default": true,
      "description": "As on sw_sketch_add_geometry: false places geometry at exactly the coordinates given, instead of letting SOLIDWORKS snap it onto neighbours.",
      "title": "Auto Relations",
      "type": "boolean"
    },
    "detail": {
      "default": "auto",
      "description": "How much to say about each created segment. 'full' describes every one; 'compact' returns only the handle, type and index; 'auto' (the default) is full up to 60 segments and compact beyond that. Handles are always returned, so relations, dimensions and deletes can still address the geometry. Entities that landed off their requested coordinates keep full detail in every mode.",
      "enum": [
        "auto",
        "full",
        "compact"
      ],
      "title": "Detail",
      "type": "string"
    },
    "document": {
      "$ref": "#/$defs/DocTarget",
      "description": "Which document to act on. Defaults to the active document."
    },
    "entities": {
      "description": "Sketch primitives to create, in order. Give this or entities_file, not both.",
      "items": {
        "discriminator": {
          "mapping": {
            "arc_3pt": "#/$defs/Arc3PointEntity",
            "arc_center": "#/$defs/ArcCenterEntity",
            "centerline": "#/$defs/CenterlineEntity",
            "circle": "#/$defs/CircleEntity",
            "ellipse": "#/$defs/EllipseEntity",
            "line": "#/$defs/LineEntity",
            "point": "#/$defs/PointEntity",
            "polygon": "#/$defs/PolygonEntity",
            "rect_center": "#/$defs/RectCenterEntity",
            "rect_corner": "#/$defs/RectCornerEntity",
            "slot_3point_arc": "#/$defs/SlotArc3PointEntity",
            "slot_arc": "#/$defs/SlotArcEntity",
            "slot_centerpoint": "#/$defs/SlotCenterpointEntity",
            "slot_straight": "#/$defs/SlotStraightEntity",
            "spline": "#/$defs/SplineEntity"
          },
          "propertyName": "type"
        },
        "oneOf": [
          {
            "$ref": "#/$defs/LineEntity"
          },
          {
            "$ref": "#/$defs/CenterlineEntity"
          },
          {
            "$ref": "#/$defs/PointEntity"
          },
          {
            "$ref": "#/$defs/RectCornerEntity"
          },
          {
            "$ref": "#/$defs/RectCenterEntity"
          },
          {
            "$ref": "#/$defs/CircleEntity"
          },
          {
            "$ref": "#/$defs/ArcCenterEntity"
          },
          {
            "$ref": "#/$defs/Arc3PointEntity"
          },
          {
            "$ref": "#/$defs/EllipseEntity"
          },
          {
            "$ref": "#/$defs/PolygonEntity"
          },
          {
            "$ref": "#/$defs/SlotStraightEntity"
          },
          {
            "$ref": "#/$defs/SlotCenterpointEntity"
          },
          {
            "$ref": "#/$defs/SlotArcEntity"
          },
          {
            "$ref": "#/$defs/SlotArc3PointEntity"
          },
          {
            "$ref": "#/$defs/SplineEntity"
          }
        ]
      },
      "maxItems": 500,
      "title": "Entities",
      "type": "array"
    },
    "entities_file": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Path to a UTF-8 JSON file holding the same list, so a generated profile does not have to travel through the request. Either a bare array of entities or an object with an 'entities' key. A few hundred splined segments is tens of kilobytes of argument otherwise, and anything that computes a profile has already written it to a file.",
      "title": "Entities File"
    },
    "exit_sketch": {
      "default": true,
      "description": "Close the sketch when the geometry is in. Leave it open only to keep adding relations or dimensions before a feature consumes it.",
      "title": "Exit Sketch",
      "type": "boolean"
    },
    "on": {
      "$ref": "#/$defs/SketchPlaneTarget"
    },
    "rebuild": {
      "default": true,
      "description": "Rebuild the model on exiting.",
      "title": "Rebuild",
      "type": "boolean"
    }
  },
  "required": [
    "on"
  ],
  "title": "SketchCreateArgs",
  "type": "object"
}
```

## Result schema

```json
{
  "$defs": {
    "Check": {
      "additionalProperties": false,
      "description": "One named invariant asserted after a mutation.",
      "properties": {
        "detail": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Detail"
        },
        "name": {
          "title": "Name",
          "type": "string"
        },
        "passed": {
          "title": "Passed",
          "type": "boolean"
        }
      },
      "required": [
        "name",
        "passed"
      ],
      "title": "Check",
      "type": "object"
    },
    "CheckpointRecord": {
      "additionalProperties": false,
      "description": "What the auto-checkpoint layer did before a mutation ran.",
      "properties": {
        "checkpoint_path": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Checkpoint Path"
        },
        "created_utc": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Created Utc"
        },
        "method": {
          "description": "Never optional: the caller must be able to tell a real snapshot from a skipped one. 'file_copy' does not capture unsaved session state.",
          "enum": [
            "save_as_copy",
            "file_copy",
            "skipped",
            "reused"
          ],
          "title": "Method",
          "type": "string"
        },
        "reason": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "description": "Why the checkpoint was skipped or reused.",
          "title": "Reason"
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
          "title": "Source Path"
        }
      },
      "required": [
        "method"
      ],
      "title": "CheckpointRecord",
      "type": "object"
    },
    "SketchState": {
      "additionalProperties": false,
      "description": "CON-005, carried on every relation and dimension result so it cannot be skipped.",
      "properties": {
        "dangling_relations": {
          "items": {
            "additionalProperties": true,
            "type": "object"
          },
          "title": "Dangling Relations",
          "type": "array"
        },
        "fully_defined": {
          "title": "Fully Defined",
          "type": "boolean"
        },
        "over_defined": {
          "title": "Over Defined",
          "type": "boolean"
        },
        "over_defining_relations": {
          "items": {
            "additionalProperties": true,
            "type": "object"
          },
          "title": "Over Defining Relations",
          "type": "array"
        },
        "relation_count": {
          "title": "Relation Count",
          "type": "integer"
        },
        "status": {
          "description": "fully_defined, under_defined, over_defined, or no_solution.",
          "title": "Status",
          "type": "string"
        },
        "status_code": {
          "title": "Status Code",
          "type": "integer"
        }
      },
      "required": [
        "status",
        "status_code",
        "fully_defined",
        "over_defined",
        "relation_count"
      ],
      "title": "SketchState",
      "type": "object"
    },
    "Verification": {
      "additionalProperties": false,
      "description": "Evidence that a mutation actually happened, read back out of the model.",
      "properties": {
        "after": {
          "additionalProperties": true,
          "title": "After",
          "type": "object"
        },
        "before": {
          "additionalProperties": true,
          "title": "Before",
          "type": "object"
        },
        "checks": {
          "description": "At least one invariant must be asserted.",
          "items": {
            "$ref": "#/$defs/Check"
          },
          "minItems": 1,
          "title": "Checks",
          "type": "array"
        },
        "read_back": {
          "description": "True only when the post-state was re-read from SOLIDWORKS, not assumed.",
          "title": "Read Back",
          "type": "boolean"
        }
      },
      "required": [
        "read_back",
        "checks"
      ],
      "title": "Verification",
      "type": "object"
    }
  },
  "additionalProperties": false,
  "properties": {
    "checkpoint": {
      "anyOf": [
        {
          "$ref": "#/$defs/CheckpointRecord"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Populated by the dispatch pipeline, not by handlers."
    },
    "contours": {
      "additionalProperties": true,
      "description": "The profile topology of what was just drawn, so whether it closes is known before a revolve or extrude is attempted rather than after one is refused.",
      "title": "Contours",
      "type": "object"
    },
    "created": {
      "items": {
        "additionalProperties": true,
        "type": "object"
      },
      "title": "Created",
      "type": "array"
    },
    "created_compacted": {
      "default": false,
      "title": "Created Compacted",
      "type": "boolean"
    },
    "created_total": {
      "default": 0,
      "title": "Created Total",
      "type": "integer"
    },
    "exited": {
      "default": false,
      "title": "Exited",
      "type": "boolean"
    },
    "failed": {
      "items": {
        "additionalProperties": true,
        "type": "object"
      },
      "title": "Failed",
      "type": "array"
    },
    "max_deviation_mm": {
      "anyOf": [
        {
          "type": "number"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "title": "Max Deviation Mm"
    },
    "plane": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "title": "Plane"
    },
    "rebuild_errors": {
      "items": {
        "type": "string"
      },
      "title": "Rebuild Errors",
      "type": "array"
    },
    "sketch_name": {
      "title": "Sketch Name",
      "type": "string"
    },
    "sketch_state": {
      "$ref": "#/$defs/SketchState"
    },
    "verification": {
      "$ref": "#/$defs/Verification"
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
    "verification",
    "sketch_name",
    "sketch_state"
  ],
  "title": "SketchCreateResult",
  "type": "object"
}
```
