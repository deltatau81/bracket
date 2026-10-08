const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');
const ts = require('typescript');

const root = path.resolve(__dirname, '..');

function load(relativePath, dependencies = {}) {
  const source = fs.readFileSync(path.join(root, relativePath), 'utf8');
  const compiled = ts.transpileModule(source, {
    compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX },
  }).outputText;
  const module = { exports: {} };
  vm.runInNewContext(
    compiled,
    {
      module,
      exports: module.exports,
      require(name) {
        assert.ok(name in dependencies, `Unexpected dependency: ${name}`);
        return dependencies[name];
      },
    },
    { filename: relativePath },
  );
  return module.exports;
}

const tournament = {
  id: 7,
  name: 'Stored tournament',
  dashboard_public: true,
  dashboard_endpoint: 'stored',
  players_can_be_in_multiple_teams: false,
  auto_assign_courts: true,
  start_time: '2026-10-07T10:00:00Z',
  duration_minutes: 10,
  margin_minutes: 5,
  competition_format: 'STANDARD',
  hockey_mode: 'COMPETITION',
  status: 'OPEN',
  game_win_points: '3.00',
  game_draw_points: '1.25',
  game_loss_points: '0.35',
  shootout_win_points: '2.00',
  shootout_draw_points: '0.50',
  shootout_loss_points: '0.25',
};

function harness(record = tournament, requestError = null, refetchError = null) {
  const requests = [];
  const notifications = [];
  const states = [];
  let form;
  let refetches = 0;
  const service = load('src/services/tournament.tsx', {
    './adapter': {
      createAxios: () => ({
        put: async (url, body) => {
          requests.push({ url, body });
          if (requestError) throw requestError;
          return { data: { success: true } };
        },
      }),
      handleRequestError: (error) => notifications.push(error),
    },
  });
  const element = (type, props) => ({ type, props });
  const mantine = Object.fromEntries(
    ['Alert', 'Button', 'Fieldset', 'Grid', 'Stack', 'Text', 'TextInput'].map((name) => [
      name,
      name,
    ]),
  );
  mantine.Grid = Object.assign(function Grid() {}, { Col: 'Grid.Col' });
  const component = load('src/components/forms/hockey_scoring.tsx', {
    '@mantine/core': mantine,
    '@mantine/form': {
      useForm(options) {
        form = {
          values: { ...options.initialValues },
          validate: options.validate,
          setValues(values) {
            this.values = { ...values };
          },
          getInputProps(field) {
            return { value: this.values[field], name: field };
          },
          // Exercise the component's own guard even if form validation is bypassed.
          onSubmit(callback) {
            return () => callback(form.values);
          },
        };
        return form;
      },
    },
    react: {
      useRef: (current) => ({ current }),
      useEffect: (effect) => effect(),
      useState(initial) {
        const index = states.length;
        states.push(initial);
        return [
          initial,
          (next) => {
            states[index] = next;
          },
        ];
      },
    },
    'react/jsx-runtime': { jsx: element, jsxs: element },
    '@services/tournament': service,
  });
  const tree = component.default({
    tournament: record,
    mutateTournament: async () => {
      refetches++;
      if (refetchError) throw refetchError;
      return { data: record };
    },
  });
  return {
    component,
    service,
    tree,
    requests,
    notifications,
    states,
    get form() {
      return form;
    },
    get refetches() {
      return refetches;
    },
  };
}

function nodes(tree) {
  if (!tree || typeof tree !== 'object') return [];
  const children = tree.props?.children;
  return [tree, ...[children].flat().flatMap(nodes)];
}

const { normalizeHockeyPoints, normalizeHockeyScoring, getHockeyScoringValues } =
  harness().component;

for (const [input, expected] of [
  ['0.5', '0.5'],
  ['0,5', '0.5'],
  ['0,35', '0.35'],
  ['2', '2'],
  ['0', '0'],
  ['1', '1'],
  ['0.35', '0.35'],
  ['2,25', '2.25'],
  ['999999.99', '999999.99'],
  ['999999,99', '999999.99'],
  ['000002.25', '2.25'],
]) {
  test(`normalizes valid decimal ${input}`, () => {
    assert.equal(normalizeHockeyPoints(input), expected);
  });
}

for (const input of [
  '',
  ' ',
  '-1',
  'abc',
  '.',
  ',',
  '1.234',
  '1,234',
  'NaN',
  'Infinity',
  '1000000',
  '1e2',
  '0,3.5',
]) {
  test(`rejects invalid decimal ${JSON.stringify(input)}`, () => {
    assert.equal(normalizeHockeyPoints(input), null);
  });
}

test('initializes all six inputs from stored API strings', () => {
  const h = harness();
  const inputs = nodes(h.tree).filter((node) => node.type === 'TextInput');
  assert.equal(inputs.length, 6);
  for (const input of inputs) {
    assert.equal(input.props.value, tournament[input.props.name]);
    assert.equal(typeof input.props.value, 'string');
    assert.equal(input.props.inputMode, 'decimal');
  }
  assert.deepEqual(
    Object.keys(getHockeyScoringValues(tournament)).sort(),
    [...h.component.hockeyScoringFields].sort(),
  );
});

