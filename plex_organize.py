#!/usr/bin/env python

"""Plex.organize is a simple script that lets you log into your Plex account and organize your media playlists.
You can sort, upgrade, and analyze different media playlists, which, sadly, Plex itself won't be able to do.

URL: https://github.com/mikelandzelo173/Plex.organize
Python Version: 3.7+

Disclaimer:
I'm not responsible for any data loss which might occur. There may also be bugs or unexpected behaviors.
Always use with common sense.

What does it do:
You will be prompted to log into your Plex account. After that you can select a playlist that you want to organize.
You can then select which action you want to perform, including sorting, upgrading or analyzing your playlists.
Plex lacks this feature, so I made this script. It comes in handy if you e.g. want to find duplicates in a gigantic
music playlist, just want to have everything sorted alphabetically, or want to find music albums with low bitrate.

Before use:
You will be guided through the whole process but to skip the initial login process every time you use the script you
might want to take a note of your authentication token and save it to the config.ini file which should be located in
~/.config/plexapi/ (which can be overridden by setting the environment variable PLEXAPI_CONFIG_PATH with the file path
you desire) or in the same directory as this script. You could also save your username and password to the config.ini
file instead.

In step 2 you will have to select a resource which is connected to your Plex account. You can only select Plex Media
Servers that host playlists. If there is only one Plex Media Server available, this step will be skipped.

After that, you must select a playlist to organize. Please note that smart playlists must not be altered and therefore
are not listed. You can also determine if you want to edit the selected playlist or create a new and organized one
based on the playlist you just selected.

For more information on the Python PlexAPI visit:
https://python-plexapi.readthedocs.io/en/latest/index.html

This project was inspired by Plex Playlist Sorter by uswemar:
https://github.com/uswemar/PlexPlaylistSorter
"""

import datetime
import json
import os
import random
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import inquirer
from plexapi import PlexConfig
from plexapi.audio import Audio
from plexapi.exceptions import Unauthorized
from plexapi.library import MovieSection, MusicSection, PhotoSection, ShowSection
from plexapi.myplex import MyPlexAccount, MyPlexResource
from plexapi.playlist import Playlist
from plexapi.server import PlexServer
from unidecode import unidecode

__author__ = "Michael Pölzl"
__copyright__ = "Copyright 2022-2025, Michael Pölzl"
__credits__ = ""
__license__ = "GPL"
__version__ = "1.0.1"
__maintainer__ = "Michael Pölzl"
__email__ = "michael.poelzl@proton.me"
__status__ = "Production"


def clear():
    """
    Function: clear()

    Clears the shell depending on the operating system.
    """

    try:
        os.system("clear")
    except Exception:
        os.system("cls")


def duration_to_str(duration: int) -> str:
    """
    Function: duration_to_str()

    Converts a duration value in milliseconds to a usual string representation for audio length.

    :param duration: Duration in milliseconds
    :type duration: int
    :returns: String representation of duration
    :rtype: str
    """

    seconds, milliseconds = divmod(duration, 1000)
    minutes, seconds = divmod(seconds, 60)
    return f"{minutes:02d}:{seconds:02d}"


def format_elapsed_time(start_time: datetime.datetime) -> str:
    """
    Function: format_elapsed_time()

    Converts an elapsed time to a readable string representation.

    :param start_time: Datetime when the operation started
    :type start_time: datetime.datetime
    :returns: String representation of elapsed time
    :rtype: str
    """

    elapsed_seconds = int((datetime.datetime.now() - start_time).total_seconds())
    minutes, seconds = divmod(elapsed_seconds, 60)
    hours, minutes = divmod(minutes, 60)

    if hours:
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

    return f"{minutes:02d}:{seconds:02d}"


def print_progress_bar(
    current: int,
    total: int,
    label: str,
    start_time: datetime.datetime,
    width: int = 40,
) -> None:
    """
    Function: print_progress_bar()

    Prints a terminal progress bar on a single updating line.

    :param current: Current number of processed items
    :type current: int
    :param total: Total number of items to process
    :type total: int
    :param label: Label to display before the progress bar
    :type label: str
    :param start_time: Datetime when the operation started
    :type start_time: datetime.datetime
    :param width: Width of the progress bar
    :type width: int
    """

    progress = current / total if total else 1
    filled_width = int(width * progress)
    bar = "#" * filled_width + "-" * (width - filled_width)

    sys.stdout.write(
        f"\r{label}: [{bar}] {progress * 100:5.1f}% ({current}/{total}) elapsed {format_elapsed_time(start_time)}",
    )
    sys.stdout.flush()


def artist(item: Audio) -> str:
    """
    Function: artist()

    Extracts the artist from an Audio object and returns the value as a human readable string representation.
    If no artist is found the album artist will be used instead.

    :param item: Audio object representing a track
    :type item: Audio
    :returns: String representation of the track artist
    :rtype: str
    """

    return item.originalTitle or item.grandparentTitle


def audio_to_str(item: Audio) -> str:
    """
    Function: audio_to_str()

    Converts an Audio object to a human readable string representation.

    :param item: Audio object representing a track
    :type item: Audio
    :returns: String representation of an Audio object
    :rtype: str
    """

    return (
        f"{artist(item)} - {item.title} ({item.album().title}) "
        f"[{duration_to_str(item.media[0].duration)}][{item.media[0].audioCodec}][{item.media[0].bitrate}]"
    )


def item_duration_seconds(item: any) -> int:
    """
    Function: item_duration_seconds()

    Returns the duration of an item in seconds.

    :param item: Playlist item
    :type item: any
    :returns: Duration in seconds
    :rtype: int
    """

    duration = getattr(item, "duration", 0) or 0
    return int(duration / 1000)


def item_to_m3u_title(item: any, playlist_type: str) -> str:
    """
    Function: item_to_m3u_title()

    Returns a human-readable title for an M3U entry.

    :param item: Playlist item
    :type item: any
    :param playlist_type: Playlist type
    :type playlist_type: str
    :returns: String representation of the item title
    :rtype: str
    """

    if playlist_type == "audio":
        item_artist = getattr(item, "originalTitle", None) or getattr(item, "grandparentTitle", None)
        if item_artist:
            return f"{item_artist} - {item.title}"

    return item.title


def item_to_paths(item: any) -> list[str]:
    """
    Function: item_to_paths()

    Extracts all local file paths from a playlist item.

    :param item: Playlist item
    :type item: any
    :returns: A list of local file paths
    :rtype: list[str]
    """

    paths = []
    for media in getattr(item, "media", []):
        for part in getattr(media, "parts", []):
            if getattr(part, "file", None):
                paths.append(part.file)
    return paths


