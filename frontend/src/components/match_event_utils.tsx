import { MatchPeriod } from '../interfaces/match';
import { MatchEvent } from '../interfaces/match_event';

export const MATCH_PERIOD_LABELS: Record<MatchPeriod, string> = {
  GAME: 'Game',
  HALF1: '1. Halbzeit',
  HALF2: '2. Halbzeit',
  SHOOTOUT: 'Penalty',
  PERIOD1: '1. Drittel',
  PERIOD2: '2. Drittel',
  PERIOD3: '3. Drittel',
  OVERTIME: 'Verlängerung',
};

export function formatGameTime(seconds: number): string {
  const minutes = Math.floor(seconds / 60).toString().padStart(2, '0');
  const remainingSeconds = (seconds % 60).toString().padStart(2, '0');
  return minutes + ':' + remainingSeconds;
}

function minutesLabel(minutes: number | null | undefined): string | null {
  return minutes == null ? null : minutes + ' Minuten';
}

export function formatPenaltySanction(event: MatchEvent): string | null {
  switch (event.penalty_type) {
    case 'MINOR':
      return '2 Minuten';
    case 'DOUBLE_MINOR':
      return '4 Minuten';
    case 'BENCH_MINOR':
      return '2 Minuten Bankstrafe';
    case 'MAJOR':
      return '5 Minuten';
    case 'MISCONDUCT':
      return '10 Minuten Disziplinarstrafe';
    case 'GAME_MISCONDUCT':
      return 'Spieldauerdisziplinarstrafe';
    case 'MAJOR_GAME_MISCONDUCT':
      return '5 Minuten + Spieldauer';
    case 'MINOR_MISCONDUCT':
      return '2 Minuten + 10 Minuten Disziplinarstrafe';
    case 'MINOR_GAME_MISCONDUCT':
      return '2 Minuten + Spieldauer';
    case 'PENALTY_SHOT':
      return 'Strafschuss';
    case 'AWARDED_GOAL':
      return 'Zugesprochenes Tor';
    case 'CUSTOM': {
      const duration = minutesLabel(event.penalty_minutes);
      return duration == null ? 'Benutzerdefiniert' : 'Benutzerdefiniert (' + duration + ')';
    }
    default:
      return minutesLabel(event.penalty_minutes) ?? event.penalty_type ?? null;
  }
}

export function formatPenaltyDetails(event: MatchEvent): string | null {
  const sanction = formatPenaltySanction(event);
  if (event.infraction == null || event.infraction === '') return sanction;
  return sanction == null ? event.infraction : event.infraction + ' — ' + sanction;
}