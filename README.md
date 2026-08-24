# Plex.organize

Plex.organize is a simple script that lets you log into your Plex account and organize your media playlists.
You can sort, upgrade, export, and analyze different media playlists, which, sadly, Plex itself won't be able to do.

Currently, Python 3.10+ is supported.

Smart playlists are read-only in Plex and are therefore not listed.

## Quickstart

1. Make sure [pip](https://pip.pypa.io/en/stable/installation/) is installed on your machine.

2. Create a virtual environment and activate it (optional), e.g.:

```bash
pip install virtualenv
python3 -m venv venv
source venv/bin/activate
```

3. Install the packages from the `requirements.txt` file using pip:

```bash
pip install -r requirements.txt
```

4. Execute the script and follow the guidance

```bash
./plex_organize.py
```

## Example usage

```bash
(venv) ➜ Plex.organize ./plex_organize.py

[?] Select resource to connect to:
 > PlexServerHome
   NAS1337
   Another Storage Resource
   ❌ Abort

[?] What do you want to organize?:
 > Sort playlists (audio & video)
   Upgrade playlists (audio only)
   Find all music albums with low bitrate (audio only)
   Export playlist as M3U (audio & video)
   Export playlist to Music Assistant (audio only)
   ❌ Abort

[?] Select a playlist to sort:
   Favorite music
 > Movies to watch
   Random hits
   X-mas songs
   ❌ Abort

[?] Select the sorting key for this video playlist:
 > Title
   Sorting title
   Release year
   Duration
   Shuffle randomly
   ❌ Abort

[?] Select the sorting direction for Title:
 > Sort ascending
   Sort descending
   ❌ Abort

[?] Do you want to create a duplicated playlist instead of modifying the selected one? (y/N): n

Sorting playlist in progress. This may take a while depending on the size of your playlist. Please be patient.
Preparing playlist items...
Sorting playlist "Movies to watch"...
Sorting playlist: [########################################] 100.0% (42/42) elapsed 00:18
Successfully sorted playlist "Movies to watch".

[?] Do you want to organize another playlist? (Y/n): n
```

## Features

### Sort playlists (audio & video)

Sorts the selected playlist in Plex. You can either change the original playlist or create `Copy of <name>`.

Audio playlists can be sorted by title, sorting title, artist, album artist, album, or duration. Video playlists can be
sorted by title, sorting title, release year, originally available date, or duration. Both types also offer a random
shuffle. Titles are normalized for sorting (articles like "the"/"die" are ignored).

### Upgrade playlists (audio only)

Replaces tracks in a music playlist with a better copy of the same track from your Plex library, when one exists.

By default a track is considered too low quality if it is MP3 below 320 kbps or AAC below 256 kbps. You can ask for a
dry run first. Simple replacement mode picks the best available version automatically; otherwise you choose. You can
also write the result to a duplicated playlist instead of changing the original.

See [Upgrade options](#upgrade-options) for `force_lossless` and `force_all`.

### Find all music albums with low bitrate (audio only)

Scans a music library section and lists albums that contain at least one track below the quality rules above. You can
optionally save that list to a timestamped text file in the current directory.

### Export playlist as M3U (audio & video)

Writes the selected playlist to a local `.m3u` file. Items without a local media file path are skipped. See
[M3U export](#m3u-export) for `output_directory` and `relative_path_base`.

### Export playlist to Music Assistant (audio only)

Copies a Plex audio playlist into [Music Assistant](https://www.music-assistant.io/) as a library playlist.

Each Plex item is matched by **exact file path**, not by artist or title. That matters when the same song exists on an
album and on compilations: only the file Plex actually points at is added. The Plex/NAS path is stripped of
`relative_path_base` and looked up in Music Assistant as a filesystem track, for example:

`/volume1/music/a-ha/Lifelines (Deluxe Edition)/01-03 Forever Not Yours.flac`  
→ `filesystem_local://track/a-ha/Lifelines (Deluxe Edition)/01-03 Forever Not Yours.flac`

If that file is not in the Music Assistant library, the track is skipped and counted at the end. There is no fallback to
another album or a different codec/extension.

If a Music Assistant playlist with the same name already exists, you can **replace** it (the existing playlist is
deleted and recreated) or keep it and create a new playlist with a timestamp appended, e.g.
`Masterpieces 2026-08-21 18-55`.

Required config: `music_assistant.baseurl`, `music_assistant.token`, and `export.relative_path_base`. Create a
long-lived access token in Music Assistant under `SETTINGS >> PROFILE`. `relative_path_base` must be the Plex/NAS
library root that matches the Music Assistant filesystem library.

## Configuration options

The script reads `config.ini` from the same directory as `plex_organize.py`, or from `PLEXAPI_CONFIG_PATH` /
`~/.config/plexapi/` if no local file exists.

### Authentication

To skip the login prompt, save your Plex token (or username and password) in `config.ini`.

```ini
[auth]
myplex_username = JohnDoe
myplex_password = MyR4nd0mPassword
server_token = AjsUeO6Bk89BQPdu5Dnj
```

If the machine running this script can access your Plex server directly on the local network, you can bypass Plex.tv
resource discovery by configuring the local server URL together with your token:

```ini
[auth]
server_baseurl = http://192.168.x.x:32400
server_token = AjsUeO6Bk89BQPdu5Dnj
```

**Important note for 2FA accounts**  
If you have activated two-factor authentication, after you have already logged in once you can either log in again with
your previously generated token or add your 6-digit number from the authenticator app at the end of your password, e.g.

Authenticator app shows: 123456  
Username: JohnDoe  
Password (will not be echoed): MyR4nd0mPassword123456

Or use the `config.ini` file with your previously generated token:

```ini
[auth]
server_token = AjsUeO6Bk89BQPdu5Dnj
```

### Upgrade options

Set the following options to `1` to change how tracks are judged during upgrade and the low-bitrate album search.

`force_lossless=1` requires lossless files (ALAC or FLAC). `force_all=1` treats every track as needing an upgrade, even
if it is already lossless. That is useful when you want to move to higher-resolution files.

```ini
[upgrade]
force_all=
force_lossless=
```

### M3U export

`output_directory` is where `.m3u` files are written (the current directory if empty). By default, media file paths are
exported as absolute paths. To export paths relative to a music library directory, set `relative_path_base`. Paths
outside that base are still written as absolute paths, with a warning.

```ini
[export]
output_directory = ~/Music/Playlists
relative_path_base = /volume1/music
```

With `relative_path_base = /volume1/music`, an item path like
`/volume1/music/a-ha/Lifelines (Deluxe Edition)/01-03 Forever Not Yours.flac` is written as
`a-ha/Lifelines (Deluxe Edition)/01-03 Forever Not Yours.flac`.

### Music Assistant export

```ini
[export]
relative_path_base = /volume1/music

[music_assistant]
baseurl = http://192.168.x.x:8095
token = your_music_assistant_token
```

`relative_path_base` is shared with M3U export: it is the Plex/NAS root of the same files Music Assistant indexes.
`baseurl` is the Music Assistant server (typically port 8095). `token` is a long-lived access token from
`SETTINGS >> PROFILE`.
