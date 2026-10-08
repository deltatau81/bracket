import { Alert, Badge, Button, Group, Stack, Text, Title } from '@mantine/core';
import { isAxiosError } from 'axios';
import { useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useSWRConfig } from 'swr';
import { Match, MatchPeriod, MatchPhaseAction, Tournament } from '@openapi';
import { transitionMatchPhase } from '@services/match';

export function hockeyPeriods(mode: Tournament['hockey_mode']): MatchPeriod[] {
  return mode === 'COMPETITION'
    ? ['HALF1', 'HALF2', 'SHOOTOUT']
    : mode === 'GAME_SHOOTOUT'
      ? ['GAME', 'SHOOTOUT']
      : [];
}
// Select request actions from the API contract; never calculate a next match state.
export function phaseActions(match: Match, mode: Tournament['hockey_mode']): MatchPhaseAction[] {
  const periods = hockeyPeriods(mode);
  if (!periods.length) return [];
  if (match.status === 'PLANNED')
    return match.active_period === null && match.phase_state === null ? ['START_MATCH'] : [];
  if (match.active_period === null || !periods.includes(match.active_period)) return [];
  if (match.status === 'FINISHED') return match.phase_state === 'BREAK' ? ['REOPEN_MATCH'] : [];
  if (match.status !== 'RUNNING') return [];
  if (match.phase_state === 'ACTIVE')
    return match.active_period === 'SHOOTOUT' ? ['FINISH_MATCH'] : ['END_PERIOD'];
  if (match.phase_state === 'BREAK')
    return match.active_period === 'SHOOTOUT'
      ? ['RESUME_PERIOD']
      : ['START_NEXT_PERIOD', 'RESUME_PERIOD'];
  return [];
}
export default function HockeyPhaseControl({
  tournament,
  match,
  dirty,
  busy,
  refreshMatch,
  onMatchUpdated,
  onSavingChange,
  hasUnsavedChanges,
}: {
  tournament: Tournament;
  match: Match;
  dirty: boolean;
  busy: boolean;
  refreshMatch: () => Promise<Match | undefined>;
  onMatchUpdated: (match: Match) => void;
  onSavingChange: (saving: boolean) => void;
  hasUnsavedChanges?: () => boolean;
}) {
  const { t } = useTranslation();
  const { mutate } = useSWRConfig();
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const pendingRef = useRef(false);
  const periods = hockeyPeriods(tournament.hockey_mode);
  if (!periods.length) return null;
  const actions = phaseActions(match, tournament.hockey_mode);
  async function act(action: MatchPhaseAction) {
    if (
      dirty ||
      hasUnsavedChanges?.() ||
      busy ||
      pendingRef.current ||
      tournament.status === 'ARCHIVED' ||
      !actions.includes(action)
    )
      return;
    if (
      (action === 'FINISH_MATCH' || action === 'REOPEN_MATCH') &&
      !window.confirm(t('hockey_phase_confirm'))
    )
      return;
    pendingRef.current = true;
    setPending(true);
    onSavingChange(true);
    setError(null);
    let applied = false;
    try {
      const response = await transitionMatchPhase(tournament.id, match.id, action);
      const updated = response.data?.data;
      if (
        !updated ||
        updated.id !== match.id ||
        !phaseActions(updated, tournament.hockey_mode).length
      )
        throw new Error('Invalid phase response');
      applied = true;
      onMatchUpdated(updated);
      const fresh = await refreshMatch();
      if (fresh) onMatchUpdated(fresh);
      await mutate(`tournaments/${tournament.id}/rankings`);
      await mutate(`tournaments/${tournament.id}/overall_standings`);
    } catch (failure: unknown) {
      const status = isAxiosError(failure) ? failure.response?.status : undefined;
      setError(
        t(
          applied
            ? 'hockey_phase_refresh_error'
            : status === 409
              ? 'hockey_phase_conflict'
              : status === 401 || status === 403
                ? 'hockey_phase_forbidden'
                : 'hockey_phase_error',
        ),
      );
      if (status === 409) {
        try {
          const fresh = await refreshMatch();
          if (fresh) onMatchUpdated(fresh);
        } catch {
          /* Preserve visible conflict feedback. */
        }
      }
    } finally {
      pendingRef.current = false;
      setPending(false);
      onSavingChange(false);
    }
  }
  const currentIndex = match.active_period === null ? -1 : periods.indexOf(match.active_period);
  const state =
    match.status === 'PLANNED' && currentIndex === -1 && match.phase_state === null
      ? 'planned'
      : match.status === 'FINISHED'
        ? 'finished'
        : match.phase_state === 'ACTIVE'
          ? 'active'
          : match.phase_state === 'BREAK'
            ? 'break'
            : 'unknown';
  return (
    <Stack gap="sm">
      <Title order={4}>{t('hockey_phase_title')}</Title>
      <Text>{t(`hockey_phase_${state}`)}</Text>
      <Group gap="xs">
        {periods.map((period, index) => (
          <Badge key={period} variant={index === currentIndex ? 'filled' : 'outline'}>
            {t(`hockey_phase_period_${period}`)}
            {' - '}
            {t(
              index === currentIndex
                ? `hockey_phase_${state}`
                : state === 'planned'
                  ? 'hockey_phase_pending'
                  : index < currentIndex
                    ? 'hockey_phase_previous'
                    : 'hockey_phase_unknown',
            )}
          </Badge>
        ))}
      </Group>
      <Text size="xs" c="dimmed">
        {t('hockey_phase_history_note')}
      </Text>
      {dirty && <Alert color="yellow">{t('hockey_phase_dirty')}</Alert>}
      {error && <Alert color="red">{error}</Alert>}
      {!actions.length && <Text c="dimmed">{t('hockey_phase_unavailable')}</Text>}
      {tournament.status !== 'ARCHIVED' && (
        <Group>
          {actions.map((action) => (
            <Button
              key={action}
              loading={pending}
              disabled={busy || dirty || pending}
              onClick={() => act(action)}
            >
              {t(`hockey_phase_action_${action}`)}
            </Button>
          ))}
        </Group>
      )}
    </Stack>
  );
}
