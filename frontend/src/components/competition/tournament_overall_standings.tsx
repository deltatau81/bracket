import {
  Alert,
  Box,
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
                <Box style={{ width: '100%', overflow: 'hidden' }}>
          <Table
            striped
            highlightOnHover
            style={{
              width: '100%',
              tableLayout: 'fixed',
            }}
          >
            <Table.Thead>
              <Table.Tr>
                <Table.Th
                  style={{
                    width: '3.5rem',
                    paddingLeft: '0.5rem',
                    paddingRight: '0.25rem',
                    whiteSpace: 'nowrap',
                  }}
                >
                  Platz
                </Table.Th>

                <Table.Th
                  style={{
                    width: 'auto',
                    paddingLeft: '0.25rem',
                    paddingRight: '0.25rem',
                  }}
                >
                  Mannschaft
                </Table.Th>

                <Table.Th
                  ta="right"
                  style={{
                    width: '4rem',
                    paddingLeft: '0.25rem',
                    paddingRight: '0.25rem',
                    whiteSpace: 'nowrap',
                  }}
                >
                  Hockey
                </Table.Th>

                <Table.Th
                  ta="right"
                  style={{
                    width: '4rem',
                    paddingLeft: '0.25rem',
                    paddingRight: '0.25rem',
                    whiteSpace: 'nowrap',
                  }}
                >
                  Technik
                </Table.Th>

                <Table.Th
                  ta="right"
                  style={{
                    width: '4.25rem',
                    paddingLeft: '0.25rem',
                    paddingRight: '0.5rem',
                    whiteSpace: 'nowrap',
                  }}
                >
                  Gesamt
                </Table.Th>
              </Table.Tr>
            </Table.Thead>

            <Table.Tbody>
              {standings.map((standing, index) => {
                const team = teamsById.get(standing.team_id);

                return (
                  <Table.Tr key={standing.team_id}>
                    <Table.Td
                      style={{
                        paddingLeft: '0.5rem',
                        paddingRight: '0.25rem',
                        whiteSpace: 'nowrap',
                      }}
                    >
                      {index + 1}
                    </Table.Td>

                    <Table.Td
                      style={{
                        paddingLeft: '0.25rem',
                        paddingRight: '0.25rem',
                      }}
                    >
                      <Group
                        gap="xs"
                        wrap="nowrap"
                        align="center"
                        style={{ minWidth: 0 }}
                      >
                        <TeamLogo team={team} />

                        <Text
                          component="span"
                          style={{
                            minWidth: 0,
                            overflowWrap: 'break-word',
                          }}
                        >
                          {standing.team_name}
                        </Text>
                      </Group>
                    </Table.Td>

                    <Table.Td
                      ta="right"
                      style={{
                        paddingLeft: '0.25rem',
                        paddingRight: '0.25rem',
                        whiteSpace: 'nowrap',
                      }}
                    >
                      {pointsFormatter.format(
                        standing.game_points
                      )}
                    </Table.Td>

                    <Table.Td
                      ta="right"
                      style={{
                        paddingLeft: '0.25rem',
                        paddingRight: '0.25rem',
                        whiteSpace: 'nowrap',
                      }}
                    >
                      {pointsFormatter.format(
                        standing.competition_points
                      )}
                    </Table.Td>

                    <Table.Td
                      ta="right"
                      style={{
                        paddingLeft: '0.25rem',
                        paddingRight: '0.5rem',
                        whiteSpace: 'nowrap',
                      }}
                    >
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
        </Box>
      )}
    </Card>
  );
}