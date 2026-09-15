import { getTournamentEndpointFromRouter } from '../components/utils/util';
import {
  HockeyAgeCategory,
  HockeyMode,
  HockeyRuleset,
  TournamentCompetitionFormat,
} from '../interfaces/tournament';
import { createAxios, getTournamentByEndpointName, handleRequestError } from './adapter';

export async function createTournament(
  club_id: number,
  name: string,
  dashboard_public: boolean,
  dashboard_endpoint: string,
  players_can_be_in_multiple_teams: boolean,
  auto_assign_courts: boolean,
  start_time: string,
  duration_minutes: number,
  margin_minutes: number,
  hockey_mode: HockeyMode,
  ruleset: HockeyRuleset,
  age_category: HockeyAgeCategory,
  ruleset_season: string,
  competition_format: TournamentCompetitionFormat
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
  dashboard_endpoint: string,
  players_can_be_in_multiple_teams: boolean,
  auto_assign_courts: boolean,
  start_time: string,
  duration_minutes: number,
  margin_minutes: number,
  competition_format: TournamentCompetitionFormat
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
    })
    .catch((response: any) => handleRequestError(response));
}

export function getTournamentResponseByEndpointName() {
  const endpointName = getTournamentEndpointFromRouter();
  const swrTournamentsResponse = getTournamentByEndpointName(endpointName);

  return swrTournamentsResponse.data?.data;
}
