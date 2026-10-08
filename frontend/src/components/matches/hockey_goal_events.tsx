import {
  Alert,
  Button,
  Group,
  Loader,
  NumberInput,
  Paper,
  Select,
  Stack,
  Text,
  Title,
} from '@mantine/core';
import { isAxiosError } from 'axios';
import { useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useSWRConfig } from 'swr';
import {
  MatchEvent,
  MatchEventBody,
  MatchEventPeriod,
  MatchWithDetails,
  Tournament,
} from '@openapi';
import {
  createGoalEvent,
  deleteGoalEvent,
  getMatchEvents,
  updateGoalEvent,
} from '@services/match_event';
import { hockeyPeriods } from './hockey_phase_control';

export type EventTeam = { id: number; name: string };
type Draft = {
  event: MatchEvent | null;
  team: string | null;
  period: MatchEventPeriod;
  time: string | number;
};
export function canCreateGoal(match: MatchWithDetails, mode: Tournament['hockey_mode']) {
  return (
    match.status === 'RUNNING' &&
    match.phase_state === 'ACTIVE' &&
    match.active_period !== null &&
    hockeyPeriods(mode).includes(match.active_period)
  );
}
export function goalBody(
  team: number,
  period: MatchEventPeriod,
  time: number | null,
  event: MatchEvent | null,
): MatchEventBody {
  const sameTeam = event?.team_id === team;
  return {
    team_id: team,
    event_type: 'GOAL',
    period,
    game_time_seconds: time,
    player_id: sameTeam ? event.player_id : null,
    player_name: sameTeam ? event.player_name : null,
    player_number: sameTeam ? event.player_number : null,
    assist1_player_id: sameTeam ? event.assist1_player_id : null,
    assist1_name: sameTeam ? event.assist1_name : null,
    assist1_number: sameTeam ? event.assist1_number : null,
    assist2_player_id: sameTeam ? event.assist2_player_id : null,
    assist2_name: sameTeam ? event.assist2_name : null,
    assist2_number: sameTeam ? event.assist2_number : null,
    penalty_code: null,
    penalty_rule: null,
    penalty_type: null,
    penalty_minutes: null,
    infraction: null,
    game_misconduct: null,
    sort_order: event?.sort_order ?? 0,
  };
}

