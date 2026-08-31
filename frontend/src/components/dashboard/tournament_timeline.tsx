import { Badge, Card, Center, Group, Stack, Text } from '@mantine/core';
import React from 'react';

import { formatTime } from '../utils/datetime';
import { Translator } from '../utils/types';
import { CompetitionInterface } from '../../interfaces/competition';
import {
  formatMatchInput1,
  formatMatchInput2,
  MatchInterface,
} from '../../interfaces/match';
import { TeamInterface } from '../../interfaces/team';
import CompetitionTimelineItem from '../competition/competition_timeline_item';

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
      <Group justify="space-between" wrap="nowrap">
        <Stack gap={4} style={{ flex: 1 }}>
          <Text fw={500}>{formatMatchInput1(t, stageItemsLookup, matchesLookup, match)}</Text>
          <Text fw={500}>{formatMatchInput2(t, stageItemsLookup, matchesLookup, match)}</Text>
        </Stack>
        <Text fw={800} size="lg" style={{ whiteSpace: 'nowrap' }}>
          {match.status === 'PLANNED'
            ? '– : –'
            : `${match.stage_item_input1_score} : ${match.stage_item_input2_score}`}
        </Text>
      </Group>
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
  const competitionEvents: CompetitionTimelineEvent[] = competitions.map((competition) => ({
    kind: 'competition',
    id: competition.id,
    startTime: competition.start_time,
    competition,
  }));
  const events: TimelineEvent[] = [...matchEvents, ...competitionEvents].sort(
    (first, second) =>
      new Date(first.startTime).getTime() - new Date(second.startTime).getTime() ||
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
