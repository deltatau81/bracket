import { Badge, Card, Group, Loader, ScrollArea, Stack, Table, Text, Title } from '@mantine/core';
import React from 'react';

import {
  CompetitionDisciplineInterface,
  CompetitionInterface,
  CompetitionMetricType,
  CompetitionResultInterface,
  CompetitionScoringInterface,
} from '../../interfaces/competition';
import { TeamInterface } from '../../interfaces/team';
import {
  getCompetitionDisciplines,
  getCompetitionResults,
  getCompetitionScoring,
} from '../../services/adapter';
import { responseIsValid } from '../utils/util';

const numberFormatter = new Intl.NumberFormat('de-DE', {
  maximumFractionDigits: 2,
});

function formatTime(timeMs: number | null): string {
  if (timeMs == null) return '–';

  const minutes = Math.floor(timeMs / 60_000);
  const seconds = (timeMs % 60_000) / 1000;
  const formattedSeconds = seconds.toLocaleString('de-DE', {
    minimumIntegerDigits: minutes > 0 ? 2 : 1,
    minimumFractionDigits: 0,
    maximumFractionDigits: 3,
  });

  return minutes > 0 ? `${minutes}:${formattedSeconds} min` : `${formattedSeconds} s`;
}

function formatMetric(
  metricType: CompetitionMetricType,
  result?: CompetitionResultInterface
): string {
  if (result == null) return '–';

  if (metricType === 'TIME') return formatTime(result.time_ms);

  if (metricType === 'COUNT') {
    if (result.successes == null) return '–';
    return result.attempts == null
      ? String(result.successes)
      : `${result.successes}/${result.attempts}`;
  }

  if (metricType === 'RATIO') {
    if (result.successes == null || result.attempts == null) return '–';
    const percentage =
      result.attempts > 0 ? (result.successes / result.attempts) * 100 : 0;
    return `${result.successes}/${result.attempts} (${numberFormatter.format(percentage)} %)`;
  }

  return result.place == null ? '–' : `Platz ${result.place}`;
}

function DisciplineResults({
  tournamentId,
  competition,
  discipline,
  teams,
  pointsByPlace,
}: {
  tournamentId: number;
  competition: CompetitionInterface;
  discipline: CompetitionDisciplineInterface;
  teams: TeamInterface[];
  pointsByPlace: Record<number, number>;
}) {
  const swrResultsResponse = getCompetitionResults(
    tournamentId,
    competition.id,
    discipline.id
  );

  if (swrResultsResponse.error != null) {
    return (
      <Text c="red" size="sm">
        Ergebnisse konnten nicht geladen werden.
      </Text>
    );
  }
  if (!responseIsValid(swrResultsResponse)) return <Loader size="xs" />;

  const results: CompetitionResultInterface[] = swrResultsResponse.data.data;
  const resultsByTeam = results.reduce<Record<number, CompetitionResultInterface>>(
    (lookup, result) => ({ ...lookup, [result.team_id]: result }),
    {}
  );

  return (
    <Stack gap="xs">
      <div>
        <Group gap="xs">
          <Text fw={700}>{discipline.name}</Text>
          <Badge variant="light" size="sm">
            {discipline.metric_type}
          </Badge>
        </Group>
        {discipline.description ? (
          <Text size="sm" c="dimmed">
            {discipline.description}
          </Text>
        ) : null}
      </div>
      <ScrollArea>
        <Table striped withTableBorder miw={480}>
          <Table.Thead>
            <Table.Tr>
              <Table.Th>Mannschaft</Table.Th>
              <Table.Th>Platz</Table.Th>
              <Table.Th>Messwert</Table.Th>
              <Table.Th ta="right">Punkte</Table.Th>
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {teams.map((team) => {
              const result = resultsByTeam[team.id];
              const points = result?.place != null ? pointsByPlace[result.place] : undefined;
              return (
                <Table.Tr key={team.id}>
                  <Table.Td>{team.name}</Table.Td>
                  <Table.Td>{result?.place ?? '–'}</Table.Td>
                  <Table.Td>{formatMetric(discipline.metric_type, result)}</Table.Td>
                  <Table.Td ta="right">
                    {points == null ? '–' : numberFormatter.format(points)}
                  </Table.Td>
                </Table.Tr>
              );
            })}
          </Table.Tbody>
        </Table>
      </ScrollArea>
    </Stack>
  );
}

export default function CompetitionTimelineItem({
  tournamentId,
  competition,
  teams,
}: {
  tournamentId: number;
  competition: CompetitionInterface;
  teams: TeamInterface[];
}) {
  const swrDisciplinesResponse = getCompetitionDisciplines(tournamentId, competition.id);
  const swrScoringResponse = getCompetitionScoring(tournamentId, competition.id);

  const disciplines: CompetitionDisciplineInterface[] = responseIsValid(
    swrDisciplinesResponse
  )
    ? swrDisciplinesResponse.data.data
    : [];
  const scoring: CompetitionScoringInterface[] = responseIsValid(swrScoringResponse)
    ? swrScoringResponse.data.data
    : [];
  const pointsByPlace = scoring.reduce<Record<number, number>>(
    (lookup, item) => ({ ...lookup, [item.place]: Number(item.points) || 0 }),
    {}
  );

  return (
    <Card withBorder radius="md" padding="md">
      <Group justify="space-between" align="flex-start" mb="md">
        <div>
          <Title order={4}>{competition.name}</Title>
          {competition.description ? (
            <Text size="sm" c="dimmed">
              {competition.description}
            </Text>
          ) : null}
        </div>
        <Badge color="violet" variant="light">
          Technikwettbewerb
        </Badge>
      </Group>
      {swrDisciplinesResponse.error != null || swrScoringResponse.error != null ? (
        <Text c="red" size="sm">
          Wettbewerbsdaten konnten nicht geladen werden.
        </Text>
      ) : !responseIsValid(swrDisciplinesResponse) ||
        !responseIsValid(swrScoringResponse) ? (
        <Loader size="sm" />
      ) : disciplines.length === 0 ? (
        <Text c="dimmed" size="sm">
          Noch keine Disziplinen angelegt.
        </Text>
      ) : (
        <Stack>
          {disciplines.map((discipline) => (
            <DisciplineResults
              key={discipline.id}
              tournamentId={tournamentId}
              competition={competition}
              discipline={discipline}
              teams={teams}
              pointsByPlace={pointsByPlace}
            />
          ))}
        </Stack>
      )}
    </Card>
  );
}
