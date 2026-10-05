import { awaitRequestAndHandleError, createAxios, handleRequestError } from './adapter';

export async function createTeam(
  tournament_id: number,
  name: string,
  active: boolean,
  player_ids: string[],
  player_assignments: null = null,
  participant_club_id: number | null = null,
  pairing_group: string | null = null,
) {
  return createAxios()
    .post(`tournaments/${tournament_id}/teams`, {
      name,
      active,
      player_ids: player_ids.map(Number),
      player_assignments,
      participant_club_id,
      pairing_group,
    })
    .catch((response: any) => handleRequestError(response));
}

export async function createTeams(
  tournament_id: number,
  names: string,
  active: boolean,
  participant_club_id: number | null = null,
  pairing_group: string | null = null,
) {
  return createAxios()
    .post(`tournaments/${tournament_id}/teams_multi`, {
      names,
      active,
      participant_club_id,
      pairing_group,
    })
    .catch((response: any) => handleRequestError(response));
}

export async function deleteTeam(tournament_id: number, team_id: number) {
  await createAxios()
    .delete(`tournaments/${tournament_id}/teams/${team_id}`)
    .catch((response: any) => handleRequestError(response));
}

export async function updateTeam(
  tournament_id: number,
  team_id: number,
  name: string,
  active: boolean,
  player_ids: string[],
  player_assignments: null = null,
  participant_club_id: number | null = null,
  pairing_group: string | null = null,
) {
  return awaitRequestAndHandleError(async (axios) =>
    axios.put(`tournaments/${tournament_id}/teams/${team_id}`, {
      name,
      active,
      player_ids: player_ids.map(Number),
      player_assignments,
      participant_club_id,
      pairing_group,
    }),
  );
}
