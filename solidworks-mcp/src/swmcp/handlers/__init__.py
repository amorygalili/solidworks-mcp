"""Handler modules.

Importing this package registers every operation: the ``@op`` decorator populates
:data:`swmcp.catalog.registry.OPS` as a side effect of import, so the catalog and the
implementations can never disagree about what exists.
"""

from __future__ import annotations

from swmcp.handlers import (
    assembly,
    constraint,
    discovery,
    document,
    exchange,
    feature,
    mate,
    material,
    parameter,
    reference,
    review,
    safety,
    sketch,
    solid,
    surface,
    system,
    view,
)

__all__ = [
    "assembly",
    "constraint",
    "discovery",
    "document",
    "exchange",
    "feature",
    "mate",
    "material",
    "parameter",
    "reference",
    "review",
    "safety",
    "sketch",
    "solid",
    "surface",
    "system",
    "view",
]
