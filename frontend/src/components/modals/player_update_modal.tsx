import { Button, Modal } from '@mantine/core';
import { useForm } from '@mantine/form';
import { BiEditAlt } from '@react-icons/all-files/bi/BiEditAlt';
import { useTranslation } from 'next-i18next';
import { useState } from 'react';
import { SWRResponse } from 'swr';

import { Player, PlayerPosition } from '../../interfaces/player';
import { TeamInterface } from '../../interfaces/team';
import { updatePlayer } from '../../services/player';
import { setPlayerTeam } from '../../services/team';
import { PlayerRosterFields } from '../forms/player_roster_fields';

export default function PlayerUpdateModal({
  tournament_id,
  player,
  swrPlayersResponse,
  swrTeamsResponse,
  teams,
  team,
}: {
  tournament_id: number;
  player: Player;
  swrPlayersResponse: SWRResponse;
  swrTeamsResponse: SWRResponse;
  teams: TeamInterface[];
  team: TeamInterface | null;
}) {
  const { t } = useTranslation();
  const [opened, setOpened] = useState(false);
  const getCurrentValues = () => {
    const teamPlayer = team?.players.find((member) => member.id === player.id);
    return {
      first_name: player.first_name || '',
      last_name: player.last_name || '',
      team_id: team == null ? null : `${team.id}`,
      number: teamPlayer?.number ?? null,
      position: (teamPlayer?.position ?? null) as PlayerPosition | null,
      active: player.active,
    };
  };

  const form = useForm({
    initialValues: getCurrentValues(),
    validate: {
      first_name: (_value, values) => {
        const hasStructuredName =
          `${values.first_name} ${values.last_name}`.trim().length > 0;
        const mayKeepLegacyName = player.first_name == null && player.last_name == null;
        return hasStructuredName || mayKeepLegacyName
          ? null
          : t('too_short_name_validation');
      },
    },
  });

  const openModal = () => {
    const currentValues = getCurrentValues();
    form.setInitialValues(currentValues);
    form.setValues(currentValues);
    form.resetDirty(currentValues);
    form.clearErrors();
    setOpened(true);
  };

  return (
    <>
      <Modal opened={opened} onClose={() => setOpened(false)} title={t('edit_player')}>
        <form
          onSubmit={form.onSubmit(async (values) => {
            const structuredName = `${values.first_name} ${values.last_name}`.trim();
            const keepsLegacyName =
              player.first_name == null && player.last_name == null && structuredName.length === 0;
            const response = await updatePlayer(
              tournament_id,
              player.id,
              structuredName || player.name,
              values.active,
              null,
              keepsLegacyName ? undefined : values.first_name || null,
              keepsLegacyName ? undefined : values.last_name || null
            );
            if (response == null) return;

            const teamUpdated = await setPlayerTeam(
              tournament_id,
              teams,
              player.id,
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
          <PlayerRosterFields
            form={form}
            teams={teams}
            legacyName={
              player.first_name == null && player.last_name == null ? player.name : undefined
            }
          />

          <Button fullWidth style={{ marginTop: 10 }} color="green" type="submit">
            {t('save_button')}
          </Button>
        </form>
      </Modal>

      <Button
        color="green"
        size="xs"
        style={{ marginRight: 10 }}
        onClick={openModal}
        leftSection={<BiEditAlt size={20} />}
      >
        {t('edit_player')}
      </Button>
    </>
  );
}
