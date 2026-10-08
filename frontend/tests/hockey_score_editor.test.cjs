const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');
const ts = require('typescript');
const root = path.resolve(__dirname, '..');
function load(file, dependencies) {
  const source = fs.readFileSync(path.join(root, file), 'utf8');
  const module = { exports: {} };
  vm.runInNewContext(
    ts.transpileModule(source, {
      compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX },
    }).outputText,
    {
      module,
      window: { confirm: () => false },
      exports: module.exports,
      require(name) {
        assert.ok(name in dependencies, `Unexpected dependency ${name}`);
        return dependencies[name];
      },
    },
  );
  return module.exports;
}
const jsx = (type, props, key) => ({ type, props, key });
function nodes(tree) {
  if (Array.isArray(tree)) return tree.flatMap(nodes);
  if (!tree || typeof tree !== 'object') return [];
  return [tree, ...nodes(tree.props?.children)];
}
function mantine() {
  const result = Object.fromEntries(
    [
      'Alert',
      'Button',
      'NumberInput',
      'Stack',
      'Text',
      'Title',
      'Modal',
      'Center',
      'Checkbox',
      'Divider',
      'Loader',
    ].map((name) => [name, name]),
  );
  result.Grid = Object.assign(() => {}, { Col: 'Grid.Col' });
  result.Accordion = Object.assign(() => {}, {
    Item: 'Accordion.Item',
    Control: 'Accordion.Control',
    Panel: 'Accordion.Panel',
  });
  return result;
}
const tournament = {
  id: 7,
  hockey_mode: 'COMPETITION',
  competition_format: 'STANDARD',
  age_category: 'U15',
  status: 'OPEN',
};
const match = {
  id: 3,
  round_id: 2,
  status: 'FINISHED',
  score_entry_source: 'MANUAL',
  stage_item_input1_score: 7,
  stage_item_input2_score: 4,
  stage_item_input1_half1_score: 5,
  stage_item_input2_half1_score: 3,
  stage_item_input1_half2_score: 2,
  stage_item_input2_half2_score: 1,
  stage_item_input1_penalty_score: 1,
  stage_item_input2_penalty_score: 0,
  custom_duration_minutes: null,
  custom_margin_minutes: null,
  court_id: 4,
};
function harness({
  record = match,
  config = tournament,
  requestError = null,
  refreshError = null,
  pending = null,
  onDirtyChange,
} = {}) {
  const requests = [],
    notifications = [],
    states = [],
    refreshed = [],
    saving = [];
  let closed = 0,
    form;
  const service = load('src/services/match.tsx', {
    '@mantine/notifications': {},
    './adapter': {
      createAxios: () => ({
        put: async (url, body) => {
          requests.push({ url, body });
          if (pending) await pending;
          if (requestError) throw requestError;
          return { status: 200 };
        },
      }),
      handleRequestError: (error) => notifications.push(error),
    },
  });
  const react = {
    useEffect: (effect) => effect(),
    useRef: (current) => ({ current }),
    useState: (initial) => {
      const index = states.length;
      states.push(initial);
      return [
        initial,
        (next) => {
          states[index] = next;
        },
      ];
    },
  };
  const useForm = (options) => {
    form = {
      values: { ...options.initialValues },
      validate: options.validate,
      setFieldValue: (field, value) => {
        form.values[field] = value;
      },
      setValues: (values) => {
        form.values = values;
      },
      getInputProps: (field) => ({ name: field, value: form.values[field] }),
      onSubmit: (callback) => () => callback(form.values),
    };
    return form;
  };
  const shared = {
    '@mantine/core': mantine(),
    '@mantine/form': { useForm },
    react,
    'react-i18next': { useTranslation: () => ({ t: (key) => key }) },
    'react/jsx-runtime': { jsx, jsxs: jsx },
    '@services/match': service,
  };
  const editor = load('src/components/matches/hockey_score_editor.tsx', {
    ...shared,
    swr: { useSWRConfig: () => ({ mutate: async (key) => refreshed.push(key) }) },
  });
  const tree = editor.default({
    tournament: config,
    match: record,
    teamNames: ['Team A', 'Team B'],
    refreshMatch: async () => {
      refreshed.push('stages');
      if (refreshError) throw refreshError;
    },
    onSaved: () => {
      closed++;
    },
    onSavingChange: (value) => saving.push(value),
    onDirtyChange,
  });
  return {
    editor,
    tree,
    service,
    shared,
    requests,
    notifications,
    states,
    refreshed,
    saving,
    get form() {
      return form;
    },
    get closed() {
      return closed;
    },
  };
}
for (const mode of ['GAME_SHOOTOUT', 'COMPETITION']) {
  test(`${mode} shows the exact sections and stored team scores`, () => {
    const h = harness({ config: { ...tournament, hockey_mode: mode } });
    const inputs = nodes(h.tree).filter((node) => node.type === 'NumberInput');
    assert.equal(inputs.length, mode === 'GAME_SHOOTOUT' ? 4 : 6);
    for (const input of inputs) {
      assert.equal(input.props.value, match[input.props.name]);
      assert.equal(input.props.allowDecimal, false);
      assert.equal(input.props.allowNegative, false);
      assert.ok(input.props.label === 'Team A' || input.props.label === 'Team B');
    }
    assert.ok(
      nodes(h.tree).some((node) => node.props?.children === 'hockey_score_unknown_capture'),
    );
    if (mode === 'COMPETITION')
      assert.ok(
        inputs.every(
          (node) =>
            !['stage_item_input1_score', 'stage_item_input2_score'].includes(node.props.name),
        ),
      );
  });
}
test('partial save sends only changed score including explicit zero and refreshes backend caches', async () => {
  const h = harness();
  h.form.values.stage_item_input1_half1_score = 0;
  await h.tree.props.onSubmit();
  assert.equal(
    JSON.stringify(h.requests[0]),
    JSON.stringify({
      url: 'tournaments/7/matches/3',
      body: { round_id: 2, stage_item_input1_half1_score: 0 },
    }),
  );
  assert.deepEqual(h.refreshed, ['stages', 'tournaments/7/overall_standings']);
  assert.equal(h.closed, 1);
  assert.deepEqual(h.saving, [true, false]);
});
test('GAME_SHOOTOUT saves GAME and shootout without half or administrative fields', async () => {
  const h = harness({ config: { ...tournament, hockey_mode: 'GAME_SHOOTOUT' } });
  h.form.values.stage_item_input1_score = 0;
  h.form.values.stage_item_input2_penalty_score = 2;
  await h.tree.props.onSubmit();
  assert.equal(
    JSON.stringify(h.requests[0].body),
    JSON.stringify({
      round_id: 2,
      stage_item_input1_score: 0,
      stage_item_input2_penalty_score: 2,
    }),
  );
});
for (const value of [-1, 1.5, '', '0', 'abc', NaN, Infinity]) {
  test(`invalid score ${String(value)} is rejected without saving`, async () => {
    const h = harness();
    h.form.values.stage_item_input1_half1_score = value;
    assert.notEqual(h.form.validate.stage_item_input1_half1_score(value), null);
    await h.tree.props.onSubmit();
    assert.equal(h.requests.length, 0);
    assert.equal(h.closed, 0);
    assert.equal(h.states[1], 'hockey_score_invalid');
  });
}
test('failed save forwards same error and keeps dialog open without refetch', async () => {
  const error = new Error('rejected');
  const h = harness({ requestError: error });
  await h.tree.props.onSubmit();
  assert.equal(h.notifications[0], error);
  assert.equal(h.closed, 0);
  assert.deepEqual(h.refreshed, []);
  assert.equal(h.states[1], 'hockey_score_save_error');
});
test('failed refresh keeps dialog open and distinguishes saved result', async () => {
  const h = harness({ refreshError: new Error('offline') });
  await h.tree.props.onSubmit();
  assert.equal(h.requests.length, 1);
  assert.equal(h.closed, 0);
  assert.equal(h.states[1], 'hockey_score_refresh_error');
});
test('duplicate saves are blocked immediately before rerender', async () => {
  let release;
  const pending = new Promise((resolve) => {
    release = resolve;
  });
  const h = harness({ pending });
  const first = h.tree.props.onSubmit();
  await h.tree.props.onSubmit();
  assert.equal(h.requests.length, 1);
  release();
  await first;
  assert.equal(h.closed, 1);
});
for (const source of ['MANUAL', null, 'EVENTS']) {
  test(`source ${source} is respected without migration`, async () => {
    const h = harness({ record: { ...match, score_entry_source: source } });
    const inputs = nodes(h.tree).filter((node) => node.type === 'NumberInput');
    assert.equal(
      inputs.every((node) => node.props.disabled),
      source === 'EVENTS',
    );
    h.form.values.stage_item_input1_half1_score = 0;
    await h.tree.props.onSubmit();
    assert.equal(h.requests.length, source === 'EVENTS' ? 0 : 1);
    if (h.requests[0]) assert.ok(!('score_entry_source' in h.requests[0].body));
  });
}
test('archived tournament cannot save even when submit is invoked directly', async () => {
  const h = harness({ config: { ...tournament, status: 'ARCHIVED' } });
  assert.ok(
    nodes(h.tree)
      .filter((node) => node.type === 'NumberInput')
      .every((node) => node.props.disabled),
  );
  await h.tree.props.onSubmit();
  assert.equal(h.requests.length, 0);
});
test('mode selection ignores age and competition format', () => {
  for (const age_category of ['U9', 'U11', 'U15']) {
    for (const competition_format of ['STANDARD', 'YOUTH_CLUB']) {
      const h = harness({ config: { ...tournament, age_category, competition_format } });
      assert.equal(nodes(h.tree).filter((node) => node.type === 'NumberInput').length, 6);
    }
  }
});
test('legacy service callers still resolve errors; opt-in forwards then rethrows same error', async () => {
  const error = new Error('rejected');
  const h = harness({ requestError: error });
  assert.equal(await h.service.updateMatch(7, 3, { round_id: 2 }), undefined);
  await assert.rejects(
    h.service.updateMatch(7, 3, { round_id: 2 }, true),
    (caught) => caught === error,
  );
  assert.deepEqual(h.notifications, [error, error]);
});
function modalHarness({
  mode = 'STANDARD',
  role = 'REGULAR',
  status = 'OPEN',
  requestError = null,
  loadError = false,
  stageData = true,
} = {}) {
  const h = harness({ requestError });
  const component = load('src/components/modals/match_modal.tsx', {
    ...h.shared,
    '@components/matches/hockey_phase_control': { default: 'HockeyPhaseControl' },
    '@components/matches/hockey_score_editor': { default: 'HockeyScoreEditor' },
    '@services/adapter': {
      getTournamentById: () => ({
        data: loadError ? undefined : { data: { ...tournament, hockey_mode: mode, status } },
        error: loadError,
      }),
      getUser: () => ({ data: { data: { account_type: role } } }),
    },
    '@components/buttons/delete': { default: 'DeleteButton' },
    '@components/utils/match': {
      formatMatchInput1: () => 'Team A',
      formatMatchInput2: () => 'Team B',
    },
    '@services/lookups': {
      getMatchLookup: (response) => {
        assert.ok(response.data);
        return {};
      },
      getStageItemLookup: () => ({}),
    },
  });
  const closes = [];
  let tree = component.default({
    tournamentData: { id: 7 },
    match,
    swrStagesResponse: { data: stageData ? { data: [] } : undefined, mutate: async () => {} },
    swrUpcomingMatchesResponse: null,
    opened: true,
    setOpened: (value) => closes.push(value),
    round: null,
  });
  function expand(node) {
    if (Array.isArray(node)) return node.map(expand);
    if (!node || typeof node !== 'object') return node;
    if (typeof node.type === 'function' && node.type.name === 'HockeyMatchSession')
      return expand(node.type(node.props));
    return { ...node, props: { ...node.props, children: expand(node.props?.children) } };
  }
  tree = expand(tree);
  return { ...h, tree, closes };
}
test('STANDARD retains original score and match settings form', () => {
  const h = modalHarness();
  const node = nodes(h.tree).find(
    (node) => typeof node.type === 'function' && node.type.name === 'MatchModalForm',
  );
  assert.ok(node);
  const inputs = nodes(node.type(node.props)).filter((node) => node.type === 'NumberInput');
  assert.equal(inputs.length, 4);
  assert.equal(inputs[0].props.value, match.stage_item_input1_score);
  assert.equal(inputs[1].props.value, match.stage_item_input2_score);
  assert.ok(!nodes(h.tree).some((node) => node.type === 'HockeyScoreEditor'));
});
test('STANDARD save failure also keeps dialog open', async () => {
  const h = modalHarness({ requestError: new Error('rejected') });
  const node = nodes(h.tree).find(
    (node) => typeof node.type === 'function' && node.type.name === 'MatchModalForm',
  );
  const form = nodes(node.type(node.props)).find((node) => node.type === 'form');
  await form.props.onSubmit();
  assert.deepEqual(h.closes, []);
});
test('SCORER sees hockey scores but no administrative settings', () => {
  const h = modalHarness({ mode: 'GAME_SHOOTOUT', role: 'SCORER' });
  assert.ok(nodes(h.tree).some((node) => node.type === 'HockeyScoreEditor'));
  assert.ok(!nodes(h.tree).some((node) => node.type === 'Accordion.Control'));
});
test('archived hockey tournament hides administrative settings', () => {
  const h = modalHarness({ mode: 'COMPETITION', status: 'ARCHIVED' });
  assert.ok(!nodes(h.tree).some((node) => node.type === 'Accordion.Control'));
});
test('missing configuration reports error and does not invent a mode', () => {
  const h = modalHarness({ loadError: true });
  assert.ok(nodes(h.tree).some((node) => node.type === 'Alert'));
  assert.ok(!nodes(h.tree).some((node) => node.type === 'HockeyScoreEditor'));
});

