"""Unit: knowledge model builder registry."""

from __future__ import annotations

import pytest
from app.domain.knowledge_model_constants import MODEL_TYPES
from app.services.models.builders.dispatch import get_builder


@pytest.mark.unit
@pytest.mark.parametrize("model_type", sorted(MODEL_TYPES))
def test_get_builder_registered(model_type: str) -> None:
    fn = get_builder(model_type)
    assert callable(fn)


@pytest.mark.unit
def test_get_builder_rejects_unknown() -> None:
    with pytest.raises(ValueError, match="unknown model_type"):
        get_builder("not_a_model")
