import { Alert, Button, Fieldset, Grid, Stack, Text, TextInput } from '@mantine/core';
import { useForm } from '@mantine/form';
import { useEffect, useRef, useState } from 'react';

import { Tournament, TournamentResponse } from '@openapi';
import { updateTournament } from '@services/tournament';

export const hockeyScoringFields = [
  'game_win_points',
  'game_draw_points',
  'game_loss_points',
  'shootout_win_points',
  'shootout_draw_points',
  'shootout_loss_points',
] as const;

type HockeyScoringValues = Pick<Tournament, (typeof hockeyScoringFields)[number]>;

export function normalizeHockeyPoints(value: string): string | null {
  const normalized = value.trim().replace(',', '.');
  if (!/^\d+(?:\.\d{1,2})?$/.test(normalized)) return null;
  const [integer, fraction] = normalized.split('.');
  const whole = integer.replace(/^0+(?=\d)/, '');
  // Numeric(8,2) allows at most six integer digits and two decimal digits.
  if (whole.length > 6) return null;
  return fraction === undefined ? whole : `${whole}.${fraction}`;
}

export function getHockeyScoringValues(tournament: Tournament): HockeyScoringValues {
  return {
    game_win_points: tournament.game_win_points,
    game_draw_points: tournament.game_draw_points,
    game_loss_points: tournament.game_loss_points,
    shootout_win_points: tournament.shootout_win_points,
    shootout_draw_points: tournament.shootout_draw_points,
    shootout_loss_points: tournament.shootout_loss_points,
  };
}

export function normalizeHockeyScoring(values: HockeyScoringValues): HockeyScoringValues | null {
  const normalized = { ...values };
  for (const field of hockeyScoringFields) {
    const value = normalizeHockeyPoints(values[field]);
    if (value === null) return null;
    normalized[field] = value;
  }
  return normalized;
}

const groups = [
  {
    label: 'Spiel',
    fields: [
      { field: 'game_win_points', label: 'Sieg' },
      { field: 'game_draw_points', label: 'Unentschieden' },
      { field: 'game_loss_points', label: 'Niederlage' },
    ],
  },
  {
    label: 'Shootout',
    fields: [
      { field: 'shootout_win_points', label: 'Sieg' },
      { field: 'shootout_draw_points', label: 'Unentschieden' },
      { field: 'shootout_loss_points', label: 'Niederlage' },
    ],
  },
] as const;

export default function HockeyScoringForm({
  tournament,
  mutateTournament,
}: {
  tournament: Tournament;
  mutateTournament: () => Promise<TournamentResponse | undefined>;
}) {
  const [saving, setSaving] = useState(false);
  const [result, setResult] = useState<'saved' | 'error' | null>(null);
  const form = useForm<HockeyScoringValues>({
    initialValues: getHockeyScoringValues(tournament),
    validate: Object.fromEntries(
      hockeyScoringFields.map((field) => [
        field,
        (value: string) =>
          normalizeHockeyPoints(value) === null
            ? 'Bitte einen Wert von 0 bis 999999,99 mit maximal zwei Nachkommastellen eingeben.'
            : null,
      ]),
    ),
  });

  const previousScoring = useRef(JSON.stringify(getHockeyScoringValues(tournament)));
  useEffect(() => {
    const storedValues = getHockeyScoringValues(tournament);
    const nextScoring = JSON.stringify(storedValues);
    if (previousScoring.current === nextScoring) return;
    previousScoring.current = nextScoring;
    form.setValues(storedValues);
  }, [tournament]);

  if (tournament.hockey_mode !== 'COMPETITION' && tournament.hockey_mode !== 'GAME_SHOOTOUT') {
    return null;
  }

  const disabled = saving || tournament.status !== 'OPEN';
  return (
    <form
      onSubmit={form.onSubmit(async (values) => {
        const normalized = normalizeHockeyScoring(values);
        if (normalized === null || disabled) return;
        setSaving(true);
        setResult(null);
        try {
          await updateTournament(
            tournament.id,
            tournament.name,
            tournament.dashboard_public,
            tournament.dashboard_endpoint,
            tournament.players_can_be_in_multiple_teams,
            tournament.auto_assign_courts,
            tournament.start_time,
            tournament.duration_minutes,
            tournament.margin_minutes,
            tournament.competition_format,
            normalized,
          );
          const response = await mutateTournament();
          form.setValues(response ? getHockeyScoringValues(response.data) : normalized);
          setResult('saved');
        } catch {
          setResult('error');
        } finally {
          setSaving(false);
        }
      })}
    >
      <Fieldset legend="Hockey-Punkteverteilung" mt="lg" radius="md">
        <Stack gap="md">
          <Text size="sm">
            Legt fest, wie viele Punkte für Sieg, Unentschieden und Niederlage in Hockeyspielen und
            Shootouts vergeben werden.
          </Text>
          <Grid>
            {groups.map((group) => (
              <Grid.Col key={group.label} span={{ base: 12, sm: 6 }}>
                <Fieldset legend={group.label} radius="md">
                  <Stack gap="sm">
                    {group.fields.map(({ field, label }) => (
                      <TextInput
                        key={field}
                        label={label}
                        withAsterisk
                        inputMode="decimal"
                        autoComplete="off"
                        disabled={disabled}
                        {...form.getInputProps(field)}
                      />
                    ))}
                  </Stack>
                </Fieldset>
              </Grid.Col>
            ))}
          </Grid>
          {result === 'error' && (
            <Alert color="red">Die Hockey-Punkteverteilung konnte nicht gespeichert werden.</Alert>
          )}
          {result === 'saved' && (
            <Alert color="green">Die Hockey-Punkteverteilung wurde gespeichert.</Alert>
          )}
          <Button type="submit" color="green" loading={saving} disabled={disabled}>
            Punkteverteilung speichern
          </Button>
        </Stack>
      </Fieldset>
    </form>
  );
}
