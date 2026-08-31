import { Badge, Button, Center, Checkbox, Divider, Grid, Group, Modal, NumberInput, Text, TextInput } from '@mantine/core';
import { DatePickerInput, TimeInput } from '@mantine/dates';
import { useForm } from '@mantine/form';
import { useTranslation } from 'next-i18next';
import React, { useState } from 'react';
import { SWRResponse } from 'swr';
import { format, parseISO } from 'date-fns';

import {
  MatchBodyInterface,
  MatchInterface,
  MatchStatus,
  formatMatchInput1,
  formatMatchInput2,
} from '../../interfaces/match';
import { RoundInterface } from '../../interfaces/round';
import { TournamentMinimal } from '../../interfaces/tournament';
import { getMatchLookup, getStageItemLookup } from '../../services/lookups';
import { deleteMatch, updateMatch } from '../../services/match';
import DeleteButton from '../buttons/delete';

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
  match,
  swrStagesResponse,
  swrUpcomingMatchesResponse,
  setOpened,
  round,
}: {
  tournamentData: TournamentMinimal;
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

  // Parse start_time for initial values
  const parsedStartTime = match.start_time ? parseISO(match.start_time) : null;
  const startTimeDate =
    parsedStartTime != null && !Number.isNaN(parsedStartTime.getTime()) ? parsedStartTime : null;

  const form = useForm({
    initialValues: {
      stage_item_input1_score: match.stage_item_input1_score,
      stage_item_input2_score: match.stage_item_input2_score,
      start_time_date: startTimeDate,
      start_time_time: startTimeDate ? format(startTimeDate, 'HH:mm') : '',
      custom_duration_minutes: match.custom_duration_minutes,
      custom_margin_minutes: match.custom_margin_minutes,
    },

    validate: {
      stage_item_input1_score: (value) => (value >= 0 ? null : t('negative_score_validation')),
      stage_item_input2_score: (value) => (value >= 0 ? null : t('negative_score_validation')),
      custom_duration_minutes: (value) =>
        value == null || value >= 0 ? null : t('negative_match_duration_validation'),
      custom_margin_minutes: (value) =>
        value == null || value >= 0 ? null : t('negative_match_margin_validation'),
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

  async function changeStatus(status: MatchStatus) {
    const startTime = combineStartDateAndTime(
      form.values.start_time_date,
      form.values.start_time_time
    );

    const updatedMatch: MatchBodyInterface = {
      id: match.id,
      round_id: match.round_id,
      stage_item_input1_score: form.values.stage_item_input1_score,
      stage_item_input2_score: form.values.stage_item_input2_score,
      court_id: match.court_id,
      start_time: startTime,
      custom_duration_minutes: customDurationEnabled
        ? form.values.custom_duration_minutes
        : null,
      custom_margin_minutes: customMarginEnabled ? form.values.custom_margin_minutes : null,
      status,
    };
    await updateMatch(tournamentData.id, match.id, updatedMatch);
    await swrStagesResponse.mutate();
    if (swrUpcomingMatchesResponse != null) await swrUpcomingMatchesResponse.mutate();
    setOpened(false);
  }

  const statusLabel = {
    PLANNED: 'Geplant',
    RUNNING: 'Läuft',
    FINISHED: 'Beendet',
  }[match.status];

  return (
    <>
      <Group justify="space-between" mb="lg">
        <Badge variant="light">{statusLabel}</Badge>
        {match.status === 'PLANNED' ? (
          <Button onClick={() => changeStatus('RUNNING')}>Spiel starten</Button>
        ) : null}
        {match.status === 'RUNNING' ? (
          <Button color="green" onClick={() => changeStatus('FINISHED')}>
            Spiel beenden
          </Button>
        ) : null}
        {match.status === 'FINISHED' ? (
          <Button variant="light" onClick={() => changeStatus('RUNNING')}>
            Spiel wieder öffnen
          </Button>
        ) : null}
      </Group>
      <form
        onSubmit={form.onSubmit(async (values) => {
          const startTime = combineStartDateAndTime(
            values.start_time_date,
            values.start_time_time
          );

          const updatedMatch: MatchBodyInterface = {
            id: match.id,
            round_id: match.round_id,
            stage_item_input1_score: values.stage_item_input1_score,
            stage_item_input2_score: values.stage_item_input2_score,
            court_id: match.court_id,
            start_time: startTime,
            custom_duration_minutes: customDurationEnabled ? values.custom_duration_minutes : null,
            custom_margin_minutes: customMarginEnabled ? values.custom_margin_minutes : null,
            status: match.status,
          };
          await updateMatch(tournamentData.id, match.id, updatedMatch);
          await swrStagesResponse.mutate();
          if (swrUpcomingMatchesResponse != null) await swrUpcomingMatchesResponse.mutate();
          setOpened(false);
        })}
      >
        <NumberInput
          withAsterisk
          label={`${t('score_of_label')} ${team1Name}`}
          placeholder={`${t('score_of_label')} ${team1Name}`}
          disabled={match.status === 'PLANNED'}
          {...form.getInputProps('stage_item_input1_score')}
        />
        <NumberInput
          withAsterisk
          mt="lg"
          label={`${t('score_of_label')} ${team2Name}`}
          placeholder={`${t('score_of_label')} ${team2Name}`}
          disabled={match.status === 'PLANNED'}
          {...form.getInputProps('stage_item_input2_score')}
        />
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

        <Button fullWidth style={{ marginTop: 20 }} color="green" type="submit">
          {t('save_button')}
        </Button>
      </form>
      {round && round.is_draft && (
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

  return (
    <>
      <Modal opened={opened} onClose={() => setOpened(false)} title={t('edit_match_modal_title')}>
        <MatchModalForm
          swrStagesResponse={swrStagesResponse}
          swrUpcomingMatchesResponse={swrUpcomingMatchesResponse}
          tournamentData={tournamentData}
          match={match}
          setOpened={setOpened}
          round={round}
        />
      </Modal>
    </>
  );
}
