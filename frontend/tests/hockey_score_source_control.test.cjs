const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const test = require('node:test');
const ts = require('typescript');
const axios = require('axios');
const root = path.resolve(__dirname, '..');
const jsx = (type, props) => ({ type, props });
function nodes(tree) {
  if (Array.isArray(tree)) return tree.flatMap(nodes);
  return tree && typeof tree === 'object' ? [tree, ...nodes(tree.props?.children)] : [];
}
function text(tree) {
  if (Array.isArray(tree)) return tree.map(text).join(' ');
  if (tree && typeof tree === 'object') return text(tree.props?.children);
  return tree == null || tree === false ? '' : String(tree);
}
function load(file, dependencies) {
  const module = { exports: {} };
  vm.runInNewContext(
    ts.transpileModule(fs.readFileSync(path.join(root, file), 'utf8'), {
      compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX },
    }).outputText,
    {
      module,
      exports: module.exports,
      require(name) {
        assert.ok(name in dependencies, name);
        return dependencies[name];
      },
    },
  );
  return module.exports;
}
const tournament = {
  id: 7,
  hockey_mode: 'COMPETITION',
  status: 'OPEN',
  competition_format: 'YOUTH_CLUB',
  age_category: 'U9',
};
const match = {
  id: 3,
  status: 'RUNNING',
  active_period: 'HALF1',
  phase_state: 'ACTIVE',
  score_entry_source: 'MANUAL',
};
const phases = load('src/components/matches/hockey_phase_control.tsx', {
  '@mantine/core': {},
  react: {},
  'react-i18next': {},
  swr: {},
  axios: {},
  '@services/match': {},
  'react/jsx-runtime': {},
});
function previewFor(current, target, config = tournament) {
  const periods = phases.hockeyPeriods(config.hockey_mode);
  return {
    match_id: 3,
    current_source: current,
    target_source: target,
    current_scores: periods.map((period) => ({ period, team1_score: 4, team2_score: 3 })),
    resulting_scores: periods.map((period) => ({
      period,
      team1_score: target === 'EVENTS' ? 1 : 4,
      team2_score: target === 'EVENTS' ? 2 : 3,
    })),
    differences: periods.map((period) => ({
      period,
      team1_difference: target === 'EVENTS' ? -3 : 0,
      team2_difference: target === 'EVENTS' ? -1 : 0,
    })),
    relevant_goal_count: 9,
    scores_changed: target === 'EVENTS',
    rankings_may_change: target === 'EVENTS',
    conflict_token: 'a'.repeat(64),
  };
}
const errorFor = (status) =>
  Object.assign(new Error('failed'), { isAxiosError: true, response: { status } });
