import pytest

from bracket.logic.penalty_catalog import (
    PENALTY_TYPES,
    PenaltyType,
    UnsupportedPenaltyCatalogError,
    get_penalty_catalog,
)
from bracket.models.db.tournament import HockeyAgeCategory, HockeyRuleset


def test_iihf_2026_27_known_penalties_and_metadata() -> None:
    catalog = get_penalty_catalog(
        HockeyRuleset.IIHF,
        "2026/27",
        HockeyAgeCategory.U15,
    )
    penalties = {penalty.code: penalty for penalty in catalog.penalties}
    types = {penalty_type.type: penalty_type for penalty_type in PENALTY_TYPES}

    assert catalog.catalog_source == "IIHF_2026_27"
    assert penalties["BOARDING"].rule == "41"
    assert penalties["TRIPPING"].rule == "57"
    assert penalties["TRIPPING"].label == "Beinstellen"
    assert penalties["TOO_MANY_PLAYERS"].rule == "74"
    assert penalties["UNSPORTSMANLIKE_CONDUCT"].rule == "75"
    assert all(
        penalty.default_penalty_type in penalty.allowed_penalty_types
        for penalty in catalog.penalties
    )
    assert types[PenaltyType.MINOR].minutes == 2
    assert types[PenaltyType.MAJOR_GAME_MISCONDUCT].minutes == 5
    assert types[PenaltyType.MAJOR_GAME_MISCONDUCT].game_misconduct is True
    assert types[PenaltyType.PENALTY_SHOT].minutes is None
    assert types[PenaltyType.AWARDED_GOAL].minutes is None


def test_deb_uses_explicit_iihf_base_catalog() -> None:
    catalog = get_penalty_catalog(
        HockeyRuleset.DEB,
        "2026/27",
        HockeyAgeCategory.SENIOR,
    )

    assert catalog.catalog_source == "IIHF_BASE"
    assert catalog.ruleset is HockeyRuleset.DEB


def test_unsupported_season_is_explicit() -> None:
    with pytest.raises(UnsupportedPenaltyCatalogError, match="2027/28"):
        get_penalty_catalog(
            HockeyRuleset.IIHF,
            "2027/28",
            HockeyAgeCategory.U17,
        )


@pytest.mark.parametrize(
    "age_category",
    [
        HockeyAgeCategory.U9,
        HockeyAgeCategory.U11,
        HockeyAgeCategory.U13,
        HockeyAgeCategory.U15,
        HockeyAgeCategory.U17,
        HockeyAgeCategory.U20,
        HockeyAgeCategory.SENIOR,
    ],
)
def test_catalog_has_no_age_specific_mutation(age_category: HockeyAgeCategory) -> None:
    catalog = get_penalty_catalog(HockeyRuleset.IIHF, "2026/27", age_category)

    assert catalog.penalties == get_penalty_catalog(
        HockeyRuleset.IIHF,
        "2026/27",
        HockeyAgeCategory.SENIOR,
    ).penalties