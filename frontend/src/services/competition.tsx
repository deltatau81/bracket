import useSWR, { SWRResponse } from 'swr';

import {
  CompetitionDisciplineBodyInterface,
  CompetitionResultBodyInterface,
  CompetitionScoringBodyInterface,
  TournamentOverallStandingInterface,
} from '../interfaces/competition';

import { createAxios } from './adapter';

export async function createCompetition(
  tournament_id: number,
  data: {
    name: string;
    description?: string | null;
    start_time: string;
    duration_minutes: number;
    court_id?: number | null;
  }
) {
  return createAxios().post(
    `tournaments/${tournament_id}/competitions`,
    data
  );
}

export async function updateCompetition(
  tournament_id: number,
  competition_id: number,
  data: {
    name: string;
    description?: string | null;
    start_time: string;
    duration_minutes: number;
    court_id?: number | null;
  }
) {
  return createAxios().put(
    `tournaments/${tournament_id}/competitions/${competition_id}`,
    data
  );
}

export async function deleteCompetition(
  tournament_id: number,
  competition_id: number
) {
  return createAxios().delete(
    `tournaments/${tournament_id}/competitions/${competition_id}`
  );
}

export async function saveCompetitionResult(
  tournament_id: number,
  competition_id: number,
  discipline_id: number,
  data: CompetitionResultBodyInterface
) {
  return createAxios().put(
    `tournaments/${tournament_id}/competitions/${competition_id}/disciplines/${discipline_id}/results`,
    data
  );
}

export async function saveCompetitionScoring(
  tournament_id: number,
  competition_id: number,
  data: CompetitionScoringBodyInterface[]
) {
  return createAxios().put(
    `tournaments/${tournament_id}/competitions/${competition_id}/scoring`,
    data
  );
}

export async function calculateCompetitionResults(
  tournament_id: number,
  competition_id: number,
  discipline_id: number
) {
  return createAxios().post(
    `tournaments/${tournament_id}/competitions/${competition_id}/disciplines/${discipline_id}/calculate`
  );
}

export async function createCompetitionDiscipline(
  tournament_id: number,
  competition_id: number,
  data: CompetitionDisciplineBodyInterface
) {
  return createAxios().post(
    `tournaments/${tournament_id}/competitions/${competition_id}/disciplines`,
    data
  );
}

export async function updateCompetitionDiscipline(
  tournament_id: number,
  competition_id: number,
  discipline_id: number,
  data: CompetitionDisciplineBodyInterface
) {
  return createAxios().put(
    `tournaments/${tournament_id}/competitions/${competition_id}/disciplines/${discipline_id}`,
    data
  );
}

export async function deleteCompetitionDiscipline(
  tournament_id: number,
  competition_id: number,
  discipline_id: number
) {
  return createAxios().delete(
    `tournaments/${tournament_id}/competitions/${competition_id}/disciplines/${discipline_id}`
  );
}

interface TournamentOverallStandingResponse {
  data: TournamentOverallStandingInterface[];
}

interface TournamentOverallStandingApiResponse {
  data: Array<{
    team_id: number;
    team_name: string;
    game_points: string | number;
    competition_points: string | number;
    total_points: string | number;
  }>;
}

export function getTournamentOverallStandings(
  tournament_id: number | null
): SWRResponse<TournamentOverallStandingResponse> {
  return useSWR(
    tournament_id == null ? null : `tournaments/${tournament_id}/overall_standings`,
    async (url: string) => {
      const response = await createAxios().get<TournamentOverallStandingApiResponse>(url);
      return {
        data: response.data.data.map((standing) => ({
          ...standing,
          game_points: Number(standing.game_points) || 0,
          competition_points: Number(standing.competition_points) || 0,
          total_points: Number(standing.total_points) || 0,
        })),
      };
    },
    { refreshInterval: 5_000 }
  );
}
