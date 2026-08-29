# sw_sketch_add_geometry

Create sketch primitives in one batch — lines, centerlines, points, rectangles, circles, arcs, ellipses, polygons, slots, and splines. Each created segment comes back with a stable id for use in relations, dimensions, and deletes.

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
| Satisfies | `SK-003`, `SK-004` |
| Partially satisfies | `FEAT-013` |

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
  "properties": {
    "document": {
      "$ref": "#/$defs/DocTarget",
      "description": "Which document to act on. Defaults to the active document."
    },
    "entities": {
      "description": "Sketch primitives to create, in order.",
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
      "minItems": 1,
      "title": "Entities",
      "type": "array"
    },
    "preflight": {
      "default": false,
      "description": "Validate inputs and report what would happen, without changing the model.",
      "title": "Preflight",
      "type": "boolean"
    },
    "sketch_name": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "description": "Sketch to edit. Defaults to the sketch currently open for editing.",
      "title": "Sketch Name"
    }
  },
  "required": [
    "entities"
  ],
  "title": "SketchAddGeometryArgs",
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
    "created": {
      "items": {
        "additionalProperties": true,
        "type": "object"
      },
      "title": "Created",
      "type": "array"
    },
    "failed": {
      "items": {
        "additionalProperties": true,
        "type": "object"
      },
      "title": "Failed",
      "type": "array"
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
  "title": "SketchAddGeometryResult",
  "type": "object"
}
```
