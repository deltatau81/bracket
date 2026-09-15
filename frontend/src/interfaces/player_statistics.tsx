import { PlayerPosition } from './player';

export interface PlayerStatistics {
  player_id: number;
  player_name: string;
  team_id: number | null;
  team_name: string | null;
  jersey_number: number | null;
  position: PlayerPosition | null;
  goals: number;
  assists: number;
  points: number;
  penalty_minutes: number;
}
