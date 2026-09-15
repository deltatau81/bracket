import { TeamPlayer } from './player';

export interface PlayerTeamAssignment {
  player_id: number;
  number: number | null;
  position: TeamPlayer['position'];
}

export interface TeamInterface {
  id: number;
  name: string;
  created: string;
  active: boolean;
  players: TeamPlayer[];
  elo_score: number;
  swiss_score: number;
  wins: number;
  draws: number;
  losses: number;
  logo_path: string;
  participant_club_id: number | null;
}
