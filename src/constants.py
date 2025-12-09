import flet as ft
import os

# --- Constants ---
APP_NAME = "All Might"
CONFIG_DIR = os.path.expanduser("~/.config/all-might")
CONFIG_FILE = os.path.join(CONFIG_DIR, "settings.json")
TRACKING_FILE = os.path.join(CONFIG_DIR, "installed.json")

# --- Mock Data for Daily Digest ---
DAILY_APPS = [
    {"pname": "firefox", "desc": "A free and open-source web browser developed by the Mozilla Foundation."},
    {"pname": "neovim", "desc": "Hyperextensible Vim-based text editor."},
    {"pname": "htop", "desc": "An interactive process viewer."},
    {"pname": "git", "desc": "Distributed version control system."},
    {"pname": "vscode", "desc": "Code editing. Redefined."},
    {"pname": "vlc", "desc": "The ultimate media player."},
    {"pname": "obs-studio", "desc": "Free and open source software for video recording and live streaming."},
    {"pname": "gimp", "desc": "GNU Image Manipulation Program."},
    {"pname": "ripgrep", "desc": "A line-oriented search tool that recursively searches the current directory."},
    {"pname": "bat", "desc": "A cat(1) clone with wings."}
]

DAILY_QUOTES = [
    {"text": "The computer was born to solve problems that did not exist before.", "author": "Bill Gates"},
    {"text": "Talk is cheap. Show me the code.", "author": "Linus Torvalds"},
    {"text": "Software is like sex: it's better when it's free.", "author": "Linus Torvalds"},
    {"text": "It's not a bug – it's an undocumented feature.", "author": "Anonymous"},
    {"text": "First, solve the problem. Then, write the code.", "author": "John Johnson"},
    {"text": "Experience is the name everyone gives to their mistakes.", "author": "Oscar Wilde"}
]

DAILY_TIPS = [
    {"title": "Tracked Installs", "code": "All-Might remembers what you installed, so you can see details later!"},
    {"title": "Try without Installing", "code": "Use the 'Run' button to test apps in a temporary shell."},
    {"title": "Custom Lists", "code": "Save your favorite apps into custom lists for bulk operations."},
    {"title": "Search Power", "code": "Search results come directly from the official NixOS search backend."},
    {"title": "Clean Metadata", "code": "All-Might cleans up package names and descriptions for a better UI."}
]

DAILY_SONGS = [
    {"title": "Doin' it Right", "artist": "Daft Punk"},
    {"title": "Midnight City", "artist": "M83"},
    {"title": "Instant Crush", "artist": "Daft Punk"},
    {"title": "Technologic", "artist": "Daft Punk"},
    {"title": "Computer Love", "artist": "Kraftwerk"},
    {"title": "Resonance", "artist": "Home"}
]

CAROUSEL_DATA = [
    {"title": "Search Packages", "desc": "Find any package from nixpkgs. Search by name or description.", "color": ft.Colors.BLUE, "icon": ft.Icons.SEARCH},
    {"title": "Manage Lists", "desc": "Create Favorites or custom lists to organize your software.", "color": ft.Colors.GREEN, "icon": ft.Icons.LIST},
    {"title": "Try in Shell", "desc": "Use 'nix-shell' to try packages without installing them permanently.", "color": ft.Colors.PURPLE, "icon": ft.Icons.TERMINAL},
    {"title": "Inspect Binaries", "desc": "View the binaries installed by a package in the card details.", "color": ft.Colors.ORANGE, "icon": ft.Icons.CODE},
    {"title": "Build Commands", "desc": "Copy install commands for NixOS, Home Manager, or generic Nix.", "color": ft.Colors.RED, "icon": ft.Icons.COPY},
]

# Mapping for string color names to Flet colors
COLOR_NAME_MAP = {
    "indigo": ft.Colors.INDIGO,
    "blue": ft.Colors.BLUE,
    "teal": ft.Colors.TEAL,
    "green": ft.Colors.GREEN,
    "amber": ft.Colors.AMBER,
    "orange": ft.Colors.ORANGE,
    "red": ft.Colors.RED,
    "pink": ft.Colors.PINK,
    "purple": ft.Colors.PURPLE,
    "blue_grey": ft.Colors.BLUE_GREY
}

# Default Configuration for Cards
CARD_DEFAULTS = {
    "app": {"visible": True, "h": 180, "w": 0, "align": "left", "color": "indigo"},
    "quote": {"visible": True, "h": 130, "w": 0, "align": "center", "color": "red"},
    "tip": {"visible": True, "h": 180, "w": 0, "align": "left", "color": "teal"},
    "song": {"visible": True, "h": 130, "w": 0, "align": "center", "color": "amber"},
}
