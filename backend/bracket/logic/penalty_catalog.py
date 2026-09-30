from enum import auto

from pydantic import BaseModel

from bracket.models.db.shared import BaseModelORM
from bracket.models.db.tournament import HockeyAgeCategory, HockeyRuleset
from bracket.utils.types import EnumAutoStr

SUPPORTED_SEASON = "2026/27"


class PenaltyType(EnumAutoStr):
    MINOR = auto()
    DOUBLE_MINOR = auto()
    BENCH_MINOR = auto()
    MAJOR = auto()
    MISCONDUCT = auto()
    GAME_MISCONDUCT = auto()
    MAJOR_GAME_MISCONDUCT = auto()
    MINOR_MISCONDUCT = auto()
    MINOR_GAME_MISCONDUCT = auto()
    PENALTY_SHOT = auto()
    AWARDED_GOAL = auto()
    CUSTOM = auto()


class PenaltyTypeDefinition(BaseModelORM):
    type: PenaltyType
    label: str
    minutes: int | None
    game_misconduct: bool


class PenaltyDefinition(BaseModelORM):
    code: str
    rule: str | None
    label: str
    category: str
    default_penalty_type: PenaltyType
    allowed_penalty_types: tuple[PenaltyType, ...]


class PenaltyCatalog(BaseModelORM):
    ruleset: HockeyRuleset
    season: str
    age_category: HockeyAgeCategory
    catalog_source: str
    penalty_types: tuple[PenaltyTypeDefinition, ...]
    penalties: tuple[PenaltyDefinition, ...]


class UnsupportedPenaltyCatalogError(ValueError):
    pass


PENALTY_TYPES = (
    PenaltyTypeDefinition(
        type=PenaltyType.MINOR,
        label="2 Minuten",
        minutes=2,
        game_misconduct=False,
    ),
    PenaltyTypeDefinition(
        type=PenaltyType.DOUBLE_MINOR,
        label="4 Minuten",
        minutes=4,
        game_misconduct=False,
    ),
    PenaltyTypeDefinition(
        type=PenaltyType.BENCH_MINOR,
        label="2 Minuten Bankstrafe",
        minutes=2,
        game_misconduct=False,
    ),
    PenaltyTypeDefinition(
        type=PenaltyType.MAJOR,
        label="5 Minuten",
        minutes=5,
        game_misconduct=False,
    ),
    PenaltyTypeDefinition(
        type=PenaltyType.MISCONDUCT,
        label="10 Minuten Disziplinarstrafe",
        minutes=10,
        game_misconduct=False,
    ),
    PenaltyTypeDefinition(
        type=PenaltyType.GAME_MISCONDUCT,
        label="Spieldauerdisziplinarstrafe",
        minutes=None,
        game_misconduct=True,
    ),
    PenaltyTypeDefinition(
        type=PenaltyType.MAJOR_GAME_MISCONDUCT,
        label="5 Minuten + Spieldauer",
        minutes=5,
        game_misconduct=True,
    ),
    PenaltyTypeDefinition(
        type=PenaltyType.MINOR_MISCONDUCT,
        label="2 Minuten + 10 Minuten Disziplinarstrafe",
        minutes=2,
        game_misconduct=False,
    ),
    PenaltyTypeDefinition(
        type=PenaltyType.MINOR_GAME_MISCONDUCT,
        label="2 Minuten + Spieldauer",
        minutes=2,
        game_misconduct=True,
    ),
    PenaltyTypeDefinition(
        type=PenaltyType.PENALTY_SHOT,
        label="Strafschuss",
        minutes=None,
        game_misconduct=False,
    ),
    PenaltyTypeDefinition(
        type=PenaltyType.AWARDED_GOAL,
        label="Zugesprochenes Tor",
        minutes=None,
        game_misconduct=False,
    ),
    PenaltyTypeDefinition(
        type=PenaltyType.CUSTOM,
        label="Benutzerdefiniert",
        minutes=None,
        game_misconduct=False,
    ),
)
PENALTY_TYPE_BY_TYPE = {definition.type: definition for definition in PENALTY_TYPES}


