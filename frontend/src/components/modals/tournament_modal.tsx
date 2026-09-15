import {
  Button,
  Checkbox,
  Grid,
  Image,
  Modal,
  NumberInput,
  Select,
  TextInput,
} from '@mantine/core';
import { DateTimePicker } from '@mantine/dates';
import { useForm } from '@mantine/form';
import { GoPlus } from '@react-icons/all-files/go/GoPlus';
import { IconCalendar, IconCalendarTime } from '@tabler/icons-react';
import assert from 'assert';
import { useTranslation } from 'next-i18next';
import React, { useState } from 'react';
import { SWRResponse } from 'swr';

import { Club } from '../../interfaces/club';
import {
  HockeyAgeCategory,
  HockeyMode,
  HockeyRuleset,
  Tournament,
} from '../../interfaces/tournament';
import { getBaseApiUrl, getClubs } from '../../services/adapter';
import { createTournament } from '../../services/tournament';
import SaveButton from '../buttons/save';

export function TournamentLogo({ tournament }: { tournament: Tournament | null }) {
  if (tournament == null || tournament.logo_path == null) return null;
  return (
    <Image
      radius="md"
      alt="Logo of the tournament"
      src={`${getBaseApiUrl()}/static/tournament-logos/${tournament.logo_path}`}
    />
  );
}

