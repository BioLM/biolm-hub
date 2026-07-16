"""The load-bearing uniformity test: every registered model is reachable through the MCP surface.

Parametrized over every model the gateway discovers, so adding a model under ``models/<name>/``
either just works here or fails CI — it can never silently disappear from the MCP catalog. This is
what makes "adding a model needs zero MCP code" an enforced guarantee, not a hope.
"""

from __future__ import annotations

import pytest

from gateway.mcp import catalog as cat
from gateway.model_discovery import get_model_mapper

MAPPER = get_model_mapper()
SNAPSHOT = cat.build_snapshot(MAPPER)
BASE_SLUGS = sorted(MAPPER.get_all_registered_models())


def test_snapshot_covers_every_registered_model() -> None:
    assert {card.slug for card in SNAPSHOT.cards} == set(BASE_SLUGS)


@pytest.mark.parametrize("slug", BASE_SLUGS)
def test_every_model_has_a_card_and_action_schemas(slug: str) -> None:
    card = next((c for c in SNAPSHOT.cards if c.slug == slug), None)
    assert card is not None, f"{slug}: missing from the catalog snapshot"
    assert card.display_name
    assert card.actions, f"{slug}: no actions"
    assert card.variants, f"{slug}: no variants"

    schemas = cat.build_model_schemas(MAPPER, slug)
    assert schemas.actions, f"{slug}: no action schemas"
    for action_schema in schemas.actions:
        assert (
            action_schema.request_schema
        ), f"{slug}/{action_schema.action}: empty request schema"
        assert (
            action_schema.response_schema
        ), f"{slug}/{action_schema.action}: empty response schema"


def test_capabilities_vocabulary_is_populated() -> None:
    caps = cat.build_capabilities()
    assert caps.molecules and caps.tasks and caps.actions
    assert "encode" in caps.actions
