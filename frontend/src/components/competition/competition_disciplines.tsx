import {
  Accordion,
  Alert,
  Badge,
  Button,
  Group,
  Loader,
  NumberInput,
  Stack,
  Table,
  Text,
  TextInput,
} from '@mantine/core';
import { useState } from 'react';

import CompetitionScoring from '@components/competition/competition_scoring';
import CompetitionOverallStandings from '@components/competition/tournament_overall_standings';
import {
  AddDisciplineButton,
  DisciplineActions,
} from '@components/competition/discipline_management';
import {
  CompetitionDiscipline,
  CompetitionMetricType,
  CompetitionRankedResult,
  CompetitionResult,
  CompetitionResultBody,
  TournamentCompetitionFormat,
  Team,
} from '@openapi';
import {
  getCompetitionDisciplines,
  getCompetitionResults,
  getTeamsPaginated,
} from '@services/adapter';
import { calculateCompetitionResults, saveCompetitionResult } from '@services/competition';

type ResultValues = {
  timeInput: string;
  attempts: number | string;
  successes: number | string;
  place: number | string;
};

function asIntegerOrNull(value: number | string, minimum = 0): number | null {
  return typeof value === 'number' && Number.isSafeInteger(value) && value >= minimum
    ? value
    : null;
}

function formatTimeInput(timeMs: number | null | undefined): string {
  if (timeMs == null || !Number.isSafeInteger(timeMs) || timeMs < 0) return '';
  const hundredths = Math.round(timeMs / 10);
  const minutes = Math.floor(hundredths / 6000);
  const seconds = Math.floor((hundredths % 6000) / 100);
  return `${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')},${String(hundredths % 100).padStart(2, '0')}`;
}

function parseTimeInput(value: string): number | null {
  const match = value.trim().match(/^(\d+):([0-5]\d),(\d{2})$/);
  if (match == null) return null;
  const timeMs = Number(match[1]) * 60_000 + Number(match[2]) * 1000 + Number(match[3]) * 10;
  return Number.isSafeInteger(timeMs) && timeMs >= 0 ? timeMs : null;
}

function buildResultBody(
  metricType: CompetitionMetricType,
  teamId: number,
  values: ResultValues,
): CompetitionResultBody | null {
  const body: CompetitionResultBody = {
    team_id: teamId,
    place: null,
    time_ms: null,
    attempts: null,
    successes: null,
    notes: null,
  };
  switch (metricType) {
    case 'TIME':
      body.time_ms = parseTimeInput(values.timeInput);
      return body.time_ms == null ? null : body;
    case 'COUNT':
    case 'RATIO':
      body.successes = asIntegerOrNull(values.successes);
      body.attempts = asIntegerOrNull(values.attempts);
      if (body.successes == null) return null;
      if (metricType === 'RATIO' && body.attempts == null) return null;
      if (metricType === 'COUNT' && values.attempts !== '' && body.attempts == null) return null;
      return body;
    case 'MANUAL':
      body.place = asIntegerOrNull(values.place, 1);
      return body.place == null ? null : body;
  }
}

function normalizeRankedPoints(value: CompetitionRankedResult['points']): number | null {
  if (value.trim() === '') return null;
  const points = Number(value);
  return Number.isFinite(points) ? points : null;
}

function resultsVersion(results: CompetitionResult[], metricType: CompetitionMetricType): string {
  // Calculation writes places and timestamps; only changed inputs invalidate the ranking.
  return JSON.stringify(
    [...results]
      .sort((a, b) => a.team_id - b.team_id)
      .map((result) => [
        result.team_id,
        result.time_ms,
        result.attempts,
        result.successes,
        metricType === 'MANUAL' ? result.place : null,
      ]),
  );
}

