import pytest

from app.rubric import (
    DIMENSIONS,
    IncompleteScoreError,
    rubric_hash,
    total_weight,
    weighted_composite,
)


def test_total_weight_sums_to_one():
    assert total_weight() == 1.0


def test_weighted_composite_all_dimensions_present():
    scores = {d["key"]: 100.0 for d in DIMENSIONS}
    assert weighted_composite(scores) == 100.0

    scores_zero = {d["key"]: 0.0 for d in DIMENSIONS}
    assert weighted_composite(scores_zero) == 0.0


def test_weighted_composite_respects_weights():
    # Give every dimension a different score and check against a manual sum.
    scores = {d["key"]: (i + 1) * 10.0 for i, d in enumerate(DIMENSIONS)}
    expected = round(sum(scores[d["key"]] * d["weight"] for d in DIMENSIONS), 1)
    assert weighted_composite(scores) == expected


def test_weighted_composite_raises_on_missing_dimension():
    incomplete = {d["key"]: 50.0 for d in DIMENSIONS[:-1]}  # drop the last one
    with pytest.raises(IncompleteScoreError):
        weighted_composite(incomplete)


def test_rubric_hash_is_deterministic():
    assert rubric_hash() == rubric_hash()
    assert isinstance(rubric_hash(), str)
    assert len(rubric_hash()) == 12
