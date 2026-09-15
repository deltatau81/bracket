import {
  Alert,
  Button,
  Checkbox,
  Divider,
  Group,
  Loader,
  Modal,
  Paper,
  ScrollArea,
  Stack,
  Text,
} from '@mantine/core';
import { showNotification } from '@mantine/notifications';
import { AxiosError } from 'axios';
import React, { useEffect, useMemo, useState } from 'react';
import { SWRResponse } from 'swr';

import { Club } from '../../interfaces/club';
import { TeamInterface } from '../../interfaces/team';
import { getClubs, getTeams, handleRequestError } from '../../services/adapter';
import { createYouthSchedule } from '../../services/stage_item';

interface GroupPreview {
  group: string;
  teams: number;
  matches: number;
}

function eligibilityReasons(team: TeamInterface): string[] {
  const reasons: string[] = [];
  if (team.participant_club_id == null) reasons.push('Verein fehlt');
  if (team.pairing_group == null || team.pairing_group.trim() === '') {
    reasons.push('Gruppe fehlt');
  }
  return reasons;
}

function backendErrorMessage(error: AxiosError): string {
  const detail = (error.response?.data as { detail?: unknown } | undefined)?.detail;
  if (Array.isArray(detail)) return detail.map((item) => JSON.stringify(item)).join(', ');
  return detail == null ? error.message : String(detail);
}

export default function CreateYouthScheduleModal({
  tournamentId,
  stageId,
  swrStagesResponse,
  swrAvailableInputsResponse,
  swrRankingsPerStageItemResponse,
}: {
  tournamentId: number;
  stageId: number;
  swrStagesResponse: SWRResponse;
  swrAvailableInputsResponse: SWRResponse;
  swrRankingsPerStageItemResponse: SWRResponse;
}) {
  const [opened, setOpened] = useState(false);
  const [selectedTeamIds, setSelectedTeamIds] = useState<number[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const teamsResponse = getTeams(tournamentId);
  const clubsResponse = getClubs();
  const teams: TeamInterface[] = teamsResponse.data?.data?.teams ?? [];
  const clubs: Club[] = clubsResponse.data?.data ?? [];
  const eligibleTeams = teams.filter((team) => eligibilityReasons(team).length === 0);

  useEffect(() => {
    if (!opened || teamsResponse.data == null) return;
    setSelectedTeamIds(eligibleTeams.map((team) => team.id));
    setError(null);
  }, [opened, teamsResponse.data]);

  const clubNames = useMemo(
    () => Object.fromEntries(clubs.map((club) => [club.id, club.name])),
    [clubsResponse.data]
  );
  const selectedTeams = eligibleTeams.filter((team) => selectedTeamIds.includes(team.id));
  const preview = useMemo(() => {
    const counts = new Map<string, number>();
    selectedTeams.forEach((team) => {
      const group = team.pairing_group as string;
      counts.set(group, (counts.get(group) ?? 0) + 1);
    });
    return Array.from(counts.entries())
      .sort(([left], [right]) => left.localeCompare(right, 'de'))
      .map(([group, teamCount]): GroupPreview => ({
        group,
        teams: teamCount,
        matches: (teamCount * (teamCount - 1)) / 2,
      }));
  }, [selectedTeamIds, teamsResponse.data]);
  const totalMatches = preview.reduce((sum, group) => sum + group.matches, 0);
  const invalidSelection =
    selectedTeamIds.length === 0 || preview.some((group) => group.teams < 2);

  async function generate() {
    setSubmitting(true);
    setError(null);
    try {
      await createYouthSchedule(tournamentId, stageId, selectedTeamIds);
      await Promise.all([
        swrStagesResponse.mutate(),
        swrAvailableInputsResponse.mutate(),
        swrRankingsPerStageItemResponse.mutate(),
      ]);
      showNotification({
        color: 'green',
        title: 'Jugend-Spielplan erstellt',
        message: '',
      });
      setOpened(false);
    } catch (requestError) {
      const axiosError = requestError as AxiosError;
      setError(backendErrorMessage(axiosError));
      handleRequestError(axiosError);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <>
      <Button variant="light" fullWidth onClick={() => setOpened(true)}>
        Jugend-Spielplan erstellen
      </Button>
      <Modal
        opened={opened}
        onClose={() => setOpened(false)}
        title="Jugend-Spielplan erstellen"
        size="lg"
      >
        <Stack gap="sm">
          <Text fw={600}>Teams auswählen</Text>
          <Group gap="xs">
            <Button
              size="xs"
              variant="default"
              onClick={() => setSelectedTeamIds(eligibleTeams.map((team) => team.id))}
            >
              Alle auswählen
            </Button>
            <Button size="xs" variant="default" onClick={() => setSelectedTeamIds([])}>
              Auswahl aufheben
            </Button>
          </Group>

          {teamsResponse.isLoading || clubsResponse.isLoading ? (
            <Loader size="sm" />
          ) : (
            <ScrollArea.Autosize mah={360} type="auto">
              <Stack gap="xs">
                {teams.map((team) => {
                  const reasons = eligibilityReasons(team);
                  const eligible = reasons.length === 0;
                  return (
                    <Paper key={team.id} withBorder p="sm">
                      <Group justify="space-between" align="flex-start" wrap="nowrap">
                        <Checkbox
                          checked={selectedTeamIds.includes(team.id)}
                          disabled={!eligible}
                          onChange={(event) => {
                            setSelectedTeamIds((current) =>
                              event.currentTarget.checked
                                ? [...current, team.id]
                                : current.filter((teamId) => teamId !== team.id)
                            );
                          }}
                          label={team.name}
                        />
                        <Stack gap={0} align="flex-end">
                          <Text size="sm">
                            Verein:{' '}
                            {team.participant_club_id == null
                              ? '-'
                              : clubNames[team.participant_club_id] ??
                                `Verein #${team.participant_club_id}`}
                          </Text>
                          <Text size="sm">Gruppe: {team.pairing_group?.trim() || '-'}</Text>
                          {!eligible ? (
                            <Text size="xs" c="red">
                              {reasons.join(', ')}
                            </Text>
                          ) : null}
                        </Stack>
                      </Group>
                    </Paper>
                  );
                })}
                {teams.length === 0 ? <Text c="dimmed">Keine Teams vorhanden.</Text> : null}
              </Stack>
            </ScrollArea.Autosize>
          )}

          <Divider />
          <Group gap="lg">
            <Text>{selectedTeamIds.length} Teams</Text>
            <Text>{preview.length} Gruppen</Text>
            <Text>{totalMatches} Spiele</Text>
          </Group>
          {preview.map((group) => (
            <Text key={group.group} size="sm" c="dimmed">
              {group.group}: {group.teams} Teams → {group.matches} Spiele
            </Text>
          ))}
          {preview.some((group) => group.teams < 2) ? (
            <Alert color="yellow">Jede ausgewählte Gruppe benötigt mindestens zwei Teams.</Alert>
          ) : null}
          {error != null ? <Alert color="red">{error}</Alert> : null}

          <Group justify="flex-end">
            <Button variant="default" onClick={() => setOpened(false)} disabled={submitting}>
              Abbrechen
            </Button>
            <Button onClick={generate} disabled={invalidSelection} loading={submitting}>
              Spielplan erstellen
            </Button>
          </Group>
        </Stack>
      </Modal>
    </>
  );
}