function TeamResultRow({
  tournamentId,
  competitionId,
  discipline,
  team,
  result,
  calculating,
  onSavingChange,
  onSaved,
}: {
  tournamentId: number;
  competitionId: number;
  discipline: CompetitionDiscipline;
  team: Team;
  result?: CompetitionResult;
  calculating: boolean;
  onSavingChange: (change: number) => void;
  onSaved: () => Promise<unknown>;
}) {
  const [values, setValues] = useState<ResultValues>({
    timeInput: formatTimeInput(result?.time_ms),
    attempts: result?.attempts ?? '',
    successes: result?.successes ?? '',
    place: result?.place ?? '',
  });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(false);
  const body = buildResultBody(discipline.metric_type, team.id, values);
  const disabled = saving || calculating;

  function numericInput(
    field: 'attempts' | 'successes' | 'place',
    label: string,
    optional = false,
  ) {
    return (
      <NumberInput
        size="xs"
        hideControls
        allowDecimal={false}
        allowNegative={false}
        min={field === 'place' ? 1 : 0}
        value={values[field]}
        aria-label={`${team.name}: ${label}`}
        placeholder={optional ? 'optional' : undefined}
        disabled={disabled}
        onChange={(value) => {
          setValues((current) => ({ ...current, [field]: value }));
          setError(false);
        }}
      />
    );
  }

  async function save() {
    if (body == null || disabled) return;
    setSaving(true);
    setError(false);
    onSavingChange(1);
    try {
      await saveCompetitionResult(tournamentId, competitionId, discipline.id, body);
      await onSaved();
    } catch {
      setError(true);
    } finally {
      setSaving(false);
      onSavingChange(-1);
    }
  }

  return (
    <Table.Tr>
      <Table.Td>
        <Text size="sm" fw={500}>
          {team.name}
        </Text>
      </Table.Td>
      {discipline.metric_type === 'TIME' && (
        <Table.Td>
          <TextInput
            size="xs"
            value={values.timeInput}
            placeholder="mm:ss,HH"
            aria-label={`${team.name}: Zeit in Minuten, Sekunden und Hundertstelsekunden`}
            disabled={disabled}
            error={
              values.timeInput !== '' && parseTimeInput(values.timeInput) == null
                ? 'Format: mm:ss,HH'
                : undefined
            }
            onChange={(event) => {
              const timeInput = event.currentTarget.value;
              setValues((current) => ({ ...current, timeInput }));
              setError(false);
            }}
          />
        </Table.Td>
      )}
      {discipline.metric_type === 'COUNT' && (
        <>
          <Table.Td>{numericInput('successes', 'Tore')}</Table.Td>
          <Table.Td>{numericInput('attempts', 'Torschüsse (optional)', true)}</Table.Td>
        </>
      )}
      {discipline.metric_type === 'RATIO' && (
        <>
          <Table.Td>{numericInput('attempts', 'Torschüsse')}</Table.Td>
          <Table.Td>{numericInput('successes', 'Gehalten')}</Table.Td>
        </>
      )}
      {discipline.metric_type === 'MANUAL' && <Table.Td>{numericInput('place', 'Platz')}</Table.Td>}
      <Table.Td>
        <Button
          size="xs"
          variant="light"
          loading={saving}
          disabled={body == null || calculating}
          onClick={save}
        >
          Speichern
        </Button>
        {error && (
          <Text size="xs" c="red" role="alert">
            Das Ergebnis konnte nicht gespeichert werden.
          </Text>
        )}
      </Table.Td>
    </Table.Tr>
  );
}

