import flet as ft
import subprocess
import json
import os
import shlex
import threading
import time
import random
import datetime
from collections import Counter
from pathlib import Path

# --- Constants ---
APP_NAME = "All Might"
CONFIG_DIR = os.path.expanduser("~/.config/all-might")
CONFIG_FILE = os.path.join(CONFIG_DIR, "settings.json")

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
    {"title": "Nix Shell", "code": "nix-shell -p python3"},
    {"title": "Check Config", "code": "nixos-rebuild test"},
    {"title": "Search", "code": "nix search nixpkgs#firefox"},
    {"title": "Garbage Collect", "code": "nix-collect-garbage -d"},
    {"title": "Flake Update", "code": "nix flake update"},
    {"title": "Repl", "code": "nix repl"},
    {"title": "List Generations", "code": "nix-env --list-generations"}
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
    {"title": "New Feature!", "desc": "Check out the new settings page.", "color": ft.Colors.BLUE},
    {"title": "Nix Tip", "desc": "Use 'nix flake update' often.", "color": ft.Colors.GREEN},
    {"title": "Community", "desc": "Join the Matrix chat!", "color": ft.Colors.PURPLE},
    {"title": "Pro Tip", "desc": "Right click for context menus.", "color": ft.Colors.ORANGE},
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

# --- Global Callback Reference ---
global_open_menu_func = None

# --- State Management ---
class AppState:
    def __init__(self):
        self.username = "user"
        self.default_channel = "nixos-24.11"
        self.confirm_timer = 5
        self.undo_timer = 5
        self.nav_badge_size = 20
        self.theme_mode = "dark"
        self.theme_color = "blue"

        # New Features
        self.search_limit = 30

        # Nav Bar Settings
        self.floating_nav = True
        self.adaptive_nav = True
        self.glass_nav = True
        self.nav_bar_width = 500
        self.nav_icon_spacing = 15
        self.sync_nav_spacing = True

        # Radius Settings
        self.global_radius = 33

        self.nav_radius = 33
        self.sync_nav_radius = True

        self.card_radius = 15
        self.sync_card_radius = True

        self.button_radius = 10
        self.sync_button_radius = True

        self.search_radius = 15
        self.sync_search_radius = True

        self.selector_radius = 15
        self.sync_selector_radius = True

        self.footer_radius = 15
        self.sync_footer_radius = True

        self.chip_radius = 10
        self.sync_chip_radius = True

        # Font Settings
        self.global_font_size = 14

        self.title_font_size = 16
        self.sync_title_font = True

        self.body_font_size = 14
        self.sync_body_font = True

        self.small_font_size = 12
        self.sync_small_font = True

        self.nav_font_size = 12
        self.sync_nav_font = True

        # Home Page Settings
        self.home_card_config = CARD_DEFAULTS.copy()
        self.carousel_timer = 10
        self.carousel_glass = True # Default to glassmorphism

        self.daily_indices = {"app": 0, "quote": 0, "tip": 0, "song": 0}
        self.last_daily_date = ""

        # History
        self.recent_activity = []

        # Separate configs for Single App vs Cart
        self.shell_single_prefix = "x-terminal-emulator -e"
        self.shell_single_suffix = ""
        self.shell_cart_prefix = "x-terminal-emulator -e"
        self.shell_cart_suffix = ""

        self.available_channels = [
            "nixos-25.05", "nixos-unstable", "nixos-24.11", "nixos-24.05"
        ]
        self.active_channels = [
            "nixos-25.05", "nixos-unstable", "nixos-24.11"
        ]
        self.cart_items = []
        self.favourites = []
        self.saved_lists = {}
        self.load_settings()
        self.update_daily_indices()

    def update_daily_indices(self):
        today = datetime.date.today().isoformat()
        if self.last_daily_date != today:
            self.last_daily_date = today
            self.daily_indices = {
                "app": random.randint(0, len(DAILY_APPS) - 1),
                "quote": random.randint(0, len(DAILY_QUOTES) - 1),
                "tip": random.randint(0, len(DAILY_TIPS) - 1),
                "song": random.randint(0, len(DAILY_SONGS) - 1),
            }
            self.save_settings()

    def load_settings(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r') as f:
                    data = json.load(f)
                    self.username = data.get("username", "user")
                    self.default_channel = data.get("default_channel", self.default_channel)
                    self.theme_mode = data.get("theme_mode", "dark")
                    self.theme_color = data.get("theme_color", "blue")

                    legacy_timer = data.get("countdown_timer", 5)
                    self.confirm_timer = data.get("confirm_timer", legacy_timer)
                    self.undo_timer = data.get("undo_timer", legacy_timer)

                    self.nav_badge_size = data.get("nav_badge_size", 20)

                    self.search_limit = data.get("search_limit", 30)
                    self.floating_nav = data.get("floating_nav", True)
                    self.adaptive_nav = data.get("adaptive_nav", True)
                    self.glass_nav = data.get("glass_nav", True)
                    self.nav_bar_width = data.get("nav_bar_width", 500)
                    self.nav_icon_spacing = data.get("nav_icon_spacing", 15)
                    self.sync_nav_spacing = data.get("sync_nav_spacing", True)

                    # Radius
                    self.global_radius = data.get("global_radius", 33)

                    self.nav_radius = data.get("nav_radius", 33)
                    self.sync_nav_radius = data.get("sync_nav_radius", True)

                    self.card_radius = data.get("card_radius", 15)
                    self.sync_card_radius = data.get("sync_card_radius", True)

                    self.button_radius = data.get("button_radius", 10)
                    self.sync_button_radius = data.get("sync_button_radius", True)

                    self.search_radius = data.get("search_radius", 15)
                    self.sync_search_radius = data.get("sync_search_radius", True)

                    self.selector_radius = data.get("selector_radius", 15)
                    self.sync_selector_radius = data.get("sync_selector_radius", True)

                    self.footer_radius = data.get("footer_radius", 15)
                    self.sync_footer_radius = data.get("sync_footer_radius", True)

                    self.chip_radius = data.get("chip_radius", 10)
                    self.sync_chip_radius = data.get("sync_chip_radius", True)

                    # Fonts
                    self.global_font_size = data.get("font_size", data.get("global_font_size", 14))

                    self.title_font_size = data.get("title_font_size", 16)
                    self.sync_title_font = data.get("sync_title_font", True)

                    self.body_font_size = data.get("body_font_size", 14)
                    self.sync_body_font = data.get("sync_body_font", True)

                    self.small_font_size = data.get("small_font_size", 12)
                    self.sync_small_font = data.get("sync_small_font", True)

                    self.nav_font_size = data.get("nav_font_size", 12)
                    self.sync_nav_font = data.get("sync_nav_font", True)

                    # Home Page
                    saved_card_config = data.get("home_card_config", None)
                    if saved_card_config:
                        for k, v in CARD_DEFAULTS.items():
                            if k not in saved_card_config:
                                saved_card_config[k] = v
                            else:
                                if "color" not in saved_card_config[k]:
                                    saved_card_config[k]["color"] = v["color"]
                        self.home_card_config = saved_card_config
                    else:
                        self.home_card_config = CARD_DEFAULTS.copy()
                        if "home_show_app" in data: self.home_card_config["app"]["visible"] = data["home_show_app"]
                        if "home_show_quote" in data: self.home_card_config["quote"]["visible"] = data["home_show_quote"]
                        if "home_show_tip" in data: self.home_card_config["tip"]["visible"] = data["home_show_tip"]
                        if "home_show_song" in data: self.home_card_config["song"]["visible"] = data["home_show_song"]

                    self.daily_indices = data.get("daily_indices", self.daily_indices)
                    self.last_daily_date = data.get("last_daily_date", "")
                    self.carousel_timer = data.get("carousel_timer", 10)
                    self.carousel_glass = data.get("carousel_glass", True)

                    self.available_channels = data.get("available_channels", self.available_channels)
                    self.active_channels = data.get("active_channels", self.active_channels)

                    self.shell_single_prefix = data.get("shell_single_prefix", data.get("shell_prefix", "x-terminal-emulator -e"))
                    self.shell_single_suffix = data.get("shell_single_suffix", data.get("shell_suffix", ""))
                    self.shell_cart_prefix = data.get("shell_cart_prefix", self.shell_single_prefix)
                    self.shell_cart_suffix = data.get("shell_cart_suffix", self.shell_single_suffix)

                    self.cart_items = data.get("cart_items", [])
                    self.favourites = data.get("favourites", [])
                    self.saved_lists = data.get("saved_lists", {})
                    self.recent_activity = data.get("recent_activity", [])

            except Exception as e:
                print(f"Error loading settings: {e}")

    def save_settings(self):
        try:
            Path(CONFIG_DIR).mkdir(parents=True, exist_ok=True)
            data = {
                "username": self.username,
                "default_channel": self.default_channel,
                "theme_mode": self.theme_mode,
                "theme_color": self.theme_color,
                "confirm_timer": self.confirm_timer,
                "undo_timer": self.undo_timer,
                "nav_badge_size": self.nav_badge_size,
                "search_limit": self.search_limit,

                "floating_nav": self.floating_nav,
                "adaptive_nav": self.adaptive_nav,
                "glass_nav": self.glass_nav,
                "nav_bar_width": self.nav_bar_width,
                "nav_icon_spacing": self.nav_icon_spacing,
                "sync_nav_spacing": self.sync_nav_spacing,

                "global_radius": self.global_radius,
                "nav_radius": self.nav_radius,
                "sync_nav_radius": self.sync_nav_radius,
                "card_radius": self.card_radius,
                "sync_card_radius": self.sync_card_radius,
                "button_radius": self.button_radius,
                "sync_button_radius": self.sync_button_radius,
                "search_radius": self.search_radius,
                "sync_search_radius": self.sync_search_radius,
                "selector_radius": self.selector_radius,
                "sync_selector_radius": self.sync_selector_radius,
                "footer_radius": self.footer_radius,
                "sync_footer_radius": self.sync_footer_radius,
                "chip_radius": self.chip_radius,
                "sync_chip_radius": self.sync_chip_radius,

                "global_font_size": self.global_font_size,
                "title_font_size": self.title_font_size,
                "sync_title_font": self.sync_title_font,
                "body_font_size": self.body_font_size,
                "sync_body_font": self.sync_body_font,
                "small_font_size": self.small_font_size,
                "sync_small_font": self.sync_small_font,
                "nav_font_size": self.nav_font_size,
                "sync_nav_font": self.sync_nav_font,

                "home_card_config": self.home_card_config,
                "daily_indices": self.daily_indices,
                "last_daily_date": self.last_daily_date,
                "carousel_timer": self.carousel_timer,
                "carousel_glass": self.carousel_glass,

                "available_channels": self.available_channels,
                "active_channels": self.active_channels,
                "shell_single_prefix": self.shell_single_prefix,
                "shell_single_suffix": self.shell_single_suffix,
                "shell_cart_prefix": self.shell_cart_prefix,
                "shell_cart_suffix": self.shell_cart_suffix,
                "cart_items": self.cart_items,
                "favourites": self.favourites,
                "saved_lists": self.saved_lists,
                "recent_activity": self.recent_activity
            }
            with open(CONFIG_FILE, 'w') as f:
                json.dump(data, f, indent=4)
        except Exception as e:
            print(f"Error saving settings: {e}")

    # --- Scalable Font Logic ---
    def get_font_size(self, component):
        # Default scaling factors relative to global
        if component == 'title':
            if self.sync_title_font:
                return int(self.global_font_size * 1.15)
            return self.title_font_size
        elif component == 'body':
            if self.sync_body_font:
                return int(self.global_font_size * 1.0)
            return self.body_font_size
        elif component == 'small':
            if self.sync_small_font:
                return int(self.global_font_size * 0.85)
            return self.small_font_size
        elif component == 'nav':
            if self.sync_nav_font:
                return int(self.get_font_size('small') * 0.9)
            return self.nav_font_size

        return self.global_font_size

    def get_size(self, scale=1.0):
        return int(self.global_font_size * scale)

    def get_radius(self, component):
        if component == 'nav':
            return self.global_radius if self.sync_nav_radius else self.nav_radius
        elif component == 'card':
            return self.global_radius if self.sync_card_radius else self.card_radius
        elif component == 'button':
            return self.global_radius if self.sync_button_radius else self.button_radius
        elif component == 'search':
            return self.global_radius if self.sync_search_radius else self.search_radius
        elif component == 'selector':
            return self.global_radius if self.sync_selector_radius else self.selector_radius
        elif component == 'footer':
            return self.global_radius if self.sync_footer_radius else self.footer_radius
        elif component == 'chip':
            return self.global_radius if self.sync_chip_radius else self.chip_radius
        return self.global_radius

    def add_channel(self, channel_name):
        if channel_name and channel_name not in self.available_channels:
            self.available_channels.append(channel_name)
            if channel_name not in self.active_channels:
                self.active_channels.append(channel_name)
            self.save_settings()
            return True
        return False

    def remove_channel(self, channel_name):
        if channel_name in self.available_channels:
            self.available_channels.remove(channel_name)
            if channel_name in self.active_channels:
                self.active_channels.remove(channel_name)
            if self.default_channel == channel_name:
                self.default_channel = self.available_channels[0] if self.available_channels else "nixos-unstable"
            self.save_settings()
            return True
        return False

    def toggle_channel(self, channel_name, is_active):
        if is_active:
            if channel_name not in self.active_channels:
                self.active_channels.append(channel_name)
        else:
            if channel_name in self.active_channels:
                self.active_channels.remove(channel_name)
        self.save_settings()

    def _get_pkg_id(self, package):
        if "package_attr_name" in package:
            return package["package_attr_name"]
        return f"{package.get('package_pname')}-{package.get('package_pversion')}"

    def is_in_cart(self, package, channel):
        pkg_id = self._get_pkg_id(package)
        for item in self.cart_items:
            if self._get_pkg_id(item['package']) == pkg_id and item['channel'] == channel:
                return True
        return False

    def add_to_cart(self, package, channel):
        if self.is_in_cart(package, channel):
            return False
        self.cart_items.append({'package': package, 'channel': channel})
        self.save_settings()
        return True

    def remove_from_cart(self, package, channel):
        pkg_id = self._get_pkg_id(package)
        for i, item in enumerate(self.cart_items):
            if self._get_pkg_id(item['package']) == pkg_id and item['channel'] == channel:
                del self.cart_items[i]
                self.save_settings()
                return True
        return False

    def clear_cart(self):
        self.cart_items = []
        self.save_settings()

    def restore_cart(self, items):
        self.cart_items = items
        self.save_settings()

    def save_list(self, name, items):
        self.saved_lists[name] = items
        self.save_settings()

    def delete_list(self, name):
        if name in self.saved_lists:
            del self.saved_lists[name]
            self.save_settings()

    def restore_list(self, name, items):
        self.saved_lists[name] = items
        self.save_settings()

    def add_to_history(self, package, channel):
        pkg_id = self._get_pkg_id(package)
        self.recent_activity = [
            item for item in self.recent_activity
            if self._get_pkg_id(item['package']) != pkg_id or item['channel'] != channel
        ]
        self.recent_activity.insert(0, {'package': package, 'channel': channel})
        self.recent_activity = self.recent_activity[:5]
        self.save_settings()

    def clear_history(self):
        self.recent_activity = []
        self.save_settings()

    def is_favourite(self, package, channel):
        pkg_id = self._get_pkg_id(package)
        for item in self.favourites:
            if self._get_pkg_id(item['package']) == pkg_id and item['channel'] == channel:
                return True
        return False

    def toggle_favourite(self, package, channel):
        pkg_id = self._get_pkg_id(package)
        idx = -1
        for i, item in enumerate(self.favourites):
            if self._get_pkg_id(item['package']) == pkg_id and item['channel'] == channel:
                idx = i
                break

        if idx >= 0:
            del self.favourites[idx]
            action = "removed"
        else:
            self.favourites.append({'package': package, 'channel': channel})
            action = "added"

        self.save_settings()
        return action

    def get_containing_lists(self, pkg, channel):
        pkg_id = self._get_pkg_id(pkg)
        containing = []
        for list_name, items in self.saved_lists.items():
            for item in items:
                if self._get_pkg_id(item['package']) == pkg_id and item['channel'] == channel:
                    containing.append(list_name)
                    break
        return containing

    def toggle_pkg_in_list(self, list_name, pkg, channel):
        if list_name not in self.saved_lists:
            return
        pkg_id = self._get_pkg_id(pkg)
        items = self.saved_lists[list_name]
        idx = -1
        for i, item in enumerate(items):
             if self._get_pkg_id(item['package']) == pkg_id and item['channel'] == channel:
                 idx = i
                 break
        if idx >= 0:
            del items[idx]
            msg = f"Removed from {list_name}"
        else:
            items.append({'package': pkg, 'channel': channel})
            msg = f"Added to {list_name}"
        self.saved_lists[list_name] = items
        self.save_settings()
        return msg

    def get_base_color(self):
        return ft.Colors.WHITE if self.theme_mode == "dark" else ft.Colors.BLACK

state = AppState()

# --- Logic: Search ---

def execute_nix_search(query, channel):
    if not query:
        return []

    limit_val = str(state.search_limit)

    command = [
        "nix", "run", "nixpkgs#nh", "--",
        "search", "--channel", channel, "-j", "--limit", limit_val, query
    ]

    try:
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        data = json.loads(result.stdout)
        raw_results = data.get("results", [])

        seen = set()
        unique_results = []
        for pkg in raw_results:
            sig = (pkg.get("package_pname"), pkg.get("package_pversion"))
            if sig not in seen:
                seen.add(sig)
                unique_results.append(pkg)

        return unique_results
    except subprocess.CalledProcessError as e:
        print(f"Nix Search Failed: {e.stderr}")
        return [{"error": str(e.stderr)}]
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Execution Error: {e}")
        return [{"error": f"Execution Error: {str(e)}"}]

# --- Custom Controls ---

class GlassContainer(ft.Container):
    def __init__(self, content, opacity=0.1, blur_sigma=10, border_radius=None, **kwargs):
        bg_color = kwargs.pop("bgcolor", None)
        if bg_color is None:
             base = state.get_base_color()
             bg_color = ft.Colors.with_opacity(opacity, base)
        if "border" not in kwargs:
            border_col = ft.Colors.with_opacity(0.2, state.get_base_color())
            kwargs["border"] = ft.border.all(1, border_col)
        if border_radius is None:
            border_radius = state.get_radius('card')
        super().__init__(
            content=content,
            bgcolor=bg_color,
            blur=ft.Blur(blur_sigma, blur_sigma, ft.BlurTileMode.MIRROR),
            border_radius=border_radius,
            shadow=ft.BoxShadow(
                spread_radius=1,
                blur_radius=15,
                color=ft.Colors.with_opacity(0.1, ft.Colors.BLACK),
            ),
            **kwargs
        )

class HoverLink(ft.Container):
    def __init__(self, icon, text, url, color_group, text_size=None):
        base_col = state.get_base_color()
        if text_size is None:
            text_size = state.get_font_size('small')
        super().__init__(
            content=ft.Row([ft.Icon(icon, size=text_size+2, color=color_group[0]), ft.Text(text, size=text_size, color=color_group[1])], spacing=5, alignment=ft.MainAxisAlignment.START),
            on_click=lambda _: os.system(f"xdg-open {url}") if url else None,
            on_hover=self.on_hover,
            tooltip=url,
            ink=True,
            border_radius=state.get_radius('chip'),
            padding=ft.padding.symmetric(horizontal=8, vertical=4),
            bgcolor=ft.Colors.with_opacity(0.1, base_col),
            border=ft.border.all(1, ft.Colors.with_opacity(0.2, base_col))
        )
        self.target_url = url
        self.text_control = self.content.controls[1]

    def on_hover(self, e):
        is_hovering = e.data == "true"
        self.text_control.decoration = ft.TextDecoration.UNDERLINE if is_hovering else ft.TextDecoration.NONE
        self.text_control.update()

class UndoToast(ft.Container):
    def __init__(self, message, on_undo, duration_seconds=5, on_timeout=None):
        self.duration_seconds = duration_seconds
        self.on_undo = on_undo
        self.on_timeout = on_timeout
        self.cancelled = False
        text_sz = state.get_font_size('body')
        self.counter_text = ft.Text(str(duration_seconds), size=text_sz*0.85, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE)
        self.progress_ring = ft.ProgressRing(value=1.0, stroke_width=3, color=ft.Colors.WHITE, width=24, height=24)

        content = ft.Row(
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                ft.Row(
                    spacing=15,
                    controls=[
                        ft.Stack([
                            self.progress_ring,
                            ft.Container(content=self.counter_text, alignment=ft.alignment.center, width=24, height=24)
                        ]),
                        ft.Text(message, color=ft.Colors.WHITE, weight=ft.FontWeight.W_500, size=text_sz)
                    ]
                ),
                ft.TextButton(
                    content=ft.Row([ft.Icon(ft.Icons.UNDO, size=text_sz*1.2), ft.Text("UNDO", weight=ft.FontWeight.BOLD, size=text_sz)], spacing=5),
                    style=ft.ButtonStyle(color=ft.Colors.BLUE_200),
                    on_click=self.handle_undo
                )
            ]
        )
        super().__init__(
            content=content,
            bgcolor=ft.Colors.with_opacity(0.95, "#1a202c"),
            padding=ft.padding.symmetric(horizontal=20, vertical=12),
            border_radius=30,
            shadow=ft.BoxShadow(blur_radius=15, color=ft.Colors.with_opacity(0.5, ft.Colors.BLACK), offset=ft.Offset(0, 5)),
            margin=ft.margin.only(bottom=20),
            width=380,
            animate_opacity=300,
        )

    def did_mount(self):
        threading.Thread(target=self.run_timer, daemon=True).start()

    def run_timer(self):
        step = 0.1
        total_steps = int(self.duration_seconds / step)
        for i in range(total_steps):
            if self.cancelled: return
            time.sleep(step)
            remaining = self.duration_seconds - (i * step)
            self.progress_ring.value = remaining / self.duration_seconds
            self.counter_text.value = str(int(remaining) + 1)
            self.update()
        if not self.cancelled:
            self.progress_ring.value = 0
            self.counter_text.value = "0"
            self.update()
            time.sleep(0.5)
            if self.on_timeout:
                self.on_timeout()

    def handle_undo(self, e):
        self.cancelled = True
        if self.on_undo:
            self.on_undo()

