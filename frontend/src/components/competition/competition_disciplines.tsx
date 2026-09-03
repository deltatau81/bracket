import {
  Accordion,
  Alert,
  Badge,
  Button,
  Card,
  Group,
  Loader,
  NumberInput,
  Stack,
  Table,
  Text,
  TextInput,
  Title,
} from '@mantine/core';
import React, { useEffect, useMemo, useState } from 'react';

import {
  CompetitionDisciplineInterface,
  CompetitionMetricType,
  CompetitionRankedResultInterface,
  CompetitionResultBodyInterface,
  CompetitionResultInterface,
} from '../../interfaces/competition';
import { TeamInterface } from '../../interfaces/team';
import {
  getCompetitionDisciplines,
  getCompetitionResults,
} from '../../services/adapter';
import {
  calculateCompetitionResults,
  saveCompetitionResult,
} from '../../services/competition';
import { responseIsValid } from '../utils/util';
import CompetitionScoring from './competition_scoring';
import {
  AddDisciplineButton,
  DisciplineActions,
} from './discipline_management';

type NumericValue = number | string;

function asNumberOrNull(value: NumericValue): number | null {
  return typeof value === 'number' && Number.isFinite(value)
    ? value
    : null;
}

function formatTimeInput(
  timeMs: number | null | undefined
): string {
  if (timeMs == null) return '';

  const totalHundredths = Math.round(timeMs / 10);
  const minutes = Math.floor(totalHundredths / 6000);
  const seconds = Math.floor(
    (totalHundredths % 6000) / 100
  );
  const hundredths = totalHundredths % 100;

  return `${String(minutes).padStart(2, '0')}:${String(
    seconds
  ).padStart(2, '0')},${String(hundredths).padStart(
    2,
    '0'
  )}`;
}

function parseTimeInput(value: string): number | null {
  const match = value
    .trim()
    .match(/^(\d+):([0-5]\d),(\d{2})$/);

  if (match == null) return null;

  const minutes = Number(match[1]);
  const seconds = Number(match[2]);
  const hundredths = Number(match[3]);

  return (
    minutes * 60_000 +
    seconds * 1000 +
    hundredths * 10
  );
}

function ResultInput({
  metricType,
  value,
  onChange,
  optional = false,
}: {
  metricType: CompetitionMetricType;
  value: NumericValue;
  onChange: (value: NumericValue) => void;
  optional?: boolean;
}) {
  const commonProps = {
    value,
    onChange,
    min: metricType === 'MANUAL' ? 1 : 0,
    size: 'xs' as const,
    hideControls: true,
  };

  return (
    <NumberInput
      {...commonProps}
      aria-label={
        optional ? 'Torschüsse (optional)' : 'Ergebnis'
      }
      placeholder={optional ? 'optional' : undefined}
      allowDecimal={false}
    />
  );
}