function harness(options = {}) {
  const requests = [],
    refreshes = [],
    updates = [],
    saving = [],
    dirty = [];
  const states = [],
    refs = [],
    deps = [];
  let cursor, refCursor, effectCursor, effects, tree, changed;
  const react = {
    useState(initial) {
      const i = cursor++;
      if (!(i in states)) states[i] = initial;
      return [
        states[i],
        (next) => {
          const value = typeof next === 'function' ? next(states[i]) : next;
          changed ||= value !== states[i];
          states[i] = value;
        },
      ];
    },
    useRef(current) {
      const i = refCursor++;
      return refs[i] ?? (refs[i] = { current });
    },
    useEffect(effect, values) {
      const i = effectCursor++;
      if (!deps[i] || values.some((v, j) => v !== deps[i][j])) effects.push(effect);
      deps[i] = values;
    },
  };
  const props = {
    tournament: options.tournament ?? tournament,
    match: options.match ?? match,
    role: options.role ?? 'REGULAR',
    teamNames: ['Alpha A', 'Beta B'],
    busy: options.busy ?? false,
    hasBlockedChanges: () => options.blocked === true,
    refreshMatch: async () => {
      refreshes.push('match');
      if (options.refreshError) throw options.refreshError;
      if (options.missingRefresh) return undefined;
      return {
        ...props.match,
        score_entry_source:
          options.freshSource ??
          requests.at(-1)?.body.target_source ??
          props.match.score_entry_source,
      };
    },
    onMatchUpdated: (updated) => {
      updates.push(updated);
      props.match = { ...props.match, ...updated };
    },
    onSavingChange: (value) => saving.push(value),
    onDirtyChange: (value) => dirty.push(value),
  };
  const request = (kind) => async (tid, mid, body) => {
    requests.push({ kind, tid, mid, body: JSON.parse(JSON.stringify(body)) });
    if (options.pending) await options.pending;
    const failure = kind === 'preview' ? options.previewError : options.confirmError;
    if (failure) throw failure;
    const preview =
      options.preview ??
      previewFor(props.match.score_entry_source, body.target_source, props.tournament);
    return {
      data: {
        data:
          kind === 'preview'
            ? preview
            : (options.confirmation ?? {
                active_source: body.target_source,
                match: { ...props.match, score_entry_source: body.target_source },
                current_scores: preview.resulting_scores,
              }),
      },
    };
  };
  const component = load('src/components/matches/hockey_score_source_control.tsx', {
    '@mantine/core': Object.fromEntries(
      [
        'Alert',
        'Badge',
        'Button',
        'Checkbox',
        'Group',
        'Paper',
        'Select',
        'Stack',
        'Text',
        'Title',
      ].map((name) => [name, name]),
    ),
    axios,
    react,
    'react-i18next': {
      useTranslation: () => ({
        t: (key, variables) => (variables ? key + JSON.stringify(variables) : key),
      }),
    },
    swr: {
      useSWRConfig: () => ({
        mutate: async (key) => {
          refreshes.push(key);
          if (options.cacheError) throw options.cacheError;
        },
      }),
    },
    '@services/match_score_source': {
      previewScoreSource: request('preview'),
      confirmScoreSource: request('confirm'),
    },
    '@services/match_event': {
      matchEventsKey: (tid, mid) => 'tournaments/' + tid + '/matches/' + mid + '/events',
    },
    './hockey_phase_control': phases,
    'react/jsx-runtime': { jsx, jsxs: jsx },
  });
  function render(patch) {
    Object.assign(props, patch);
    for (let pass = 0; pass < 5; pass++) {
      cursor = refCursor = effectCursor = 0;
      effects = [];
      changed = false;
      tree = component.default(props);
      effects.forEach((effect) => effect());
      if (!changed) break;
    }
    return tree;
  }
  const find = (type, label) =>
    nodes(tree).find(
      (node) => node.type === type && (node.props.children === label || node.props.label === label),
    );
  render();
  return {
    component,
    options,
    props,
    requests,
    refreshes,
    updates,
    saving,
    dirty,
    render,
    find,
    text: () => text(tree).replace(/\s+/g, ' ').replace(/ : /g, ': '),
    tree: () => tree,
    choose(value) {
      find('Select', 'hockey_source_target').props.onChange(value);
      render();
    },
    approve() {
      find('Checkbox', 'hockey_source_approve').props.onChange({
        currentTarget: { checked: true },
      });
      render();
    },
    click(label) {
      const node = find('Button', label);
      assert.ok(node, label);
      return node.props.onClick();
    },
    async preview(target = 'EVENTS') {
      this.choose(target);
      await this.click('hockey_source_preview');
      render();
    },
    async confirm() {
      this.approve();
      await this.click('hockey_source_confirm');
      render();
    },
  };
}
test('STANDARD hides source control', () => {
  assert.equal(harness({ tournament: { ...tournament, hockey_mode: 'STANDARD' } }).tree(), null);
});
for (const source of ['MANUAL', 'EVENTS', null])
  test('accurate readonly label: ' + source, () => {
    const h = harness({ match: { ...match, score_entry_source: source }, role: 'SCORER' });
    assert.ok(h.find('Badge', 'hockey_source_' + (source ?? 'legacy')));
    assert.ok(h.text().includes('hockey_source_' + (source ?? 'legacy') + '_description'));
    assert.equal(h.requests.length, 0);
    if (source === null) assert.ok(!h.text().includes('hockey_source_MANUAL'));
  });
