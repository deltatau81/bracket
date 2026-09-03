import { Checkbox, NumberInput, Select, TextInput } from '@mantine/core';

import { TeamInterface } from '../../interfaces/team';

export const playerPositionOptions = [
  { value: 'GK', label: 'Torhüter' },
  { value: 'D', label: 'Verteidiger' },
  { value: 'F', label: 'Stürmer' },
];

export function PlayerRosterFields({
  form,
  teams,
  legacyName,
}: {
  form: any;
  teams: TeamInterface[];
  legacyName?: string;
}) {
  const hasTeam = form.values.team_id != null;

  return (
    <>
      {legacyName != null && (
        <TextInput label="Bisheriger Anzeigename" value={legacyName} readOnly mb="sm" />
      )}
      <TextInput label="Vorname" {...form.getInputProps('first_name')} />
      <TextInput label="Nachname" mt="sm" {...form.getInputProps('last_name')} />
      <Select
        clearable
        searchable
        label="Mannschaft"
        placeholder="Keine Mannschaft"
        data={teams.map((team) => ({ value: `${team.id}`, label: team.name }))}
        mt="sm"
        {...form.getInputProps('team_id')}
      />
      <NumberInput
        disabled={!hasTeam}
        label="Trikotnummer"
        min={0}
        mt="sm"
        {...form.getInputProps('number')}
      />
      <Select
        clearable
        disabled={!hasTeam}
        label="Position"
        data={playerPositionOptions}
        mt="sm"
        {...form.getInputProps('position')}
      />
      <Checkbox
        mt="md"
        label="Aktiv"
        {...form.getInputProps('active', { type: 'checkbox' })}
      />
    </>
  );
}
