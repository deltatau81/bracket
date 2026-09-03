import { Grid, Title } from '@mantine/core';
import { useTranslation } from 'next-i18next';
import { serverSideTranslations } from 'next-i18next/serverSideTranslations';
import React from 'react';

import PlayerCreateModal from '../../../components/modals/player_create_modal';
import PlayersTable from '../../../components/tables/players';
import { getTableState, tableStateToPagination } from '../../../components/tables/table';
import { capitalize, getTournamentIdFromRouter } from '../../../components/utils/util';
import { TeamInterface } from '../../../interfaces/team';
import { getPlayersPaginated, getTeams } from '../../../services/adapter';
import TournamentLayout from '../_tournament_layout';

export default function Players() {
  const tableState = getTableState('name');
  const { tournamentData } = getTournamentIdFromRouter();
  const swrPlayersResponse = getPlayersPaginated(
    tournamentData.id,
    tableStateToPagination(tableState)
  );
  const swrTeamsResponse = getTeams(tournamentData.id);
  const teams: TeamInterface[] =
    swrTeamsResponse.data != null ? swrTeamsResponse.data.data.teams : [];
  const playerCount = swrPlayersResponse.data != null ? swrPlayersResponse.data.data.count : 1;
  const { t } = useTranslation();
  return (
    <TournamentLayout tournament_id={tournamentData.id}>
      <Grid justify="space-between">
        <Grid.Col span="auto">
          <Title>{capitalize(t('players_title'))}</Title>
        </Grid.Col>
        <Grid.Col span="content">
          <PlayerCreateModal
            swrPlayersResponse={swrPlayersResponse}
            swrTeamsResponse={swrTeamsResponse}
            tournament_id={tournamentData.id}
            teams={teams}
          />
        </Grid.Col>
      </Grid>
      <PlayersTable
        playerCount={playerCount}
        swrPlayersResponse={swrPlayersResponse}
        tournamentData={tournamentData}
        tableState={tableState}
        swrTeamsResponse={swrTeamsResponse}
      />
    </TournamentLayout>
  );
}

export const getServerSideProps = async ({ locale }: { locale: string }) => ({
  props: {
    ...(await serverSideTranslations(locale, ['common'])),
  },
});
