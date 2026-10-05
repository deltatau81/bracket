import { Alert, Card, Loader, Table, Text, Title } from '@mantine/core';

import {
  Club,
  CompetitionDiscipline,
  CompetitionResult,
  CompetitionScoring,
  Team,
  TournamentCompetitionFormat,
} from '@openapi';
import { getClubs, getCompetitionResults, getCompetitionScoring } from '@services/adapter';

type Standing = { id: string; name: string; points: number };

function scoringByPlace(scoring: CompetitionScoring[]): Map<number, number> {
  return new Map(
    scoring.map((item) => {
      const points = item.points.trim() === '' ? NaN : Number(item.points);
      if (!Number.isFinite(points) || points < 0) throw new Error('Invalid scoring points');
      return [item.place, points] as const;
    }),
  );
}

function addDisciplinePoints(
  totals: Map<number, number>,
  results: CompetitionResult[],
  scoring: Map<number, number>,
): Map<number, number> {
  const next = new Map(totals);
  for (const result of results) {
    // This follows the backend standings SQL: stored place -> competition scoring.
    // Results without a stored place have not been evaluated and contribute no points.
    if (result.place == null) continue;
    const points = (next.get(result.team_id) ?? 0) + (scoring.get(result.place) ?? 0);
    if (!Number.isFinite(points)) throw new Error('Invalid competition total');
    next.set(result.team_id, points);
  }
  return next;
}

function buildStandings(
  teams: Team[],
  clubs: Club[],
  totals: Map<number, number>,
  format: TournamentCompetitionFormat,
): Standing[] {
  const clubNames = new Map(clubs.map((club) => [club.id, club.name]));
  const standings = new Map<string, Standing>();
  for (const team of teams) {
    const clubId = format === 'YOUTH_CLUB' ? team.participant_club_id : null;
    const id = clubId == null ? `team:${team.id}` : `club:${clubId}`;
    const name = clubId == null ? team.name : (clubNames.get(clubId) ?? `Verein #${clubId}`);
    const points = (standings.get(id)?.points ?? 0) + (totals.get(team.id) ?? 0);
    if (!Number.isFinite(points)) throw new Error('Invalid competition total');
    standings.set(id, { id, name, points });
  }
  return [...standings.values()].sort(
    (a, b) => b.points - a.points || a.name.localeCompare(b.name, 'de'),
  );
}

function StandingsTable({
  teams,
  clubs,
  totals,
  competitionFormat,
}: {
  teams: Team[];
  clubs: Club[];
  totals: Map<number, number>;
  competitionFormat: TournamentCompetitionFormat;
}) {
  let standings: Standing[];
  try {
    standings = buildStandings(teams, clubs, totals, competitionFormat);
  } catch {
    return <Alert color="red">Die Gesamtwertung enthält ungültige Punktewerte.</Alert>;
  }
  return standings.length === 0 ? (
    <Text c="dimmed">Noch keine Teams vorhanden.</Text>
  ) : (
    <Table.ScrollContainer minWidth={400}>
      <Table withTableBorder>
        <Table.Thead>
          <Table.Tr>
            <Table.Th>Rang</Table.Th>
            <Table.Th>{competitionFormat === 'YOUTH_CLUB' ? 'Verein' : 'Team'}</Table.Th>
            <Table.Th>Punkte</Table.Th>
          </Table.Tr>
        </Table.Thead>
        <Table.Tbody>
          {standings.map((standing, index) => (
            <Table.Tr key={standing.id}>
              <Table.Td>{index + 1}</Table.Td>
              <Table.Td>{standing.name}</Table.Td>
              <Table.Td>{standing.points}</Table.Td>
            </Table.Tr>
          ))}
        </Table.Tbody>
      </Table>
    </Table.ScrollContainer>
  );
}

function ClubStandings({ teams, totals }: { teams: Team[]; totals: Map<number, number> }) {
  const response = getClubs();
  if (response.error)
    return <Alert color="red">Die Vereinsnamen konnten nicht geladen werden.</Alert>;
  if (!response.data) return <Loader size="sm" />;
  return (
    <StandingsTable
      teams={teams}
      clubs={response.data.data}
      totals={totals}
      competitionFormat="YOUTH_CLUB"
    />
  );
}

type StandingsProps = {
  tournamentId: number;
  competitionId: number;
  disciplines: CompetitionDiscipline[];
  teams: Team[];
  competitionFormat: TournamentCompetitionFormat;
};

function DisplayStandings({
  teams,
  totals,
  competitionFormat,
}: {
  teams: Team[];
  totals: Map<number, number>;
  competitionFormat: TournamentCompetitionFormat;
}) {
  return competitionFormat === 'YOUTH_CLUB' ? (
    <ClubStandings teams={teams} totals={totals} />
  ) : (
    <StandingsTable
      teams={teams}
      clubs={[]}
      totals={totals}
      competitionFormat={competitionFormat}
    />
  );
}

function DisciplinePoints({
  tournamentId,
  competitionId,
  discipline,
  remaining,
  teams,
  competitionFormat,
  scoring,
  totals,
}: Omit<StandingsProps, 'disciplines'> & {
  discipline: CompetitionDiscipline;
  remaining: CompetitionDiscipline[];
  scoring: Map<number, number>;
  totals: Map<number, number>;
}) {
  const response = getCompetitionResults(tournamentId, competitionId, discipline.id);
  if (response.error)
    return (
      <Alert color="red">Die Ergebnisse für die Gesamtwertung konnten nicht geladen werden.</Alert>
    );
  if (!response.data) return <Loader size="sm" />;
  let next: Map<number, number>;
  try {
    next = addDisciplinePoints(totals, response.data.data, scoring);
  } catch {
    return <Alert color="red">Die Gesamtwertung enthält ungültige Punktewerte.</Alert>;
  }
  if (remaining.length > 0) {
    return (
      <DisciplinePoints
        key={remaining[0].id}
        tournamentId={tournamentId}
        competitionId={competitionId}
        discipline={remaining[0]}
        remaining={remaining.slice(1)}
        teams={teams}
        competitionFormat={competitionFormat}
        scoring={scoring}
        totals={next}
      />
    );
  }
  return <DisplayStandings teams={teams} totals={next} competitionFormat={competitionFormat} />;
}

export default function CompetitionOverallStandings({
  tournamentId,
  competitionId,
  disciplines,
  teams,
  competitionFormat,
}: StandingsProps) {
  const response = getCompetitionScoring(tournamentId, competitionId);
  let content: React.ReactNode;
  if (response.error) {
    content = (
      <Alert color="red">Das Punkteschema für die Gesamtwertung konnte nicht geladen werden.</Alert>
    );
  } else if (!response.data) {
    content = <Loader size="sm" />;
  } else {
    try {
      const scoring = scoringByPlace(response.data.data);
      content =
        disciplines.length === 0 ? (
          <DisplayStandings
            teams={teams}
            totals={new Map()}
            competitionFormat={competitionFormat}
          />
        ) : (
          <DisciplinePoints
            key={disciplines[0].id}
            tournamentId={tournamentId}
            competitionId={competitionId}
            discipline={disciplines[0]}
            remaining={disciplines.slice(1)}
            teams={teams}
            competitionFormat={competitionFormat}
            scoring={scoring}
            totals={new Map()}
          />
        );
    } catch {
      content = <Alert color="red">Das Punkteschema enthält ungültige Punktewerte.</Alert>;
    }
  }
  return (
    <Card withBorder padding="md" radius="md">
      <Title order={4} mb="sm">
        Competition-Gesamtwertung
      </Title>
      {content}
    </Card>
  );
}
