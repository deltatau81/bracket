from bracket.database import database
from bracket.models.db.player_statistics import PlayerStatistics
from bracket.utils.id_types import TournamentId


async def get_player_statistics(tournament_id: TournamentId) -> list[PlayerStatistics]:
    query = """
        WITH tournament_events AS (
            SELECT match_events.*
            FROM match_events
            JOIN matches ON matches.id = match_events.match_id
            JOIN rounds ON rounds.id = matches.round_id
            JOIN stage_items ON stage_items.id = rounds.stage_item_id
            JOIN stages ON stages.id = stage_items.stage_id
            WHERE stages.tournament_id = :tournament_id
            AND matches.status = 'FINISHED'
        ),
        contributions AS (
            SELECT player_id, 1 AS goals, 0 AS assists, 0 AS penalty_minutes
            FROM tournament_events
            WHERE event_type = 'GOAL'
            AND period <> 'SHOOTOUT'
            AND player_id IS NOT NULL

            UNION ALL

            SELECT assist1_player_id, 0, 1, 0
            FROM tournament_events
            WHERE event_type = 'GOAL'
            AND period <> 'SHOOTOUT'
            AND assist1_player_id IS NOT NULL

            UNION ALL

            SELECT assist2_player_id, 0, 1, 0
            FROM tournament_events
            WHERE event_type = 'GOAL'
            AND period <> 'SHOOTOUT'
            AND assist2_player_id IS NOT NULL

            UNION ALL

            SELECT player_id, 0, 0, penalty_minutes
            FROM tournament_events
            WHERE event_type = 'PENALTY'
            AND player_id IS NOT NULL
            AND penalty_minutes IS NOT NULL
        ),
        event_totals AS (
            SELECT
                player_id,
                sum(goals)::integer AS goals,
                sum(assists)::integer AS assists,
                sum(penalty_minutes)::integer AS penalty_minutes
            FROM contributions
            GROUP BY player_id
        ),
        roster AS (
            SELECT
                players_x_teams.player_id,
                CASE WHEN count(*) = 1 THEN min(teams.id) END AS team_id,
                CASE WHEN count(*) = 1 THEN min(teams.name) END AS team_name,
                CASE WHEN count(*) = 1 THEN min(players_x_teams.number) END AS jersey_number,
                CASE WHEN count(*) = 1 THEN min(players_x_teams.position) END AS position
            FROM players_x_teams
            JOIN teams ON teams.id = players_x_teams.team_id
            WHERE teams.tournament_id = :tournament_id
            GROUP BY players_x_teams.player_id
        )
        SELECT
            players.id AS player_id,
            players.name AS player_name,
            roster.team_id,
            roster.team_name,
            roster.jersey_number,
            roster.position,
            coalesce(event_totals.goals, 0) AS goals,
            coalesce(event_totals.assists, 0) AS assists,
            coalesce(event_totals.goals, 0) + coalesce(event_totals.assists, 0) AS points,
            coalesce(event_totals.penalty_minutes, 0) AS penalty_minutes
        FROM players
        LEFT JOIN roster ON roster.player_id = players.id
        LEFT JOIN event_totals ON event_totals.player_id = players.id
        WHERE players.tournament_id = :tournament_id
        ORDER BY
            points DESC,
            goals DESC,
            assists DESC,
            players.name ASC,
            players.id ASC
    """
    results = await database.fetch_all(query=query, values={"tournament_id": tournament_id})
    return [PlayerStatistics.model_validate(dict(result._mapping)) for result in results]
