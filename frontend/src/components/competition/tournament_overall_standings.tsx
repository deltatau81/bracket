import { Alert, Card, Loader, Table, Text, Title } from '@mantine/core';
import React from 'react';

import { TournamentOverallStandingInterface } from '../../interfaces/competition';
import { getTournamentOverallStandings } from '../../services/competition';

const pointsFormatter = new Intl.NumberFormat('de-DE', {
  maximumFractionDigits: 2,
});

export default function TournamentOverallStandings({
  tournamentId,
}: {
  tournamentId: number | null;
}) {
  const swrStandingsResponse = getTournamentOverallStandings(tournamentId);

  if (swrStandingsResponse.error != null) {
    return (
      <Alert color="red" title="Fehler" mt="lg">
        Die Gesamtwertung konnte nicht geladen werden.
      </Alert>
    );
  }

  if (swrStandingsResponse.data == null) {
    return <Loader mt="lg" />;
  }

  const standings: TournamentOverallStandingInterface[] =
    swrStandingsResponse.data.data;

  return (
    <Card withBorder padding="md" radius="md" mt="lg">
      <Title order={3} mb="sm">
        Gesamtwertung
      </Title>
      {standings.length === 0 ? (
        <Text c="dimmed">Noch keine Mannschaften vorhanden.</Text>
      ) : (
        <Table striped highlightOnHover>
          <Table.Thead>
            <Table.Tr>
              <Table.Th>Platz</Table.Th>
              <Table.Th>Mannschaft</Table.Th>
              <Table.Th ta="right">Hockey</Table.Th>
              <Table.Th ta="right">Technik</Table.Th>
              <Table.Th ta="right">Gesamt</Table.Th>
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {standings.map((standing, index) => (
              <Table.Tr key={standing.team_id}>
                <Table.Td>{index + 1}</Table.Td>
                <Table.Td>{standing.team_name}</Table.Td>
                <Table.Td ta="right">
                  {pointsFormatter.format(standing.game_points)}
                </Table.Td>
                <Table.Td ta="right">
                  {pointsFormatter.format(standing.competition_points)}
                </Table.Td>
                <Table.Td ta="right">
                  <Text component="span" fw={700} c="blue">
                    {pointsFormatter.format(standing.total_points)}
                  </Text>
                </Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      )}
    </Card>
  );
}