def export_path_to_m3u_path(item_path: str, relative_path_base: str | None = None) -> str:
    """
    Function: export_path_to_m3u_path()

    Converts an item path to a relative M3U path when a relative base path is configured.

    :param item_path: Local media file path
    :type item_path: str
    :param relative_path_base: Base path to remove from item paths
    :type relative_path_base: str|None
    :returns: Absolute or relative M3U path
    :rtype: str
    """

    if not relative_path_base:
        return item_path

    item_path_object = Path(item_path).expanduser().resolve(strict=False)
    relative_path_base_object = Path(relative_path_base).expanduser().resolve(strict=False)

    try:
        return item_path_object.relative_to(relative_path_base_object).as_posix()
    except ValueError:
        return item_path


def export_path_to_music_assistant_uri(
    item_path: str,
    relative_path_base: str,
    provider_instance: str,
) -> str | None:
    """
    Function: export_path_to_music_assistant_uri()

    Converts a Plex media file path to a Music Assistant filesystem track URI.

    :param item_path: Local media file path as reported by Plex
    :type item_path: str
    :param relative_path_base: Plex/NAS library root to strip from item paths
    :type relative_path_base: str
    :param provider_instance: Music Assistant filesystem provider instance id
    :type provider_instance: str
    :returns: Music Assistant track URI, or None if the item is outside the relative path base
    :rtype: str|None
    """

    relative_item_path = export_path_to_m3u_path(item_path, relative_path_base)
    if relative_item_path == item_path:
        return None

    return f"{provider_instance}://track/{relative_item_path}"


def get_music_assistant_filesystem_provider(baseurl: str, token: str) -> str:
    """
    Function: get_music_assistant_filesystem_provider()

    Returns a filesystem provider instance id from the Music Assistant library.

    :param baseurl: Music Assistant server URL
    :type baseurl: str
    :param token: Music Assistant bearer token
    :type token: str
    :returns: Filesystem provider instance id
    :rtype: str
    """

    tracks = music_assistant_request(
        baseurl,
        token,
        "music/tracks/library_items",
        {"limit": 50},
    )
    if not isinstance(tracks, list):
        print("ERROR: Music Assistant returned an unexpected track list.")
        sys.exit(1)

    for track in tracks:
        if not isinstance(track, dict):
            continue
        for mapping in track.get("provider_mappings") or []:
            if not isinstance(mapping, dict):
                continue
            domain = mapping.get("provider_domain") or ""
            instance = mapping.get("provider_instance") or ""
            if domain.startswith("filesystem") and instance:
                return instance

    print("ERROR: Could not find a filesystem music provider in the Music Assistant library.")
    sys.exit(1)


def music_assistant_request(
    baseurl: str,
    token: str,
    command: str,
    args: dict | None = None,
    fail_loud: bool = True,
) -> any:
    """
    Function: music_assistant_request()

    Sends a command to the Music Assistant HTTP API and returns the result.

    :param baseurl: Music Assistant server URL
    :type baseurl: str
    :param token: Music Assistant bearer token
    :type token: str
    :param command: API command name
    :type command: str
    :param args: Command arguments
    :type args: dict|None
    :param fail_loud: Exit the script when the API call fails
    :type fail_loud: bool
    :returns: API result payload
    :rtype: any
    """

    url = f"{baseurl.rstrip('/')}/api"
    payload = {
        "message_id": command,
        "command": command,
        "args": args or {},
    }
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Accept": "application/json",
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=300) as response:
            body = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        error_body = error.read().decode("utf-8", errors="replace")
        if not fail_loud:
            return None
        print(f'ERROR: Music Assistant API returned HTTP {error.code} for command "{command}".')
        print(error_body)
        sys.exit(1)
    except urllib.error.URLError as error:
        if not fail_loud:
            return None
        print(f'ERROR: Could not connect to Music Assistant at "{url}".')
        print(error)
        sys.exit(1)
    except json.JSONDecodeError as error:
        if not fail_loud:
            return None
        print(f'ERROR: Music Assistant API returned invalid JSON for command "{command}".')
        print(error)
        sys.exit(1)

    if isinstance(body, dict) and "message_id" in body:
        if body.get("error"):
            if not fail_loud:
                return None
            print(f'ERROR: Music Assistant command "{command}" failed.')
            print(body["error"])
            sys.exit(1)
        return body.get("result")

    # HTTP /api returns the command result directly, e.g. a list of playlists.
    return body


def music_assistant_library_uri(baseurl: str, token: str, uri: str) -> str | None:
    """
    Function: music_assistant_library_uri()

    Resolves a Music Assistant URI to a library track URI.

    :param baseurl: Music Assistant server URL
    :type baseurl: str
    :param token: Music Assistant bearer token
    :type token: str
    :param uri: Track URI to resolve
    :type uri: str
    :returns: Library URI, or None if the track is not in the library
    :rtype: str|None
    """

    item = music_assistant_request(
        baseurl,
        token,
        "music/item_by_uri",
        {"uri": uri},
        fail_loud=False,
    )
    if not isinstance(item, dict):
        return None
    return item.get("uri")


def music_assistant_track_uris(track: dict) -> set[str]:
    """
    Function: music_assistant_track_uris()

    Collects identity URIs from a Music Assistant track payload.

    :param track: Track object returned by the Music Assistant API
    :type track: dict
    :returns: URIs that can identify the track
    :rtype: set[str]
    """

    uris = set()
    if not isinstance(track, dict):
        return uris

    uri = track.get("uri")
    if uri:
        uris.add(uri)

    item_id = track.get("item_id")
    provider = track.get("provider")
    if item_id and provider:
        uris.add(f"{provider}://track/{item_id}")

    for mapping in track.get("provider_mappings") or []:
        if not isinstance(mapping, dict):
            continue
        mapping_uri = mapping.get("uri")
        if mapping_uri:
            uris.add(mapping_uri)
        mapping_instance = mapping.get("provider_instance")
        mapping_item_id = mapping.get("item_id")
        if mapping_instance and mapping_item_id:
            uris.add(f"{mapping_instance}://track/{mapping_item_id}")

    return uris


def music_assistant_duplicate_library_uri_groups(resolved_tracks: list[dict]) -> list[list[dict]]:
    """
    Function: music_assistant_duplicate_library_uri_groups()

    Groups resolved export records that share the same Music Assistant library URI.

    :param resolved_tracks: Export records with a library_uri
    :type resolved_tracks: list[dict]
    :returns: Groups that contain more than one record
    :rtype: list[list[dict]]
    """

    groups = {}
    for track in resolved_tracks:
        library_uri = track["library_uri"]
        groups.setdefault(library_uri, []).append(track)

    return [group for group in groups.values() if len(group) > 1]


