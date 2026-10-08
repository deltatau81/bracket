import { showNotification } from '@mantine/notifications';

import {
  MatchCreateBodyFrontend,
  MatchRescheduleBody,
  MatchUpdateBody,
  MatchPhaseAction,
  SingleMatchResponse,
} from '@openapi';
import { createAxios, handleRequestError } from './adapter';

type MatchUpdateRequest = Partial<MatchUpdateBody> & Pick<MatchUpdateBody, 'round_id'>;

export async function createMatch(tournament_id: number, match: MatchCreateBodyFrontend) {
  return createAxios()
    .post(`tournaments/${tournament_id}/matches`, match)
    .catch((response: any) => handleRequestError(response));
}

export async function deleteMatch(tournament_id: number, match_id: number) {
  return createAxios()
    .delete(`tournaments/${tournament_id}/matches/${match_id}`)
    .catch((response: any) => handleRequestError(response));
}

export async function updateMatch(
  tournament_id: number,
  match_id: number,
  match: MatchUpdateRequest,
  propagateError = false,
) {
  return createAxios()
    .put(`tournaments/${tournament_id}/matches/${match_id}`, match)
    .catch((error: Parameters<typeof handleRequestError>[0]) => {
      handleRequestError(error);
      if (propagateError) throw error;
    });
}

export async function rescheduleMatch(
  tournament_id: number,
  match_id: number,
  match: MatchRescheduleBody,
) {
  return createAxios()
    .post(`tournaments/${tournament_id}/matches/${match_id}/reschedule`, match)
    .catch((response: any) => handleRequestError(response))
    .then((response: any) => {
      if (response != null && response.status === 200) {
        showNotification({
          color: 'green',
          title: 'Successfully rescheduled match',
          message: '',
        });
      }
    });
}

export async function scheduleMatches(tournament_id: number) {
  return createAxios()
    .post(`tournaments/${tournament_id}/schedule_matches`)
    .catch((response: any) => handleRequestError(response));
}

export async function transitionMatchPhase(
  tournamentId: number,
  matchId: number,
  action: MatchPhaseAction,
) {
  return createAxios()
    .post<SingleMatchResponse>(`tournaments/${tournamentId}/matches/${matchId}/phase`, { action })
    .catch((error: Parameters<typeof handleRequestError>[0]) => {
      handleRequestError(error);
      throw error;
    });
}
