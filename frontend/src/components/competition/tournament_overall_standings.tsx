import {
  Alert,
  Card,
  Group,
  Image,
  Loader,
  Table,
  Text,
  Title,
} from '@mantine/core';
import React from 'react';

import { TournamentOverallStandingInterface } from '../../interfaces/competition';
import { TeamInterface } from '../../interfaces/team';
import { getBaseApiUrl } from '../../services/adapter';
import { getTournamentOverallStandings } from '../../services/competition';

const pointsFormatter = new Intl.NumberFormat('de-DE', {
  maximumFractionDigits: 2,
});

function TeamLogo({ team }: { team: TeamInterface | undefined }) {
  if (team == null || team.logo_path == null || team.logo_path === '') {
    return null;
  }

  return (
    <Image
      src={`${getBaseApiUrl()}/static/team-logos/${team.logo_path}`}
      alt={`Logo ${team.name}`}
      w={30}
      h={30}
      fit="contain"
      style={{ flexShrink: 0 }}
    />
  );
}

export default function TournamentOverallStandings({
  tournamentId,
  teams = [],
}: {
  tournamentId: number | null;
  teams?: TeamInterface[];
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

  const teamsById = new Map(
    teams.map((team) => [team.id, team])
  );

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
            {standings.map((standing, index) => {
              const team = teamsById.get(standing.team_id);

              return (
                <Table.Tr key={standing.team_id}>
                  <Table.Td>{index + 1}</Table.Td>

                  <Table.Td>
                    <Group gap="xs" wrap="nowrap">
                      <TeamLogo team={team} />
                      <Text component="span">
                        {standing.team_name}
                      </Text>
                    </Group>
                  </Table.Td>

                  <Table.Td ta="right">
                    {pointsFormatter.format(standing.game_points)}
                  </Table.Td>

                  <Table.Td ta="right">
                    {pointsFormatter.format(
                      standing.competition_points
                    )}
                  </Table.Td>

                  <Table.Td ta="right">
                    <Text component="span" fw={700} c="blue">
                      {pointsFormatter.format(
                        standing.total_points
                      )}
                    </Text>
                  </Table.Td>
                </Table.Tr>
              );
            })}
          </Table.Tbody>
        </Table>
      )}
    </Card>
  );
}
