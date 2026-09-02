import { Alert, Button, Card, Group, Loader, NumberInput, Stack, Text, Title } from '@mantine/core';
import React, { useState } from 'react';

import {
  CompetitionScoringBodyInterface,
  CompetitionScoringInterface,
} from '../../interfaces/competition';
import { getCompetitionScoring } from '../../services/adapter';
import { saveCompetitionScoring } from '../../services/competition';
import { responseIsValid } from '../utils/util';

const defaultScoring: CompetitionScoringBodyInterface[] = [
  { place: 1, points: 2.5 },
  { place: 2, points: 1.5 },
  { place: 3, points: 1 },
  { place: 4, points: 0.5 },
];

function CompetitionScoringForm({
  tournamentId,
  competitionId,
  scoring,
  mutateScoring,
}: {
  tournamentId: number;
  competitionId: number;
  scoring: CompetitionScoringInterface[];
  mutateScoring: () => Promise<unknown>;
}) {
  const [values, setValues] = useState<CompetitionScoringBodyInterface[]>(
    scoring.length > 0
      ? scoring.map((item) => ({ place: item.place, points: Number(item.points) }))
      : defaultScoring
  );
  const [saving, setSaving] = useState(false);

  async function save() {
    setSaving(true);
    try {
      await saveCompetitionScoring(tournamentId, competitionId, values);
      await mutateScoring();
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
        <Group gap="sm" align="end">
          {values.map((item, index) => (
            <NumberInput
              key={item.place}
              label={`Platz ${item.place}`}
              value={item.points}
              min={0}
              decimalScale={2}
              step={0.5}
              w={100}
              onChange={(value) => {
                const points = typeof value === 'number' ? value : 0;
                setValues((current) =>
                  current.map((entry, entryIndex) =>
                    entryIndex === index ? { ...entry, points } : entry
                  )
                );
              }}
            />
          ))}
          <Button loading={saving} onClick={save}>
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
  const swrScoringResponse = getCompetitionScoring(tournamentId, competitionId);

  if (swrScoringResponse.error != null) {
    return <Alert color="red">Punkteschema konnte nicht geladen werden.</Alert>;
  }
  if (!responseIsValid(swrScoringResponse)) return <Loader size="sm" />;

  return (
    <CompetitionScoringForm
      tournamentId={tournamentId}
      competitionId={competitionId}
      scoring={swrScoringResponse.data.data}
      mutateScoring={swrScoringResponse.mutate}
    />
  );
}

