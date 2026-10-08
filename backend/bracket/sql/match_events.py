from bracket.database import database
from bracket.models.db.match_event import (
    MatchEvent,
    MatchEventBody,
    MatchEventInsertable,
    MatchEventPeriod,
)
from bracket.schema import match_events as match_events_table
from bracket.utils.id_types import MatchEventId, MatchId, PlayerId, TeamId, TournamentId


def event_values(event: MatchEventBody | MatchEventInsertable) -> dict[str, object]:
    values = {field: getattr(event, field) for field in MatchEventBody.model_fields}
    values["event_type"] = event.event_type.value
    values["period"] = event.period.value
    if isinstance(event, MatchEventInsertable):
        values["match_id"] = event.match_id
        values["created"] = event.created
    return values


async def get_match_team_ids(
    tournament_id: TournamentId, match_id: MatchId
) -> set[TeamId] | None:
    query = """
        SELECT input1.team_id AS team1_id, input2.team_id AS team2_id
        FROM matches
        JOIN rounds ON rounds.id = matches.round_id
        JOIN stage_items ON stage_items.id = rounds.stage_item_id
        JOIN stages ON stages.id = stage_items.stage_id
        LEFT JOIN stage_item_inputs input1 ON input1.id = matches.stage_item_input1_id
        LEFT JOIN stage_item_inputs input2 ON input2.id = matches.stage_item_input2_id
        WHERE matches.id = :match_id
        AND stages.tournament_id = :tournament_id
    """
    result = await database.fetch_one(
        query=query, values={"match_id": match_id, "tournament_id": tournament_id}
    )
    if result is None:
        return None
    return {
        TeamId(team_id)
        for team_id in (result["team1_id"], result["team2_id"])
        if team_id is not None
    }


async def adjust_goal_score(
    match_id: MatchId,
    team_id: TeamId,
    period: MatchEventPeriod,
    delta: int,
) -> bool:
    score_columns = {
        MatchEventPeriod.GAME: (
            "stage_item_input1_score",
            "stage_item_input2_score",
        ),
        MatchEventPeriod.HALF1: (
            "stage_item_input1_half1_score",
            "stage_item_input2_half1_score",
        ),
        MatchEventPeriod.HALF2: (
            "stage_item_input1_half2_score",
            "stage_item_input2_half2_score",
        ),
        MatchEventPeriod.SHOOTOUT: (
            "stage_item_input1_penalty_score",
            "stage_item_input2_penalty_score",
        ),
    }
    columns = score_columns.get(period)
    if columns is None:
        return True

    participants = await database.fetch_one(
        query="""
                 SELECT input1.team_id AS team1_id, input2.team_id AS team2_id,
                     matches.score_entry_source, tournaments.hockey_mode
            FROM matches
                 JOIN rounds ON rounds.id = matches.round_id
                 JOIN stage_items ON stage_items.id = rounds.stage_item_id
                 JOIN stages ON stages.id = stage_items.stage_id
                 JOIN tournaments ON tournaments.id = stages.tournament_id
            LEFT JOIN stage_item_inputs input1
                ON input1.id = matches.stage_item_input1_id
            LEFT JOIN stage_item_inputs input2
                ON input2.id = matches.stage_item_input2_id
            WHERE matches.id = :match_id
            FOR UPDATE OF matches
        """,
        values={"match_id": match_id},
    )
    if participants is None:
        return False
    score_mutations_enabled = participants["score_entry_source"] != "MANUAL"
    if not score_mutations_enabled:
        return True

    if participants["team1_id"] == team_id:
        score_column = columns[0]
    elif participants["team2_id"] == team_id:
        score_column = columns[1]
    else:
        return False

    if period in {MatchEventPeriod.HALF1, MatchEventPeriod.HALF2}:
        aggregate_updates = """
            , stage_item_input1_score = stage_item_input1_half1_score
                + stage_item_input1_half2_score
                + :score1_delta
            , stage_item_input2_score = stage_item_input2_half1_score
                + stage_item_input2_half2_score
                + :score2_delta
        """
    else:
        aggregate_updates = ""
    query = f"""
        UPDATE matches
        SET {score_column} = {score_column} + :delta
            {aggregate_updates}
        WHERE id = :match_id
        AND score_entry_source IS DISTINCT FROM 'MANUAL'
        AND {score_column} + :delta >= 0
        RETURNING id
    """
    values = {"match_id": match_id, "delta": delta}
    if aggregate_updates:
        values["score1_delta"] = (
            delta if participants["team1_id"] == team_id else 0
        )
        values["score2_delta"] = (
            delta if participants["team2_id"] == team_id else 0
        )
    result = await database.fetch_one(
        query=query,
        values=values,
    )
    return result is not None


async def youth_club_game_score_uses_events(match_id: MatchId) -> bool:
    result = await database.fetch_one(
        query="""
            SELECT stage_items.is_youth_club_group
                AND tournaments.competition_format = 'YOUTH_CLUB'
                AND tournaments.hockey_mode = 'GAME_SHOOTOUT'
                AND matches.score_entry_source IS DISTINCT FROM 'MANUAL' AS uses_events
            FROM matches
            JOIN rounds ON rounds.id = matches.round_id
            JOIN stage_items ON stage_items.id = rounds.stage_item_id
            JOIN stages ON stages.id = stage_items.stage_id
            JOIN tournaments ON tournaments.id = stages.tournament_id
            WHERE matches.id = :match_id
            FOR UPDATE OF matches
        """,
        values={"match_id": match_id},
    )
    return result is not None and bool(result["uses_events"])