class AutoCarousel(ft.Container):
    def __init__(self, data_list):
        super().__init__(
            width=220, height=120,
            border_radius=15,
            animate_opacity=300,
            on_hover=self.handle_hover
        )
        self.data_list = data_list
        self.current_index = 0
        self.running = False
        self.paused = False

        # UI Components
        self.title_text = ft.Text("", weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE)
        self.desc_text = ft.Text("", size=12, color=ft.Colors.WHITE70)

        # Border Containers for "Snaking" timer effect
        self.bar_thickness = 3
        self.border_bottom = ft.Container(bgcolor="white", height=self.bar_thickness, width=0, bottom=0, left=0)
        self.border_right = ft.Container(bgcolor="white", width=self.bar_thickness, height=0, bottom=0, right=0)
        self.border_top = ft.Container(bgcolor="white", height=self.bar_thickness, width=0, top=0, right=0)
        self.border_left = ft.Container(bgcolor="white", width=self.bar_thickness, height=0, top=0, left=0)

        self.content_container = ft.Container(
            padding=15,
            expand=True,
            content=ft.Column(
                [self.title_text, self.desc_text],
                spacing=5,
                alignment=ft.MainAxisAlignment.CENTER
            )
        )

        self.content = ft.Stack(
            controls=[
                self.content_container,
                self.border_bottom,
                self.border_right,
                self.border_top,
                self.border_left
            ]
        )

        self.update_content()

    def update_content(self):
        item = self.data_list[self.current_index]

        # Glassmorphism Logic
        if state.carousel_glass:
            self.bgcolor = ft.Colors.with_opacity(0.6, item["color"])
            self.blur = ft.Blur(15, 15, ft.BlurTileMode.MIRROR)
            self.border = ft.border.all(1, ft.Colors.with_opacity(0.3, ft.Colors.WHITE))
        else:
            self.bgcolor = item["color"]
            self.blur = None
            self.border = None

        self.title_text.value = item["title"]
        self.desc_text.value = item["desc"]
        if self.page: self.update()

    def did_mount(self):
        self.running = True
        threading.Thread(target=self.loop, daemon=True).start()

    def will_unmount(self):
        self.running = False

    def handle_hover(self, e):
        if e.data == "true": # Enter hover
            self.paused = True
            # Reset bars to full
            self.set_bars_progress(1.0)
            self.update_content() # Ensure style matches
        else: # Exit hover
            self.paused = False
            # Thread continues from top loop logic (resets)

    def set_bars_progress(self, progress):
        # Progress goes from 1.0 (Full) to 0.0 (Empty)
        # Sequence of vanishing: Bottom-Left -> Bottom-Right -> Top-Right -> Top-Left -> Bottom-Left
        # 1. Bottom Bar shrinks (1.0 -> 0.75)
        # 2. Right Bar shrinks (0.75 -> 0.50)
        # 3. Top Bar shrinks (0.50 -> 0.25)
        # 4. Left Bar shrinks (0.25 -> 0.0)

        w_total = 220 # Approximate width
        h_total = 120 # Approximate height

        # Bottom Bar Logic (0 to 0.25 progress chunk, mapped 0-1)
        if progress > 0.75:
            p = (progress - 0.75) * 4
            self.border_bottom.width = w_total * p
            self.border_right.height = h_total
            self.border_top.width = w_total
            self.border_left.height = h_total
        elif progress > 0.5:
            p = (progress - 0.5) * 4
            self.border_bottom.width = 0
            self.border_right.height = h_total * p
            self.border_top.width = w_total
            self.border_left.height = h_total
        elif progress > 0.25:
            p = (progress - 0.25) * 4
            self.border_bottom.width = 0
            self.border_right.height = 0
            self.border_top.width = w_total * p
            self.border_left.height = h_total
        else:
            p = progress * 4
            self.border_bottom.width = 0
            self.border_right.height = 0
            self.border_top.width = 0
            self.border_left.height = h_total * p

        if self.page:
            self.border_bottom.update()
            self.border_right.update()
            self.border_top.update()
            self.border_left.update()

    def loop(self):
        step = 0.05
        while self.running:
            if self.paused:
                time.sleep(0.1)
                continue

            duration = max(1, state.carousel_timer)
            steps_total = int(duration / step)

            # Start fresh cycle
            self.set_bars_progress(1.0)

            for i in range(steps_total):
                if not self.running: return
                if self.paused: break # Exit loop to restart logic or wait

                time.sleep(step)
                progress = 1.0 - ((i + 1) / steps_total)
                self.set_bars_progress(progress)

            if self.paused: continue # Don't switch if paused mid-way

            # Switch Item
            self.current_index = (self.current_index + 1) % len(self.data_list)
            self.update_content()

show_toast_global = None
show_undo_toast_global = None