for (const [current, target] of [
  ['MANUAL', 'EVENTS'],
  ['EVENTS', 'MANUAL'],
  [null, 'MANUAL'],
  [null, 'EVENTS'],
])
  test('explicit preview and confirm: ' + current + ' to ' + target, async () => {
    const h = harness({ match: { ...match, score_entry_source: current } });
    await h.preview(target);
    assert.equal(h.requests.length, 1);
    assert.deepEqual(h.requests[0].body, { target_source: target });
    assert.deepEqual(h.updates, []);
    assert.deepEqual(h.refreshes, []);
    assert.equal(h.props.match.score_entry_source, current);
    assert.ok(h.find('Button', 'hockey_source_confirm').props.disabled);
    await h.click('hockey_source_confirm');
    assert.equal(h.requests.length, 1);
    await h.confirm();
    assert.deepEqual(h.requests[1].body, { target_source: target, conflict_token: 'a'.repeat(64) });
    assert.equal(h.props.match.score_entry_source, target);
    assert.equal(h.dirty.at(-1), false);
    assert.equal(h.saving.at(-1), false);
    assert.ok(!h.find('Button', 'hockey_source_confirm'));
  });
for (const source of ['MANUAL', 'EVENTS'])
  test('active source is a no-op: ' + source, async () => {
    const h = harness({ match: { ...match, score_entry_source: source } });
    h.choose(source);
    assert.ok(h.find('Button', 'hockey_source_preview').props.disabled);
    await h.click('hockey_source_preview');
    assert.equal(h.requests.length, 0);
  });
test('cancel sends no confirm and preserves source', async () => {
  const h = harness();
  await h.preview();
  await h.click('hockey_source_cancel');
  h.render();
  assert.equal(h.requests.length, 1);
  assert.equal(h.props.match.score_entry_source, 'MANUAL');
  assert.equal(h.dirty.at(-1), false);
  assert.ok(!h.find('Button', 'hockey_source_confirm'));
});
for (const mode of ['GAME_SHOOTOUT', 'COMPETITION'])
  test('backend section values only: ' + mode, async () => {
    const config = { ...tournament, hockey_mode: mode };
    const preview = previewFor('MANUAL', 'EVENTS', config);
    preview.resulting_scores[0].team1_score = 17;
    preview.differences[0].team1_difference = 101;
    const h = harness({ tournament: config, preview });
    await h.preview();
    const content = h.text();
    for (const period of phases.hockeyPeriods(mode))
      assert.ok(content.includes('hockey_phase_period_' + period));
    assert.ok(content.includes('Alpha A: hockey_source_before 4'));
    assert.ok(content.includes('hockey_source_after 17'));
    assert.ok(content.includes('hockey_source_difference 101'));
    assert.ok(!content.includes('hockey_phase_period_TOTAL'));
    assert.ok(!content.includes('hockey_score_total'));
    assert.ok(content.includes('hockey_source_scores_changed'));
    assert.ok(content.includes('hockey_source_rankings_changed'));
  });
