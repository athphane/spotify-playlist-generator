## Playlists from Liked Songs. 

This project takes all of your liked songs on spotify, groups them by the year and month you liked them
and then creates playlists on your account for each group.

### Why?
Honestly, idk. This is me procrastinating and not doing my university assignments.

### How to run it?
- install requirements mentioned in the requirements.txt file. 
- copy config.ini.sample to config.ini.
- replace values in config file to your own spotify client id and secret.
- In your app's Spotify Developer Dashboard settings, add
  `http://127.0.0.1:8888/callback` as a Redirect URI and save. The `redirect_uri`
  in `config.ini` must match this value exactly.
- python main.py
- Approve the spotify oauth screen.
- Profit.

If you run it again, it wont duplicate the playlists. Instead it will add the new songs you like to the top of the existing playlist. Makes it look nicer. Ya know. 

### Spotify sign-in expired or revoked

If Spotify reports `invalid_grant` / `Refresh token revoked`, the cached refresh
token no longer works. Interactive runs will ask you to authorize again.
Scheduled runs exit with instructions instead of waiting for browser input.

To sign in again without updating playlists, run this from the project directory
in an interactive terminal, using the same user and environment as your scheduled job:

```sh
venv/bin/python main.py --reauthorize
```

Open the printed Spotify URL, approve access, and paste the full redirect URL back
into the terminal (even if the callback page fails to load). New tokens are saved
in Spotipy's token cache. Then run `venv/bin/python main.py` normally or let the
next scheduled run proceed. Keep `playlists.json`; it stores the existing playlist
IDs and does not need to be reset when signing in again.

If authorization reports `redirect_uri: Insecure`, replace `localhost` with
`127.0.0.1` in both `config.ini` and your app's Spotify Developer Dashboard
Redirect URIs. Use `http://127.0.0.1:8888/callback` in both places. Spotify allows
HTTP for explicit loopback IP addresses, but no longer accepts `localhost`.
Then restart the authorization command to get a URL with the updated redirect URI.