function TeamResultRow({
  tournamentId,
  competitionId,
  discipline,
  team,
  result,
  mutateResults,
}: {
  tournamentId: number;
  competitionId: number;
  discipline: CompetitionDisciplineInterface;
  team: TeamInterface;
  result?: CompetitionResultInterface;
  mutateResults: () => Promise<unknown>;
}) {
  const [timeInput, setTimeInput] = useState(
    formatTimeInput(result?.time_ms)
  );

  const [attempts, setAttempts] =
    useState<NumericValue>(result?.attempts ?? '');

  const [successes, setSuccesses] =
    useState<NumericValue>(result?.successes ?? '');

  const [place, setPlace] =
    useState<NumericValue>(result?.place ?? '');

  const [saving, setSaving] = useState(false);

  const requiredValue =
    discipline.metric_type === 'TIME'
      ? parseTimeInput(timeInput)
      : discipline.metric_type === 'MANUAL'
        ? asNumberOrNull(place)
        : asNumberOrNull(successes);

  const ratioComplete =
    discipline.metric_type !== 'RATIO' ||
    asNumberOrNull(attempts) != null;

  async function save() {
    const body: CompetitionResultBodyInterface = {
      team_id: team.id,

      place:
        discipline.metric_type === 'MANUAL'
          ? asNumberOrNull(place)
          : null,

      time_ms:
        discipline.metric_type === 'TIME'
          ? parseTimeInput(timeInput)
          : null,

      attempts:
        discipline.metric_type === 'COUNT' ||
        discipline.metric_type === 'RATIO'
          ? asNumberOrNull(attempts)
          : null,

      successes:
        discipline.metric_type === 'COUNT' ||
        discipline.metric_type === 'RATIO'
          ? asNumberOrNull(successes)
          : null,

      notes: null,
    };

    setSaving(true);

    try {
      await saveCompetitionResult(
        tournamentId,
        competitionId,
        discipline.id,
        body
      );

      await mutateResults();
    } finally {
      setSaving(false);
    }
  }

  return (
    <Table.Tr>
      <Table.Td>
        <Text size="sm" fw={500}>
          {team.name}
        </Text>
      </Table.Td>

      {discipline.metric_type === 'TIME' ? (
        <Table.Td>
          <TextInput
            value={timeInput}
            onChange={(event) =>
              setTimeInput(event.currentTarget.value)
            }
            aria-label="Zeit in Minuten, Sekunden und Hundertstelsekunden"
            placeholder="mm:ss,ms"
            size="xs"
          />
        </Table.Td>
      ) : null}

      {discipline.metric_type === 'COUNT' ? (
        <>
          <Table.Td>
            <ResultInput
              metricType={discipline.metric_type}
              value={successes}
              onChange={setSuccesses}
            />
          </Table.Td>

          <Table.Td>
            <ResultInput
              metricType={discipline.metric_type}
              value={attempts}
              onChange={setAttempts}
              optional
            />
          </Table.Td>
        </>
      ) : null}

      {discipline.metric_type === 'RATIO' ? (
        <>
          <Table.Td>
            <ResultInput
              metricType={discipline.metric_type}
              value={attempts}
              onChange={setAttempts}
            />
          </Table.Td>

          <Table.Td>
            <ResultInput
              metricType={discipline.metric_type}
              value={successes}
              onChange={setSuccesses}
            />
          </Table.Td>
        </>
      ) : null}

      {discipline.metric_type === 'MANUAL' ? (
        <Table.Td>
          <ResultInput
            metricType={discipline.metric_type}
            value={place}
            onChange={setPlace}
          />
        </Table.Td>
      ) : null}

      <Table.Td>
        <Button
          size="xs"
          variant="light"
          loading={saving}
          disabled={
            requiredValue == null || !ratioComplete
          }
          onClick={save}
        >
          Speichern
        </Button>
      </Table.Td>
    </Table.Tr>
  );
}

