import { Card, Table, Title } from '@mantine/core';
import React from 'react';

import { StageWithStageItems } from '../../interfaces/stage';
import { TeamInterface } from '../../interfaces/team';
import { getStages } from '../../services/adapter';
import { responseIsValid } from '../utils/util';
import { TeamInterface } from '../../interfaces/team';

export default function TournamentOverallStandings({
  tournamentId,
  teams,
  competitionPointsByTeam,
}: {
  tournamentId: number;
  teams: TeamInterface[];
  competitionPointsByTeam: Record<number, number>;
}) {
  const swrStagesResponse = getStages(tournamentId);
  const stages: StageWithStageItems[] = responseIsValid(swrStagesResponse)
    ? swrStagesResponse.data.data
    : [];
  const gamePointsByTeam = stages
    .flatMap((stage) => stage.stage_items)
    .flatMap((stageItem) => stageItem.inputs)
    .reduce<Record<number, number>>((totals, input) => {
      if (input.team_id != null) {
        totals[input.team_id] = (totals[input.team_id] ?? 0) + Number(input.points ?? 0);
      }
      return totals;
    }, {});
  const teamList: TeamInterface[] = Array.isArray(teams)
    ? teams
  : (teams as any)?.teams ?? [];
  const standings = teamList
    .map((team) => {
      const gamePoints = gamePointsByTeam[team.id] ?? 0;
      const competitionPoints = competitionPointsByTeam[team.id] ?? 0;
      return {
        team,
        gamePoints,
        competitionPoints,
        totalPoints: gamePoints + competitionPoints,
      };
    })
    .sort(
      (a, b) =>
        b.totalPoints - a.totalPoints ||
        b.gamePoints - a.gamePoints ||
        b.competitionPoints - a.competitionPoints ||
        a.team.name.localeCompare(b.team.name)
    );

  return (
    <Card withBorder padding="md" radius="md">
      <Title order={4} mb="sm">
        Turnier-Gesamtwertung
      </Title>
      <Table>
        <Table.Thead>
          <Table.Tr>
            <Table.Th>Rang</Table.Th>
            <Table.Th>Team</Table.Th>
            <Table.Th>Spielpunkte</Table.Th>
            <Table.Th>Competition-Punkte</Table.Th>
            <Table.Th>Gesamtpunkte</Table.Th>
          </Table.Tr>
        </Table.Thead>
        <Table.Tbody>
          {standings.map(({ team, gamePoints, competitionPoints, totalPoints }, index) => (
            <Table.Tr key={team.id}>
              <Table.Td>{index + 1}</Table.Td>
              <Table.Td>{team.name}</Table.Td>
              <Table.Td>{gamePoints}</Table.Td>
              <Table.Td>{competitionPoints}</Table.Td>
              <Table.Td>{totalPoints}</Table.Td>
            </Table.Tr>
          ))}
        </Table.Tbody>
      </Table>
    </Card>
  );
}
