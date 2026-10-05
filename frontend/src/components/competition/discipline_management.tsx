import { Alert, Button, Group, Modal, Select, Stack, TextInput, Textarea } from '@mantine/core';
import { useForm } from '@mantine/form';
import { useDisclosure } from '@mantine/hooks';
import { useState } from 'react';
import { CompetitionDiscipline, CompetitionDisciplineBody, CompetitionMetricType } from '@openapi';
import {
  createCompetitionDiscipline,
  deleteCompetitionDiscipline,
  updateCompetitionDiscipline,
} from '@services/competition';

const metricTypeOptions: { value: CompetitionMetricType; label: string }[] = [
  { value: 'TIME', label: 'Zeit – niedrigste Zeit gewinnt' },
  { value: 'COUNT', label: 'Anzahl – höchste Anzahl gewinnt' },
  { value: 'RATIO', label: 'Quote – höchste Erfolgsquote gewinnt' },
  { value: 'MANUAL', label: 'Manuelle Platzierung' },
];
type ManagementProps = {
  tournamentId: number;
  competitionId: number;
  mutateDisciplines: () => Promise<unknown>;
};
function DisciplineModal({
  tournamentId,
  competitionId,
  discipline,
  sortOrder,
  mutateDisciplines,
}: ManagementProps & { discipline?: CompetitionDiscipline; sortOrder: number }) {
  const [opened, { open, close }] = useDisclosure(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(false);
  const initialValues = {
    name: discipline?.name ?? '',
    description: discipline?.description ?? '',
    metric_type: discipline?.metric_type ?? 'TIME',
  };
  const form = useForm<
    Pick<CompetitionDisciplineBody, 'name' | 'metric_type'> & { description: string }
  >({
    initialValues,
    validate: { name: (value) => (value.trim() === '' ? 'Name ist erforderlich' : null) },
  });
  async function submit(values: typeof form.values) {
    const body: CompetitionDisciplineBody = {
      name: values.name.trim(),
      description: values.description.trim() || null,
      metric_type: values.metric_type,
      sort_order: discipline?.sort_order ?? sortOrder,
    };
    setSaving(true);
    setError(false);
    try {
      if (discipline == null) await createCompetitionDiscipline(tournamentId, competitionId, body);
      else await updateCompetitionDiscipline(tournamentId, competitionId, discipline.id, body);
      await mutateDisciplines();
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
        size="xs"
        variant={discipline == null ? 'filled' : 'light'}
        onClick={() => {
          form.setValues(initialValues);
          form.clearErrors();
          setError(false);
          open();
        }}
      >
        {discipline == null ? 'Disziplin hinzufügen' : 'Bearbeiten'}
      </Button>
      <Modal
        opened={opened}
        onClose={() => {
          if (!saving) close();
        }}
        title={discipline == null ? 'Disziplin hinzufügen' : 'Disziplin bearbeiten'}
      >
        <form onSubmit={form.onSubmit(submit)}>
          <Stack>
            {error && <Alert color="red">Die Disziplin konnte nicht gespeichert werden.</Alert>}
            <TextInput label="Name" required disabled={saving} {...form.getInputProps('name')} />
            <Textarea
              label="Beschreibung"
              minRows={3}
              disabled={saving}
              {...form.getInputProps('description')}
            />
            <Select
              label="Auswertungstyp"
              data={metricTypeOptions}
              value={form.values.metric_type}
              allowDeselect={false}
              required
              disabled={saving}
              onChange={(value) => {
                const option = metricTypeOptions.find((item) => item.value === value);
                if (option) form.setFieldValue('metric_type', option.value);
              }}
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
export function AddDisciplineButton(props: ManagementProps & { sortOrder: number }) {
  return <DisciplineModal {...props} />;
}
export function DisciplineActions({
  tournamentId,
  competitionId,
  discipline,
  mutateDisciplines,
}: ManagementProps & { discipline: CompetitionDiscipline }) {
  const [deleting, setDeleting] = useState(false);
  const [error, setError] = useState(false);
  async function remove() {
    if (!window.confirm(`Disziplin "${discipline.name}" wirklich löschen?`)) return;
    setDeleting(true);
    setError(false);
    try {
      await deleteCompetitionDiscipline(tournamentId, competitionId, discipline.id);
      await mutateDisciplines();
    } catch {
      setError(true);
    } finally {
      setDeleting(false);
    }
  }
  return (
    <Stack gap="xs">
      {error && <Alert color="red">Die Disziplin konnte nicht gelöscht werden.</Alert>}
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
    </Stack>
  );
}
