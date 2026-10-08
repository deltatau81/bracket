import {
  Alert,
  Badge,
  Button,
  Checkbox,
  Group,
  Paper,
  Select,
  Stack,
  Text,
  Title,
} from '@mantine/core';
import { isAxiosError } from 'axios';
import { useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useSWRConfig } from 'swr';
import {
  Match,
  MatchScoreEntrySource,
  MatchWithDetails,
  ScoreSourceConfirmation,
  ScoreSourcePreview,
  SectionScores,
  Tournament,
  UserAccountType,
} from '@openapi';
import { confirmScoreSource, previewScoreSource } from '@services/match_score_source';
import { matchEventsKey } from '@services/match_event';
import { hockeyPeriods } from './hockey_phase_control';

export function canAdministerScoreSource(role: UserAccountType) {
  return role === 'REGULAR' || role === 'ADMIN';
}
function validScores(scores: SectionScores[], tournament: Tournament) {
  const periods = hockeyPeriods(tournament.hockey_mode);
  return (
    Array.isArray(scores) &&
    scores.length === periods.length &&
    scores.every(
      (score, i) =>
        score?.period === periods[i] &&
        Number.isSafeInteger(score.team1_score) &&
        score.team1_score >= 0 &&
        Number.isSafeInteger(score.team2_score) &&
        score.team2_score >= 0,
    )
  );
}
export function validSourcePreview(
  data: ScoreSourcePreview | undefined,
  matchId: number,
  target: MatchScoreEntrySource,
  tournament: Tournament,
): data is ScoreSourcePreview {
  return (
    !!data &&
    data.match_id === matchId &&
    data.target_source === target &&
    (data.current_source === null ||
      data.current_source === 'MANUAL' ||
      data.current_source === 'EVENTS') &&
    typeof data.conflict_token === 'string' &&
    /^[0-9a-f]{64}$/.test(data.conflict_token) &&
    validScores(data.current_scores, tournament) &&
    validScores(data.resulting_scores, tournament) &&
    Array.isArray(data.differences) &&
    data.differences.length === data.current_scores.length &&
    data.differences.every(
      (difference, i) =>
        difference?.period === data.current_scores[i].period &&
        Number.isSafeInteger(difference.team1_difference) &&
        Number.isSafeInteger(difference.team2_difference),
    ) &&
    Number.isSafeInteger(data.relevant_goal_count) &&
    data.relevant_goal_count >= 0 &&
    typeof data.scores_changed === 'boolean' &&
    typeof data.rankings_may_change === 'boolean'
  );
}
function validConfirmation(
  data: ScoreSourceConfirmation | undefined,
  matchId: number,
  target: MatchScoreEntrySource,
  tournament: Tournament,
): data is ScoreSourceConfirmation {
  return (
    !!data &&
    data.match?.id === matchId &&
    data.active_source === target &&
    data.match.score_entry_source === target &&
    validScores(data.current_scores, tournament)
  );
}
export default function HockeyScoreSourceControl({
  tournament,
  match,
  role,
  teamNames,
  busy,
  hasBlockedChanges,
  refreshMatch,
  onMatchUpdated,
  onSavingChange,
  onDirtyChange,
}: {
  tournament: Tournament;
  match: MatchWithDetails;
  role: UserAccountType;
  teamNames: [string, string];
  busy: boolean;
  hasBlockedChanges: () => boolean;
  refreshMatch: () => Promise<MatchWithDetails | undefined>;
  onMatchUpdated: (match: Match) => void;
  onSavingChange: (saving: boolean) => void;
  onDirtyChange: (dirty: boolean) => void;
}) {
  const { t } = useTranslation();
  const { mutate } = useSWRConfig();
  const [target, setTarget] = useState<MatchScoreEntrySource | null>(null);
  const [preview, setPreview] = useState<ScoreSourcePreview | null>(null);
  const [approved, setApproved] = useState(false);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [needsReview, setNeedsReview] = useState(false);
  const [denied, setDenied] = useState(false);
  const pendingRef = useRef(false);
  const previewRef = useRef<ScoreSourcePreview | null>(null);
  const targetRef = useRef<MatchScoreEntrySource | null>(null);
  const approvedRef = useRef(false);
  const reviewRef = useRef(false);
  const deniedRef = useRef(false);
  const previousMatch = useRef(match);
  useEffect(() => {
    if (previousMatch.current !== match && !pendingRef.current && previewRef.current) {
      clearPreview();
      setError(t('hockey_source_conflict'));
    }
    previousMatch.current = match;
  }, [match]);
  if (tournament.hockey_mode === 'STANDARD') return null;
  const administrative = canAdministerScoreSource(role);
  const archived = tournament.status === 'ARCHIVED';
  const locked = busy || pending || hasBlockedChanges();
  const label = (source: MatchScoreEntrySource | null) => t(`hockey_source_${source ?? 'legacy'}`);
  function clearPreview() {
    previewRef.current = null;
    setPreview(null);
    approvedRef.current = false;
    setApproved(false);
  }
  function allowed() {
    return (
      administrative &&
      !archived &&
      !pendingRef.current &&
      !busy &&
      !hasBlockedChanges() &&
      !deniedRef.current
    );
  }
  function choose(value: string | null) {
    if (!allowed() || reviewRef.current) return;
    const source = value === 'MANUAL' || value === 'EVENTS' ? value : null;
    targetRef.current = source;
    setTarget(source);
    clearPreview();
    setError(null);
    onDirtyChange(source !== null);
  }
  function cancel() {
    if (pendingRef.current || reviewRef.current) return;
    cancelValues();
  }
  async function reload() {
    const fresh = await refreshMatch();
    if (
      !fresh ||
      fresh.id !== match.id ||
      ![null, 'MANUAL', 'EVENTS'].includes(fresh.score_entry_source)
    )
      throw new Error('Invalid match refresh');
    onMatchUpdated(fresh);
    await mutate(matchEventsKey(tournament.id, match.id));
    await mutate(`tournaments/${tournament.id}/rankings`);
    await mutate(`tournaments/${tournament.id}/next_stage_rankings`);
    await mutate(`tournaments/${tournament.id}/overall_standings`);
  }
  async function act(confirm: boolean) {
    if (!allowed() || reviewRef.current) return;
    const selected = targetRef.current;
    const snapshot = previewRef.current;
    if (!selected || selected === match.score_entry_source) return;
    if (confirm && (!snapshot || !approvedRef.current || snapshot.target_source !== selected))
      return;
    pendingRef.current = true;
    setPending(true);
    onSavingChange(true);
    setError(null);
    let applied = false;
    try {
      if (!confirm) {
        clearPreview();
        const response = await previewScoreSource(tournament.id, match.id, {
          target_source: selected,
        });
        const result = response.data?.data;
        if (!validSourcePreview(result, match.id, selected, tournament))
          throw new Error('Invalid preview');
        previewRef.current = result;
        setPreview(result);
      } else if (snapshot) {
        const response = await confirmScoreSource(tournament.id, match.id, {
          target_source: selected,
          conflict_token: snapshot.conflict_token,
        });
        const result = response.data?.data;
        if (!validConfirmation(result, match.id, selected, tournament))
          throw new Error('Invalid confirmation');
        applied = true;
        onMatchUpdated(result.match);
        clearPreview();
        await reload();
        cancelAfterRefresh();
      }
    } catch (failure: unknown) {
      const status = isAxiosError(failure) ? failure.response?.status : undefined;
      if (confirm) clearPreview();
      if (status === 401 || status === 403 || status === 404) {
        deniedRef.current = true;
        setDenied(true);
      }
      const uncertain =
        confirm && !applied && (status === undefined || status === 408 || status >= 500);
      setError(
        t(
          applied
            ? 'hockey_source_refresh_error'
            : uncertain
              ? 'hockey_source_uncertain'
              : status === 409
                ? 'hockey_source_conflict'
                : status === 401 || status === 403
                  ? 'hockey_source_forbidden'
                  : status === 404
                    ? 'hockey_source_missing'
                    : status === 400
                      ? 'hockey_source_archived'
                      : status === 422
                        ? 'hockey_source_invalid'
                        : 'hockey_source_error',
        ),
      );
      if (uncertain || applied) {
        reviewRef.current = true;
        setNeedsReview(true);
        if (uncertain) {
          try {
            await reload();
            cancelAfterRefresh();
          } catch {
            /* Keep review-only state and visible uncertainty. */
          }
        }
      }
    } finally {
      pendingRef.current = false;
      setPending(false);
      onSavingChange(false);
    }
  }
  function cancelAfterRefresh() {
    reviewRef.current = false;
    setNeedsReview(false);
    cancelValues();
  }
  function cancelValues() {
    clearPreview();
    targetRef.current = null;
    setTarget(null);
    onDirtyChange(false);
  }
  async function review() {
    if (!allowed()) return;
    pendingRef.current = true;
    setPending(true);
    onSavingChange(true);
    try {
      await reload();
      cancelAfterRefresh();
      setError(null);
    } catch {
      setError(t('hockey_source_refresh_error'));
    } finally {
      pendingRef.current = false;
      setPending(false);
      onSavingChange(false);
    }
  }
  return (
    <Stack gap="sm">
      <Title order={4}>{t('hockey_source_title')}</Title>
      <Badge>{label(match.score_entry_source)}</Badge>
      <Text size="sm">
        {t(`hockey_source_${match.score_entry_source ?? 'legacy'}_description`)}
      </Text>
      {hasBlockedChanges() && !pending && <Alert color="yellow">{t('hockey_source_dirty')}</Alert>}
      {error && <Alert color="red">{error}</Alert>}
      {administrative && !archived && !denied && (
        <>
          {needsReview ? (
            <Button disabled={locked} onClick={review}>
              {t('hockey_source_reload')}
            </Button>
          ) : (
            <>
              <Select
                label={t('hockey_source_target')}
                value={target}
                disabled={locked}
                data={['MANUAL', 'EVENTS'].map((source) => ({
                  value: source,
                  label: t(`hockey_source_${source}`),
                  disabled: source === match.score_entry_source,
                }))}
                onChange={choose}
              />
              <Group>
                <Button
                  loading={pending}
                  disabled={locked || !target || target === match.score_entry_source}
                  onClick={() => act(false)}
                >
                  {t('hockey_source_preview')}
                </Button>
                {target && (
                  <Button variant="outline" disabled={pending} onClick={cancel}>
                    {t('hockey_source_cancel')}
                  </Button>
                )}
              </Group>
            </>
          )}
        </>
      )}
      {target && (denied || archived || !administrative) && !needsReview && (
        <Button variant="outline" disabled={pending} onClick={cancel}>
          {t('hockey_source_cancel')}
        </Button>
      )}
      {preview && (
        <Paper withBorder p="sm">
          <Stack gap="sm">
            <Text fw={600}>
              {label(preview.current_source)} → {label(preview.target_source)}
            </Text>
            <Text>{t('hockey_source_goal_count', { count: preview.relevant_goal_count })}</Text>
            <Text>
              {t(
                preview.target_source === 'MANUAL'
                  ? 'hockey_source_to_manual'
                  : 'hockey_source_to_events',
              )}
            </Text>
            <Text>{t('hockey_source_events_preserved')}</Text>
            {preview.scores_changed && (
              <Alert color="yellow">{t('hockey_source_scores_changed')}</Alert>
            )}
            {preview.target_source === 'EVENTS' &&
              preview.relevant_goal_count === 0 &&
              preview.scores_changed && (
                <Alert color="red">{t('hockey_source_zero_warning')}</Alert>
              )}
            {preview.rankings_may_change && (
              <Alert color="yellow">{t('hockey_source_rankings_changed')}</Alert>
            )}
            {preview.current_scores.map((before, i) => (
              <Paper key={before.period} withBorder p="sm">
                <Stack gap="xs">
                  <Text fw={600}>{t(`hockey_phase_period_${before.period}`)}</Text>
                  {[0, 1].map((side) => (
                    <Text key={side} size="sm">
                      {teamNames[side]}: {t('hockey_source_before')}{' '}
                      {side === 0 ? before.team1_score : before.team2_score}
                      {' → '}
                      {t('hockey_source_after')}{' '}
                      {side === 0
                        ? preview.resulting_scores[i].team1_score
                        : preview.resulting_scores[i].team2_score}
                      {'; '}
                      {t('hockey_source_difference')}{' '}
                      {side === 0
                        ? preview.differences[i].team1_difference
                        : preview.differences[i].team2_difference}
                    </Text>
                  ))}
                </Stack>
              </Paper>
            ))}
            <Checkbox
              label={t('hockey_source_approve')}
              checked={approved}
              disabled={locked || !administrative || archived || denied}
              onChange={(event) => {
                approvedRef.current = event.currentTarget.checked;
                setApproved(event.currentTarget.checked);
              }}
            />
            <Button
              color="orange"
              loading={pending}
              disabled={!approved || locked || !administrative || archived || denied}
              onClick={() => act(true)}
            >
              {t('hockey_source_confirm')}
            </Button>
          </Stack>
        </Paper>
      )}
    </Stack>
  );
}
