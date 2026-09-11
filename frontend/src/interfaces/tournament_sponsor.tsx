export type TournamentSponsorPosition = 'LEFT' | 'RIGHT';

export interface TournamentSponsor {
  id: number;
  tournament_id: number;
  name: string;
  logo_path: string;
  url?: string | null;
  position: TournamentSponsorPosition;
  sort_order: number;
}
