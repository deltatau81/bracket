const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');
const ts = require('typescript');
const root = path.resolve(__dirname, '..');

function load(file, dependencies) {
  const source = fs
    .readFileSync(path.join(root, file), 'utf8')
    .replaceAll('import.meta.env.VITE_API_BASE_URL', 'undefined');
  const compiled = ts.transpileModule(source, {
    compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX },
  }).outputText;
  const module = { exports: {} };
  vm.runInNewContext(compiled, {
    module,
    exports: module.exports,
    require(name) {
      assert.ok(name in dependencies, `Unexpected dependency: ${name}`);
      return dependencies[name];
    },
  });
  return module.exports;
}
const jsx = (type, props, key) => ({ type, props, key });
function nodes(tree) {
  if (Array.isArray(tree)) return tree.flatMap(nodes);
  if (!tree || typeof tree !== 'object') return [];
  return [tree, ...nodes(tree.props?.children)];
}
function harness(response = {}) {
  const calls = [];
  const table = Object.assign(
    () => {},
    Object.fromEntries(
      ['ScrollContainer', 'Thead', 'Tr', 'Th', 'Tbody', 'Td'].map((name) => [
        name,
        'Table.' + name,
      ]),
    ),
  );
  const module = load('src/components/competition/combined_overall_standings.tsx', {
    '@mantine/core': {
      Table: table,
      ...Object.fromEntries(
        ['Alert', 'Button', 'Card', 'Loader', 'Text', 'Title'].map((name) => [name, name]),
      ),
    },
    'react-i18next': {
      useTranslation: () => ({ t: (key, options) => (options ? key + ':' + options.id : key) }),
    },
    'react/jsx-runtime': { jsx, jsxs: jsx },
    '@services/adapter': {
      getTournamentOverallStandings: (id) => {
        calls.push(id);
        return response;
      },
    },
  });
  return { ...module, calls };
}
function standing(values = {}) {
  return {
    team_id: 1,
    team_name: 'Team A',
    club_id: 7,
    club_name: 'Club A',
    game_points: '2.25',
    competition_points: '0.35',
    total_points: '2.60',
    ...values,
  };
}
function rows(h, data, format = 'STANDARD') {
  return nodes(h.OverallStandingsTable({ standings: data, competitionFormat: format })).filter(
    (node) => node.type === 'Table.Tr' && node.key !== undefined,
  );
}
function cells(row) {
  return nodes(row)
    .filter((node) => node.type === 'Table.Td')
    .map((node) => node.props.children);
}
test('STANDARD displays team even when club fields exist', () => {
  assert.equal(cells(rows(harness(), [standing()])[0])[1], 'Team A');
});
test('YOUTH_CLUB displays one preaggregated club row for A/B', () => {
  const data = [standing({ team_id: null, team_name: null })];
  const result = rows(harness(), data, 'YOUTH_CLUB');
  assert.equal(result.length, 1);
  assert.equal(cells(result[0])[1], 'Club A');
  assert.equal(result[0].key, 'club:7');
});
test('unassigned teams remain distinct alongside clubs with the same numeric id', () => {
  const data = [
    standing({ team_id: null, team_name: null }),
    standing({ team_id: 7, club_id: null, club_name: null }),
    standing({ team_id: 8, team_name: 'Team B', club_id: null, club_name: null }),
  ];
  assert.deepEqual(
    rows(harness(), data, 'YOUTH_CLUB').map((row) => row.key),
    ['club:7', 'team:7', 'team:8'],
  );
});
test('nullable and blank names have understandable fallbacks', () => {
  for (const format of ['STANDARD', 'YOUTH_CLUB']) {
    const result = rows(
      harness(),
      [standing({ team_id: null, team_name: null, club_id: null, club_name: null })],
      format,
    );
    assert.equal(cells(result[0])[1], 'overall_standings_unknown_team:?');
  }
  assert.equal(
    cells(rows(harness(), [standing({ club_name: ' ' })], 'YOUTH_CLUB')[0])[1],
    'overall_standings_unknown_club:7',
  );
});
test('decimal strings and backend ordering survive unchanged including ties', () => {
  const data = [
    standing({ team_id: 3, team_name: 'Z', game_points: '999999999999.99', total_points: '0.00' }),
    standing({ team_id: 2, team_name: 'A', total_points: '0.00' }),
  ];
  const before = JSON.stringify(data);
  const result = rows(harness(), data);
  assert.deepEqual(result.map(cells), [
    [1, 'Z', '999999999999.99', '0.35', '0.00'],
    [2, 'A', '2.25', '0.35', '0.00'],
  ]);
  assert.equal(JSON.stringify(data), before);
});
test('empty response displays empty message', () => {
  assert.ok(
    nodes(harness().OverallStandingsTable({ standings: [], competitionFormat: 'STANDARD' })).some(
      (node) => node.props?.children === 'overall_standings_empty',
    ),
  );
});
test('initial load displays Loader', () => {
  const h = harness();
  assert.ok(
    nodes(h.default({ tournamentId: 7, competitionFormat: 'STANDARD' })).some(
      (node) => node.type === 'Loader',
    ),
  );
  assert.deepEqual(h.calls, [7]);
});
test('initial error displays Alert and retry revalidates SWR', () => {
  let retries = 0;
  const h = harness({
    error: new Error('offline'),
    mutate: async () => {
      retries++;
    },
  });
  const tree = h.default({ tournamentId: 7, competitionFormat: 'STANDARD' });
  assert.ok(nodes(tree).some((node) => node.type === 'Alert'));
  assert.ok(!nodes(tree).some((node) => node.type === 'Loader'));
  nodes(tree)
    .find((node) => node.type === 'Button')
    .props.onClick();
  assert.equal(retries, 1);
});
test('background failure preserves API rows with error alert', () => {
  const data = [standing()];
  const h = harness({ data: { data }, error: new Error('offline'), mutate: async () => {} });
  const tree = h.default({ tournamentId: 7, competitionFormat: 'STANDARD' });
  assert.ok(nodes(tree).some((node) => node.type === 'Alert'));
  assert.equal(
    nodes(tree).find((node) => node.type === h.OverallStandingsTable).props.standings,
    data,
  );
});
test('responsive table retains every one of the five columns', () => {
  const tree = harness().OverallStandingsTable({
    standings: [standing()],
    competitionFormat: 'STANDARD',
  });
  assert.equal(tree.type, 'Table.ScrollContainer');
  assert.equal(tree.props.minWidth, 600);
  const headers = nodes(tree).filter((node) => node.type === 'Table.Th');
  assert.equal(headers.length, 5);
  assert.ok(headers.every((node) => node.props.visibleFrom === undefined));
});
test('adapter uses tournament-specific keys, existing fetcher and polling without previous data', async () => {
  const swrCalls = [];
  const requests = [];
  const adapter = load('src/services/adapter.tsx', {
    '@mantine/notifications': {},
    axios: {
      default: {
        create: () => ({
          get: async (url) => {
            requests.push(url);
            return { data: { data: [] } };
          },
        }),
      },
    },
    'react-router': {},
    swr: {
      default: (...args) => {
        swrCalls.push(args);
        return {};
      },
    },
    '@components/utils/util': {},
    dayjs: { default: () => {} },
    './local_storage': { getLogin: () => null },
  });
  adapter.getTournamentOverallStandings(7);
  adapter.getTournamentOverallStandings(8);
  assert.deepEqual(
    swrCalls.map((call) => call[0]),
    ['tournaments/7/overall_standings', 'tournaments/8/overall_standings'],
  );
  for (const [key, fetcher, options] of swrCalls) {
    assert.equal(options.refreshInterval, 5000);
    assert.equal(options.keepPreviousData, false);
    const result = await fetcher(key);
    assert.equal(result.data.length, 0);
  }
  assert.deepEqual(requests, [
    'tournaments/7/overall_standings',
    'tournaments/8/overall_standings',
  ]);
  const source = fs.readFileSync(
    path.join(root, 'src/components/competition/combined_overall_standings.tsx'),
    'utf8',
  );
  assert.ok(!source.includes('getClubs'));
});

test('failed retry remains handled through SWR error state', async () => {
  const h = harness({
    error: new Error('offline'),
    mutate: async () => {
      throw new Error('still offline');
    },
  });
  const tree = h.default({ tournamentId: 7, competitionFormat: 'STANDARD' });
  nodes(tree)
    .find((node) => node.type === 'Button')
    .props.onClick();
  await new Promise((resolve) => setImmediate(resolve));
  assert.ok(nodes(tree).some((node) => node.type === 'Alert'));
});
