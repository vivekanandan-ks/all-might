import flet as ft
import json
import os
import random
import datetime
import subprocess
import re
from pathlib import Path
from constants import *

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
        self.nav_bar_height = 80
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

        # Quote Settings
        self.use_mastodon_quote = True
        self.quote_mastodon_account = "vivekanandanks"
        self.quote_mastodon_tag = "mha"
        self.quote_style_italic = True
        self.quote_style_bold = True
        self.mastodon_quote_cache = None
        self.last_fetched_quote = None

        # App Settings
        self.app_use_mastodon = False
        self.app_mastodon_account = ""
        self.app_mastodon_tag = ""
        self.app_mastodon_cache = None
        self.last_fetched_app = None

        # Tip Settings
        self.tip_use_mastodon = False
        self.tip_mastodon_account = ""
        self.tip_mastodon_tag = ""
        self.tip_mastodon_cache = None
        self.last_fetched_tip = None

        # Song Settings
        self.song_use_mastodon = False
        self.song_mastodon_account = ""
        self.song_mastodon_tag = ""
        self.song_mastodon_cache = None
        self.last_fetched_song = None

        self.installed_enrich_metadata = True
        self.auto_refresh_ui = False
        self.auto_refresh_interval = 10
        self.installed_items = {} # pname -> list of {'key': key, 'attrPath': attrPath}

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
            "nixos-unstable", "nixos-24.11", "nixos-24.05"
        ]
        self.active_channels = [
            "nixos-unstable", "nixos-24.11"
        ]
        self.cart_items = []
        self.favourites = []
        self.saved_lists = {}
        self.tracked_installs = {}
        self.load_settings()
        self.load_tracking()
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
                    self.nav_bar_height = data.get("nav_bar_height", 80)
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

                    self.use_mastodon_quote = data.get("use_mastodon_quote", True)
                    self.quote_mastodon_account = data.get("quote_mastodon_account", "vivekanandanks")
                    self.quote_mastodon_tag = data.get("quote_mastodon_tag", "mha")
                    self.quote_style_italic = data.get("quote_style_italic", True)
                    self.quote_style_bold = data.get("quote_style_bold", True)
                    self.last_fetched_quote = data.get("last_fetched_quote", None)

                    self.app_use_mastodon = data.get("app_use_mastodon", False)
                    self.app_mastodon_account = data.get("app_mastodon_account", "")
                    self.app_mastodon_tag = data.get("app_mastodon_tag", "")
                    self.last_fetched_app = data.get("last_fetched_app", None)

                    self.tip_use_mastodon = data.get("tip_use_mastodon", False)
                    self.tip_mastodon_account = data.get("tip_mastodon_account", "")
                    self.tip_mastodon_tag = data.get("tip_mastodon_tag", "")
                    self.last_fetched_tip = data.get("last_fetched_tip", None)

                    self.song_use_mastodon = data.get("song_use_mastodon", False)
                    self.song_mastodon_account = data.get("song_mastodon_account", "")
                    self.song_mastodon_tag = data.get("song_mastodon_tag", "")
                    self.last_fetched_song = data.get("last_fetched_song", None)

                    self.installed_enrich_metadata = data.get("installed_enrich_metadata", True)
                    self.auto_refresh_ui = data.get("auto_refresh_ui", False)
                    self.auto_refresh_interval = data.get("auto_refresh_interval", 10)

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
                "nav_bar_height": self.nav_bar_height,
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
                "use_mastodon_quote": self.use_mastodon_quote,
                "quote_mastodon_account": self.quote_mastodon_account,
                "quote_mastodon_tag": self.quote_mastodon_tag,
                "quote_style_italic": self.quote_style_italic,
                "quote_style_bold": self.quote_style_bold,
                "last_fetched_quote": self.last_fetched_quote,

                "app_use_mastodon": self.app_use_mastodon,
                "app_mastodon_account": self.app_mastodon_account,
                "app_mastodon_tag": self.app_mastodon_tag,
                "last_fetched_app": self.last_fetched_app,

                "tip_use_mastodon": self.tip_use_mastodon,
                "tip_mastodon_account": self.tip_mastodon_account,
                "tip_mastodon_tag": self.tip_mastodon_tag,
                "last_fetched_tip": self.last_fetched_tip,

                "song_use_mastodon": self.song_use_mastodon,
                "song_mastodon_account": self.song_mastodon_account,
                "song_mastodon_tag": self.song_mastodon_tag,
                "last_fetched_song": self.last_fetched_song,

                "installed_enrich_metadata": self.installed_enrich_metadata,
                "auto_refresh_ui": self.auto_refresh_ui,
                "auto_refresh_interval": self.auto_refresh_interval,

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

    # --- Tracking Logic ---
    def load_tracking(self):
        if os.path.exists(TRACKING_FILE):
            try:
                with open(TRACKING_FILE, 'r') as f:
                    self.tracked_installs = json.load(f)
            except Exception as e:
                print(f"Error loading tracking: {e}")
                self.tracked_installs = {}

    def save_tracking(self):
        try:
            Path(CONFIG_DIR).mkdir(parents=True, exist_ok=True)
            with open(TRACKING_FILE, 'w') as f:
                json.dump(self.tracked_installs, f, indent=4)
        except Exception as e:
            print(f"Error saving tracking: {e}")

    def _get_track_key(self, pname, channel):
        return f"{pname}::{channel}"

    def track_install(self, pname, channel):
        key = self._get_track_key(pname, channel)
        self.tracked_installs[key] = {
            "pname": pname,
            "channel": channel,
            "installed_at": datetime.datetime.now().isoformat()
        }
        self.save_tracking()

    def untrack_install(self, pname, channel):
        key = self._get_track_key(pname, channel)
        if key in self.tracked_installs:
            del self.tracked_installs[key]
            self.save_tracking()

    def is_tracked(self, pname, channel):
        # We might need fuzzy matching if channel versions differ slightly, 
        # but for now strict match on what we installed.
        key = self._get_track_key(pname, channel)
        return key in self.tracked_installs

    def get_tracked_channel(self, pname):
        # Check if pname is tracked under any channel
        # Keys are "pname::channel"
        search_prefix = f"{pname}::"
        for key in self.tracked_installs:
            if key == pname or key.startswith(search_prefix):
                # Found it
                parts = key.split("::")
                if len(parts) >= 2:
                    return parts[1]
                return "unknown"
        return None

    # --- Cache Logic ---
    def refresh_installed_cache(self):
        try:
            result = subprocess.run(
                ["nix", "profile", "list", "--json"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            if result.returncode != 0:
                return
            
            data = json.loads(result.stdout)
            elements = data.get("elements", {})
            new_items = {}
            
            for key, info in elements.items():
                store_paths = info.get("storePaths", [])
                attr_path = info.get("attrPath", "")
                if not store_paths:
                    continue
                
                basename = os.path.basename(store_paths[0])
                # Remove hash (32 chars) + dash
                if len(basename) > 33 and basename[32] == '-':
                    rest = basename[33:]
                else:
                    rest = basename

                # Split name and version
                match = re.search(r'-(\d)', rest)
                if match:
                    name = rest[:match.start()]
                else:
                    name = rest
                
                if name not in new_items:
                    new_items[name] = []
                new_items[name].append({'key': key, 'attrPath': attr_path})
            
            self.installed_items = new_items
        except Exception as e:
            print(f"Error refreshing cache: {e}")

    def is_package_installed(self, pname, search_attr_name=None):
        if pname not in self.installed_items:
            return False
        
        if not search_attr_name:
            return True
            
        installed_list = self.installed_items[pname]
        for item in installed_list:
            attr = item['attrPath']
            if not attr: continue
            # Check suffix
            if attr.endswith(f".{search_attr_name}") or attr == search_attr_name:
                return True
        return False

    def get_element_key(self, pname):
        # Return the first element key found for this pname
        if pname in self.installed_items and self.installed_items[pname]:
            return self.installed_items[pname][0]['key']
        return None

state = AppState()
state.refresh_installed_cache()
