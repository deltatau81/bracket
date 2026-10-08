const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');
const ts = require('typescript');
const root = path.resolve(__dirname, '..');
function load(file, dependencies) {
  const module = { exports: {} };
  vm.runInNewContext(
    ts.transpileModule(fs.readFileSync(path.join(root, file), 'utf8'), {
      compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX },
    }).outputText,
    {
      module,
      exports: module.exports,
      window: { confirm: () => dependencies.confirm !== false },
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
const base = {
  id: 3,
  status: 'PLANNED',
  active_period: null,
  phase_state: null,
  score_entry_source: 'MANUAL',
};
const config = { id: 7, hockey_mode: 'COMPETITION', status: 'OPEN' };
function harness({
  match = base,
  tournament = config,
  dirty = false,
  busy = false,
  error = null,
  updated = { ...base, status: 'RUNNING', active_period: 'HALF1', phase_state: 'ACTIVE' },
  refreshError = null,
  confirm = true,
  pending = null,
  hasUnsavedChanges,
} = {}) {
  const requests = [],
    notifications = [],
    updates = [],
    refreshes = [],
    states = [],
    saving = [];
  const service = load('src/services/match.tsx', {
    '@mantine/notifications': {},
    './adapter': {
      createAxios: () => ({
        post: async (url, body) => {
          requests.push({ url, body });
          if (pending) await pending;
          if (error) throw error;
          return { data: { data: updated } };
        },
      }),
      handleRequestError: (failure) => notifications.push(failure),
    },
  });
  const component = load('src/components/matches/hockey_phase_control.tsx', {
    '@mantine/core': Object.fromEntries(
      ['Alert', 'Badge', 'Button', 'Group', 'Stack', 'Text', 'Title'].map((name) => [name, name]),
    ),
    axios: { isAxiosError: (failure) => failure?.isAxiosError === true },
    react: {
      useRef: (current) => ({ current }),
      useState: (initial) => {
        const i = states.length;
        states.push(initial);
        return [
          initial,
          (next) => {
            states[i] = next;
          },
        ];
      },
    },
    'react-i18next': { useTranslation: () => ({ t: (key) => key }) },
    'react/jsx-runtime': { jsx, jsxs: jsx },
    swr: { useSWRConfig: () => ({ mutate: async (key) => refreshes.push(key) }) },
    '@services/match': service,
    confirm,
  });
  const tree = component.default({
    match,
    tournament,
    dirty,
    busy,
    hasUnsavedChanges,
    refreshMatch: async () => {
      refreshes.push('stages');
      if (refreshError) throw refreshError;
      return updated;
    },
    onMatchUpdated: (value) => updates.push(value),
    onSavingChange: (value) => saving.push(value),
  });
  const buttons = nodes(tree).filter((node) => node.type === 'Button');
  return {
    component,
    service,
    requests,
    notifications,
    updates,
    refreshes,
    states,
    saving,
    tree,
    buttons,
  };
}

for (const mode of ['COMPETITION', 'GAME_SHOOTOUT']) {
  const periods = mode === 'COMPETITION' ? ['HALF1', 'HALF2', 'SHOOTOUT'] : ['GAME', 'SHOOTOUT'];
  test(mode + ' displays correct ordered sections and planned status', () => {
    const h = harness({ tournament: { ...config, hockey_mode: mode } });
    assert.deepEqual(Array.from(h.component.hockeyPeriods(mode)), periods);
    assert.equal(nodes(h.tree).filter((node) => node.type === 'Badge').length, periods.length);
    assert.ok(nodes(h.tree).some((node) => node.props?.children === 'hockey_phase_planned'));
  });
  for (const period of periods)
    for (const state of ['ACTIVE', 'BREAK']) {
      test(mode + ' ' + period + ' ' + state + ' offers only contract actions', () => {
        const h = harness({
          tournament: { ...config, hockey_mode: mode },
          match: { ...base, status: 'RUNNING', active_period: period, phase_state: state },
        });
        const expected =
          state === 'ACTIVE'
            ? period === 'SHOOTOUT'
              ? ['FINISH_MATCH']
              : ['END_PERIOD']
            : period === 'SHOOTOUT'
              ? ['RESUME_PERIOD']
              : ['START_NEXT_PERIOD', 'RESUME_PERIOD'];
        assert.deepEqual(
          Array.from(
            h.component.phaseActions(
              { ...base, status: 'RUNNING', active_period: period, phase_state: state },
              mode,
            ),
          ),
          expected,
        );
        assert.ok(
          nodes(h.tree)
            .filter((node) => node.type === 'Badge')
            .some((node) => node.key === period && node.props.variant === 'filled'),
        );
      });
    }
}
test('STANDARD has no phase UI', () => {
  assert.equal(harness({ tournament: { ...config, hockey_mode: 'STANDARD' } }).tree, null);
});
test('finished match offers reopen; malformed legacy state offers none', () => {
  const h = harness({
    match: { ...base, status: 'FINISHED', active_period: 'SHOOTOUT', phase_state: 'BREAK' },
  });
  assert.equal(h.buttons[0].props.children, 'hockey_phase_action_REOPEN_MATCH');
  for (const match of [
    { ...base, status: 'RUNNING' },
    { ...base, active_period: 'HALF1' },
    { ...base, status: 'RUNNING', active_period: 'GAME', phase_state: 'ACTIVE' },
  ]) {
    assert.equal(harness({ match }).buttons.length, 0);
  }
});
test('phase success sends only action and uses actual response and backend cache refresh', async () => {
  const h = harness();
  await h.buttons[0].props.onClick();
  assert.equal(
    JSON.stringify(h.requests),
    JSON.stringify([{ url: 'tournaments/7/matches/3/phase', body: { action: 'START_MATCH' } }]),
  );
  assert.equal(h.updates[0].active_period, 'HALF1');
  assert.deepEqual(h.refreshes, [
    'stages',
    'tournaments/7/rankings',
    'tournaments/7/overall_standings',
  ]);
});
for (const status of [403, 409, 422]) {
  test('backend ' + status + ' is not shown as successful', async () => {
    const error = Object.assign(new Error('rejected'), {
      isAxiosError: true,
      response: { status },
    });
    const h = harness({ error });
    await h.buttons[0].props.onClick();
    assert.equal(h.notifications[0], error);
    assert.equal(h.updates.length, status === 409 ? 1 : 0);
    assert.deepEqual(h.refreshes, status === 409 ? ['stages'] : []);
    assert.equal(
      h.states[1],
      status === 403
        ? 'hockey_phase_forbidden'
        : status === 409
          ? 'hockey_phase_conflict'
          : 'hockey_phase_error',
    );
  });
}
test('malformed response cannot create a local successful phase transition', async () => {
  const h = harness({ updated: null });
  await h.buttons[0].props.onClick();
  assert.equal(h.updates.length, 0);
  assert.equal(h.states[1], 'hockey_phase_error');
});
test('successful transition with failed refresh is reported distinctly', async () => {
  const h = harness({ refreshError: new Error('offline') });
  await h.buttons[0].props.onClick();
  assert.equal(h.updates.length, 1);
  assert.equal(h.states[1], 'hockey_phase_refresh_error');
});
for (const option of ['dirty', 'busy'])
  test(option + ' blocks phase requests even through direct invocation', async () => {
    const h = harness({ [option]: true });
    assert.ok(h.buttons[0].props.disabled);
    await h.buttons[0].props.onClick();
    assert.equal(h.requests.length, 0);
  });
test('archived tournament has no executable actions', () => {
  assert.equal(harness({ tournament: { ...config, status: 'ARCHIVED' } }).buttons.length, 0);
});
test('immediate duplicate click sends one request', async () => {
  let release;
  const pending = new Promise((resolve) => {
    release = resolve;
  });
  const h = harness({ pending });
  const first = h.buttons[0].props.onClick();
  await h.buttons[0].props.onClick();
  assert.equal(h.requests.length, 1);
  release();
  await first;
});
test('critical finish/reopen requires explicit confirmation', async () => {
  for (const status of ['RUNNING', 'FINISHED']) {
    const h = harness({
      confirm: false,
      match: {
        ...base,
        status,
        active_period: 'SHOOTOUT',
        phase_state: status === 'RUNNING' ? 'ACTIVE' : 'BREAK',
      },
    });
    await h.buttons[0].props.onClick();
    assert.equal(h.requests.length, 0);
  }
});
for (const source of ['MANUAL', 'EVENTS', null])
  test('source ' + source + ' is never changed by phase action', async () => {
    const h = harness({ match: { ...base, score_entry_source: source } });
    await h.buttons[0].props.onClick();
    assert.deepEqual(Object.keys(h.requests[0].body), ['action']);
  });

test('synchronous dirty callback blocks requests before React rerenders', async () => {
  const h = harness({ hasUnsavedChanges: () => true });
  await h.buttons[0].props.onClick();
  assert.equal(h.requests.length, 0);
});
test('previous sections are labelled without inventing completion history', () => {
  const h = harness({
    match: { ...base, status: 'RUNNING', active_period: 'HALF2', phase_state: 'BREAK' },
  });
  const first = nodes(h.tree).find((node) => node.type === 'Badge' && node.key === 'HALF1');
  assert.ok(first.props.children.includes('hockey_phase_previous'));
  assert.ok(nodes(h.tree).some((node) => node.props?.children === 'hockey_phase_history_note'));
});
