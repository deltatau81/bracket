from sqlalchemy import Numeric, cast, func, select

from bracket.database import database
from bracket.logic.ranking.overall_standings import aggregate_club_standings
from bracket.models.db.competition import (
    Competition,
    CompetitionBody,
    CompetitionDiscipline,
    CompetitionDisciplineBody,
    CompetitionDisciplineInsertable,
    CompetitionInsertable,
    CompetitionScoring,
    CompetitionScoringBody,
    CompetitionResult,
    CompetitionResultBody,
    CompetitionResultInsertable,
    TournamentOverallStanding,
)
from bracket.models.db.tournament import TournamentCompetitionFormat
from bracket.schema import (
    clubs,
    competition_disciplines,
    competition_scoring,
    competitions,
    competition_results,
    stage_item_inputs,
    teams,
)
from bracket.sql.tournaments import sql_get_tournament
from bracket.utils.db import fetch_all_parsed, fetch_one_parsed
from bracket.utils.id_types import (
    CompetitionDisciplineId,
    CompetitionId,
    TournamentId,
    CompetitionResultId,
)


# ---------------------------------------------------------------------------
# Competitions
# ---------------------------------------------------------------------------

async def get_competitions_in_tournament(
    tournament_id: TournamentId,
) -> list[Competition]:
    return await fetch_all_parsed(
        database,
        Competition,
        competitions.select()
        .where(competitions.c.tournament_id == tournament_id)
        .order_by(competitions.c.start_time, competitions.c.id),
    )


async def get_competition(
    tournament_id: TournamentId,
    competition_id: CompetitionId,
) -> Competition | None:
    return await fetch_one_parsed(
        database,
        Competition,
        competitions.select().where(
            (competitions.c.id == competition_id)
            & (competitions.c.tournament_id == tournament_id)
        ),
    )


async def create_competition(
    competition: CompetitionInsertable,
) -> CompetitionId:
    new_id = await database.execute(
        competitions.insert(),
        values=competition.model_dump(),
    )
    return CompetitionId(new_id)


async def update_competition(
    tournament_id: TournamentId,
    competition_id: CompetitionId,
    body: CompetitionBody,
) -> None:
    await database.execute(
        competitions.update()
        .where(
            (competitions.c.id == competition_id)
            & (competitions.c.tournament_id == tournament_id)
        )
        .values(**body.model_dump())
    )


async def delete_competition(
    tournament_id: TournamentId,
    competition_id: CompetitionId,
) -> None:
    await database.execute(
        competitions.delete().where(
            (competitions.c.id == competition_id)
            & (competitions.c.tournament_id == tournament_id)
        )
    )


# ---------------------------------------------------------------------------
# Disciplines
# ---------------------------------------------------------------------------

async def get_disciplines(
    competition_id: CompetitionId,
) -> list[CompetitionDiscipline]:
    return await fetch_all_parsed(
        database,
        CompetitionDiscipline,
        competition_disciplines.select()
        .where(
            competition_disciplines.c.competition_id == competition_id
        )
        .order_by(
            competition_disciplines.c.sort_order,
            competition_disciplines.c.id,
        ),
    )


async def get_discipline(
    competition_id: CompetitionId,
    discipline_id: CompetitionDisciplineId,
) -> CompetitionDiscipline | None:
    return await fetch_one_parsed(
        database,
        CompetitionDiscipline,
        competition_disciplines.select().where(
            (competition_disciplines.c.id == discipline_id)
            & (
                competition_disciplines.c.competition_id
                == competition_id
            )
        ),
    )


async def create_discipline(
    discipline: CompetitionDisciplineInsertable,
) -> CompetitionDisciplineId:
    new_id = await database.execute(
        competition_disciplines.insert(),
        values={
            **discipline.model_dump(),
            "metric_type": discipline.metric_type.value,
        },
    )
    return CompetitionDisciplineId(new_id)


async def update_discipline(
    competition_id: CompetitionId,
    discipline_id: CompetitionDisciplineId,
    body: CompetitionDisciplineBody,
) -> None:
    await database.execute(
        competition_disciplines.update()
        .where(
            (competition_disciplines.c.id == discipline_id)
            & (
                competition_disciplines.c.competition_id
                == competition_id
            )
        )
        .values(
            **{
              **body.model_dump(),
              "metric_type": body.metric_type.value,
            }
        )
    )


async def delete_discipline(
    competition_id: CompetitionId,
    discipline_id: CompetitionDisciplineId,
) -> None:
    await database.execute(
        competition_disciplines.delete().where(
            (competition_disciplines.c.id == discipline_id)
            & (
                competition_disciplines.c.competition_id
                == competition_id
            )
        )
    )


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

async def get_scoring(
    competition_id: CompetitionId,
) -> list[CompetitionScoring]:
    return await fetch_all_parsed(
        database,
        CompetitionScoring,
        competition_scoring.select()
        .where(
            competition_scoring.c.competition_id == competition_id
        )
        .order_by(competition_scoring.c.place),
    )


