// Execute the shipped callback script in an isolated browser-like context.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync('frontend/oauth-callback.js', 'utf8');

async function callback({ query = '?code=SYNTHETIC-CODE&state=SYNTHETIC-STATE',
  context = { case_id: 'synthetic-case', account_id: 'synthetic-account' }, ok = true,
  failNetwork = false } = {}) {
  const state = new Map(context ? [['fca-oauth', JSON.stringify(context)]] : []);
  const result = { textContent: '', links: [], append(link) { this.links.push(link); } };
  const seen = { requests: [], replacements: [], history: [] };
  await vm.runInNewContext(source, {
    URLSearchParams,
    location: { search: query, replace(url) { seen.replacements.push(url); } },
    history: { replaceState(_state, _title, url) { seen.history.push(url); } },
    sessionStorage: { getItem: k => state.get(k) || null, removeItem: k => state.delete(k), setItem: (k, v) => state.set(k, v) },
    document: { cookie: '__Host-fca_csrf=SYNTHETIC-CSRF', getElementById: () => result, createElement: () => ({}) },
    fetch: async (url, options) => {
      assert.deepEqual(seen.history, ['/api/oauth/callback']);
      assert.equal(state.has('fca-oauth'), false);
      seen.requests.push({ url, options });
      if (failNetwork) throw Error('SYNTHETIC-PRIVATE-ERROR');
      return { ok };
    },
  });
  return { state, result, ...seen };
}

test('successful callback removes URL secrets before same-origin CSRF request and restores case', async () => {
  const out = await callback();
  assert.equal(out.requests[0].url, '/api/oauth/complete');
  assert.equal(out.requests[0].options.headers['X-CSRF-Token'], 'SYNTHETIC-CSRF');
  assert.equal(JSON.parse(out.requests[0].options.body).account_id, 'synthetic-account');
  assert.equal(out.state.get('fca-return-case'), 'synthetic-case');
  assert.deepEqual(out.replacements, ['/']);
});

for (const [name, input] of [
  ['consent denied', { query: '?error=access_denied&error_description=SYNTHETIC-PRIVATE-ERROR' }],
  ['missing browser session', { context: null }],
  ['missing authorization code', { query: '?state=SYNTHETIC-STATE' }],
  ['server rejects callback', { ok: false }],
  ['network interrupted', { failNetwork: true }],
]) {
  test(name + ' gives safe recovery without losing URL cleanup', async () => {
    const out = await callback(input);
    assert.deepEqual(out.history, ['/api/oauth/callback']);
    assert.equal(out.state.has('fca-oauth'), false);
    assert.equal(out.state.has('fca-return-case'), false);
    assert.deepEqual(out.replacements, []);
    assert.match(out.result.textContent, /Anmeldung konnte nicht abgeschlossen/);
    assert.doesNotMatch(out.result.textContent, /SYNTHETIC/);
    assert.equal(out.result.links[0].href, '/');
  });
}
