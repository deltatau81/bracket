import {
  Button,
  Group,
  Modal,
  PasswordInput,
  Select,
  Stack,
  Table,
  Text,
  TextInput,
} from '@mantine/core';
import { useForm } from '@mantine/form';
import { showNotification } from '@mantine/notifications';
import { IconCheck, IconUsers } from '@tabler/icons-react';
import { AxiosError } from 'axios';
import { useState } from 'react';

import { Club } from '../../interfaces/club';
import {
  UserAccountType,
  UserAdminCreateInterface,
  UserInterface,
} from '../../interfaces/user';
import { getClubUsers, handleRequestError } from '../../services/adapter';
import { createClubUser } from '../../services/user';
import RequestErrorAlert from '../utils/error_alert';

export default function ClubUsersModal({
  club,
  accountType,
}: {
  club: Club;
  accountType: 'REGULAR' | 'ADMIN';
}) {
  const [opened, setOpened] = useState(false);
  const usersResponse = getClubUsers(club.id);
  const roleOptions: UserAccountType[] =
    accountType === 'REGULAR' ? ['ADMIN', 'SCORER'] : ['SCORER'];
  const form = useForm<UserAdminCreateInterface>({
    initialValues: {
      name: '',
      email: '',
      password: '',
      account_type: roleOptions[0] as 'ADMIN' | 'SCORER',
    },
    validate: {
      name: (value) => (value.trim().length > 0 ? null : 'Name is required'),
      email: (value) => (/^\S+@\S+\.\S+$/.test(value) ? null : 'A valid email is required'),
      password: (value) => (value.length >= 8 ? null : 'Password must contain at least 8 characters'),
    },
  });

  const users: UserInterface[] = usersResponse.data?.data ?? [];

  return (
    <>
      <Modal opened={opened} onClose={() => setOpened(false)} title={`Users — ${club.name}`} size="lg">
        <Stack>
          {usersResponse.error ? <RequestErrorAlert error={usersResponse.error} /> : null}
          {!usersResponse.error && usersResponse.isLoading ? <Text>Loading users…</Text> : null}
          {!usersResponse.error && !usersResponse.isLoading ? (
            <Table striped withTableBorder>
              <Table.Thead>
                <Table.Tr>
                  <Table.Th>Name</Table.Th>
                  <Table.Th>Email</Table.Th>
                  <Table.Th>Account type</Table.Th>
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {users.map((user) => (
                  <Table.Tr key={user.id}>
                    <Table.Td>{user.name}</Table.Td>
                    <Table.Td>{user.email}</Table.Td>
                    <Table.Td>{user.account_type}</Table.Td>
                  </Table.Tr>
                ))}
              </Table.Tbody>
            </Table>
          ) : null}
          {!usersResponse.isLoading && users.length === 0 ? (
            <Text c="dimmed">No users are assigned to this club.</Text>
          ) : null}

          <form
            onSubmit={form.onSubmit(async (values) => {
              try {
                await createClubUser(club.id, {
                  ...values,
                  name: values.name.trim(),
                  email: values.email.trim(),
                });
                await usersResponse.mutate();
                form.reset();
                form.setFieldValue('account_type', roleOptions[0] as 'ADMIN' | 'SCORER');
                showNotification({
                  color: 'green',
                  title: 'User created',
                  message: `${values.name} was added to ${club.name}.`,
                  icon: <IconCheck size={18} />,
                });
              } catch (error) {
                handleRequestError(error as AxiosError);
              }
            })}
          >
            <Stack>
              <Text fw={600}>Create user</Text>
              <TextInput withAsterisk label="Name" {...form.getInputProps('name')} />
              <TextInput withAsterisk label="Email" type="email" {...form.getInputProps('email')} />
              <PasswordInput
                withAsterisk
                label="Password"
                {...form.getInputProps('password')}
              />
              <Select
                withAsterisk
                label="Account type"
                data={roleOptions}
                allowDeselect={false}
                {...form.getInputProps('account_type')}
              />
              <Group justify="flex-end">
                <Button type="submit" color="green">
                  Create user
                </Button>
              </Group>
            </Stack>
          </form>
        </Stack>
      </Modal>
      <Button
        size="xs"
        variant="light"
        mr={10}
        leftSection={<IconUsers size={16} />}
        onClick={() => setOpened(true)}
      >
        Users
      </Button>
    </>
  );
}
