import {
  Button,
  Card,
  Fieldset,
  Group,
  Image,
  Modal,
  NumberInput,
  Select,
  Stack,
  Text,
  TextInput,
} from '@mantine/core';
import { useForm } from '@mantine/form';
import { showNotification } from '@mantine/notifications';
import { IconPencil, IconPlus, IconTrash } from '@tabler/icons-react';
import { AxiosError } from 'axios';
import { useState } from 'react';
import { SWRResponse } from 'swr';

import { TournamentSponsor, TournamentSponsorPosition } from '../../interfaces/tournament_sponsor';
import { getBaseApiUrl, handleRequestError } from '../../services/adapter';
import {
  createTournamentSponsor,
  deleteTournamentSponsor,
  updateTournamentSponsor,
  uploadTournamentSponsorLogo,
} from '../../services/tournament_sponsor';
import { DropzoneButton } from '../utils/file_upload';

function SponsorLogo({ sponsor }: { sponsor: TournamentSponsor }) {
  if (!sponsor.logo_path) return null;
  return (
    <Image
      key={sponsor.logo_path}
      src={`${getBaseApiUrl()}/${sponsor.logo_path.replace(/^\/+/, '')}?v=${encodeURIComponent(
        sponsor.logo_path
      )}`}
      alt={sponsor.name}
      fit="contain"
      h={80}
      w={140}
    />
  );
}

function SponsorModal({
  tournamentId,
  sponsor,
  sponsorsResponse,
}: {
  tournamentId: number;
  sponsor?: TournamentSponsor;
  sponsorsResponse: SWRResponse;
}) {
  const [opened, setOpened] = useState(false);
  const [logoFile, setLogoFile] = useState<File | null>(null);
  const form = useForm({
    initialValues: {
      name: sponsor?.name ?? '',
      url: sponsor?.url ?? '',
      position: (sponsor?.position ?? 'LEFT') as TournamentSponsorPosition,
      sort_order: sponsor?.sort_order ?? 0,
    },
    validate: {
      name: (value) => (value.trim().length > 0 ? null : 'Name ist erforderlich'),
    },
  });

  const close = () => {
    setOpened(false);
    setLogoFile(null);
  };

  const open = () => {
    form.setValues({
      name: sponsor?.name ?? '',
      url: sponsor?.url ?? '',
      position: sponsor?.position ?? 'LEFT',
      sort_order: sponsor?.sort_order ?? 0,
    });
    form.clearErrors();
    setLogoFile(null);
    setOpened(true);
  };

  return (
    <>
      <Modal
        opened={opened}
        onClose={close}
        title={sponsor ? 'Sponsor bearbeiten' : 'Sponsor hinzufügen'}
      >
        <form
          onSubmit={form.onSubmit(async (values) => {
            if (sponsor == null && logoFile == null) {
              showNotification({
                color: 'red',
                title: 'Logo fehlt',
                message: 'Bitte eine Logo-Datei auswählen.',
              });
              return;
            }

            let createdSponsorId: number | null = null;
            try {
              const body = {
                ...values,
                name: values.name.trim(),
                url: values.url.trim() || null,
                logo_path: sponsor?.logo_path ?? '',
              };
              const saved = sponsor
                ? await updateTournamentSponsor(tournamentId, sponsor.id, body)
                : await createTournamentSponsor(tournamentId, body);
              const sponsorId = sponsor?.id ?? saved.data.data.id;
              if (sponsor == null) createdSponsorId = sponsorId;

              if (logoFile != null) {
                await uploadTournamentSponsorLogo(tournamentId, sponsorId, logoFile);
              }

              await sponsorsResponse.mutate();
              showNotification({
                color: 'green',
                title: 'Sponsor gespeichert',
                message: `${values.name} wurde gespeichert.`,
              });
              close();
            } catch (error) {
              if (sponsor == null && createdSponsorId != null) {
                try {
                  await deleteTournamentSponsor(tournamentId, createdSponsorId);
                  await sponsorsResponse.mutate();
                } catch {
                  // Preserve and display the original upload error.
                }
              }
              handleRequestError(error as AxiosError);
            }
          })}
        >
          <Stack>
            <TextInput withAsterisk label="Name" {...form.getInputProps('name')} />
            <TextInput label="URL" placeholder="https://…" {...form.getInputProps('url')} />
            <Select
              withAsterisk
              label="Position"
              data={['LEFT', 'RIGHT']}
              allowDeselect={false}
              {...form.getInputProps('position')}
            />
            <NumberInput label="Sortierung" {...form.getInputProps('sort_order')} />
            <DropzoneButton
              tournamentId={tournamentId}
              swrResponse={sponsorsResponse}
              variant="sponsor"
              onFileSelect={setLogoFile}
              selectedFileName={
                logoFile == null ? undefined : `Neue Datei ausgewählt: ${logoFile.name}`
              }
            />
            {sponsor ? <SponsorLogo sponsor={sponsor} /> : null}
            <Button type="submit" color="green">
              Speichern
            </Button>
          </Stack>
        </form>
      </Modal>
      <Button
        size={sponsor ? 'xs' : 'sm'}
        leftSection={sponsor ? <IconPencil size={16} /> : <IconPlus size={18} />}
        onClick={open}
      >
        {sponsor ? 'Bearbeiten' : 'Neuer Sponsor'}
      </Button>
    </>
  );
}

export default function SponsorSettings({
  tournamentId,
  sponsorsResponse,
}: {
  tournamentId: number;
  sponsorsResponse: SWRResponse;
}) {
  const sponsors: TournamentSponsor[] = sponsorsResponse.data?.data ?? [];

  return (
    <Fieldset legend="Sponsoren" mt="xl" radius="md">
      <Group justify="flex-end" mb="md">
        <SponsorModal tournamentId={tournamentId} sponsorsResponse={sponsorsResponse} />
      </Group>
      <Stack>
        {sponsors.map((sponsor) => (
          <Card key={sponsor.id} withBorder>
            <Group justify="space-between" align="center">
              <SponsorLogo sponsor={sponsor} />
              <div style={{ flex: 1 }}>
                <Text fw={700}>{sponsor.name}</Text>
                <Text size="sm">{sponsor.url || 'Keine URL'}</Text>
                <Text size="sm">
                  {sponsor.position} · Sortierung {sponsor.sort_order}
                </Text>
              </div>
              <Group>
                <SponsorModal
                  tournamentId={tournamentId}
                  sponsor={sponsor}
                  sponsorsResponse={sponsorsResponse}
                />
                <Button
                  size="xs"
                  color="red"
                  variant="outline"
                  leftSection={<IconTrash size={16} />}
                  onClick={async () => {
                    try {
                      await deleteTournamentSponsor(tournamentId, sponsor.id);
                      await sponsorsResponse.mutate();
                      showNotification({
                        color: 'green',
                        title: 'Sponsor gelöscht',
                        message: `${sponsor.name} wurde gelöscht.`,
                      });
                    } catch (error) {
                      handleRequestError(error as AxiosError);
                    }
                  }}
                >
                  Löschen
                </Button>
              </Group>
            </Group>
          </Card>
        ))}
        {sponsors.length === 0 ? <Text c="dimmed">Noch keine Sponsoren vorhanden.</Text> : null}
      </Stack>
    </Fieldset>
  );
}
