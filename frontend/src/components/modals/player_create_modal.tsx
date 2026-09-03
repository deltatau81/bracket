import { Button, Checkbox, Modal, Tabs } from '@mantine/core';
import { useForm } from '@mantine/form';
import { IconUser, IconUserPlus, IconUsers } from '@tabler/icons-react';
import { useTranslation } from 'next-i18next';
import { useState } from 'react';
import { SWRResponse } from 'swr';

import { PlayerPosition } from '../../interfaces/player';
import { TeamInterface } from '../../interfaces/team';
import { createMultiplePlayers, createPlayer } from '../../services/player';
import { setPlayerTeam } from '../../services/team';
import SaveButton from '../buttons/save';
import { MultiPlayersInput } from '../forms/player_create_csv_input';
import { PlayerRosterFields } from '../forms/player_roster_fields';

function MultiPlayerTab({
  tournament_id,
  swrPlayersResponse,
  setOpened,
}: {
  tournament_id: number;
  swrPlayersResponse: SWRResponse;
  setOpened: any;
}) {
  const { t } = useTranslation();
  const form = useForm({
    initialValues: {
      names: '',
      active: true,
    },

    validate: {
      names: (value) => (value.length > 0 ? null : t('at_least_one_player_validation')),
    },
  });
  return (
    <form
      onSubmit={form.onSubmit(async (values) => {
        await createMultiplePlayers(tournament_id, values.names, values.active);
        await swrPlayersResponse.mutate();
        setOpened(false);
      })}
    >
      <MultiPlayersInput form={form} />

      <Checkbox
        mt="md"
        label={t('active_players_checkbox_label')}
        {...form.getInputProps('active', { type: 'checkbox' })}
      />
      <Button fullWidth style={{ marginTop: 10 }} color="green" type="submit">
        {t('save_players_button')}
      </Button>
    </form>
  );
}

function SinglePlayerTab({
  tournament_id,
  swrPlayersResponse,
  swrTeamsResponse,
  teams,
  setOpened,
}: {
  tournament_id: number;
  swrPlayersResponse: SWRResponse;
  swrTeamsResponse: SWRResponse;
  teams: TeamInterface[];
  setOpened: any;
}) {
  const { t } = useTranslation();
  const form = useForm({
    initialValues: {
      first_name: '',
      last_name: '',
      team_id: null as string | null,
      number: null as number | null,
      position: null as PlayerPosition | null,
      active: true,
    },
    validate: {
      first_name: (_value, values) =>
        `${values.first_name} ${values.last_name}`.trim().length > 0
          ? null
          : t('too_short_name_validation'),
    },
  });
  return (
    <form
      onSubmit={form.onSubmit(async (values) => {
        const name = `${values.first_name} ${values.last_name}`.trim();
        const response = await createPlayer(
          tournament_id,
          name,
          values.active,
          values.first_name || null,
          values.last_name || null
        );
        const playerId = response?.data?.data?.id;
        if (playerId == null) return;

        const teamUpdated = await setPlayerTeam(
          tournament_id,
          teams,
          playerId,
          values.team_id == null ? null : Number(values.team_id),
          values.team_id != null && typeof values.number === 'number' ? values.number : null,
          values.team_id == null ? null : values.position
        );
        if (!teamUpdated) return;
        await swrPlayersResponse.mutate();
        await swrTeamsResponse.mutate();
        setOpened(false);
      })}
    >
      <PlayerRosterFields form={form} teams={teams} />

      <Button fullWidth style={{ marginTop: 10 }} color="green" type="submit">
        {t('save_players_button')}
      </Button>
    </form>
  );
}

export default function PlayerCreateModal({
  tournament_id,
  swrPlayersResponse,
  swrTeamsResponse,
  teams,
}: {
  tournament_id: number;
  swrPlayersResponse: SWRResponse;
  swrTeamsResponse: SWRResponse;
  teams: TeamInterface[];
}) {
  const { t } = useTranslation();
  const [opened, setOpened] = useState(false);
  return (
    <>
      <Modal
        opened={opened}
        onClose={() => setOpened(false)}
        title={t('create_player_modal_title')}
      >
        <Tabs defaultValue="single">
          <Tabs.List justify="center" grow>
            <Tabs.Tab value="single" leftSection={<IconUser size="0.8rem" />}>
              {t('single_player_title')}
            </Tabs.Tab>
            <Tabs.Tab value="multi" leftSection={<IconUsers size="0.8rem" />}>
              {t('multiple_players_title')}
            </Tabs.Tab>
          </Tabs.List>

          <Tabs.Panel value="single" pt="xs">
            <SinglePlayerTab
              swrPlayersResponse={swrPlayersResponse}
              swrTeamsResponse={swrTeamsResponse}
              tournament_id={tournament_id}
              teams={teams}
              setOpened={setOpened}
            />
          </Tabs.Panel>

          <Tabs.Panel value="multi" pt="xs">
            <MultiPlayerTab
              swrPlayersResponse={swrPlayersResponse}
              tournament_id={tournament_id}
              setOpened={setOpened}
            />
          </Tabs.Panel>
        </Tabs>
      </Modal>

      <SaveButton
        onClick={() => setOpened(true)}
        leftSection={<IconUserPlus size={24} />}
        title={t('add_player_button')}
      />
    </>
  );
}