async def recalculate_youth_club_game_score(match_id: MatchId) -> bool:
    result = await database.fetch_one(
        query="""
            UPDATE matches
            SET stage_item_input1_score = (
                    SELECT COUNT(*) FROM match_events
                    WHERE match_events.match_id = matches.id
                    AND match_events.event_type = 'GOAL'
                    AND match_events.period = 'GAME'
                    AND match_events.team_id = input1.team_id
                ),
                stage_item_input2_score = (
                    SELECT COUNT(*) FROM match_events
                    WHERE match_events.match_id = matches.id
                    AND match_events.event_type = 'GOAL'
                    AND match_events.period = 'GAME'
                    AND match_events.team_id = input2.team_id
                )
            FROM rounds
            JOIN stage_items ON stage_items.id = rounds.stage_item_id
            JOIN stages ON stages.id = stage_items.stage_id
            JOIN tournaments ON tournaments.id = stages.tournament_id
            CROSS JOIN stage_item_inputs input1
            CROSS JOIN stage_item_inputs input2
            WHERE matches.id = :match_id
            AND matches.round_id = rounds.id
            AND input1.id = matches.stage_item_input1_id
            AND input2.id = matches.stage_item_input2_id
            AND stage_items.is_youth_club_group
            AND tournaments.competition_format = 'YOUTH_CLUB'
            AND tournaments.hockey_mode = 'GAME_SHOOTOUT'
            AND matches.score_entry_source IS DISTINCT FROM 'MANUAL'
            RETURNING matches.id
        """,
        values={"match_id": match_id},
    )
    return result is not None


async def get_player_snapshot(
    player_id: PlayerId, team_id: TeamId
) -> tuple[str, int | None] | None:
    query = """
        SELECT players.name, players_x_teams.number
        FROM players
        JOIN players_x_teams ON players_x_teams.player_id = players.id
        WHERE players.id = :player_id
        AND players_x_teams.team_id = :team_id
    """
    result = await database.fetch_one(
        query=query, values={"player_id": player_id, "team_id": team_id}
    )
    if result is None:
        return None
    return str(result["name"]), result["number"]


_EVENT_CHRONOLOGY_SQL = """
    CASE period
        WHEN 'GAME' THEN 0
        WHEN 'HALF1' THEN 0
        WHEN 'HALF2' THEN 1
        WHEN 'SHOOTOUT' THEN 2
        WHEN 'PERIOD1' THEN 0
        WHEN 'PERIOD2' THEN 1
        WHEN 'PERIOD3' THEN 2
        WHEN 'OVERTIME' THEN 3
    END,
    game_time_seconds,
    sort_order,
    match_events.id
"""


async def get_match_events(match_id: MatchId) -> list[MatchEvent]:
    query = f"""
        SELECT *
        FROM match_events
        WHERE match_id = :match_id
        ORDER BY {_EVENT_CHRONOLOGY_SQL}
    """
    results = await database.fetch_all(query=query, values={"match_id": match_id})
    return [MatchEvent.model_validate(result) for result in results]


async def get_tournament_match_events(tournament_id: TournamentId) -> list[MatchEvent]:
    query = f"""
        SELECT match_events.*
        FROM match_events
        JOIN matches ON matches.id = match_events.match_id
        JOIN rounds ON rounds.id = matches.round_id
        JOIN stage_items ON stage_items.id = rounds.stage_item_id
        JOIN stages ON stages.id = stage_items.stage_id
        WHERE stages.tournament_id = :tournament_id
        ORDER BY match_events.match_id, {_EVENT_CHRONOLOGY_SQL}
    """
    results = await database.fetch_all(
        query=query,
        values={"tournament_id": tournament_id},
    )
    return [MatchEvent.model_validate(result) for result in results]


async def get_match_event(match_id: MatchId, event_id: MatchEventId) -> MatchEvent | None:
    result = await database.fetch_one(
        query=match_events_table.select().where(
            (match_events_table.c.id == event_id)
            & (match_events_table.c.match_id == match_id)
        )
    )
    return MatchEvent.model_validate(result) if result is not None else None


async def create_match_event(event: MatchEventInsertable) -> MatchEvent:
    result = await database.fetch_one(
        query=match_events_table.insert().returning(*match_events_table.c),
        values=event_values(event),
    )
    if result is None:
        raise ValueError("Could not create match event")
    return MatchEvent.model_validate(result)


async def update_match_event(
    match_id: MatchId, event_id: MatchEventId, event: MatchEventBody
) -> MatchEvent | None:
    result = await database.fetch_one(
        query=match_events_table.update()
        .where(
            (match_events_table.c.id == event_id)
            & (match_events_table.c.match_id == match_id)
        )
        .values(**event_values(event))
        .returning(*match_events_table.c)
    )
    return MatchEvent.model_validate(result) if result is not None else None


async def delete_match_event(match_id: MatchId, event_id: MatchEventId) -> bool:
    result = await database.fetch_one(
        query=match_events_table.delete()
        .where(
            (match_events_table.c.id == event_id)
            & (match_events_table.c.match_id == match_id)
        )
        .returning(match_events_table.c.id)
    )
    return result is not None
