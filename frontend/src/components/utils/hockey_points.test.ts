import { MatchInterface } from '../../interfaces/match';
import { getCompetitionMatchPoints, getGameShootoutMatchPoints } from './hockey_points';

function matchWithScores(
  game1: number,
  game2: number,
  shootout1: number,
  shootout2: number
): MatchInterface {
  return {
    stage_item_input1_score: game1,
    stage_item_input2_score: game2,
    stage_item_input1_penalty_score: shootout1,
    stage_item_input2_penalty_score: shootout2,
    stage_item_input1_half1_score: 0,
    stage_item_input2_half1_score: 0,
    stage_item_input1_half2_score: 0,
    stage_item_input2_half2_score: 0,
  } as MatchInterface;
}

describe('getGameShootoutMatchPoints', () => {
  it.each([
    [1, 0, 0, 0, [2, 0.5]],
    [0, 0, 0, 0, [1.5, 1.5]],
    [2, 3, 3, 1, [1, 2]],
    [1, 1, 3, 1, [2, 1]],
    [3, 1, 1, 2, [2, 1]],
  ])(
    'scores Game %i:%i and Shootout %i:%i as %j',
    (game1, game2, shootout1, shootout2, expected) => {
      expect(
        getGameShootoutMatchPoints(matchWithScores(game1, game2, shootout1, shootout2))
      ).toEqual(expected);
    }
  );
});

test('competition scoring remains based on both halves and shootout', () => {
  const match = matchWithScores(99, 98, 1, 0);
  match.stage_item_input1_half1_score = 2;
  match.stage_item_input2_half1_score = 1;
  match.stage_item_input1_half2_score = 0;
  match.stage_item_input2_half2_score = 0;

  expect(getCompetitionMatchPoints(match)).toEqual([4, 1]);
});