def _penalty(
    code: str,
    rule: str,
    label: str,
    category: str,
    default: PenaltyType,
    *allowed: PenaltyType,
) -> PenaltyDefinition:
    allowed_types = tuple(dict.fromkeys((default, *allowed, PenaltyType.CUSTOM)))
    return PenaltyDefinition(
        code=code,
        rule=rule,
        label=label,
        category=category,
        default_penalty_type=default,
        allowed_penalty_types=allowed_types,
    )


IIHF_2026_27_PENALTIES = (
    _penalty("BOARDING", "41", "Bandencheck", "BODY", PenaltyType.MINOR, PenaltyType.MAJOR_GAME_MISCONDUCT),
    _penalty("CHARGING", "42", "Unerlaubter Körperangriff", "BODY", PenaltyType.MINOR, PenaltyType.MAJOR_GAME_MISCONDUCT),
    _penalty("CHECKING_FROM_BEHIND", "43", "Check von hinten", "BODY", PenaltyType.MINOR_MISCONDUCT, PenaltyType.MAJOR_GAME_MISCONDUCT),
    _penalty("CLIPPING", "44", "Tiefcheck / Clipping", "BODY", PenaltyType.MINOR, PenaltyType.MAJOR_GAME_MISCONDUCT),
    _penalty("ELBOWING", "45", "Ellbogencheck", "BODY", PenaltyType.MINOR, PenaltyType.MAJOR_GAME_MISCONDUCT),
    _penalty("FIGHTING", "46", "Faustkampf", "CONDUCT", PenaltyType.MAJOR_GAME_MISCONDUCT),
    _penalty("HEAD_BUTTING", "47", "Kopfstoß", "BODY", PenaltyType.DOUBLE_MINOR, PenaltyType.MAJOR_GAME_MISCONDUCT),
    _penalty("CHECK_TO_HEAD_NECK", "48", "Check gegen Kopf oder Nacken", "BODY", PenaltyType.MINOR, PenaltyType.MAJOR_GAME_MISCONDUCT),
    _penalty("KICKING", "49", "Treten", "BODY", PenaltyType.MAJOR_GAME_MISCONDUCT),
    _penalty("KNEEING", "50", "Kniecheck", "BODY", PenaltyType.MINOR, PenaltyType.MAJOR_GAME_MISCONDUCT),
    _penalty("ROUGHING", "51", "Übertriebene Härte", "CONDUCT", PenaltyType.MINOR, PenaltyType.DOUBLE_MINOR, PenaltyType.MAJOR_GAME_MISCONDUCT),
    _penalty("SLEW_FOOTING", "52", "Slew-footing", "BODY", PenaltyType.MAJOR_GAME_MISCONDUCT),
    _penalty("THROWING_EQUIPMENT", "53", "Werfen von Ausrüstung", "GAME", PenaltyType.MINOR, PenaltyType.PENALTY_SHOT, PenaltyType.AWARDED_GOAL),
    _penalty("HOLDING", "54", "Halten", "OBSTRUCTION", PenaltyType.MINOR, PenaltyType.PENALTY_SHOT, PenaltyType.AWARDED_GOAL),
    _penalty("HOOKING", "55", "Haken", "OBSTRUCTION", PenaltyType.MINOR, PenaltyType.PENALTY_SHOT, PenaltyType.AWARDED_GOAL),
    _penalty("INTERFERENCE", "56", "Behinderung", "OBSTRUCTION", PenaltyType.MINOR, PenaltyType.MAJOR_GAME_MISCONDUCT, PenaltyType.PENALTY_SHOT, PenaltyType.AWARDED_GOAL),
    _penalty("TRIPPING", "57", "Beinstellen", "OBSTRUCTION", PenaltyType.MINOR, PenaltyType.MAJOR_GAME_MISCONDUCT, PenaltyType.PENALTY_SHOT, PenaltyType.AWARDED_GOAL),
    _penalty("BUTT_ENDING", "58", "Stockendenstoß", "STICK", PenaltyType.DOUBLE_MINOR, PenaltyType.MAJOR_GAME_MISCONDUCT),
    _penalty("CROSS_CHECKING", "59", "Stockcheck", "STICK", PenaltyType.MINOR, PenaltyType.MAJOR_GAME_MISCONDUCT),
    _penalty("HIGH_STICKING", "60", "Hoher Stock", "STICK", PenaltyType.MINOR, PenaltyType.DOUBLE_MINOR, PenaltyType.MAJOR_GAME_MISCONDUCT),
    _penalty("SLASHING", "61", "Stockschlag", "STICK", PenaltyType.MINOR, PenaltyType.MAJOR_GAME_MISCONDUCT),
    _penalty("SPEARING", "62", "Stockstich", "STICK", PenaltyType.DOUBLE_MINOR, PenaltyType.MAJOR_GAME_MISCONDUCT),
    _penalty("DELAY_OF_GAME", "63", "Spielverzögerung", "GAME", PenaltyType.MINOR, PenaltyType.BENCH_MINOR, PenaltyType.PENALTY_SHOT, PenaltyType.AWARDED_GOAL),
    _penalty("DIVING_EMBELLISHMENT", "64", "Schwalbe / Täuschung", "CONDUCT", PenaltyType.MINOR),
    _penalty("EQUIPMENT", "65", "Unerlaubte Ausrüstung", "GAME", PenaltyType.MINOR),
    _penalty("HANDLING_PUCK", "67", "Unerlaubtes Spielen/Festhalten des Pucks", "GAME", PenaltyType.MINOR, PenaltyType.PENALTY_SHOT, PenaltyType.AWARDED_GOAL),
    _penalty("ILLEGAL_SUBSTITUTION", "68", "Unerlaubter Spielerwechsel", "GAME", PenaltyType.BENCH_MINOR),
    _penalty("GOALTENDER_INTERFERENCE", "69", "Torhüterbehinderung", "OBSTRUCTION", PenaltyType.MINOR, PenaltyType.MAJOR_GAME_MISCONDUCT),
    _penalty("LEAVING_BENCH", "70", "Verlassen der Spieler-/Strafbank", "CONDUCT", PenaltyType.MINOR, PenaltyType.MISCONDUCT, PenaltyType.GAME_MISCONDUCT),
    _penalty("TOO_MANY_PLAYERS", "74", "Zu viele Spieler auf dem Eis", "GAME", PenaltyType.BENCH_MINOR),
    _penalty("UNSPORTSMANLIKE_CONDUCT", "75", "Unsportliches Verhalten", "CONDUCT", PenaltyType.MINOR, PenaltyType.MISCONDUCT, PenaltyType.GAME_MISCONDUCT),
    PenaltyDefinition(
        code="OTHER",
        rule=None,
        label="Sonstige",
        category="OTHER",
        default_penalty_type=PenaltyType.CUSTOM,
        allowed_penalty_types=(PenaltyType.CUSTOM,),
    ),
)
PENALTY_BY_CODE = {definition.code: definition for definition in IIHF_2026_27_PENALTIES}


def get_penalty_catalog(
    ruleset: HockeyRuleset,
    season: str,
    age_category: HockeyAgeCategory,
) -> PenaltyCatalog:
    if season != SUPPORTED_SEASON:
        raise UnsupportedPenaltyCatalogError(
            f"No penalty catalog is available for {ruleset.value} season {season}"
        )
    return PenaltyCatalog(
        ruleset=ruleset,
        season=season,
        age_category=age_category,
        catalog_source="IIHF_2026_27" if ruleset is HockeyRuleset.IIHF else "IIHF_BASE",
        penalty_types=PENALTY_TYPES,
        penalties=IIHF_2026_27_PENALTIES,
    )