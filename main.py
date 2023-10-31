import json
import os
from configparser import ConfigParser

import requests
import spotipy
from spotipy.oauth2 import SpotifyOAuth

config = ConfigParser()
config.read('config.ini')

spotify_client_id = config.get('spotify', 'client_id')
spotify_client_secret = config.get('spotify', 'client_secret')
spotify_redirect_uri = config.get('spotify', 'redirect_uri')
ntfy_endpoint = config.get('ntfy', 'url')
ntfy_auth = config.get('ntfy', 'auth')

spotify = spotipy.Spotify(client_credentials_manager=SpotifyOAuth(
    scope='user-library-read playlist-modify-public',
    client_id=spotify_client_id,
    client_secret=spotify_client_secret,
    redirect_uri=spotify_redirect_uri)
)

# Create playlists json file if it does not exist.
if 'playlists.json' not in os.listdir():
    print("hits")
    f = open('playlists.json', 'w')
    f.write(json.dumps({'first_run': 'yes'}))
    f.close()

# Month map
month_map = {'01': 'January',
             '02': 'February',
             '03': 'March',
             '04': 'April',
             '05': 'May',
             '06': 'June',
             '07': 'July',
             '08': 'August',
             '09': 'September',
             '10': 'October',
             '11': 'November',
             '12': 'December'}


def json_pretty_print(data):
    print(json.dumps(data, indent=4, sort_keys=True))


def get_liked_songs():
    print('Fetching all your liked songs.')
    liked_songs = spotify.current_user_saved_tracks()
    items = liked_songs['items']

    while liked_songs['next']:
        liked_songs = spotify.next(liked_songs)
        items.extend(liked_songs['items'])

    print(f"Fetched {len(items)} songs.")
    print('Grouping tracks by year and month.')
    return items


def group_tracks_by_month():
    tracks_by_month = {}
    for x in get_liked_songs():
        added_at = x['added_at']
        track_id = x['track']['id']

        year = added_at[0:4]
        month = added_at[5:7]

        key = f"{year}-{month}"

        if key not in tracks_by_month:
            tracks_by_month[key] = []

        tracks_by_month[key].append(track_id)

    return tracks_by_month


def create_playlist(me, title, description=None, public=True):
    created_playlist = spotify.user_playlist_create(
        me['id'],
        title,
        public=public,
        collaborative=False,
        description=description
    )

    return created_playlist['id']


def add_tracks_to_playlist(playlist_id, tracks):
    data = spotify.playlist_items(playlist_id)
    existing_tracks = [x['track']['id'] for x in data['items']]

    new_tracks = [x for x in tracks if x not in set(existing_tracks)]

    old_tracks = [x for x in existing_tracks if x not in tracks]

    print(f"Deleting {len(old_tracks)} tracks\n")
    for x in old_tracks:
        spotify.playlist_remove_all_occurrences_of_items(playlist_id, [x])

    print(f"Adding {len(new_tracks)} tracks\n")
    for x in new_tracks:
        if not existing_tracks:
            spotify.playlist_add_items(playlist_id, [x])
        else:
            spotify.playlist_add_items(playlist_id, [x], position=0)

    return len(new_tracks)


def check_if_playlist_already_create(year_month):
    with open('playlists.json', 'r') as f:
        data = json.loads(f.read())

        if year_month in data:
            return data[year_month]

        return False


def save_month_playlist_id(year_month, playlist_id):
    file_json = json.load(open('playlists.json', 'r'))
    file_json[year_month] = playlist_id
    with open('playlists.json', 'w') as f:
        f.write(json.dumps(file_json))


def create_or_update_playlist(year_month, month_playlist_id, me, title, tracks, description):
    if not month_playlist_id:
        month_playlist_id = create_playlist(
            me,
            title,
            description=description
        )

        save_month_playlist_id(year_month, month_playlist_id)

    new_tracks_count = add_tracks_to_playlist(month_playlist_id, tracks)

    if new_tracks_count > 0:
        requests.post(ntfy_endpoint,
                      data=f"Added {new_tracks_count} songs to {title}",
                      headers={
                          "Title": f"Playlist updated for {title}",
                          "Tags": "tada",
                          "Authorization": ntfy_auth
                      })


def main():
    tracks_by_month = group_tracks_by_month()
    me = spotify.me()
    for x in tracks_by_month.__reversed__():
        month_playlist_id = check_if_playlist_already_create(x)

        year, month = x.split('-')
        month = month_map[month]
        title = f"{month} '{year[2:]}"

        print(f"Creating {title}")
        create_or_update_playlist(
            x,
            month_playlist_id,
            me,
            title,
            tracks_by_month[x],
            description=f"Songs liked from {month}, {year}"
        )


if __name__ == '__main__':
    main()
