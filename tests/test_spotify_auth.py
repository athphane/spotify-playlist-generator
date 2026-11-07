import importlib.util
import json
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import Mock, patch

import requests
from spotipy.cache_handler import CacheFileHandler
from spotipy.oauth2 import SpotifyOAuth, SpotifyOauthError

from spotify_auth import RecoveringSpotifyOAuth, SpotifyAuthorizationRequired


class SpotifyAuthTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.cache = CacheFileHandler(cache_path=str(Path(self.directory.name) / '.cache'))
        self.old_token = {
            'access_token': 'old-access', 'refresh_token': 'old-refresh',
            'expires_at': 0, 'scope': 'user-library-read',
        }
        self.cache.save_token_to_cache(self.old_token)
        self.session = Mock(spec=requests.Session)
        self.oauth = RecoveringSpotifyOAuth(
            client_id='test-client', client_secret='test-secret',
            redirect_uri='http://127.0.0.1:8888/callback',
            scope='user-library-read', cache_handler=self.cache,
            requests_session=self.session,
        )

    @staticmethod
    def response(status, data):
        response = requests.Response()
        response.status_code = status
        response._content = json.dumps(data).encode()
        return response

    def test_revoked_token_is_replaced_through_authorization(self):
        self.session.post.side_effect = [
            self.response(400, {'error': 'invalid_grant',
                                'error_description': 'Refresh token revoked'}),
            self.response(200, {'access_token': 'new-access',
                                'refresh_token': 'new-refresh', 'expires_in': 3600}),
        ]
        with patch('spotify_auth.sys.stdin.isatty', return_value=True), \
                patch.object(SpotifyOAuth, 'get_auth_response', return_value='new-code'):
            self.assertEqual(self.oauth.get_access_token(as_dict=False), 'new-access')

        self.assertEqual(self.cache.get_cached_token()['refresh_token'], 'new-refresh')
        grants = [call.kwargs['data']['grant_type']
                  for call in self.session.post.call_args_list]
        self.assertEqual(grants, ['refresh_token', 'authorization_code'])
        self.assertEqual(self.session.post.call_args_list[1].kwargs['data']['code'],
                         'new-code')

    def test_cron_discards_revoked_token_and_exits_without_prompting(self):
        self.session.post.return_value = self.response(400, {'error': 'invalid_grant'})
        with patch('spotify_auth.sys.stdin.isatty', return_value=False), \
                patch.object(SpotifyOAuth, 'get_auth_response') as prompt:
            for _ in range(2):
                with self.assertRaisesRegex(SpotifyAuthorizationRequired, '--reauthorize'):
                    self.oauth.get_access_token(as_dict=False)
            prompt.assert_not_called()
        self.assertIsNone(self.cache.get_cached_token())
        self.session.post.assert_called_once()

    def test_other_oauth_errors_preserve_cache_and_do_not_prompt(self):
        self.session.post.return_value = self.response(400, {'error': 'invalid_client'})
        with patch.object(SpotifyOAuth, 'get_auth_response') as prompt:
            with self.assertRaises(SpotifyOauthError) as caught:
                self.oauth.get_access_token(as_dict=False)
            self.assertEqual(caught.exception.error, 'invalid_client')
            prompt.assert_not_called()
        self.assertEqual(self.cache.get_cached_token(), self.old_token)

    def test_valid_cached_token_works_without_terminal_or_network(self):
        token = dict(self.old_token, expires_at=int(time.time()) + 3600)
        self.cache.save_token_to_cache(token)
        with patch('spotify_auth.sys.stdin.isatty', return_value=False):
            self.assertEqual(self.oauth.get_access_token(as_dict=False), 'old-access')
        self.session.post.assert_not_called()

    def test_normal_refresh_preserves_refresh_token(self):
        self.session.post.return_value = self.response(
            200, {'access_token': 'refreshed-access', 'expires_in': 3600})
        with patch('spotify_auth.sys.stdin.isatty', return_value=False):
            self.assertEqual(self.oauth.get_access_token(as_dict=False), 'refreshed-access')
        self.assertEqual(self.cache.get_cached_token()['refresh_token'], 'old-refresh')

    def test_failed_reauthorization_is_not_retried(self):
        self.session.post.return_value = self.response(400, {'error': 'invalid_grant'})
        with patch('spotify_auth.sys.stdin.isatty', return_value=True), \
                patch.object(SpotifyOAuth, 'get_auth_response', return_value='bad-code'):
            with self.assertRaises(SpotifyOauthError):
                self.oauth.get_access_token(as_dict=False)
        self.assertEqual(self.session.post.call_count, 2)

    def test_reauthorize_command_only_authenticates(self):
        source = Path(__file__).resolve().parents[1] / 'main.py'
        config = Path(self.directory.name) / 'config.ini'
        config.write_text('[spotify]\nclient_id=test\nclient_secret=test\n'
                          'redirect_uri=http://127.0.0.1:8888/callback\n'
                          '[ntfy]\nurl=https://example.com\nauth=test\n')
        previous_cwd = os.getcwd()
        os.chdir(self.directory.name)
        self.addCleanup(os.chdir, previous_cwd)
        spec = importlib.util.spec_from_file_location('playlist_main', source)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        playlists = Path('playlists.json')
        playlists.write_text('{"2026-11": "existing-playlist"}')
        with patch('sys.argv', ['main.py', '--reauthorize']), \
                patch.object(module, 'spotify_oauth') as oauth, \
                patch.object(module, 'spotify') as spotify:
            oauth.get_auth_response.return_value = 'new-code'
            module.main()
            oauth.get_auth_response.assert_called_once_with(open_browser=False)
            oauth.get_access_token.assert_called_once_with(
                code='new-code', as_dict=False, check_cache=False)
            self.assertEqual(spotify.mock_calls, [])
        self.assertEqual(playlists.read_text(), '{"2026-11": "existing-playlist"}')


if __name__ == '__main__':
    unittest.main()