test('submits all six normalized decimal strings through the existing service', async () => {
  const h = harness();
  Object.assign(h.form.values, {
    game_win_points: '3',
    game_draw_points: '1,25',
    game_loss_points: '0,35',
    shootout_win_points: '2,25',
    shootout_draw_points: '0,5',
    shootout_loss_points: '0',
  });
  await h.tree.props.onSubmit();
  assert.equal(h.requests.length, 1);
  const { url, body } = h.requests[0];
  assert.equal(url, 'tournaments/7');
  const expected = {
    game_win_points: '3',
    game_draw_points: '1.25',
    game_loss_points: '0.35',
    shootout_win_points: '2.25',
    shootout_draw_points: '0.5',
    shootout_loss_points: '0',
  };
  for (const [field, value] of Object.entries(expected)) assert.equal(body[field], value);
  for (const [field, value] of Object.entries(body)) {
    if (!(field in expected)) assert.equal(value, tournament[field]);
    assert.notEqual(value, null);
  }
  assert.ok(!('hockey_mode' in body));
  assert.ok(!('ruleset' in body));
  assert.equal(h.refetches, 1);
  assert.equal(h.states[1], 'saved');
  for (const field of Object.keys(expected)) assert.equal(h.form.values[field], tournament[field]);
});

for (const field of harness().component.hockeyScoringFields) {
  test(`invalid ${field} prevents the update and refetch`, async () => {
    const h = harness();
    h.form.values[field] = '1,234';
    assert.notEqual(h.form.validate[field](h.form.values[field]), null);
    assert.equal(normalizeHockeyScoring(h.form.values), null);
    await h.tree.props.onSubmit();
    assert.equal(h.requests.length, 0);
    assert.equal(h.refetches, 0);
  });
}

for (const mode of ['COMPETITION', 'GAME_SHOOTOUT']) {
  for (const format of ['STANDARD', 'YOUTH_CLUB']) {
    test(`shows identical six fields for ${mode} / ${format}`, () => {
      const h = harness({ ...tournament, hockey_mode: mode, competition_format: format });
      assert.equal(nodes(h.tree).filter((node) => node.type === 'TextInput').length, 6);
    });
  }
}

test('STANDARD mode does not show the hockey points section', () => {
  assert.equal(harness({ ...tournament, hockey_mode: 'STANDARD' }).tree, null);
});

test('archived tournament cannot submit scoring changes', async () => {
  const h = harness({ ...tournament, status: 'ARCHIVED' });
  assert.ok(
    nodes(h.tree)
      .filter((node) => node.type === 'TextInput')
      .every((node) => node.props.disabled),
  );
  await h.tree.props.onSubmit();
  assert.equal(h.requests.length, 0);
});

test('failed API update shows the existing notification and no success/refetch', async () => {
  const error = Object.assign(new Error('Rejected'), { isAxiosError: true });
  const h = harness(tournament, error);
  await h.tree.props.onSubmit();
  assert.equal(h.requests.length, 1);
  assert.equal(h.notifications[0], error);
  assert.equal(h.refetches, 0);
  assert.equal(h.states[1], 'error');
  assert.equal(h.states[0], false);
});

test('failed refetch shows an error rather than a saved confirmation', async () => {
  const h = harness(tournament, null, new Error('Refetch failed'));
  await h.tree.props.onSubmit();
  assert.equal(h.states[1], 'error');
  assert.equal(h.states[0], false);
});

test('general settings updates omit hockey fields and retain existing error handling', async () => {
  const error = Object.assign(new Error('Rejected'), { isAxiosError: true });
  const h = harness(tournament, error);
  await h.service.updateTournament(
    7,
    tournament.name,
    true,
    'stored',
    false,
    true,
    tournament.start_time,
    10,
    5,
    'STANDARD',
  );
  assert.equal(h.notifications[0], error);
  for (const field of h.component.hockeyScoringFields) assert.ok(!(field in h.requests[0].body));
});

for (const classified of [false, true]) {
  test(`general update forwards the same error and resolves without scoring (AxiosError=${classified})`, async () => {
    const error = new Error('Rejected');
    if (classified) error.isAxiosError = true;
    const h = harness(tournament, error);
    const result = await h.service.updateTournament(
      7,
      tournament.name,
      true,
      'stored',
      false,
      true,
      tournament.start_time,
      10,
      5,
      'STANDARD',
    );
    assert.equal(result, undefined);
    assert.equal(h.notifications.length, 1);
    assert.equal(h.notifications[0], error);
    assert.equal(h.requests.length, 1);
  });

  test(`scoring update forwards then rethrows the same error (AxiosError=${classified})`, async () => {
    const error = new Error('Rejected');
    if (classified) error.isAxiosError = true;
    const h = harness(tournament, error);
    await assert.rejects(
      h.service.updateTournament(
        7,
        tournament.name,
        true,
        'stored',
        false,
        true,
        tournament.start_time,
        10,
        5,
        'STANDARD',
        getHockeyScoringValues(tournament),
      ),
      (caught) => {
        assert.equal(caught, error);
        assert.equal(h.notifications.length, 1);
        assert.equal(h.notifications[0], error);
        return true;
      },
    );
  });
}
