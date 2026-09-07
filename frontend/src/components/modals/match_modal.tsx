import {
  Badge,
  Button,
  Center,
  Checkbox,
  Divider,
  Grid,
  Group,
  Modal,
  NumberInput,
  Select,
  Text,
  TextInput,
} from '@mantine/core';
import { DatePickerInput, TimeInput } from '@mantine/dates';
import { useForm } from '@mantine/form';
import { useTranslation } from 'next-i18next';
import React, { useState } from 'react';
import { SWRResponse } from 'swr';
import { format, parseISO } from 'date-fns';

import {
  MatchBodyInterface,
  MatchInterface,
  MatchPeriod,
  MatchPhaseAction,
  MatchPhaseState,
  MatchStatus,
  formatMatchInput1,
  formatMatchInput2,
} from '../../interfaces/match';
import { RoundInterface } from '../../interfaces/round';
import { MatchEvent } from '../../interfaces/match_event';
import {
  HockeyAgeCategory,
  HockeyRuleset,
  HockeyMode,
  Tournament,
  TournamentMinimal,
} from '../../interfaces/tournament';
import { getTournamentById, getUser } from '../../services/adapter';
import { getMatchLookup, getStageItemLookup } from '../../services/lookups';
import { deleteMatch, transitionMatchPhase, updateMatch } from '../../services/match';
import DeleteButton from '../buttons/delete';
import MatchEvents from '../match_events';

function combineStartDateAndTime(date: Date | null, time: string): string | null {
  if (date == null || Number.isNaN(date.getTime()) || time.trim() === '') return null;

  const [hoursValue, minutesValue, secondsValue = '0'] = time.split(':');
  const hours = Number(hoursValue);
  const minutes = Number(minutesValue);
  const seconds = Number(secondsValue);

  if (
    !Number.isInteger(hours) ||
    !Number.isInteger(minutes) ||
    !Number.isInteger(seconds) ||
    hours < 0 ||
    hours > 23 ||
    minutes < 0 ||
    minutes > 59 ||
    seconds < 0 ||
    seconds > 59
  ) {
    return null;
  }

  return new Date(
    date.getFullYear(),
    date.getMonth(),
    date.getDate(),
    hours,
    minutes,
    seconds
  ).toISOString();
}

function getPartPoints(
  teamScore: number,
  opponentScore: number,
  winPoints: number,
  drawPoints: number
): number {
  if (teamScore > opponentScore) return winPoints;
  if (teamScore === opponentScore) return drawPoints;
  return 0;
}

function getHockeyPoints(
  half1Team: number,
  half1Opponent: number,
  half2Team: number,
  half2Opponent: number,
  penaltyTeam: number,
  penaltyOpponent: number
): number {
  return (
    getPartPoints(half1Team, half1Opponent, 2, 1) +
    getPartPoints(half2Team, half2Opponent, 2, 1) +
    getPartPoints(penaltyTeam, penaltyOpponent, 1, 0.5)
  );
}

function formatHockeyPoints(points: number): string {
  return Number.isInteger(points) ? `${points}` : points.toFixed(1).replace('.', ',');
}

function formatAgeCategory(ageCategory: HockeyAgeCategory): string {
  return ageCategory === 'SENIOR' ? 'Senioren' : ageCategory;
}

interface PhaseControl {
  label: string;
  action: MatchPhaseAction;
  color?: string;
  variant?: 'filled' | 'light';
}

interface PhaseUi {
  label: string;
  controls: PhaseControl[];
}

function resumeControl(period: MatchPeriod): PhaseControl {
  const label = {
    HALF1: '1. Halbzeit fortsetzen',
    HALF2: '2. Halbzeit fortsetzen',
    SHOOTOUT: 'Penalty fortsetzen',
    PERIOD1: '1. Drittel fortsetzen',
    PERIOD2: '2. Drittel fortsetzen',
    PERIOD3: '3. Drittel fortsetzen',
    OVERTIME: 'Overtime fortsetzen',
  }[period];
  return { label, action: 'RESUME_PERIOD' };
}