function GeneralTournamentForm({
  setOpened,
  swrTournamentsResponse,
  clubs,
}: {
  setOpened: any;
  swrTournamentsResponse: SWRResponse;
  clubs: Club[];
}) {
  const { t } = useTranslation();
  const form = useForm({
    initialValues: {
      start_time: new Date(),
      name: '',
      club_id: null,
      dashboard_public: true,
      dashboard_endpoint: '',
      players_can_be_in_multiple_teams: false,
      auto_assign_courts: true,
      duration_minutes: 10,
      margin_minutes: 5,
      hockey_mode: 'COMPETITION' as HockeyMode,
      ruleset: 'DEB' as HockeyRuleset,
      age_category: 'U15' as HockeyAgeCategory,
      ruleset_season: '2026/27',
    },

    validate: {
      name: (value) => (value.length > 0 ? null : t('too_short_name_validation')),
      club_id: (value) => (value != null ? null : t('club_choose_title')),
      start_time: (value) => (value != null ? null : t('start_time_choose_title')),
      duration_minutes: (value) =>
        value != null && value > 0 ? null : t('duration_minutes_choose_title'),
      margin_minutes: (value) =>
        value != null && value > 0 ? null : t('margin_minutes_choose_title'),
      ruleset_season: (value) => {
        const match = /^(\d{4})\/(\d{2})$/.exec(value);
        return match != null && Number(match[2]) === (Number(match[1]) + 1) % 100
          ? null
          : 'Regelsaison muss das Format YYYY/YY haben und fortlaufend sein';
      },
    },
  });

  return (
    <form
      onSubmit={form.onSubmit(async (values) => {
        assert(values.club_id != null);
        await createTournament(
          parseInt(values.club_id, 10),
          values.name,
          values.dashboard_public,
          values.dashboard_endpoint,
          values.players_can_be_in_multiple_teams,
          values.auto_assign_courts,
          values.start_time.toISOString(),
          values.duration_minutes,
          values.margin_minutes,
          values.hockey_mode,
          values.ruleset,
          values.age_category,
          values.ruleset_season
        );
        await swrTournamentsResponse.mutate();
        setOpened(false);
      })}
    >
      <TextInput
        withAsterisk
        label={t('name_input_label')}
        placeholder={t('tournament_name_input_placeholder')}
        {...form.getInputProps('name')}
      />

      <Select
        withAsterisk
        data={clubs.map((p) => ({ value: `${p.id}`, label: p.name }))}
        label={t('club_select_label')}
        placeholder={t('club_select_placeholder')}
        searchable
        limit={20}
        style={{ marginTop: 10 }}
        {...form.getInputProps('club_id')}
      />

      <Select
        withAsterisk
        label="Turniermodus"
        description={
          'Turnier mit Technikwettbewerb: 2 Halbzeiten + Penalty-Wertung + ' +
          'Technikwettbewerb. Game + Shootout: ein Spiel + Shootout-Wertung. ' +
          'Standard-Eishockey: 3 Drittel, später ' +
          'Overtime/Penalty nach Spielregeln.'
        }
        data={[
          { value: 'COMPETITION', label: 'Turnier mit Technikwettbewerb' },
          { value: 'GAME_SHOOTOUT', label: 'Game + Shootout' },
          { value: 'STANDARD', label: 'Standard-Eishockey' },
        ]}
        mt="lg"
        {...form.getInputProps('hockey_mode')}
      />

      <Select
        withAsterisk
        label="Regelwerk"
        data={[
          { value: 'DEB', label: 'DEB' },
          { value: 'IIHF', label: 'IIHF' },
        ]}
        mt="lg"
        {...form.getInputProps('ruleset')}
      />

      <Select
        withAsterisk
        label="Altersklasse"
        data={[
          { value: 'U9', label: 'U9' },
          { value: 'U11', label: 'U11' },
          { value: 'U13', label: 'U13' },
          { value: 'U15', label: 'U15' },
          { value: 'U17', label: 'U17' },
          { value: 'U20', label: 'U20' },
          { value: 'SENIOR', label: 'Senioren' },
        ]}
        mt="lg"
        {...form.getInputProps('age_category')}
      />

      <TextInput
        withAsterisk
        label="Regelsaison"
        placeholder="2026/27"
        mt="lg"
        {...form.getInputProps('ruleset_season')}
      />

      <TextInput
        label={t('dashboard_link_label')}
        placeholder={t('dashboard_link_placeholder')}
        mt="lg"
        {...form.getInputProps('dashboard_endpoint')}
      />
      <Grid mt="1rem">
        <Grid.Col span={{ sm: 9 }}>
          <DateTimePicker
            leftSection={<IconCalendar size="1.1rem" stroke={1.5} />}
            mx="auto"
            {...form.getInputProps('start_time')}
          />
        </Grid.Col>
        <Grid.Col span={{ sm: 3 }}>
          <Button
            fullWidth
            color="indigo"
            leftSection={<IconCalendarTime size="1.1rem" stroke={1.5} />}
            onClick={() => {
              form.setFieldValue('start_time', new Date());
            }}
          >
            {t('now_button')}
          </Button>
        </Grid.Col>
      </Grid>

      <Grid>
        <Grid.Col span={{ sm: 6 }}>
          <NumberInput
            label={t('match_duration_label')}
            mt="lg"
            {...form.getInputProps('duration_minutes')}
          />
        </Grid.Col>
        <Grid.Col span={{ sm: 6 }}>
          <NumberInput
            label={t('time_between_matches_label')}
            mt="lg"
            {...form.getInputProps('margin_minutes')}
          />
        </Grid.Col>
      </Grid>

      <Checkbox
        mt="md"
        label={t('dashboard_public_description')}
        {...form.getInputProps('dashboard_public', { type: 'checkbox' })}
      />
      <Checkbox
        mt="md"
        label={t('miscellaneous_label')}
        {...form.getInputProps('players_can_be_in_multiple_teams', { type: 'checkbox' })}
      />
      <Checkbox
        mt="md"
        label={t('auto_assign_courts_label')}
        {...form.getInputProps('auto_assign_courts', { type: 'checkbox' })}
      />

      <Button fullWidth mt={8} color="green" type="submit">
        {t('save_button')}
      </Button>
    </form>
  );
}

export default function TournamentModal({
  swrTournamentsResponse,
}: {
  swrTournamentsResponse: SWRResponse;
}) {
  const { t } = useTranslation();
  const [opened, setOpened] = useState(false);
  const operation_text = t('create_tournament_button');
  const swrClubsResponse: SWRResponse = getClubs();
  const clubs: Club[] = swrClubsResponse.data != null ? swrClubsResponse.data.data : [];

  return (
    <>
      <Modal opened={opened} onClose={() => setOpened(false)} title={operation_text} size="50rem">
        <GeneralTournamentForm
          setOpened={setOpened}
          swrTournamentsResponse={swrTournamentsResponse}
          clubs={clubs}
        />
      </Modal>
      <SaveButton
        mx="0px"
        fullWidth
        onClick={() => setOpened(true)}
        leftSection={<GoPlus size={24} />}
        title={operation_text}
      />
    </>
  );
}
