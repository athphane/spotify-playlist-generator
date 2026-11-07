import sys

from spotipy.oauth2 import SpotifyOAuth, SpotifyOauthError


class SpotifyAuthorizationRequired(RuntimeError):
    pass


class RecoveringSpotifyOAuth(SpotifyOAuth):
    def validate_token(self, token_info):
        try:
            return super().validate_token(token_info)
        except SpotifyOauthError as error:
            if error.error != 'invalid_grant':
                raise

            # A revoked refresh token cannot be retried. Let Spotipy start
            # authorization again, and stop future runs from reusing it.
            self.cache_handler.save_token_to_cache(None)
            print('Spotify authorization expired or was revoked. Sign in again.',
                  file=sys.stderr)
            return None

    def get_auth_response(self, open_browser=None):
        if not sys.stdin.isatty():
            raise SpotifyAuthorizationRequired(
                'Spotify sign-in requires an interactive terminal. '
                'From the project directory, run '
                '`venv/bin/python main.py --reauthorize` or, for Docker, '
                '`docker compose run --rm playlist --reauthorize`, '
                'then rerun the job.'
            )
        return super().get_auth_response(open_browser=open_browser)