function getPhaseUi(
  mode: HockeyMode,
  status: MatchStatus,
  period: MatchPeriod | null,
  phaseState: MatchPhaseState | null,
  reopenedBreak: boolean
): PhaseUi {
  if (status === 'PLANNED') {
    return {
      label: 'Spiel geplant',
      controls: [{ label: 'Spiel starten', action: 'START_MATCH' }],
    };
  }
  if (status === 'FINISHED') {
    return {
      label: 'Spiel beendet',
      controls: [
        {
          label: 'Spiel wieder öffnen',
          action: 'REOPEN_MATCH',
          variant: 'light',
        },
      ],
    };
  }
  if (period == null || phaseState == null) {
    return { label: 'Spiel läuft – Spielphase unbekannt', controls: [] };
  }
  if (phaseState === 'BREAK' && reopenedBreak) {
    return { label: 'Pause', controls: [resumeControl(period)] };
  }

  if (mode === 'COMPETITION') {
    if (period === 'HALF1' && phaseState === 'ACTIVE') {
      return {
        label: '1. Halbzeit läuft',
        controls: [{ label: '1. Halbzeit beenden', action: 'END_PERIOD' }],
      };
    }
    if (period === 'HALF1' && phaseState === 'BREAK') {
      return {
        label: 'Pause nach 1. Halbzeit',
        controls: [{ label: '2. Halbzeit starten', action: 'START_NEXT_PERIOD' }],
      };
    }
    if (period === 'HALF2' && phaseState === 'ACTIVE') {
      return {
        label: '2. Halbzeit läuft',
        controls: [{ label: '2. Halbzeit beenden', action: 'END_PERIOD' }],
      };
    }
    if (period === 'HALF2' && phaseState === 'BREAK') {
      return {
        label: 'Pause nach 2. Halbzeit',
        controls: [{ label: 'Penalty starten', action: 'START_NEXT_PERIOD' }],
      };
    }
    if (period === 'SHOOTOUT' && phaseState === 'ACTIVE') {
      return {
        label: 'Penalty läuft',
        controls: [{ label: 'Spiel beenden', action: 'FINISH_MATCH', color: 'green' }],
      };
    }
    if (period === 'SHOOTOUT' && phaseState === 'BREAK') {
      return { label: 'Pause', controls: [resumeControl(period)] };
    }
  }

  if (mode === 'STANDARD') {
    if (period === 'PERIOD1' && phaseState === 'ACTIVE') {
      return {
        label: '1. Drittel läuft',
        controls: [{ label: '1. Drittel beenden', action: 'END_PERIOD' }],
      };
    }
    if (period === 'PERIOD1' && phaseState === 'BREAK') {
      return {
        label: 'Pause nach 1. Drittel',
        controls: [{ label: '2. Drittel starten', action: 'START_NEXT_PERIOD' }],
      };
    }
    if (period === 'PERIOD2' && phaseState === 'ACTIVE') {
      return {
        label: '2. Drittel läuft',
        controls: [{ label: '2. Drittel beenden', action: 'END_PERIOD' }],
      };
    }
    if (period === 'PERIOD2' && phaseState === 'BREAK') {
      return {
        label: 'Pause nach 2. Drittel',
        controls: [{ label: '3. Drittel starten', action: 'START_NEXT_PERIOD' }],
      };
    }
    if (period === 'PERIOD3' && phaseState === 'ACTIVE') {
      return {
        label: '3. Drittel läuft',
        controls: [
          { label: '3. Drittel beenden', action: 'END_PERIOD' },
          { label: 'Spiel beenden', action: 'FINISH_MATCH', color: 'green' },
        ],
      };
    }
    if (period === 'PERIOD3' && phaseState === 'BREAK') {
      return {
        label: 'Pause nach 3. Drittel',
        controls: [
          { label: 'Spiel beenden', action: 'FINISH_MATCH', color: 'green' },
          { label: 'Overtime starten', action: 'START_OVERTIME' },
        ],
      };
    }
    if (period === 'OVERTIME' && phaseState === 'ACTIVE') {
      return {
        label: 'Overtime läuft',
        controls: [
          { label: 'Overtime beenden', action: 'END_PERIOD' },
          { label: 'Spiel beenden', action: 'FINISH_MATCH', color: 'green' },
        ],
      };
    }
    if (period === 'OVERTIME' && phaseState === 'BREAK') {
      return {
        label: 'Pause nach Overtime',
        controls: [{ label: 'Spiel beenden', action: 'FINISH_MATCH', color: 'green' }],
      };
    }
  }

  return { label: 'Spielphase unbekannt', controls: [] };
}

