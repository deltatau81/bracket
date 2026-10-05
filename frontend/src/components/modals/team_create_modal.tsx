import { Button, Checkbox, Modal, MultiSelect, Select, Tabs, TextInput } from '@mantine/core';
import { useForm } from '@mantine/form';
import { IconUser, IconUsers, IconUsersPlus } from '@tabler/icons-react';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { SWRResponse } from 'swr';

import SaveButton from '@components/buttons/save';
import { MultiTeamsInput } from '@components/forms/player_create_csv_input';
import { Club, Player, TeamsWithPlayersResponse } from '@openapi';
import { getClubs, getPlayers } from '@services/adapter';
import { createTeam, createTeams } from '@services/team';

function MultiTeamTab({
  tournament_id,
  swrTeamsResponse,
  setOpened,
  clubs,
}: {
  tournament_id: number;
  swrTeamsResponse: SWRResponse<TeamsWithPlayersResponse>;
  setOpened: any;
  clubs: Club[];
}) {
  const { t } = useTranslation();
  const form = useForm({
    initialValues: {
      names: '',
      active: true,
      participant_club_id: null as string | null,
      pairing_group: '',
    },

    validate: {
      names: (value) => (value.length > 0 ? null : t('at_least_one_team_validation')),
    },
  });
  return (
    <form
      onSubmit={form.onSubmit(async (values) => {
        await createTeams(
          tournament_id,
          values.names,
          values.active,
          values.participant_club_id == null ? null : Number(values.participant_club_id),
          values.pairing_group.trim() || null,
        );
        await swrTeamsResponse.mutate();
        setOpened(false);
      })}
    >
      <MultiTeamsInput form={form} />

      <Select
        clearable
        searchable
        mt="md"
        label="Club"
        placeholder="Optional"
        data={clubs.map((club) => ({ value: `${club.id}`, label: club.name }))}
        {...form.getInputProps('participant_club_id')}
      />

      <TextInput
        mt="md"
        label="Pairing group"
        placeholder="Optional"
        {...form.getInputProps('pairing_group')}
      />

      <Checkbox
        mt="md"
        label={t('active_teams_checkbox_label')}
        {...form.getInputProps('active', { type: 'checkbox' })}
      />
      <Button fullWidth style={{ marginTop: 10 }} color="green" type="submit">
        {t('save_button')}
      </Button>
    </form>
  );
}

function SingleTeamTab({
  tournament_id,
  swrTeamsResponse,
  setOpened,
  clubs,
}: {
  tournament_id: number;
  swrTeamsResponse: SWRResponse<TeamsWithPlayersResponse>;
  setOpened: any;
  clubs: Club[];
}) {
  const { t } = useTranslation();
  const { data } = getPlayers(tournament_id, false);
  const players: Player[] = data != null ? data.data.players : [];
  const form = useForm({
    initialValues: {
      name: '',
      active: true,
      player_ids: [],
      participant_club_id: null as string | null,
      pairing_group: '',
    },
    validate: {
      name: (value) => (value.length > 0 ? null : t('too_short_name_validation')),
    },
  });
  return (
    <form
      onSubmit={form.onSubmit(async (values) => {
        await createTeam(
          tournament_id,
          values.name,
          values.active,
          values.player_ids,
          null,
          values.participant_club_id == null ? null : Number(values.participant_club_id),
          values.pairing_group.trim() || null,
        );
        await swrTeamsResponse.mutate();
        setOpened(false);
      })}
    >
      <TextInput
        withAsterisk
        label={t('name_input_label')}
        placeholder={t('team_name_input_placeholder')}
        {...form.getInputProps('name')}
      />

      <Checkbox
        mt="md"
        label={t('active_teams_checkbox_label')}
        {...form.getInputProps('active', { type: 'checkbox' })}
      />

      <Select
        clearable
        searchable
        mt="md"
        label="Club"
        placeholder="Optional"
        data={clubs.map((club) => ({ value: `${club.id}`, label: club.name }))}
        {...form.getInputProps('participant_club_id')}
      />

      <TextInput
        mt="md"
        label="Pairing group"
        placeholder="Optional"
        {...form.getInputProps('pairing_group')}
      />

      <MultiSelect
        data={players.map((p) => ({ value: `${p.id}`, label: p.name }))}
        label={t('team_member_select_title')}
        maxDropdownHeight={160}
        searchable
        mb="12rem"
        mt={12}
        limit={25}
        {...form.getInputProps('player_ids')}
      />
      <Button fullWidth style={{ marginTop: 10 }} color="green" type="submit">
        {t('save_button')}
      </Button>
    </form>
  );
}

export default function TeamCreateModal({
  tournament_id,
  swrTeamsResponse,
}: {
  tournament_id: number;
  swrTeamsResponse: SWRResponse<TeamsWithPlayersResponse>;
}) {
  const { t } = useTranslation();
  const [opened, setOpened] = useState(false);
  const clubsResponse = getClubs();
  const clubs: Club[] = clubsResponse.data?.data ?? [];
  return (
    <>
      <Modal opened={opened} onClose={() => setOpened(false)} title="Create Team">
        <Tabs defaultValue="single">
          <Tabs.List justify="center" grow>
            <Tabs.Tab value="single" leftSection={<IconUser size="0.8rem" />}>
              {t('single_team')}
            </Tabs.Tab>
            <Tabs.Tab value="multi" leftSection={<IconUsers size="0.8rem" />}>
              {t('multiple_teams')}
            </Tabs.Tab>
          </Tabs.List>

          <Tabs.Panel value="single" pt="xs">
            <SingleTeamTab
              swrTeamsResponse={swrTeamsResponse}
              tournament_id={tournament_id}
              setOpened={setOpened}
              clubs={clubs}
            />
          </Tabs.Panel>

          <Tabs.Panel value="multi" pt="xs">
            <MultiTeamTab
              swrTeamsResponse={swrTeamsResponse}
              tournament_id={tournament_id}
              setOpened={setOpened}
              clubs={clubs}
            />
          </Tabs.Panel>
        </Tabs>
      </Modal>

      <SaveButton
        onClick={() => setOpened(true)}
        leftSection={<IconUsersPlus size={24} />}
        title={t('add_team_button')}
        mb={0}
      />
    </>
  );
}
