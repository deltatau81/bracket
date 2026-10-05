import { isAxiosError, AxiosResponse } from 'axios';
import {
  CompetitionBody,
  CompetitionDisciplineBody,
  CompetitionResponse,
  CompetitionDisciplineResponse,
} from '@openapi';
import { createAxios, handleRequestError } from './adapter';

async function handleMutation<T>(request: Promise<AxiosResponse<T>>) {
  try {
    return await request;
  } catch (error: unknown) {
    if (isAxiosError(error)) handleRequestError(error);
    throw error;
  }
}
export function createCompetition(tournamentId: number, body: CompetitionBody) {
  return handleMutation(
    createAxios().post<CompetitionResponse>(`tournaments/${tournamentId}/competitions`, body),
  );
}
export function updateCompetition(
  tournamentId: number,
  competitionId: number,
  body: CompetitionBody,
) {
  return handleMutation(
    createAxios().put<CompetitionResponse>(
      `tournaments/${tournamentId}/competitions/${competitionId}`,
      body,
    ),
  );
}
export function deleteCompetition(tournamentId: number, competitionId: number) {
  return handleMutation(
    createAxios().delete(`tournaments/${tournamentId}/competitions/${competitionId}`),
  );
}
export function createCompetitionDiscipline(
  tournamentId: number,
  competitionId: number,
  body: CompetitionDisciplineBody,
) {
  return handleMutation(
    createAxios().post<CompetitionDisciplineResponse>(
      `tournaments/${tournamentId}/competitions/${competitionId}/disciplines`,
      body,
    ),
  );
}
export function updateCompetitionDiscipline(
  tournamentId: number,
  competitionId: number,
  disciplineId: number,
  body: CompetitionDisciplineBody,
) {
  return handleMutation(
    createAxios().put<CompetitionDisciplineResponse>(
      `tournaments/${tournamentId}/competitions/${competitionId}/disciplines/${disciplineId}`,
      body,
    ),
  );
}
export function deleteCompetitionDiscipline(
  tournamentId: number,
  competitionId: number,
  disciplineId: number,
) {
  return handleMutation(
    createAxios().delete(
      `tournaments/${tournamentId}/competitions/${competitionId}/disciplines/${disciplineId}`,
    ),
  );
}
