import { Alert, Button, Card, Group, Loader, NumberInput, Stack, Text, Title } from '@mantine/core';
import { useEffect, useRef, useState } from 'react';

import { CompetitionScoring as CompetitionScoringEntry, CompetitionScoringBody } from '@openapi';
import { getCompetitionScoring } from '@services/adapter';
import { saveCompetitionScoring } from '@services/competition';

const defaultScoring: CompetitionScoringBody[] = [
  { place: 1, points: 2.5 },
  { place: 2, points: 1.5 },
  { place: 3, points: 1 },
  { place: 4, points: 0.5 },
];

function scoringPoints(value: CompetitionScoringBody['points']): number | null {
  if (typeof value === 'string' && value.trim() === '') return null;
  const points = Number(value);
  return Number.isFinite(points) && points >= 0 ? points : null;
}

function CompetitionScoringForm({
  tournamentId,
  competitionId,
  scoring,
  mutateScoring,
}: {
  tournamentId: number;
  competitionId: number;
  scoring: CompetitionScoringEntry[];
  mutateScoring: () => Promise<unknown>;
}) {
  const [values, setValues] = useState<CompetitionScoringBody[]>(() =>
    scoring.length === 0
      ? defaultScoring.map((item) => ({ ...item }))
      : scoring.map((item) => ({ place: item.place, points: scoringPoints(item.points) ?? '' })),
  );
  const previousScoring = useRef(JSON.stringify(scoring));
  useEffect(() => {
    const nextScoring = JSON.stringify(scoring);
    if (previousScoring.current === nextScoring) return;
    previousScoring.current = nextScoring;
    setValues(
      scoring.map((item) => ({
        place: item.place,
        points: scoringPoints(item.points) ?? '',
      })),
    );
  }, [scoring]);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(false);
  const valid =
    values.every(
      (item) =>
        Number.isSafeInteger(item.place) && item.place >= 1 && scoringPoints(item.points) != null,
    ) && new Set(values.map((item) => item.place)).size === values.length;

  function addPlace() {
    if (saving) return;
    setError(false);
    setValues((current) => {
      const place = current.reduce((maximum, item) => Math.max(maximum, item.place), 0) + 1;
      return [...current, { place, points: 0 }];
    });
  }

  function removePlace(place: number) {
    if (saving) return;
    setError(false);
    setValues((current) => current.filter((item) => item.place !== place));
  }

  async function save() {
    if (!valid || saving) return;
    const body: CompetitionScoringBody[] = values.map((item) => ({
      place: item.place,
      points: Number(item.points),
    }));
    setSaving(true);
    setError(false);
    try {
      await saveCompetitionScoring(tournamentId, competitionId, body);
      await mutateScoring();
    } catch {
      setError(true);
    } finally {
      setSaving(false);
    }
  }

  return (
    <Card withBorder padding="md" radius="md">
      <Stack gap="sm">
        <div>
          <Title order={4}>Punkteschema</Title>
          <Text size="sm" c="dimmed">
            Dieses Schema gilt für alle Disziplinen der Competition.
          </Text>
        </div>
        {error && <Alert color="red">Das Punkteschema konnte nicht gespeichert werden.</Alert>}
        {!valid && (
          <Alert color="red">Bitte gültige, nichtnegative Punkte für jeden Platz eingeben.</Alert>
        )}
        <Group gap="sm" align="end">
          {values.map((item, index) => (
            <Stack key={item.place} gap="xs">
              <NumberInput
                label={`Platz ${item.place}`}
                value={item.points}
                min={0}
                decimalScale={2}
                step={0.5}
                w={100}
                disabled={saving}
                onChange={(points) => {
                  setError(false);
                  setValues((current) =>
                    current.map((entry, entryIndex) =>
                      entryIndex === index ? { ...entry, points } : entry,
                    ),
                  );
                }}
              />
              <Button
                size="xs"
                variant="light"
                color="red"
                disabled={saving}
                aria-label={`Platz ${item.place} entfernen`}
                onClick={() => removePlace(item.place)}
              >
                Entfernen
              </Button>
            </Stack>
          ))}
          <Button variant="light" disabled={saving} onClick={addPlace}>
            Platz hinzufügen
          </Button>
          <Button loading={saving} disabled={!valid} onClick={save}>
            Punkteschema speichern
          </Button>
        </Group>
      </Stack>
    </Card>
  );
}

export default function CompetitionScoring({
  tournamentId,
  competitionId,
}: {
  tournamentId: number;
  competitionId: number;
}) {
  const response = getCompetitionScoring(tournamentId, competitionId);
  if (response.error)
    return <Alert color="red">Das Punkteschema konnte nicht geladen werden.</Alert>;
  if (!response.data) return <Loader size="sm" />;
  return (
    <CompetitionScoringForm
      key={JSON.stringify([tournamentId, competitionId])}
      tournamentId={tournamentId}
      competitionId={competitionId}
      scoring={response.data.data}
      mutateScoring={response.mutate}
    />
  );
}
