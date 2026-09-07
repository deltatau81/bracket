import {
  ActionIcon,
  Badge,
  Button,
  Divider,
  Group,
  NumberInput,
  Paper,
  Select,
  Stack,
  Text,
  TextInput,
} from '@mantine/core';
import { IconPencil, IconTrash, IconX } from '@tabler/icons-react';
import React, { useMemo, useState } from 'react';

import { MatchInterface, MatchPeriod, MatchPhaseState, MatchStatus } from '../interfaces/match';
import {
  formatGameTime,
  formatPenaltyDetails,
  MATCH_PERIOD_LABELS,
} from './match_event_utils';
import {
  MatchEvent,
  MatchEventBody,
  MatchEventType,
  PenaltyDefinition,
  PenaltyType,
} from '../interfaces/match_event';
import { TeamInterface } from '../interfaces/team';
import { HockeyMode } from '../interfaces/tournament';
import { getTeams } from '../services/adapter';
import {
  createMatchEvent,
  deleteMatchEvent,
  getMatchEvents,
  getPenaltyCatalog,
  updateMatchEvent,
} from '../services/match_event';

function parseGameTime(value: string): number | null {
  const match = /^(\d+):([0-5]\d)$/.exec(value.trim());
  if (match == null) return null;
  return Number(match[1]) * 60 + Number(match[2]);
}


function sortPenalties(penalties: PenaltyDefinition[]): PenaltyDefinition[] {
  return [...penalties].sort((a, b) => a.label.localeCompare(b.label, 'de'));
}

function phaseLabel(
  status: MatchStatus,
  period: MatchPeriod | null,
  phaseState: MatchPhaseState | null
): string {
  if (status === 'FINISHED') return 'Spiel beendet';
  if (status === 'PLANNED') return 'Spiel geplant';
  if (period == null || phaseState == null) return 'Spielphase unbekannt';
  if (phaseState === 'BREAK') return 'Pause';
  return MATCH_PERIOD_LABELS[period];
}

function eventBody(
  event: MatchEvent,
  teamId: number,
  playerId: number | null,
  playerNumber: number | null,
  period: MatchPeriod,
  gameTimeSeconds: number,
  penaltyCode: string | null,
  penaltyType: PenaltyType | null,
  penaltyMinutes: number | null,
  infraction: string
): MatchEventBody {
  return {
    team_id: teamId,
    event_type: event.event_type,
    period,
    game_time_seconds: gameTimeSeconds,
    player_id: playerId,
    player_number: playerNumber,
    player_name: playerId == null ? null : event.player_name,
    assist1_player_id: event.assist1_player_id,
    assist1_number: event.assist1_number,
    assist1_name: event.assist1_name,
    assist2_player_id: event.assist2_player_id,
    assist2_number: event.assist2_number,
    assist2_name: event.assist2_name,
    penalty_code: event.event_type === 'PENALTY' ? penaltyCode : null,
    penalty_rule: event.penalty_rule,
    penalty_type: event.event_type === 'PENALTY' ? penaltyType : null,
    penalty_minutes: event.event_type === 'PENALTY' ? penaltyMinutes : null,
    infraction: event.event_type === 'PENALTY' ? infraction || null : null,
    game_misconduct: event.game_misconduct,
    sort_order: event.sort_order,
  };
}