def unmatched_music_assistant_export_tracks(resolved_tracks: list[dict], playlist_tracks: list) -> list[dict]:
    """
    Function: unmatched_music_assistant_export_tracks()

    Returns export records that have no remaining match in a Music Assistant playlist.

    :param resolved_tracks: Export records that were sent to Music Assistant
    :type resolved_tracks: list[dict]
    :param playlist_tracks: Tracks currently in the Music Assistant playlist
    :type playlist_tracks: list
    :returns: Export records that are missing from the playlist
    :rtype: list[dict]
    """

    remaining = []
    for track in playlist_tracks or []:
        if isinstance(track, dict):
            remaining.append(music_assistant_track_uris(track))

    unmatched = []
    for record in resolved_tracks:
        match_index = None
        candidates = {record["library_uri"], record["filesystem_uri"]}
        for index, uris in enumerate(remaining):
            if candidates & uris:
                match_index = index
                break
        if match_index is None:
            unmatched.append(record)
        else:
            remaining.pop(match_index)

    return unmatched


def wait_for_music_assistant_playlist_tracks(
    baseurl: str,
    token: str,
    playlist_id: str | int,
    expected_count: int,
    timeout_seconds: int = 300,
) -> tuple[int, list]:
    """
    Function: wait_for_music_assistant_playlist_tracks()

    Waits until a Music Assistant playlist contains the expected number of tracks.

    :param baseurl: Music Assistant server URL
    :type baseurl: str
    :param token: Music Assistant bearer token
    :type token: str
    :param playlist_id: Library playlist id
    :type playlist_id: str|int
    :param expected_count: Number of tracks that should be present
    :type expected_count: int
    :param timeout_seconds: Maximum time to wait
    :type timeout_seconds: int
    :returns: Number of tracks found and the last fetched track list
    :rtype: tuple[int, list]
    """

    deadline = time.time() + timeout_seconds
    tracks = []
    track_count = 0

    while time.time() <= deadline:
        playlist_tracks = music_assistant_request(
            baseurl,
            token,
            "music/playlists/playlist_tracks",
            {"item_id": str(playlist_id), "provider_instance_id_or_domain": "library"},
        )
        tracks = playlist_tracks if isinstance(playlist_tracks, list) else []
        track_count = len(tracks)
        if track_count >= expected_count:
            return track_count, tracks
        time.sleep(1)

    return track_count, tracks


def object_to_string(item: any, attr: str) -> str:
    """
    Function: object_to_string()

    Converts an object or dict to a string representation.

    :param item: The item to convert, which may be of type object or dict
    :type item: list
    :param attr: The attribute to use for string representation
    :type attr: str
    :returns: A string representation
    :rtype: bool
    """

    return (
        attr(item)
        if callable(attr)
        else (item if isinstance(item, str) else (item.get(attr) if isinstance(item, dict) else getattr(item, attr)))
    )


def sortable_term(term: str | int | float | datetime.date | None) -> tuple[int, str | int | float]:
    """
    Function: sortable_term()

    Transforms the provided term to a sortable value. Text values have articles removed
    and are normalized; numeric and date values keep their natural ordering.

    :param term: Term to sort by
    :type term: str|int|float|datetime.date|None
    :returns: Manipulated value to be used for sorting
    :rtype: tuple
    """
    if term is None:
        return (0, "")

    if isinstance(term, (int, float)):
        return (1, term)

    if isinstance(term, datetime.date):
        return (2, term.isoformat())

    term = unidecode(str(term).lower())

    articles = [
        # German
        "die",
        "der",
        "das",
        "ein",
        "eine",
        # English
        "the",
        "a",
        "an",
        # Spanish
        "el",
        "la",
        "los",
        "las",
        "un",
        "una",
        "unos",
        "unas",
        # French
        "le",
        "la",
        "les",
        "un",
        "une",
        "des",
        # Italian
        "il",
        "lo",
        "la",
        "i",
        "gli",
        "un",
        "una",
        "uno",
    ]

    words = term.split(" ")

    if len(words) > 1 and words[0] in articles:
        words.pop(0)
        term = " ".join(words)

    term = term.replace("&", "and")
    term = re.sub(r"[*.:,;…'\"/\\!?$()=+#<>|‘“¡¿´`]", "", term)

    return (3, term.strip())


def check_quality_requirements(item: Audio) -> bool:
    """
    Function: check_quality_requirements()

    Checks if the quality requirements of a track have been met.

    :param item: Audio object representing the track to check
    :type item: Audio
    :returns: A boolean
    :rtype: bool
    """

    if bool(config.get("upgrade.force_all")):
        return False

    if bool(config.get("upgrade.force_lossless")):
        return item.media[0].audioCodec in [
            "alac",
            "flac",
        ]

    return not (
        item.media[0].audioCodec == "mp3"
        and item.media[0].bitrate < 320
        or item.media[0].audioCodec == "aac"
        and item.media[0].bitrate < 256
    )


def confirm_question(message: str, default: bool = True) -> bool:
    """
    Function: confirm_question()

    Prompts a simple question with 'Yes' and 'No' choices.

    :param message: The question to prompt
    :type message: str
    :param default: Whether 'Yes' or 'No' should be set as the default choice
    :type default: bool
    :returns: A boolean
    :rtype: bool
    """

    questions = [
        inquirer.Confirm(
            "confirm",
            message=message or "Do you want to do proceed?",
            default=default,
        ),
    ]

    answers = inquirer.prompt(questions)

    return answers["confirm"]


def question(
    message: str,
    items: list,
    attr: str | None = None,
    none_choice: bool = False,
    automatic_single_coice_return: bool = False,
) -> any:
    """
    Function: question()

    Prompts a question with choices.

    :param message: The question to prompt
    :type message: str
    :param items: The choices to offer as an answer
    :type items: list
    :param attr: The attribute to use for string representation of an item if it is of type object or dict
    :type attr: str
    :returns: The selected item of the same type which has been passed in items
    :type none_choice: bool
    :returns: Whether the answers should include a "None" option by default
    :type automatic_single_coice_return: bool
    :returns: Whether the function should automatically return the only available option by default
    :rtype: any
    """

    # Return the first item if there is only one choice
    if len(items) == 1 and automatic_single_coice_return:
        return items[0]

    clear()

    choices = []

    if none_choice:
        choices.insert(0, "None")

    if items is not None:
        for item in items:
            choices.append(object_to_string(item, attr))

    choices.append("❌ Abort")

    questions = [
        inquirer.List(
            "question",
            message=message or "What do you want to do?",
            choices=choices,
        ),
    ]

    answers = inquirer.prompt(questions)
    answer = answers["question"]

    if answer == "❌ Abort":
        sys.exit()

    return next((item for item in items if object_to_string(item, attr) == answers["question"]), None)