test('opening hockey dialog without loaded stage data does not call unsafe match lookup', () => {
  const h = modalHarness({ mode: 'COMPETITION', stageData: false });
  assert.ok(nodes(h.tree).some((node) => node.type === 'HockeyScoreEditor'));
});

test('local edits report dirty state; explicit discard restores stored scores without a request', () => {
  const dirty = [];
  const h = harness({ onDirtyChange: (value) => dirty.push(value) });
  const input = nodes(h.tree).find((node) => node.type === 'NumberInput');
  input.props.onChange('');
  assert.equal(dirty.at(-1), true);
  input.props.onChange(0);
  assert.equal(dirty.at(-1), true);
  nodes(h.tree)
    .find((node) => node.type === 'Button' && node.props.children === 'hockey_phase_discard')
    .props.onClick();
  assert.equal(dirty.at(-1), false);
  assert.equal(h.form.values.stage_item_input1_half1_score, 5);
  assert.equal(h.requests.length, 0);
});

test('closing a dialog with dirty scores requires explicit discard confirmation', () => {
  const h = modalHarness({ mode: 'COMPETITION' });
  const editor = nodes(h.tree).find((node) => node.type === 'HockeyScoreEditor');
  editor.props.onDirtyChange(true);
  h.tree.props.onClose();
  assert.deepEqual(h.closes, []);
  editor.props.onDirtyChange(false);
  h.tree.props.onClose();
  assert.deepEqual(h.closes, [false]);
});
