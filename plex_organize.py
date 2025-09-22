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
import os
import random
import re
import sys
from getpass import getpass

import inquirer
from plexapi import PlexConfig
from plexapi.audio import Album, Audio
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


def sortable_term(term: str | datetime.datetime) -> str:
    """
    Function: sortable_term()

    Transforms the provided term to a sortable string by removing articles and changing it to lowercase.
    It also transliterates the term and changes or removes certain characters.

    :param term: Term to sort by
    :type term: str|datetime.datetime
    :returns: Manipulated string to be used for sorting
    :rtype: str
    """
    if isinstance(term, datetime.datetime):
        return term.isoformat()

    term = unidecode(term.lower())

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

    return term.strip()


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
    :param default: Wheter 'Yes' or 'No' should be set as the default choice
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


def question(message: str, items: list, attr: str | None = None, none_choice: bool = False) -> any:
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
    :returns: Wheter the answers should include a "None" option by default
    :rtype: any
    """

    # Return the first item if there is only one choice
    if len(items) == 1:
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

    :returns: A tuple with the key, backup key and direction to sort. The backup key can be used if the main key may be of type NoneType.
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

    selected_choice = question(f"Select the sorting key for this {playlist_type} playlist", choices, "name")

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
        f"Select the sorting direction for {selected_choice['name']}",
        sorting_choices,
        "name",
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
                "This is your authentication token that you can save in your configuration file to avoid having to log in every time:",
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

        answers = inquirer.prompt(questions)

        try:
            account = MyPlexAccount(answers["username"], answers["password"])

            print()
            print(
                "This is your authentication token that you can save in your configuration file to avoid having to log in every time:",
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
    :param sort_key: The object key you want to sort the playlist by. Available choices depend on the type of media the playlist contains.
    :type sort_key: str
    :param backup_sort_key: The backup object key to sort the playlist by if the sort_key may be of type NoneType. Mandatory for sorting by artist.
    :type backup_sort_key: str
    :param secondary_sort_key: The secondary object key you want to sort the playlist by after it has already been sorted by the sort_key, e.g. the track artist after sorting the list by track title to group them together. Only viable for audio playlists.
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
        "Sorting playlist in progress. This may take a while depending on the size of your playlist. Please be patient.",
    )

    # Get all items and sort them
    print("Preparing playlist items...")
    items = playlist.items()
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
    else:
        print(f'Sorting playlist "{playlist.title}"...')
        previous_item = None
        for item in items:
            playlist.moveItem(item, after=previous_item)
            previous_item = item

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
        "Upgrading playlist in progress. This may take a while depending on the size of your playlist. Please be patient.",
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
                key=lambda x: (
                    getattr(x, "originalTitle")
                    if getattr(x, "originalTitle") is not None
                    else getattr(x, "grandparentTitle")
                ),
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


if __name__ == "__main__":
    clear()

    # Load configuration
    config = get_config()

    # Login to the Plex account
    account = get_account(config)

    # Select a resource to connect to
    resources = get_resources(account)
    resource = question("Select resource to connect to", resources, "name")

    # Connect to the selected resource and create a server object
    server = account.resource(resource.name).connect()

    while True:
        # Decide what you want to organize
        action = question(
            "What do you want to organize?",
            [
                "Sort playlists (audio & video)",
                "Upgrade playlists (audio only)",
                "Find all music albums with low bitrate (audio only)",
            ],
        )

        # Sort playlists (audio & video)
        if action == "Sort playlists (audio & video)":
            # Select a playlist to organize
            playlists = get_playlists(server)
            playlist = question("Select a playlist to sort", playlists, "title")

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

        # Upgrade playlists (audio only)
        elif action == "Upgrade playlists (audio only)":
            # Select a playlist to organize
            playlists = get_playlists(server, ["audio"])
            playlist = question("Select a playlist to upgrade", playlists, "title")

            clear()

            # Decide on wheter this should only be a dry run
            dry = confirm_question(
                "Do you want to perform a dry run instead of actually modifying anything?",
                default=False,
            )

            # Decide on wheter the simple replacement mode should be used
            simple_mode = (
                True
                if dry
                else confirm_question(
                    "Do you want to enable the simple replacement mode (The best version available will automatically be selected)?",
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

        # Find all music albums with low bitrate (audio only)
        elif action == "Find all music albums with low bitrate (audio only)":
            # Select a library section to connect to
            sections = get_sections(server, "artist")
            section = question("Select section to connect to", sections, "title")

            clear()

            print(
                "Album search in progress. This may take a while depending on the size of your music library. Please be patient.",
            )
            print()

            # Get all albums
            for album in section.albums():
                # Get all tracks of the album and check if they all meet the quality criteria
                for track in album.tracks():
                    if not check_quality_requirements(track):
                        print(
                            f"❌ {album.parentTitle} - {album.title} ({album.year}) [{track.media[0].audioCodec}][{track.media[0].bitrate}] must be upgraded.",
                        )
                        break

            print()

        clear()

        if not confirm_question("Do you want to organize another playlist?"):
            sys.exit()
