import { Badge, Center, Pagination, Table, Text } from '@mantine/core';
import { useTranslation } from 'next-i18next';
import React from 'react';
import { SWRResponse } from 'swr';

import { Player } from '../../interfaces/player';
import { TeamInterface } from '../../interfaces/team';
import { TournamentMinimal } from '../../interfaces/tournament';
import { deletePlayer } from '../../services/player';
import DeleteButton from '../buttons/delete';
import PlayerUpdateModal from '../modals/player_update_modal';
import { NoContent } from '../no_content/empty_table_info';
import RequestErrorAlert from '../utils/error_alert';
import { TableSkeletonSingleColumn } from '../utils/skeletons';
import TableLayout, { TableState, ThNotSortable, ThSortable, sortTableEntries } from './table';

export function WinDistributionTitle() {
  const { t } = useTranslation();
  return (
    <>
      <Text span color="teal" inherit>
        {t('win_distribution_text_win')}
      </Text>{' '}
      /{' '}
      <Text span color="orange" inherit>
        {t('win_distribution_text_draws')}
      </Text>{' '}
      /{' '}
      <Text span color="red" inherit>
        {t('win_distribution_text_losses')}
      </Text>
    </>
  );
}

export default function PlayersTable({
  swrPlayersResponse,
  tournamentData,
  tableState,
  playerCount,
  swrTeamsResponse,
}: {
  swrPlayersResponse: SWRResponse;
  tournamentData: TournamentMinimal;
  tableState: TableState;
  playerCount: number;
  swrTeamsResponse: SWRResponse;
}) {
  const { t } = useTranslation();
  const players: Player[] =
    swrPlayersResponse.data != null ? swrPlayersResponse.data.data.players : [];
  const teams: TeamInterface[] =
    swrTeamsResponse.data != null ? swrTeamsResponse.data.data.teams : [];
  const positionLabels = { GK: 'Torhüter', D: 'Verteidiger', F: 'Stürmer' };

  // const minELOScore = Math.min(...players.map((player) => Number(player.elo_score)));
  // const maxELOScore = Math.max(...players.map((player) => Number(player.elo_score)));
  // const maxSwissScore = Math.max(...players.map((player) => Number(player.swiss_score)));

  if (swrPlayersResponse.error || swrTeamsResponse.error) {
    return <RequestErrorAlert error={swrPlayersResponse.error || swrTeamsResponse.error} />;
  }

  if (swrPlayersResponse.isLoading || swrTeamsResponse.isLoading) {
    return <TableSkeletonSingleColumn />;
  }

  const rows = players
    .sort((p1: Player, p2: Player) => sortTableEntries(p1, p2, tableState))
    .map((player) => {
      const team = teams.find((candidate) =>
        candidate.players.some((member) => member.id === player.id)
      );
      const teamPlayer = team?.players.find((member) => member.id === player.id);
      const firstName = player.first_name ?? (player.last_name == null ? player.name : '-');

      return (
        <Table.Tr key={player.id}>
          <Table.Td>
            <Text>{teamPlayer?.number ?? '-'}</Text>
          </Table.Td>
          <Table.Td>
            <Text>{firstName}</Text>
          </Table.Td>
          <Table.Td>
            <Text>{player.last_name ?? '-'}</Text>
          </Table.Td>
          <Table.Td>
            <Text>{team?.name ?? '-'}</Text>
          </Table.Td>
          <Table.Td>
            <Text>{teamPlayer?.position == null ? '-' : positionLabels[teamPlayer.position]}</Text>
          </Table.Td>
          <Table.Td>
            {player.active ? (
              <Badge color="green">{t('active')}</Badge>
            ) : (
              <Badge color="red">{t('inactive')}</Badge>
            )}
          </Table.Td>
          <Table.Td>
            <PlayerUpdateModal
              swrPlayersResponse={swrPlayersResponse}
              tournament_id={tournamentData.id}
              player={player}
              swrTeamsResponse={swrTeamsResponse}
              teams={teams}
              team={team ?? null}
            />
            <DeleteButton
              onClick={async () => {
                await deletePlayer(tournamentData.id, player.id);
                await swrPlayersResponse.mutate();
                await swrTeamsResponse.mutate();
              }}
              title={t('delete_player_button')}
            />
          </Table.Td>
        </Table.Tr>
      );
    });

  if (rows.length < 1) return <NoContent title={t('no_players_title')} />;

  return (
    <>
      <TableLayout miw={900}>
        <Table.Thead>
          <Table.Tr>
            <ThNotSortable>Nr.</ThNotSortable>
            <ThSortable state={tableState} field="name">
              Vorname
            </ThSortable>
            <ThNotSortable>Nachname</ThNotSortable>
            <ThNotSortable>Mannschaft</ThNotSortable>
            <ThNotSortable>Position</ThNotSortable>
            <ThSortable state={tableState} field="active">
              Aktiv
            </ThSortable>
            <ThNotSortable>{null}</ThNotSortable>
          </Table.Tr>
        </Table.Thead>
        <Table.Tbody>{rows}</Table.Tbody>
      </TableLayout>
      <Center mt="1rem">
        <Pagination
          value={tableState.page}
          onChange={tableState.setPage}
          total={1 + playerCount / tableState.pageSize}
          size="lg"
        />
      </Center>
    </>
  );
}
