# CAD MCP capability comparison

This folder inventories the CAD capabilities present in the four projects in this
repository and turns their combined coverage into a requirements checklist for a
new SolidWorks MCP/skill implementation.

## Documents

- [Capability matrix](capability-matrix.md) — domain-level comparison of the four
  projects, including the distinction between dedicated MCP tools, skill/library
  functions, generic escape hatches, and reference-only claims.
- [Project inventories](project-inventories.md) — source-audited list of the tools
  and notable non-MCP operations in each project.
- [SolidWorks target requirements](solidworks-target-requirements.md) — the
  recommended feature backlog and acceptance criteria for a new SolidWorks
  integration, including a FreeCAD-to-SolidWorks crosswalk.

## Projects and abbreviations

| Abbreviation | Folder | Kind |
|---|---|---|
| FC | `freecad-addon-robust-mcp-server` | FreeCAD MCP server and FreeCAD add-on |
| SKILL | `solidworks-automation-skill` | SolidWorks skill, Python automation library, local MCP server, and desktop workbench |
| ALISAM | `Solidworks-MCP-alisam` | Compact Python SolidWorks MCP server |
| JAY | `solidworks-mcp-jay` | TypeScript MCP server with a .NET SolidWorks COM worker |

## Interpretation rules

This is a static source audit, not a live SolidWorks/FreeCAD acceptance test.
"Available" therefore means that an operation has an implementation and a path
from an advertised entry point in the checked-in code. It does not guarantee that
the operation works on every CAD version or every model.

The comparison uses these coverage levels:

| Code | Meaning |
|---|---|
| **M** | Dedicated MCP tool is registered in current source. |
| **L** | Implemented in a skill, script, or library, but not exposed as a dedicated MCP tool. |
| **G** | Reachable only through a generic executor/invoker, not a task-specific contract. |
| **R** | Reference-only, roadmap, pilot preflight, or explicitly not implemented. |
| **—** | No meaningful evidence found in the audited project. |

When a cell contains more than one code, the accompanying text explains the
strongest dedicated path and any broader fallback. A generic Python/COM escape
hatch is recorded, but it is not treated as equivalent to a safe, typed,
discoverable operation.

## Source-of-truth policy

Tool counts and names come from current registration code, not headline README
claims:

| Project | Current source-audited MCP tools | Important documentation drift |
|---|---:|---|
| FC | 152 | `docs/MCP_TOOLS_REFERENCE.md` says 85 and omits newer object, sketch, spreadsheet, draft, and validation tools. |
| SKILL | 40 | The project also has many script/library operations that are not dedicated MCP tools. |
| ALISAM | 25 | The README says 22 and omits newer tools such as face sketches and sketch diagnostics. |
| JAY | 142 at the default `all` tier | 133 generated manifest tools plus 9 manually registered search, status, audit, invoke, and URDF tools. Tier filtering can expose fewer. |

## Audit date

The repository was audited on 2026-08-25 from the checked-in working tree.
