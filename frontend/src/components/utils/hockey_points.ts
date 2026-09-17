import { MatchInterface } from '../../interfaces/match';

function segmentPoints(
  score1: number,
  score2: number,
  winPoints: number,
  drawPoints: number
): [number, number] {
  if (score1 > score2) return [winPoints, 0];
  if (score2 > score1) return [0, winPoints];
  return [drawPoints, drawPoints];
}

export function getCompetitionMatchPoints(match: MatchInterface): [number, number] {
  const half1 = segmentPoints(
    match.stage_item_input1_half1_score,
    match.stage_item_input2_half1_score,
    2,
    1
  );
  const half2 = segmentPoints(
    match.stage_item_input1_half2_score,
    match.stage_item_input2_half2_score,
    2,
    1
  );
  const shootout = segmentPoints(
    match.stage_item_input1_penalty_score,
    match.stage_item_input2_penalty_score,
    1,
    0.5
  );

  return [half1[0] + half2[0] + shootout[0], half1[1] + half2[1] + shootout[1]];
}

export function getGameShootoutMatchPoints(match: MatchInterface): [number, number] {
  const game = segmentPoints(match.stage_item_input1_score, match.stage_item_input2_score, 2, 1);
  const shootout = segmentPoints(
    match.stage_item_input1_penalty_score,
    match.stage_item_input2_penalty_score,
    1,
    0.5
  );

  return [game[0] + shootout[0], game[1] + shootout[1]];
}

export function formatHockeyPoints(points: number): string {
  return Number.isInteger(points) ? `${points}` : points.toFixed(1).replace('.', ',');
}
