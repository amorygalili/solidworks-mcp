# sw_api_search

Search the SOLIDWORKS constants registered on this machine by name, so a caller can find the enum member a low-level call needs without guessing its value.

| | |
|---|---|
| Tier | `extended` |
| Domains | `discovery` |
| Document precondition | `none` |
| Safety | `read` |
| Read-only | True |
| Destructive | False |
| Confirmation required | False |
| Auto-checkpointed | False |
| Idempotent | True |
| Timeout | 120s |
| Satisfies | `DISC-002` |

## Input schema

```json
{
  "additionalProperties": false,
  "properties": {
    "kind": {
      "default": "any",
      "enum": [
        "enum",
        "member",
        "any"
      ],
      "title": "Kind",
      "type": "string"
    },
    "limit": {
      "default": 40,
      "maximum": 200,
      "minimum": 1,
      "title": "Limit",
      "type": "integer"
    },
    "query": {
      "default": "",
      "description": "Text matched against names.",
      "maxLength": 120,
      "title": "Query",
      "type": "string"
    }
  },
  "title": "ApiSearchArgs",
  "type": "object"
}
```

## Result schema

```json
{
  "additionalProperties": false,
  "properties": {
    "enums": {
      "items": {
        "additionalProperties": true,
        "type": "object"
      },
      "title": "Enums",
      "type": "array"
    },
    "members": {
      "items": {
        "additionalProperties": true,
        "type": "object"
      },
      "title": "Members",
      "type": "array"
    },
    "note": {
      "default": "This index is built from the type libraries registered on this machine, so it matches the installed release. It is not a copy of the online API reference.",
      "title": "Note",
      "type": "string"
    },
    "typelib": {
      "additionalProperties": true,
      "title": "Typelib",
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
  "title": "ApiSearchResult",
  "type": "object"
}
```
