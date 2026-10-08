import {
  HockeyAgeCategory,
  HockeyMode,
  HockeyRuleset,
  TournamentCompetitionFormat,
  TournamentUpdateBody,
} from '@openapi';
import { Dayjs } from 'dayjs';

import { createAxios, handleRequestError } from './adapter';

export async function createTournament(
  club_id: number,
  name: string,
  dashboard_public: boolean,
  dashboard_endpoint: string,
  players_can_be_in_multiple_teams: boolean,
  auto_assign_courts: boolean,
  start_time: Dayjs,
  duration_minutes: number,
  margin_minutes: number,
  hockey_mode: HockeyMode,
  ruleset: HockeyRuleset,
  age_category: HockeyAgeCategory,
  ruleset_season: string,
  competition_format: TournamentCompetitionFormat,
) {
  return createAxios()
    .post('tournaments', {
      name,
      club_id,
      dashboard_public,
      dashboard_endpoint,
      players_can_be_in_multiple_teams,
      auto_assign_courts,
      start_time,
      duration_minutes,
      margin_minutes,
      hockey_mode,
      ruleset,
      age_category,
      ruleset_season,
      competition_format,
    })
    .catch((response: any) => handleRequestError(response));
}

export async function deleteTournament(tournament_id: number) {
  return createAxios().delete(`tournaments/${tournament_id}`);
}

export async function archiveTournament(tournament_id: number) {
  return createAxios().post(`tournaments/${tournament_id}/change-status`, { status: 'ARCHIVED' });
}

export async function unarchiveTournament(tournament_id: number) {
  return createAxios().post(`tournaments/${tournament_id}/change-status`, { status: 'OPEN' });
}

export async function updateTournament(
  tournament_id: number,
  name: string,
  dashboard_public: boolean,
  dashboard_endpoint: string | null | undefined,
  players_can_be_in_multiple_teams: boolean,
  auto_assign_courts: boolean,
  start_time: string,
  duration_minutes: number,
  margin_minutes: number,
  competition_format: TournamentCompetitionFormat,
  hockeyScoring?: Pick<
    TournamentUpdateBody,
    | 'game_win_points'
    | 'game_draw_points'
    | 'game_loss_points'
    | 'shootout_win_points'
    | 'shootout_draw_points'
    | 'shootout_loss_points'
  >,
) {
  return createAxios()
    .put(`tournaments/${tournament_id}`, {
      name,
      dashboard_public,
      dashboard_endpoint,
      players_can_be_in_multiple_teams,
      auto_assign_courts,
      start_time,
      duration_minutes,
      margin_minutes,
      competition_format,
      ...hockeyScoring,
    })
    .catch((error: Parameters<typeof handleRequestError>[0]) => {
      handleRequestError(error);
      // Preserve existing callers; the scoring form must not report failed saves as success.
      if (hockeyScoring !== undefined) throw error;
    });
}
