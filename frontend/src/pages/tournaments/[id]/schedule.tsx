import { DragDropContext, Draggable, Droppable } from '@hello-pangea/dnd';
import {
  ActionIcon,
  Alert,
  Badge,
  Button,
  Card,
  Grid,
  Group,
  Menu,
  Stack,
  Text,
  Title,
} from '@mantine/core';
import { AiFillWarning } from '@react-icons/all-files/ai/AiFillWarning';
import {
  IconAlertCircle,
  IconCalendarPlus,
  IconDots,
  IconTrash,
  IconTrophy,
} from '@tabler/icons-react';
import { useTranslation } from 'next-i18next';
import { serverSideTranslations } from 'next-i18next/serverSideTranslations';
import React, { useState } from 'react';
import { SWRResponse } from 'swr';

import CourtModal from '../../../components/modals/create_court_modal';
import MatchModal from '../../../components/modals/match_modal';
import { NoContent } from '../../../components/no_content/empty_table_info';
import { Time } from '../../../components/utils/datetime';
import { Translator } from '../../../components/utils/types';
import { getTournamentIdFromRouter, responseIsValid } from '../../../components/utils/util';
import {
  CompetitionDisciplineInterface,
  CompetitionInterface,
} from '../../../interfaces/competition';
import { Court } from '../../../interfaces/court';
import { MatchInterface, formatMatchInput1, formatMatchInput2 } from '../../../interfaces/match';
import { TournamentMinimal } from '../../../interfaces/tournament';
import { getCompetitionDisciplines, getCompetitions, getCourts, getStages } from '../../../services/adapter';
import { deleteCourt } from '../../../services/court';
import {
  getMatchLookup,
  getMatchLookupByCourt,
  getScheduleData,
  getStageItemLookup,
  stringToColour,
} from '../../../services/lookups';
import { rescheduleMatch, scheduleMatches } from '../../../services/match';
import TournamentLayout from '../_tournament_layout';

function CompetitionCard({
  competition,
  tournamentId,
}: {
  competition: CompetitionInterface;
  tournamentId: number;
}) {
  const swrDisciplinesResponse = getCompetitionDisciplines(tournamentId, competition.id);
  const disciplines: CompetitionDisciplineInterface[] = responseIsValid(swrDisciplinesResponse)
    ? swrDisciplinesResponse.data.data
    : [];

  return (
    <Card shadow="sm" padding="lg" radius="md" withBorder mt="md">
      <Grid>
        <Grid.Col span="auto">
          <Group gap="xs">
            <IconTrophy size="1.25rem" />
            <Text fw={700}>{competition.name}</Text>
            <Badge variant="light">Competition</Badge>
          </Group>

          {competition.description != null && competition.description !== '' ? (
            <Text size="sm" c="dimmed" mt="xs">
              {competition.description}
            </Text>
          ) : null}

          {disciplines.length > 0 ? (
            <Stack gap={4} mt="sm">
              {disciplines.map((discipline) => (
                <Group key={discipline.id} gap="xs" justify="space-between" wrap="nowrap">
                  <Text size="sm">{discipline.name}</Text>
                  <Badge size="xs" variant="light">
                    {discipline.metric_type}
                  </Badge>
                </Group>
              ))}
            </Stack>
          ) : null}
        </Grid.Col>

        <Grid.Col span="content">
          <Stack gap="xs" align="end">
            <Badge variant="default" size="lg">
              <Time datetime={competition.start_time} />
            </Badge>
            <Text size="sm" c="dimmed">
              {competition.duration_minutes} Min.
            </Text>
          </Stack>
        </Grid.Col>
      </Grid>
    </Card>
  );
}

function ScheduleRow({
  index,
  match,
  openMatchModal,
  stageItemsLookup,
  matchesLookup,
}: {
  index: number;
  match: MatchInterface;
  openMatchModal: any;
  stageItemsLookup: any;
  matchesLookup: any;
}) {
  const { t } = useTranslation();
  return (
    <Draggable key={match.id} index={index} draggableId={`${match.id}`}>
      {(provided) => (
        <div ref={provided.innerRef} {...provided.draggableProps}>
          <Card
            shadow="sm"
            padding="lg"
            radius="md"
            withBorder
            mt="md"
            onClick={() => {
              openMatchModal(match);
            }}
            {...provided.dragHandleProps}
          >
            <Grid>
              <Grid.Col span="auto">
                <Group gap="xs">
                  {match.stage_item_input1_conflict && <AiFillWarning color="red" />}
                  <Text fw={500}>
                    {formatMatchInput1(t, stageItemsLookup, matchesLookup, match)}
                  </Text>
                </Group>
                <Group gap="xs">
                  {match.stage_item_input2_conflict && <AiFillWarning color="red" />}
                  <Text fw={500}>
                    {formatMatchInput2(t, stageItemsLookup, matchesLookup, match)}
                  </Text>
                </Group>
              </Grid.Col>
              <Grid.Col span="content">
                <Stack gap="xs" align="end">
                  <Badge variant="default" size="lg">
                    {match.start_time != null ? <Time datetime={match.start_time} /> : null}
                  </Badge>
                  <Badge
                    color={stringToColour(`${matchesLookup[match.id].stageItem.id}`)}
                    variant="outline"
                  >
                    {matchesLookup[match.id].stageItem.name}
                  </Badge>
                </Stack>
              </Grid.Col>
            </Grid>
          </Card>
        </div>
      )}
    </Draggable>
  );
}

