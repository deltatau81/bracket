import { Alert, Button, Card, Loader, Table, Text, Title } from '@mantine/core';
import { useTranslation } from 'react-i18next';

import { TournamentCompetitionFormat, TournamentOverallStanding } from '@openapi';
import { getTournamentOverallStandings } from '@services/adapter';

export function OverallStandingsTable({
  standings,
  competitionFormat,
}: {
  standings: TournamentOverallStanding[];
  competitionFormat: TournamentCompetitionFormat;
}) {
  const { t } = useTranslation();
  if (standings.length === 0) return <Text c="dimmed">{t('overall_standings_empty')}</Text>;
  return (
    <Table.ScrollContainer minWidth={600}>
      <Table withTableBorder striped>
        <Table.Thead>
          <Table.Tr>
            <Table.Th>{t('overall_standings_place')}</Table.Th>
            <Table.Th>
              {t(
                competitionFormat === 'YOUTH_CLUB'
                  ? 'overall_standings_club'
                  : 'overall_standings_team',
              )}
            </Table.Th>
            <Table.Th>{t('overall_standings_hockey_points')}</Table.Th>
            <Table.Th>{t('overall_standings_competition_points')}</Table.Th>
            <Table.Th>{t('overall_standings_total_points')}</Table.Th>
          </Table.Tr>
        </Table.Thead>
        <Table.Tbody>
          {standings.map((standing, index) => {
            const isClub = competitionFormat === 'YOUTH_CLUB' && standing.club_id !== null;
            const id = isClub ? standing.club_id : standing.team_id;
            const name = isClub ? standing.club_name : standing.team_name;
            return (
              <Table.Tr
                key={id === null ? `unknown:${index}` : `${isClub ? 'club' : 'team'}:${id}`}
              >
                <Table.Td>{index + 1}</Table.Td>
                <Table.Td>
                  {name?.trim()
                    ? name
                    : t(
                        isClub
                          ? 'overall_standings_unknown_club'
                          : 'overall_standings_unknown_team',
                        { id: id ?? '?' },
                      )}
                </Table.Td>
                <Table.Td>{standing.game_points}</Table.Td>
                <Table.Td>{standing.competition_points}</Table.Td>
                <Table.Td>{standing.total_points}</Table.Td>
              </Table.Tr>
            );
          })}
        </Table.Tbody>
      </Table>
    </Table.ScrollContainer>
  );
}

export default function CombinedOverallStandings({
  tournamentId,
  competitionFormat,
}: {
  tournamentId: number;
  competitionFormat: TournamentCompetitionFormat;
}) {
  const { t } = useTranslation();
  const response = getTournamentOverallStandings(tournamentId);
  return (
    <Card withBorder padding="md" radius="md">
      <Title order={2} mb="sm">
        {t('overall_standings_title')}
      </Title>
      {response.error && (
        <Alert color="red" mb="sm">
          <Text>{t('overall_standings_error')}</Text>
          <Button
            variant="light"
            mt="xs"
            onClick={() => {
              void response.mutate().catch(() => {
                // SWR exposes retry failures through its error state.
              });
            }}
          >
            {t('overall_standings_retry')}
          </Button>
        </Alert>
      )}
      {response.data ? (
        <OverallStandingsTable
          standings={response.data.data}
          competitionFormat={competitionFormat}
        />
      ) : !response.error ? (
        <Loader aria-label={t('overall_standings_loading')} />
      ) : null}
    </Card>
  );
}
