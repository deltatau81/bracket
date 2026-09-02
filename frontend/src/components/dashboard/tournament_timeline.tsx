import { Badge, Card, Center, Group, Image, Stack, Text } from '@mantine/core';
import React from 'react';

import { CompetitionInterface } from '../../interfaces/competition';
import {
  formatMatchInput1,
  formatMatchInput2,
  MatchInterface,
} from '../../interfaces/match';
import { TeamInterface } from '../../interfaces/team';
import { getBaseApiUrl } from '../../services/adapter';
import CompetitionTimelineItem from '../competition/competition_timeline_item';
import { formatTime } from '../utils/datetime';
import { Translator } from '../utils/types';

interface MatchTimelineEvent {
  kind: 'match';
  id: number;
  startTime: string;
  match: MatchInterface;
  stageItem: { id: number; name: string };
}

interface CompetitionTimelineEvent {
  kind: 'competition';
  id: number;
  startTime: string;
  competition: CompetitionInterface;
}

type TimelineEvent = MatchTimelineEvent | CompetitionTimelineEvent;

function TeamLogo({ team }: { team: TeamInterface | null | undefined }) {
  if (team == null || team.logo_path == null || team.logo_path === '') {
    return null;
  }

  return (
    <Image
      src={`${getBaseApiUrl()}/static/team-logos/${team.logo_path}`}
      alt={`Logo ${team.name}`}
      w={32}
      h={32}
      fit="contain"
      style={{ flexShrink: 0 }}
    />
  );
}

function MatchTeamRow({
  team,
  name,
}: {
  team: TeamInterface | null | undefined;
  name: string;
}) {
  return (
    <Group gap="sm" wrap="nowrap">
      <TeamLogo team={team} />
      <Text fw={500}>{name}</Text>
    </Group>
  );
}

function segmentPoints(score1: number, score2: number, winPoints: number, drawPoints: number) {
  if (score1 > score2) {
    return [winPoints, 0];
  }

  if (score2 > score1) {
    return [0, winPoints];
  }

  return [drawPoints, drawPoints];
}

function getGamePoints(match: MatchInterface) {
  const half1 = segmentPoints(
    match.stage_item_input1_half1_score,
    match.stage_item_input2_half1_score,
    2,
    1
  );

  const half2 = segmentPoints(
    match.stage_item_input1_half2_score,
    match.stage_item_input2_half2_score,
    2,
    1
  );

  const penalty = segmentPoints(
    match.stage_item_input1_penalty_score,
    match.stage_item_input2_penalty_score,
    1,
    0.5
  );

  return [
    half1[0] + half2[0] + penalty[0],
    half1[1] + half2[1] + penalty[1],
  ];
}

function formatPoints(points: number) {
  return Number.isInteger(points) ? `${points}` : points.toFixed(1).replace('.', ',');
}

function ScoreRow({
  label,
  score1,
  score2,
  bold = false,
}: {
  label: string;
  score1: number | string;
  score2: number | string;
  bold?: boolean;
}) {
  return (
    <Group justify="space-between" gap="md" wrap="nowrap">
      <Text size="sm" c={bold ? undefined : 'dimmed'} fw={bold ? 700 : 400}>
        {label}
      </Text>

      <Text
        size="sm"
        fw={bold ? 800 : 600}
        style={{
          minWidth: '4.5rem',
          textAlign: 'right',
          whiteSpace: 'nowrap',
        }}
      >
        {score1} : {score2}
      </Text>
    </Group>
  );
}

