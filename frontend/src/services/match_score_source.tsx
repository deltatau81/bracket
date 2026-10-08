import {
  ScoreSourceConfirmBody,
  ScoreSourcePreviewBody,
  confirmMatchScoreSourceTournamentsTournamentIdMatchesMatchIdScoreSourceConfirmPost,
  previewMatchScoreSourceTournamentsTournamentIdMatchesMatchIdScoreSourcePreviewPost,
} from '@openapi';
import { createClient } from '@openapi/client';
import { createAxios, getBaseApiUrl, handleRequestError } from './adapter';

function scoreSourceClient() {
  // The generated SDK embeds baseURL in its URL; preserve the deployment prefix.
  return createClient({ axios: createAxios(), baseURL: getBaseApiUrl() });
}
function reportError(error: Parameters<typeof handleRequestError>[0]): never {
  handleRequestError(error);
  throw error;
}
export function previewScoreSource(
  tournamentId: number,
  matchId: number,
  body: ScoreSourcePreviewBody,
) {
  return previewMatchScoreSourceTournamentsTournamentIdMatchesMatchIdScoreSourcePreviewPost({
    client: scoreSourceClient(),
    path: { tournament_id: tournamentId, match_id: matchId },
    body,
    throwOnError: true,
  }).catch(reportError);
}
export function confirmScoreSource(
  tournamentId: number,
  matchId: number,
  body: ScoreSourceConfirmBody,
) {
  return confirmMatchScoreSourceTournamentsTournamentIdMatchesMatchIdScoreSourceConfirmPost({
    client: scoreSourceClient(),
    path: { tournament_id: tournamentId, match_id: matchId },
    body,
    throwOnError: true,
  }).catch(reportError);
}
