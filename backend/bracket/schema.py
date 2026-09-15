from sqlalchemy import (
    CheckConstraint,
    Column,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Table,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import declarative_base  # type: ignore[attr-defined]
from sqlalchemy.sql.sqltypes import BigInteger, Boolean, DateTime, Enum, Float, Text

Base = declarative_base()
metadata = Base.metadata
DateTimeTZ = DateTime(timezone=True)

clubs = Table(
    "clubs",
    metadata,
    Column("id", BigInteger, primary_key=True, index=True, autoincrement=True),
    Column("name", String, nullable=False, index=True),
    Column("created", DateTimeTZ, nullable=False, server_default=func.now()),
)

tournaments = Table(
    "tournaments",
    metadata,
    Column("id", BigInteger, primary_key=True, index=True),
    Column("name", String, nullable=False, index=True),
    Column("created", DateTimeTZ, nullable=False, server_default=func.now()),
    Column("start_time", DateTimeTZ, nullable=False),
    Column("club_id", BigInteger, ForeignKey("clubs.id"), index=True, nullable=False),
    Column("dashboard_public", Boolean, nullable=False),
    Column("logo_path", String, nullable=True),
    Column("dashboard_endpoint", String, nullable=True, index=True, unique=True),
    Column("players_can_be_in_multiple_teams", Boolean, nullable=False, server_default="f"),
    Column("auto_assign_courts", Boolean, nullable=False, server_default="f"),
    Column("hockey_mode", String(20), nullable=False, server_default="COMPETITION"),
    Column("competition_format", String(20), nullable=False, server_default="STANDARD"),
    Column("ruleset", String(20), nullable=False, server_default="DEB"),
    Column("age_category", String(20), nullable=False, server_default="U15"),
    Column("ruleset_season", String(7), nullable=False, server_default="2026/27"),
    Column("duration_minutes", Integer, nullable=False, server_default="15"),
    Column("margin_minutes", Integer, nullable=False, server_default="5"),
    Column(
        "status",
        Enum(
            "OPEN",
            "ARCHIVED",
            name="tournament_status",
        ),
        nullable=False,
        server_default="OPEN",
        index=True,
    ),
    CheckConstraint(
        "hockey_mode IN ('COMPETITION', 'GAME_SHOOTOUT', 'STANDARD')",
        name="ck_tournaments_hockey_mode",
    ),
    CheckConstraint(
        "competition_format IN ('STANDARD', 'YOUTH_CLUB')",
        name="ck_tournaments_competition_format",
    ),
    CheckConstraint("ruleset IN ('DEB', 'IIHF')", name="ck_tournaments_ruleset"),
    CheckConstraint(
        "age_category IN ('U9', 'U11', 'U13', 'U15', 'U17', 'U20', 'SENIOR')",
        name="ck_tournaments_age_category",
    ),
    CheckConstraint(
        "ruleset_season ~ '^[0-9]{4}/[0-9]{2}$' "
        "AND substring(ruleset_season from 6 for 2)::integer = "
        "(substring(ruleset_season from 1 for 4)::integer + 1) % 100",
        name="ck_tournaments_ruleset_season",
    ),
)

tournament_sponsors = Table(
    "tournament_sponsors",
    metadata,
    Column("id", BigInteger, primary_key=True, index=True, autoincrement=True),
    Column(
        "tournament_id",
        BigInteger,
        ForeignKey("tournaments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    ),
    Column("name", String, nullable=False),
    Column("logo_path", String, nullable=False),
    Column("url", String, nullable=True),
    Column("position", String(10), nullable=False),
    Column("sort_order", Integer, nullable=False, server_default="0"),
    CheckConstraint("position IN ('LEFT', 'RIGHT')", name="ck_tournament_sponsors_position"),
)

stages = Table(
    "stages",
    metadata,
    Column("id", BigInteger, primary_key=True, index=True),
    Column("name", String, nullable=False, index=True),
    Column("created", DateTimeTZ, nullable=False, server_default=func.now()),
    Column("tournament_id", BigInteger, ForeignKey("tournaments.id"), index=True, nullable=False),
    Column("is_active", Boolean, nullable=False, server_default="false"),
)

stage_items = Table(
    "stage_items",
    metadata,
    Column("id", BigInteger, primary_key=True, index=True),
    Column("name", Text, nullable=False),
    Column("created", DateTimeTZ, nullable=False, server_default=func.now()),
    Column("stage_id", BigInteger, ForeignKey("stages.id"), index=True, nullable=False),
    Column("team_count", Integer, nullable=False),
    Column("ranking_id", BigInteger, ForeignKey("rankings.id"), nullable=False),
    Column("is_youth_club_group", Boolean, nullable=False, server_default="false"),
    Column(
        "type",
        Enum(
            "SINGLE_ELIMINATION",
            "SWISS",
            "ROUND_ROBIN",
            name="stage_type",
        ),
        nullable=False,
    ),
)

stage_item_inputs = Table(
    "stage_item_inputs",
    metadata,
    Column("id", BigInteger, primary_key=True, index=True),
    Column("slot", Integer, nullable=False),
    Column("tournament_id", BigInteger, ForeignKey("tournaments.id"), index=True, nullable=False),
    Column(
        "stage_item_id",
        BigInteger,
        ForeignKey("stage_items.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    ),
    Column("team_id", BigInteger, ForeignKey("teams.id"), nullable=True),
    Column("winner_from_stage_item_id", BigInteger, ForeignKey("stage_items.id"), nullable=True),
    Column("winner_position", Integer, nullable=True),
    Column("points", Float, nullable=False, server_default="0"),
    Column("wins", Integer, nullable=False, server_default="0"),
    Column("draws", Integer, nullable=False, server_default="0"),
    Column("losses", Integer, nullable=False, server_default="0"),
    UniqueConstraint("stage_item_id", "team_id"),
    UniqueConstraint("stage_item_id", "winner_from_stage_item_id", "winner_position"),
)

rounds = Table(
    "rounds",
    metadata,
    Column("id", BigInteger, primary_key=True, index=True),
    Column("name", Text, nullable=False),
    Column("created", DateTimeTZ, nullable=False, server_default=func.now()),
    Column("is_draft", Boolean, nullable=False),
    Column("stage_item_id", BigInteger, ForeignKey("stage_items.id"), nullable=False),
)


matches = Table(
    "matches",
    metadata,
    Column("id", BigInteger, primary_key=True, index=True),
    Column("created", DateTimeTZ, nullable=False, server_default=func.now()),
    Column("start_time", DateTimeTZ, nullable=True),
    Column("duration_minutes", Integer, nullable=True),
    Column("margin_minutes", Integer, nullable=True),
    Column("custom_duration_minutes", Integer, nullable=True),
    Column("custom_margin_minutes", Integer, nullable=True),
    Column("round_id", BigInteger, ForeignKey("rounds.id"), nullable=False),
    Column("stage_item_input1_id", BigInteger, ForeignKey("stage_item_inputs.id"), nullable=True),
    Column("stage_item_input2_id", BigInteger, ForeignKey("stage_item_inputs.id"), nullable=True),
    Column("stage_item_input1_conflict", Boolean, nullable=False),
    Column("stage_item_input2_conflict", Boolean, nullable=False),
    Column(
        "stage_item_input1_winner_from_match_id",
        BigInteger,
        ForeignKey("matches.id"),
        nullable=True,
    ),
    Column(
        "stage_item_input2_winner_from_match_id",
        BigInteger,
        ForeignKey("matches.id"),
        nullable=True,
    ),
    Column("court_id", BigInteger, ForeignKey("courts.id"), nullable=True),
    Column("stage_item_input1_score", Integer, nullable=False),
    Column("stage_item_input2_score", Integer, nullable=False),
    Column("stage_item_input1_half1_score", Integer, nullable=False, server_default="0"),
    Column("stage_item_input2_half1_score", Integer, nullable=False, server_default="0"),
    Column("stage_item_input1_half2_score", Integer, nullable=False, server_default="0"),
    Column("stage_item_input2_half2_score", Integer, nullable=False, server_default="0"),
    Column("stage_item_input1_penalty_score", Integer, nullable=False, server_default="0"),
    Column("stage_item_input2_penalty_score", Integer, nullable=False, server_default="0"), 
    Column("status", String(20), nullable=False, server_default="PLANNED"),
    Column("active_period", String(20), nullable=True),
    Column("phase_state", String(20), nullable=True),
    Column("ruleset_override", String(20), nullable=True),
    Column("age_category_override", String(20), nullable=True),
    Column("ruleset_season_override", String(7), nullable=True),
    Column("score_entry_source", String(10), nullable=True),
    CheckConstraint(
        "status IN ('PLANNED', 'RUNNING', 'FINISHED')",
        name="ck_matches_status",
    ),
    CheckConstraint(
        "active_period IS NULL OR active_period IN "
        "('GAME', 'HALF1', 'HALF2', 'SHOOTOUT', 'PERIOD1', 'PERIOD2', 'PERIOD3', 'OVERTIME')",
        name="ck_matches_active_period",
    ),
    CheckConstraint(
        "phase_state IS NULL OR phase_state IN ('ACTIVE', 'BREAK')",
        name="ck_matches_phase_state",
    ),
    CheckConstraint(
        "ruleset_override IS NULL OR ruleset_override IN ('DEB', 'IIHF')",
        name="ck_matches_ruleset_override",
    ),
    CheckConstraint(
        "age_category_override IS NULL OR age_category_override "
        "IN ('U9', 'U11', 'U13', 'U15', 'U17', 'U20', 'SENIOR')",
        name="ck_matches_age_category_override",
    ),
    CheckConstraint(
        "ruleset_season_override IS NULL OR ("
        "ruleset_season_override ~ '^[0-9]{4}/[0-9]{2}$' "
        "AND substring(ruleset_season_override from 6 for 2)::integer = "
        "(substring(ruleset_season_override from 1 for 4)::integer + 1) % 100)",
        name="ck_matches_ruleset_season_override",
    ),
    CheckConstraint(
        "score_entry_source IS NULL OR score_entry_source IN ('MANUAL', 'EVENTS')",
        name="ck_matches_score_entry_source",
    ),
    Column("position_in_schedule", Integer, nullable=True),
)

teams = Table(
    "teams",
    metadata,
    Column("id", BigInteger, primary_key=True, index=True),
    Column("name", String, nullable=False, index=True),
    Column("created", DateTimeTZ, nullable=False, server_default=func.now()),
    Column("tournament_id", BigInteger, ForeignKey("tournaments.id"), index=True, nullable=False),
    Column("participant_club_id", BigInteger, ForeignKey("clubs.id"), nullable=True),
    Column("pairing_group", String(32), nullable=True),
    Column("active", Boolean, nullable=False, index=True, server_default="t"),
    Column("elo_score", Float, nullable=False, server_default="0"),
    Column("swiss_score", Float, nullable=False, server_default="0"),
    Column("wins", Integer, nullable=False, server_default="0"),
    Column("draws", Integer, nullable=False, server_default="0"),
    Column("losses", Integer, nullable=False, server_default="0"),
    Column("logo_path", String, nullable=True),
    Index("ix_teams_tournament_id_participant_club_id", "tournament_id", "participant_club_id"),
)

players = Table(
    "players",
    metadata,
    Column("id", BigInteger, primary_key=True, index=True),
    Column("name", String, nullable=False, index=True),
    Column("first_name", String, nullable=True),
    Column("last_name", String, nullable=True),
    Column("created", DateTimeTZ, nullable=False, server_default=func.now()),
    Column("tournament_id", BigInteger, ForeignKey("tournaments.id"), index=True, nullable=False),
    Column("elo_score", Float, nullable=False),
    Column("swiss_score", Float, nullable=False),
    Column("wins", Integer, nullable=False),
    Column("draws", Integer, nullable=False),
    Column("losses", Integer, nullable=False),
    Column("active", Boolean, nullable=False, index=True, server_default="t"),
)

users = Table(
    "users",
    metadata,
    Column("id", BigInteger, primary_key=True, index=True),
    Column("email", String, nullable=False, index=True, unique=True),
    Column("name", String, nullable=False),
    Column("password_hash", String, nullable=False),
    Column("created", DateTimeTZ, nullable=False, server_default=func.now()),
    Column(
        "account_type",
        Enum(
            "REGULAR",
            "ADMIN",
            "SCORER",
            "DEMO",
            name="account_type",
        ),
        nullable=False,
    ),
)

users_x_clubs = Table(
    "users_x_clubs",
    metadata,
    Column("id", BigInteger, primary_key=True, index=True),
    Column("club_id", BigInteger, ForeignKey("clubs.id", ondelete="CASCADE"), nullable=False),
    Column("user_id", BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
    Column(
        "relation",
        Enum(
            "OWNER",
            "COLLABORATOR",
            name="user_x_club_relation",
        ),
        nullable=False,
        default="OWNER",
    ),
)

players_x_teams = Table(
    "players_x_teams",
    metadata,
    Column("id", BigInteger, primary_key=True, index=True),
    Column("player_id", BigInteger, ForeignKey("players.id", ondelete="CASCADE"), nullable=False),
    Column("team_id", BigInteger, ForeignKey("teams.id", ondelete="CASCADE"), nullable=False),
    Column("number", Integer, nullable=True),
    Column("position", String, nullable=True),
)

match_events = Table(
    "match_events",
    metadata,
    Column("id", BigInteger, primary_key=True, index=True),
    Column(
        "match_id",
        BigInteger,
        ForeignKey("matches.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    ),
    Column("team_id", BigInteger, ForeignKey("teams.id"), nullable=False),
    Column("event_type", String(20), nullable=False),
    Column("period", String(20), nullable=False),
    Column("game_time_seconds", Integer, nullable=True),
    Column(
        "player_id",
        BigInteger,
        ForeignKey("players.id", ondelete="SET NULL"),
        nullable=True,
    ),
    Column("player_number", Integer, nullable=True),
    Column("player_name", String, nullable=True),
    Column(
        "assist1_player_id",
        BigInteger,
        ForeignKey("players.id", ondelete="SET NULL"),
        nullable=True,
    ),
    Column("assist1_number", Integer, nullable=True),
    Column("assist1_name", String, nullable=True),
    Column(
        "assist2_player_id",
        BigInteger,
        ForeignKey("players.id", ondelete="SET NULL"),
        nullable=True,
    ),
    Column("assist2_number", Integer, nullable=True),
    Column("assist2_name", String, nullable=True),
    Column("penalty_code", String, nullable=True),
    Column("penalty_rule", String, nullable=True),
    Column("penalty_type", String, nullable=True),
    Column("penalty_minutes", Integer, nullable=True),
    Column("infraction", String, nullable=True),
    Column("game_misconduct", Boolean, nullable=True),
    Column("sort_order", Integer, nullable=False, server_default="0"),
    Column("created", DateTimeTZ, nullable=False, server_default=func.now()),
    CheckConstraint("event_type IN ('GOAL', 'PENALTY')", name="ck_match_events_event_type"),
    CheckConstraint(
        "period IN "
        "('GAME', 'HALF1', 'HALF2', 'SHOOTOUT', 'PERIOD1', 'PERIOD2', 'PERIOD3', 'OVERTIME')",
        name="ck_match_events_period",
    ),
    CheckConstraint("game_time_seconds >= 0", name="ck_match_events_game_time_positive"),
    CheckConstraint(
        "penalty_minutes IS NULL OR penalty_minutes >= 0",
        name="ck_match_events_penalty_minutes_positive",
    ),
)

courts = Table(
    "courts",
    metadata,
    Column("id", BigInteger, primary_key=True, index=True),
    Column("name", Text, nullable=False),
    Column("created", DateTimeTZ, nullable=False, server_default=func.now()),
    Column("tournament_id", BigInteger, ForeignKey("tournaments.id"), nullable=False, index=True),
)

rankings = Table(
    "rankings",
    metadata,
    Column("id", BigInteger, primary_key=True, index=True),
    Column("created", DateTimeTZ, nullable=False, server_default=func.now()),
    Column("tournament_id", BigInteger, ForeignKey("tournaments.id"), nullable=False, index=True),
    Column("position", Integer, nullable=False),
    Column("win_points", Float, nullable=False),
    Column("draw_points", Float, nullable=False),
    Column("loss_points", Float, nullable=False),
    Column("add_score_points", Boolean, nullable=False),
)

competitions = Table(
    "competitions",
    metadata,
    Column("id", BigInteger, primary_key=True, index=True, autoincrement=True),
    Column(
        "tournament_id",
        BigInteger,
        ForeignKey("tournaments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    ),
    Column("name", String, nullable=False),
    Column("description", Text, nullable=True),
    Column("start_time", DateTimeTZ, nullable=False, index=True),
    Column("duration_minutes", Integer, nullable=False, server_default="60"),
    Column(
        "court_id",
        BigInteger,
        ForeignKey("courts.id", ondelete="SET NULL"),
        nullable=True,
    ),
    Column("created", DateTimeTZ, nullable=False, server_default=func.now()),
    CheckConstraint(
        "duration_minutes > 0",
        name="ck_competitions_duration_positive",
    ),
)

competition_disciplines = Table(
    "competition_disciplines",
    metadata,
    Column("id", BigInteger, primary_key=True, index=True, autoincrement=True),
    Column(
        "competition_id",
        BigInteger,
        ForeignKey("competitions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    ),
    Column("name", String, nullable=False),
    Column("description", Text, nullable=True),
    Column("metric_type", String(20), nullable=False, server_default="MANUAL"),
    Column("sort_order", Integer, nullable=False, server_default="0"),
    Column("created", DateTimeTZ, nullable=False, server_default=func.now()),
    CheckConstraint(
        "metric_type IN ('TIME', 'COUNT', 'RATIO', 'MANUAL')",
        name="ck_competition_discipline_metric_type",
    ),
)

competition_scoring = Table(
    "competition_scoring",
    metadata,
    Column("id", BigInteger, primary_key=True, index=True, autoincrement=True),
    Column(
        "competition_id",
        BigInteger,
        ForeignKey("competitions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    ),
    Column("place", Integer, nullable=False),
    Column("points", Numeric(8, 2), nullable=False),
    CheckConstraint(
        "place > 0",
        name="ck_competition_scoring_place_positive",
    ),
    CheckConstraint(
        "points >= 0",
        name="ck_competition_scoring_points_positive",
    ),
    UniqueConstraint(
        "competition_id",
        "place",
        name="uq_competition_scoring_place",
    ),
)

competition_results = Table(
    "competition_results",
    metadata,
    Column("id", BigInteger, primary_key=True, index=True, autoincrement=True),
    Column(
        "discipline_id",
        BigInteger,
        ForeignKey("competition_disciplines.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    ),
    Column(
        "team_id",
        BigInteger,
        ForeignKey("teams.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    ),
    Column("place", Integer, nullable=True),
    Column("time_ms", BigInteger, nullable=True),
    Column("attempts", Integer, nullable=True),
    Column("successes", Integer, nullable=True),
    Column("notes", Text, nullable=True),
    Column("updated", DateTimeTZ, nullable=False, server_default=func.now()),
    CheckConstraint(
        "place IS NULL OR place > 0",
        name="ck_competition_results_place_positive",
    ),
    CheckConstraint(
        "time_ms IS NULL OR time_ms >= 0",
        name="ck_competition_results_time_positive",
    ),
    CheckConstraint(
        "attempts IS NULL OR attempts >= 0",
        name="ck_competition_results_attempts_positive",
    ),
    CheckConstraint(
        "successes IS NULL OR successes >= 0",
        name="ck_competition_results_successes_positive",
    ),
    CheckConstraint(
        "attempts IS NULL OR successes IS NULL OR successes <= attempts",
        name="ck_competition_results_successes_lte_attempts",
    ),
    UniqueConstraint(
        "discipline_id",
        "team_id",
        name="uq_competition_result_team",
    ),
)

competition_pairings = Table(
    "competition_pairings",
    metadata,
    Column("id", BigInteger, primary_key=True, index=True, autoincrement=True),
    Column(
        "discipline_id",
        BigInteger,
        ForeignKey("competition_disciplines.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    ),
    Column(
        "shooter_team_id",
        BigInteger,
        ForeignKey("teams.id", ondelete="CASCADE"),
        nullable=True,
    ),
    Column(
        "goalkeeper_team_id",
        BigInteger,
        ForeignKey("teams.id", ondelete="CASCADE"),
        nullable=True,
    ),
    Column("shooter_name", String, nullable=True),
    Column("goalkeeper_name", String, nullable=True),
    Column("sort_order", Integer, nullable=False, server_default="0"),
    Column("notes", Text, nullable=True),
)
