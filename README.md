# Plex.organize

Plex.organize is a simple script that lets you log into your Plex account and organize your media playlists.
You can sort, upgrade, and analyze different media playlists, which, sadly, Plex itself won't be able to do.

Currently, Python 3.7+ is supported.

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
Successfully sorted playlist "Movies to watch".

[?] Do you want to organize another playlist? (Y/n): n
```

## Configuration options

To skip the initial login process every time you use the script you might want to take a note of your authentication
token after your first login and save it to the config.ini file which should be located in `~/.config/plexapi/`
(which can be overridden by setting the environment variable `PLEXAPI_CONFIG_PATH` with the file path you desire) or in
the same directory as this script. Instead of the token you could also save your username and password to the
`config.ini` file.

Instead of the token you could also save your username and password to the `config.ini` file.

```ini
[auth]
myplex_username = JohnDoe
myplex_password = MyR4nd0mPassword
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

You can also influence the script on how to upgrade your playlists by setting the appropriate options to `1`.

`force_lossless=1` would force the script to upgrade everything to lossless files. `force_all=1` would force the script to upgrade everything, even if an item would already be lossless in your playlist. This is useful if you want to upgrade to Hi-Ress audio files with even higher bitrate.

```ini
[upgrade]
force_all=
force_lossless=
```