function ScheduleColumn({
  tournamentId,
  court,
  matches,
  competitions,
  openMatchModal,
  stageItemsLookup,
  swrCourtsResponse,
  matchesLookup,
}: {
  tournamentId: number;
  court: Court;
  matches: MatchInterface[];
  competitions: CompetitionInterface[];
  openMatchModal: any;
  stageItemsLookup: any;
  swrCourtsResponse: SWRResponse;
  matchesLookup: any;
}) {
  const { t } = useTranslation();
  const sortedCompetitions = [...competitions].sort(
    (a, b) => new Date(a.start_time).getTime() - new Date(b.start_time).getTime()
  );
  let competitionIndex = 0;
  const rows: React.ReactNode[] = [];

  matches.forEach((match: MatchInterface, matchIndex: number) => {
    while (
      competitionIndex < sortedCompetitions.length &&
      new Date(sortedCompetitions[competitionIndex].start_time).getTime() <=
        new Date(match.start_time as string).getTime()
    ) {
      const competition = sortedCompetitions[competitionIndex];
      rows.push(
        <CompetitionCard
          key={`competition-${competition.id}`}
          competition={competition}
          tournamentId={tournamentId}
        />
      );
      competitionIndex += 1;
    }

    rows.push(
      <ScheduleRow
        index={matchIndex}
        stageItemsLookup={stageItemsLookup}
        matchesLookup={matchesLookup}
        match={match}
        openMatchModal={openMatchModal}
        key={match.id}
      />
    );
  });

  sortedCompetitions.slice(competitionIndex).forEach((competition) => {
    rows.push(
      <CompetitionCard
        key={`competition-${competition.id}`}
        competition={competition}
        tournamentId={tournamentId}
      />
    );
  });

  const noItemsAlert =
    matches.length < 1 ? (
      <Alert
        icon={<IconAlertCircle size={16} />}
        title={t('no_matches_title')}
        color="gray"
        radius="md"
        mt="1rem"
      >
        {t('drop_match_alert_title')}
      </Alert>
    ) : null;

  return (
    <Droppable droppableId={`${court.id}`} direction="vertical">
      {(provided) => (
        <div {...provided.droppableProps} ref={provided.innerRef}>
          <div style={{ width: '25rem' }}>
            <Group justify="space-between">
              <Group>
                <h4 style={{ marginTop: '0', margin: 'auto' }}>{court.name}</h4>
              </Group>
              <Menu withinPortal position="bottom-end" shadow="sm">
                <Menu.Target>
                  <ActionIcon variant="transparent" color="gray">
                    <IconDots size="1.25rem" />
                  </ActionIcon>
                </Menu.Target>

                <Menu.Dropdown>
                  <Menu.Item
                    leftSection={<IconTrash size="1.5rem" />}
                    onClick={async () => {
                      await deleteCourt(tournamentId, court.id);
                      await swrCourtsResponse.mutate();
                    }}
                    color="red"
                  >
                    {t('delete_court_button')}
                  </Menu.Item>
                </Menu.Dropdown>
              </Menu>
            </Group>
            {rows}
            {noItemsAlert}
            {provided.placeholder}
          </div>
        </div>
      )}
    </Droppable>
  );
}