export default function MatchEvents({
  tournamentId,
  hockeyMode,
  match,
  status,
  activePeriod,
  phaseState,
  refreshMatch,
  onGoalMutation,
}: {
  tournamentId: number;
  hockeyMode: HockeyMode;
  match: MatchInterface;
  status: MatchStatus;
  activePeriod: MatchPeriod | null;
  phaseState: MatchPhaseState | null;
  refreshMatch: () => Promise<unknown>;
  onGoalMutation: (oldEvent: MatchEvent | null, newEvent: MatchEvent | null) => void;
}) {
  const eventResponse = getMatchEvents(tournamentId, match.id);
  const penaltyCatalogResponse = getPenaltyCatalog(tournamentId, match.id);
  const teamsResponse = getTeams(tournamentId);
  const events = eventResponse.data?.data ?? [];
  const teams: TeamInterface[] = teamsResponse.data?.data?.teams ?? [];
  const participantIds = [match.stage_item_input1?.team_id, match.stage_item_input2?.team_id].filter(
    (teamId): teamId is number => teamId != null
  );
  const participants = teams.filter((team) => participantIds.includes(team.id));
  const teamById = Object.fromEntries(participants.map((team) => [team.id, team]));

  const [eventType, setEventType] = useState<MatchEventType>('GOAL');
  const [teamId, setTeamId] = useState<string | null>(null);
  const [playerNumber, setPlayerNumber] = useState<number | string>('');
  const [playerId, setPlayerId] = useState<string | null>(null);
  const [gameTime, setGameTime] = useState('');
  const [penaltyCode, setPenaltyCode] = useState<string | null>(null);
  const [penaltyType, setPenaltyType] = useState<PenaltyType | null>(null);
  const [penaltyMinutes, setPenaltyMinutes] = useState<number | string>('');
  const [infraction, setInfraction] = useState('');
  const [validationError, setValidationError] = useState<string | null>(null);
  const [editing, setEditing] = useState<MatchEvent | null>(null);
  const [editTeamId, setEditTeamId] = useState<string | null>(null);
  const [editPlayerId, setEditPlayerId] = useState<string | null>(null);
  const [editPlayerNumber, setEditPlayerNumber] = useState<number | string>('');
  const [editPeriod, setEditPeriod] = useState<MatchPeriod | null>(null);
  const [editGameTime, setEditGameTime] = useState('');
  const [editPenaltyCode, setEditPenaltyCode] = useState<string | null>(null);
  const [editPenaltyType, setEditPenaltyType] = useState<PenaltyType | null>(null);
  const [editPenaltyMinutes, setEditPenaltyMinutes] = useState<number | string>('');
  const [editInfraction, setEditInfraction] = useState('');
  const [editError, setEditError] = useState<string | null>(null);

  const catalog = penaltyCatalogResponse.data?.data;
  const penalties = sortPenalties(catalog?.penalties ?? []);
  const penaltyTypes = catalog?.penalty_types ?? [];
  const selectedPenalty = penalties.find((penalty) => penalty.code === penaltyCode);
  const selectedEditPenalty = penalties.find((penalty) => penalty.code === editPenaltyCode);
  const typeOptions = (selectedPenalty?.allowed_penalty_types ?? []).map((type) => ({
    value: type,
    label: penaltyTypes.find((definition) => definition.type === type)?.label ?? type,
  }));
  const editTypeOptions = (selectedEditPenalty?.allowed_penalty_types ?? []).map((type) => ({
    value: type,
    label: penaltyTypes.find((definition) => definition.type === type)?.label ?? type,
  }));
  const canCreate = status === 'RUNNING' && phaseState === 'ACTIVE' && activePeriod != null;
  const selectedTeam = teamId == null ? null : teamById[Number(teamId)];
  const editTeam = editTeamId == null ? null : teamById[Number(editTeamId)];
  const periodOptions = useMemo(
    () =>
      (hockeyMode === 'COMPETITION'
        ? (['HALF1', 'HALF2', 'SHOOTOUT'] as MatchPeriod[])
        : (['PERIOD1', 'PERIOD2', 'PERIOD3', 'OVERTIME'] as MatchPeriod[])
      ).map((period) => ({ value: period, label: MATCH_PERIOD_LABELS[period] })),
    [hockeyMode]
  );

  const teamOptions = participants.map((team) => ({ value: `${team.id}`, label: team.name }));
  const playerOptions = (selectedTeam?.players ?? []).map((player) => ({
    value: `${player.id}`,
    label: `${player.number == null ? '' : `#${player.number} `}${player.name}`,
  }));
  const editPlayerOptions = (editTeam?.players ?? []).map((player) => ({
    value: `${player.id}`,
    label: `${player.number == null ? '' : `#${player.number} `}${player.name}`,
  }));

  async function refreshAfterMutation() {
    await eventResponse.mutate();
    await refreshMatch();
  }

  async function submitEvent() {
    const seconds = parseGameTime(gameTime);
    if (teamId == null) {
      setValidationError('Bitte ein Team ausw\u00e4hlen.');
      return;
    }
    if (seconds == null) {
      setValidationError('Spielzeit im Format MM:SS eingeben (Sekunden 00\u201359).');
      return;
    }
    if (activePeriod == null) return;
    if (eventType === 'PENALTY' && (penaltyCode == null || penaltyType == null)) {
      setValidationError('Bitte Vergehen und Strafe auswählen.');
      return;
    }
    if (eventType === 'PENALTY' && penaltyCode === 'OTHER' && infraction.trim() === '') {
      setValidationError('Bitte das Vergehen angeben.');
      return;
    }

    const response = await createMatchEvent(tournamentId, match.id, activePeriod, {
      team_id: Number(teamId),
      event_type: eventType,
      game_time_seconds: seconds,
      player_id: playerId == null ? null : Number(playerId),
      player_number: playerNumber === '' ? null : Number(playerNumber),
      penalty_code: eventType === 'PENALTY' ? penaltyCode : null,
      penalty_type: eventType === 'PENALTY' ? penaltyType : null,
      penalty_minutes:
        eventType === 'PENALTY' &&
        penaltyType === 'CUSTOM' &&
        penaltyMinutes !== ''
          ? Number(penaltyMinutes)
          : null,
      infraction:
        eventType === 'PENALTY' && penaltyCode === 'OTHER' ? infraction || null : null,
    });
    await refreshAfterMutation();
    if (response == null) return;
    onGoalMutation(null, response.data.data);

    setGameTime('');
    setPlayerId(null);
    setPlayerNumber('');
    setPenaltyCode(null);
    setPenaltyType(null);
    setPenaltyMinutes('');
    setInfraction('');
    setValidationError(null);
  }

  function beginEdit(event: MatchEvent) {
    setEditing(event);
    setEditTeamId(`${event.team_id}`);
    setEditPlayerId(event.player_id == null ? null : `${event.player_id}`);
    setEditPlayerNumber(event.player_number ?? '');
    setEditPeriod(event.period);
    setEditGameTime(formatGameTime(event.game_time_seconds));
    setEditPenaltyCode(event.penalty_code ?? null);
    setEditPenaltyType((event.penalty_type as PenaltyType | null | undefined) ?? null);
    setEditPenaltyMinutes(event.penalty_minutes ?? '');
    setEditInfraction(event.infraction ?? '');
    setEditError(null);
  }

  async function submitEdit() {
    if (editing == null || editTeamId == null || editPeriod == null) return;
    const seconds = parseGameTime(editGameTime);
    if (seconds == null) {
      setEditError('Spielzeit im Format MM:SS eingeben (Sekunden 00\u201359).');
      return;
    }
    const response = await updateMatchEvent(
      tournamentId,
      match.id,
      editing.id,
      eventBody(
        editing,
        Number(editTeamId),
        editPlayerId == null ? null : Number(editPlayerId),
        editPlayerNumber === '' ? null : Number(editPlayerNumber),
        editPeriod,
        seconds,
        editPenaltyCode,
        editPenaltyType,
        editPenaltyMinutes === '' ? null : Number(editPenaltyMinutes),
        editInfraction
      )
    );
    await refreshAfterMutation();
    if (response != null) {
      onGoalMutation(editing, response.data.data);
      setEditing(null);
    }
  }

  return (
    <Stack gap="sm">
      <Divider my="md" label="Spielereignisse" labelPosition="left" />
      <Group justify="space-between">
        <Text fw={600}>Aktuelle Spielphase</Text>
        <Badge size="lg">{phaseLabel(status, activePeriod, phaseState)}</Badge>
      </Group>

      {canCreate ? (
        <Paper withBorder p="sm">
          <Stack gap="xs">
            <Group grow>
              <Button
                variant={eventType === 'GOAL' ? 'filled' : 'light'}
                onClick={() => setEventType('GOAL')}
              >
                Tor
              </Button>
              <Button
                variant={eventType === 'PENALTY' ? 'filled' : 'light'}
                onClick={() => setEventType('PENALTY')}
              >
                Strafe
              </Button>
            </Group>
            <Select
              label="Team"
              data={teamOptions}
              value={teamId}
              onChange={(value) => {
                setTeamId(value);
                setPlayerId(null);
              }}
            />
            <NumberInput
              label="Spielernummer"
              min={0}
              value={playerNumber}
              onChange={setPlayerNumber}
            />
            <Select
              label="Spieler (optional)"
              data={playerOptions}
              value={playerId}
              onChange={(value) => {
                setPlayerId(value);
                if (value != null) {
                  const player = selectedTeam?.players.find(
                    (candidate) => candidate.id === Number(value)
                  );
                  if (player?.number != null) setPlayerNumber(player.number);
                }
              }}
              disabled={teamId == null}
              clearable
              searchable
            />
            <TextInput
              label="Spielzeit (MM:SS)"
              placeholder="00:35"
              value={gameTime}
              onChange={(event) => setGameTime(event.currentTarget.value)}
            />
            {eventType === 'PENALTY' ? (
              <>
                <Select
                  label="Vergehen"
                  data={penalties.map((penalty) => ({
                    value: penalty.code,
                    label: penalty.label,
                  }))}
                  value={penaltyCode}
                  onChange={(value) => {
                    setPenaltyCode(value);
                    const definition = penalties.find((penalty) => penalty.code === value);
                    setPenaltyType(definition?.default_penalty_type ?? null);
                    setPenaltyMinutes('');
                    setInfraction('');
                  }}
                  searchable
                />
                <Select
                  label="Strafe"
                  data={typeOptions}
                  value={penaltyType}
                  onChange={(value) => setPenaltyType(value as PenaltyType | null)}
                  disabled={selectedPenalty == null}
                />
                {penaltyCode === 'OTHER' ? (
                  <TextInput
                    label="Vergehen (Freitext)"
                    value={infraction}
                    onChange={(event) => setInfraction(event.currentTarget.value)}
                  />
                ) : null}
                {penaltyType === 'CUSTOM' ? (
                  <NumberInput
                    label="Strafdauer (Minuten, optional)"
                    min={0}
                    value={penaltyMinutes}
                    onChange={setPenaltyMinutes}
                  />
                ) : null}
              </>
            ) : null}
            {validationError != null ? <Text c="red">{validationError}</Text> : null}
            <Button onClick={submitEvent}>{eventType === 'GOAL' ? 'Tor eintragen' : 'Strafe eintragen'}</Button>
          </Stack>
        </Paper>
      ) : (
        <Text c="dimmed" size="sm">
          Neue Ereignisse k&ouml;nnen nur w&auml;hrend einer aktiven Spielphase erfasst werden.
        </Text>
      )}

      {events.length === 0 ? <Text c="dimmed">Noch keine Spielereignisse.</Text> : null}
      {events.map((event) => {
        const team = teamById[event.team_id];

        return (
          <Paper key={event.id} withBorder p="sm">
            <Group justify="space-between" align="flex-start">
              <div>
                <Group gap="xs">
                  <Badge variant="light">{MATCH_PERIOD_LABELS[event.period]}</Badge>
                  <Text fw={600}>{formatGameTime(event.game_time_seconds)}</Text>
                  <Text>{event.event_type === 'GOAL' ? 'Tor' : 'Strafe'}</Text>
                </Group>
                <Text size="sm">
                  {team?.name ?? `Team ${event.team_id}`}
                  {event.player_name != null || event.player_number != null
                    ? ` \u00b7 ${event.player_number == null ? '' : `#${event.player_number} `}${event.player_name ?? ''}`
                    : ''}
                </Text>
                {event.event_type === 'PENALTY' ? (
                  <Text size="sm" c="dimmed">
                    {formatPenaltyDetails(event)}
                  </Text>
                ) : null}
              </div>
              <Group gap="xs">
                <ActionIcon variant="light" aria-label="Ereignis bearbeiten" onClick={() => beginEdit(event)}>
                  <IconPencil size={16} />
                </ActionIcon>
                <ActionIcon
                  color="red"
                  variant="light"
                  aria-label="Ereignis l\u00f6schen"
                  onClick={async () => {
                    const response = await deleteMatchEvent(tournamentId, match.id, event.id);
                    await refreshAfterMutation();
                    if (response == null) return;
                    if (editing?.id === event.id) setEditing(null);
                    onGoalMutation(event, null);
                  }}
                >
                  <IconTrash size={16} />
                </ActionIcon>
              </Group>
            </Group>
          </Paper>
        );
      })}

      {editing != null ? (
        <Paper withBorder p="sm">
          <Stack gap="xs">
            <Group justify="space-between">
              <Text fw={600}>Ereignis bearbeiten</Text>
              <ActionIcon variant="subtle" aria-label="Bearbeitung schlie\u00dfen" onClick={() => setEditing(null)}>
                <IconX size={16} />
              </ActionIcon>
            </Group>
            <Select
              label="Phase"
              data={periodOptions}
              value={editPeriod}
              onChange={(value) => setEditPeriod(value as MatchPeriod | null)}
            />
            <Select
              label="Team"
              data={teamOptions}
              value={editTeamId}
              onChange={(value) => {
                setEditTeamId(value);
                setEditPlayerId(null);
              }}
            />
            <NumberInput
              label="Spielernummer"
              min={0}
              value={editPlayerNumber}
              onChange={setEditPlayerNumber}
            />
            <Select
              label="Spieler (optional)"
              data={editPlayerOptions}
              value={editPlayerId}
              onChange={(value) => {
                setEditPlayerId(value);
                if (value != null) {
                  const player = editTeam?.players.find(
                    (candidate) => candidate.id === Number(value)
                  );
                  if (player?.number != null) setEditPlayerNumber(player.number);
                }
              }}
              clearable
              searchable
            />
            <TextInput
              label="Spielzeit (MM:SS)"
              value={editGameTime}
              onChange={(event) => setEditGameTime(event.currentTarget.value)}
            />
            {editing.event_type === 'PENALTY' ? (
              <>
                <Select
                  label="Vergehen"
                  placeholder={
                    editing.penalty_code == null ? editing.infraction ?? 'Legacy-Eintrag' : undefined
                  }
                  data={penalties.map((penalty) => ({
                    value: penalty.code,
                    label: penalty.label,
                  }))}
                  value={editPenaltyCode}
                  onChange={(value) => {
                    setEditPenaltyCode(value);
                    const definition = penalties.find((penalty) => penalty.code === value);
                    setEditPenaltyType(definition?.default_penalty_type ?? null);
                    setEditPenaltyMinutes('');
                    setEditInfraction('');
                  }}
                  searchable
                  clearable
                />
                {editPenaltyCode == null ? (
                  <>
                    <TextInput
                      label="Vergehen (Legacy)"
                      value={editInfraction}
                      onChange={(event) => setEditInfraction(event.currentTarget.value)}
                    />
                    <NumberInput
                      label="Strafdauer (Minuten)"
                      min={0}
                      value={editPenaltyMinutes}
                      onChange={setEditPenaltyMinutes}
                    />
                  </>
                ) : (
                  <>
                    <Select
                      label="Strafe"
                      data={editTypeOptions}
                      value={editPenaltyType}
                      onChange={(value) => setEditPenaltyType(value as PenaltyType | null)}
                    />
                    {editPenaltyCode === 'OTHER' ? (
                      <TextInput
                        label="Vergehen (Freitext)"
                        value={editInfraction}
                        onChange={(event) => setEditInfraction(event.currentTarget.value)}
                      />
                    ) : null}
                    {editPenaltyType === 'CUSTOM' ? (
                      <NumberInput
                        label="Strafdauer (Minuten, optional)"
                        min={0}
                        value={editPenaltyMinutes}
                        onChange={setEditPenaltyMinutes}
                      />
                    ) : null}
                  </>
                )}
              </>
            ) : null}
            {editError != null ? <Text c="red">{editError}</Text> : null}
            <Button onClick={submitEdit}>{'\u00c4nderungen speichern'}</Button>
          </Stack>
        </Paper>
      ) : null}
    </Stack>
  );
}