def choose_sorting_method(playlist: Playlist) -> tuple:
    """
    Function: choose_sorting_method()

    Decide on how to sort the selected playlist.

    :returns: A tuple with the key, backup key and direction to sort. The backup key can be used if the
              main key may be of type NoneType.
    :rtype: tuple
    """

    playlist_type = playlist.playlistType

    choices = [
        {
            "name": "Title",
            "key": "title",
            "secondary_key": "originalTitle",
            "secondary_backup_key": "grandparentTitle",
        },
        {
            "name": "Sorting title",
            "key": "titleSort",
            "secondary_key": "originalTitle",
            "secondary_backup_key": "grandparentTitle",
        },
    ]

    if playlist_type == "audio":
        choices.extend(
            [
                {
                    "name": "Artist name",
                    "key": "originalTitle",
                    "backup_key": "grandparentTitle",
                    "secondary_key": "title",
                },
                {
                    "name": "Album artist name",
                    "key": "grandparentTitle",
                    "secondary_key": "title",
                },
                {
                    "name": "Album name",
                    "key": "parentTitle",
                    "secondary_key": "originalTitle",
                    "secondary_backup_key": "grandparentTitle",
                },
            ],
        )
    elif playlist_type == "video":
        choices.extend(
            [
                {
                    "name": "Release year",
                    "key": "year",
                    "secondary_key": "title",
                },
                {
                    "name": "Originally available at",
                    "key": "originallyAvailableAt",
                    "secondary_key": "title",
                },
            ],
        )

    choices.extend(
        [
            {
                "name": "Duration",
                "key": "duration",
                "secondary_key": "title",
            },
            {
                "name": "Shuffle randomly",
                "key": "shuffle",
            },
        ],
    )

    clear()

    selected_choice = question(
        message=f"Select the sorting key for this {playlist_type} playlist",
        items=choices,
        attr="name",
        automatic_single_coice_return=False,
    )

    if selected_choice["key"] == "shuffle":
        return selected_choice["key"], selected_choice["key"], selected_choice["key"], selected_choice["key"], False

    sorting_choices = [
        {
            "name": "Sort ascending",
            "reverse": False,
        },
        {
            "name": "Sort descending",
            "reverse": True,
        },
    ]

    clear()

    selected_sorting_choice = question(
        message=f"Select the sorting direction for {selected_choice['name']}",
        items=sorting_choices,
        attr="name",
        automatic_single_coice_return=False,
    )

    return (
        selected_choice["key"],
        selected_choice.get("backup_key", selected_choice["key"]),
        selected_choice.get("secondary_key", selected_choice["key"]),
        selected_choice.get("secondary_backup_key", selected_choice["key"]),
        selected_sorting_choice["reverse"],
    )


def get_account(config: PlexConfig) -> MyPlexAccount:
    """
    Function: get_account()

    Handles the Plex login process and returns a MyPlexAccount object.
    Login is handled via input prompt of username and password or by reading the config.ini file and extracting
    username and password or authentication token from there.

    :param config: PlexConfig object
    :type config: PlexConfig
    :returns: A MyPlexAccount object
    :rtype: MyPlexAccount
    """

    clear()

    if config.get("auth.server_token"):
        try:
            return MyPlexAccount(token=config.get("auth.server_token"))
        except Exception:
            print("ERROR: Invalid token.")
            print()

    if config.get("auth.myplex_username") and config.get("auth.myplex_password"):
        try:
            account = MyPlexAccount(config.get("auth.myplex_username"), config.get("auth.myplex_password"))

            print()
            print(
                "This is your authentication token that you can save in your configuration file to avoid "
                "having to log in every time:",
            )
            print(account.authenticationToken)
            print()

            if not confirm_question("Do you want to do proceed?"):
                sys.exit()

            return account
        except Unauthorized:
            clear()
            print("ERROR: Invalid email, username, or password. Please try again.")
            print()
        except Exception:
            clear()
            print("ERROR: Please try again.")
            print()

    while True:
        print("Please provide your login credentials for your Plex account.")

        questions = [
            inquirer.Text(
                "username",
                message="Username",
            ),
            inquirer.Password(
                "password",
                message="Password (will not be echoed)",
            ),
        ]

        try:
            answers = inquirer.prompt(questions)
        except KeyboardInterrupt:
            print()
            print("Login cancelled.")
            sys.exit(130)

        if not answers:
            print()
            print("Login cancelled.")
            sys.exit(130)

        try:
            account = MyPlexAccount(answers["username"], answers["password"])

            print()
            print(
                "This is your authentication token that you can save in your configuration file to avoid "
                "having to log in every time:",
            )
            print(account.authenticationToken)
            print()

            if not confirm_question("Do you want to do proceed?"):
                sys.exit()

            return account
        except Unauthorized:
            clear()
            print("ERROR: Invalid email, username, or password. Please try again.")
            print()
        except Exception as e:
            clear()
            print(e)
            print("ERROR: Please try again.")
            print()


def get_config() -> PlexConfig:
    """
    Function: get_config()

    Checks for a config file in either the same directory as this script or in the default configuration path set via
    PLEXAPI_CONFIG_PATH in your environment.

    :returns: A PlexConfig object
    :rtype: PlexConfig
    """

    script_path = os.path.abspath(os.path.dirname(__file__))
    local_config_file = os.path.join(script_path, "config.ini")
    if os.path.exists(local_config_file):
        return PlexConfig(os.path.expanduser(local_config_file))
    else:
        return PlexConfig(os.environ.get("PLEXAPI_CONFIG_PATH", os.path.expanduser("config.ini")))


def get_server(config: PlexConfig) -> PlexServer:
    """
    Function: get_server()

    Connects to a Plex server either directly via configured base URL and token, or through MyPlex discovery.

    :param config: PlexConfig object
    :type config: PlexConfig
    :returns: A PlexServer object
    :rtype: PlexServer
    """

    server_baseurl = (config.get("auth.server_baseurl") or "").strip()
    server_token = (config.get("auth.server_token") or "").strip()

    if server_baseurl:
        if not server_token:
            print("ERROR: auth.server_token must be set when auth.server_baseurl is configured.")
            sys.exit(1)

        try:
            return PlexServer(server_baseurl, server_token)
        except Unauthorized:
            print("ERROR: Invalid token for the configured Plex server.")
            sys.exit(1)
        except Exception as e:
            print(f'ERROR: Could not connect to Plex server at "{server_baseurl}".')
            print(e)
            sys.exit(1)

    # Login to the Plex account
    account = get_account(config)

    # Select a resource to connect to
    resources = get_resources(account)
    resource = question(
        message="Select a resource to connect to",
        items=resources,
        attr="name",
        automatic_single_coice_return=True,
    )

    # Connect to the selected resource and create a server object
    return account.resource(resource.name).connect()


def get_playlists(server: PlexServer, filter_type: list = None) -> list[Playlist]:
    """
    Function: get_playlists()

    Returns all playlists from a connected resource, filtered by smart status.

    :param server: PlexServer object
    :type server: PlexServer
    :returns: A list of Playlist objects
    :rtype: list[Playlist]
    """

    if not filter_type:
        filter_type = ["audio", "video"]

    return [playlist for playlist in server.playlists() if not playlist.smart and playlist.playlistType in filter_type]


