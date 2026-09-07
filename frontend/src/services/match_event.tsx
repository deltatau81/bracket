import useSWR, { SWRResponse } from 'swr';

import { MatchPeriod } from '../interfaces/match';
import {
  MatchEvent,
  MatchEventBody,
  MatchEventCreateBody,
  MatchEventsResponse,
  PenaltyCatalogResponse,
} from '../interfaces/match_event';
import { createAxios, handleRequestError } from './adapter';

const eventUrl = (tournamentId: number, matchId: number) =>
  `tournaments/${tournamentId}/matches/${matchId}/events`;

export function getPenaltyCatalog(
  tournamentId: number,
  matchId: number
): SWRResponse<PenaltyCatalogResponse> {
  const url = 'tournaments/' + tournamentId + '/matches/' + matchId + '/penalties/catalog';
  return useSWR(url, async (catalogUrl: string) => {
    const response = await createAxios().get<PenaltyCatalogResponse>(catalogUrl);
    return response.data;
  });
}

export function getTournamentMatchEvents(
  tournamentId: number | null
): SWRResponse<MatchEventsResponse> {
  const url = tournamentId == null ? null : 'tournaments/' + tournamentId + '/events';
  return useSWR(
    url,
    async (eventFeedUrl: string) => {
      const response = await createAxios().get<MatchEventsResponse>(eventFeedUrl);
      return response.data;
    },
    { refreshInterval: 5_000 }
  );
}

export function getMatchEvents(
  tournamentId: number,
  matchId: number
): SWRResponse<MatchEventsResponse> {
  return useSWR(eventUrl(tournamentId, matchId), async (url: string) => {
    const response = await createAxios().get<MatchEventsResponse>(url);
    return response.data;
  });
}

export async function createMatchEvent(
  tournamentId: number,
  matchId: number,
  activePeriod: MatchPeriod,
  event: MatchEventCreateBody
) {
  return createAxios()
    .post<{ data: MatchEvent }>(eventUrl(tournamentId, matchId), {
      ...event,
      period: activePeriod,
    })
    .catch((response: any) => handleRequestError(response));
}

export async function updateMatchEvent(
  tournamentId: number,
  matchId: number,
  eventId: number,
  event: MatchEventBody
) {
  return createAxios()
    .put<{ data: MatchEvent }>(`${eventUrl(tournamentId, matchId)}/${eventId}`, event)
    .catch((response: any) => handleRequestError(response));
}

export async function deleteMatchEvent(
  tournamentId: number,
  matchId: number,
  eventId: number
) {
  return createAxios()
    .delete(`${eventUrl(tournamentId, matchId)}/${eventId}`)
    .catch((response: any) => handleRequestError(response));
}
