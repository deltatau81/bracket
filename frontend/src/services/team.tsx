import { PlayerPosition } from '../interfaces/player';
import { PlayerTeamAssignment, TeamInterface } from '../interfaces/team';
import {
  awaitRequestAndHandleError,
  createAxios,
  handleRequestError,
  requestSucceeded,
} from './adapter';

export async function createTeam(
  tournament_id: number,
  name: string,
  active: boolean,
  player_ids: string[],
  player_assignments?: PlayerTeamAssignment[]
) {
  return createAxios()
    .post(`tournaments/${tournament_id}/teams`, {
      name,
      active,
      player_ids,
      player_assignments,
    })
    .catch((response: any) => handleRequestError(response));
}

export async function createTeams(tournament_id: number, names: string, active: boolean) {
  return createAxios()
    .post(`tournaments/${tournament_id}/teams_multi`, { names, active })
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
  player_assignments?: PlayerTeamAssignment[]
) {
  return awaitRequestAndHandleError(async (axios) =>
    axios.put(`tournaments/${tournament_id}/teams/${team_id}`, {
      name,
      active,
      player_ids,
      player_assignments,
    })
  );
}

export async function setPlayerTeam(
  tournament_id: number,
  teams: TeamInterface[],
  player_id: number,
  team_id: number | null,
  number: number | null,
  position: PlayerPosition | null
) {
  const existingTeams = teams.filter((team) =>
    team.players.some((player) => player.id === player_id)
  );
  const targetTeam = teams.find((team) => team.id === team_id);
  const targetIsExistingTeam = existingTeams.some((team) => team.id === team_id);
  if (team_id != null && targetTeam == null) return false;

  if (targetTeam != null) {
    const playerIds = targetTeam.players
      .filter((player) => player.id !== player_id)
      .map((player) => `${player.id}`);
    playerIds.push(`${player_id}`);
    const result = await updateTeam(
      tournament_id,
      targetTeam.id,
      targetTeam.name,
      targetTeam.active,
      playerIds,
      [{ player_id, number, position }]
    );
    if (!requestSucceeded(result)) return false;

    if (targetIsExistingTeam) return true;
  }

  for (const team of existingTeams) {
    const playerIds = team.players
      .filter((player) => player.id !== player_id)
      .map((player) => `${player.id}`);
    const result = await updateTeam(
      tournament_id,
      team.id,
      team.name,
      team.active,
      playerIds
    );
    if (!requestSucceeded(result)) return false;
  }

  return true;
}
