import { Accordion, Alert, Badge, Group, Loader, Stack, Text } from '@mantine/core';
import {
  AddDisciplineButton,
  DisciplineActions,
} from '@components/competition/discipline_management';
import { getCompetitionDisciplines } from '@services/adapter';

export default function CompetitionDisciplines({
  tournamentId,
  competitionId,
}: {
  tournamentId: number;
  competitionId: number;
}) {
  const response = getCompetitionDisciplines(tournamentId, competitionId);
  if (response.error)
    return <Alert color="red">Die Disziplinen konnten nicht geladen werden.</Alert>;
  if (!response.data) return <Loader />;
  const disciplines = [...response.data.data].sort(
    (a, b) => a.sort_order - b.sort_order || a.id - b.id,
  );
  const nextSortOrder =
    disciplines.length === 0 ? 0 : Math.max(...disciplines.map((item) => item.sort_order)) + 1;
  return (
    <Stack>
      <Group justify="flex-end">
        <AddDisciplineButton
          tournamentId={tournamentId}
          competitionId={competitionId}
          sortOrder={nextSortOrder}
          mutateDisciplines={response.mutate}
        />
      </Group>
      {disciplines.length === 0 ? (
        <Text c="dimmed">Noch keine Disziplinen angelegt.</Text>
      ) : (
        <Accordion variant="separated" multiple>
          {disciplines.map((discipline) => (
            <Accordion.Item key={discipline.id} value={String(discipline.id)}>
              <Accordion.Control>
                <Group gap="xs">
                  <Text fw={500}>{discipline.name}</Text>
                  <Badge size="xs" variant="light">
                    {discipline.metric_type}
                  </Badge>
                </Group>
              </Accordion.Control>
              <Accordion.Panel>
                <Stack gap="sm">
                  {discipline.description && (
                    <Text size="sm" c="dimmed">
                      {discipline.description}
                    </Text>
                  )}
                  <Group justify="flex-end">
                    <DisciplineActions
                      tournamentId={tournamentId}
                      competitionId={competitionId}
                      discipline={discipline}
                      mutateDisciplines={response.mutate}
                    />
                  </Group>
                </Stack>
              </Accordion.Panel>
            </Accordion.Item>
          ))}
        </Accordion>
      )}
    </Stack>
  );
}
