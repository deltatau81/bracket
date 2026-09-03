import {
  Alert,
  Button,
  Card,
  Grid,
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
import { serverSideTranslations } from 'next-i18next/serverSideTranslations';
import React from 'react';

import CompetitionDisciplines from '../../../components/competition/competition_disciplines';
import {
  getTournamentIdFromRouter,
  responseIsValid,
} from '../../../components/utils/util';
import { CompetitionInterface } from '../../../interfaces/competition';
import { getCompetitions } from '../../../services/adapter';
import {
  createCompetition,
  deleteCompetition,
  updateCompetition,
} from '../../../services/competition';
import TournamentLayout from '../_tournament_layout';

function CompetitionCreateModal({
  tournament_id,
  swrCompetitionsResponse,
}: {
  tournament_id: number;
  swrCompetitionsResponse: any;
}) {
  const [opened, { open, close }] = useDisclosure(false);

  const form = useForm({
    initialValues: {
      name: 'Skills Competition',
      description: '',
      start_time: new Date(),
      duration_minutes: 60,
    },

    validate: {
      name: (value) =>
        value.trim().length < 1
          ? 'Name ist erforderlich'
          : null,

      duration_minutes: (value) =>
        value < 1
          ? 'Dauer muss mindestens 1 Minute betragen'
          : null,
    },
  });

  async function submit(values: typeof form.values) {
    await createCompetition(
      tournament_id,
      {
        name: values.name,
        description:
          values.description.trim() === ''
            ? null
            : values.description,
        start_time: values.start_time.toISOString(),
        duration_minutes: values.duration_minutes,
        court_id: null,
      }
    );

    await swrCompetitionsResponse.mutate();

    close();
  }

  return (
    <>
      <Modal
        opened={opened}
        onClose={close}
        title="Competition anlegen"
        size="lg"
      >
        <form onSubmit={form.onSubmit(submit)}>
          <Stack>
            <TextInput
              label="Name"
              placeholder="Skills Competition"
              required
              {...form.getInputProps('name')}
            />

            <Textarea
              label="Beschreibung"
              placeholder="Technikwettbewerbe während des Turniers"
              minRows={3}
              {...form.getInputProps('description')}
            />

            <DateTimePicker
              label="Startzeit"
              required
              {...form.getInputProps('start_time')}
            />

            <NumberInput
              label="Dauer in Minuten"
              min={1}
              required
              {...form.getInputProps('duration_minutes')}
            />

            <Group justify="flex-end">
              <Button
                variant="default"
                onClick={close}
              >
                Abbrechen
              </Button>

              <Button type="submit">
                Competition anlegen
              </Button>
            </Group>
          </Stack>
        </form>
      </Modal>

      <Button onClick={open}>
        + Competition anlegen
      </Button>
    </>
  );
}

function CompetitionEditModal({
  tournament_id,
  competition,
  swrCompetitionsResponse,
}: {
  tournament_id: number;
  competition: CompetitionInterface;
  swrCompetitionsResponse: any;
}) {
  const [opened, { open, close }] = useDisclosure(false);

  const form = useForm({
    initialValues: {
      name: competition.name,
      description: competition.description || '',
      start_time: new Date(competition.start_time),
      duration_minutes: competition.duration_minutes,
    },

    validate: {
      name: (value) =>
        value.trim().length < 1
          ? 'Name ist erforderlich'
          : null,

      duration_minutes: (value) =>
        value < 1
          ? 'Dauer muss mindestens 1 Minute betragen'
          : null,
    },
  });

  async function submit(values: typeof form.values) {
    await updateCompetition(
      tournament_id,
      competition.id,
      {
        name: values.name,
        description:
          values.description.trim() === ''
            ? null
            : values.description,
        start_time: values.start_time.toISOString(),
        duration_minutes: values.duration_minutes,
        court_id: competition.court_id,
      }
    );

    await swrCompetitionsResponse.mutate();

    close();
  }

  return (
    <>
      <Modal
        opened={opened}
        onClose={close}
        title="Competition bearbeiten"
        size="lg"
      >
        <form onSubmit={form.onSubmit(submit)}>
          <Stack>
            <TextInput
              label="Name"
              placeholder="Skills Competition"
              required
              {...form.getInputProps('name')}
            />

            <Textarea
              label="Beschreibung"
              placeholder="Technikwettbewerbe während des Turniers"
              minRows={3}
              {...form.getInputProps('description')}
            />

            <DateTimePicker
              label="Startzeit"
              required
              {...form.getInputProps('start_time')}
            />

            <NumberInput
              label="Dauer in Minuten"
              min={1}
              required
              {...form.getInputProps('duration_minutes')}
            />

            <Group justify="flex-end">
              <Button
                variant="default"
                onClick={close}
              >
                Abbrechen
              </Button>

              <Button type="submit">
                Competition speichern
              </Button>
            </Group>
          </Stack>
        </form>
      </Modal>

      <Button onClick={open} variant="light">
        Bearbeiten
      </Button>
    </>
  );
}

export default function Competitions() {
  const { tournamentData } =
    getTournamentIdFromRouter();

  const swrCompetitionsResponse =
    getCompetitions(tournamentData.id);

  if (swrCompetitionsResponse.error != null) {
    return (
      <TournamentLayout
        tournament_id={tournamentData.id}
      >
        <Title>Competitions</Title>

        <Alert
          color="red"
          mt="md"
          title="Fehler"
        >
          Die Competitions konnten nicht geladen werden.
        </Alert>
      </TournamentLayout>
    );
  }

  if (!responseIsValid(swrCompetitionsResponse)) {
    return (
      <TournamentLayout
        tournament_id={tournamentData.id}
      >
        <Title>Competitions</Title>
        <Loader mt="md" />
      </TournamentLayout>
    );
  }

  const competitions: CompetitionInterface[] =
    swrCompetitionsResponse.data.data;

  return (
    <TournamentLayout
      tournament_id={tournamentData.id}
    >
      <Grid
        justify="space-between"
        mb="1rem"
      >
        <Grid.Col span="auto">
          <Title>
            Competitions
          </Title>
        </Grid.Col>

        <Grid.Col span="content">
          <CompetitionCreateModal
            tournament_id={tournamentData.id}
            swrCompetitionsResponse={
              swrCompetitionsResponse
            }
          />
        </Grid.Col>
      </Grid>

      {competitions.length === 0 ? (
        <Alert
          color="blue"
          title="Noch keine Competition"
        >
          Für dieses Turnier wurde noch keine
          Competition angelegt.
        </Alert>
      ) : (
        <Stack>
          {competitions.map(
            (competition: CompetitionInterface) => (
              <Card
                key={competition.id}
                withBorder
                radius="md"
                padding="lg"
              >
                <Group
                  justify="space-between"
                  align="flex-start"
                >
                  <div>
                    <Title order={3}>
                      {competition.name}
                    </Title>

                    {competition.description != null &&
                    competition.description !== '' && (
                      <Text mt="xs">
                        {competition.description}
                      </Text>
                    )}

                    <Text
                      size="sm"
                      c="dimmed"
                      mt="md"
                    >
                      Start:{' '}
                      {new Date(
                        competition.start_time
                      ).toLocaleString()}
                    </Text>

                    <Text
                      size="sm"
                      c="dimmed"
                    >
                      Dauer:{' '}
                      {competition.duration_minutes}{' '}
                      Minuten
                    </Text>
                  </div>

                  <Group>
                    <CompetitionEditModal
                      tournament_id={tournamentData.id}
                      competition={competition}
                      swrCompetitionsResponse={
                        swrCompetitionsResponse
                      }
                    />

                    <Button
                      color="red"
                      variant="light"
                      onClick={async () => {
                        if (
                          !window.confirm(
                            `Competition "${competition.name}" wirklich löschen?`
                          )
                        ) {
                          return;
                        }

                        await deleteCompetition(
                          tournamentData.id,
                          competition.id
                        );

                        await swrCompetitionsResponse.mutate();
                      }}
                    >
                      Löschen
                    </Button>
                  </Group>
                </Group>

                <Stack mt="lg">
                  <CompetitionDisciplines
                    tournamentId={tournamentData.id}
                    competitionId={competition.id}
                    mode="manage"
                  />
                </Stack>
              </Card>
            )
          )}
        </Stack>
      )}
    </TournamentLayout>
  );
}

export const getServerSideProps =
  async ({
    locale,
  }: {
    locale: string;
  }) => ({
    props: {
      ...(await serverSideTranslations(
        locale,
        ['common']
      )),
    },
  });