function MatchTimelineItem({
  event,
  t,
  stageItemsLookup,
  matchesLookup,
}: {
  event: MatchTimelineEvent;
  t: Translator;
  stageItemsLookup: any;
  matchesLookup: any;
}) {
  const { match } = event;

  const status = {
    PLANNED: { label: 'Geplant', color: 'gray' },
    RUNNING: { label: 'Läuft', color: 'orange' },
    FINISHED: { label: 'Beendet', color: 'green' },
  }[match.status];

  const team1Name = formatMatchInput1(
    t,
    stageItemsLookup,
    matchesLookup,
    match
  );

  const team2Name = formatMatchInput2(
    t,
    stageItemsLookup,
    matchesLookup,
    match
  );

  const gamePoints = getGamePoints(match);
  const showScores = match.status !== 'PLANNED';

  return (
    <Card withBorder radius="md" padding="md">
      <Group justify="space-between" align="flex-start" mb="sm">
        <div>
          <Badge variant="light">Hockeyspiel</Badge>

          {match.court != null ? (
            <Text size="sm" c="dimmed" mt={4}>
              {match.court.name}
            </Text>
          ) : null}
        </div>

        <Group gap="xs">
          <Badge color={status.color} variant="light">
            {status.label}
          </Badge>

          <Badge variant="outline">{event.stageItem.name}</Badge>
        </Group>
      </Group>

      <Stack gap="sm">
        <MatchTeamRow
          team={match.stage_item_input1?.team}
          name={team1Name}
        />

        <MatchTeamRow
          team={match.stage_item_input2?.team}
          name={team2Name}
        />
      </Stack>

      <Card
        withBorder
        radius="sm"
        padding="sm"
        mt="md"
        style={{ backgroundColor: 'var(--mantine-color-default-hover)' }}
      >
        {showScores ? (
          <Stack gap={5}>
            <ScoreRow
              label="1. Halbzeit"
              score1={match.stage_item_input1_half1_score}
              score2={match.stage_item_input2_half1_score}
            />

            <ScoreRow
              label="2. Halbzeit"
              score1={match.stage_item_input1_half2_score}
              score2={match.stage_item_input2_half2_score}
            />

            <ScoreRow
              label="Penalty"
              score1={match.stage_item_input1_penalty_score}
              score2={match.stage_item_input2_penalty_score}
            />

            <div
              style={{
                borderTop: '1px solid var(--mantine-color-default-border)',
                marginTop: '0.25rem',
                paddingTop: '0.35rem',
              }}
            >
              <Stack gap={5}>
                <ScoreRow
                  label="Gesamttore"
                  score1={match.stage_item_input1_score}
                  score2={match.stage_item_input2_score}
                  bold
                />

                <ScoreRow
                  label="Spielpunkte"
                  score1={formatPoints(gamePoints[0])}
                  score2={formatPoints(gamePoints[1])}
                  bold
                />
              </Stack>
            </div>
          </Stack>
        ) : (
          <Center>
            <Text fw={800}>– : –</Text>
          </Center>
        )}
      </Card>
    </Card>
  );
}

export default function TournamentTimeline({
  tournamentId,
  t,
  competitions,
  teams,
  matchesLookup,
  stageItemsLookup,
}: {
  tournamentId: number;
  t: Translator;
  competitions: CompetitionInterface[];
  teams: TeamInterface[];
  matchesLookup: any;
  stageItemsLookup: any;
}) {
  const matchEvents: MatchTimelineEvent[] = Object.values(matchesLookup)
    .map((data: any) => ({
      kind: 'match' as const,
      id: data.match.id,
      startTime: data.match.start_time,
      match: data.match,
      stageItem: data.stageItem,
    }))
    .filter((event) => event.startTime != null);

  const competitionEvents: CompetitionTimelineEvent[] = competitions.map(
    (competition) => ({
      kind: 'competition',
      id: competition.id,
      startTime: competition.start_time,
      competition,
    })
  );

  const events: TimelineEvent[] = [...matchEvents, ...competitionEvents].sort(
    (first, second) =>
      new Date(first.startTime).getTime() -
        new Date(second.startTime).getTime() ||
      first.kind.localeCompare(second.kind) ||
      first.id - second.id
  );

  if (events.length === 0) {
    return <Text c="dimmed">Noch keine Programmpunkte geplant.</Text>;
  }

  return (
    <Stack gap="md">
      {events.map((event) => (
        <React.Fragment key={`${event.kind}-${event.id}`}>
          <Center>
            <Text fw={800} size="lg">
              {formatTime(event.startTime)}
            </Text>
          </Center>

          {event.kind === 'match' ? (
            <MatchTimelineItem
              event={event}
              t={t}
              stageItemsLookup={stageItemsLookup}
              matchesLookup={matchesLookup}
            />
          ) : (
            <CompetitionTimelineItem
              tournamentId={tournamentId}
              competition={event.competition}
              teams={teams}
            />
          )}
        </React.Fragment>
      ))}
    </Stack>
  );
}