async def replace_scoring(
    competition_id: CompetitionId,
    scoring: list[CompetitionScoringBody],
) -> None:
    async with database.transaction():
        await database.execute(
            competition_scoring.delete().where(
                competition_scoring.c.competition_id == competition_id
            )
        )

        if scoring:
            await database.execute_many(
                competition_scoring.insert(),
                values=[
                    {
                        "competition_id": competition_id,
                        "place": item.place,
                        "points": item.points,
                    }
                    for item in scoring
                ],
            )
# ---------------------------------------------------------------------------
# Results
# ---------------------------------------------------------------------------

async def get_results(
    discipline_id: CompetitionDisciplineId,
) -> list[CompetitionResult]:
    return await fetch_all_parsed(
        database,
        CompetitionResult,
        competition_results.select()
        .where(
            competition_results.c.discipline_id == discipline_id
        )
        .order_by(
            competition_results.c.place.asc().nullslast(),
            competition_results.c.id,
        ),
    )


async def get_result(
    discipline_id: CompetitionDisciplineId,
    result_id: CompetitionResultId,
) -> CompetitionResult | None:
    return await fetch_one_parsed(
        database,
        CompetitionResult,
        competition_results.select().where(
            (competition_results.c.id == result_id)
            & (
                competition_results.c.discipline_id
                == discipline_id
            )
        ),
    )


async def upsert_result(
    result: CompetitionResultInsertable,
) -> CompetitionResultId:
    existing = await fetch_one_parsed(
        database,
        CompetitionResult,
        competition_results.select().where(
            (
                competition_results.c.discipline_id
                == result.discipline_id
            )
            & (
                competition_results.c.team_id
                == result.team_id
            )
        ),
    )

    values = result.model_dump()

    if existing is not None:
        await database.execute(
            competition_results.update()
            .where(competition_results.c.id == existing.id)
            .values(**values)
        )
        return existing.id

    new_id = await database.execute(
        competition_results.insert(),
        values=values,
    )

    return CompetitionResultId(new_id)


async def update_result_place(
    result_id: CompetitionResultId,
    place: int | None,
) -> None:
    await database.execute(
        competition_results.update()
        .where(competition_results.c.id == result_id)
        .values(place=place)
    )


async def get_tournament_overall_standings(
    tournament_id: TournamentId,
) -> list[TournamentOverallStanding]:
    numeric_points = Numeric(12, 2)
    zero = cast(0, numeric_points)

    game_totals = (
        select(
            stage_item_inputs.c.team_id.label("team_id"),
            func.sum(cast(stage_item_inputs.c.points, numeric_points)).label(
                "game_points"
            ),
            func.min(stage_item_inputs.c.id).label("hockey_order"),
        )
        .where(
            (stage_item_inputs.c.tournament_id == tournament_id)
            & stage_item_inputs.c.team_id.is_not(None)
        )
        .group_by(stage_item_inputs.c.team_id)
        .subquery()
    )

    competition_totals = (
        select(
            competition_results.c.team_id.label("team_id"),
            func.sum(competition_scoring.c.points).label("competition_points"),
        )
        .select_from(
            competition_results.join(
                competition_disciplines,
                competition_disciplines.c.id
                == competition_results.c.discipline_id,
            )
            .join(
                competitions,
                competitions.c.id == competition_disciplines.c.competition_id,
            )
            .join(
                competition_scoring,
                (competition_scoring.c.competition_id == competitions.c.id)
                & (competition_scoring.c.place == competition_results.c.place),
            )
        )
        .where(competitions.c.tournament_id == tournament_id)
        .group_by(competition_results.c.team_id)
        .subquery()
    )

    game_points = func.coalesce(game_totals.c.game_points, zero)
    competition_points = func.coalesce(
        competition_totals.c.competition_points,
        zero,
    )
    total_points = game_points + competition_points

    query = (
        select(
            teams.c.id.label("team_id"),
            teams.c.name.label("team_name"),
            clubs.c.id.label("club_id"),
            clubs.c.name.label("club_name"),
            game_points.label("game_points"),
            competition_points.label("competition_points"),
            total_points.label("total_points"),
        )
        .outerjoin(clubs, clubs.c.id == teams.c.participant_club_id)
        .outerjoin(game_totals, game_totals.c.team_id == teams.c.id)
        .outerjoin(
            competition_totals,
            competition_totals.c.team_id == teams.c.id,
        )
        .where(teams.c.tournament_id == tournament_id)
        .order_by(
            total_points.desc(),
            game_points.desc(),
            game_totals.c.hockey_order.asc().nullslast(),
            teams.c.id,
        )
    )

    tournament = await sql_get_tournament(tournament_id)
    standings = await fetch_all_parsed(database, TournamentOverallStanding, query)
    if tournament.competition_format is TournamentCompetitionFormat.YOUTH_CLUB:
        return aggregate_club_standings(standings)
    return standings
