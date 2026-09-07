import { MatchPeriod } from './match';

export type MatchEventType = 'GOAL' | 'PENALTY';

export type PenaltyType =
  | 'MINOR'
  | 'DOUBLE_MINOR'
  | 'BENCH_MINOR'
  | 'MAJOR'
  | 'MISCONDUCT'
  | 'GAME_MISCONDUCT'
  | 'MAJOR_GAME_MISCONDUCT'
  | 'MINOR_MISCONDUCT'
  | 'MINOR_GAME_MISCONDUCT'
  | 'PENALTY_SHOT'
  | 'AWARDED_GOAL'
  | 'CUSTOM';

export interface PenaltyTypeDefinition {
  type: PenaltyType;
  label: string;
  minutes: number | null;
  game_misconduct: boolean;
}

export interface PenaltyDefinition {
  code: string;
  rule: string | null;
  label: string;
  category: string;
  default_penalty_type: PenaltyType;
  allowed_penalty_types: PenaltyType[];
}

export interface PenaltyCatalog {
  ruleset: 'DEB' | 'IIHF';
  season: string;
  age_category: string;
  catalog_source: 'IIHF_2026_27' | 'IIHF_BASE';
  penalty_types: PenaltyTypeDefinition[];
  penalties: PenaltyDefinition[];
}

export interface PenaltyCatalogResponse {
  data: PenaltyCatalog;
}

export interface MatchEventBody {
  team_id: number;
  event_type: MatchEventType;
  period: MatchPeriod;
  game_time_seconds: number;
  player_id: number | null;
  player_number?: number | null;
  player_name?: string | null;
  assist1_player_id?: number | null;
  assist1_number?: number | null;
  assist1_name?: string | null;
  assist2_player_id?: number | null;
  assist2_number?: number | null;
  assist2_name?: string | null;
  penalty_code?: string | null;
  penalty_rule?: string | null;
  penalty_type?: PenaltyType | string | null;
  penalty_minutes?: number | null;
  infraction?: string | null;
  game_misconduct?: boolean | null;
  sort_order?: number;
}

export interface MatchEventCreateBody {
  team_id: number;
  event_type: MatchEventType;
  game_time_seconds: number;
  player_id: number | null;
  player_number?: number | null;
  assist1_player_id?: number | null;
  assist1_number?: number | null;
  assist2_player_id?: number | null;
  assist2_number?: number | null;
  penalty_code?: string | null;
  penalty_type?: PenaltyType | null;
  penalty_minutes?: number | null;
  infraction?: string | null;
}

export interface MatchEvent extends MatchEventBody {
  id: number;
  match_id: number;
  created: string;
}

export interface MatchEventsResponse {
  data: MatchEvent[];
}