class NixPackageCard(GlassContainer):
    def __init__(self, package_data, page_ref, initial_channel, on_cart_change=None, is_cart_view=False, show_toast_callback=None, on_menu_open=None):
        self.pkg = package_data
        self.page_ref = page_ref
        self.on_cart_change = on_cart_change
        self.is_cart_view = is_cart_view
        self.show_toast = show_toast_callback
        self.on_menu_open = on_menu_open

        self.pname = self.pkg.get("package_pname", "Unknown")
        self.version = self.pkg.get("package_pversion", "?")
        description = self.pkg.get("package_description") or "No description available."
        homepage_list = self.pkg.get("package_homepage", [])
        homepage_url = homepage_list[0] if isinstance(homepage_list, list) and homepage_list else ""
        license_list = self.pkg.get("package_license_set", [])
        license_text = license_list[0] if isinstance(license_list, list) and license_list else "Unknown"

        self.programs_list = self.pkg.get("package_programs", [])
        programs_str = ", ".join(self.programs_list) if self.programs_list else None

        file_path = self.pkg.get("package_position", "").split(":")[0]
        source_url = f"https://github.com/NixOS/nixpkgs/blob/master/{file_path}" if file_path else ""
        self.attr_set = self.pkg.get("package_attr_set", "No package set")

        self.selected_channel = initial_channel
        self.run_mode = "direct"

        text_col = "onSurfaceVariant"
        size_norm = state.get_font_size('body')
        size_sm = state.get_font_size('small')
        size_lg = state.get_font_size('title')
        size_tag = state.get_font_size('small') * 0.9

        self.channel_text = ft.Text(f"{self.version} ({self.selected_channel})", size=size_sm, color=text_col)
        channel_menu_items = [ft.PopupMenuItem(text=ch, on_click=self.change_channel, data=ch) for ch in state.active_channels]

        border_col = ft.Colors.with_opacity(0.3, state.get_base_color())
        self.channel_selector = ft.Container(
            padding=ft.padding.symmetric(horizontal=8, vertical=4),
            border_radius=state.get_radius('selector'),
            border=ft.border.all(1, border_col),
            content=ft.Row(spacing=4, controls=[self.channel_text, ft.Icon(ft.Icons.ARROW_DROP_DOWN, color=text_col, size=size_sm)]),
        )
        self.channel_dropdown = ft.PopupMenuButton(content=self.channel_selector, items=channel_menu_items, tooltip="Select Channel")

        self.try_btn_icon = ft.Icon(ft.Icons.PLAY_ARROW, size=size_norm + 2, color=ft.Colors.WHITE)
        self.try_btn_text = ft.Text("Run without installing", weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE, size=size_norm)

        self.try_btn = ft.Container(
            padding=ft.padding.symmetric(horizontal=12, vertical=8),
            content=ft.Row(spacing=6, controls=[self.try_btn_icon, self.try_btn_text], alignment=ft.MainAxisAlignment.CENTER),
            on_click=lambda e: self.run_action(),
            bgcolor=ft.Colors.TRANSPARENT,
            ink=True,
            tooltip=""
        )

        self.copy_btn = ft.IconButton(
            icon=ft.Icons.CONTENT_COPY,
            icon_color=ft.Colors.WHITE70,
            tooltip="Copy Command",
            on_click=self.copy_command,
            icon_size=size_norm,
            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=0))
        )

        self.action_menu = ft.PopupMenuButton(
            icon=ft.Icons.ARROW_DROP_DOWN, icon_color=ft.Colors.WHITE70,
            items=[
                ft.PopupMenuItem(text="Run without installing", icon=ft.Icons.PLAY_ARROW, on_click=lambda e: self.set_mode_and_update_ui("direct")),
                ft.PopupMenuItem(text="Try in a shell", icon=ft.Icons.TERMINAL, on_click=lambda e: self.set_mode_and_update_ui("shell")),
            ]
        )

        self.unified_action_bar = ft.Container(
            bgcolor=ft.Colors.BLUE_700,
            border_radius=state.get_radius('button'),
            content=ft.Row(spacing=0, controls=[
                self.try_btn,
                ft.Container(width=1, height=20, bgcolor=ft.Colors.WHITE24),
                self.action_menu,
                ft.Container(width=1, height=20, bgcolor=ft.Colors.WHITE24),
                self.copy_btn,
            ])
        )

        self.cart_btn = ft.IconButton(
            on_click=self.handle_cart_click,
            tooltip="Add/Remove Cart",
            icon_size=size_norm + 4
        )
        self.update_cart_btn_state()

        self.list_badge_count = ft.Text("0", size=size_tag, color=ft.Colors.WHITE, weight=ft.FontWeight.BOLD)
        self.list_badge = ft.Container(
            content=self.list_badge_count,
            bgcolor=ft.Colors.RED_500, width=size_sm, height=size_sm, border_radius=size_sm/2,
            alignment=ft.alignment.center, visible=False
        )

        self.lists_btn = ft.GestureDetector(
            mouse_cursor=ft.MouseCursor.CLICK,
            on_tap_up=self.trigger_global_menu,
            content=ft.Container(
                bgcolor=ft.Colors.TRANSPARENT,
                padding=8,
                border_radius=50,
                content=ft.Icon(ft.Icons.PLAYLIST_ADD, size=size_norm + 4, color="onSurface"),
            )
        )

        self.lists_btn_container = ft.Container(
            content=ft.Stack([
                self.lists_btn,
                ft.Container(content=self.list_badge, top=2, right=2)
            ]),
        )
        self.refresh_lists_state()

        self.fav_btn = ft.IconButton(
            icon=ft.Icons.FAVORITE_BORDER,
            icon_color="onSurface",
            selected_icon=ft.Icons.FAVORITE,
            selected_icon_color=ft.Colors.RED_500,
            on_click=self.toggle_favourite,
            tooltip="Toggle Favourite",
            icon_size=size_norm + 4
        )
        self.update_fav_btn_state()

        tag_color = ft.Colors.BLUE_GREY_700 if self.attr_set == "No package set" else ft.Colors.TEAL_700
        self.tag_chip = ft.Container(
            padding=ft.padding.symmetric(horizontal=6, vertical=2),
            border_radius=state.get_radius('chip'),
            bgcolor=ft.Colors.with_opacity(0.5, tag_color),
            content=ft.Text(self.attr_set, size=size_tag, color=ft.Colors.WHITE, weight=ft.FontWeight.BOLD),
            visible=bool(self.attr_set)
        )

        footer_size = size_sm

        def create_footer_chip(icon, text, color_group):
            chip_bg = ft.Colors.with_opacity(0.08, color_group[0])
            return ft.Container(
                content=ft.Row([ft.Icon(icon, size=footer_size+2, color=color_group[0]), ft.Text(text, size=footer_size, color=color_group[1])], spacing=5),
                border_radius=state.get_radius('chip'),
                padding=ft.padding.symmetric(horizontal=8, vertical=4),
                bgcolor=chip_bg,
            )

        footer_items = [
            create_footer_chip(ft.Icons.VERIFIED_USER_OUTLINED, license_text, (ft.Colors.GREEN, ft.Colors.GREEN))
        ]
        if programs_str:
            footer_items.append(create_footer_chip(ft.Icons.TERMINAL, f"Bins: {programs_str}", (ft.Colors.ORANGE, ft.Colors.ORANGE)))
        if homepage_url:
            footer_items.append(HoverLink(ft.Icons.LINK, "Homepage", homepage_url, (ft.Colors.BLUE, ft.Colors.BLUE), text_size=footer_size))
        if source_url:
            footer_items.append(HoverLink(ft.Icons.CODE, "Source", source_url, (ft.Colors.PURPLE_200, ft.Colors.PURPLE_200), text_size=footer_size))

        content = ft.Column(
            spacing=4,
            controls=[
                ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    controls=[
                        ft.Column(spacing=2, controls=[
                            ft.Row([
                                ft.Text(self.pname, weight=ft.FontWeight.BOLD, size=size_lg, color="onSurface"),
                                self.tag_chip
                            ]),
                        ]),
                        ft.Row(spacing=5, controls=[
                            self.channel_dropdown,
                            self.unified_action_bar,
                            self.lists_btn_container,
                            self.fav_btn,
                            self.cart_btn
                        ])
                    ]
                ),
                ft.Container(content=ft.Text(description, size=size_norm, color="onSurfaceVariant", no_wrap=False, max_lines=2, overflow=ft.TextOverflow.ELLIPSIS), padding=ft.padding.only(bottom=5)),
                ft.Container(
                    bgcolor=ft.Colors.with_opacity(0.05, state.get_base_color()),
                    border_radius=state.get_radius('footer'),
                    padding=4,
                    content=ft.Row(wrap=False, scroll=ft.ScrollMode.HIDDEN, controls=footer_items, spacing=10)
                )
            ]
        )
        super().__init__(content=content, padding=12, opacity=0.15, border_radius=state.get_radius('card'))
        self.update_copy_tooltip()

    def refresh_lists_state(self):
        containing_lists = state.get_containing_lists(self.pkg, self.selected_channel)
        count = len(containing_lists)
        self.list_badge_count.value = str(count)
        self.list_badge.visible = count > 0
        if self.list_badge.page: self.list_badge.update()

    def trigger_global_menu(self, e):
        if global_open_menu_func:
            global_open_menu_func(e, self.pkg, self.selected_channel, self.refresh_lists_state)

    def update_cart_btn_state(self):
        in_cart = state.is_in_cart(self.pkg, self.selected_channel)
        if in_cart:
            self.cart_btn.icon = ft.Icons.REMOVE_SHOPPING_CART
            self.cart_btn.icon_color = ft.Colors.RED_400
            self.cart_btn.tooltip = "Remove from Cart"
        else:
            self.cart_btn.icon = ft.Icons.ADD_SHOPPING_CART
            self.cart_btn.icon_color = ft.Colors.GREEN
            self.cart_btn.tooltip = "Add to Cart"
        if self.cart_btn.page:
            self.cart_btn.update()

    def update_fav_btn_state(self):
        is_fav = state.is_favourite(self.pkg, self.selected_channel)
        self.fav_btn.selected = is_fav
        if self.fav_btn.page:
            self.fav_btn.update()

    def toggle_favourite(self, e):
        state.add_to_history(self.pkg, self.selected_channel)
        action = state.toggle_favourite(self.pkg, self.selected_channel)
        self.update_fav_btn_state()

        if action == "removed":
            if self.on_cart_change: self.on_cart_change()
            def on_undo():
                state.toggle_favourite(self.pkg, self.selected_channel)
                self.update_fav_btn_state()
                if self.on_cart_change: self.on_cart_change()

            if show_undo_toast_global:
                show_undo_toast_global("Removed from favourites", on_undo)
        else:
            if self.show_toast: self.show_toast("Added to favourites")

    def handle_cart_click(self, e):
        state.add_to_history(self.pkg, self.selected_channel)
        in_cart = state.is_in_cart(self.pkg, self.selected_channel)
        action_type = "remove" if in_cart else "add"
        msg = ""
        if action_type == "add":
            state.add_to_cart(self.pkg, self.selected_channel)
            msg = f"Added {self.pname} to cart"
        else:
            state.remove_from_cart(self.pkg, self.selected_channel)
            msg = f"Removed {self.pname} from cart"

        if self.show_toast: self.show_toast(msg)
        self.update_cart_btn_state()
        if self.on_cart_change: self.on_cart_change()

    def change_channel(self, e):
        new_channel = e.control.data
        if new_channel == self.selected_channel: return
        self.channel_text.value = f"Fetching..."
        self.channel_text.update()
        try:
            results = execute_nix_search(self.pname, new_channel)
            new_version = "?"
            if results and "error" in results[0]:
                 self.channel_text.value = "Error"
            else:
                for r in results:
                    if r.get("package_pname") == self.pname:
                        new_version = r.get("package_pversion", "?")
                        break
                else:
                    if results: new_version = results[0].get("package_pversion", "?")
                self.version = new_version
                self.channel_text.value = f"{self.version} ({self.selected_channel})"

            self.selected_channel = new_channel
            self.channel_text.update()
            self.update_cart_btn_state()
            self.update_fav_btn_state()
            self.refresh_lists_state()
            self.update_copy_tooltip()
        except Exception as ex:
            self.channel_text.value = "Error"
            self.channel_text.update()

    def set_mode_and_update_ui(self, mode):
        self.run_mode = mode
        if mode == "direct":
            self.try_btn_text.value = "Run without installing"
            self.try_btn_icon.name = ft.Icons.PLAY_ARROW
        elif mode == "shell":
            self.try_btn_text.value = "Try in a shell"
            self.try_btn_icon.name = ft.Icons.TERMINAL
        self.try_btn_text.update()
        self.try_btn_icon.update()
        self.update_copy_tooltip()

    def _generate_nix_command(self, with_wrapper=True):
        target = f"nixpkgs/{self.selected_channel}#{self.pname}"
        core_cmd = ""
        if self.run_mode == "direct":
            core_cmd = f"nix run {target}"
        elif self.run_mode == "shell":
            core_cmd = f"nix shell {target}"

        if with_wrapper:
            prefix = state.shell_single_prefix.strip()
            suffix = state.shell_single_suffix.strip()
            return f"{prefix} {core_cmd} {suffix}".strip()

        return core_cmd

    def update_copy_tooltip(self):
        self.copy_btn.tooltip = self._generate_nix_command(with_wrapper=False)
        self.try_btn.tooltip = self._generate_nix_command(with_wrapper=True)
        if self.copy_btn.page: self.copy_btn.update()
        if self.try_btn.page: self.try_btn.update()

    def copy_command(self, e):
        state.add_to_history(self.pkg, self.selected_channel)
        cmd = self._generate_nix_command(with_wrapper=False)
        self.page_ref.set_clipboard(cmd)
        if self.show_toast: self.show_toast(f"Copied: {cmd}")

    def run_action(self):
        state.add_to_history(self.pkg, self.selected_channel)
        display_cmd = self._generate_nix_command(with_wrapper=True)
        cmd_list = shlex.split(display_cmd)

        output_text = ft.Text("Launching process...", font_family="monospace", size=12)
        dlg = ft.AlertDialog(
            title=ft.Text(f"Launching: {self.run_mode.capitalize()}"),
            content=ft.Container(width=500, height=150, content=ft.Column([ft.Text(f"Command: {display_cmd}", color=ft.Colors.BLUE_200, size=12, selectable=True), ft.Divider(), ft.Column([output_text], scroll=ft.ScrollMode.AUTO, expand=True)])),
            actions=[ft.TextButton("Close", on_click=lambda e: self.page_ref.close(dlg))]
        )
        self.page_ref.open(dlg)
        self.page_ref.update()

        try:
            subprocess.Popen(cmd_list, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
            output_text.value = "Process started.\nYou can close this dialog."
            self.page_ref.update()
        except Exception as ex:
            output_text.value = f"Error executing command:\n{str(ex)}"
            self.page_ref.update()

# --- Main Application ---

def main(page: ft.Page):
    page.title = APP_NAME
    page.theme_mode = ft.ThemeMode.DARK if state.theme_mode == "dark" else (ft.ThemeMode.LIGHT if state.theme_mode == "light" else ft.ThemeMode.SYSTEM)
    page.theme = ft.Theme(color_scheme_seed=state.theme_color)
    page.padding = 0
    page.window_width = 400
    page.window_height = 800

    current_results = []
    active_filters = set()
    pending_filters = set()

    settings_ui_state = {
        "expanded_tile": None,
        "selected_category": "appearance",
        "scroll_offset": 0
    }

    settings_scroll_ref = ft.Ref()
    settings_refresh_ref = [None]

    settings_main_column = ft.Column(
        scroll=ft.ScrollMode.HIDDEN,
        expand=True,
        ref=settings_scroll_ref,
        on_scroll=lambda e: settings_ui_state.update({"scroll_offset": e.pixels}),
        on_scroll_interval=10,
    )

    global_menu_card = ft.Container(
        visible=False,
        bgcolor="#252525",
        border_radius=12,
        padding=10,
        width=200,
        top=0, left=0,
        border=ft.border.all(1, ft.Colors.with_opacity(0.2, ft.Colors.WHITE)),
        shadow=ft.BoxShadow(
            spread_radius=1, blur_radius=10,
            color=ft.Colors.with_opacity(0.5, ft.Colors.BLACK), offset=ft.Offset(0, 5)
        ),
        content=ft.Column(spacing=5, tight=True, scroll=ft.ScrollMode.AUTO),
        animate_opacity=150,
        opacity=0
    )

    global_dismiss_layer = ft.Container(
        expand=True,
        bgcolor=ft.Colors.TRANSPARENT,
        visible=False,
        on_click=lambda e: close_global_menu()
    )

    def close_global_menu():
        global_menu_card.opacity = 0
        global_menu_card.visible = False
        global_dismiss_layer.visible = False
        page.update()

    def open_global_menu(e, pkg, channel, refresh_callback):
        menu_x = e.global_x - 180
        menu_y = e.global_y + 10
        if menu_x < 10: menu_x = 10
        if menu_y + 200 > page.height: menu_y = page.height - 210
        global_menu_card.left = menu_x
        global_menu_card.top = menu_y

        content_col = global_menu_card.content
        content_col.controls.clear()

        if not state.saved_lists:
            content_col.controls.append(
                ft.Container(
                    content=ft.Text("No lists created yet.\nCreate one in Cart.", size=12, color=ft.Colors.GREY_400, text_align=ft.TextAlign.CENTER),
                    padding=10,
                    alignment=ft.alignment.center
                )
            )
            global_menu_card.height = 60
        else:
            containing_lists = state.get_containing_lists(pkg, channel)
            sorted_lists = sorted(state.saved_lists.keys(), key=str.lower)

            def on_checkbox_change(e):
                list_name = e.control.label
                state.toggle_pkg_in_list(list_name, pkg, channel)
                if refresh_callback: refresh_callback()

            for list_name in sorted_lists:
                is_checked = list_name in containing_lists
                row = ft.Container(
                    padding=ft.padding.symmetric(vertical=4, horizontal=8),
                    border_radius=5,
                    content=ft.Checkbox(
                        label=list_name,
                        value=is_checked,
                        on_change=on_checkbox_change,
                        label_style=ft.TextStyle(size=14, color="white"),
                        check_color=ft.Colors.WHITE,
                        fill_color={
                            ft.ControlState.HOVERED: ft.Colors.BLUE_400,
                            ft.ControlState.SELECTED: ft.Colors.BLUE_600,
                            ft.ControlState.DEFAULT: ft.Colors.TRANSPARENT,
                        }
                    )
                )
                content_col.controls.append(row)

            calculated_height = (len(sorted_lists) * 45) + 20
            global_menu_card.height = min(300, calculated_height)

        global_dismiss_layer.visible = True
        global_menu_card.visible = True
        global_menu_card.opacity = 1
        page.update()

    global global_open_menu_func
    global_open_menu_func = open_global_menu

    toast_overlay_container = ft.Container(bottom=90, left=0, right=0, alignment=ft.alignment.center, visible=False)
    current_toast_token = [0]

    def show_toast(message):
        current_toast_token[0] += 1
        my_token = current_toast_token[0]
        t_text = ft.Text(message, color=ft.Colors.WHITE, weight=ft.FontWeight.BOLD)
        t_container = ft.Container(
            content=t_text,
            bgcolor=ft.Colors.with_opacity(0.9, "#2D3748"),
            padding=ft.padding.symmetric(horizontal=16, vertical=10),
            border_radius=25,
            shadow=ft.BoxShadow(blur_radius=10, color=ft.Colors.with_opacity(0.3, ft.Colors.BLACK), offset=ft.Offset(0, 5)),
            opacity=0,
            animate_opacity=300,
            alignment=ft.alignment.center,
        )
        toast_overlay_container.content = t_container
        toast_overlay_container.visible = True
        page.update()
        t_container.opacity = 1
        t_container.update()

        def hide():
            time.sleep(2.0)
            if current_toast_token[0] != my_token: return
            t_container.opacity = 0
            page.update()
            time.sleep(0.3)
            if current_toast_token[0] != my_token: return
            toast_overlay_container.visible = False
            page.update()
        threading.Thread(target=hide, daemon=True).start()

    def show_undo_toast(message, on_undo):
        current_toast_token[0] += 1
        my_token = current_toast_token[0]
        undo_duration = state.undo_timer
        def on_timeout():
            if current_toast_token[0] == my_token:
                toast_overlay_container.visible = False
                page.update()

        def wrapped_undo():
            on_undo()
            if current_toast_token[0] == my_token:
                toast_overlay_container.visible = False
                page.update()

        undo_control = UndoToast(message, on_undo=wrapped_undo, duration_seconds=undo_duration, on_timeout=on_timeout)
        toast_overlay_container.content = undo_control
        toast_overlay_container.visible = True
        page.update()

    global show_toast_global
    global show_undo_toast_global
    show_toast_global = show_toast
    show_undo_toast_global = show_undo_toast

    def show_destructive_dialog(title, content_text, on_confirm):
        duration = state.confirm_timer
        confirm_btn = ft.ElevatedButton(f"Yes ({duration}s)", bgcolor=ft.Colors.GREY_700, color=ft.Colors.WHITE70, disabled=True)
        cancel_btn = ft.OutlinedButton("No")
        dlg = ft.AlertDialog(
            title=ft.Text(title),
            content=ft.Text(content_text),
            actions=[confirm_btn, cancel_btn],
            actions_alignment=ft.MainAxisAlignment.END
        )

        def close_dlg(e):
            page.close(dlg)

        def handle_confirm(e):
            page.close(dlg)
            on_confirm(e)

        cancel_btn.on_click = close_dlg
        def timer_logic():
            for i in range(duration, 0, -1):
                if not dlg.open: return
                confirm_btn.text = f"Yes ({i}s)"
                confirm_btn.update()
                time.sleep(1)

            if dlg.open:
                confirm_btn.text = "Yes"
                confirm_btn.disabled = False
                confirm_btn.bgcolor = ft.Colors.RED_700
                confirm_btn.color = ft.Colors.WHITE
                confirm_btn.on_click = handle_confirm
                confirm_btn.update()

        page.open(dlg)
        threading.Thread(target=timer_logic, daemon=True).start()

    results_column = ft.Column(spacing=10, scroll=ft.ScrollMode.HIDDEN, expand=True)

    cart_list = ft.Column(spacing=10, scroll=ft.ScrollMode.HIDDEN, expand=True)
    cart_header_title = ft.Text("Your Cart (0 items)", size=24, weight=ft.FontWeight.W_900, color="onSurface")
    cart_header_save_btn = ft.ElevatedButton("Save cart as list", icon=ft.Icons.ADD, bgcolor=ft.Colors.TEAL_700, color=ft.Colors.WHITE)
    cart_header_clear_btn = ft.IconButton(ft.Icons.DELETE_SWEEP, tooltip="Clear Cart", icon_color=ft.Colors.RED_400)
    cart_header_shell_btn_container = ft.Container(
        padding=ft.padding.symmetric(horizontal=12, vertical=8),
        content=ft.Row(spacing=6, controls=[ft.Icon(ft.Icons.TERMINAL, size=16, color=ft.Colors.WHITE), ft.Text("Try Cart in Shell", weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE, size=12)]),
        ink=True
    )
    cart_header_copy_btn = ft.IconButton(ft.Icons.CONTENT_COPY, icon_color=ft.Colors.WHITE70, tooltip="Copy Command", icon_size=16, style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=0)))
    cart_header_shell_btn = ft.Container(
        bgcolor=ft.Colors.BLUE_600, border_radius=8,
        content=ft.Row(spacing=0, controls=[
            cart_header_shell_btn_container,
            ft.Container(width=1, height=20, bgcolor=ft.Colors.WHITE24),
            cart_header_copy_btn
        ])
    )
    cart_header = ft.Container(
        padding=ft.padding.only(bottom=10, top=10),
        content=ft.Row(
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            controls=[
                cart_header_title,
                ft.Row(controls=[cart_header_save_btn, cart_header_clear_btn, cart_header_shell_btn])
            ]
        )
    )

    result_count_text = ft.Text("", size=12, color="onSurfaceVariant", visible=False)
    channel_dropdown = ft.Dropdown(
        width=160, text_size=12, border_color=ft.Colors.TRANSPARENT, bgcolor="surfaceVariant",
        value=state.default_channel if state.default_channel in state.active_channels else (state.active_channels[0] if state.active_channels else ""),
        options=[ft.dropdown.Option(c) for c in state.active_channels],
        content_padding=10, filled=True,
    )
    search_field = ft.TextField(
        hint_text="Search packages...", border=ft.InputBorder.NONE,
        hint_style=ft.TextStyle(color="onSurfaceVariant"), text_style=ft.TextStyle(color="onSurface"), expand=True,
    )
    search_icon_btn = ft.IconButton(icon=ft.Icons.SEARCH, on_click=lambda e: perform_search(e))
    filter_badge_count = ft.Text("0", size=10, color=ft.Colors.WHITE, weight=ft.FontWeight.BOLD)
    filter_badge_container = ft.Container(content=filter_badge_count, bgcolor=ft.Colors.RED_500, width=16, height=16, border_radius=8, alignment=ft.alignment.center, visible=False, top=0, right=0)
    badge_size_val = state.nav_badge_size
    cart_badge_count = ft.Text(str(len(state.cart_items)), size=max(8, badge_size_val/2), color=ft.Colors.WHITE, weight=ft.FontWeight.BOLD, text_align=ft.TextAlign.CENTER)
    cart_badge_container = ft.Container(
        content=cart_badge_count,
        bgcolor=ft.Colors.RED_500,
        width=badge_size_val, height=badge_size_val, border_radius=badge_size_val/2,
        alignment=ft.alignment.center,
        visible=len(state.cart_items) > 0,
        top=2, right=2
    )

    filter_dismiss_layer = ft.Container(expand=True, visible=False, bgcolor=ft.Colors.with_opacity(0.01, ft.Colors.BLACK))
    filter_list_col = ft.Column(scroll=ft.ScrollMode.AUTO)
    filter_menu = GlassContainer(visible=False, width=300, height=350, top=60, right=50, padding=15, border=ft.border.all(1, "outline"), content=ft.Column([ft.Text("Filter by Package Set", weight=ft.FontWeight.BOLD, size=16, color="onSurface"), ft.Divider(height=10, color="outline"), ft.Container(expand=True, content=filter_list_col), ft.Row(alignment=ft.MainAxisAlignment.END, controls=[ft.TextButton("Close"), ft.ElevatedButton("Apply")])]))

    selected_list_name = None
    is_viewing_favourites = False
    lists_main_col = ft.Column(scroll=ft.ScrollMode.HIDDEN, expand=True)
    list_detail_col = ft.Column(scroll=ft.ScrollMode.HIDDEN, expand=True)
    lists_badge_count = ft.Text(str(len(state.saved_lists)), size=max(8, badge_size_val/2), color=ft.Colors.WHITE, weight=ft.FontWeight.BOLD, text_align=ft.TextAlign.CENTER)
    lists_badge_container = ft.Container(
        content=lists_badge_count,
        bgcolor=ft.Colors.RED_500,
        width=badge_size_val, height=badge_size_val, border_radius=badge_size_val/2,
        alignment=ft.alignment.center,
        visible=len(state.saved_lists) > 0,
        top=2, right=2
    )

    def update_lists_badge():
        count = len(state.saved_lists)
        lists_badge_count.value = str(count)
        if lists_badge_container.page:
            lists_badge_container.visible = count > 0
            lists_badge_container.update()

    def update_badges_style():
        sz = state.nav_badge_size
        radius = sz / 2
        font_sz = max(8, sz / 2)

        cart_badge_container.width = sz
        cart_badge_container.height = sz
        cart_badge_container.border_radius = radius
        cart_badge_count.size = font_sz

        lists_badge_container.width = sz
        lists_badge_container.height = sz
        lists_badge_container.border_radius = radius
        lists_badge_count.size = font_sz

        if cart_badge_container.page: cart_badge_container.update()
        if lists_badge_container.page: lists_badge_container.update()

    def _build_shell_command_for_items(items, with_wrapper=True):
        prefix = state.shell_cart_prefix.strip()
        suffix = state.shell_cart_suffix.strip()

        nix_pkgs_args = []
        for item in items:
            pkg = item['package']
            channel = item['channel']
            nix_pkgs_args.append(f"nixpkgs/{channel}#{pkg.get('package_pname')}")

        nix_args_str = " ".join(nix_pkgs_args)
        nix_cmd = f"nix shell {nix_args_str}"

        if with_wrapper:
            return f"{prefix} {nix_cmd} {suffix}".strip()
        else:
            return nix_cmd

    def run_cart_shell(e):
        if not state.cart_items: return
        display_cmd = _build_shell_command_for_items(state.cart_items, with_wrapper=True)
        _launch_shell_dialog(display_cmd, "Cart Shell")

    def run_list_shell(e):
        items = []
        title = ""

        if is_viewing_favourites:
            items = state.favourites
            title = "Favourites"
        elif selected_list_name and selected_list_name in state.saved_lists:
            items = state.saved_lists[selected_list_name]

        if not items: return
        display_cmd = _build_shell_command_for_items(items, with_wrapper=True)
        _launch_shell_dialog(display_cmd, title)

    def _launch_shell_dialog(display_cmd, title):
        cmd_list = shlex.split(display_cmd)
        output_text = ft.Text("Launching process...", font_family="monospace", size=12)
        dlg = ft.AlertDialog(title=ft.Text(f"Launching {title}"), content=ft.Container(width=500, height=150, content=ft.Column([ft.Text(f"Command: {display_cmd}", color=ft.Colors.BLUE_200, size=12, selectable=True), ft.Divider(), ft.Column([output_text], scroll=ft.ScrollMode.AUTO, expand=True)])), actions=[ft.TextButton("Close", on_click=lambda e: page.close(dlg))])
        page.open(dlg)
        page.update()

        try:
            subprocess.Popen(cmd_list, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
            output_text.value = "Process started.\nYou can close this dialog."
            page.update()
        except Exception as ex:
            output_text.value = f"Error executing command:\n{str(ex)}"
            page.update()

    def copy_cart_command(e):
        if not state.cart_items: return
        cmd = _build_shell_command_for_items(state.cart_items, with_wrapper=False)
        page.set_clipboard(cmd)
        show_toast(f"Copied Cart Command")

    def copy_list_command(e):
        items = []
        if is_viewing_favourites:
            items = state.favourites
        elif selected_list_name and selected_list_name in state.saved_lists:
            items = state.saved_lists[selected_list_name]

        if not items: return
        tooltip_cmd = _build_shell_command_for_items(items, with_wrapper=True)
        clean_cmd = _build_shell_command_for_items(items, with_wrapper=False)

        page.set_clipboard(clean_cmd)
        show_toast(f"Copied List Command")

    def save_cart_as_list(e):
        if not state.cart_items:
            show_toast("Cart is empty")
            return

        list_name_input = ft.TextField(hint_text="List Name (e.g., dev-tools)", autofocus=True)
        dlg_ref = [None]

        def confirm_save(e):
            name = list_name_input.value.strip()
            if not name:
                show_toast("Please enter a name")
                return
            state.save_list(name, list(state.cart_items))
            update_lists_badge()
            show_toast(f"Saved list: {name}")
            page.close(dlg_ref[0])
            if cart_list.page: refresh_cart_view(update_ui=True)

        dlg = ft.AlertDialog(
            title=ft.Text("Save Cart as List"),
            content=list_name_input,
            actions=[
                ft.TextButton("Cancel", on_click=lambda e: page.close(dlg_ref[0])),
                ft.TextButton("Save", on_click=confirm_save),
            ]
        )
        dlg_ref[0] = dlg
        page.open(dlg)

    def clear_all_cart(e):
        if not state.cart_items: return
        backup_items = list(state.cart_items)
        def do_clear(e):
            state.clear_cart()
            on_global_cart_change()
            def on_undo():
                state.restore_cart(backup_items)
                on_global_cart_change()
            show_undo_toast("Cart cleared", on_undo)
        show_destructive_dialog("Clear Cart?", "Remove all items from cart?", do_clear)

    cart_header_save_btn.on_click = save_cart_as_list
    cart_header_clear_btn.on_click = clear_all_cart
    cart_header_shell_btn_container.on_click = run_cart_shell
    cart_header_copy_btn.on_click = copy_cart_command

    def update_cart_badge():
        count = len(state.cart_items)
        cart_badge_count.value = str(count)
        if cart_badge_container.page:
            cart_badge_container.visible = count > 0
            cart_badge_container.update()

    def on_global_cart_change():
        update_cart_badge()
        if cart_list.page: refresh_cart_view(update_ui=True)
        if list_detail_col.page: refresh_list_detail_view(update_ui=True)

    def refresh_cart_view(update_ui=False):
        total_items = len(state.cart_items)
        cart_header_title.value = f"Your Cart ({total_items} items)"
        if total_items > 0:
             cmd_clean = _build_shell_command_for_items(state.cart_items, with_wrapper=False)
             cmd_full = _build_shell_command_for_items(state.cart_items, with_wrapper=True)
             cart_header_copy_btn.tooltip = cmd_clean
             cart_header_shell_btn_container.tooltip = cmd_full
        else:
             cart_header_copy_btn.tooltip = "Cart is empty"
             cart_header_shell_btn_container.tooltip = ""

        cart_header_save_btn.disabled = (total_items == 0)
        cart_header_clear_btn.disabled = (total_items == 0)
        cart_header_shell_btn.border_radius = state.get_radius('button')

        cart_list.controls.clear()
        if not state.cart_items:
            cart_list.controls.append(ft.Container(content=ft.Text("Your cart is empty.", color="onSurface"), alignment=ft.alignment.center, padding=20))
        else:
            for item in state.cart_items:
                pkg_data = item['package']
                saved_channel = item['channel']
                cart_list.controls.append(NixPackageCard(pkg_data, page, saved_channel, on_cart_change=on_global_cart_change, is_cart_view=True, show_toast_callback=show_toast, on_menu_open=None))

        if update_ui:
            if cart_header.page: cart_header.update()
            if cart_list.page: cart_list.update()

    def refresh_dropdown_options():
        channel_dropdown.options = [ft.dropdown.Option(c) for c in state.active_channels]
        if state.default_channel in state.active_channels: channel_dropdown.value = state.default_channel
        elif state.active_channels: channel_dropdown.value = state.active_channels[0]
        if channel_dropdown.page: channel_dropdown.update()

    def update_results_list():
        results_column.controls.clear()
        if current_results and "error" in current_results[0]:
            error_msg = current_results[0]["error"]
            results_column.controls.append(ft.Container(content=ft.Column([ft.Icon(ft.Icons.ERROR_OUTLINE, color=ft.Colors.RED_400, size=40), ft.Text("Search Failed", color=ft.Colors.RED_400, weight=ft.FontWeight.BOLD), ft.Text(error_msg, color="onSurface", size=12, text_align=ft.TextAlign.CENTER)], horizontal_alignment=ft.CrossAxisAlignment.CENTER), alignment=ft.alignment.center, padding=20))
            result_count_text.value = "Error"
            if results_column.page: results_column.update()
            if result_count_text.page: result_count_text.update()
            return

        filtered_data = []
        if not active_filters:
            filtered_data = current_results
            result_count_text.value = f"Showing total {len(current_results)} results"
        else:
            filtered_data = [pkg for pkg in current_results if pkg.get("package_attr_set", "No package set") in active_filters]
            result_count_text.value = f"Showing {len(filtered_data)} filtered results from total {len(current_results)} results"

        result_count_text.visible = True
        filter_count = len(active_filters)
        filter_badge_count.value = str(filter_count)
        if filter_badge_container.page:
            filter_badge_container.visible = filter_count > 0
            filter_badge_container.update()
        if result_count_text.page: result_count_text.update()

        if not filtered_data:
             results_column.controls.append(ft.Container(content=ft.Text("No results found.", color="onSurface", text_align=ft.TextAlign.CENTER), alignment=ft.alignment.center, padding=20))
        else:
            for pkg in filtered_data:
                results_column.controls.append(NixPackageCard(pkg, page, channel_dropdown.value, on_cart_change=on_global_cart_change, show_toast_callback=show_toast, on_menu_open=None))
        if results_column.page: results_column.update()

    def perform_search(e):
        if results_column.page:
            results_column.controls = [ft.Container(content=ft.ProgressRing(color=ft.Colors.PURPLE_400), alignment=ft.alignment.center, padding=20)]
            results_column.update()
        if filter_menu.visible: toggle_filter_menu(False)
        query = search_field.value
        current_channel = channel_dropdown.value
        active_filters.clear()
        nonlocal current_results
        try:
            current_results = execute_nix_search(query, current_channel)
        finally:
            update_results_list()

    def toggle_filter_menu(visible):
        if visible:
            if not current_results or (current_results and "error" in current_results[0]):
                show_toast("No valid search results to filter.")
                return
            pending_filters.clear()
            pending_filters.update(active_filters)
            sets = [pkg.get("package_attr_set", "No package set") for pkg in current_results]
            counts = Counter(sets)
            filter_list_col.controls.clear()
            def on_check(e):
                val = e.control.data
                if e.control.value: pending_filters.add(val)
                elif val in pending_filters: pending_filters.remove(val)
            for attr_set, count in counts.most_common():
                filter_list_col.controls.append(ft.Checkbox(label=f"{attr_set} ({count})", value=(attr_set in pending_filters), on_change=on_check, data=attr_set))
        filter_menu.visible = visible
        filter_dismiss_layer.visible = visible
        filter_menu.update()
        if filter_dismiss_layer.page: filter_dismiss_layer.update()

    def apply_filters():
        active_filters.clear()
        active_filters.update(pending_filters)
        toggle_filter_menu(False)
        update_results_list()

    search_field.on_submit = perform_search
    filter_menu.content.controls[3].controls[0].on_click = lambda e: toggle_filter_menu(False)
    filter_menu.content.controls[3].controls[1].on_click = lambda e: apply_filters()
    filter_dismiss_layer.on_click = lambda e: toggle_filter_menu(False)

    def open_list_detail(list_name, is_fav=False):
        nonlocal selected_list_name
        nonlocal is_viewing_favourites
        selected_list_name = list_name
        is_viewing_favourites = is_fav
        content_area.content = get_lists_view()
        content_area.update()

    def go_back_to_lists_index(e):
        nonlocal selected_list_name
        nonlocal is_viewing_favourites
        selected_list_name = None
        is_viewing_favourites = False
        content_area.content = get_lists_view()
        content_area.update()

    def delete_saved_list(e):
        name = e.control.data
        backup_items = state.saved_lists.get(name, [])

        def do_delete(e):
            nonlocal selected_list_name
            state.delete_list(name)
            update_lists_badge()
            refresh_lists_main_view(update_ui=True)

            if selected_list_name == name:
                selected_list_name = None
                content_area.content = get_lists_view()
                content_area.update()

            def on_undo():
                state.restore_list(name, backup_items)
                update_lists_badge()
                refresh_lists_main_view(update_ui=True)

            show_undo_toast(f"Deleted: {name}", on_undo)

        show_destructive_dialog("Delete List?", f"Are you sure you want to delete '{name}'?", do_delete)

    def refresh_lists_main_view(update_ui=False):
        lists_main_col.controls.clear()
        fav_count = len(state.favourites)
        if fav_count > 0:
            pkgs_preview = ", ".join([i['package'].get('package_pname', '?') for i in state.favourites[:3]])
            if fav_count > 3: pkgs_preview += "..."
            preview_text = f"{fav_count} packages - {pkgs_preview}"
        else:
            preview_text = "No apps in favourites"

        fav_card = GlassContainer(
            opacity=0.15, padding=15, ink=True, on_click=lambda e: open_list_detail("Favourites", is_fav=True),
            border=ft.border.all(1, ft.Colors.PINK_400),
            content=ft.Row(
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                controls=[
                    ft.Column([
                        ft.Row([ft.Icon(ft.Icons.FAVORITE, color=ft.Colors.PINK_400), ft.Text("Favourites", size=18, weight=ft.FontWeight.BOLD, color="onSurface")]),
                        ft.Text(preview_text, size=12, color="onSurfaceVariant", no_wrap=True)
                    ], expand=True),
                    ft.Icon(ft.Icons.ARROW_FORWARD_IOS, size=14, color="onSurfaceVariant")
                ]
            ),
            border_radius=state.get_radius('card')
        )
        lists_main_col.controls.append(fav_card)
        lists_main_col.controls.append(ft.Container(height=10))

        if not state.saved_lists:
             lists_main_col.controls.append(ft.Container(content=ft.Text("No custom lists created yet.", color="onSurfaceVariant"), alignment=ft.alignment.center, padding=20))
        else:
            sorted_lists = sorted(state.saved_lists.items(), key=lambda x: x[0].lower())

            for name, items in sorted_lists:
                count = len(items)
                pkgs_preview = ", ".join([i['package'].get('package_pname', '?') for i in items[:3]])
                if len(items) > 3: pkgs_preview += "..."
                display_text = f"{count} packages - {pkgs_preview}"
                info_col = ft.Column([
                    ft.Text(name, size=18, weight=ft.FontWeight.BOLD, color="onSurface"),
                    ft.Text(display_text, size=12, color=ft.Colors.TEAL_200, no_wrap=True)
                ], expand=True)

                card_content = ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    controls=[
                        ft.Container(content=info_col, expand=True, on_click=lambda e, n=name: open_list_detail(n)),
                        ft.IconButton(ft.Icons.DELETE_OUTLINE, icon_color=ft.Colors.RED_300, data=name, on_click=delete_saved_list)
                    ]
                )

                card = GlassContainer(
                    opacity=0.1, padding=15,
                    content=card_content,
                    border_radius=state.get_radius('card')
                )
                lists_main_col.controls.append(card)
        if update_ui and lists_main_col.page: lists_main_col.update()

    def refresh_list_detail_view(update_ui=False):
        list_detail_col.controls.clear()
        items = []
        if is_viewing_favourites:
            items = state.favourites
        elif selected_list_name and selected_list_name in state.saved_lists:
            items = state.saved_lists[selected_list_name]

        if not items:
             list_detail_col.controls.append(ft.Container(content=ft.Text("This list is empty.", color="onSurface"), alignment=ft.alignment.center, padding=20))
        else:
            for item in items:
                pkg_data = item['package']
                saved_channel = item['channel']
                list_detail_col.controls.append(NixPackageCard(pkg_data, page, saved_channel, on_cart_change=on_global_cart_change, is_cart_view=True, show_toast_callback=show_toast, on_menu_open=None))

        if update_ui and list_detail_col.page: list_detail_col.update()

    def get_search_view():
        channel_dropdown.border_radius = state.get_radius('selector')
        return ft.Container(
            expand=True,
            content=ft.Column(
                controls=[
                    ft.Row(controls=[
                        channel_dropdown,
                        ft.Container(
                            content=ft.Row([search_field, search_icon_btn], alignment=ft.MainAxisAlignment.SPACE_BETWEEN, spacing=0),
                            bgcolor="surfaceVariant",
                            border_radius=state.get_radius('search'),
                            padding=ft.padding.only(left=15, right=5),
                            expand=True
                        ),
                        ft.Container(content=ft.Stack([ft.IconButton(ft.Icons.FILTER_LIST, on_click=lambda e: toggle_filter_menu(True)), filter_badge_container]))
                    ]),
                    result_count_text,
                    results_column
                ]
            )
        )

    def get_cart_view():
        refresh_cart_view()
        return ft.Container(
            expand=True,
            content=ft.Column(controls=[cart_header, cart_list])
        )

    def get_lists_view():
        if selected_list_name or is_viewing_favourites:
            refresh_list_detail_view()
            title = "Favourites" if is_viewing_favourites else selected_list_name
            btn_text = f"Try {title} in Shell"

            items_for_tooltip = []
            if is_viewing_favourites:
                items_for_tooltip = state.favourites
            elif selected_list_name and selected_list_name in state.saved_lists:
                items_for_tooltip = state.saved_lists[selected_list_name]

            tooltip_cmd = _build_shell_command_for_items(items_for_tooltip, with_wrapper=True) if items_for_tooltip else ""
            clean_cmd = _build_shell_command_for_items(items_for_tooltip, with_wrapper=False) if items_for_tooltip else ""

            return ft.Container(
                expand=True,
                content=ft.Column(controls=[
                    ft.Row(alignment=ft.MainAxisAlignment.SPACE_BETWEEN, controls=[
                        ft.Row([ft.IconButton(ft.Icons.ARROW_BACK, on_click=go_back_to_lists_index), ft.Text(title, size=24, weight=ft.FontWeight.BOLD)]),
                        ft.Row([
                            ft.Container(
                                padding=ft.padding.symmetric(horizontal=12, vertical=8),
                                content=ft.Row(spacing=6, controls=[ft.Icon(ft.Icons.TERMINAL, size=16, color=ft.Colors.WHITE), ft.Text(btn_text, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE)]),
                                on_click=run_list_shell,
                                bgcolor=ft.Colors.BLUE_600,
                                border_radius=state.get_radius('button'),
                                ink=True,
                                tooltip=tooltip_cmd
                            ),
                            ft.IconButton(ft.Icons.CONTENT_COPY, on_click=copy_list_command, tooltip=clean_cmd)
                        ])
                    ]),
                    list_detail_col
                ])
            )
        else:
            refresh_lists_main_view()
            return ft.Container(
                expand=True,
                content=ft.Column(controls=[
                    ft.Text("My Lists", size=24, weight=ft.FontWeight.BOLD, color="onSurface"),
                    ft.Container(height=10),
                    lists_main_col
                ])
            )

    class AutoCarousel(ft.Container):
        def __init__(self, data_list):
            super().__init__(
                width=220, height=120,
                border_radius=15,
                animate_opacity=300,
                on_hover=self.handle_hover
            )
            self.data_list = data_list
            self.current_index = 0
            self.running = False
            self.paused = False

            self.title_text = ft.Text("", weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE)
            self.desc_text = ft.Text("", size=12, color=ft.Colors.WHITE70)

            self.bar_thickness = 3
            self.border_bottom = ft.Container(bgcolor="white", height=self.bar_thickness, width=0, bottom=0, left=0)
            self.border_right = ft.Container(bgcolor="white", width=self.bar_thickness, height=0, bottom=0, right=0)
            self.border_top = ft.Container(bgcolor="white", height=self.bar_thickness, width=0, top=0, right=0)
            self.border_left = ft.Container(bgcolor="white", width=self.bar_thickness, height=0, top=0, left=0)

            self.content_container = ft.Container(
                padding=15,
                expand=True,
                content=ft.Column(
                    [self.title_text, self.desc_text],
                    spacing=5,
                    alignment=ft.MainAxisAlignment.CENTER
                )
            )

            self.content = ft.Stack(
                controls=[
                    self.content_container,
                    self.border_bottom,
                    self.border_right,
                    self.border_top,
                    self.border_left
                ]
            )

            self.update_content()

        def update_content(self):
            item = self.data_list[self.current_index]

            if state.carousel_glass:
                self.bgcolor = ft.Colors.with_opacity(0.6, item["color"])
                self.blur = ft.Blur(15, 15, ft.BlurTileMode.MIRROR)
                self.border = ft.border.all(1, ft.Colors.with_opacity(0.3, ft.Colors.WHITE))
            else:
                self.bgcolor = item["color"]
                self.blur = None
                self.border = None

            self.title_text.value = item["title"]
            self.desc_text.value = item["desc"]
            if self.page: self.update()

        def did_mount(self):
            self.running = True
            threading.Thread(target=self.loop, daemon=True).start()

        def will_unmount(self):
            self.running = False

        def handle_hover(self, e):
            if e.data == "true":
                self.paused = True
                self.set_bars_progress(1.0)
                self.update_content()
            else:
                self.paused = False

        def set_bars_progress(self, progress):
            w_total = 220
            h_total = 120

            if progress > 0.75:
                p = (progress - 0.75) * 4
                self.border_bottom.width = w_total * p
                self.border_right.height = h_total
                self.border_top.width = w_total
                self.border_left.height = h_total
            elif progress > 0.5:
                p = (progress - 0.5) * 4
                self.border_bottom.width = 0
                self.border_right.height = h_total * p
                self.border_top.width = w_total
                self.border_left.height = h_total
            elif progress > 0.25:
                p = (progress - 0.25) * 4
                self.border_bottom.width = 0
                self.border_right.height = 0
                self.border_top.width = w_total * p
                self.border_left.height = h_total
            else:
                p = progress * 4
                self.border_bottom.width = 0
                self.border_right.height = 0
                self.border_top.width = 0
                self.border_left.height = h_total * p

            if self.page:
                self.border_bottom.update()
                self.border_right.update()
                self.border_top.update()
                self.border_left.update()

        def loop(self):
            step = 0.05
            while self.running:
                if self.paused:
                    time.sleep(0.1)
                    continue

                duration = max(1, state.carousel_timer)
                steps_total = int(duration / step)

                self.set_bars_progress(1.0)

                for i in range(steps_total):
                    if not self.running: return
                    if self.paused: break

                    time.sleep(step)
                    progress = 1.0 - ((i + 1) / steps_total)
                    self.set_bars_progress(progress)

                if self.paused: continue

                self.current_index = (self.current_index + 1) % len(self.data_list)
                self.update_content()

    def create_stacked_card(content, base_color, width=None, height=None, expand=1):
        container_width = width if width and width > 0 else None
        container_expand = expand if (not width or width == 0) else 0

        layer1 = ft.Container(
            bgcolor=ft.Colors.with_opacity(0.3, base_color),
            border_radius=20,
            border=ft.border.all(1, ft.Colors.with_opacity(0.1, ft.Colors.WHITE)),
            rotate=ft.Rotate(0.12, alignment=ft.alignment.center),
            scale=0.92,
            left=0, right=0, top=0, bottom=0,
        )

        layer2 = ft.Container(
            bgcolor=ft.Colors.with_opacity(0.6, base_color),
            border_radius=20,
            border=ft.border.all(1, ft.Colors.with_opacity(0.2, ft.Colors.WHITE)),
            rotate=ft.Rotate(0.06, alignment=ft.alignment.center),
            scale=0.96,
            left=0, right=0, top=0, bottom=0,
        )

        content.left = 0
        content.right = 0
        content.top = 0
        content.bottom = 0

        return ft.Container(
            expand=container_expand,
            width=container_width,
            height=height,
            content=ft.Stack(
                controls=[
                    layer1,
                    layer2,
                    content
                ]
            )
        )

    def get_home_view():
        state.update_daily_indices()

        app_data = DAILY_APPS[state.daily_indices["app"] % len(DAILY_APPS)]
        quote_data = DAILY_QUOTES[state.daily_indices["quote"] % len(DAILY_QUOTES)]
        tip_data = DAILY_TIPS[state.daily_indices["tip"] % len(DAILY_TIPS)]
        song_data = DAILY_SONGS[state.daily_indices["song"] % len(DAILY_SONGS)]

        # --- Daily Digest Cards ---
        cards_row1 = []
        cards_row2 = []

        def get_cfg(key):
            return state.home_card_config.get(key, CARD_DEFAULTS[key])

        def get_alignment(align_str):
            if align_str == "left": return ft.MainAxisAlignment.START
            if align_str == "right": return ft.MainAxisAlignment.END
            return ft.MainAxisAlignment.CENTER

        def get_card_color(color_name):
            return COLOR_NAME_MAP.get(color_name, ft.Colors.BLUE)

        # Build App Card
        cfg = get_cfg("app")
        if cfg["visible"]:
            base_col = get_card_color(cfg["color"])
            main_card = GlassContainer(
                padding=20, border_radius=20,
                bgcolor=ft.Colors.with_opacity(0.9, base_col),
                content=ft.Column(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    horizontal_alignment=ft.CrossAxisAlignment.START,
                    controls=[
                        ft.Row([ft.Text("Random App of the Day", size=12, color=ft.Colors.WHITE70, weight=ft.FontWeight.BOLD)], alignment=get_alignment(cfg["align"])),
                        ft.Row([ft.Text(app_data["pname"], size=32, color=ft.Colors.WHITE, weight=ft.FontWeight.W_900)], alignment=get_alignment(cfg["align"])),
                        ft.Row([ft.Text(app_data["desc"], size=12, color=ft.Colors.WHITE70, max_lines=2, overflow=ft.TextOverflow.ELLIPSIS, text_align=ft.TextAlign.LEFT if cfg["align"] == "left" else (ft.TextAlign.RIGHT if cfg["align"] == "right" else ft.TextAlign.CENTER))], alignment=get_alignment(cfg["align"])),
                    ]
                )
            )
            cards_row1.append(create_stacked_card(main_card, base_col, height=cfg["h"], width=cfg["w"], expand=2))

        # Build Tip Card
        cfg = get_cfg("tip")
        if cfg["visible"]:
            base_col = get_card_color(cfg["color"])
            main_card = GlassContainer(
                padding=15, border_radius=20,
                bgcolor=ft.Colors.with_opacity(0.9, base_col),
                content=ft.Column(
                    controls=[
                        ft.Row([ft.Text("Nix Random Tip", size=12, color=ft.Colors.WHITE70, weight=ft.FontWeight.BOLD)], alignment=get_alignment(cfg["align"])),
                        ft.Container(height=10),
                        ft.Row([ft.Text(tip_data["title"], size=16, color=ft.Colors.WHITE, weight=ft.FontWeight.BOLD)], alignment=get_alignment(cfg["align"])),
                        ft.Container(
                            bgcolor=ft.Colors.BLACK26, padding=10, border_radius=8,
                            content=ft.Text(tip_data["code"], font_family="monospace", size=12, color=ft.Colors.GREEN_100),
                            alignment=ft.alignment.center_left if cfg["align"] == "left" else (ft.alignment.center_right if cfg["align"] == "right" else ft.alignment.center)
                        )
                    ]
                )
            )
            cards_row1.append(create_stacked_card(main_card, base_col, height=cfg["h"], width=cfg["w"], expand=1))

        # Build Quote Card
        cfg = get_cfg("quote")
        if cfg["visible"]:
            base_col = get_card_color(cfg["color"])
            main_card = GlassContainer(
                padding=15, border_radius=20,
                bgcolor=ft.Colors.with_opacity(0.9, base_col),
                content=ft.Column(
                    alignment=ft.MainAxisAlignment.CENTER,
                    controls=[
                        ft.Row([ft.Text("Quote of the Day", size=10, color=ft.Colors.WHITE70, weight=ft.FontWeight.BOLD)], alignment=get_alignment(cfg["align"])),
                        ft.Text(f'"{quote_data["text"]}"', size=13, color=ft.Colors.WHITE, italic=True, text_align=ft.TextAlign.LEFT if cfg["align"] == "left" else (ft.TextAlign.RIGHT if cfg["align"] == "right" else ft.TextAlign.CENTER)),
                        ft.Row([ft.Text(f"- {quote_data['author']}", size=11, color=ft.Colors.WHITE70)], alignment=ft.MainAxisAlignment.END if cfg["align"] == "right" else (ft.MainAxisAlignment.START if cfg["align"] == "left" else ft.MainAxisAlignment.CENTER))
                    ]
                )
            )
            cards_row2.append(create_stacked_card(main_card, base_col, height=cfg["h"], width=cfg["w"], expand=1))

        # Build Song Card
        cfg = get_cfg("song")
        if cfg["visible"]:
            base_col = get_card_color(cfg["color"])
            main_card = GlassContainer(
                padding=15, border_radius=20,
                bgcolor=ft.Colors.with_opacity(0.9, base_col),
                content=ft.Column(
                    alignment=ft.MainAxisAlignment.CENTER,
                    controls=[
                        ft.Row([ft.Text("Song of the Day", size=10, color=ft.Colors.BLACK54, weight=ft.FontWeight.BOLD)], alignment=get_alignment(cfg["align"])),
                        ft.Row([ft.Icon(ft.Icons.MUSIC_NOTE, size=30, color=ft.Colors.BLACK87)], alignment=get_alignment(cfg["align"])),
                        ft.Row([ft.Text(song_data["title"], size=16, color=ft.Colors.BLACK87, weight=ft.FontWeight.BOLD)], alignment=get_alignment(cfg["align"])),
                        ft.Row([ft.Text(song_data["artist"], size=12, color=ft.Colors.BLACK54)], alignment=get_alignment(cfg["align"]))
                    ]
                )
            )
            cards_row2.append(create_stacked_card(main_card, base_col, height=cfg["h"], width=cfg["w"], expand=1))

        carousel_widget = AutoCarousel(CAROUSEL_DATA)

        controls = []

        header_row = ft.Row(
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.START,
            controls=[
                ft.Column([
                    ft.Row([ft.Icon(ft.Icons.HOME_FILLED, size=state.get_size(4.0), color=ft.Colors.BLUE_200)], alignment=ft.MainAxisAlignment.START),
                    ft.Text(f"Hello, {state.username}!", size=state.get_size(2.3), weight=ft.FontWeight.W_900, color="onSurface"),
                    ft.Text("Welcome to All Might", size=state.get_size(1.15), color="onSurfaceVariant"),
                ]),
                ft.Container(
                    width=300,
                    content=ft.Column([
                        ft.Text("Updates", size=12, weight=ft.FontWeight.BOLD, color="onSurfaceVariant"),
                        carousel_widget
                    ])
                )
            ]
        )
        controls.append(header_row)

        if cards_row1 or cards_row2:
            controls.append(ft.Container(height=30))
            controls.append(ft.Text("Daily Digest", size=18, weight=ft.FontWeight.BOLD, color="onSurfaceVariant"))
            controls.append(ft.Container(height=10))

            if cards_row1:
                controls.append(ft.Row(controls=cards_row1, spacing=20, alignment=ft.MainAxisAlignment.START, vertical_alignment=ft.CrossAxisAlignment.START))
            if cards_row2:
                controls.append(ft.Container(height=40))
                controls.append(ft.Row(controls=cards_row2, spacing=20, alignment=ft.MainAxisAlignment.START, vertical_alignment=ft.CrossAxisAlignment.START))

        return ft.Container(
            expand=True,
            alignment=ft.alignment.top_left,
            padding=ft.padding.only(top=40, left=30, right=30, bottom=20),
            content=ft.Column(
                horizontal_alignment=ft.CrossAxisAlignment.START,
                controls=controls,
                scroll=ft.ScrollMode.AUTO
            )
        )

    def get_settings_view():
        channels_row = ft.Row(wrap=True, spacing=10, run_spacing=10)

        def update_username(e):
            state.username = e.control.value
            state.save_settings()
            show_toast(f"Username updated")

        def update_default_channel(e):
            state.default_channel = e.control.value
            state.save_settings()
            refresh_dropdown_options()
            show_toast(f"Saved default: {state.default_channel}")

        preview_text_normal = ft.Text("This is how your text looks.", size=state.get_font_size('body'), color="onSurface")
        preview_text_small = ft.Text("Small text example", size=state.get_font_size('small'), color="onSurfaceVariant")
        preview_text_title = ft.Text("Large Header", size=state.get_font_size('title'), weight=ft.FontWeight.BOLD)

        def refresh_fonts():
            if settings_refresh_ref[0]:
                settings_refresh_ref[0]()
            else:
                on_nav_change(4)

            if navbar_ref[0]: navbar_ref[0]()
            page.update()

        def get_label_text(label, current, default):
            return f"{label} (Cur: {int(current)} | Def: {default})"

        # --- Font Logic Handlers ---

        # Define text controls for Font Labels
        txt_global_font = ft.Text(get_label_text("Global Font Size", state.global_font_size, 14), weight=ft.FontWeight.BOLD)
        txt_title_font = ft.Text(get_label_text("Title Font Size", state.title_font_size, 16))
        txt_body_font = ft.Text(get_label_text("Body Font Size", state.body_font_size, 14))
        txt_small_font = ft.Text(get_label_text("Small/Tag Font Size", state.small_font_size, 12))
        txt_nav_font = ft.Text(get_label_text("Navbar Font Size", state.nav_font_size, 12))

        def update_global_font_live(e):
            val = int(e.control.value)
            state.global_font_size = val
            txt_global_font.value = get_label_text("Global Font Size", val, 14)
            txt_global_font.update()

            preview_text_normal.size = state.get_font_size('body')
            preview_text_small.size = state.get_font_size('small')
            preview_text_title.size = state.get_font_size('title')
            preview_text_normal.update()
            preview_text_small.update()
            preview_text_title.update()

        def save_and_refresh_fonts(e):
            state.save_settings()
            refresh_fonts()

        def update_title_font_live(e):
            val = int(e.control.value)
            state.title_font_size = val
            txt_title_font.value = get_label_text("Title Font Size", val, 16)
            txt_title_font.update()

            preview_text_title.size = state.get_font_size('title')
            preview_text_title.update()

        def update_sync_title(e):
            state.sync_title_font = e.control.value
            state.save_settings()
            slider_title_font.disabled = state.sync_title_font
            slider_title_font.update()
            refresh_fonts()

        def update_body_font_live(e):
            val = int(e.control.value)
            state.body_font_size = val
            txt_body_font.value = get_label_text("Body Font Size", val, 14)
            txt_body_font.update()

            preview_text_normal.size = state.get_font_size('body')
            preview_text_normal.update()

        def update_sync_body(e):
            state.sync_body_font = e.control.value
            state.save_settings()
            slider_body_font.disabled = state.sync_body_font
            slider_body_font.update()
            refresh_fonts()

        def update_small_font_live(e):
            val = int(e.control.value)
            state.small_font_size = val
            txt_small_font.value = get_label_text("Small/Tag Font Size", val, 12)
            txt_small_font.update()

            preview_text_small.size = state.get_font_size('small')
            preview_text_small.update()

        def update_sync_small(e):
            state.sync_small_font = e.control.value
            state.save_settings()
            slider_small_font.disabled = state.sync_small_font
            slider_small_font.update()
            refresh_fonts()

        def update_nav_font_live(e):
            val = int(e.control.value)
            state.nav_font_size = val
            txt_nav_font.value = get_label_text("Navbar Font Size", val, 12)
            txt_nav_font.update()

        def update_sync_nav_font(e):
            state.sync_nav_font = e.control.value
            state.save_settings()
            slider_nav_font.disabled = state.sync_nav_font
            slider_nav_font.update()
            refresh_fonts()

        def update_confirm_timer(e):
            state.confirm_timer = int(e.control.value)
            state.save_settings()

        def update_undo_timer(e):
            state.undo_timer = int(e.control.value)
            state.save_settings()

        def update_badge_size(e):
            state.nav_badge_size = int(e.control.value)
            state.save_settings()
            update_badges_style()

        def update_search_limit(e):
            state.search_limit = int(e.control.value)
            state.save_settings()

        def update_floating_nav(e):
            state.floating_nav = e.control.value
            state.save_settings()
            if navbar_ref[0]: navbar_ref[0]()

        def update_adaptive_nav(e):
            state.adaptive_nav = e.control.value
            state.save_settings()
            if navbar_ref[0]: navbar_ref[0]()

        def update_glass_nav(e):
            state.glass_nav = e.control.value
            state.save_settings()
            if navbar_ref[0]: navbar_ref[0]()

        # --- Navbar Sliders Logic ---
        txt_nav_width = ft.Text(get_label_text("Total Length (Floating)", state.nav_bar_width, 500))
        txt_nav_spacing = ft.Text(get_label_text("Icon Spacing (Manual)", state.nav_icon_spacing, 15))

        def update_nav_width(e):
            val = int(e.control.value)
            state.nav_bar_width = val
            txt_nav_width.value = get_label_text("Total Length (Floating)", val, 500)
            txt_nav_width.update()
            state.save_settings()
            if navbar_ref[0]: navbar_ref[0]()

        def update_icon_spacing(e):
            val = int(e.control.value)
            state.nav_icon_spacing = val
            txt_nav_spacing.value = get_label_text("Icon Spacing (Manual)", val, 15)
            txt_nav_spacing.update()
            state.save_settings()
            if navbar_ref[0]: navbar_ref[0]()

        def update_sync_nav_spacing(e):
            state.sync_nav_spacing = e.control.value
            state.save_settings()
            nav_spacing_slider.disabled = state.sync_nav_spacing
            nav_spacing_slider.update()
            if navbar_ref[0]: navbar_ref[0]()

        # --- Radius Sliders Logic ---

        # Define Text Controls for Radius
        txt_global_radius = ft.Text(get_label_text("Global Radius", state.global_radius, 33), weight=ft.FontWeight.BOLD)
        txt_nav_radius = ft.Text(get_label_text("Nav Bar Radius", state.nav_radius, 33))
        txt_card_radius = ft.Text(get_label_text("Card Radius", state.card_radius, 15))
        txt_button_radius = ft.Text(get_label_text("Button Radius", state.button_radius, 10))
        txt_search_radius = ft.Text(get_label_text("Search Bar Radius", state.search_radius, 15))
        txt_selector_radius = ft.Text(get_label_text("Selector Radius", state.selector_radius, 15))
        txt_footer_radius = ft.Text(get_label_text("Footer Section Radius", state.footer_radius, 15))
        txt_chip_radius = ft.Text(get_label_text("Footer Chip Radius", state.chip_radius, 10))

        def update_global_radius(e):
            val = int(e.control.value)
            state.global_radius = val
            txt_global_radius.value = get_label_text("Global Radius", val, 33)
            txt_global_radius.update()
            state.save_settings()
            if navbar_ref[0]: navbar_ref[0]()

        def update_nav_radius(e):
            val = int(e.control.value)
            state.nav_radius = val
            txt_nav_radius.value = get_label_text("Nav Bar Radius", val, 33)
            txt_nav_radius.update()
            state.save_settings()
            if navbar_ref[0]: navbar_ref[0]()

        def update_sync_nav_radius(e):
            state.sync_nav_radius = e.control.value
            state.save_settings()
            slider_nav_radius.disabled = state.sync_nav_radius
            slider_nav_radius.update()
            if navbar_ref[0]: navbar_ref[0]()

        def update_card_radius(e):
            val = int(e.control.value)
            state.card_radius = val
            txt_card_radius.value = get_label_text("Card Radius", val, 15)
            txt_card_radius.update()
            state.save_settings()

        def update_sync_card_radius(e):
            state.sync_card_radius = e.control.value
            state.save_settings()
            slider_card_radius.disabled = state.sync_card_radius
            slider_card_radius.update()

        def update_button_radius(e):
            val = int(e.control.value)
            state.button_radius = val
            txt_button_radius.value = get_label_text("Button Radius", val, 10)
            txt_button_radius.update()
            state.save_settings()

        def update_sync_button_radius(e):
            state.sync_button_radius = e.control.value
            state.save_settings()
            slider_button_radius.disabled = state.sync_button_radius
            slider_button_radius.update()

        def update_search_radius(e):
            val = int(e.control.value)
            state.search_radius = val
            txt_search_radius.value = get_label_text("Search Bar Radius", val, 15)
            txt_search_radius.update()
            state.save_settings()

        def update_sync_search_radius(e):
            state.sync_search_radius = e.control.value
            state.save_settings()
            slider_search_radius.disabled = state.sync_search_radius
            slider_search_radius.update()

        def update_selector_radius(e):
            val = int(e.control.value)
            state.selector_radius = val
            txt_selector_radius.value = get_label_text("Selector Radius", val, 15)
            txt_selector_radius.update()
            state.save_settings()

        def update_sync_selector_radius(e):
            state.sync_selector_radius = e.control.value
            state.save_settings()
            slider_selector_radius.disabled = state.sync_selector_radius
            slider_selector_radius.update()

        def update_footer_radius(e):
            val = int(e.control.value)
            state.footer_radius = val
            txt_footer_radius.value = get_label_text("Footer Section Radius", val, 15)
            txt_footer_radius.update()
            state.save_settings()

        def update_sync_footer_radius(e):
            state.sync_footer_radius = e.control.value
            state.save_settings()
            slider_footer_radius.disabled = state.sync_footer_radius
            slider_footer_radius.update()

        def update_chip_radius(e):
            val = int(e.control.value)
            state.chip_radius = val
            txt_chip_radius.value = get_label_text("Footer Chip Radius", val, 10)
            txt_chip_radius.update()
            state.save_settings()

        def update_sync_chip_radius(e):
            state.sync_chip_radius = e.control.value
            state.save_settings()
            slider_chip_radius.disabled = state.sync_chip_radius
            slider_chip_radius.update()

        def update_carousel_timer(e):
            try:
                val = int(e.control.value)
                state.carousel_timer = val
                state.save_settings()
            except:
                pass

        def update_carousel_glass(e):
            state.carousel_glass = e.control.value
            state.save_settings()

        # --- Reset Functions ---
        def reset_with_confirmation(title, default_applier, undo_state_capturer, undo_restorer):
            old_state = undo_state_capturer()
            def on_confirm(e):
                default_applier()
                state.save_settings()

                if "home" in title.lower():
                    if settings_refresh_ref[0]: settings_refresh_ref[0]()
                else:
                    refresh_fonts()

                def on_undo():
                    undo_restorer(old_state)
                    state.save_settings()
                    if "home" in title.lower():
                        if settings_refresh_ref[0]: settings_refresh_ref[0]()
                    else:
                        refresh_fonts()

                show_undo_toast("Reset to defaults", on_undo)

            show_destructive_dialog(title, "Are you sure you want to reset settings to defaults?", on_confirm)

        def reset_radius_defaults(e):
            def capture():
                return {
                    'global': state.global_radius, 'nav': state.nav_radius, 'sync_nav': state.sync_nav_radius,
                    'card': state.card_radius, 'sync_card': state.sync_card_radius, 'btn': state.button_radius, 'sync_btn': state.sync_button_radius,
                    'search': state.search_radius, 'sync_search': state.sync_search_radius, 'sel': state.selector_radius, 'sync_sel': state.sync_selector_radius,
                    'foot': state.footer_radius, 'sync_foot': state.sync_footer_radius, 'chip': state.chip_radius, 'sync_chip': state.sync_chip_radius
                }
            def apply():
                state.global_radius = 33; state.nav_radius = 33; state.sync_nav_radius = True
                state.card_radius = 15; state.sync_card_radius = True; state.button_radius = 10; state.sync_button_radius = True
                state.search_radius = 15; state.sync_search_radius = True; state.selector_radius = 15; state.sync_selector_radius = True
                state.footer_radius = 15; state.sync_footer_radius = True; state.chip_radius = 10; state.sync_chip_radius = True

                slider_global_radius.value = 33
                txt_global_radius.value = get_label_text("Global Radius", 33, 33)

                slider_nav_radius.value = 33
                txt_nav_radius.value = get_label_text("Nav Bar Radius", 33, 33)

                slider_card_radius.value = 15
                txt_card_radius.value = get_label_text("Card Radius", 15, 15)

                slider_button_radius.value = 10
                txt_button_radius.value = get_label_text("Button Radius", 10, 10)

                slider_search_radius.value = 15
                txt_search_radius.value = get_label_text("Search Bar Radius", 15, 15)

                slider_selector_radius.value = 15
                txt_selector_radius.value = get_label_text("Selector Radius", 15, 15)

                slider_footer_radius.value = 15
                txt_footer_radius.value = get_label_text("Footer Section Radius", 15, 15)

                slider_chip_radius.value = 10
                txt_chip_radius.value = get_label_text("Footer Chip Radius", 10, 10)

            def restore(s):
                state.global_radius = s['global']; state.nav_radius = s['nav']; state.sync_nav_radius = s['sync_nav']
                state.card_radius = s['card']; state.sync_card_radius = s['sync_card']; state.button_radius = s['btn']; state.sync_button_radius = s['sync_btn']
                state.search_radius = s['search']; state.sync_search_radius = s['sync_search']; state.selector_radius = s['sel']; state.sync_selector_radius = s['sync_sel']
                state.footer_radius = s['foot']; state.sync_footer_radius = s['sync_foot']; state.chip_radius = s['chip']; state.sync_chip_radius = s['sync_chip']

            reset_with_confirmation("Reset Appearance Defaults?", apply, capture, restore)

        def reset_navbar_defaults(e):
            def capture():
                return {'float': state.floating_nav, 'adapt': state.adaptive_nav, 'glass': state.glass_nav, 'w': state.nav_bar_width, 'space': state.nav_icon_spacing, 'sync_space': state.sync_nav_spacing, 'badge': state.nav_badge_size}
            def apply():
                state.floating_nav = True; state.adaptive_nav = True; state.glass_nav = True
                state.nav_bar_width = 500; state.nav_icon_spacing = 15; state.sync_nav_spacing = True; state.nav_badge_size = 20

                nav_width_slider.value = 500
                txt_nav_width.value = get_label_text("Total Length (Floating)", 500, 500)

                nav_spacing_slider.value = 15
                txt_nav_spacing.value = get_label_text("Icon Spacing (Manual)", 15, 15)

            def restore(s):
                state.floating_nav = s['float']; state.adaptive_nav = s['adapt']; state.glass_nav = s['glass']
                state.nav_bar_width = s['w']; state.nav_icon_spacing = s['space']; state.sync_nav_spacing = s['sync_space']; state.nav_badge_size = s['badge']

            reset_with_confirmation("Reset Navbar Defaults?", apply, capture, restore)

        def reset_timer_defaults(e):
            def capture(): return {'confirm': state.confirm_timer, 'undo': state.undo_timer}
            def apply(): state.confirm_timer = 5; state.undo_timer = 5
            def restore(s): state.confirm_timer = s['confirm']; state.undo_timer = s['undo']

            reset_with_confirmation("Reset Timer Defaults?", apply, capture, restore)

        def reset_font_defaults(e):
            def capture():
                return {
                    'global': state.global_font_size, 'title': state.title_font_size, 'sync_title': state.sync_title_font,
                    'body': state.body_font_size, 'sync_body': state.sync_body_font, 'small': state.small_font_size, 'sync_small': state.sync_small_font,
                    'nav': state.nav_font_size, 'sync_nav': state.sync_nav_font
                }
            def apply():
                state.global_font_size = 14; state.title_font_size = 16; state.sync_title_font = True
                state.body_font_size = 14; state.sync_body_font = True; state.small_font_size = 12; state.sync_small_font = True
                state.nav_font_size = 12; state.sync_nav_font = True

                slider_global_font.value = 14
                txt_global_font.value = get_label_text("Global Font Size", 14, 14)

                slider_title_font.value = 16
                txt_title_font.value = get_label_text("Title Font Size", 16, 16)

                slider_body_font.value = 14
                txt_body_font.value = get_label_text("Body Font Size", 14, 14)

                slider_small_font.value = 12
                txt_small_font.value = get_label_text("Small/Tag Font Size", 12, 12)

                slider_nav_font.value = 12
                txt_nav_font.value = get_label_text("Navbar Font Size", 12, 12)

            def restore(s):
                state.global_font_size = s['global']; state.title_font_size = s['title']; state.sync_title_font = s['sync_title']
                state.body_font_size = s['body']; state.sync_body_font = s['sync_body']; state.small_font_size = s['small']; state.sync_small_font = s['sync_small']
                state.nav_font_size = s['nav']; state.sync_nav_font = s['sync_nav']

            reset_with_confirmation("Reset Font Defaults?", apply, capture, restore)

        # --- Home Page Config Helper ---
        def create_card_config_tile(card_key, label):
            default = CARD_DEFAULTS[card_key]
            cfg = state.home_card_config.get(card_key, default.copy())

            txt_height = ft.Text(get_label_text("Height (px)", cfg["h"], default["h"]))
            txt_width = ft.Text(get_label_text("Width (px) [0 = Auto]", cfg["w"], default["w"]))

            def update_visible(e):
                state.home_card_config[card_key]["visible"] = e.control.value
                state.save_settings()

            def update_height(e):
                val = int(e.control.value)
                state.home_card_config[card_key]["h"] = val
                txt_height.value = get_label_text("Height (px)", val, default["h"])
                txt_height.update()
                state.save_settings()

            def update_width(e):
                val = int(e.control.value)
                state.home_card_config[card_key]["w"] = val
                txt_width.value = get_label_text("Width (px) [0 = Auto]", val, default["w"])
                txt_width.update()
                state.save_settings()

            def update_align(e):
                val = list(e.control.selected)[0]
                state.home_card_config[card_key]["align"] = val
                state.save_settings()

            def update_card_color(e):
                val = e.control.data
                state.home_card_config[card_key]["color"] = val
                state.save_settings()
                for ctrl in color_row.controls:
                    is_sel = (ctrl.data == val)
                    ctrl.border = ft.border.all(2, "white") if is_sel else ft.border.all(2, ft.Colors.TRANSPARENT)
                color_row.update()

            def reset_card_defaults(e):
                def capture():
                    return state.home_card_config[card_key].copy()

                def apply():
                    state.home_card_config[card_key] = default.copy()

                    switch_visible.value = default["visible"]
                    slider_height.value = default["h"]
                    txt_height.value = get_label_text("Height (px)", default["h"], default["h"])

                    slider_width.value = default["w"]
                    txt_width.value = get_label_text("Width (px) [0 = Auto]", default["w"], default["w"])

                    seg_align.selected = {default["align"]}

                    for ctrl in color_row.controls:
                        ctrl.border = ft.border.all(2, "white") if ctrl.data == default["color"] else ft.border.all(2, ft.Colors.TRANSPARENT)

                    if settings_main_column.page:
                        switch_visible.update()
                        slider_height.update()
                        txt_height.update()
                        slider_width.update()
                        txt_width.update()
                        seg_align.update()
                        color_row.update()

                def restore(s):
                    state.home_card_config[card_key] = s

                reset_with_confirmation(f"Reset {label}?", apply, capture, restore)

            switch_visible = ft.Switch(value=cfg["visible"], on_change=update_visible)
            slider_height = ft.Slider(min=100, max=400, value=cfg["h"], label="{value}", on_change=update_height)
            slider_width = ft.Slider(min=0, max=600, value=cfg["w"], label="{value}", on_change=update_width)
            seg_align = ft.SegmentedButton(
                selected={cfg["align"]},
                on_change=update_align,
                segments=[
                    ft.Segment(value="left", label=ft.Text("Left"), icon=ft.Icon(ft.Icons.FORMAT_ALIGN_LEFT)),
                    ft.Segment(value="center", label=ft.Text("Center"), icon=ft.Icon(ft.Icons.FORMAT_ALIGN_CENTER)),
                    ft.Segment(value="right", label=ft.Text("Right"), icon=ft.Icon(ft.Icons.FORMAT_ALIGN_RIGHT)),
                ]
            )

            color_controls = []
            for name, code in COLOR_NAME_MAP.items():
                is_selected = (name == cfg.get("color", default["color"]))
                color_controls.append(
                    ft.Container(
                        width=30, height=30, border_radius=15, bgcolor=code,
                        border=ft.border.all(2, "white") if is_selected else ft.border.all(2, ft.Colors.TRANSPARENT),
                        on_click=update_card_color, data=name, ink=True, tooltip=name.capitalize()
                    )
                )
            color_row = ft.Row(controls=color_controls, spacing=10, wrap=True)

            return make_settings_tile(label, [
                ft.Row([ft.Text("Show Card:", weight=ft.FontWeight.BOLD), switch_visible], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                ft.Divider(),
                txt_height, slider_height,
                txt_width, slider_width,
                ft.Text("Content Alignment:"), seg_align,
                ft.Container(height=10),
                ft.Text(f"Card Color (Def: {default['color'].capitalize()})"), color_row
            ], reset_func=reset_card_defaults)

        def get_settings_controls(category):
            controls_list = []
            if category == "home_config":
                carousel_timer_input = ft.TextField(value=str(state.carousel_timer), hint_text="Def: 10", width=100, height=40, text_size=12, content_padding=10, filled=True, bgcolor=ft.Colors.with_opacity(0.1, "onSurface"), on_submit=update_carousel_timer, on_blur=update_carousel_timer)
                controls_list = [
                    ft.Text("Home Page Configuration", size=24, weight=ft.FontWeight.BOLD), ft.Divider(),
                    ft.Row([ft.Text("Carousel Timer (s):"), carousel_timer_input], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    ft.Row([ft.Text("Carousel Glass Effect:"), ft.Switch(value=state.carousel_glass, on_change=update_carousel_glass)], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    ft.Container(height=10),
                    create_card_config_tile("app", "Random App Card"),
                    ft.Container(height=10),
                    create_card_config_tile("quote", "Quote Card"),
                    ft.Container(height=10),
                    create_card_config_tile("tip", "Nix Tip Card"),
                    ft.Container(height=10),
                    create_card_config_tile("song", "Song Card"),
                ]
            elif category == "profile":
                controls_list = [
                    ft.Text("User Profile", size=24, weight=ft.FontWeight.BOLD), ft.Divider(),
                    make_settings_tile("User Identity", [
                        ft.Text("Customize your user identity within the app."),
                        ft.Container(height=10),
                        ft.Row([ft.Text("Username:", weight=ft.FontWeight.BOLD, color="onSurface", width=100), username_input], alignment=ft.MainAxisAlignment.START)
                    ])
                ]
            elif category == "appearance":
                controls_list = [
                    ft.Text("Appearance", size=24, weight=ft.FontWeight.BOLD), ft.Divider(),
                    make_settings_tile("Theme", [
                        ft.Text("Mode:", weight=ft.FontWeight.BOLD), theme_mode_segment,
                        ft.Container(height=10),
                        ft.Text("Accent Color:", weight=ft.FontWeight.BOLD), ft.Row(controls=color_controls, spacing=10)
                    ]),
                    ft.Container(height=10),
                    make_settings_tile("Radius", [
                        txt_global_radius, slider_global_radius,
                        ft.Row([txt_nav_radius, ft.Switch(value=state.sync_nav_radius, label="Global", on_change=update_sync_nav_radius)], alignment=ft.MainAxisAlignment.SPACE_BETWEEN), slider_nav_radius,
                        ft.Row([txt_card_radius, ft.Switch(value=state.sync_card_radius, label="Global", on_change=update_sync_card_radius)], alignment=ft.MainAxisAlignment.SPACE_BETWEEN), slider_card_radius,
                        ft.Row([txt_button_radius, ft.Switch(value=state.sync_button_radius, label="Global", on_change=update_sync_button_radius)], alignment=ft.MainAxisAlignment.SPACE_BETWEEN), slider_button_radius,
                        ft.Row([txt_search_radius, ft.Switch(value=state.sync_search_radius, label="Global", on_change=update_sync_search_radius)], alignment=ft.MainAxisAlignment.SPACE_BETWEEN), slider_search_radius,
                        ft.Row([txt_selector_radius, ft.Switch(value=state.sync_selector_radius, label="Global", on_change=update_sync_selector_radius)], alignment=ft.MainAxisAlignment.SPACE_BETWEEN), slider_selector_radius,
                        ft.Row([txt_footer_radius, ft.Switch(value=state.sync_footer_radius, label="Global", on_change=update_sync_footer_radius)], alignment=ft.MainAxisAlignment.SPACE_BETWEEN), slider_footer_radius,
                        ft.Row([txt_chip_radius, ft.Switch(value=state.sync_chip_radius, label="Global", on_change=update_sync_chip_radius)], alignment=ft.MainAxisAlignment.SPACE_BETWEEN), slider_chip_radius,
                    ], reset_func=reset_radius_defaults),
                    ft.Container(height=10),
                    make_settings_tile("Navigation Bar", [
                        ft.Row([ft.Text("Always Floating:"), ft.Switch(value=state.floating_nav, on_change=update_floating_nav)], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                        ft.Row([ft.Text("Adaptive Expansion:"), ft.Switch(value=state.adaptive_nav, on_change=update_adaptive_nav)], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                        txt_nav_width, nav_width_slider,
                        ft.Row([ft.Text("Sync Icon Spacing:"), ft.Switch(value=state.sync_nav_spacing, on_change=update_sync_nav_spacing)], alignment=ft.MainAxisAlignment.SPACE_BETWEEN), txt_nav_spacing, nav_spacing_slider, ft.Container(height=10),
                        ft.Row([ft.Text("Glass Effect:"), ft.Switch(value=state.glass_nav, on_change=update_glass_nav)], alignment=ft.MainAxisAlignment.SPACE_BETWEEN), ft.Container(height=10),
                        ft.Row([ft.Text("Nav Badge Size:"), badge_size_input], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    ], reset_func=reset_navbar_defaults),
                    ft.Container(height=10),
                    make_settings_tile("Timers", [
                        ft.Row([ft.Text("Confirm Dialog (s):"), confirm_timer_input], alignment=ft.MainAxisAlignment.SPACE_BETWEEN), ft.Container(height=10),
                        ft.Row([ft.Text("Undo Toast (s):"), undo_timer_input], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
                    ], reset_func=reset_timer_defaults),
                    ft.Container(height=10),
                    make_settings_tile("Fonts", [
                        txt_global_font, slider_global_font,
                        ft.Divider(),
                        ft.Row([txt_title_font, ft.Switch(value=state.sync_title_font, label="Global", on_change=update_sync_title)], alignment=ft.MainAxisAlignment.SPACE_BETWEEN), slider_title_font,
                        ft.Row([txt_body_font, ft.Switch(value=state.sync_body_font, label="Global", on_change=update_sync_body)], alignment=ft.MainAxisAlignment.SPACE_BETWEEN), slider_body_font,
                        ft.Row([txt_small_font, ft.Switch(value=state.sync_small_font, label="Global", on_change=update_sync_small)], alignment=ft.MainAxisAlignment.SPACE_BETWEEN), slider_small_font,
                        ft.Row([txt_nav_font, ft.Switch(value=state.sync_nav_font, label="Global", on_change=update_sync_nav_font)], alignment=ft.MainAxisAlignment.SPACE_BETWEEN), slider_nav_font,
                        ft.Container(height=10),
                        ft.Container(
                            padding=20, bgcolor=ft.Colors.with_opacity(0.1, "onSurface"), border_radius=10,
                            content=ft.Column([
                                ft.Text("Live Preview", size=12, color="onSurfaceVariant", weight=ft.FontWeight.BOLD),
                                ft.Divider(),
                                preview_text_normal,
                                preview_text_small,
                                preview_text_title
                            ])
                        )
                    ], reset_func=reset_font_defaults)
                ]
            elif category == "channels":
                controls_list = [
                    ft.Text("Channel & Search", size=24, weight=ft.FontWeight.BOLD), ft.Divider(),
                    make_settings_tile("Search Configuration", [
                        ft.Text("Search Limit", weight=ft.FontWeight.BOLD), ft.Row([ft.Text("Max results:", size=12), search_limit_input], alignment=ft.MainAxisAlignment.SPACE_BETWEEN), ft.Container(height=20),
                        ft.Text("Default Search Channel", weight=ft.FontWeight.BOLD), ft.Container(height=5), ft.Dropdown(options=[ft.dropdown.Option(c) for c in state.available_channels], value=state.default_channel, on_change=update_default_channel, bgcolor="surfaceVariant", border_color="outline", text_style=ft.TextStyle(color="onSurface"), filled=True)
                    ]),
                    ft.Container(height=10),
                    make_settings_tile("Channel Management", [
                        ft.Text("Available Channels", weight=ft.FontWeight.BOLD), ft.Container(height=10), channels_row, ft.Divider(color=ft.Colors.OUTLINE, height=20),
                        ft.Row([ft.Text("Add Channel:", size=12), new_channel_input, ft.IconButton(ft.Icons.ADD_CIRCLE, icon_color=ft.Colors.GREEN, on_click=add_custom_channel)])
                    ])
                ]
            elif category == "run_config":
                controls_list = [
                     ft.Text("Run Configurations", size=24, weight=ft.FontWeight.BOLD), ft.Divider(),
                     make_settings_tile("Single App Execution", [
                        ft.Text("Run without installing cmd config", weight=ft.FontWeight.BOLD), ft.Container(height=5),
                        ft.Text("Prefix", weight=ft.FontWeight.BOLD), ft.TextField(value=state.shell_single_prefix, hint_text="nix run", text_size=12, filled=True, bgcolor=ft.Colors.with_opacity(0.1, "onSurface"), on_change=update_shell_single_prefix),
                        ft.Text("Suffix", weight=ft.FontWeight.BOLD), ft.TextField(value=state.shell_single_suffix, hint_text="", text_size=12, filled=True, bgcolor=ft.Colors.with_opacity(0.1, "onSurface"), on_change=update_shell_single_suffix), cmd_preview_single
                      ]),
                      ft.Container(height=10),
                      make_settings_tile("Cart/List Execution", [
                        ft.Text("Cart/List try in shell cmd config", weight=ft.FontWeight.BOLD), ft.Container(height=5),
                        ft.Text("Prefix", weight=ft.FontWeight.BOLD), ft.TextField(value=state.shell_cart_prefix, hint_text="nix shell", text_size=12, filled=True, bgcolor=ft.Colors.with_opacity(0.1, "onSurface"), on_change=update_shell_cart_prefix),
                        ft.Text("Suffix", weight=ft.FontWeight.BOLD), ft.TextField(value=state.shell_cart_suffix, hint_text="", text_size=12, filled=True, bgcolor=ft.Colors.with_opacity(0.1, "onSurface"), on_change=update_shell_cart_suffix), cmd_preview_cart
                    ])
                ]
            return controls_list

        def update_settings_view():
            current_cat = settings_ui_state["selected_category"]
            settings_main_column.controls = get_settings_controls(current_cat)

            if settings_main_column.page:
                if current_cat == "appearance" and settings_scroll_ref.current:
                    try:
                        settings_scroll_ref.current.scroll_to(offset=settings_ui_state.get("scroll_offset", 0), duration=0)
                    except:
                        pass
                else:
                    if settings_scroll_ref.current:
                        settings_scroll_ref.current.scroll_to(offset=0, duration=0)

                settings_main_column.update()

        settings_content_area = ft.Container(expand=True, padding=ft.padding.only(left=20), content=settings_main_column)

        def refresh_settings_view_only():
            current_cat = settings_ui_state["selected_category"]
            settings_main_column.controls = get_settings_controls(current_cat)
            if current_cat == "appearance" and settings_scroll_ref.current:
                try:
                    settings_scroll_ref.current.scroll_to(offset=settings_ui_state.get("scroll_offset", 0), duration=0)
                except:
                    pass
            settings_main_column.update()

        settings_refresh_ref[0] = refresh_settings_view_only

        settings_main_column.controls = get_settings_controls(settings_ui_state["selected_category"])

        return ft.Container(padding=10, content=ft.Row(spacing=0, vertical_alignment=ft.CrossAxisAlignment.START, controls=[ft.Container(width=200, content=settings_nav_rail, border=ft.border.only(right=ft.border.BorderSide(1, ft.Colors.OUTLINE_VARIANT)), padding=ft.padding.only(right=10)), settings_content_area], expand=True))

    content_area = ft.Container(expand=True, padding=20, content=get_home_view())
    navbar_ref = [None]

    def build_custom_navbar(on_change):
        nav_button_controls = []
        current_nav_idx = [0]
        base_container_ref = [None]
        main_row_ref = [None]

        items = [
            (ft.Icons.HOME_OUTLINED, ft.Icons.HOME, "Home"),
            (ft.Icons.SEARCH_OUTLINED, ft.Icons.SEARCH, "Search"),
            (ft.Icons.SHOPPING_CART_OUTLINED, ft.Icons.SHOPPING_CART, "Cart"),
            (ft.Icons.LIST_ALT_OUTLINED, ft.Icons.LIST_ALT, "Lists"),
            (ft.Icons.SETTINGS_OUTLINED, ft.Icons.SETTINGS, "Settings")
        ]

        def update_active_state(selected_idx):
            for i, control in enumerate(nav_button_controls):
                is_selected = (i == selected_idx)
                actual_btn_container = control.controls[0] if isinstance(control, ft.Stack) else control
                content_col = actual_btn_container.content
                icon_control = content_col.controls[0]
                text_control = content_col.controls[1]

                active_col = "onSecondaryContainer"
                inactive_col = ft.Colors.with_opacity(0.6, state.get_base_color())

                icon_control.name = items[i][1] if is_selected else items[i][0]
                icon_control.color = active_col if is_selected else inactive_col
                text_control.color = active_col if is_selected else inactive_col

                text_control.size = state.get_font_size('nav')

                actual_btn_container.bgcolor = "secondaryContainer" if is_selected else ft.Colors.TRANSPARENT

                if is_selected:
                    icon_control.color = "onSecondaryContainer"
                    text_control.color = "onSecondaryContainer"

                if control.page: control.update()

        def refresh_navbar():
            update_active_state(current_nav_idx[0])

            if main_row_ref[0]:
                main_row_ref[0].spacing = 0 if state.sync_nav_spacing else state.nav_icon_spacing
                main_row_ref[0].alignment = ft.MainAxisAlignment.SPACE_EVENLY if state.sync_nav_spacing else ft.MainAxisAlignment.CENTER
                if main_row_ref[0].page: main_row_ref[0].update()

            if base_container_ref[0]:
                is_wide = page.width > 600
                should_float = True if state.floating_nav else (False if state.adaptive_nav and is_wide else True)

                base_container_ref[0].width = state.nav_bar_width if should_float else page.width - 40
                base_container_ref[0].margin = ft.margin.only(bottom=20) if should_float else ft.margin.only(bottom=10)
                base_container_ref[0].border_radius = state.get_radius('nav') if should_float else 10

                if state.glass_nav:
                     base_container_ref[0].bgcolor = ft.Colors.with_opacity(0.15, state.get_base_color())
                     base_container_ref[0].blur = ft.Blur(15, 15, ft.BlurTileMode.MIRROR)
                     base_container_ref[0].border = ft.border.all(1, ft.Colors.with_opacity(0.2, state.get_base_color()))
                else:
                     base_container_ref[0].bgcolor = ft.Colors.SURFACE_VARIANT
                     base_container_ref[0].blur = None
                     base_container_ref[0].border = None

                if base_container_ref[0].page: base_container_ref[0].update()

        navbar_ref[0] = refresh_navbar

        def handle_click(e):
            idx = e.control.data
            current_nav_idx[0] = idx
            update_active_state(idx)
            on_change(idx)

        def create_nav_btn(index, icon_off, icon_on, label):
            inactive_col = ft.Colors.with_opacity(0.6, state.get_base_color())
            return ft.Container(
                content=ft.Column(
                    controls=[ft.Icon(name=icon_off, color=inactive_col, size=24), ft.Text(value=label, size=state.get_font_size('nav'), color=inactive_col, weight=ft.FontWeight.BOLD)],
                    alignment=ft.MainAxisAlignment.CENTER,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=0
                ),
                padding=ft.padding.symmetric(horizontal=12, vertical=8),
                border_radius=30,
                ink=True,
                on_click=handle_click,
                data=index,
                animate=ft.Animation(300, ft.AnimationCurve.EASE_OUT)
            )

        final_controls = []
        for i, (icon_off, icon_on, label) in enumerate(items):
            btn = create_nav_btn(i, icon_off, icon_on, label)
            if i == 2:
                wrapper = ft.Stack([btn, cart_badge_container])
                final_controls.append(wrapper)
                nav_button_controls.append(wrapper)
            elif i == 3:
                wrapper = ft.Stack([btn, lists_badge_container])
                final_controls.append(wrapper)
                nav_button_controls.append(wrapper)
            else:
                final_controls.append(btn)
                nav_button_controls.append(btn)

        main_row = ft.Row(controls=final_controls, alignment=ft.MainAxisAlignment.SPACE_EVENLY, spacing=0)
        main_row_ref[0] = main_row

        container = ft.Container(content=main_row, padding=ft.padding.symmetric(horizontal=10, vertical=5), animate=ft.Animation(300, ft.AnimationCurve.EASE_OUT))
        base_container_ref[0] = container

        refresh_navbar()

        return ft.Container(alignment=ft.alignment.center, content=container, padding=ft.padding.only(bottom=10))

    def on_nav_change(idx):
        if idx != 4:
            settings_refresh_ref[0] = None

        if idx == 0:
            content_area.content = get_home_view()
        elif idx == 1:
            content_area.content = get_search_view()
        elif idx == 2:
            content_area.content = get_cart_view()
        elif idx == 3:
            nonlocal selected_list_name
            selected_list_name = None
            content_area.content = get_lists_view()
        elif idx == 4:
            content_area.content = get_settings_view()
        content_area.update()

    def handle_resize(e):
        if navbar_ref[0]: navbar_ref[0]()

    page.on_resized = handle_resize

    nav_bar = build_custom_navbar(on_nav_change)

    background = ft.Container(expand=True, gradient=ft.LinearGradient(begin=ft.alignment.top_left, end=ft.alignment.bottom_right, colors=["background", "surfaceVariant"]))
    decorations = ft.Stack(controls=[
        ft.Container(width=300, height=300, bgcolor="primary", border_radius=150, top=-100, right=-50, blur=ft.Blur(100, 100, ft.BlurTileMode.MIRROR), opacity=0.15),
        ft.Container(width=200, height=200, bgcolor="tertiary", border_radius=100, bottom=100, left=-50, blur=ft.Blur(80, 80, ft.BlurTileMode.MIRROR), opacity=0.15)
    ])

    page.add(ft.Stack(expand=True, controls=[background, decorations, ft.Column(expand=True, spacing=0, controls=[content_area, nav_bar]), global_dismiss_layer, global_menu_card, toast_overlay_container]))

if __name__ == "__main__":
    ft.app(target=main)
