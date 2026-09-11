import { TournamentSponsorPosition } from '../interfaces/tournament_sponsor';
import { createAxios } from './adapter';

export interface TournamentSponsorBody {
  name: string;
  logo_path: string;
  url: string | null;
  position: TournamentSponsorPosition;
  sort_order: number;
}

export function createTournamentSponsor(tournamentId: number, body: TournamentSponsorBody) {
  return createAxios().post(`tournaments/${tournamentId}/sponsors`, body);
}

export function updateTournamentSponsor(
  tournamentId: number,
  sponsorId: number,
  body: TournamentSponsorBody
) {
  return createAxios().put(`tournaments/${tournamentId}/sponsors/${sponsorId}`, body);
}

export function deleteTournamentSponsor(tournamentId: number, sponsorId: number) {
  return createAxios().delete(`tournaments/${tournamentId}/sponsors/${sponsorId}`);
}

export function uploadTournamentSponsorLogo(
  tournamentId: number,
  sponsorId: number,
  file: File
) {
  const formData = new FormData();
  formData.append('file', file, file.name);
  return createAxios().post(
    `tournaments/${tournamentId}/sponsors/${sponsorId}/logo`,
    formData
  );
}