function Schedule({
  t,
  tournament,
  swrCourtsResponse,
  stageItemsLookup,
  matchesLookup,
  schedule,
  competitions,
  openMatchModal,
}: {
  t: Translator;
  tournament: TournamentMinimal;
  swrCourtsResponse: SWRResponse;
  stageItemsLookup: any;
  matchesLookup: any;
  schedule: { court: Court; matches: MatchInterface[] }[];
  competitions: CompetitionInterface[];
  openMatchModal: CallableFunction;
}) {
  const columns = schedule.map((item) => (
    <ScheduleColumn
      tournamentId={tournament.id}
      swrCourtsResponse={swrCourtsResponse}
      stageItemsLookup={stageItemsLookup}
      matchesLookup={matchesLookup}
      key={item.court.id}
      court={item.court}
      matches={item.matches}
      competitions={competitions.filter((competition) => competition.court_id === item.court.id)}
      openMatchModal={openMatchModal}
    />
  ));

  columns.push(
    <div style={{ width: '25rem' }}>
      <CourtModal
        swrCourtsResponse={swrCourtsResponse}
        tournamentId={tournament.id}
        buttonSize="xs"
      />
    </div>
  );
  if (columns.length < 2) {
    return (
      <Stack align="center">
        <NoContent title={t('no_courts_title')} description={t('no_courts_description')} />
        <CourtModal
          swrCourtsResponse={swrCourtsResponse}
          tournamentId={tournament.id}
          buttonSize="lg"
        />
      </Stack>
    );
  }

  return (
    <Group wrap="nowrap" align="top">
      {columns}
    </Group>
  );
}

export default function SchedulePage() {
  const [modalOpened, modalSetOpened] = useState(false);
  const [match, setMatch] = useState<MatchInterface | null>(null);

  const { t } = useTranslation();
  const { tournamentData } = getTournamentIdFromRouter();
  const swrStagesResponse = getStages(tournamentData.id);
  const swrCourtsResponse = getCourts(tournamentData.id);
  const swrCompetitionsResponse = getCompetitions(tournamentData.id);

  const stageItemsLookup = responseIsValid(swrStagesResponse)
    ? getStageItemLookup(swrStagesResponse)
    : [];
  const matchesLookup = responseIsValid(swrStagesResponse) ? getMatchLookup(swrStagesResponse) : [];
  const matchesByCourtId = responseIsValid(swrStagesResponse)
    ? getMatchLookupByCourt(swrStagesResponse)
    : [];

  const data =
    responseIsValid(swrCourtsResponse) && responseIsValid(swrStagesResponse)
      ? getScheduleData(swrCourtsResponse, matchesByCourtId)
      : [];

  if (!responseIsValid(swrStagesResponse)) return null;
  if (!responseIsValid(swrCourtsResponse)) return null;
  if (!responseIsValid(swrCompetitionsResponse)) return null;

  const competitions: CompetitionInterface[] = swrCompetitionsResponse.data.data;
  const tournamentCompetitions = competitions
    .filter((competition) => competition.court_id == null)
    .sort((a, b) => new Date(a.start_time).getTime() - new Date(b.start_time).getTime());

  function openMatchModal(matchToOpen: MatchInterface) {
    setMatch(matchToOpen);
    modalSetOpened(true);
  }

  return (
    <TournamentLayout tournament_id={tournamentData.id}>
      {match != null ? (
        <MatchModal
          swrStagesResponse={swrStagesResponse}
          swrUpcomingMatchesResponse={null}
          tournamentData={tournamentData}
          match={match}
          opened={modalOpened}
          setOpened={modalSetOpened}
          round={null}
        />
      ) : null}

      <Grid grow>
        <Grid.Col span={6}>
          <Title>{t('planning_title')}</Title>
        </Grid.Col>
        <Grid.Col span={6}>
          {data.length < 1 ? null : (
            <Group justify="right">
              <Button
                color="indigo"
                size="md"
                variant="filled"
                style={{ marginBottom: 10 }}
                leftSection={<IconCalendarPlus size={24} />}
                onClick={async () => {
                  await scheduleMatches(tournamentData.id);
                  await swrStagesResponse.mutate();
                }}
              >
                {t('schedule_description')}
              </Button>
            </Group>
          )}
        </Grid.Col>
      </Grid>
      {tournamentCompetitions.map((competition) => (
        <CompetitionCard
          key={`competition-${competition.id}`}
          competition={competition}
          tournamentId={tournamentData.id}
        />
      ))}
      <Group grow mt="1rem">
        <DragDropContext
          onDragEnd={async ({ destination, source, draggableId: matchId }) => {
            if (destination == null || source == null) return;
            await rescheduleMatch(tournamentData.id, +matchId, {
              old_court_id: +source.droppableId,
              old_position: source.index,
              new_court_id: +destination.droppableId,
              new_position: destination.index,
            });
            await swrStagesResponse.mutate();
          }}
        >
          <Schedule
            t={t}
            tournament={tournamentData}
            swrCourtsResponse={swrCourtsResponse}
            schedule={data}
            competitions={competitions}
            stageItemsLookup={stageItemsLookup}
            matchesLookup={matchesLookup}
            openMatchModal={openMatchModal}
          />
        </DragDropContext>
      </Group>
    </TournamentLayout>
  );
}

export const getServerSideProps = async ({ locale }: { locale: string }) => ({
  props: {
    ...(await serverSideTranslations(locale, ['common'])),
  },
});