def get_sections(
    server: PlexServer,
    section_type: str,
) -> list[MovieSection | ShowSection | MusicSection | PhotoSection]:
    """
    Function: get_sections()

    Returns all library sections from a connected resource.

    :param server: PlexServer object
    :type server: PlexServer
    :param section_type: Section type
    :type section_type: str
    :returns: A list of library section objects
    :rtype: list[MovieSection|ShowSection|MusicSection|PhotoSection]
    """

    sections = server.library.sections()

    if section_type:
        sections = [section for section in sections if section.type == section_type]

    return sections


def get_resources(account: MyPlexAccount) -> list[MyPlexResource]:
    """
    Function: get_resources()

    Returns all resources connected to a MyPlexAccount, filtered by type. Only "Plex Media Server" items are returned.

    :param account: MyPlexAccount object
    :type account: MyPlexAccount
    :returns: A list of MyPlexResource objects
    :rtype: list[MyPlexResource]
    """

    return [resource for resource in account.resources() if resource.product == "Plex Media Server"]


def playlist_item_order_key(item: any) -> str:
    """
    Function: playlist_item_order_key()

    Returns the most specific stable key available for comparing playlist item order.

    :param item: Playlist item
    :type item: any
    :returns: Comparable playlist item key
    :rtype: str
    """

    return str(getattr(item, "playlistItemID", None) or getattr(item, "ratingKey", None) or id(item))


def move_playlist_items_one_by_one(playlist: Playlist, items: list) -> Playlist:
    """
    Function: move_playlist_items_one_by_one()

    Sorts a playlist using Plex's single-item move endpoint.

    :param playlist: Playlist object
    :type playlist: Playlist
    :param items: Playlist items in the desired order
    :type items: list
    :returns: The modified Playlist object
    :rtype: Playlist
    """

    progress_started_at = datetime.datetime.now()
    print_progress_bar(0, len(items), "Sorting playlist", progress_started_at)
    previous_item = None
    for index, item in enumerate(items, start=1):
        playlist.moveItem(item, after=previous_item)
        previous_item = item
        print_progress_bar(index, len(items), "Sorting playlist", progress_started_at)
    print()

    return playlist


def sort_playlist(
    server: PlexServer,
    playlist: Playlist,
    sort_key: str = "title",
    backup_sort_key: str = "title",
    secondary_sort_key: str = "title",
    backup_secondary_sort_key: str = "title",
    sort_reverse: bool = False,
    duplicate: bool = False,
) -> Playlist:
    """
    Function: sort_playlist()

    Sorts tracks in a playlist by user-defined parameters.

    :param server: PlexServer object
    :type server: PlexServer
    :param playlist: Playlist object
    :type playlist: Playlistobject
    :param sort_key: The object key you want to sort the playlist by. Available choices depend on the
                     type of media the playlist contains.
    :type sort_key: str
    :param backup_sort_key: The backup object key to sort the playlist by if the sort_key may be of
                            type NoneType. Mandatory for sorting by artist.
    :type backup_sort_key: str
    :param secondary_sort_key: The secondary object key you want to sort the playlist by after it has
                               already been sorted by the sort_key, e.g. the track artist after sorting
                               the list by track title to group them together. Only viable for audio playlists.
    :type secondary_sort_key: str
    :param backup_secondary_sort_key: The backup object key for the secondary_sort_key.
    :type backup_secondary_sort_key: str
    :param sort_reverse: Whether you want to sort the playlist in reverse order
    :type sort_reverse: bool
    :param duplicate: Whether you want to create a duplicated playlist instead of modifying the selected one
    :type duplicate: bool
    :returns: A Playlist object, either the modified or a newly created one
    :rtype: Playlist
    """

    clear()

    print(
        "Sorting playlist in progress. This may take a while depending on the size of your playlist. "
        "Please be patient.",
    )

    # Get all items and sort them
    print("Preparing playlist items...")
    original_items = playlist.items()
    items = list(original_items)
    if sort_key == "shuffle":
        random.shuffle(items)
    else:
        if secondary_sort_key and playlist.playlistType == "audio":
            items = sorted(
                items,
                key=lambda x: (
                    sortable_term(getattr(x, secondary_sort_key))
                    if getattr(x, secondary_sort_key) is not None
                    else sortable_term(getattr(x, backup_secondary_sort_key))
                ),
                reverse=sort_reverse,
            )

        items = sorted(
            items,
            key=lambda x: (
                sortable_term(getattr(x, sort_key))
                if getattr(x, sort_key) is not None
                else sortable_term(getattr(x, backup_sort_key))
            ),
            reverse=sort_reverse,
        )

    # Create a new playlist with sorted items
    if duplicate:
        print(f'Creating new playlist "Copy of {playlist.title}"...')
        new_playlist = Playlist.create(
            server=server,
            title=f"Copy of {playlist.title}",
            summary=playlist.summary,
            items=items,
            playlistType=playlist.playlistType,
        )

        print(f'Successfully created and sorted playlist "{new_playlist.title}".')
        return new_playlist

    # Sort an existing playlist
    print(f'Sorting playlist "{playlist.title}"...')

    if [playlist_item_order_key(item) for item in original_items] == [playlist_item_order_key(item) for item in items]:
        print(f'Playlist "{playlist.title}" is already sorted.')
        return playlist

    move_playlist_items_one_by_one(playlist, items)

    print(f'Successfully sorted playlist "{playlist.title}".')
    return playlist


