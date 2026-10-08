import useSWR from 'swr';
import {
  MatchEventBody,
  MatchEventsResponse,
  SingleMatchEventResponse,
  SuccessResponse,
} from '@openapi';
import { createAxios, handleRequestError } from './adapter';

export function matchEventsKey(tournamentId: number, matchId: number) {
  return `tournaments/${tournamentId}/matches/${matchId}/events`;
}
export function getMatchEvents(tournamentId: number, matchId: number, enabled = true) {
  return useSWR<MatchEventsResponse>(
    enabled ? matchEventsKey(tournamentId, matchId) : null,
    (url: string) =>
      createAxios()
        .get<MatchEventsResponse>(url)
        .then((response) => response.data),
    { keepPreviousData: false },
  );
}
function reportError(error: Parameters<typeof handleRequestError>[0]): never {
  handleRequestError(error);
  throw error;
}
export function createGoalEvent(tournamentId: number, matchId: number, body: MatchEventBody) {
  return createAxios()
    .post<SingleMatchEventResponse>(matchEventsKey(tournamentId, matchId), body)
    .catch(reportError);
}
export function updateGoalEvent(
  tournamentId: number,
  matchId: number,
  eventId: number,
  body: MatchEventBody,
) {
  return createAxios()
    .put<SingleMatchEventResponse>(`${matchEventsKey(tournamentId, matchId)}/${eventId}`, body)
    .catch(reportError);
}
export function deleteGoalEvent(tournamentId: number, matchId: number, eventId: number) {
  return createAxios()
    .delete<SuccessResponse>(`${matchEventsKey(tournamentId, matchId)}/${eventId}`)
    .catch(reportError);
}