test('zero GOAL warning uses backend zeros without creating events', async () => {
  const preview = previewFor('MANUAL', 'EVENTS');
  preview.relevant_goal_count = 0;
  preview.resulting_scores.forEach((s) => {
    s.team1_score = 0;
    s.team2_score = 0;
  });
  const h = harness({ preview });
  await h.preview();
  assert.ok(h.find('Alert', 'hockey_source_zero_warning'));
  assert.ok(h.text().includes('hockey_source_after 0'));
  assert.equal(h.requests.length, 1);
});
test('EVENTS to MANUAL explains preservation', async () => {
  const h = harness({ match: { ...match, score_entry_source: 'EVENTS' } });
  await h.preview('MANUAL');
  assert.ok(h.text().includes('hockey_source_to_manual'));
  assert.ok(h.text().includes('hockey_source_events_preserved'));
  assert.ok(!h.find('Alert', 'hockey_source_scores_changed'));
});
test('target change invalidates token and approval synchronously', async () => {
  const h = harness({ match: { ...match, score_entry_source: null } });
  await h.preview();
  h.approve();
  const oldConfirm = h.find('Button', 'hockey_source_confirm').props.onClick;
  h.choose('MANUAL');
  await oldConfirm();
  assert.equal(h.requests.length, 1);
  assert.ok(!h.find('Button', 'hockey_source_confirm'));
});
test('changed match invalidates preview', async () => {
  const h = harness();
  await h.preview();
  h.approve();
  h.render({ match: { ...h.props.match, phase_state: 'BREAK' } });
  assert.ok(h.find('Alert', 'hockey_source_conflict'));
  assert.ok(!h.find('Button', 'hockey_source_confirm'));
});
test('409 requires new preview and approval, never retries confirm', async () => {
  const h = harness({ confirmError: errorFor(409) });
  await h.preview();
  await h.confirm();
  assert.ok(h.find('Alert', 'hockey_source_conflict'));
  assert.equal(h.requests.length, 2);
  assert.deepEqual(h.updates, []);
  assert.ok(!h.find('Button', 'hockey_source_confirm'));
  h.options.confirmError = null;
  await h.click('hockey_source_preview');
  h.render();
  assert.equal(h.requests.length, 3);
  assert.ok(h.find('Button', 'hockey_source_confirm').props.disabled);
  assert.equal(h.requests.filter((r) => r.kind === 'confirm').length, 1);
});
for (const status of [401, 403, 404, 400, 422, 500])
  test('preview error ' + status, async () => {
    const h = harness({ previewError: errorFor(status) });
    await h.preview();
    const key =
      status === 401 || status === 403
        ? 'forbidden'
        : status === 404
          ? 'missing'
          : status === 400
            ? 'archived'
            : status === 422
              ? 'invalid'
              : 'error';
    assert.ok(h.find('Alert', 'hockey_source_' + key));
    assert.ok(!h.find('Button', 'hockey_source_confirm'));
    assert.equal(h.requests.length, 1);
    assert.deepEqual(h.updates, []);
  });
test('preview network failure releases request lock without updates', async () => {
  const h = harness({ previewError: new Error('offline') });
  await h.preview();
  assert.ok(h.find('Alert', 'hockey_source_error'));
  assert.deepEqual(h.updates, []);
  assert.deepEqual(h.saving, [true, false]);
});
for (const status of [undefined, 408, 500])
  test('unknown confirm outcome reconciles through GET without retry: ' + status, async () => {
    const h = harness({
      confirmError: status ? errorFor(status) : new Error('timeout'),
      freshSource: 'EVENTS',
    });
    await h.preview();
    await h.confirm();
    assert.equal(h.requests.filter((r) => r.kind === 'confirm').length, 1);
    assert.equal(h.props.match.score_entry_source, 'EVENTS');
    assert.ok(h.refreshes.includes('match'));
    assert.ok(h.find('Alert', 'hockey_source_uncertain'));
    assert.ok(!h.find('Button', 'hockey_source_confirm'));
    assert.equal(h.dirty.at(-1), false);
  });