function MatchDeleteButton({
  tournamentData,
  match,
  swrRoundsResponse,
  swrUpcomingMatchesResponse,
}: {
  tournamentData: TournamentMinimal;
  match: MatchInterface;
  swrRoundsResponse: SWRResponse;
  swrUpcomingMatchesResponse: SWRResponse | null;
}) {
  const { t } = useTranslation();
  return (
    <DeleteButton
      fullWidth
      onClick={async () => {
        await deleteMatch(tournamentData.id, match.id);
        await swrRoundsResponse.mutate();
        if (swrUpcomingMatchesResponse != null) await swrUpcomingMatchesResponse.mutate();
      }}
      style={{ marginTop: '1rem' }}
      size="sm"
      title={t('remove_match_button')}
    />
  );
}

function MatchModalForm({
  tournamentData,
  tournament,
  match,
  swrStagesResponse,
  swrUpcomingMatchesResponse,
  setOpened,
  round,
}: {
  tournamentData: TournamentMinimal;
  tournament: Tournament;
  match: MatchInterface | null;
  swrStagesResponse: SWRResponse;
  swrUpcomingMatchesResponse: SWRResponse | null;
  setOpened: any;
  round: RoundInterface | null;
}) {
  if (match == null) {
    return null;
  }

  const { t } = useTranslation();
  const swrUserResponse = getUser();
  const currentUser = swrUserResponse.data != null ? swrUserResponse.data.data : null;
  const isScorer = currentUser?.account_type === 'SCORER';
  const [currentStatus, setCurrentStatus] = useState<MatchStatus>(match.status);
  const [currentPeriod, setCurrentPeriod] = useState<MatchPeriod | null>(match.active_period);
  const [currentPhaseState, setCurrentPhaseState] = useState<MatchPhaseState | null>(
    match.phase_state
  );
  const [reopenedBreak, setReopenedBreak] = useState(false);


  // Parse start_time for initial values
  const parsedStartTime = match.start_time ? parseISO(match.start_time) : null;
  const startTimeDate =
    parsedStartTime != null && !Number.isNaN(parsedStartTime.getTime()) ? parsedStartTime : null;

  const form = useForm({
    initialValues: {
      stage_item_input1_half1_score: match.stage_item_input1_half1_score,
      stage_item_input2_half1_score: match.stage_item_input2_half1_score,
      stage_item_input1_half2_score: match.stage_item_input1_half2_score,
      stage_item_input2_half2_score: match.stage_item_input2_half2_score,
      stage_item_input1_penalty_score: match.stage_item_input1_penalty_score,
      stage_item_input2_penalty_score: match.stage_item_input2_penalty_score,     
      start_time_date: startTimeDate,
      start_time_time: startTimeDate ? format(startTimeDate, 'HH:mm') : '',
      custom_duration_minutes: match.custom_duration_minutes,
      custom_margin_minutes: match.custom_margin_minutes,
      ruleset_override: match.ruleset_override ?? '',
      age_category_override: match.age_category_override ?? '',
      ruleset_season_inherited: match.ruleset_season_override == null,
      ruleset_season_override: match.ruleset_season_override ?? tournament.ruleset_season,
    },

    validate: {
      stage_item_input1_half1_score: (value) =>
        value >= 0 ? null : t('negative_score_validation'),
      stage_item_input2_half1_score: (value) =>
        value >= 0 ? null : t('negative_score_validation'),
      stage_item_input1_half2_score: (value) =>
        value >= 0 ? null : t('negative_score_validation'),
      stage_item_input2_half2_score: (value) =>
        value >= 0 ? null : t('negative_score_validation'),
      stage_item_input1_penalty_score: (value) =>
        value >= 0 ? null : t('negative_score_validation'),
      stage_item_input2_penalty_score: (value) =>
        value >= 0 ? null : t('negative_score_validation'),    
      custom_duration_minutes: (value) =>
        value == null || value >= 0 ? null : t('negative_match_duration_validation'),
      custom_margin_minutes: (value) =>
        value == null || value >= 0 ? null : t('negative_match_margin_validation'),
      ruleset_season_override: (value, values) => {
        if (values.ruleset_season_inherited) return null;
        const matchResult = /^(\d{4})\/(\d{2})$/.exec(value);
        if (matchResult == null) return 'Format JJJJ/JJ verwenden';
        return (Number(matchResult[1]) + 1) % 100 === Number(matchResult[2])
          ? null
          : 'Die zweite Jahreszahl muss das Folgejahr sein';
      },
    },
  });

  const [customDurationEnabled, setCustomDurationEnabled] = useState(
    match.custom_duration_minutes != null
  );
  const [customMarginEnabled, setCustomMarginEnabled] = useState(
    match.custom_margin_minutes != null
  );

  const stageItemsLookup = getStageItemLookup(swrStagesResponse);
  const matchesLookup = getMatchLookup(swrStagesResponse);

  const team1Name = formatMatchInput1(t, stageItemsLookup, matchesLookup, match);
  const team2Name = formatMatchInput2(t, stageItemsLookup, matchesLookup, match);

  const totalScore1 =
    form.values.stage_item_input1_half1_score +
    form.values.stage_item_input1_half2_score;

  const totalScore2 =
    form.values.stage_item_input2_half1_score +
    form.values.stage_item_input2_half2_score;

  const hockeyPoints1 = getHockeyPoints(
    form.values.stage_item_input1_half1_score,
    form.values.stage_item_input2_half1_score,
    form.values.stage_item_input1_half2_score,
    form.values.stage_item_input2_half2_score,
    form.values.stage_item_input1_penalty_score,
    form.values.stage_item_input2_penalty_score
  );

  const hockeyPoints2 = getHockeyPoints(
    form.values.stage_item_input2_half1_score,
    form.values.stage_item_input1_half1_score,
    form.values.stage_item_input2_half2_score,
    form.values.stage_item_input1_half2_score,
    form.values.stage_item_input2_penalty_score,
    form.values.stage_item_input1_penalty_score
  );

  type ScoreField =
    | 'stage_item_input1_half1_score'
    | 'stage_item_input2_half1_score'
    | 'stage_item_input1_half2_score'
    | 'stage_item_input2_half2_score'
    | 'stage_item_input1_penalty_score'
    | 'stage_item_input2_penalty_score';

  function goalScoreField(event: MatchEvent | null): ScoreField | null {
    if (event == null || event.event_type !== 'GOAL' || match == null) return null;
    const firstTeam = match.stage_item_input1?.team_id === event.team_id;
    const secondTeam = match.stage_item_input2?.team_id === event.team_id;
    if (!firstTeam && !secondTeam) return null;
    if (event.period === 'HALF1') {
      return firstTeam
        ? 'stage_item_input1_half1_score'
        : 'stage_item_input2_half1_score';
    }
    if (event.period === 'HALF2') {
      return firstTeam
        ? 'stage_item_input1_half2_score'
        : 'stage_item_input2_half2_score';
    }
    if (event.period === 'SHOOTOUT') {
      return firstTeam
        ? 'stage_item_input1_penalty_score'
        : 'stage_item_input2_penalty_score';
    }
    return null;
  }

  function applyGoalMutation(oldEvent: MatchEvent | null, newEvent: MatchEvent | null) {
    const changes = new Map<ScoreField, number>();
    const oldField = goalScoreField(oldEvent);
    const newField = goalScoreField(newEvent);
    if (oldField != null) changes.set(oldField, (changes.get(oldField) ?? 0) - 1);
    if (newField != null) changes.set(newField, (changes.get(newField) ?? 0) + 1);
    changes.forEach((delta, field) => {
      form.setFieldValue(field, form.values[field] + delta);
    });
  }

  async function saveMatch(values: typeof form.values): Promise<boolean> {
    if (!match) return false;

    const updatedMatch = isScorer
      ? {
          round_id: match.round_id,
          stage_item_input1_half1_score: values.stage_item_input1_half1_score,
          stage_item_input2_half1_score: values.stage_item_input2_half1_score,
          stage_item_input1_half2_score: values.stage_item_input1_half2_score,
          stage_item_input2_half2_score: values.stage_item_input2_half2_score,
          stage_item_input1_penalty_score: values.stage_item_input1_penalty_score,
          stage_item_input2_penalty_score: values.stage_item_input2_penalty_score,
        }
      : {
          id: match.id,
          round_id: match.round_id,
          stage_item_input1_half1_score: values.stage_item_input1_half1_score,
          stage_item_input2_half1_score: values.stage_item_input2_half1_score,
          stage_item_input1_half2_score: values.stage_item_input1_half2_score,
          stage_item_input2_half2_score: values.stage_item_input2_half2_score,
          stage_item_input1_penalty_score: values.stage_item_input1_penalty_score,
          stage_item_input2_penalty_score: values.stage_item_input2_penalty_score,
          court_id: match.court_id,
          start_time: combineStartDateAndTime(values.start_time_date, values.start_time_time),
          custom_duration_minutes: customDurationEnabled
            ? values.custom_duration_minutes
            : null,
          custom_margin_minutes: customMarginEnabled ? values.custom_margin_minutes : null,
          ruleset_override:
            values.ruleset_override === ''
              ? null
              : (values.ruleset_override as HockeyRuleset),
          age_category_override:
            values.age_category_override === ''
              ? null
              : (values.age_category_override as HockeyAgeCategory),
          ruleset_season_override: values.ruleset_season_inherited
            ? null
            : values.ruleset_season_override,
        };

    const response = await updateMatch(
      tournamentData.id,
      match.id,
      updatedMatch as MatchBodyInterface
    );

    if (response == null) return false;

    await swrStagesResponse.mutate();
    if (swrUpcomingMatchesResponse != null) await swrUpcomingMatchesResponse.mutate();
    return true;
  }

  async function changePhase(action: MatchPhaseAction) {
    if (!match) return;

    const saved = await saveMatch(form.values);
    if (!saved) return;

    const response = await transitionMatchPhase(tournamentData.id, match.id, action);

    await swrStagesResponse.mutate();
    if (swrUpcomingMatchesResponse != null) await swrUpcomingMatchesResponse.mutate();

    if (response == null) return;

    const updatedMatch = response.data.data;
    setCurrentStatus(updatedMatch.status);
    setCurrentPeriod(updatedMatch.active_period);
    setCurrentPhaseState(updatedMatch.phase_state);
    setReopenedBreak(action === 'REOPEN_MATCH');

    if (action === 'FINISH_MATCH') {
      setOpened(false);
    }
  }

  const phaseUi = getPhaseUi(
    tournament.hockey_mode,
    currentStatus,
    currentPeriod,
    currentPhaseState,
    reopenedBreak
  );

  return (
    <>
      <Group justify="space-between" align="center" mb="lg">
        <Badge variant="light" size="lg">
          {phaseUi.label}
        </Badge>
        <Group gap="xs">
          {phaseUi.controls.map((control) => (
            <Button
              key={control.action}
              color={control.color}
              variant={control.variant}
              onClick={() => changePhase(control.action)}
            >
              {control.label}
            </Button>
          ))}
        </Group>
      </Group>
      <form
        onSubmit={form.onSubmit(async (values) => {
          const saved = await saveMatch(values);
          if (!saved) return;
          setOpened(false);
        })}
      >
        <Text fw={600} mb="sm">
          Ergebnis
        </Text>

        <Grid align="end">
          <Grid.Col span={4}>
            <Text size="sm" fw={500}>
              Abschnitt
            </Text>
          </Grid.Col>

          <Grid.Col span={4}>
            <Text size="sm" fw={500} ta="center">
              {team1Name}
            </Text>
          </Grid.Col>

          <Grid.Col span={4}>
            <Text size="sm" fw={500} ta="center">
              {team2Name}
            </Text>
          </Grid.Col>

          <Grid.Col span={4}>
            <Text size="sm">1. Halbzeit</Text>
          </Grid.Col>

          <Grid.Col span={4}>
            <NumberInput
              min={0}
              hideControls
              disabled={currentStatus === 'PLANNED'}
              {...form.getInputProps('stage_item_input1_half1_score')}
            />
          </Grid.Col>

          <Grid.Col span={4}>
            <NumberInput
              min={0}
              hideControls
              disabled={currentStatus === 'PLANNED'}
              {...form.getInputProps('stage_item_input2_half1_score')}
            />
          </Grid.Col>

          <Grid.Col span={4}>
           <Text size="sm">2. Halbzeit</Text>
          </Grid.Col>

          <Grid.Col span={4}>
            <NumberInput
              min={0}
              hideControls
              disabled={currentStatus === 'PLANNED'}
              {...form.getInputProps('stage_item_input1_half2_score')}
            />
          </Grid.Col>

          <Grid.Col span={4}>
            <NumberInput
              min={0}
              hideControls
              disabled={currentStatus === 'PLANNED'}
              {...form.getInputProps('stage_item_input2_half2_score')}
            />
          </Grid.Col>

          <Grid.Col span={4}>
            <Text size="sm">Penalty</Text>
          </Grid.Col>

          <Grid.Col span={4}>
            <NumberInput
              min={0}
              hideControls
              disabled={currentStatus === 'PLANNED'}
              {...form.getInputProps('stage_item_input1_penalty_score')}
            />
          </Grid.Col>

          <Grid.Col span={4}>
            <NumberInput
              min={0}
              hideControls
              disabled={currentStatus === 'PLANNED'}
              {...form.getInputProps('stage_item_input2_penalty_score')}
            />
          </Grid.Col>

        </Grid>

        <Divider my="lg" />

        <Grid>
          <Grid.Col span={4}>
            <Text fw={600}>Gesamttore</Text>
          </Grid.Col>

          <Grid.Col span={4}>
            <Text fw={600} ta="center">
              {totalScore1}
            </Text>
          </Grid.Col>

          <Grid.Col span={4}>
            <Text fw={600} ta="center">
              {totalScore2}
            </Text>
          </Grid.Col>

          <Grid.Col span={4}>
            <Text fw={600}>Spielpunkte</Text>
          </Grid.Col>

          <Grid.Col span={4}>
            <Text fw={600} ta="center">
              {formatHockeyPoints(hockeyPoints1)}
            </Text>
          </Grid.Col>

          <Grid.Col span={4}>
            <Text fw={600} ta="center">
              {formatHockeyPoints(hockeyPoints2)}
            </Text>
          </Grid.Col>
        </Grid>

        {!isScorer ? (
          <>
            <Divider mt="lg" />

            <Text size="sm" mt="lg">
              Startzeit
        </Text>
        
        <Grid>
          <Grid.Col span={{ sm: 6 }}>
            <DatePickerInput
              label="Datum"
              placeholder="Wähle Datum"
              valueFormat="dd.MM.yyyy"
              {...form.getInputProps('start_time_date')}
            />
          </Grid.Col>
          <Grid.Col span={{ sm: 6 }}>
            <TimeInput
              label="Uhrzeit"
              placeholder="HH:mm"
              {...form.getInputProps('start_time_time')}
            />
          </Grid.Col>
        </Grid>
        <Divider mt="lg" />

        <Text fw={600} mt="lg" mb="sm">
          Spielregeln
        </Text>
        <Grid>
          <Grid.Col span={{ sm: 6 }}>
            <Select
              label="Regelwerk"
              data={[
                {
                  value: '',
                  label: `Turniereinstellung verwenden (${tournament.ruleset})`,
                },
                { value: 'DEB', label: 'DEB' },
                { value: 'IIHF', label: 'IIHF' },
              ]}
              allowDeselect={false}
              {...form.getInputProps('ruleset_override')}
            />
          </Grid.Col>
          <Grid.Col span={{ sm: 6 }}>
            <Select
              label="Altersklasse"
              data={[
                {
                  value: '',
                  label: `Turniereinstellung verwenden (${formatAgeCategory(tournament.age_category)})`,
                },
                ...(['U9', 'U11', 'U13', 'U15', 'U17', 'U20', 'SENIOR'] as HockeyAgeCategory[]).map(
                  (value) => ({
                    value,
                    label: formatAgeCategory(value),
                  })
                ),
              ]}
              allowDeselect={false}
              {...form.getInputProps('age_category_override')}
            />
          </Grid.Col>
        </Grid>
        <Checkbox
          mt="md"
          label={`Turniereinstellung verwenden (${tournament.ruleset_season})`}
          {...form.getInputProps('ruleset_season_inherited', { type: 'checkbox' })}
        />
        <TextInput
          mt="xs"
          label="Regelsaison"
          placeholder="2026/27"
          disabled={form.values.ruleset_season_inherited}
          {...form.getInputProps('ruleset_season_override')}
        />

        <Divider mt="lg" />

        <Text size="sm" mt="lg">
          {t('custom_match_duration_label')}
        </Text>
        <Grid align="center">
          <Grid.Col span={{ sm: 8 }}>
            <NumberInput
              disabled={!customDurationEnabled}
              rightSection={<Text>{t('minutes')}</Text>}
              placeholder={`${match.duration_minutes}`}
              rightSectionWidth={92}
              {...form.getInputProps('custom_duration_minutes')}
            />
          </Grid.Col>
          <Grid.Col span={{ sm: 4 }}>
            <Center>
              <Checkbox
                checked={customDurationEnabled}
                label={t('customize_checkbox_label')}
                onChange={(event) => {
                  setCustomDurationEnabled(event.currentTarget.checked);
                }}
              />
            </Center>
          </Grid.Col>
        </Grid>

        <Text size="sm" mt="lg">
          {t('custom_match_margin_label')}
        </Text>
        <Grid align="center">
          <Grid.Col span={{ sm: 8 }}>
            <NumberInput
              disabled={!customMarginEnabled}
              placeholder={`${match.margin_minutes}`}
              rightSection={<Text>{t('minutes')}</Text>}
              rightSectionWidth={92}
              {...form.getInputProps('custom_margin_minutes')}
            />
          </Grid.Col>
          <Grid.Col span={{ sm: 4 }}>
            <Center>
              <Checkbox
                checked={customMarginEnabled}
                label={t('customize_checkbox_label')}
                onChange={(event) => {
                  setCustomMarginEnabled(event.currentTarget.checked);
                }}
              />
            </Center>
          </Grid.Col>
        </Grid>

          </>
        ) : null}

        <Button fullWidth style={{ marginTop: 20 }} color="green" type="submit">
          {t('save_button')}
        </Button>
      </form>
      <MatchEvents
        tournamentId={tournamentData.id}
        hockeyMode={tournament.hockey_mode}
        match={match}
        status={currentStatus}
        activePeriod={currentPeriod}
        phaseState={currentPhaseState}
        refreshMatch={() => swrStagesResponse.mutate()}
        onGoalMutation={applyGoalMutation}
      />
      {!isScorer && round && round.is_draft && (
        <MatchDeleteButton
          swrRoundsResponse={swrStagesResponse}
          swrUpcomingMatchesResponse={swrUpcomingMatchesResponse}
          tournamentData={tournamentData}
          match={match}
        />
      )}
    </>
  );
}

export default function MatchModal({
  tournamentData,
  match,
  swrStagesResponse,
  swrUpcomingMatchesResponse,
  opened,
  setOpened,
  round,
}: {
  tournamentData: TournamentMinimal;
  match: MatchInterface | null;
  swrStagesResponse: SWRResponse;
  swrUpcomingMatchesResponse: SWRResponse | null;
  opened: boolean;
  setOpened: any;
  round: RoundInterface | null;
}) {
  const { t } = useTranslation();
  const swrTournamentResponse = getTournamentById(tournamentData.id);
  const tournament: Tournament | null =
    swrTournamentResponse.data != null ? swrTournamentResponse.data.data : null;

  return (
    <>
      <Modal opened={opened} onClose={() => setOpened(false)} title={t('edit_match_modal_title')}>
        {tournament != null ? (
        <MatchModalForm
          key={`${match?.id ?? 'none'}-${opened}`}
          swrStagesResponse={swrStagesResponse}
          swrUpcomingMatchesResponse={swrUpcomingMatchesResponse}
          tournamentData={tournamentData}
          tournament={tournament}
          match={match}
          setOpened={setOpened}
          round={round}
        />
        ) : null}
      </Modal>
    </>
  );
}
