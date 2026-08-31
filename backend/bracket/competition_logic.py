from dataclasses import dataclass
from decimal import Decimal

from bracket.models.db.competition import (
    CompetitionDiscipline,
    CompetitionMetricType,
    CompetitionResult,
    CompetitionScoring,
)


@dataclass
class RankedCompetitionResult:
    result: CompetitionResult
    place: int
    points: Decimal
    tied: bool


def metric_value(
    discipline: CompetitionDiscipline,
    result: CompetitionResult,
) -> Decimal | None:

    if discipline.metric_type == CompetitionMetricType.TIME:
        if result.time_ms is None:
            return None
        return Decimal(result.time_ms)

    if discipline.metric_type == CompetitionMetricType.COUNT:
        if result.successes is None:
            return None
        return Decimal(result.successes)

    if discipline.metric_type == CompetitionMetricType.RATIO:
        if (
            result.attempts is None
            or result.successes is None
            or result.attempts <= 0
        ):
            return None

        return (
            Decimal(result.successes)
            / Decimal(result.attempts)
        )

    return None


def rank_results(
    discipline: CompetitionDiscipline,
    results: list[CompetitionResult],
    scoring: list[CompetitionScoring],
) -> list[RankedCompetitionResult]:

    scoring_map = {
        item.place: item.points
        for item in scoring
    }

    # ------------------------------------------------------------
    # Manuelle Platzierung
    # ------------------------------------------------------------
    if discipline.metric_type == CompetitionMetricType.MANUAL:
        valid = [
            result
            for result in results
            if result.place is not None
        ]

        places_count: dict[int, int] = {}

        for result in valid:
            places_count[result.place] = (
                places_count.get(result.place, 0) + 1
            )

        return [
            RankedCompetitionResult(
                result=result,
                place=result.place,
                points=scoring_map.get(
                    result.place,
                    Decimal("0"),
                ),
                tied=places_count[result.place] > 1,
            )
            for result in sorted(
                valid,
                key=lambda item: item.place,
            )
        ]

    # ------------------------------------------------------------
    # Automatische Wertung
    # ------------------------------------------------------------
    values: list[tuple[CompetitionResult, Decimal]] = []

    for result in results:
        value = metric_value(
            discipline,
            result,
        )

        if value is not None:
            values.append((result, value))

    reverse = discipline.metric_type in (
        CompetitionMetricType.COUNT,
        CompetitionMetricType.RATIO,
    )

    values.sort(
        key=lambda item: item[1],
        reverse=reverse,
    )

    ranked: list[RankedCompetitionResult] = []

    previous_value: Decimal | None = None
    previous_place: int | None = None

    for index, (result, value) in enumerate(values):
        nominal_place = index + 1

        if (
            previous_value is not None
            and value == previous_value
        ):
            place = previous_place
        else:
            place = nominal_place

        assert place is not None

        tied = sum(
            1
            for _, candidate_value in values
            if candidate_value == value
        ) > 1

        ranked.append(
            RankedCompetitionResult(
                result=result,
                place=place,
                points=scoring_map.get(
                    place,
                    Decimal("0"),
                ),
                tied=tied,
            )
        )

        previous_value = value
        previous_place = place

    return ranked