test('failed GET after uncertain confirm permits only reloading', async () => {
  const h = harness({ confirmError: new Error('timeout'), refreshError: new Error('GET failed') });
  await h.preview();
  await h.confirm();
  assert.ok(h.find('Button', 'hockey_source_reload'));
  assert.ok(!h.find('Select', 'hockey_source_target'));
  assert.equal(h.dirty.at(-1), true);
  h.options.refreshError = null;
  h.options.freshSource = 'EVENTS';
  await h.click('hockey_source_reload');
  h.render();
  assert.equal(h.requests.length, 2);
  assert.equal(h.props.match.score_entry_source, 'EVENTS');
  assert.equal(h.dirty.at(-1), false);
});
test('successful confirm with failed cache refresh remains review-only', async () => {
  const h = harness({ cacheError: new Error('cache failed') });
  await h.preview();
  await h.confirm();
  assert.ok(h.find('Alert', 'hockey_source_refresh_error'));
  assert.ok(h.find('Button', 'hockey_source_reload'));
  assert.equal(h.props.match.score_entry_source, 'EVENTS');
  assert.equal(h.dirty.at(-1), true);
  h.options.cacheError = null;
  await h.click('hockey_source_reload');
  h.render();
  assert.equal(h.requests.length, 2);
  assert.equal(h.dirty.at(-1), false);
});
for (const role of ['SCORER', 'DEMO'])
  test('readonly role cannot switch: ' + role, () => {
    const h = harness({ role });
    assert.ok(h.find('Badge', 'hockey_source_MANUAL'));
    assert.ok(!h.find('Select', 'hockey_source_target'));
    assert.equal(h.component.canAdministerScoreSource(role), false);
  });
for (const role of ['REGULAR', 'ADMIN'])
  test('administrative role can preview: ' + role, async () => {
    const h = harness({ role });
    await h.preview();
    assert.equal(h.requests.length, 1);
  });
test('archived tournament hides switching controls', () => {
  const h = harness({ tournament: { ...tournament, status: 'ARCHIVED' } });
  assert.ok(h.find('Badge', 'hockey_source_MANUAL'));
  assert.ok(!h.find('Select', 'hockey_source_target'));
});
test('archiving or revoking role after preview blocks confirmation', async () => {
  for (const patch of [{ tournament: { ...tournament, status: 'ARCHIVED' } }, { role: 'SCORER' }]) {
    const h = harness();
    await h.preview();
    h.approve();
    h.render(patch);
    await h.click('hockey_source_confirm');
    assert.equal(h.requests.length, 1);
  }
});
for (const blocked of ['unsaved scores', 'event draft', 'pending match mutation'])
  test('dynamic guard blocks ' + blocked, async () => {
    const h = harness();
    h.choose('EVENTS');
    h.options.blocked = true;
    await h.click('hockey_source_preview');
    h.render();
    assert.equal(h.requests.length, 0);
    assert.ok(h.find('Alert', 'hockey_source_dirty'));
    assert.ok(h.find('Button', 'hockey_source_preview').props.disabled);
  });
for (const kind of ['preview', 'confirm'])
  test('duplicate ' + kind + ' click is synchronously blocked', async () => {
    const h = harness();
    if (kind === 'confirm') {
      await h.preview();
      h.approve();
    } else h.choose('EVENTS');
    let release;
    h.options.pending = new Promise((resolve) => {
      release = resolve;
    });
    const first = h.click('hockey_source_' + kind);
    await h.click('hockey_source_' + kind);
    assert.equal(h.requests.filter((r) => r.kind === kind).length, 1);
    release();
    await first;
  });
test('success refreshes match, events, rankings and shared club standings cache', async () => {
  const h = harness();
  await h.preview();
  await h.confirm();
  assert.deepEqual(h.refreshes, [
    'match',
    'tournaments/7/matches/3/events',
    'tournaments/7/rankings',
    'tournaments/7/next_stage_rankings',
    'tournaments/7/overall_standings',
  ]);
});
for (const patch of [
  { match_id: 99 },
  { target_source: 'MANUAL' },
  { conflict_token: 'bad' },
  { resulting_scores: [] },
  { differences: [] },
  { relevant_goal_count: -1 },
  { current_source: 'invented' },
])
  test('reject malformed preview: ' + Object.keys(patch)[0], async () => {
    const h = harness({ preview: { ...previewFor('MANUAL', 'EVENTS'), ...patch } });
    await h.preview();
    assert.ok(h.find('Alert', 'hockey_source_error'));
    assert.ok(!h.find('Button', 'hockey_source_confirm'));
    assert.deepEqual(h.updates, []);
  });
