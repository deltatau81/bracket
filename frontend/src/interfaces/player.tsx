export interface Player {
  id: number;
  name: string;
  first_name: string | null;
  last_name: string | null;
  active: boolean;
  created: string;
  tournament_id: number;
  elo_score: number;
  swiss_score: number;
  wins: number;
  draws: number;
  losses: number;
}

export type PlayerPosition = 'GK' | 'D' | 'F';

export interface TeamPlayer extends Player {
  number: number | null;
  position: PlayerPosition | null;
}