function DisciplineResults({
  tournamentId,
  competitionId,
  discipline,
  teams,
  onCalculated,
}: {
  tournamentId: number;
  competitionId: number;
  discipline: CompetitionDisciplineInterface;
  teams: TeamInterface[];
  onCalculated: (
    disciplineId: number,
    results: CompetitionRankedResultInterface[]
  ) => void;
}) {
  const swrResultsResponse = getCompetitionResults(
    tournamentId,
    competitionId,
    discipline.id
  );

  const [rankedResults, setRankedResults] = useState<
    CompetitionRankedResultInterface[] | null
  >(null);

  const [calculating, setCalculating] =
    useState(false);

  async function calculate() {
    setCalculating(true);

    try {
      const response =
        await calculateCompetitionResults(
          tournamentId,
          competitionId,
          discipline.id
        );

      const ranked: CompetitionRankedResultInterface[] =
        response.data.data.map(
          (
            item: Omit<
              CompetitionRankedResultInterface,
              'points'
            > & {
              points: number | string;
            }
          ) => ({
            ...item,
            points: Number(item.points),
          })
        );

      setRankedResults(ranked);

      onCalculated(
        discipline.id,
        ranked
      );

      await swrResultsResponse.mutate();
    } finally {
      setCalculating(false);
    }
  }

  if (swrResultsResponse.error != null) {
    return (
      <Alert color="red">
        Ergebnisse konnten nicht geladen werden.
      </Alert>
    );
  }

  if (!responseIsValid(swrResultsResponse)) {
    return <Loader size="sm" />;
  }

  const results: CompetitionResultInterface[] =
    swrResultsResponse.data.data;

  const resultsByTeam = Object.fromEntries(
    results.map((result) => [
      result.team_id,
      result,
    ])
  );

  const teamsById = Object.fromEntries(
    teams.map((team) => [team.id, team])
  );

  const valueHeaders =
    discipline.metric_type === 'COUNT'
      ? ['Tore', 'Torschüsse']
      : discipline.metric_type === 'RATIO'
        ? ['Torschüsse', 'Gehalten']
        : [
            discipline.metric_type === 'TIME'
              ? 'Zeit (mm:ss,ms)'
              : 'Platz',
          ];

  return (
    <Stack gap="md">
      <Group justify="flex-end">
        <Button
          loading={calculating}
          onClick={calculate}
        >
          Auswerten
        </Button>
      </Group>

      <Table.ScrollContainer minWidth={600}>
        <Table verticalSpacing="xs">
          <Table.Thead>
            <Table.Tr>
              <Table.Th>Team</Table.Th>

              {valueHeaders.map((header) => (
                <Table.Th key={header}>
                  {header}
                </Table.Th>
              ))}

              <Table.Th />
            </Table.Tr>
          </Table.Thead>

          <Table.Tbody>
            {teams.map((team) => {
              const result =
                resultsByTeam[team.id];

              return (
                <TeamResultRow
                  key={`${team.id}-${result?.updated ?? 'new'}`}
                  tournamentId={tournamentId}
                  competitionId={competitionId}
                  discipline={discipline}
                  team={team}
                  result={result}
                  mutateResults={
                    swrResultsResponse.mutate
                  }
                />
              );
            })}
          </Table.Tbody>
        </Table>
      </Table.ScrollContainer>

      {rankedResults != null ? (
        rankedResults.length > 0 ? (
          <Table withTableBorder>
            <Table.Thead>
              <Table.Tr>
                <Table.Th>Platz</Table.Th>
                <Table.Th>Team</Table.Th>
                <Table.Th>Punkte</Table.Th>
                <Table.Th />
              </Table.Tr>
            </Table.Thead>

            <Table.Tbody>
              {rankedResults.map((ranked) => (
                <Table.Tr key={ranked.result.id}>
                  <Table.Td>
                    {ranked.place}
                  </Table.Td>

                  <Table.Td>
                    {
                      teamsById[
                        ranked.result.team_id
                      ]?.name
                    }
                  </Table.Td>

                  <Table.Td>
                    {ranked.points}
                  </Table.Td>

                  <Table.Td>
                    {ranked.tied ? (
                      <Badge
                        size="xs"
                        color="yellow"
                        variant="light"
                      >
                        Gleichstand
                      </Badge>
                    ) : null}
                  </Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        ) : (
          <Text
            size="sm"
            c="dimmed"
          >
            Keine vollständigen Ergebnisse zur
            Auswertung vorhanden.
          </Text>
        )
      ) : null}
    </Stack>
  );
}

export default function CompetitionDisciplines({
  tournamentId,
  competitionId,
  teams = [],
  onPointsChange,
  mode = 'manage',
}: {
  tournamentId: number;
  competitionId: number;
  teams?: TeamInterface[];
  onPointsChange?: (
    competitionId: number,
    pointsByTeam: Record<number, number>
  ) => void;
  mode?: 'manage' | 'results';
}) {
  const swrDisciplinesResponse =
    getCompetitionDisciplines(
      tournamentId,
      competitionId
    );

  const [
    rankedByDiscipline,
    setRankedByDiscipline,
  ] = useState<
    Record<
      number,
      CompetitionRankedResultInterface[]
    >
  >({});

  const totalPointsByTeam = useMemo(
    () =>
      Object.values(rankedByDiscipline)
        .flat()
        .reduce<Record<number, number>>(
          (totals, ranked) => {
            totals[ranked.result.team_id] =
              (totals[
                ranked.result.team_id
              ] ?? 0) + ranked.points;

            return totals;
          },
          {}
        ),
    [rankedByDiscipline]
  );

  useEffect(() => {
    onPointsChange?.(
      competitionId,
      totalPointsByTeam
    );
  }, [
    competitionId,
    onPointsChange,
    totalPointsByTeam,
  ]);

  if (
    swrDisciplinesResponse.error != null
  ) {
    return (
      <Alert color="red">
        Disziplinen konnten nicht geladen werden.
      </Alert>
    );
  }

  if (
    !responseIsValid(
      swrDisciplinesResponse
    )
  ) {
    return <Loader size="sm" />;
  }

  const disciplines: CompetitionDisciplineInterface[] =
    swrDisciplinesResponse.data.data;

  const nextSortOrder =
    disciplines.reduce(
      (maximum, discipline) =>
        Math.max(
          maximum,
          discipline.sort_order
        ),
      -1
    ) + 1;

  const teamList: TeamInterface[] =
    Array.isArray(teams)
      ? teams
      : (teams as any)?.teams ?? [];

  const standings = teamList
    .map((team) => ({
      team,
      points:
        totalPointsByTeam[team.id] ?? 0,
    }))
    .sort(
      (a, b) =>
        b.points - a.points ||
        a.team.name.localeCompare(
          b.team.name
        )
    );

  return (
    <Stack gap="lg">
      {mode === 'manage' ? (
        <>
          <CompetitionScoring
            tournamentId={tournamentId}
            competitionId={competitionId}
          />

          <Group justify="flex-end">
            <AddDisciplineButton
              tournamentId={tournamentId}
              competitionId={competitionId}
              sortOrder={nextSortOrder}
              mutateDisciplines={
                swrDisciplinesResponse.mutate
              }
            />
          </Group>
        </>
      ) : null}

      {disciplines.length === 0 ? (
        <Text
          size="sm"
          c="dimmed"
        >
          Noch keine Disziplinen angelegt.
        </Text>
      ) : (
        <Accordion
          key={disciplines
            .map(
              (discipline) =>
                discipline.id
            )
            .join('-')}
          variant="separated"
          multiple
          defaultValue={disciplines.map(
            (discipline) =>
              String(discipline.id)
          )}
        >
          {disciplines.map(
            (discipline) => (
              <Accordion.Item
                key={discipline.id}
                value={`${discipline.id}`}
              >
                <Accordion.Control>
                  <Group gap="xs">
                    <Text fw={500}>
                      {discipline.name}
                    </Text>

                    <Badge
                      size="xs"
                      variant="light"
                    >
                      {
                        discipline.metric_type
                      }
                    </Badge>
                  </Group>
                </Accordion.Control>

                <Accordion.Panel>
                  <Stack gap="sm">
                    {mode === 'manage' ? (
                      <Group justify="flex-end">
                        <DisciplineActions
                          tournamentId={
                            tournamentId
                          }
                          competitionId={
                            competitionId
                          }
                          discipline={
                            discipline
                          }
                          mutateDisciplines={
                            swrDisciplinesResponse.mutate
                          }
                        />
                      </Group>
                    ) : null}

                    {discipline.description !=
                      null &&
                    discipline.description !==
                      '' ? (
                      <Text
                        size="sm"
                        c="dimmed"
                      >
                        {
                          discipline.description
                        }
                      </Text>
                    ) : null}

                    {mode === 'results' ? (
                      <DisciplineResults
                        tournamentId={
                          tournamentId
                        }
                        competitionId={
                          competitionId
                        }
                        discipline={
                          discipline
                        }
                        teams={teamList}
                        onCalculated={(
                          disciplineId,
                          ranked
                        ) => {
                          setRankedByDiscipline(
                            (current) => ({
                              ...current,
                              [disciplineId]:
                                ranked,
                            })
                          );
                        }}
                      />
                    ) : null}
                  </Stack>
                </Accordion.Panel>
              </Accordion.Item>
            )
          )}
        </Accordion>
      )}

      {mode === 'results' ? (
        <Card
          withBorder
          padding="md"
          radius="md"
        >
          <Title
            order={4}
            mb="sm"
          >
            Competition-Gesamtwertung
          </Title>

          <Table>
            <Table.Thead>
              <Table.Tr>
                <Table.Th>Rang</Table.Th>
                <Table.Th>Team</Table.Th>
                <Table.Th>Punkte</Table.Th>
              </Table.Tr>
            </Table.Thead>

            <Table.Tbody>
              {standings.map(
                (
                  { team, points },
                  index
                ) => (
                  <Table.Tr key={team.id}>
                    <Table.Td>
                      {index + 1}
                    </Table.Td>

                    <Table.Td>
                      {team.name}
                    </Table.Td>

                    <Table.Td>
                      {points}
                    </Table.Td>
                  </Table.Tr>
                )
              )}
            </Table.Tbody>
          </Table>
        </Card>
      ) : null}
    </Stack>
  );
}