test('unrelated confirm is uncertain and only GET supplies match update', async () => {
  const h = harness({
    confirmation: {
      active_source: 'EVENTS',
      match: { ...match, id: 999, score_entry_source: 'EVENTS' },
      current_scores: previewFor('MANUAL', 'EVENTS').resulting_scores,
    },
  });
  await h.preview();
  await h.confirm();
  assert.ok(h.find('Alert', 'hockey_source_uncertain'));
  assert.ok(h.updates.every((m) => m.id === 3));
  assert.equal(h.requests.length, 2);
});
test('missing refreshed match cannot unlock uncertain switch', async () => {
  const h = harness({ confirmError: new Error('timeout'), missingRefresh: true });
  await h.preview();
  await h.confirm();
  assert.ok(h.find('Button', 'hockey_source_reload'));
  assert.equal(h.dirty.at(-1), true);
});
test('hockey_mode overrides age assumptions', async () => {
  const h = harness({
    tournament: { ...tournament, hockey_mode: 'GAME_SHOOTOUT', age_category: 'U17' },
  });
  await h.preview();
  assert.ok(h.text().includes('hockey_phase_period_GAME'));
  assert.ok(!h.text().includes('hockey_phase_period_HALF1'));
});
test('source translations exist in both languages with matching placeholders', () => {
  const source = fs.readFileSync(
    path.join(root, 'src/components/matches/hockey_score_source_control.tsx'),
    'utf8',
  );
  const de = JSON.parse(fs.readFileSync(path.join(root, 'public/locales/de/common.json'), 'utf8'));
  const en = JSON.parse(fs.readFileSync(path.join(root, 'public/locales/en/common.json'), 'utf8'));
  const keys = Object.keys(de).filter((k) => k.startsWith('hockey_source_'));
  assert.ok(keys.length > 25);
  for (const key of keys) {
    assert.ok(en[key]);
    assert.deepEqual(de[key].match(/{{.*?}}/g), en[key].match(/{{.*?}}/g));
  }
  for (const [, key] of source.matchAll(/'(hockey_source_[A-Za-z_]+)'/g)) assert.ok(de[key], key);
  assert.equal(de.hockey_source_legacy, 'Bisherige Ergebniserfassung');
});

