from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from bracket.models.db.competition import TournamentOverallStanding


def aggregate_club_standings(
    standings: list[TournamentOverallStanding],
) -> list[TournamentOverallStanding]:
    """Aggregate already calculated team totals; unassigned teams remain individual."""
    rows: list[TournamentOverallStanding] = []
    clubs: dict[int, TournamentOverallStanding] = {}
    for standing in standings:
        if standing.club_id is None:
            rows.append(standing)
            continue
        current = clubs.get(standing.club_id)
        if current is None:
            current = standing.model_copy(update={"team_id": None, "team_name": None})
            clubs[standing.club_id] = current
            rows.append(current)
        else:
            current.game_points += standing.game_points
            current.competition_points += standing.competition_points
            current.total_points += standing.total_points
    # Retain deterministic incoming order for equal total and hockey points.
    return sorted(rows, key=lambda row: (-row.total_points, -row.game_points))
