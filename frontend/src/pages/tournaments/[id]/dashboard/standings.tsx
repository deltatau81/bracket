import { Container, Text, Title } from '@mantine/core';
import { AiOutlineHourglass } from '@react-icons/all-files/ai/AiOutlineHourglass';
import { useTranslation } from 'next-i18next';
import { serverSideTranslations } from 'next-i18next/serverSideTranslations';
import Head from 'next/head';
import React from 'react';
import { SWRResponse } from 'swr';

import NotFoundTitle from '../../../404';
import TournamentOverallStandings from '../../../../components/competition/tournament_overall_standings';
import { DashboardFooter } from '../../../../components/dashboard/footer';
import { DoubleHeader, TournamentHeadTitle } from '../../../../components/dashboard/layout';
import { NoContent } from '../../../../components/no_content/empty_table_info';
import { StandingsTableForStageItem } from '../../../../components/tables/standings';
import PlayerStatisticsTable from '../../../../components/tables/player_statistics';
import { TableSkeletonTwoColumns } from '../../../../components/utils/skeletons';
import { responseIsValid } from '../../../../components/utils/util';
import { getPlayerStatistics, getStagesLive } from '../../../../services/adapter';
import { getStageItemLookup, getStageItemTeamsLookup } from '../../../../services/lookups';
import { getTournamentResponseByEndpointName } from '../../../../services/tournament';

export function StandingsContent({
  swrStagesResponse,
  fontSizeInPixels,
  maxTeamsToDisplay,
}: {
  swrStagesResponse: SWRResponse;
  fontSizeInPixels: number;
  maxTeamsToDisplay: number;
}) {
  const { t } = useTranslation();

  const stageItemsLookup = getStageItemLookup(swrStagesResponse);
  const stageItemTeamLookup = responseIsValid(swrStagesResponse)
    ? getStageItemTeamsLookup(swrStagesResponse)
    : {};

  const rows = Object.keys(stageItemTeamLookup)
    .filter((stageItemId) => stageItemsLookup[stageItemId] != null)
    .sort((si1: any, si2: any) =>
      stageItemsLookup[si1].name > stageItemsLookup[si2].name ? 1 : -1
    )
    .map((stageItemId) => (
      <div key={stageItemId}>
        <Text size="xl" mt="md" mb="xs" inherit>
          {stageItemsLookup[stageItemId].name}
        </Text>
        <StandingsTableForStageItem
          teams_with_inputs={stageItemTeamLookup[stageItemId]}
          stageItem={stageItemsLookup[stageItemId]}
          stageItemsLookup={stageItemsLookup}
          fontSizeInPixels={fontSizeInPixels}
          maxTeamsToDisplay={maxTeamsToDisplay}
        />
      </div>
    ));

  if (rows.length < 1) {
    return (
      <NoContent
        title={`${t('could_not_find_any_alert')} ${t('teams_title')}`}
        description=""
        icon={<AiOutlineHourglass />}
      />
    );
  }
  return rows;
}

export default function Standings() {
  const { t } = useTranslation();
  const tournamentResponse = getTournamentResponseByEndpointName();

  const tournamentDataFull = tournamentResponse ? tournamentResponse[0] : null;

  const notFound = tournamentDataFull == null;
  const tournamentId = !notFound ? tournamentDataFull.id : null;

  const swrStagesResponse = getStagesLive(tournamentId);
  const playerStatisticsResponse = getPlayerStatistics(tournamentId);

  if (!tournamentResponse) {
    return <TableSkeletonTwoColumns />;
  }

  if (swrStagesResponse.isLoading) {
    return <TableSkeletonTwoColumns />;
  }

  if (notFound) {
    return <NotFoundTitle />;
  }

  return (
    <>
      <Head>
        <TournamentHeadTitle tournamentDataFull={tournamentDataFull} />
      </Head>
      <DoubleHeader tournamentData={tournamentDataFull} />
      <Container mt="1rem" px="0rem">
        <Container style={{ width: '100%' }} px="sm">
          <StandingsContent
            swrStagesResponse={swrStagesResponse}
            fontSizeInPixels={16}
            maxTeamsToDisplay={100}
          />
          <TournamentOverallStandings tournamentId={tournamentId} />
          <Title order={2} mt="xl" mb="sm">
            {t('players_title')} – {t('ranking_title')}
          </Title>
          <PlayerStatisticsTable response={playerStatisticsResponse} />
        </Container>
      </Container>
      <DashboardFooter />
    </>
  );
}

export const getServerSideProps = async ({ locale }: { locale: string }) => ({
  props: {
    ...(await serverSideTranslations(locale, ['common'])),
  },
});
