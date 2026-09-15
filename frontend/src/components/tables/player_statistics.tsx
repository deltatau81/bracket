import { Table } from '@mantine/core';
import { useTranslation } from 'next-i18next';
import { SWRResponse } from 'swr';

import { PlayerStatistics } from '../../interfaces/player_statistics';
import { EmptyTableInfo } from '../no_content/empty_table_info';
import RequestErrorAlert from '../utils/error_alert';
import { TableSkeletonSingleColumn } from '../utils/skeletons';
import TableLayout, { ThNotSortable } from './table';

const placeholder = '-';

export default function PlayerStatisticsTable({ response }: { response: SWRResponse }) {
  const { t } = useTranslation();

  if (response.error) return <RequestErrorAlert error={response.error} />;
  if (response.isLoading) return <TableSkeletonSingleColumn />;

  const statistics: PlayerStatistics[] = response.data?.data ?? [];
  if (statistics.length === 0) {
    return <EmptyTableInfo entity_name={t('players_title')} />;
  }

  return (
    <TableLayout miw={760}>
      <Table.Thead>
        <Table.Tr>
          <ThNotSortable>{t('ranking_title')}</ThNotSortable>
          <ThNotSortable>{t('players_title')}</ThNotSortable>
          <ThNotSortable>{t('teams_title')}</ThNotSortable>
          <ThNotSortable>#</ThNotSortable>
          <ThNotSortable>Pos</ThNotSortable>
          <ThNotSortable>G</ThNotSortable>
          <ThNotSortable>A</ThNotSortable>
          <ThNotSortable>Pts</ThNotSortable>
          <ThNotSortable>PIM</ThNotSortable>
        </Table.Tr>
      </Table.Thead>
      <Table.Tbody>
        {statistics.map((player, index) => (
          <Table.Tr key={player.player_id}>
            <Table.Td>{index + 1}</Table.Td>
            <Table.Td>{player.player_name}</Table.Td>
            <Table.Td>{player.team_name ?? placeholder}</Table.Td>
            <Table.Td>{player.jersey_number ?? placeholder}</Table.Td>
            <Table.Td>{player.position ?? placeholder}</Table.Td>
            <Table.Td>{player.goals}</Table.Td>
            <Table.Td>{player.assists}</Table.Td>
            <Table.Td fw={700}>{player.points}</Table.Td>
            <Table.Td>{player.penalty_minutes}</Table.Td>
          </Table.Tr>
        ))}
      </Table.Tbody>
    </TableLayout>
  );
}