// Execute the actual generated SDK and axios client; the adapter never uses a network.
function realService(failure) {
  const cache = new Map(),
    requests = [],
    errors = [];
  const baseURL = 'https://bracket.example/api';
  const instance = axios.create({
    baseURL,
    headers: { Authorization: 'bearer test-token' },
    adapter: async (config) => {
      const body = JSON.parse(config.data);
      requests.push({
        url: config.url,
        method: config.method,
        body,
        authorization: config.headers.get('Authorization'),
      });
      if (failure) throw failure;
      const data = config.url.endsWith('/preview')
        ? previewFor('MANUAL', body.target_source)
        : {
            active_source: body.target_source,
            match: { ...match, score_entry_source: body.target_source },
            current_scores: previewFor('MANUAL', body.target_source).resulting_scores,
          };
      return { data: { data }, status: 200, statusText: 'OK', headers: {}, config };
    },
  });
  function resolve(file) {
    for (const candidate of [file, file + '.ts', file + '.tsx', path.join(file, 'index.ts')])
      if (fs.existsSync(candidate) && fs.statSync(candidate).isFile()) return candidate;
    throw new Error('Module not found: ' + file);
  }
  function generated(file) {
    file = resolve(file);
    if (cache.has(file)) return cache.get(file).exports;
    const module = { exports: {} };
    cache.set(file, module);
    const source = ts.transpileModule(fs.readFileSync(file, 'utf8'), {
      compilerOptions: { module: ts.ModuleKind.CommonJS },
    }).outputText;
    vm.runInNewContext(source, {
      module,
      exports: module.exports,
      URL,
      Headers,
      Request,
      Response,
      FormData,
      Blob,
      AbortController,
      TextEncoder,
      fetch,
      require(name) {
        if (name === 'axios') return axios;
        assert.ok(name.startsWith('.'), name);
        return generated(path.resolve(path.dirname(file), name));
      },
    });
    return module.exports;
  }
  const service = load('src/services/match_score_source.tsx', {
    '@openapi': generated(path.join(root, 'src/openapi/index.ts')),
    '@openapi/client': generated(path.join(root, 'src/openapi/client/index.ts')),
    './adapter': {
      createAxios: () => instance,
      getBaseApiUrl: () => baseURL,
      handleRequestError: (error) => errors.push(error),
    },
  });
  return { service, requests, errors };
}
test('real generated preview SDK preserves prefix, authorization, envelope and request body', async () => {
  const h = realService();
  const result = await h.service.previewScoreSource(7, 3, { target_source: 'EVENTS' });
  assert.equal(result.data.data.match_id, 3);
  assert.equal(result.data.data.conflict_token, 'a'.repeat(64));
  assert.deepEqual(h.requests, [
    {
      method: 'post',
      url: 'https://bracket.example/api/tournaments/7/matches/3/score-source/preview',
      body: { target_source: 'EVENTS' },
      authorization: 'bearer test-token',
    },
  ]);
});
test('real generated confirm SDK preserves token and response envelope', async () => {
  const h = realService();
  const body = { target_source: 'EVENTS', conflict_token: 'b'.repeat(64) };
  const result = await h.service.confirmScoreSource(7, 3, body);
  assert.equal(result.data.data.active_source, 'EVENTS');
  assert.deepEqual(h.requests[0].body, body);
  assert.equal(
    h.requests[0].url,
    'https://bracket.example/api/tournaments/7/matches/3/score-source/confirm',
  );
});
for (const method of ['previewScoreSource', 'confirmScoreSource'])
  test('service forwards and rethrows same non-Axios error without retry: ' + method, async () => {
    const error = new Error('offline');
    const h = realService(error);
    await assert.rejects(
      h.service[method](7, 3, {
        target_source: 'EVENTS',
        ...(method === 'confirmScoreSource' ? { conflict_token: 'a'.repeat(64) } : {}),
      }),
      (caught) => caught === error,
    );
    assert.deepEqual(h.errors, [error]);
    assert.equal(h.requests.length, 1);
  });

test('403 during confirmation allows cancelling selection without another mutation', async () => {
  const h = harness({ confirmError: errorFor(403) });
  await h.preview();
  await h.confirm();
  assert.ok(h.find('Alert', 'hockey_source_forbidden'));
  await h.click('hockey_source_cancel');
  h.render();
  assert.equal(h.dirty.at(-1), false);
  assert.equal(h.requests.length, 2);
  assert.equal(h.props.match.score_entry_source, 'MANUAL');
});
test('stale cancel handler cannot unlock an uncertain confirmation before fresh GET', async () => {
  const h = harness({ confirmError: new Error('timeout'), refreshError: new Error('offline') });
  await h.preview();
  const cancel = h.find('Button', 'hockey_source_cancel').props.onClick;
  await h.confirm();
  cancel();
  h.render();
  assert.equal(h.dirty.at(-1), true);
  assert.ok(h.find('Button', 'hockey_source_reload'));
  assert.ok(!h.find('Select', 'hockey_source_target'));
});
