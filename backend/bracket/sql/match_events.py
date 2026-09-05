from bracket.database import database
from bracket.models.db.match_event import MatchEvent, MatchEventBody, MatchEventInsertable
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


async def get_match_events(match_id: MatchId) -> list[MatchEvent]:
    query = """
        SELECT *
        FROM match_events
        WHERE match_id = :match_id
        ORDER BY
            CASE period
                WHEN 'HALF1' THEN 0
                WHEN 'HALF2' THEN 1
                WHEN 'PERIOD1' THEN 2
                WHEN 'PERIOD2' THEN 3
                WHEN 'PERIOD3' THEN 4
                WHEN 'OVERTIME' THEN 5
            END,
            game_time_seconds,
            sort_order,
            id
    """
    results = await database.fetch_all(query=query, values={"match_id": match_id})
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