def upgrade_playlist(
    config: PlexConfig,
    server: PlexServer,
    playlist: Playlist,
    duplicate: bool = False,
    simple_mode: bool = False,
    dry: bool = False,
) -> Playlist:
    """
    Function: upgrade_playlist()

    Upgrades tracks in a playlist to a better version of the same track present in your library.
    Tracks to be upgradeable are as defined in check_quality_requirements().

    :param config: PlexConfig object
    :type config: PlexConfig
    :param server: PlexServer object
    :type server: PlexServer
    :param playlist: Playlist object
    :type playlist: Playlistobject
    :param duplicate: Whether you want to create a duplicated playlist instead of modifying the selected one
    :type duplicate: bool
    :param simple_mode: Whether you want to enable the simple replacement mode
    :type simple_mode: bool
    :param dry: Whether you want to perform a dry run and only check what would be replaced instead of actually
                modifying anything
    :type dry: bool
    :returns: A Playlist object, either the modified or a newly created one
    :rtype: Playlist
    """

    clear()

    print(
        "Upgrading playlist in progress. This may take a while depending on the size of your playlist. "
        "Please be patient.",
    )

    # Get all items
    print("Preparing playlist items...")
    items = playlist.items()

    # Create a new playlist with the same items for now
    if duplicate and not dry:
        print(f'Creating new playlist "Copy of {playlist.title}"...')
        new_playlist = Playlist.create(
            server=server,
            title=f"Copy of {playlist.title}",
            summary=playlist.summary,
            items=items,
            playlistType=playlist.playlistType,
        )

        print(f'Successfully created playlist "{new_playlist.title}".')
        playlist = new_playlist
        items = playlist.items()

    items_to_remove = []
    items_to_add = []
    items_ommited = []

    clear()

    # Analyze all tracks in the playlist and check if they fail to meet the quality requirements
    for item in items:
        if not check_quality_requirements(item):
            print(f"❌ {audio_to_str(item)} must be upgraded.")

            # Search for the same track in your library
            search_results = server.library.search(
                title=re.sub(r"[^\w\s]", "", item.title),
                artist=re.sub(r"[^\w\s]", "", artist(item)),
                libtype="track",
            )

            # Remove all tracks with lower quality
            replacements = [
                r for r in search_results if r.media[0].bitrate and r.media[0].bitrate > item.media[0].bitrate
            ]

            # Remove all tracks where there's a completely different artist
            replacements = [r for r in replacements if artist(item).casefold() in artist(r).casefold()]

            # Sort the search results by bitrate and artist
            replacements = sorted(
                replacements,
                key=lambda x: x.originalTitle if x.originalTitle is not None else x.grandparentTitle,
            )
            replacements = sorted(replacements, key=lambda x: x.media[0].bitrate, reverse=True)

            if not len(replacements):
                items_ommited.append(item)
                print("❔ No potential replacement tracks found. No changes to the track will be made.")
                continue

            replacement_candidate = False

            # Simple replacement mode
            if simple_mode:
                # Automatically select the track with the highest bitrate as the replacement track
                replacement = replacements[0]
                print(f"🆕 {audio_to_str(replacement)} will be used instead.")

                # Add the tracks to separate lists for future usage
                items_to_add.append(replacement)
                items_to_remove.append(item)

                replacement_candidate = True
                continue

            # Manual replacement mode
            else:
                # List all tracks with higher bitrates
                replacement = question(
                    message=f'Select a replacement track for "{audio_to_str(item)}"',
                    items=replacements,
                    attr=audio_to_str,
                    none_choice=True,
                    automatic_single_coice_return=False,
                )

                # Add the tracks to separate lists for future usage
                if replacement:
                    items_to_add.append(replacement)
                    items_to_remove.append(item)
                    replacement_candidate = True

                    print(f"🆕 {audio_to_str(replacement)} will be used instead.")

            # Check if similar tracks have been found
            if not replacement_candidate:
                items_ommited.append(item)

                if simple_mode:
                    print("❔ No replacement track found. No changes to the track will be made.")
                else:
                    print("❔ No replacement track selected. No changes to the track will be made.")

        else:
            print(f"✅ {audio_to_str(item)}")

    print()
    clear()

    # Perform all modifications
    if not dry:
        # Remove all items to be upgraded
        if len(items_to_remove):
            playlist.removeItems(items_to_remove)
            print("The following tracks were removed:")
            for item in items_to_remove:
                print(f"❌ {audio_to_str(item)}")
            print()

        # Add new items with better quality
        if len(items_to_add):
            playlist.addItems(items_to_add)
            print("The following tracks were added:")
            for item in items_to_add:
                print(f"🆕 {audio_to_str(item)}")
            print()

        # List all items which couldn't be upgraded
        if len(items_ommited):
            print("The following tracks couldn't be upgraded:")
            for item in items_ommited:
                print(f"❔ {audio_to_str(item)}")
            print()

        print(f'Successfully upgraded playlist "{playlist.title}".')

    return playlist


def export_playlist_as_m3u(config: PlexConfig, playlist: Playlist) -> Path:
    """
    Function: export_playlist_as_m3u()

    Exports a playlist to a local M3U file.

    :param config: PlexConfig object
    :type config: PlexConfig
    :param playlist: Playlist object
    :type playlist: Playlist
    :returns: Path to the exported M3U file
    :rtype: pathlib.Path
    """

    clear()
    print(
        "Playlist export in progress. This may take a while depending on the size of your playlist. Please be patient.",
    )

    output_directory = (config.get("export.output_directory") or "").strip()
    relative_path_base = (config.get("export.relative_path_base") or "").strip()
    output_directory_path = Path(output_directory or ".").expanduser().resolve()
    output_directory_path.mkdir(parents=True, exist_ok=True)
    print(f'Using export directory "{output_directory_path}" (source: active Plex config).')
    if relative_path_base:
        print(f'Exporting media paths relative to "{Path(relative_path_base).expanduser().resolve(strict=False)}".')
    else:
        print("Exporting media paths as absolute paths.")

    safe_playlist_title = re.sub(r"\s*:\s*", " - ", playlist.title)
    safe_playlist_title = re.sub(r"[^\w\-. ']", "_", safe_playlist_title).strip() or "playlist"
    output_file_name = f"{safe_playlist_title}.m3u"
    output_file_path = output_directory_path / output_file_name

    items = list(playlist.items())
    skipped_items = 0
    unmatched_relative_base_paths = 0

    progress_started_at = datetime.datetime.now()
    print_progress_bar(0, len(items), "Exporting playlist", progress_started_at)

    with output_file_path.open("w", encoding="utf-8") as file:
        file.write("#EXTM3U\n")

        for index, item in enumerate(items, start=1):
            try:
                item_paths = item_to_paths(item)

                if not item_paths:
                    skipped_items += 1
                    continue

                file.write(f"#EXTINF:{item_duration_seconds(item)},{item_to_m3u_title(item, playlist.playlistType)}\n")

                for item_path in item_paths:
                    m3u_item_path = export_path_to_m3u_path(item_path, relative_path_base)
                    if relative_path_base and m3u_item_path == item_path:
                        unmatched_relative_base_paths += 1
                    file.write(f"{m3u_item_path}\n")
            finally:
                print_progress_bar(index, len(items), "Exporting playlist", progress_started_at)

    print()

    print(f'✅ Playlist "{playlist.title}" exported to "{output_file_path}".')
    if skipped_items:
        print(f"⚠️ Skipped {skipped_items} items because no local media file path was available.")
    if unmatched_relative_base_paths:
        print(
            f"⚠️ Wrote {unmatched_relative_base_paths} media file paths as absolute paths because they are outside "
            f'the configured relative path base "{Path(relative_path_base).expanduser().resolve(strict=False)}".',
        )

    return output_file_path


