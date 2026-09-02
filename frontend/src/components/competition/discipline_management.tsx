import { Button, Group, Modal, Select, Stack, TextInput, Textarea } from '@mantine/core';
import { useForm } from '@mantine/form';
import { useDisclosure } from '@mantine/hooks';
import React, { useState } from 'react';

import {
  CompetitionDisciplineInterface,
  CompetitionMetricType,
} from '../../interfaces/competition';
import {
  createCompetitionDiscipline,
  deleteCompetitionDiscipline,
  updateCompetitionDiscipline,
} from '../../services/competition';

const metricTypeOptions = [
  { value: 'TIME', label: 'Zeit – niedrigste Zeit gewinnt' },
  { value: 'COUNT', label: 'Anzahl – höchste Anzahl gewinnt' },
  { value: 'RATIO', label: 'Quote – höchste Erfolgsquote gewinnt' },
  { value: 'MANUAL', label: 'Manuelle Platzierung' },
];

interface DisciplineFormValues {
  name: string;
  description: string;
  metric_type: CompetitionMetricType;
}

function DisciplineModal({
  tournamentId,
  competitionId,
  discipline,
  sortOrder,
  mutateDisciplines,
}: {
  tournamentId: number;
  competitionId: number;
  discipline?: CompetitionDisciplineInterface;
  sortOrder: number;
  mutateDisciplines: () => Promise<unknown>;
}) {
  const [opened, { open, close }] = useDisclosure(false);
  const [saving, setSaving] = useState(false);
  const form = useForm<DisciplineFormValues>({
    initialValues: {
      name: discipline?.name ?? '',
      description: discipline?.description ?? '',
      metric_type: discipline?.metric_type ?? 'TIME',
    },
    validate: {
      name: (value) => (value.trim().length === 0 ? 'Name ist erforderlich' : null),
    },
  });

  function openModal() {
    form.setValues({
      name: discipline?.name ?? '',
      description: discipline?.description ?? '',
      metric_type: discipline?.metric_type ?? 'TIME',
    });
    open();
  }

  async function submit(values: DisciplineFormValues) {
    const data = {
      name: values.name.trim(),
      description: values.description.trim() === '' ? null : values.description.trim(),
      metric_type: values.metric_type,
      sort_order: discipline?.sort_order ?? sortOrder,
    };

    setSaving(true);
    try {
      if (discipline == null) {
        await createCompetitionDiscipline(tournamentId, competitionId, data);
      } else {
        await updateCompetitionDiscipline(tournamentId, competitionId, discipline.id, data);
      }
      await mutateDisciplines();
      close();
    } finally {
      setSaving(false);
    }
  }

  return (
    <>
      <Button size="xs" variant={discipline == null ? 'filled' : 'light'} onClick={openModal}>
        {discipline == null ? 'Disziplin hinzufügen' : 'Bearbeiten'}
      </Button>
      <Modal
        opened={opened}
        onClose={close}
        title={discipline == null ? 'Disziplin hinzufügen' : 'Disziplin bearbeiten'}
      >
        <form onSubmit={form.onSubmit(submit)}>
          <Stack>
            <TextInput label="Name" required {...form.getInputProps('name')} />
            <Textarea
              label="Beschreibung"
              minRows={3}
              {...form.getInputProps('description')}
            />
            <Select
              label="Auswertungstyp"
              data={metricTypeOptions}
              value={form.values.metric_type}
              allowDeselect={false}
              required
              onChange={(value) => {
                if (value != null) {
                  form.setFieldValue('metric_type', value as CompetitionMetricType);
                }
              }}
            />
            <Group justify="flex-end">
              <Button variant="default" onClick={close}>
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

export function AddDisciplineButton({
  tournamentId,
  competitionId,
  sortOrder,
  mutateDisciplines,
}: {
  tournamentId: number;
  competitionId: number;
  sortOrder: number;
  mutateDisciplines: () => Promise<unknown>;
}) {
  return (
    <DisciplineModal
      tournamentId={tournamentId}
      competitionId={competitionId}
      sortOrder={sortOrder}
      mutateDisciplines={mutateDisciplines}
    />
  );
}

export function DisciplineActions({
  tournamentId,
  competitionId,
  discipline,
  mutateDisciplines,
}: {
  tournamentId: number;
  competitionId: number;
  discipline: CompetitionDisciplineInterface;
  mutateDisciplines: () => Promise<unknown>;
}) {
  const [deleting, setDeleting] = useState(false);

  async function remove() {
    if (!window.confirm(`Disziplin "${discipline.name}" wirklich löschen?`)) return;
    setDeleting(true);
    try {
      await deleteCompetitionDiscipline(tournamentId, competitionId, discipline.id);
      await mutateDisciplines();
    } finally {
      setDeleting(false);
    }
  }

  return (
    <Group gap="xs">
      <DisciplineModal
        tournamentId={tournamentId}
        competitionId={competitionId}
        discipline={discipline}
        sortOrder={discipline.sort_order}
        mutateDisciplines={mutateDisciplines}
      />
      <Button size="xs" color="red" variant="light" loading={deleting} onClick={remove}>
        Löschen
      </Button>
    </Group>
  );
}

