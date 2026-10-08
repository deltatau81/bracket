import { Alert, Button, Grid, NumberInput, Stack, Text, Title } from '@mantine/core';
import { useForm } from '@mantine/form';
import { useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useSWRConfig } from 'swr';

import { MatchUpdateBody, MatchWithDetails, Tournament } from '@openapi';
import { updateMatch } from '@services/match';

type ScoreField =
  | 'stage_item_input1_score'
  | 'stage_item_input2_score'
  | 'stage_item_input1_half1_score'
  | 'stage_item_input2_half1_score'
  | 'stage_item_input1_half2_score'
  | 'stage_item_input2_half2_score'
  | 'stage_item_input1_penalty_score'
  | 'stage_item_input2_penalty_score';

export function hockeyScoreSections(mode: Tournament['hockey_mode']): {
  label: string;
  fields: [ScoreField, ScoreField];
}[] {
  const shootout: { label: string; fields: [ScoreField, ScoreField] } = {
    label: 'hockey_score_shootout',
    fields: ['stage_item_input1_penalty_score', 'stage_item_input2_penalty_score'],
  };
  if (mode === 'GAME_SHOOTOUT')
    return [
      {
        label: 'hockey_score_game',
        fields: ['stage_item_input1_score', 'stage_item_input2_score'],
      },
      shootout,
    ];
  if (mode === 'COMPETITION')
    return [
      {
        label: 'hockey_score_half1',
        fields: ['stage_item_input1_half1_score', 'stage_item_input2_half1_score'],
      },
      {
        label: 'hockey_score_half2',
        fields: ['stage_item_input1_half2_score', 'stage_item_input2_half2_score'],
      },
      shootout,
    ];
  return [];
}

export function validHockeyScore(value: string | number): value is number {
  return typeof value === 'number' && Number.isSafeInteger(value) && value >= 0;
}

export default function HockeyScoreEditor({
  tournament,
  match,
  teamNames,
  refreshMatch,
  onSaved,
  onSavingChange,
  onDirtyChange,
}: {
  tournament: Tournament;
  match: MatchWithDetails;
  teamNames: [string, string];
  refreshMatch: () => Promise<unknown>;
  onSaved: () => void;
  onSavingChange: (saving: boolean) => void;
  onDirtyChange?: (dirty: boolean) => void;
}) {
  const { t } = useTranslation();
  const { mutate } = useSWRConfig();
  const sections = hockeyScoreSections(tournament.hockey_mode);
  const fields = sections.flatMap((section) => section.fields);
  const form = useForm<Partial<Record<ScoreField, string | number>>>({
    initialValues: Object.fromEntries(fields.map((field) => [field, match[field]])),
    validate: Object.fromEntries(
      fields.map((field) => [
        field,
        (value: string | number) => (validHockeyScore(value) ? null : t('hockey_score_invalid')),
      ]),
    ),
  });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const savingRef = useRef(false);
  const previousMatch = useRef(match);
  useEffect(() => {
    const previous = previousMatch.current;
    if (previous === match) return;
    const pristine = fields.every((field) => form.values[field] === previous[field]);
    if (pristine) {
      form.setValues(Object.fromEntries(fields.map((field) => [field, match[field]])));
      onDirtyChange?.(false);
    } else {
      // Preserve local inputs even when fresh server scores differ.
      onDirtyChange?.(true);
    }
    previousMatch.current = match;
  }, [match]);
  const events = match.score_entry_source === 'EVENTS';
  const readOnly = events || tournament.status === 'ARCHIVED';
  async function save(values: typeof form.values) {
    if (savingRef.current || readOnly || fields.length === 0) return;
    if (fields.some((field) => !validHockeyScore(values[field] ?? ''))) {
      setError(t('hockey_score_invalid'));
      return;
    }
    const body: Partial<MatchUpdateBody> & Pick<MatchUpdateBody, 'round_id'> = {
      round_id: match.round_id,
    };
    for (const field of fields) {
      const value = values[field];
      if (value !== undefined && validHockeyScore(value) && value !== match[field])
        body[field] = value;
    }
    savingRef.current = true;
    setSaving(true);
    onSavingChange(true);
    setError(null);
    let saved = false;
    try {
      await updateMatch(tournament.id, match.id, body, true);
      saved = true;
      await refreshMatch();
      await mutate(`tournaments/${tournament.id}/overall_standings`);
      onSaved();
    } catch {
      setError(t(saved ? 'hockey_score_refresh_error' : 'hockey_score_save_error'));
    } finally {
      savingRef.current = false;
      setSaving(false);
      onSavingChange(false);
    }
  }
  return (
    <form onSubmit={form.onSubmit(save)}>
      <Stack gap="md">
        <Text size="sm" c="dimmed">
          {t('hockey_score_unknown_capture')}
        </Text>
        {events && <Alert color="blue">{t('hockey_score_events')}</Alert>}
        {tournament.status === 'ARCHIVED' && (
          <Alert color="gray">{t('hockey_score_archived')}</Alert>
        )}
        {error && <Alert color="red">{error}</Alert>}
        {sections.map((section) => (
          <Stack key={section.label} gap="xs">
            <Title order={4}>{t(section.label)}</Title>
            <Grid>
              {section.fields.map((field, side) => (
                <Grid.Col key={field} span={{ base: 12, sm: 6 }}>
                  <NumberInput
                    label={teamNames[side]}
                    aria-label={`${t(section.label)}: ${teamNames[side]}`}
                    min={0}
                    allowDecimal={false}
                    allowNegative={false}
                    required
                    disabled={saving || readOnly}
                    {...form.getInputProps(field)}
                    onChange={(value) => {
                      form.setFieldValue(field, value);
                      onDirtyChange?.(
                        fields.some(
                          (candidate) =>
                            (candidate === field ? value : form.values[candidate]) !==
                            match[candidate],
                        ),
                      );
                    }}
                  />
                </Grid.Col>
              ))}
            </Grid>
          </Stack>
        ))}
        {!readOnly && onDirtyChange && (
          <Button
            variant="default"
            disabled={saving}
            onClick={() => {
              form.setValues(Object.fromEntries(fields.map((field) => [field, match[field]])));
              onDirtyChange(false);
            }}
          >
            {t('hockey_phase_discard')}
          </Button>
        )}
        {!readOnly && (
          <Button type="submit" loading={saving} disabled={saving}>
            {t('save_button')}
          </Button>
        )}
      </Stack>
    </form>
  );
}
