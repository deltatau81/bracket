const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const test = require('node:test');
const ts = require('typescript');
const root = path.resolve(__dirname, '..');
function load(file, dependencies, confirm = () => true) {
  const module = { exports: {} };
  vm.runInNewContext(
    ts.transpileModule(fs.readFileSync(path.join(root, file), 'utf8'), {
      compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX },
    }).outputText,
    {
      module,
      exports: module.exports,
      window: { confirm },
      require(name) {
        assert.ok(name in dependencies, name);
        return dependencies[name];
      },
    },
  );
  return module.exports;
}
const jsx = (type, props, key) => ({ type, props, key });
function nodes(tree) {
  if (Array.isArray(tree)) return tree.flatMap(nodes);
  return tree && typeof tree === 'object' ? [tree, ...nodes(tree.props?.children)] : [];
}
const match = {
  id: 3,
  status: 'RUNNING',
  active_period: 'HALF1',
  phase_state: 'ACTIVE',
  score_entry_source: 'EVENTS',
};
const tournament = { id: 7, hockey_mode: 'COMPETITION', status: 'OPEN' };
const teams = [
  { id: 11, name: 'Alpha A' },
  { id: 12, name: 'Beta B' },
];
const goal = {
  id: 91,
  match_id: 3,
  event_type: 'GOAL',
  team_id: 11,
  period: 'HALF1',
  game_time_seconds: 125,
  sort_order: 9,
  player_id: 20,
  player_name: 'Alex',
  player_number: 8,
  assist1_player_id: 21,
  assist1_name: 'Sam',
  assist1_number: 9,
  assist2_player_id: null,
  assist2_name: null,
  assist2_number: null,
};
function harness(options = {}) {
  const requests = [],
    notifications = [],
    refreshes = [],
    updates = [],
    saving = [],
    dirty = [],
    confirmations = [],
    swrKeys = [];
  const values = [],
    refs = [],
    fetchers = [];
  let cursor = 0,
    refCursor = 0,
    tree,
    props,
    list = options.list === undefined ? [goal] : options.list;
  let requestError = options.requestError,
    refreshError = options.refreshError;
  const react = {
    useState(initial) {
      const i = cursor++;
      if (!(i in values)) values[i] = initial;
      return [
        values[i],
        (next) => {
          values[i] = typeof next === 'function' ? next(values[i]) : next;
        },
      ];
    },
    useRef(current) {
      const i = refCursor++;
      return refs[i] ?? (refs[i] = { current });
    },
  };
  const swr = Object.assign(
    (key, fetcher) => {
      fetchers.push(fetcher);
      swrKeys.push(key);
      return {
        data: list === null ? undefined : { data: list },
        error: options.loadError,
        mutate: async () => {
          refreshes.push('events');
          if (refreshError) throw refreshError;
          return { data: list };
        },
      };
    },
    { useSWRConfig: () => ({ mutate: async (key) => refreshes.push(key) }) },
  );
  swr.default = swr;
  const request = (method) => async (url, body) => {
    requests.push({ method, url, body });
    if (options.pending) await options.pending;
    if (requestError) throw requestError;
    if (options.malformed) return { data: {} };
    return method === 'delete'
      ? { data: { success: true } }
      : { data: { data: { ...goal, ...body, id: 91, match_id: options.responseMatchId ?? 3 } } };
  };
  const service = load('src/services/match_event.tsx', {
    swr,
    './adapter': {
      createAxios: () => ({
        get: async (url) => {
          requests.push({ method: 'get', url });
          return { data: { data: list } };
        },
        post: request('post'),
        put: request('put'),
        delete: request('delete'),
      }),
      handleRequestError: (error) => notifications.push(error),
    },
  });
  const phases = load('src/components/matches/hockey_phase_control.tsx', {
    '@mantine/core': {},
    axios: {},
    react: {},
    'react-i18next': {},
    swr: {},
    '@services/match': {},
    'react/jsx-runtime': {},
  });
  const component = load(
    'src/components/matches/hockey_goal_events.tsx',
    {
      '@mantine/core': Object.fromEntries(
        [
          'Alert',
          'Button',
          'Group',
          'Loader',
          'NumberInput',
          'Paper',
          'Select',
          'Stack',
          'Text',
          'Title',
        ].map((name) => [name, name]),
      ),
      axios: { isAxiosError: (error) => error?.isAxiosError === true },
      react,
      'react-i18next': {
        useTranslation: () => ({
          t: (key, variables) => (variables ? key + JSON.stringify(variables) : key),
        }),
      },
      swr,
      '@services/match_event': service,
      './hockey_phase_control': phases,
      'react/jsx-runtime': { jsx, jsxs: jsx },
    },
    (message) => {
      confirmations.push(message);
      return options.confirm !== false;
    },
  );
  props = {
    tournament: options.tournament ?? tournament,
    match: options.match ?? match,
    teams: options.teams ?? teams,
    busy: options.busy ?? false,
    hasUnsavedScores: () => options.unsaved === true,
    hasPendingRequest: () => options.sharedBusy === true,
    refreshMatch: async () => {
      refreshes.push('match');
      if (refreshError) throw refreshError;
      return { ...props.match, stage_item_input1_half1_score: 42 };
    },
    onMatchUpdated: (updated) => updates.push(updated),
    onSavingChange: (value) => saving.push(value),
    onDirtyChange: (value) => dirty.push(value),
  };
  function render(patch) {
    Object.assign(props, patch);
    cursor = 0;
    refCursor = 0;
    tree = component.default(props);
    return tree;
  }
  render();
  const find = (type, label) =>
    nodes(tree).find(
      (node) => node.type === type && (node.props.children === label || node.props.label === label),
    );
  return {
    component,
    service,
    phases,
    requests,
    notifications,
    refreshes,
    updates,
    saving,
    dirty,
    confirmations,
    swrKeys,
    fetchers,
    values,
    props,
    render,
    nodes: () => nodes(tree),
    find,
    click: (label) => {
      const node = find('Button', label);
      assert.ok(node, label);
      return node.props.onClick();
    },
    change: (label, value, type = 'Select') => {
      find(type, label).props.onChange(value);
      render();
    },
    create: () => {
      const node = find('Button', 'hockey_events_add');
      node.props.onClick();
      render();
    },
    edit: () => {
      find('Button', 'hockey_events_edit').props.onClick();
      render();
    },
    setError: (error) => {
      requestError = error;
    },
    setRefreshError: (error) => {
      refreshError = error;
    },
  };
}
test('STANDARD renders no event manager and disables event fetching', () => {
  const h = harness({ tournament: { ...tournament, hockey_mode: 'STANDARD' } });
  assert.equal(h.render(), null);
  assert.equal(h.swrKeys.at(-1), null);
});
for (const [mode, period] of [
  ['GAME_SHOOTOUT', 'GAME'],
  ['COMPETITION', 'HALF1'],
  ['COMPETITION', 'HALF2'],
  ['COMPETITION', 'SHOOTOUT'],
  ['GAME_SHOOTOUT', 'SHOOTOUT'],
]) {
  test(mode + ' creates GOAL in active ' + period + ' without player or time', async () => {
    const h = harness({
      tournament: { ...tournament, hockey_mode: mode },
      match: { ...match, active_period: period },
    });
    h.create();
    h.change('hockey_events_team', '12');
    await h.click('save_button');
    assert.equal(h.requests.length, 1);
    const r = h.requests[0];
    assert.equal(r.url, 'tournaments/7/matches/3/events');
    assert.equal(r.method, 'post');
    assert.equal(r.body.team_id, 12);
    assert.equal(r.body.period, period);
    assert.equal(r.body.event_type, 'GOAL');
    assert.equal(r.body.game_time_seconds, null);
    assert.equal(r.body.player_id, null);
    assert.ok(!('score_entry_source' in r.body));
    assert.ok(!('stage_item_input1_score' in r.body));
    assert.equal(h.updates[0].stage_item_input1_half1_score, 42);
  });
}
test('list is scoped to match and GOAL, preserving backend chronology', () => {
  const h = harness({
    list: [
      goal,
      { ...goal, id: 92, team_id: 12 },
      { ...goal, id: 93, match_id: 4 },
      { ...goal, id: 94, event_type: 'PENALTY' },
    ],
  });
  const cards = h.nodes().filter((node) => node.type === 'Paper');
  assert.equal(cards.length, 2);
  assert.ok(cards[0].props.children.props.children[0].props.children.includes('Alpha A'));
  assert.ok(cards[1].props.children.props.children[0].props.children.includes('Beta B'));
});
test('empty, loading and load-error states', () => {
  assert.ok(
    harness({ list: [] })
      .nodes()
      .some((n) => n.props.children === 'hockey_events_empty'),
  );
  assert.ok(
    harness({ list: null })
      .nodes()
      .some((n) => n.type === 'Loader'),
  );
  const h = harness({ list: null, loadError: new Error('load') });
  assert.ok(h.nodes().some((n) => n.props.children === 'hockey_events_load_error'));
  assert.equal(h.find('Button', 'hockey_events_add').props.disabled, true);
});
test('optional snapshot and time are only shown when present', () => {
  const h = harness({
    list: [{ ...goal, game_time_seconds: null, player_name: null, player_number: null }],
  });
  assert.ok(!h.nodes().some((n) => n.props.children?.includes?.('Alex')));
  h.edit();
  assert.equal(h.find('NumberInput', 'hockey_events_time').props.value, '');
});
test('edit loads team, period, time and preserves snapshots and order', async () => {
  const h = harness();
  h.edit();
  assert.equal(h.find('Select', 'hockey_events_team').props.value, '11');
  assert.equal(h.find('Select', 'hockey_events_period').props.value, 'HALF1');
  assert.equal(h.find('NumberInput', 'hockey_events_time').props.value, 125);
  h.change('hockey_events_time', 130, 'NumberInput');
  await h.click('save_button');
  const r = h.requests[0];
  assert.equal(r.method, 'put');
  assert.equal(r.url, 'tournaments/7/matches/3/events/91');
  assert.equal(r.body.player_id, 20);
  assert.equal(r.body.assist1_player_id, 21);
  assert.equal(r.body.sort_order, 9);
  assert.equal(r.body.game_time_seconds, 130);
});
test('explicit team and phase correction sends targeted update and clears incompatible snapshots', async () => {
  const h = harness();
  h.edit();
  h.change('hockey_events_team', '12');
  h.change('hockey_events_period', 'HALF2');
  await h.click('save_button');
  assert.equal(h.requests[0].body.period, 'HALF2');
  assert.equal(h.requests[0].body.player_id, null);
  assert.equal(h.requests[0].body.assist1_player_id, null);
  assert.ok(h.confirmations[0].includes('hockey_events_team_change'));
});
test('team-change cancellation preserves edit without API request', async () => {
  const h = harness({ confirm: false });
  h.edit();
  h.change('hockey_events_team', '12');
  await h.click('save_button');
  assert.equal(h.requests.length, 0);
});
test('delete confirms the specific goal then refreshes authoritative data', async () => {
  const h = harness();
  await h.click('hockey_events_delete');
  assert.equal(h.requests[0].method, 'delete');
  assert.equal(h.requests[0].url, 'tournaments/7/matches/3/events/91');
  assert.ok(h.confirmations[0].includes('Alpha A'));
  assert.ok(h.confirmations[0].includes('91'));
  assert.equal(h.updates.length, 1);
});
test('delete cancellation issues no request', async () => {
  const h = harness({ confirm: false });
  await h.click('hockey_events_delete');
  assert.equal(h.requests.length, 0);
});
for (const status of [401, 403, 409, 422]) {
  for (const action of ['create', 'edit', 'delete']) {
    test(
      action + ' HTTP ' + status + ' leaves event/draft intact and reports failure',
      async () => {
        const failure = { isAxiosError: true, response: { status } };
        const h = harness({ requestError: failure });
        if (action === 'create') {
          h.create();
          h.change('hockey_events_team', '11');
        }
        if (action === 'edit') h.edit();
        await h.click(action === 'delete' ? 'hockey_events_delete' : 'save_button');
        h.render();
        assert.equal(h.notifications[0], failure);
        assert.equal(h.updates.length, 0);
        assert.equal(h.refreshes.length, 0);
        assert.ok(h.nodes().some((n) => n.type === 'Alert'));
        if (action !== 'delete') assert.ok(h.find('Button', 'save_button'));
        assert.ok(h.nodes().some((n) => n.key === '91' || n.key === 91));
      },
    );
  }
}
test('duplicate create clicks produce only one request while pending', async () => {
  let release;
  const pending = new Promise((resolve) => {
    release = resolve;
  });
  const h = harness({ pending });
  h.create();
  h.change('hockey_events_team', '11');
  const first = h.click('save_button');
  await h.click('save_button');
  assert.equal(h.requests.length, 1);
  release();
  await first;
});
test('ambiguous create response never retries and requires server review', async () => {
  const h = harness({ requestError: new Error('connection lost') });
  h.create();
  h.change('hockey_events_team', '11');
  await h.click('save_button');
  await h.click('save_button');
  h.render();
  assert.equal(h.requests.length, 1);
  assert.ok(h.find('Button', 'save_button').props.disabled);
  assert.ok(h.nodes().some((n) => n.props.children === 'hockey_events_uncertain'));
  h.setError(null);
  await h.click('hockey_events_reload');
  h.render();
  assert.ok(h.find('Button', 'hockey_events_add'));
  assert.equal(h.requests.length, 1);
});
for (const options of [{ malformed: true }, { responseMatchId: 99 }]) {
  test('malformed or foreign-match mutation response is not treated as success', async () => {
    const h = harness(options);
    h.create();
    h.change('hockey_events_team', '11');
    await h.click('save_button');
    assert.equal(h.updates.length, 0);
    assert.equal(h.refreshes.length, 0);
    assert.equal(h.values[3], true);
  });
}
for (const source of ['MANUAL', 'EVENTS', null]) {
  test('source ' + source + ' is preserved and displayed honestly', async () => {
    const h = harness({ match: { ...match, score_entry_source: source } });
    assert.ok(
      h
        .nodes()
        .some(
          (n) =>
            n.props.children ===
            'hockey_events_' +
              (source === 'MANUAL' ? 'manual' : source === 'EVENTS' ? 'events' : 'legacy'),
        ),
    );
    h.create();
    h.change('hockey_events_team', '11');
    await h.click('save_button');
    assert.ok(!('score_entry_source' in h.requests[0].body));
    assert.equal(h.updates[0].score_entry_source, source);
  });
}
for (const record of [
  { ...match, status: 'PLANNED', active_period: null, phase_state: null },
  { ...match, status: 'FINISHED', phase_state: 'BREAK' },
  { ...match, phase_state: 'BREAK' },
]) {
  test(
    record.status +
      '/' +
      record.phase_state +
      ' forbids new events but allows historical corrections',
    async () => {
      const h = harness({ match: record });
      assert.equal(h.find('Button', 'hockey_events_add').props.disabled, true);
      h.edit();
      await h.click('save_button');
      assert.equal(h.requests[0].method, 'put');
    },
  );
}
test('active-phase change does not silently reassign an open create draft', async () => {
  const h = harness();
  h.create();
  h.change('hockey_events_team', '11');
  h.render({ match: { ...match, active_period: 'HALF2' } });
  await h.click('save_button');
  assert.equal(h.requests.length, 0);
  h.render();
  assert.ok(h.nodes().some((n) => n.props.children === 'hockey_events_phase_changed'));
});
for (const options of [
  { unsaved: true },
  { busy: true },
  { tournament: { ...tournament, status: 'ARCHIVED' } },
]) {
  test('dirty/busy/archive blocks event mutation', async () => {
    const h = harness(options);
    if (h.find('Button', 'hockey_events_add')) {
      h.create();
    }
    if (h.find('Button', 'hockey_events_delete')) await h.click('hockey_events_delete');
    assert.equal(h.requests.length, 0);
  });
}
test('invalid team and fractional, negative or textual times are rejected before API calls', async () => {
  for (const time of [-1, 1.5, 'invalid']) {
    const h = harness();
    h.create();
    h.change('hockey_events_team', '11');
    h.change('hockey_events_time', time, 'NumberInput');
    await h.click('save_button');
    assert.equal(h.requests.length, 0);
  }
  const h = harness();
  h.create();
  h.change('hockey_events_team', '99');
  await h.click('save_button');
  assert.equal(h.requests.length, 0);
});
test('success revalidates event, match, stage-ranking and combined standings caches', async () => {
  const h = harness();
  h.edit();
  await h.click('save_button');
  assert.deepEqual(h.refreshes, [
    'events',
    'match',
    'tournaments/7/rankings',
    'tournaments/7/next_stage_rankings',
    'tournaments/7/overall_standings',
  ]);
  assert.deepEqual(h.saving, [true, false]);
  assert.deepEqual(h.dirty, [true, false]);
});
test('refresh failure after accepted mutation is distinct from request failure', async () => {
  const h = harness({ refreshError: new Error('refresh') });
  h.edit();
  await h.click('save_button');
  h.render();
  assert.equal(h.requests.length, 1);
  assert.ok(h.nodes().some((n) => n.props.children === 'hockey_events_refresh_error'));
});
test('discarding event draft clears dirty status without score or event request', async () => {
  const h = harness();
  h.edit();
  await h.click('hockey_events_cancel');
  h.render();
  assert.deepEqual(h.dirty, [true, false]);
  assert.equal(h.requests.length, 0);
});
test('all goal-event labels are present in German and English', () => {
  const source = fs.readFileSync(
    path.join(root, 'src/components/matches/hockey_goal_events.tsx'),
    'utf8',
  );
  const keys = [...source.matchAll(/'((?:hockey_events_)[a-z_]+)'/g)].map((m) => m[1]);
  for (const lang of ['de', 'en']) {
    const messages = JSON.parse(
      fs.readFileSync(path.join(root, 'public/locales', lang, 'common.json'), 'utf8'),
    );
    for (const key of keys) assert.equal(typeof messages[key], 'string', lang + ':' + key);
  }
});
test('event list fetcher calls the real scoped GET contract', async () => {
  const h = harness();
  const response = await h.fetchers[0]('tournaments/7/matches/3/events');
  assert.equal(h.requests[0].method, 'get');
  assert.equal(h.requests[0].url, 'tournaments/7/matches/3/events');
  assert.equal(response.data[0].id, 91);
});
test('a synchronous dirty-score change blocks an existing submit handler before rerender', async () => {
  const options = {};
  const h = harness(options);
  h.create();
  h.change('hockey_events_team', '11');
  options.unsaved = true;
  await h.click('save_button');
  assert.equal(h.requests.length, 0);
});
test('a server 502 create response is ambiguous and cannot be replayed automatically', async () => {
  const h = harness({ requestError: { isAxiosError: true, response: { status: 502 } } });
  h.create();
  h.change('hockey_events_team', '11');
  await h.click('save_button');
  await h.click('save_button');
  assert.equal(h.requests.length, 1);
  h.render();
  assert.ok(h.nodes().some((n) => n.props.children === 'hockey_events_uncertain'));
});
test('failed post-mutation refresh blocks another mutation until server review', async () => {
  const h = harness({ refreshError: new Error('offline') });
  h.edit();
  await h.click('save_button');
  h.render();
  assert.equal(h.find('Button', 'hockey_events_add').props.disabled, true);
  h.setRefreshError(null);
  await h.click('hockey_events_reload');
  h.render();
  assert.equal(h.find('Button', 'hockey_events_add').props.disabled, false);
});

test('shared in-flight request locks events without pretending scores are dirty', async () => {
  const options = {};
  const h = harness(options);
  h.create();
  h.change('hockey_events_team', '11');
  options.sharedBusy = true;
  await h.click('save_button');
  assert.equal(h.requests.length, 0);
  h.render();
  assert.ok(!h.nodes().some((n) => n.props.children === 'hockey_phase_dirty'));
});
test('server review cannot discard a failed event draft without confirmation', async () => {
  const h = harness({
    confirm: false,
    requestError: { isAxiosError: true, response: { status: 422 } },
  });
  h.edit();
  await h.click('save_button');
  h.render();
  await h.click('hockey_events_reload');
  h.render();
  assert.ok(h.find('Button', 'save_button'));
  assert.equal(h.refreshes.length, 0);
});