function DisciplineRanking({
  rankedResults,
  teams,
}: {
  rankedResults: CompetitionRankedResult[];
  teams: Team[];
}) {
  if (rankedResults.length === 0)
    return (
      <Text size="sm" c="dimmed">
        Keine vollständigen Ergebnisse zur Auswertung vorhanden.
      </Text>
    );
  const teamsById = new Map(teams.map((team) => [team.id, team]));
  return (
    <Stack gap="sm">
      {rankedResults.some((ranked) => normalizeRankedPoints(ranked.points) == null) && (
        <Alert color="red">Die Auswertung enthält ungültige Punktewerte.</Alert>
      )}
      <Table.ScrollContainer minWidth={450}>
        <Table withTableBorder>
          <Table.Thead>
            <Table.Tr>
              <Table.Th>Platz</Table.Th>
              <Table.Th>Team</Table.Th>
              <Table.Th>Punkte</Table.Th>
              <Table.Th>Status</Table.Th>
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {rankedResults.map((ranked) => (
              <Table.Tr key={ranked.result.id}>
                <Table.Td>{ranked.place}</Table.Td>
                <Table.Td>
                  {teamsById.get(ranked.result.team_id)?.name ?? `Team #${ranked.result.team_id}`}
                </Table.Td>
                <Table.Td>{normalizeRankedPoints(ranked.points) ?? 'Ungültige Punkte'}</Table.Td>
                <Table.Td>
                  {ranked.tied && (
                    <Badge size="xs" color="yellow" variant="light">
                      Gleichstand
                    </Badge>
                  )}
                </Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      </Table.ScrollContainer>
    </Stack>
  );
}

function DisciplineResults({
  tournamentId,
  competitionId,
  discipline,
  teams,
}: {
  tournamentId: number;
  competitionId: number;
  discipline: CompetitionDiscipline;
  teams: Team[];
}) {
  const response = getCompetitionResults(tournamentId, competitionId, discipline.id);
  const [ranking, setRanking] = useState<{
    data: CompetitionRankedResult[];
    version: string;
  } | null>(null);
  const [calculating, setCalculating] = useState(false);
  const [savingCount, setSavingCount] = useState(0);
  const [error, setError] = useState(false);
  const results = response.data?.data ?? [];
  const version = resultsVersion(results, discipline.metric_type);

  async function calculate() {
    if (calculating || savingCount > 0) return;
    setCalculating(true);
    setError(false);
    setRanking(null);
    try {
      const calculated = await calculateCompetitionResults(
        tournamentId,
        competitionId,
        discipline.id,
      );
      const updated = await response.mutate();
      setRanking({
        data: calculated.data.data,
        version: resultsVersion(updated?.data ?? results, discipline.metric_type),
      });
    } catch {
      setError(true);
    } finally {
      setCalculating(false);
    }
  }
  async function onSaved() {
    setRanking(null);
    await response.mutate();
  }

  if (response.error)
    return <Alert color="red">Die Ergebnisse konnten nicht geladen werden.</Alert>;
  if (!response.data) return <Loader size="sm" />;
  const resultsByTeam = new Map(results.map((result) => [result.team_id, result]));
  const headers =
    discipline.metric_type === 'COUNT'
      ? ['Tore', 'Torschüsse (optional)']
      : discipline.metric_type === 'RATIO'
        ? ['Torschüsse', 'Gehalten']
        : [discipline.metric_type === 'TIME' ? 'Zeit (mm:ss,HH)' : 'Platz'];

  return (
    <Stack gap="md">
      {error && <Alert color="red">Die Disziplin konnte nicht ausgewertet werden.</Alert>}
      <Group justify="space-between">
        <Text size="sm" c="dimmed">
          Die Auswertung verwendet die gespeicherten Ergebnisse.
        </Text>
        <Button
          loading={calculating}
          disabled={savingCount > 0 || teams.length === 0}
          onClick={calculate}
        >
          Auswerten
        </Button>
      </Group>
      {teams.length === 0 ? (
        <Text size="sm" c="dimmed">
          Noch keine Teams vorhanden.
        </Text>
      ) : (
        <Table.ScrollContainer minWidth={600}>
          <Table verticalSpacing="xs">
            <Table.Thead>
              <Table.Tr>
                <Table.Th>Team</Table.Th>
                {headers.map((header) => (
                  <Table.Th key={header}>{header}</Table.Th>
                ))}
                <Table.Th>Aktion</Table.Th>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {teams.map((team) => {
                const result = resultsByTeam.get(team.id);
                return (
                  <TeamResultRow
                    key={JSON.stringify([team.id, discipline.metric_type, result ?? null])}
                    tournamentId={tournamentId}
                    competitionId={competitionId}
                    discipline={discipline}
                    team={team}
                    result={result}
                    calculating={calculating}
                    onSavingChange={(change) => setSavingCount((current) => current + change)}
                    onSaved={onSaved}
                  />
                );
              })}
            </Table.Tbody>
          </Table>
        </Table.ScrollContainer>
      )}
      {ranking != null && ranking.version === version && (
        <DisciplineRanking rankedResults={ranking.data} teams={teams} />
      )}
    </Stack>
  );
}

type DisciplinesProps = {
  tournamentId: number;
  competitionId: number;
  teams?: Team[];
  mode?: 'manage' | 'results';
  competitionFormat?: TournamentCompetitionFormat;
};

export function CompetitionTeams({
  tournamentId,
  offset = 0,
  teams = [],
  render,
}: {
  tournamentId: number;
  offset?: number;
  teams?: Team[];
  render: (teams: Team[]) => React.ReactNode;
}) {
  const response = getTeamsPaginated(tournamentId, {
    offset,
    limit: 100,
    sort_by: 'name',
    sort_direction: 'asc',
  });
  if (response.error) return <Alert color="red">Die Teams konnten nicht geladen werden.</Alert>;
  if (!response.data) return <Loader size="sm" />;
  const loaded = [...teams, ...response.data.data.teams];
  if (offset + 100 < response.data.data.count) {
    return (
      <CompetitionTeams
        tournamentId={tournamentId}
        offset={offset + 100}
        teams={loaded}
        render={render}
      />
    );
  }
  return render(loaded);
}

function DisciplineList({
  tournamentId,
  competitionId,
  disciplines,
  teams,
  mode,
  mutateDisciplines,
  competitionFormat,
}: {
  tournamentId: number;
  competitionId: number;
  disciplines: CompetitionDiscipline[];
  teams: Team[];
  mode: 'manage' | 'results';
  mutateDisciplines: () => Promise<unknown>;
  competitionFormat: TournamentCompetitionFormat;
}) {
  const nextSortOrder =
    disciplines.length === 0 ? 0 : Math.max(...disciplines.map((item) => item.sort_order)) + 1;
  return (
    <Stack>
      {mode === 'manage' && (
        <>
          <CompetitionScoring tournamentId={tournamentId} competitionId={competitionId} />
          <Group justify="flex-end">
            <AddDisciplineButton
              tournamentId={tournamentId}
              competitionId={competitionId}
              sortOrder={nextSortOrder}
              mutateDisciplines={mutateDisciplines}
            />
          </Group>
        </>
      )}
      {disciplines.length === 0 ? (
        <Text c="dimmed">Noch keine Disziplinen angelegt.</Text>
      ) : (
        <Accordion key={mode} variant="separated" multiple>
          {disciplines.map((discipline) => (
            <Accordion.Item key={discipline.id} value={String(discipline.id)}>
              <Accordion.Control>
                <Group gap="xs">
                  <Text fw={500}>{discipline.name}</Text>
                  <Badge size="xs" variant="light">
                    {discipline.metric_type}
                  </Badge>
                </Group>
              </Accordion.Control>
              <Accordion.Panel>
                <Stack gap="sm">
                  {discipline.description && (
                    <Text size="sm" c="dimmed">
                      {discipline.description}
                    </Text>
                  )}
                  {mode === 'manage' ? (
                    <Group justify="flex-end">
                      <DisciplineActions
                        tournamentId={tournamentId}
                        competitionId={competitionId}
                        discipline={discipline}
                        mutateDisciplines={mutateDisciplines}
                      />
                    </Group>
                  ) : (
                    <DisciplineResults
                      key={JSON.stringify([
                        tournamentId,
                        competitionId,
                        discipline.id,
                        discipline.metric_type,
                      ])}
                      tournamentId={tournamentId}
                      competitionId={competitionId}
                      discipline={discipline}
                      teams={teams}
                    />
                  )}
                </Stack>
              </Accordion.Panel>
            </Accordion.Item>
          ))}
        </Accordion>
      )}
      {mode === 'results' && (
        <CompetitionOverallStandings
          tournamentId={tournamentId}
          competitionId={competitionId}
          disciplines={disciplines}
          teams={teams}
          competitionFormat={competitionFormat}
        />
      )}
    </Stack>
  );
}

export default function CompetitionDisciplines({
  tournamentId,
  competitionId,
  teams,
  mode = 'manage',
  competitionFormat = 'STANDARD',
}: DisciplinesProps) {
  const response = getCompetitionDisciplines(tournamentId, competitionId);
  if (response.error)
    return <Alert color="red">Die Disziplinen konnten nicht geladen werden.</Alert>;
  if (!response.data) return <Loader />;
  const disciplines = [...response.data.data].sort(
    (a, b) => a.sort_order - b.sort_order || a.id - b.id,
  );
  function render(teamList: Team[]) {
    return (
      <DisciplineList
        tournamentId={tournamentId}
        competitionId={competitionId}
        disciplines={disciplines}
        teams={teamList}
        mode={mode}
        mutateDisciplines={response.mutate}
        competitionFormat={competitionFormat}
      />
    );
  }
  if (mode === 'results' && teams == null && disciplines.length > 0) {
    return <CompetitionTeams key={tournamentId} tournamentId={tournamentId} render={render} />;
  }
  return render(teams ?? []);
}
