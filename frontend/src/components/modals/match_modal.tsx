import {
  Accordion,
  Alert,
  Loader,
  Stack,
  Button,
  Center,
  Checkbox,
  Divider,
  Grid,
  Modal,
  NumberInput,
  Text,
} from '@mantine/core';
import { useForm } from '@mantine/form';
import { useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { SWRResponse } from 'swr';

import HockeyGoalEvents from '@components/matches/hockey_goal_events';
import HockeyPhaseControl from '@components/matches/hockey_phase_control';
import HockeyScoreEditor from '@components/matches/hockey_score_editor';
import HockeyScoreSourceControl from '@components/matches/hockey_score_source_control';
import { getTournamentById, getUser } from '@services/adapter';
import DeleteButton from '@components/buttons/delete';
import { formatMatchInput1, formatMatchInput2 } from '@components/utils/match';
import { TournamentMinimal } from '@components/utils/tournament';
import {
  MatchWithDetails,
  RoundWithMatches,
  StagesWithStageItemsResponse,
  Tournament,
  UserAccountType,
} from '@openapi';
import { getMatchLookup, getStageItemLookup } from '@services/lookups';
import { deleteMatch, updateMatch } from '@services/match';

function MatchDeleteButton({
  tournamentData,
  match,
  swrStagesResponse,
  swrUpcomingMatchesResponse,
}: {
  tournamentData: TournamentMinimal;
  match: MatchWithDetails;
  swrStagesResponse: SWRResponse<StagesWithStageItemsResponse>;
  swrUpcomingMatchesResponse: SWRResponse | null;
}) {
  const { t } = useTranslation();
  return (
    <DeleteButton
      fullWidth
      onClick={async () => {
        await deleteMatch(tournamentData.id, match.id);
        await swrStagesResponse.mutate();
        if (swrUpcomingMatchesResponse != null) await swrUpcomingMatchesResponse.mutate();
      }}
      style={{ marginTop: '1rem' }}
      size="sm"
      title={t('remove_match_button')}
    />
  );
}

function MatchModalForm({
  tournamentData,
  match,
  swrStagesResponse,
  swrUpcomingMatchesResponse,
  setOpened,
  round,
  administrativeOnly = false,
  onSavingChange,
}: {
  tournamentData: TournamentMinimal;
  match: MatchWithDetails | null;
  swrStagesResponse: SWRResponse<StagesWithStageItemsResponse>;
  swrUpcomingMatchesResponse: SWRResponse | null;
  setOpened: any;
  round: RoundWithMatches | null;
  administrativeOnly?: boolean;
  onSavingChange: (saving: boolean) => void;
}) {
  if (match == null) {
    return null;
  }

  const { t } = useTranslation();
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState(false);
  const savingRef = useRef(false);
  const form = useForm({
    initialValues: {
      stage_item_input1_score: match.stage_item_input1_score,
      stage_item_input2_score: match.stage_item_input2_score,
      custom_duration_minutes: match.custom_duration_minutes,
      custom_margin_minutes: match.custom_margin_minutes,
    },

    validate: {
      stage_item_input1_score: (value) => (value >= 0 ? null : t('negative_score_validation')),
      stage_item_input2_score: (value) => (value >= 0 ? null : t('negative_score_validation')),
      custom_duration_minutes: (value) =>
        value == null || value >= 0 ? null : t('negative_match_duration_validation'),
      custom_margin_minutes: (value) =>
        value == null || value >= 0 ? null : t('negative_match_margin_validation'),
    },
  });

  const [customDurationEnabled, setCustomDurationEnabled] = useState(
    match.custom_duration_minutes != null,
  );
  const [customMarginEnabled, setCustomMarginEnabled] = useState(
    match.custom_margin_minutes != null,
  );

  const stageItemsLookup = getStageItemLookup(swrStagesResponse);
  const matchesLookup = getMatchLookup(swrStagesResponse);

  const team1Name = formatMatchInput1(t, stageItemsLookup, matchesLookup, match);
  const team2Name = formatMatchInput2(t, stageItemsLookup, matchesLookup, match);

  return (
    <>
      <form
        onSubmit={form.onSubmit(async (values) => {
          if (savingRef.current) return;
          savingRef.current = true;
          setSaving(true);
          onSavingChange(true);
          setSaveError(false);
          try {
            const updatedMatch = {
              id: match.id,
              round_id: match.round_id,
              ...(!administrativeOnly
                ? {
                    stage_item_input1_score: values.stage_item_input1_score,
                    stage_item_input2_score: values.stage_item_input2_score,
                  }
                : {}),
              court_id: match.court_id || null,
              custom_duration_minutes: customDurationEnabled
                ? values.custom_duration_minutes
                : null,
              custom_margin_minutes: customMarginEnabled ? values.custom_margin_minutes : null,
            };
            await updateMatch(tournamentData.id, match.id, updatedMatch, true);
            await swrStagesResponse.mutate();
            if (swrUpcomingMatchesResponse != null) await swrUpcomingMatchesResponse.mutate();
            setOpened(false);
          } catch {
            setSaveError(true);
          } finally {
            savingRef.current = false;
            setSaving(false);
            onSavingChange(false);
          }
        })}
      >
        {saveError && <Alert color="red">{t('hockey_score_save_error')}</Alert>}
        {!administrativeOnly && (
          <>
            <NumberInput
              withAsterisk
              label={`${t('score_of_label')} ${team1Name}`}
              placeholder={`${t('score_of_label')} ${team1Name}`}
              {...form.getInputProps('stage_item_input1_score')}
            />
            <NumberInput
              withAsterisk
              mt="lg"
              label={`${t('score_of_label')} ${team2Name}`}
              placeholder={`${t('score_of_label')} ${team2Name}`}
              {...form.getInputProps('stage_item_input2_score')}
            />
          </>
        )}
        <Divider mt="lg" />

        <Text size="sm" mt="lg">
          {t('custom_match_duration_label')}
        </Text>
        <Grid align="center">
          <Grid.Col span={{ sm: 8 }}>
            <NumberInput
              disabled={!customDurationEnabled}
              rightSection={<Text>{t('minutes')}</Text>}
              placeholder={`${match.duration_minutes}`}
              rightSectionWidth={92}
              {...form.getInputProps('custom_duration_minutes')}
            />
          </Grid.Col>
          <Grid.Col span={{ sm: 4 }}>
            <Center>
              <Checkbox
                checked={customDurationEnabled}
                label={t('customize_checkbox_label')}
                onChange={(event) => {
                  setCustomDurationEnabled(event.currentTarget.checked);
                }}
              />
            </Center>
          </Grid.Col>
        </Grid>

        <Text size="sm" mt="lg">
          {t('custom_match_margin_label')}
        </Text>
        <Grid align="center">
          <Grid.Col span={{ sm: 8 }}>
            <NumberInput
              disabled={!customMarginEnabled}
              placeholder={`${match.margin_minutes}`}
              rightSection={<Text>{t('minutes')}</Text>}
              rightSectionWidth={92}
              {...form.getInputProps('custom_margin_minutes')}
            />
          </Grid.Col>
          <Grid.Col span={{ sm: 4 }}>
            <Center>
              <Checkbox
                checked={customMarginEnabled}
                label={t('customize_checkbox_label')}
                onChange={(event) => {
                  setCustomMarginEnabled(event.currentTarget.checked);
                }}
              />
            </Center>
          </Grid.Col>
        </Grid>

        <Button
          fullWidth
          style={{ marginTop: 20 }}
          color="green"
          type="submit"
          loading={saving}
          disabled={saving}
        >
          {t('save_button')}
        </Button>
      </form>
      {round && round.is_draft && (
        <MatchDeleteButton
          swrStagesResponse={swrStagesResponse}
          swrUpcomingMatchesResponse={swrUpcomingMatchesResponse}
          tournamentData={tournamentData}
          match={match}
        />
      )}
    </>
  );
}

function HockeyMatchSession({
  role,
  hasPendingRequest,
  tournament,
  match,
  teamNames,
  refreshMatch,
  setOpened,
  setSaving,
  saving,
  children,
  onDirtyChange,
}: {
  role: UserAccountType;
  hasPendingRequest: () => boolean;
  tournament: Tournament;
  match: MatchWithDetails;
  teamNames: [string, string];
  refreshMatch: () => Promise<MatchWithDetails | undefined>;
  setOpened: (opened: boolean) => void;
  setSaving: (saving: boolean) => void;
  saving: boolean;
  children: React.ReactNode;
  onDirtyChange: (dirty: boolean) => void;
}) {
  const [currentMatch, setCurrentMatch] = useState(match);
  const [dirty, setDirty] = useState(false);
  const dirtyRef = useRef(false);
  const eventDirtyRef = useRef(false);
  const sourceDirtyRef = useRef(false);
  const [sourceDirty, setSourceDirty] = useState(false);
  const requestRef = useRef(false);
  const [eventDirty, setEventDirty] = useState(false);
  function savingChanged(value: boolean) {
    requestRef.current = value;
    setSaving(value);
  }
  useEffect(() => () => onDirtyChange(false), []);
  return (
    <Stack>
      <HockeyScoreSourceControl
        tournament={tournament}
        match={currentMatch}
        role={role}
        teamNames={teamNames}
        busy={saving}
        hasBlockedChanges={() =>
          dirtyRef.current || eventDirtyRef.current || requestRef.current || hasPendingRequest()
        }
        refreshMatch={refreshMatch}
        onMatchUpdated={(updated) => setCurrentMatch((previous) => ({ ...previous, ...updated }))}
        onSavingChange={savingChanged}
        onDirtyChange={(value) => {
          sourceDirtyRef.current = value;
          setSourceDirty(value);
          onDirtyChange(value || dirtyRef.current || eventDirtyRef.current);
        }}
      />
      <HockeyPhaseControl
        tournament={tournament}
        match={currentMatch}
        dirty={dirty || eventDirty || sourceDirty}
        busy={saving}
        refreshMatch={refreshMatch}
        onMatchUpdated={(updated) => setCurrentMatch((previous) => ({ ...previous, ...updated }))}
        hasUnsavedChanges={() =>
          dirtyRef.current ||
          eventDirtyRef.current ||
          sourceDirtyRef.current ||
          requestRef.current ||
          hasPendingRequest()
        }
        onSavingChange={savingChanged}
      />
      <HockeyGoalEvents
        tournament={tournament}
        match={currentMatch}
        teams={[currentMatch.stage_item_input1, currentMatch.stage_item_input2].flatMap((input) =>
          input && 'team' in input && input.team_id !== null
            ? [{ id: input.team_id, name: input.team.name }]
            : [],
        )}
        busy={saving}
        hasUnsavedScores={() => dirtyRef.current}
        hasPendingRequest={() =>
          requestRef.current || sourceDirtyRef.current || hasPendingRequest()
        }
        refreshMatch={refreshMatch}
        onMatchUpdated={setCurrentMatch}
        onSavingChange={savingChanged}
        onDirtyChange={(value) => {
          eventDirtyRef.current = value;
          setEventDirty(value);
          onDirtyChange(value || dirtyRef.current || sourceDirtyRef.current);
        }}
      />
      <fieldset disabled={eventDirty || sourceDirty} style={{ border: 0, padding: 0, margin: 0 }}>
        <HockeyScoreEditor
          tournament={tournament}
          match={currentMatch}
          teamNames={teamNames}
          refreshMatch={refreshMatch}
          onSaved={() => setOpened(false)}
          onSavingChange={savingChanged}
          onDirtyChange={(value) => {
            dirtyRef.current = value;
            setDirty(value);
            onDirtyChange(value || eventDirtyRef.current || sourceDirtyRef.current);
          }}
        />
      </fieldset>
      {children}
    </Stack>
  );
}

export default function MatchModal({
  tournamentData,
  match,
  swrStagesResponse,
  swrUpcomingMatchesResponse,
  opened,
  setOpened,
  round,
}: {
  tournamentData: TournamentMinimal;
  match: MatchWithDetails | null;
  swrStagesResponse: SWRResponse<StagesWithStageItemsResponse>;
  swrUpcomingMatchesResponse: SWRResponse | null;
  opened: boolean;
  setOpened: any;
  round: RoundWithMatches | null;
}) {
  const { t } = useTranslation();
  const tournament = getTournamentById(tournamentData.id);
  const user = getUser();
  const [saving, setSaving] = useState(false);
  const [dirtyScores, setDirtyScores] = useState(false);
  const scoreDirtyRef = useRef(false);
  const pendingRequestRef = useRef(false);
  function savingChanged(value: boolean) {
    pendingRequestRef.current = value;
    setSaving(value);
  }
  const configurationError = tournament.error || user.error;
  const stageItemsLookup = getStageItemLookup(swrStagesResponse);
  const matchesLookup = swrStagesResponse.data ? getMatchLookup(swrStagesResponse) : {};
  const hockey = tournament.data?.data.hockey_mode !== 'STANDARD';
  const scorer = user.data?.data.account_type === 'SCORER';
  async function refreshMatch() {
    const stages = await swrStagesResponse.mutate();
    if (swrUpcomingMatchesResponse != null) await swrUpcomingMatchesResponse.mutate();
    return stages?.data
      .flatMap((stage) =>
        stage.stage_items.flatMap((item) => item.rounds.flatMap((round) => round.matches)),
      )
      .find((candidate) => candidate.id === match?.id);
  }
  return (
    <Modal
      opened={opened}
      onClose={() => {
        if (
          !saving &&
          !pendingRequestRef.current &&
          (!scoreDirtyRef.current || window.confirm(t('hockey_phase_discard_confirm')))
        )
          setOpened(false);
      }}
      title={t('edit_match_modal_title')}
      closeOnClickOutside={!saving}
      closeOnEscape={!saving}
    >
      {configurationError ? (
        <Alert color="red">{t('hockey_score_config_error')}</Alert>
      ) : !tournament.data || !user.data ? (
        <Loader />
      ) : !match || !opened ? null : hockey ? (
        <fieldset disabled={saving} style={{ border: 0, padding: 0, margin: 0 }}>
          <HockeyMatchSession
            key={`${tournamentData.id}:${match.id}`}
            tournament={tournament.data.data}
            role={user.data.data.account_type}
            hasPendingRequest={() => pendingRequestRef.current}
            match={match}
            teamNames={[
              formatMatchInput1(t, stageItemsLookup, matchesLookup, match),
              formatMatchInput2(t, stageItemsLookup, matchesLookup, match),
            ]}
            refreshMatch={refreshMatch}
            setOpened={setOpened}
            setSaving={savingChanged}
            saving={saving}
            onDirtyChange={(value) => {
              scoreDirtyRef.current = value;
              setDirtyScores(value);
            }}
          >
            {!scorer && tournament.data.data.status !== 'ARCHIVED' && (
              <fieldset disabled={dirtyScores} style={{ border: 0, padding: 0, margin: 0 }}>
                <Accordion>
                  <Accordion.Item value="settings">
                    <Accordion.Control>{t('hockey_score_match_settings')}</Accordion.Control>
                    <Accordion.Panel>
                      <MatchModalForm
                        key={match.id}
                        administrativeOnly
                        onSavingChange={savingChanged}
                        swrStagesResponse={swrStagesResponse}
                        swrUpcomingMatchesResponse={swrUpcomingMatchesResponse}
                        tournamentData={tournamentData}
                        match={match}
                        setOpened={setOpened}
                        round={round}
                      />
                    </Accordion.Panel>
                  </Accordion.Item>
                </Accordion>
              </fieldset>
            )}
          </HockeyMatchSession>
        </fieldset>
      ) : (
        <fieldset
          disabled={saving || scorer || tournament.data.data.status === 'ARCHIVED'}
          style={{ border: 0, padding: 0, margin: 0 }}
        >
          <MatchModalForm
            key={match.id}
            onSavingChange={setSaving}
            swrStagesResponse={swrStagesResponse}
            swrUpcomingMatchesResponse={swrUpcomingMatchesResponse}
            tournamentData={tournamentData}
            match={match}
            setOpened={setOpened}
            round={round}
          />
        </fieldset>
      )}
    </Modal>
  );
}
