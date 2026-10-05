import {
  Alert,
  Button,
  Card,
  Group,
  Loader,
  Modal,
  NumberInput,
  Stack,
  Text,
  TextInput,
  Textarea,
  Title,
} from '@mantine/core';
import { DateTimePicker } from '@mantine/dates';
import { useForm } from '@mantine/form';
import { useDisclosure } from '@mantine/hooks';
import dayjs from 'dayjs';
import { useState } from 'react';
import { SWRResponse } from 'swr';
import CompetitionDisciplines from '@components/competition/competition_disciplines';
import { getTournamentIdFromRouter } from '@components/utils/util';
import { Competition, CompetitionBody, CompetitionsResponse } from '@openapi';
import TournamentLayout from '@pages/tournaments/_tournament_layout';
import { getCompetitions } from '@services/adapter';
import { createCompetition, deleteCompetition, updateCompetition } from '@services/competition';

type CompetitionModalProps = { tournamentId: number; response: SWRResponse<CompetitionsResponse> };
function CompetitionModal({
  tournamentId,
  response,
  competition,
}: CompetitionModalProps & { competition?: Competition }) {
  const [opened, { open, close }] = useDisclosure(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(false);
  function initialValues() {
    return {
      name: competition?.name ?? 'Skills Competition',
      description: competition?.description ?? '',
      start_time: dayjs(competition?.start_time ?? new Date()).format('YYYY-MM-DD HH:mm:ss'),
      duration_minutes: competition?.duration_minutes ?? 60,
    };
  }
  const form = useForm<{
    name: string;
    description: string;
    start_time: string | null;
    duration_minutes: string | number;
  }>({
    initialValues: initialValues(),
    validate: {
      name: (value) => (value.trim() === '' ? 'Name ist erforderlich' : null),
      start_time: (value) =>
        value == null || !dayjs(value).isValid() ? 'Startzeit ist erforderlich' : null,
      duration_minutes: (value) =>
        typeof value !== 'number' || !Number.isInteger(value) || value < 1
          ? 'Dauer muss mindestens 1 ganze Minute betragen'
          : null,
    },
  });
  async function submit(values: typeof form.values) {
    setSaving(true);
    setError(false);
    try {
      const body: CompetitionBody = {
        name: values.name.trim(),
        description: values.description.trim() || null,
        start_time: dayjs(values.start_time).toISOString(),
        duration_minutes: Number(values.duration_minutes),
        court_id: competition?.court_id ?? null,
      };
      if (competition) await updateCompetition(tournamentId, competition.id, body);
      else await createCompetition(tournamentId, body);
      await response.mutate();
      close();
    } catch {
      setError(true);
    } finally {
      setSaving(false);
    }
  }
  return (
    <>
      <Button
        variant={competition ? 'light' : 'filled'}
        onClick={() => {
          form.setValues(initialValues());
          form.clearErrors();
          setError(false);
          open();
        }}
      >
        {competition ? 'Bearbeiten' : '+ Competition anlegen'}
      </Button>
      <Modal
        opened={opened}
        onClose={() => {
          if (!saving) close();
        }}
        size="lg"
        title={competition ? 'Competition bearbeiten' : 'Competition anlegen'}
      >
        <form onSubmit={form.onSubmit(submit)}>
          <Stack>
            {error && <Alert color="red">Die Competition konnte nicht gespeichert werden.</Alert>}
            <TextInput label="Name" required disabled={saving} {...form.getInputProps('name')} />
            <Textarea
              label="Beschreibung"
              minRows={3}
              disabled={saving}
              {...form.getInputProps('description')}
            />
            <DateTimePicker
              label="Startzeit"
              required
              disabled={saving}
              {...form.getInputProps('start_time')}
            />
            <NumberInput
              label="Dauer in Minuten"
              min={1}
              allowDecimal={false}
              required
              disabled={saving}
              {...form.getInputProps('duration_minutes')}
            />
            <Group justify="flex-end">
              <Button variant="default" disabled={saving} onClick={close}>
                Abbrechen
              </Button>
              <Button type="submit" loading={saving}>
                Speichern
              </Button>
            </Group>
          </Stack>
        </form>
      </Modal>
    </>
  );
}
function CompetitionCreateModal(props: CompetitionModalProps) {
  return <CompetitionModal {...props} />;
}
function CompetitionEditModal(props: CompetitionModalProps & { competition: Competition }) {
  return <CompetitionModal {...props} />;
}
function CompetitionCard({
  tournamentId,
  response,
  competition,
}: CompetitionModalProps & { competition: Competition }) {
  const [deleting, setDeleting] = useState(false);
  const [error, setError] = useState(false);
  async function remove() {
    if (!window.confirm(`Competition "${competition.name}" wirklich löschen?`)) return;
    setDeleting(true);
    setError(false);
    try {
      await deleteCompetition(tournamentId, competition.id);
      await response.mutate();
    } catch {
      setError(true);
    } finally {
      setDeleting(false);
    }
  }
  return (
    <Card withBorder radius="md" padding="lg">
      <Stack>
        <Group justify="space-between" align="flex-start">
          <div>
            <Title order={3}>{competition.name}</Title>
            {competition.description && <Text mt="xs">{competition.description}</Text>}
            <Text size="sm" c="dimmed" mt="md">
              Start: {new Date(competition.start_time).toLocaleString()}
            </Text>
            <Text size="sm" c="dimmed">
              Dauer: {competition.duration_minutes} Minuten
            </Text>
          </div>
          <Group>
            <CompetitionEditModal
              tournamentId={tournamentId}
              response={response}
              competition={competition}
            />
            <Button color="red" variant="light" loading={deleting} onClick={remove}>
              Löschen
            </Button>
          </Group>
        </Group>
        {error && <Alert color="red">Die Competition konnte nicht gelöscht werden.</Alert>}
        <CompetitionDisciplines tournamentId={tournamentId} competitionId={competition.id} />
      </Stack>
    </Card>
  );
}
export default function CompetitionsPage() {
  const { tournamentData } = getTournamentIdFromRouter();
  const response = getCompetitions(tournamentData.id);
  return (
    <TournamentLayout tournament_id={tournamentData.id}>
      <Group justify="space-between" mb="md">
        <Title>Technikwettbewerb</Title>
        {response.data && !response.error && (
          <CompetitionCreateModal tournamentId={tournamentData.id} response={response} />
        )}
      </Group>
      {response.error ? (
        <Alert color="red">Die Competitions konnten nicht geladen werden.</Alert>
      ) : !response.data ? (
        <Loader />
      ) : response.data.data.length === 0 ? (
        <Alert color="blue" title="Noch keine Competition">
          Für dieses Turnier wurde noch keine Competition angelegt.
        </Alert>
      ) : (
        <Stack>
          {response.data.data.map((competition) => (
            <CompetitionCard
              key={competition.id}
              tournamentId={tournamentData.id}
              response={response}
              competition={competition}
            />
          ))}
        </Stack>
      )}
    </TournamentLayout>
  );
}