def export_playlist_to_music_assistant(config: PlexConfig, playlist: Playlist) -> str:
    """
    Function: export_playlist_to_music_assistant()

    Exports a playlist to a Music Assistant library playlist.

    :param config: PlexConfig object
    :type config: PlexConfig
    :param playlist: Playlist object
    :type playlist: Playlist
    :returns: Name of the Music Assistant playlist
    :rtype: str
    """

    baseurl = (config.get("music_assistant.baseurl") or "").strip()
    token = (config.get("music_assistant.token") or "").strip()
    relative_path_base = (config.get("export.relative_path_base") or "").strip()

    if not baseurl:
        print("ERROR: music_assistant.baseurl must be set to export a playlist to Music Assistant.")
        sys.exit(1)
    if not token:
        print("ERROR: music_assistant.token must be set to export a playlist to Music Assistant.")
        sys.exit(1)
    if not relative_path_base:
        print("ERROR: export.relative_path_base must be set to export a playlist to Music Assistant.")
        sys.exit(1)

    clear()
    print(
        "Playlist export in progress. This may take a while depending on the size of your playlist. Please be patient.",
    )
    print(f'Using Music Assistant at "{baseurl.rstrip("/")}".')
    filesystem_provider = get_music_assistant_filesystem_provider(baseurl, token)
    print(
        f'Mapping media paths relative to "{Path(relative_path_base).expanduser().resolve(strict=False)}" '
        f'as "{filesystem_provider}" track URIs.',
    )

    items = list(playlist.items())
    skipped_items = 0
    unmatched_relative_base_paths = 0
    unresolved_library_uris = 0
    mapped_tracks = []

    progress_started_at = datetime.datetime.now()
    print_progress_bar(0, len(items), "Exporting playlist", progress_started_at)

    for index, item in enumerate(items, start=1):
        try:
            item_paths = item_to_paths(item)
            if not item_paths:
                skipped_items += 1
                continue

            label = audio_to_str(item) if isinstance(item, Audio) else item.title
            mapped_item_uris = []
            for item_path in item_paths:
                music_assistant_item_uri = export_path_to_music_assistant_uri(
                    item_path,
                    relative_path_base,
                    filesystem_provider,
                )
                if music_assistant_item_uri is None:
                    unmatched_relative_base_paths += 1
                    continue
                mapped_item_uris.append(music_assistant_item_uri)

            if not mapped_item_uris:
                continue

            for filesystem_uri in mapped_item_uris:
                mapped_tracks.append({"label": label, "filesystem_uri": filesystem_uri})
        finally:
            print_progress_bar(index, len(items), "Exporting playlist", progress_started_at)

    print()

    if not mapped_tracks:
        print(f'ERROR: Playlist "{playlist.title}" has no exportable local media files.')
        if unmatched_relative_base_paths:
            print(
                f"{unmatched_relative_base_paths} media file paths are outside "
                f'the configured relative path base "{Path(relative_path_base).expanduser().resolve(strict=False)}".',
            )
        sys.exit(1)

    resolved_tracks = []
    progress_started_at = datetime.datetime.now()
    print_progress_bar(0, len(mapped_tracks), "Resolving tracks", progress_started_at)
    for index, mapped_track in enumerate(mapped_tracks, start=1):
        try:
            library_uri = music_assistant_library_uri(baseurl, token, mapped_track["filesystem_uri"])
            if library_uri:
                resolved_tracks.append(
                    {
                        "label": mapped_track["label"],
                        "filesystem_uri": mapped_track["filesystem_uri"],
                        "library_uri": library_uri,
                    },
                )
            else:
                unresolved_library_uris += 1
        finally:
            print_progress_bar(index, len(mapped_tracks), "Resolving tracks", progress_started_at)

    print()

    if not resolved_tracks:
        print(f'ERROR: None of the tracks in "{playlist.title}" were found in the Music Assistant library.')
        sys.exit(1)

    library_uris = [track["library_uri"] for track in resolved_tracks]

    matching_playlists = []
    library_playlists = music_assistant_request(
        baseurl,
        token,
        "music/playlists/library_items",
        {"search": playlist.title, "limit": 500},
    )
    if library_playlists is None:
        library_playlists = []
    if not isinstance(library_playlists, list):
        print("ERROR: Music Assistant returned an unexpected playlist list.")
        sys.exit(1)

    playlist_title_key = playlist.title.casefold()
    for library_playlist in library_playlists:
        if not isinstance(library_playlist, dict):
            print("ERROR: Music Assistant returned an unexpected playlist item.")
            sys.exit(1)
        if (library_playlist.get("name") or "").casefold() == playlist_title_key:
            matching_playlists.append(library_playlist)

    if len(matching_playlists) > 1:
        matching_names = ", ".join(f'"{item.get("name")}"' for item in matching_playlists)
        print(
            f'ERROR: Music Assistant has {len(matching_playlists)} playlists named "{playlist.title}": '
            f"{matching_names}.",
        )
        sys.exit(1)

    music_assistant_playlist_name = playlist.title
    existing_playlist = matching_playlists[0] if matching_playlists else None

    if existing_playlist:
        replace = confirm_question(
            f'A playlist named "{playlist.title}" already exists in Music Assistant. '
            "Do you want to replace it (the existing playlist will be deleted and recreated)?",
            default=False,
        )
        if replace:
            existing_playlist_id = existing_playlist.get("item_id")
            if existing_playlist_id is None:
                print(f'ERROR: Music Assistant playlist "{playlist.title}" has no item_id.')
                sys.exit(1)
            print(f'Deleting existing Music Assistant playlist "{playlist.title}"...')
            music_assistant_request(
                baseurl,
                token,
                "music/library/remove_item",
                {"media_type": "playlist", "library_item_id": existing_playlist_id},
            )
        else:
            music_assistant_playlist_name = f"{playlist.title} {datetime.datetime.now().strftime('%Y-%m-%d %H-%M')}"

    print(f'Creating Music Assistant playlist "{music_assistant_playlist_name}"...')
    created_playlist = music_assistant_request(
        baseurl,
        token,
        "music/playlists/create_playlist",
        {"name": music_assistant_playlist_name},
    )
    if not isinstance(created_playlist, dict) or created_playlist.get("item_id") is None:
        print("ERROR: Music Assistant did not return a playlist id after create_playlist.")
        sys.exit(1)

    created_playlist_id = created_playlist["item_id"]
    if created_playlist.get("name"):
        music_assistant_playlist_name = created_playlist["name"]

    print(f'Adding {len(library_uris)} tracks to "{music_assistant_playlist_name}"...')
    add_task = music_assistant_request(
        baseurl,
        token,
        "music/playlists/add_playlist_tracks",
        {"db_playlist_id": created_playlist_id, "uris": library_uris},
    )
    if isinstance(add_task, dict) and add_task.get("last_error"):
        print("ERROR: Music Assistant failed to add tracks to the playlist.")
        print(add_task["last_error"])
        sys.exit(1)

    add_task_status = str((add_task or {}).get("status") if isinstance(add_task, dict) else "").lower()
    wait_timeout = (
        15
        if isinstance(add_task, dict)
        and (add_task.get("finished_at") or add_task_status in {"completed", "complete", "finished", "success", "done"})
        else 300
    )
    added_track_count, added_tracks = wait_for_music_assistant_playlist_tracks(
        baseurl,
        token,
        created_playlist_id,
        len(library_uris),
        timeout_seconds=wait_timeout,
    )
    if added_track_count < len(library_uris):
        print(
            f'ERROR: Music Assistant playlist "{music_assistant_playlist_name}" contains '
            f"{added_track_count}/{len(library_uris)} tracks after export.",
        )
        unmatched_tracks = unmatched_music_assistant_export_tracks(resolved_tracks, added_tracks)
        if unmatched_tracks:
            print("Music Assistant did not keep these tracks:")
            for record in unmatched_tracks:
                print(f"  - {record['label']}")
                print(f"    {record['filesystem_uri']}")
        else:
            print("Could not identify which sent tracks are missing from the playlist response.")

        duplicate_groups = music_assistant_duplicate_library_uri_groups(resolved_tracks)
        if duplicate_groups:
            print("These Plex tracks resolved to the same Music Assistant library item:")
            for group in duplicate_groups:
                print(f"  {group[0]['library_uri']}")
                for record in group:
                    print(f"    - {record['label']}")
                    print(f"      {record['filesystem_uri']}")
            duplicate_extras = sum(len(group) - 1 for group in duplicate_groups)
            if len(unmatched_tracks) == duplicate_extras:
                print("Music Assistant skipped the duplicate library item(s).")
        sys.exit(1)

    print(f'✅ Playlist "{playlist.title}" exported to Music Assistant as "{music_assistant_playlist_name}".')
    if skipped_items:
        print(f"⚠️ Skipped {skipped_items} items because no local media file path was available.")
    if unmatched_relative_base_paths:
        print(
            f"⚠️ Skipped {unmatched_relative_base_paths} media file paths because they are outside "
            f'the configured relative path base "{Path(relative_path_base).expanduser().resolve(strict=False)}".',
        )
    if unresolved_library_uris:
        print(
            f"⚠️ Skipped {unresolved_library_uris} tracks because they were not found in the Music Assistant library.",
        )

    return music_assistant_playlist_name


