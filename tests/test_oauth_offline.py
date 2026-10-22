"""Real encrypted FCA OAuth state, synthetic provider only; no database/network."""
import base64
import hashlib
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit
from uuid import uuid4

from backend import oauth
from providers.apple.adapter import ProviderError


class GoogleOfflineFlow(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name).resolve()
        key = root / 'key'
        key.write_text('SYNTHETIC-' + 'x' * 64)
        key.chmod(0o600)
        self.auth = root / 'auth'
        self.auth.mkdir(mode=0o700)
        env = patch.dict(os.environ, {
            'FCA_CLOUD_MASTER_KEY_FILE': str(key),
            'FCA_CLOUD_AUTH_ROOT': str(self.auth),
            'FCA_OAUTH_CONFIG_FILE': str(root / 'absent'),
        })
        env.start()
        self.addCleanup(env.stop)
        self.case, self.account, self.user = uuid4(), uuid4(), uuid4()
        self.redirect = 'https://fca.example.org/api/oauth/callback'
        oauth.save_configuration('google', 'SYNTHETIC-CLIENT', 'SYNTHETIC-SECRET', self.redirect)

    def begin(self, account=None):
        account = account or self.account
        result = oauth.begin('google', self.case, account, self.user, session_id='synthetic-session')
        return parse_qs(urlsplit(result['url']).query), oauth.load(self.case, account)['pending']

    def complete(self, pending, **overrides):
        args = dict(provider='google', case_id=self.case, account_id=self.account,
                    user_id=self.user, state=pending['state'], code='SYNTHETIC-CODE',
                    session_id='synthetic-session')
        args.update(overrides)
        return oauth.complete(**args)

    def test_pkce_offline_access_and_registered_return_address(self):
        query, pending = self.begin()
        expected = base64.urlsafe_b64encode(hashlib.sha256(pending['verifier'].encode()).digest()).decode().rstrip('=')
        self.assertEqual(query['code_challenge'], [expected])
        self.assertEqual(query['code_challenge_method'], ['S256'])
        self.assertEqual(query['redirect_uri'], [self.redirect])
        self.assertEqual(query['access_type'], ['offline'])
        self.assertEqual(query['response_type'], ['code'])
        self.assertNotIn('client_secret', query)
        self.assertNotIn('code_verifier', query)

    def test_separate_accounts_and_case_cannot_reuse_pending_login(self):
        _, first = self.begin()
        _, second = self.begin(uuid4())
        self.assertNotEqual(first['state'], second['state'])
        with patch.object(oauth, 'exchange') as exchange:
            for changes in ({'account_id': uuid4()}, {'case_id': uuid4()},
                            {'user_id': uuid4()}, {'session_id': 'different-session'},
                            {'state': 'synthetic-wrong-state'}, {'provider': 'microsoft'}):
                with self.subTest(changes=tuple(changes)):
                    with self.assertRaises(ProviderError):
                        self.complete(first, **changes)
            exchange.assert_not_called()

    def test_tokens_remain_encrypted_and_state_is_one_use(self):
        _, pending = self.begin()
        with patch.object(oauth, 'exchange', return_value={
            'access_token': 'SYNTHETIC-ACCESS', 'refresh_token': 'SYNTHETIC-REFRESH', 'expires_in': 3600,
        }) as exchange:
            self.assertEqual(self.complete(pending), {'status': 'connected'})
            sent = exchange.call_args.args[1]
            self.assertEqual(sent['code_verifier'], pending['verifier'])
            self.assertEqual(sent['redirect_uri'], self.redirect)
            self.assertEqual(oauth.token('google', self.case, self.account), 'SYNTHETIC-ACCESS')
            with self.assertRaises(ProviderError):
                self.complete(pending)
            self.assertEqual(exchange.call_count, 1)
        for file in self.auth.rglob('oauth.enc'):
            self.assertEqual(file.stat().st_mode & 0o777, 0o600)
            self.assertNotIn(b'SYNTHETIC-', file.read_bytes())
        self.assertNotIn('pending', oauth.load(self.case, self.account))

    def test_expired_or_changed_registration_rejected_before_exchange(self):
        for change in ('expired', 'client', 'redirect'):
            with self.subTest(change=change):
                oauth.save_configuration('google', 'SYNTHETIC-CLIENT', 'SYNTHETIC-SECRET', self.redirect)
                _, pending = self.begin()
                if change == 'expired':
                    state = oauth.load(self.case, self.account)
                    state['pending']['expires'] = time.time() - 1
                    oauth.save(self.case, self.account, state)
                elif change == 'client':
                    oauth.save_configuration('google', 'DIFFERENT', 'SYNTHETIC-SECRET', self.redirect)
                else:
                    oauth.save_configuration('google', 'SYNTHETIC-CLIENT', 'SYNTHETIC-SECRET', 'https://other.example.org/api/oauth/callback')
                with patch.object(oauth, 'exchange') as exchange:
                    with self.assertRaises(ProviderError):
                        self.complete(pending)
                    exchange.assert_not_called()

    def test_exchange_failure_consumes_state_and_does_not_publish_tokens(self):
        _, pending = self.begin()
        with patch.object(oauth, 'exchange', side_effect=ProviderError('Synthetischer Anbieterfehler.')) as exchange:
            with self.assertRaises(ProviderError):
                self.complete(pending)
            with self.assertRaises(ProviderError):
                self.complete(pending)
            self.assertEqual(exchange.call_count, 1)
        self.assertNotIn('access_token', oauth.load(self.case, self.account))

    def test_refresh_preserves_existing_refresh_token(self):
        oauth.save(self.case, self.account, {'access_token': 'SYNTHETIC-OLD',
                   'refresh_token': 'SYNTHETIC-REFRESH', 'expires_at': 0})
        with patch.object(oauth, 'exchange', return_value={'access_token': 'SYNTHETIC-NEW', 'expires_in': 3600}) as exchange:
            self.assertEqual(oauth.token('google', self.case, self.account), 'SYNTHETIC-NEW')
            self.assertEqual(exchange.call_args.args[1]['grant_type'], 'refresh_token')
        self.assertEqual(oauth.load(self.case, self.account)['refresh_token'], 'SYNTHETIC-REFRESH')

    def test_exchange_error_redacts_upstream_secrets(self):
        with patch.object(oauth.urllib.request, 'urlopen', side_effect=RuntimeError('SYNTHETIC-SECRET')):
            with self.assertRaises(ProviderError) as caught:
                oauth.exchange('google', {'grant_type': 'authorization_code', 'code': 'SYNTHETIC-CODE'})
        self.assertNotIn('SYNTHETIC-', str(caught.exception))


if __name__ == '__main__':
    unittest.main()
