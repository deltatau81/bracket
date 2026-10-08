from fastapi import HTTPException
from starlette import status

from bracket.models.db.account import UserAccountType
from bracket.models.db.match import Match, MatchBody
from bracket.models.db.tournament import HockeyMode
from bracket.models.db.user import UserPublic


SCORER_MATCH_UPDATE_FIELDS = {
    "round_id",
    "stage_item_input1_half1_score",
    "stage_item_input2_half1_score",
    "stage_item_input1_half2_score",
    "stage_item_input2_half2_score",
    "stage_item_input1_penalty_score",
    "stage_item_input2_penalty_score",
}


def validate_match_update_permissions(
    user: UserPublic,
    match: Match,
    match_body: MatchBody,
    hockey_mode: HockeyMode = HockeyMode.COMPETITION,
) -> None:
    if user.account_type is not UserAccountType.SCORER:
        return

    if match_body.round_id != match.round_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Scorer cannot move matches between rounds",
        )

    allowed_fields = SCORER_MATCH_UPDATE_FIELDS.copy()
    if hockey_mode is HockeyMode.GAME_SHOOTOUT:
        allowed_fields.update({"stage_item_input1_score", "stage_item_input2_score"})
    forbidden_fields = match_body.model_fields_set - allowed_fields

    if forbidden_fields:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Scorer cannot modify administrative match fields: "
                + ", ".join(sorted(forbidden_fields))
            ),
        )
