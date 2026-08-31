export type CompetitionMetricType = 'TIME' | 'COUNT' | 'RATIO' | 'MANUAL';

export interface CompetitionDisciplineBodyInterface {
  name: string;
  description: string | null;
  metric_type: CompetitionMetricType;
  sort_order: number;
}

export interface CompetitionDisciplineInterface {
  id: number;
  name: string;
  description: string | null;
  metric_type: CompetitionMetricType;
  sort_order: number;
  competition_id: number;
  created: string;
}

export interface CompetitionInterface {
  id: number;
  name: string;
  description: string | null;
  start_time: string;
  duration_minutes: number;
  court_id: number | null;
}

export interface CompetitionResultBodyInterface {
  team_id: number;
  place: number | null;
  time_ms: number | null;
  attempts: number | null;
  successes: number | null;
  notes: string | null;
}

export interface CompetitionResultInterface extends CompetitionResultBodyInterface {
  id: number;
  discipline_id: number;
  updated: string;
}

export interface CompetitionScoringBodyInterface {
  place: number;
  points: number;
}

export interface CompetitionScoringInterface {
  id: number;
  competition_id: number;
  place: number;
  points: number | string;
}

export interface CompetitionRankedResultInterface {
  result: CompetitionResultInterface;
  place: number;
  points: number;
  tied: boolean;
}