if __name__ == "__main__":
    clear()

    # Load configuration
    config = get_config()

    # Connect to the Plex server
    server = get_server(config)

    while True:
        # Decide what you want to organize
        action = question(
            message="What do you want to organize?",
            items=[
                "Sort playlists (audio & video)",
                "Upgrade playlists (audio only)",
                "Find all music albums with low bitrate (audio only)",
                "Export playlist as M3U (audio & video)",
                "Export playlist to Music Assistant (audio only)",
            ],
            automatic_single_coice_return=False,
        )

        # Sort playlists (audio & video)
        if action == "Sort playlists (audio & video)":
            # Select a playlist to organize
            playlists = get_playlists(server)
            playlist = question(
                message="Select a playlist to sort",
                items=playlists,
                attr="title",
                automatic_single_coice_return=False,
            )

            # Select the sorting method
            sort_key, backup_sort_key, secondary_sort_key, backup_secondary_sort_key, sort_reverse = (
                choose_sorting_method(
                    playlist,
                )
            )

            clear()

            # Decide on duplicating the selected playlist
            duplicate = confirm_question(
                "Do you want to create a duplicated playlist instead of modifying the selected one?",
                default=False,
            )

            # Sort playlist
            sort_playlist(
                server=server,
                playlist=playlist,
                sort_key=sort_key,
                backup_sort_key=backup_sort_key,
                secondary_sort_key=secondary_sort_key,
                backup_secondary_sort_key=backup_secondary_sort_key,
                sort_reverse=sort_reverse,
                duplicate=duplicate,
            )

            clear()

        # Upgrade playlists (audio only)
        elif action == "Upgrade playlists (audio only)":
            # Select a playlist to organize
            playlists = get_playlists(server, ["audio"])
            playlist = question(
                message="Select a playlist to upgrade",
                items=playlists,
                attr="title",
                automatic_single_coice_return=False,
            )

            clear()

            # Decide on whether this should only be a dry run
            dry = confirm_question(
                "Do you want to perform a dry run instead of actually modifying anything?",
                default=False,
            )

            # Decide on whether the simple replacement mode should be used
            simple_mode = (
                True
                if dry
                else confirm_question(
                    "Do you want to enable the simple replacement mode "
                    "(The best version available will automatically be selected)?",
                    default=False,
                )
            )

            # Decide on duplicating the selected playlist
            duplicate = (
                False
                if dry
                else confirm_question(
                    "Do you want to create a duplicated playlist instead of modifying the selected one?",
                    default=False,
                )
            )

            clear()

            # Upgrade playlist
            upgrade_playlist(
                config=config,
                server=server,
                playlist=playlist,
                duplicate=duplicate,
                simple_mode=simple_mode,
                dry=dry,
            )

            clear()

        # Find all music albums with low bitrate (audio only)
        elif action == "Find all music albums with low bitrate (audio only)":
            # Select a library section to connect to
            sections = get_sections(server, "artist")
            section = question(
                message="Select a section to connect to",
                items=sections,
                attr="title",
                automatic_single_coice_return=True,
            )

            # Decide on whether to save the list of albums to a local text file
            save_to_file = confirm_question(
                "Do you want to save the list of albums to a local text file?",
                default=False,
            )

            clear()

            print(
                "Album search in progress. This may take a while depending on the size of your music library. "
                "Please be patient.",
            )
            print()

            low_bitrate_albums = []

            # Get all albums
            for album in section.albums():
                # Get all tracks of the album and check if they all meet the quality criteria
                for track in album.tracks():
                    if not check_quality_requirements(track):
                        low_bitrate_album = (
                            f"{album.parentTitle} - {album.title} ({album.year}) "
                            f"[{track.media[0].audioCodec}][{track.media[0].bitrate}]"
                        )
                        low_bitrate_albums.append(low_bitrate_album)
                        print(
                            f"❌ {low_bitrate_album} must be upgraded.",
                        )
                        break

            if len(low_bitrate_albums) and save_to_file:
                file_name = f"low_bitrate_albums_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
                with open(file_name, "w", encoding="utf-8") as file:
                    file.write("\n".join(sorted(low_bitrate_albums)))
                print(f"✅ Saved {len(low_bitrate_albums)} entries to '{file_name}'.")
                clear()
            else:
                print()
                print()

        # Export playlist as M3U
        elif action == "Export playlist as M3U (audio & video)":
            playlists = get_playlists(server)
            playlist = question(
                message="Select a playlist to export",
                items=playlists,
                attr="title",
                automatic_single_coice_return=False,
            )

            export_playlist_as_m3u(
                config=config,
                playlist=playlist,
            )

        # Export playlist to Music Assistant
        elif action == "Export playlist to Music Assistant (audio only)":
            playlists = get_playlists(server, ["audio"])
            playlist = question(
                message="Select a playlist to export",
                items=playlists,
                attr="title",
                automatic_single_coice_return=False,
            )

            export_playlist_to_music_assistant(
                config=config,
                playlist=playlist,
            )

        if not confirm_question("Do you want to organize another playlist?"):
            sys.exit()