export default function HockeyGoalEvents({
  tournament,
  match,
  teams,
  busy,
  hasUnsavedScores,
  hasPendingRequest,
  refreshMatch,
  onMatchUpdated,
  onSavingChange,
  onDirtyChange,
}: {
  tournament: Tournament;
  match: MatchWithDetails;
  teams: EventTeam[];
  busy: boolean;
  hasUnsavedScores: () => boolean;
  hasPendingRequest?: () => boolean;
  refreshMatch: () => Promise<MatchWithDetails | undefined>;
  onMatchUpdated: (match: MatchWithDetails) => void;
  onSavingChange: (saving: boolean) => void;
  onDirtyChange: (dirty: boolean) => void;
}) {
  const { t } = useTranslation();
  const { mutate } = useSWRConfig();
  const hockey = tournament.hockey_mode !== 'STANDARD';
  const events = getMatchEvents(tournament.id, match.id, hockey);
  const [draft, setDraft] = useState<Draft | null>(null);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [uncertain, setUncertain] = useState(false);
  const requestRef = useRef(false);
  const uncertainRef = useRef(false);
  if (!hockey) return null;
  const periods = hockeyPeriods(tournament.hockey_mode);
  const archived = tournament.status === 'ARCHIVED';
  const rows = (events.data?.data ?? []).filter(
    (event) => event.match_id === match.id && event.event_type === 'GOAL',
  );
  const writable =
    !archived && !busy && !pending && !hasPendingRequest?.() && !hasUnsavedScores() && !uncertain;
  function begin(event: MatchEvent | null) {
    if (
      !writable ||
      hasUnsavedScores() ||
      hasPendingRequest?.() ||
      events.error ||
      !events.data ||
      (!event && !canCreateGoal(match, tournament.hockey_mode))
    )
      return;
    const period = event?.period ?? match.active_period;
    if (!period || !periods.includes(period)) return;
    setDraft({
      event,
      team: event ? String(event.team_id) : null,
      period,
      time: event?.game_time_seconds ?? '',
    });
    onDirtyChange(true);
    setError(null);
  }
  function cancel() {
    if (requestRef.current) return;
    setDraft(null);
    onDirtyChange(false);
  }
  async function reload() {
    await events.mutate();
    const fresh = await refreshMatch();
    if (!fresh || fresh.id !== match.id) throw new Error('Match refresh missing');
    onMatchUpdated(fresh);
    await mutate(`tournaments/${tournament.id}/rankings`);
    await mutate(`tournaments/${tournament.id}/next_stage_rankings`);
    await mutate(`tournaments/${tournament.id}/overall_standings`);
  }
  async function submit(remove: MatchEvent | null = null) {
    if (
      requestRef.current ||
      uncertainRef.current ||
      hasUnsavedScores() ||
      hasPendingRequest?.() ||
      !writable ||
      (remove && draft)
    )
      return;
    const target = remove ?? draft?.event ?? null;
    if (target && (target.match_id !== match.id || target.event_type !== 'GOAL')) return;
    let body: MatchEventBody | undefined;
    if (!remove) {
      if (!draft || (!draft.event && !canCreateGoal(match, tournament.hockey_mode))) return;
      if (!draft.event && draft.period !== match.active_period) {
        setError(t('hockey_events_phase_changed'));
        return;
      }
      const team = Number(draft.team);
      const time = draft.time === '' ? null : draft.time;
      if (
        !teams.some((candidate) => candidate.id === team) ||
        !periods.includes(draft.period) ||
        (time !== null && (typeof time !== 'number' || !Number.isSafeInteger(time) || time < 0))
      ) {
        setError(t('hockey_events_invalid'));
        return;
      }
      if (
        draft.event &&
        draft.event.team_id !== team &&
        !window.confirm(t('hockey_events_team_change'))
      )
        return;
      body = goalBody(team, draft.period, time, draft.event);
    } else if (
      !window.confirm(
        t('hockey_events_delete_confirm', {
          team:
            teams.find((team) => team.id === remove.team_id)?.name ??
            t('hockey_events_unknown_team'),
          period: t(`hockey_phase_period_${remove.period}`),
          time:
            remove.game_time_seconds === null
              ? t('hockey_events_no_time')
              : remove.game_time_seconds,
          id: remove.id,
        }),
      )
    )
      return;
    requestRef.current = true;
    setPending(true);
    onSavingChange(true);
    setError(null);
    let applied = false;
    try {
      if (remove) {
        const response = await deleteGoalEvent(tournament.id, match.id, remove.id);
        if (response.data?.success !== true) throw new Error('Invalid delete response');
      } else if (body) {
        const response = target
          ? await updateGoalEvent(tournament.id, match.id, target.id, body)
          : await createGoalEvent(tournament.id, match.id, body);
        const result = response.data?.data;
        if (
          !result ||
          !Number.isSafeInteger(result.id) ||
          result.id <= 0 ||
          result.match_id !== match.id ||
          result.event_type !== 'GOAL' ||
          result.team_id !== body.team_id ||
          result.period !== body.period ||
          (target && result.id !== target.id)
        )
          throw new Error('Invalid event response');
      }
      applied = true;
      cancelAfterSave();
      await reload();
    } catch (failure: unknown) {
      const status = isAxiosError(failure) ? failure.response?.status : undefined;
      const ambiguous = !applied && (status === undefined || status >= 500);
      if (ambiguous || applied) {
        uncertainRef.current = true;
        setUncertain(true);
      }
      setError(
        t(
          applied
            ? 'hockey_events_refresh_error'
            : ambiguous
              ? 'hockey_events_uncertain'
              : status === 401 || status === 403
                ? 'hockey_events_forbidden'
                : status === 409
                  ? 'hockey_events_conflict'
                  : 'hockey_events_error',
        ),
      );
    } finally {
      requestRef.current = false;
      setPending(false);
      onSavingChange(false);
    }
  }
  function cancelAfterSave() {
    setDraft(null);
    onDirtyChange(false);
  }
  async function review() {
    if (requestRef.current || busy || hasPendingRequest?.() || hasUnsavedScores()) return;
    if (draft && !window.confirm(t('hockey_events_review_confirm'))) return;
    requestRef.current = true;
    setPending(true);
    onSavingChange(true);
    try {
      await reload();
      // Never replay an ambiguous mutation; the user must review the server list first.
      uncertainRef.current = false;
      setUncertain(false);
      cancelAfterSave();
      setError(null);
    } catch {
      setError(t('hockey_events_refresh_error'));
    } finally {
      requestRef.current = false;
      setPending(false);
      onSavingChange(false);
    }
  }
  return (
    <Stack gap="sm">
      <Title order={4}>{t('hockey_events_title')}</Title>
      <Text size="sm" c="dimmed">
        {t(
          match.score_entry_source === 'MANUAL'
            ? 'hockey_events_manual'
            : match.score_entry_source === 'EVENTS'
              ? 'hockey_events_events'
              : 'hockey_events_legacy',
        )}
      </Text>
      {hasUnsavedScores() && <Alert color="yellow">{t('hockey_phase_dirty')}</Alert>}
      {events.error && <Alert color="red">{t('hockey_events_load_error')}</Alert>}
      {error && <Alert color="red">{error}</Alert>}
      {(uncertain || error || events.error) && (
        <Button variant="outline" disabled={pending || busy || hasUnsavedScores()} onClick={review}>
          {t('hockey_events_reload')}
        </Button>
      )}
      {!events.data && !events.error && <Loader />}
      {events.data && !rows.length && <Text c="dimmed">{t('hockey_events_empty')}</Text>}
      {rows.map((event) => (
        <Paper key={event.id} withBorder p="sm">
          <Stack gap="xs">
            <Text fw={600}>
              {t('hockey_events_goal')} -{' '}
              {teams.find((team) => team.id === event.team_id)?.name ??
                t('hockey_events_unknown_team')}
            </Text>
            <Text size="sm">
              {t(`hockey_phase_period_${event.period}`)}
              {event.game_time_seconds !== null
                ? ` - ${event.game_time_seconds} ${t('hockey_events_seconds')}`
                : ''}
            </Text>
            {(event.player_name || event.player_number !== null) && (
              <Text size="sm">
                {event.player_name}
                {event.player_number !== null ? ` #${event.player_number}` : ''}
              </Text>
            )}
            {!archived && (
              <Group>
                <Button
                  variant="light"
                  disabled={
                    !writable || !!draft || !!events.error || !periods.includes(event.period)
                  }
                  onClick={() => begin(event)}
                >
                  {t('hockey_events_edit')}
                </Button>
                <Button
                  color="red"
                  variant="light"
                  disabled={!writable || !!draft || !!events.error}
                  onClick={() => submit(event)}
                >
                  {t('hockey_events_delete')}
                </Button>
              </Group>
            )}
          </Stack>
        </Paper>
      ))}
      {!archived && !draft && (
        <Button
          disabled={
            !writable ||
            !events.data ||
            !!events.error ||
            !teams.length ||
            !canCreateGoal(match, tournament.hockey_mode)
          }
          onClick={() => begin(null)}
        >
          {t('hockey_events_add')}
        </Button>
      )}
      {draft && (
        <Paper withBorder p="sm">
          <Stack gap="sm">
            <Title order={5}>{t(draft.event ? 'hockey_events_edit' : 'hockey_events_add')}</Title>
            <Select
              label={t('hockey_events_team')}
              data={teams.map((team) => ({ value: String(team.id), label: team.name }))}
              value={draft.team}
              disabled={!writable}
              onChange={(team) => setDraft({ ...draft, team })}
            />
            {draft.event ? (
              <Select
                label={t('hockey_events_period')}
                data={periods.map((period) => ({
                  value: period,
                  label: t(`hockey_phase_period_${period}`),
                }))}
                value={draft.period}
                disabled={!writable}
                onChange={(period) => {
                  const valid = periods.find((candidate) => candidate === period);
                  if (valid) setDraft({ ...draft, period: valid });
                }}
              />
            ) : (
              <Text>
                {t('hockey_events_period')}: {t(`hockey_phase_period_${draft.period}`)}
              </Text>
            )}
            <NumberInput
              label={t('hockey_events_time')}
              min={0}
              allowDecimal={false}
              allowNegative={false}
              value={draft.time}
              disabled={!writable}
              onChange={(time) => setDraft({ ...draft, time })}
            />
            {draft.event?.player_name && <Text size="sm">{draft.event.player_name}</Text>}
            <Group>
              <Button loading={pending} disabled={!writable} onClick={() => submit()}>
                {t('save_button')}
              </Button>
              <Button variant="outline" disabled={pending} onClick={cancel}>
                {t('hockey_events_cancel')}
              </Button>
            </Group>
          </Stack>
        </Paper>
      )}
    </Stack>
  );
}
