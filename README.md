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

### Docker

Install Docker Engine with the Compose plugin. The container runs the playlist
job once, then exits. It uses a Python 3.12 Alpine image named
`athphane/spotify-playlist-generator:local`, built locally from this checkout.

Keep your existing `config.ini`, or copy `config.ini.sample` to `config.ini` and
fill in your Spotify credentials and notification settings. Then run:

```sh
./scripts/prepare-data.sh
./scripts/rebuild-image.sh
```

The preparation script creates `data/` and copies your existing `.cache` and
`playlists.json` into it if those files are present. It never overwrites existing
container state, so your current sign-in and playlist IDs are preserved.

Run the job:

```sh
docker compose up --no-color --exit-code-from playlist playlist
```

Compose builds the image if it is missing and starts a new run even if the
previous container has exited. After changing application code or dependencies,
run `./scripts/rebuild-image.sh` before the next job.

If you need to sign in for the first time or authorize again:

```sh
docker compose run --rm playlist --reauthorize
```

Open the printed URL in your browser and paste the full redirect URL back into
the terminal. This only saves authorization; it does not update playlists. No
container port needs to be published for this flow.

`config.ini` is mounted read-only. Tokens and playlist IDs are saved under
`data/` on the host and survive container removal and image rebuilds. Once you
switch to Docker, use the Docker authorization command so it updates `data/.cache`.
The original root-level state files remain as migration copies. Back up `data/`
along with your config. Credentials and state are excluded from the image and Git.

The container runs as UID/GID 1000 by default. If your host user has different
IDs, set `PUID` and `PGID` in a local `.env` file to the values printed by `id -u`
and `id -g`. The host user running the scripts needs Docker access and write
access to this checkout and `data/`.

### Cron

`cron.sh` runs the configured Compose job from any working directory, prevents
overlapping scheduled runs, and logs output to `playlist.log` in this checkout.
It rotates logs while writing: 10 MiB per file, with three backups, for at most
40 MiB of retained output. A failed container returns a nonzero exit status.
Scheduled runs requiring Spotify authorization exit instead of waiting for input.

To run it manually with the same logging and locking:

```sh
./cron.sh
```

If your crontab already calls `cron.sh`, it will now use Docker without changing
the schedule. This checkout already has an hourly entry.

For a new installation, add this with `crontab -e` to run at the start of every
hour:

```cron
0 * * * * /home/athphane/python/spotify-playlist-generator/cron.sh
```

Use `0 3 * * *` instead for daily runs at 03:00 in the host's timezone
(UTC on this machine). Adjust the path if you move the checkout.
The cron host needs Bash, `flock`,
and Docker Compose; it does not need a Python virtual environment or a cron
daemon inside the container. The cron entry is not installed automatically.

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
