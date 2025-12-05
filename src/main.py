import flet as ft
import subprocess
import json
import os
import shlex
import threading
import time
from collections import Counter
from pathlib import Path

# --- Constants ---
APP_NAME = "All Might"
CONFIG_DIR = os.path.expanduser("~/.config/all-might")
CONFIG_FILE = os.path.join(CONFIG_DIR, "settings.json")

# --- Global Callback Reference ---
# This allows the card classes to call a function defined in main()
global_open_menu_func = None

# --- State Management ---
class AppState:
    def __init__(self):
        self.username = "user"
        self.default_channel = "nixos-24.11"
        self.font_size = 14  # Default font size
        self.confirm_timer = 5 # Default countdown for confirmation dialog
        self.undo_timer = 5    # Default countdown for undo toast
        self.nav_badge_size = 20 # Default size for nav badges
        self.theme_mode = "dark"
        self.theme_color = "blue"

        # New Features
        self.search_limit = 30 # Default search limit

        # Nav Bar Settings
        self.floating_nav = True # Now acts as "Always Floating" if adaptive is off
        self.adaptive_nav = True # New: Toggle for adaptive behavior
        self.nav_radius = 33 # Default to 33 as requested
        self.glass_nav = True
        self.nav_bar_width = 410 # Default length 410 as requested
        self.nav_icon_spacing = 15 # Default spacing
        self.sync_nav_spacing = True # Default sync enabled

        # History
        self.recent_activity = [] # List of {package, channel}

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
        self.favourites = [] # List of favorite items
        self.saved_lists = {} # Format: { "list_name": [item1, item2] }
        self.load_settings()

    def load_settings(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r') as f:
                    data = json.load(f)
                    self.username = data.get("username", "user")
                    self.default_channel = data.get("default_channel", self.default_channel)
                    self.font_size = data.get("font_size", 14)
                    self.theme_mode = data.get("theme_mode", "dark")
                    self.theme_color = data.get("theme_color", "blue")

                    legacy_timer = data.get("countdown_timer", 5)
                    self.confirm_timer = data.get("confirm_timer", legacy_timer)
                    self.undo_timer = data.get("undo_timer", legacy_timer)

                    self.nav_badge_size = data.get("nav_badge_size", 20)

                    # New Features
                    self.search_limit = data.get("search_limit", 30)
                    self.floating_nav = data.get("floating_nav", True)
                    self.adaptive_nav = data.get("adaptive_nav", True)
                    self.nav_radius = data.get("nav_radius", 33)
                    self.glass_nav = data.get("glass_nav", True)
                    self.nav_bar_width = data.get("nav_bar_width", 410)
                    self.nav_icon_spacing = data.get("nav_icon_spacing", 15)
                    self.sync_nav_spacing = data.get("sync_nav_spacing", True)

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
                "font_size": self.font_size,
                "theme_mode": self.theme_mode,
                "theme_color": self.theme_color,
                "confirm_timer": self.confirm_timer,
                "undo_timer": self.undo_timer,
                "nav_badge_size": self.nav_badge_size,
                "search_limit": self.search_limit,
                "floating_nav": self.floating_nav,
                "adaptive_nav": self.adaptive_nav,
                "nav_radius": self.nav_radius,
                "glass_nav": self.glass_nav,
                "nav_bar_width": self.nav_bar_width,
                "nav_icon_spacing": self.nav_icon_spacing,
                "sync_nav_spacing": self.sync_nav_spacing,
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

    # --- History Logic ---
    def add_to_history(self, package, channel):
        # Prevent duplicates by ID, move to top
        pkg_id = self._get_pkg_id(package)

        # Remove if exists
        self.recent_activity = [
            item for item in self.recent_activity
            if self._get_pkg_id(item['package']) != pkg_id or item['channel'] != channel
        ]

        # Add to front
        self.recent_activity.insert(0, {'package': package, 'channel': channel})

        # Keep max 5
        self.recent_activity = self.recent_activity[:5]
        self.save_settings()

    def clear_history(self):
        self.recent_activity = []
        self.save_settings()

    # --- Favourites Logic ---
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

    # --- List Membership Logic ---
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
            return # Should not happen

        pkg_id = self._get_pkg_id(pkg)
        items = self.saved_lists[list_name]

        # Check if exists
        idx = -1
        for i, item in enumerate(items):
             if self._get_pkg_id(item['package']) == pkg_id and item['channel'] == channel:
                 idx = i
                 break

        if idx >= 0:
            # Remove
            del items[idx]
            msg = f"Removed from {list_name}"
        else:
            # Add
            items.append({'package': pkg, 'channel': channel})
            msg = f"Added to {list_name}"

        self.saved_lists[list_name] = items
        self.save_settings()
        return msg

    def get_base_color(self):
        # Helper to get a safe color for opacity operations
        return ft.Colors.WHITE if self.theme_mode == "dark" else ft.Colors.BLACK

state = AppState()

# --- Logic: Search ---

def execute_nix_search(query, channel):
    if not query:
        return []

    # UPDATED: Use the configurable search limit
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
            # Use pname and version for unique display signature
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
    def __init__(self, content, opacity=0.1, blur_sigma=10, border_radius=15, **kwargs):
        bg_color = kwargs.pop("bgcolor", None)

        if bg_color is None:
             # Manual opacity application since we can't use string literals with with_opacity
             base = state.get_base_color()
             bg_color = ft.Colors.with_opacity(opacity, base)

        if "border" not in kwargs:
            border_col = ft.Colors.with_opacity(0.2, state.get_base_color())
            kwargs["border"] = ft.border.all(1, border_col)

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
    def __init__(self, icon, text, url, color_group, text_size=12):
        # Use theme-aware or hardcoded safe colors
        base_col = state.get_base_color()

        super().__init__(
            content=ft.Row([ft.Icon(icon, size=text_size+2, color=color_group[0]), ft.Text(text, size=text_size, color=color_group[1])], spacing=5, alignment=ft.MainAxisAlignment.START),
            on_click=lambda _: os.system(f"xdg-open {url}") if url else None,
            on_hover=self.on_hover,
            tooltip=url,
            ink=True,
            border_radius=5,
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

# --- Custom Undo Toast Control ---
class UndoToast(ft.Container):
    def __init__(self, message, on_undo, duration_seconds=5, on_timeout=None):
        self.duration_seconds = duration_seconds
        self.on_undo = on_undo
        self.on_timeout = on_timeout
        self.cancelled = False

        # UI Components
        self.counter_text = ft.Text(str(duration_seconds), size=12, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE)
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
                        ft.Text(message, color=ft.Colors.WHITE, weight=ft.FontWeight.W_500, size=14)
                    ]
                ),
                ft.TextButton(
                    content=ft.Row([ft.Icon(ft.Icons.UNDO, size=18), ft.Text("UNDO", weight=ft.FontWeight.BOLD)], spacing=5),
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

        # Final step
        if not self.cancelled:
            self.progress_ring.value = 0
            self.counter_text.value = "0"
            self.update()
            time.sleep(0.5) # Short pause at 0
            if self.on_timeout:
                self.on_timeout()

    def handle_undo(self, e):
        self.cancelled = True
        if self.on_undo:
            self.on_undo()

show_toast_global = None
show_undo_toast_global = None

# Reverted to GlassContainer inheritance since Menu is now global
class NixPackageCard(GlassContainer):
    def __init__(self, package_data, page_ref, initial_channel, on_cart_change=None, is_cart_view=False, show_toast_callback=None, on_menu_open=None):
        self.pkg = package_data
        self.page_ref = page_ref
        self.on_cart_change = on_cart_change
        self.is_cart_view = is_cart_view
        self.show_toast = show_toast_callback
        self.on_menu_open = on_menu_open # No longer used but kept for signature compatibility

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

        # Fonts (Use theme-aware colors)
        base_size = state.font_size
        text_col = "onSurfaceVariant"

        self.channel_text = ft.Text(f"{self.version} ({self.selected_channel})", size=base_size - 3, color=text_col)
        channel_menu_items = [ft.PopupMenuItem(text=ch, on_click=self.change_channel, data=ch) for ch in state.active_channels]

        # Fix opacity on theme color string by using helper
        border_col = ft.Colors.with_opacity(0.3, state.get_base_color())

        self.channel_selector = ft.Container(
            padding=ft.padding.symmetric(horizontal=8, vertical=4),
            border_radius=6,
            border=ft.border.all(1, border_col),
            content=ft.Row(spacing=4, controls=[self.channel_text, ft.Icon(ft.Icons.ARROW_DROP_DOWN, color=text_col, size=14)]),
        )
        self.channel_dropdown = ft.PopupMenuButton(content=self.channel_selector, items=channel_menu_items, tooltip="Select Channel")

        # --- Combined Action Buttons ---
        self.try_btn_icon = ft.Icon(ft.Icons.PLAY_ARROW, size=16, color=ft.Colors.WHITE)
        self.try_btn_text = ft.Text("Run without installing", weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE, size=base_size - 2)

        self.try_btn = ft.Container(
            padding=ft.padding.symmetric(horizontal=12, vertical=8),
            content=ft.Row(spacing=6, controls=[self.try_btn_icon, self.try_btn_text], alignment=ft.MainAxisAlignment.CENTER),
            on_click=lambda e: self.run_action(),
            bgcolor=ft.Colors.TRANSPARENT,
            ink=True,
            tooltip="" # Will be updated dynamically
        )

        self.copy_btn = ft.IconButton(
            icon=ft.Icons.CONTENT_COPY,
            icon_color=ft.Colors.WHITE70,
            tooltip="Copy Command",
            on_click=self.copy_command,
            icon_size=16,
            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=0))
        )

        self.action_menu = ft.PopupMenuButton(
            icon=ft.Icons.ARROW_DROP_DOWN, icon_color=ft.Colors.WHITE70,
            items=[
                ft.PopupMenuItem(text="Run without installing", icon=ft.Icons.PLAY_ARROW, on_click=lambda e: self.set_mode_and_update_ui("direct")),
                ft.PopupMenuItem(text="Try in a shell", icon=ft.Icons.TERMINAL, on_click=lambda e: self.set_mode_and_update_ui("shell")),
            ]
        )

        # Unified Action Bar: [Try (Full Text)] | [Menu] | [Copy]
        self.unified_action_bar = ft.Container(
            bgcolor=ft.Colors.BLUE_700, border_radius=8,
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
            icon_size=20
        )
        self.update_cart_btn_state()

        # --- List Management Inline UI ---
        self.list_badge_count = ft.Text("0", size=9, color=ft.Colors.WHITE, weight=ft.FontWeight.BOLD)
        self.list_badge = ft.Container(
            content=self.list_badge_count,
            bgcolor=ft.Colors.RED_500, width=14, height=14, border_radius=7,
            alignment=ft.alignment.center, visible=False
        )

        # --- Lists Button (Calls Global Menu) ---
        self.lists_btn = ft.GestureDetector(
            mouse_cursor=ft.MouseCursor.CLICK,
            on_tap_up=self.trigger_global_menu,
            content=ft.Container(
                bgcolor=ft.Colors.TRANSPARENT,
                padding=8,
                border_radius=50,
                content=ft.Icon(ft.Icons.PLAYLIST_ADD, size=20, color="onSurface"),
            )
        )

        self.lists_btn_container = ft.Container(
            content=ft.Stack([
                self.lists_btn,
                ft.Container(content=self.list_badge, top=2, right=2)
            ]),
        )
        self.refresh_lists_state() # Update badge

        # --- Favourite Button ---
        self.fav_btn = ft.IconButton(
            icon=ft.Icons.FAVORITE_BORDER,
            icon_color="onSurface",
            selected_icon=ft.Icons.FAVORITE,
            selected_icon_color=ft.Colors.RED_500,
            on_click=self.toggle_favourite,
            tooltip="Toggle Favourite",
            icon_size=20
        )
        self.update_fav_btn_state()

        tag_color = ft.Colors.BLUE_GREY_700 if self.attr_set == "No package set" else ft.Colors.TEAL_700
        self.tag_chip = ft.Container(
            padding=ft.padding.symmetric(horizontal=6, vertical=2),
            border_radius=8,
            bgcolor=ft.Colors.with_opacity(0.5, tag_color),
            content=ft.Text(self.attr_set, size=base_size - 5, color=ft.Colors.WHITE, weight=ft.FontWeight.BOLD),
            visible=bool(self.attr_set)
        )

        # --- Footer Items (Horizontal - 1x4 style) ---
        footer_size = base_size - 3
        # Colors need to be readable on both light and dark. We use theme colors or specific dark variants.

        footer_items = [
            ft.Container(content=ft.Row([ft.Icon(ft.Icons.VERIFIED_USER_OUTLINED, size=14, color=ft.Colors.GREEN), ft.Text(license_text, size=footer_size, color=ft.Colors.GREEN)], spacing=4), padding=ft.padding.symmetric(horizontal=4))
        ]
        if programs_str:
            footer_items.append(ft.Container(content=ft.Row([ft.Icon(ft.Icons.TERMINAL, size=14, color=ft.Colors.ORANGE), ft.Text(f"Bins: {programs_str}", size=footer_size, color=ft.Colors.ORANGE, no_wrap=True, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS)], spacing=4), padding=ft.padding.symmetric(horizontal=4)))
        if homepage_url:
            footer_items.append(HoverLink(ft.Icons.LINK, "Homepage", homepage_url, (ft.Colors.BLUE, ft.Colors.BLUE), text_size=footer_size))
        if source_url:
            footer_items.append(HoverLink(ft.Icons.CODE, "Source", source_url, (ft.Colors.PURPLE, ft.Colors.PURPLE), text_size=footer_size))

        content = ft.Column(
            spacing=4,
            controls=[
                # Top Row: Title, Tag, Channel
                ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    controls=[
                        ft.Column(spacing=2, controls=[
                            ft.Row([
                                ft.Text(self.pname, weight=ft.FontWeight.BOLD, size=base_size + 2, color="onSurface"),
                                self.tag_chip
                            ]),
                        ]),
                        # Action Row
                        ft.Row(spacing=5, controls=[
                            self.channel_dropdown, # Moved to action row
                            self.unified_action_bar,
                            self.lists_btn_container,
                            self.fav_btn,
                            self.cart_btn
                        ])
                    ]
                ),
                # Description
                ft.Container(content=ft.Text(description, size=base_size - 1, color="onSurfaceVariant", no_wrap=False, max_lines=2, overflow=ft.TextOverflow.ELLIPSIS), padding=ft.padding.only(bottom=5)),
                # Horizontal Footer - 1x4 Style
                ft.Container(
                    bgcolor=ft.Colors.with_opacity(0.05, state.get_base_color()), border_radius=6, padding=4,
                    content=ft.Row(wrap=False, scroll=ft.ScrollMode.HIDDEN, controls=footer_items, spacing=10)
                )
            ]
        )
        super().__init__(content=content, padding=12, opacity=0.15)
        self.update_copy_tooltip() # Set initial tooltip

    def refresh_lists_state(self):
        # Update Badge
        containing_lists = state.get_containing_lists(self.pkg, self.selected_channel)
        count = len(containing_lists)
        self.list_badge_count.value = str(count)
        self.list_badge.visible = count > 0
        if self.list_badge.page: self.list_badge.update()

    def trigger_global_menu(self, e):
        # Trigger the global menu function defined in main()
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
        # HISTORY LOGIC
        state.add_to_history(self.pkg, self.selected_channel)

        action = state.toggle_favourite(self.pkg, self.selected_channel)
        self.update_fav_btn_state()

        if action == "removed":
            if self.on_cart_change: self.on_cart_change() # Refresh view if we are in favourites

            def on_undo():
                state.toggle_favourite(self.pkg, self.selected_channel) # Add back
                self.update_fav_btn_state()
                if self.on_cart_change: self.on_cart_change() # Refresh view again

            if show_undo_toast_global:
                show_undo_toast_global("Removed from favourites", on_undo)
        else:
            if self.show_toast: self.show_toast("Added to favourites")

    def handle_cart_click(self, e):
        # HISTORY LOGIC
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
            self.update_fav_btn_state() # Update fav state for new channel
            self.refresh_lists_state() # Refresh lists state for new channel/version
            self.update_copy_tooltip() # Update tooltip with new version
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
        self.update_copy_tooltip() # Update tooltip on mode change

    def _generate_nix_command(self, with_wrapper=True):
        target = f"nixpkgs/{self.selected_channel}#{self.pname}"
        core_cmd = ""

        if self.run_mode == "direct":
            core_cmd = f"nix run {target}"
        elif self.run_mode == "shell":
            core_cmd = f"nix shell {target}"

        # Apply wrapper to both modes if requested
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
        # HISTORY LOGIC
        state.add_to_history(self.pkg, self.selected_channel)

        cmd = self._generate_nix_command(with_wrapper=False)
        self.page_ref.set_clipboard(cmd)
        if self.show_toast: self.show_toast(f"Copied: {cmd}")

    def run_action(self):
        # HISTORY LOGIC
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

    # Apply initial theme settings
    page.theme_mode = ft.ThemeMode.DARK if state.theme_mode == "dark" else (ft.ThemeMode.LIGHT if state.theme_mode == "light" else ft.ThemeMode.SYSTEM)
    page.theme = ft.Theme(color_scheme_seed=state.theme_color)

    page.padding = 0
    page.window_width = 400
    page.window_height = 800

    current_results = []
    active_filters = set()
    pending_filters = set()

    # --- UI Persistence State ---
    # Keeps track of which settings tile is open to restore it after theme reload
    settings_ui_state = {"expanded_tile": None}

    # --- Global Menu Logic ---
    # We use a global stack layer for the menu to ensure it's always on top and handles dismissal correctly.

    # 1. The Menu Container
    global_menu_card = ft.Container(
        visible=False,
        bgcolor="#252525",
        border_radius=12,
        padding=10,
        width=200,
        top=0, left=0, # Will be set dynamically
        border=ft.border.all(1, ft.Colors.with_opacity(0.2, ft.Colors.WHITE)),
        shadow=ft.BoxShadow(
            spread_radius=1, blur_radius=10,
            color=ft.Colors.with_opacity(0.5, ft.Colors.BLACK), offset=ft.Offset(0, 5)
        ),
        content=ft.Column(spacing=5, tight=True, scroll=ft.ScrollMode.AUTO),
        animate_opacity=150,
        opacity=0
    )

    # 2. The Dismiss Layer (Transparent, behind menu, covers screen)
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
        # Calculate Position
        # e.global_x/y are the click coordinates. We position the menu relative to that.
        # We shift X to the left to align the right side of menu near the click.
        menu_x = e.global_x - 180
        menu_y = e.global_y + 10

        # Boundary checks (simple)
        if menu_x < 10: menu_x = 10
        if menu_y + 200 > page.height: menu_y = page.height - 210

        global_menu_card.left = menu_x
        global_menu_card.top = menu_y

        # Populate Content
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

        # Show
        global_dismiss_layer.visible = True
        global_menu_card.visible = True
        global_menu_card.opacity = 1
        page.update()

    # Assign to global variable for Cards to use
    global global_open_menu_func
    global_open_menu_func = open_global_menu

    # --- Custom Toast Logic ---
    toast_overlay_container = ft.Container(bottom=90, left=0, right=0, alignment=ft.alignment.center, visible=False)
    current_toast_token = [0] # Use a list to be mutable

    def show_toast(message):
        current_toast_token[0] += 1
        my_token = current_toast_token[0]

        # Basic Toast
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

        # Animate in
        t_container.opacity = 1
        t_container.update()

        def hide():
            time.sleep(2.0)
            if current_toast_token[0] != my_token: return # Overridden by newer toast

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

        # Create UndoToast component
        undo_duration = state.undo_timer # Use setting

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

    # --- Helper: Destructive Action Dialog with Timer ---
    def show_destructive_dialog(title, content_text, on_confirm):
        duration = state.confirm_timer # Use setting

        # Start colorless (Grey)
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
            page.close(dlg) # Close dialog first
            on_confirm(e)   # Then execute logic

        cancel_btn.on_click = close_dlg

        def timer_logic():
            for i in range(duration, 0, -1):
                # Ensure dialog is still open
                if not dlg.open: return
                confirm_btn.text = f"Yes ({i}s)"
                confirm_btn.update()
                time.sleep(1)

            if dlg.open:
                confirm_btn.text = "Yes"
                confirm_btn.disabled = False
                confirm_btn.bgcolor = ft.Colors.RED_700 # Turn Red only when active
                confirm_btn.color = ft.Colors.WHITE
                confirm_btn.on_click = handle_confirm
                confirm_btn.update()

        page.open(dlg)
        threading.Thread(target=timer_logic, daemon=True).start()

    # --- UI Elements ---
    results_column = ft.Column(spacing=10, scroll=ft.ScrollMode.HIDDEN, expand=True)

    # -- Cart UI Elements (Pinned Header) --
    cart_list = ft.Column(spacing=10, scroll=ft.ScrollMode.HIDDEN, expand=True)

    cart_header_title = ft.Text("Your Cart (0 items)", size=24, weight=ft.FontWeight.W_900, color="onSurface")

    # Header Buttons
    cart_header_save_btn = ft.ElevatedButton("Save cart as list", icon=ft.Icons.ADD, bgcolor=ft.Colors.TEAL_700, color=ft.Colors.WHITE)
    cart_header_clear_btn = ft.IconButton(ft.Icons.DELETE_SWEEP, tooltip="Clear Cart", icon_color=ft.Colors.RED_400)

    # Unified Cart Shell Button (Similar to App UI)
    cart_header_shell_btn_container = ft.Container(
        padding=ft.padding.symmetric(horizontal=12, vertical=8),
        content=ft.Row(spacing=6, controls=[ft.Icon(ft.Icons.TERMINAL, size=16, color=ft.Colors.WHITE), ft.Text("Try Cart in Shell", weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE, size=12)]),
        on_click=lambda e: run_cart_shell(e),
        ink=True
    )

    cart_header_copy_btn = ft.IconButton(ft.Icons.CONTENT_COPY, icon_color=ft.Colors.WHITE70, tooltip="Copy Command", on_click=lambda e: copy_cart_command(e), icon_size=16, style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=0)))

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

    search_field = ft.TextField(hint_text="Search packages...", border=ft.InputBorder.NONE, hint_style=ft.TextStyle(color="onSurfaceVariant"), text_style=ft.TextStyle(color="onSurface"), expand=True)

    filter_badge_count = ft.Text("0", size=10, color=ft.Colors.WHITE, weight=ft.FontWeight.BOLD)
    filter_badge_container = ft.Container(content=filter_badge_count, bgcolor=ft.Colors.RED_500, width=16, height=16, border_radius=8, alignment=ft.alignment.center, visible=False, top=0, right=0)

    # FIXED CART BADGE: Ensure stack has room by placing it inside a container with padding/margin logic if needed
    # Size depends on settings
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

    filter_dismiss_layer = ft.Container(expand=True, visible=False, on_click=lambda e: toggle_filter_menu(False), bgcolor=ft.Colors.with_opacity(0.01, ft.Colors.BLACK))
    filter_list_col = ft.Column(scroll=ft.ScrollMode.AUTO)
    filter_menu = GlassContainer(visible=False, width=300, height=350, top=60, right=50, padding=15, border=ft.border.all(1, "outline"), content=ft.Column([ft.Text("Filter by Package Set", weight=ft.FontWeight.BOLD, size=16, color="onSurface"), ft.Divider(height=10, color="outline"), ft.Container(expand=True, content=filter_list_col), ft.Row(alignment=ft.MainAxisAlignment.END, controls=[ft.TextButton("Close", on_click=lambda e: toggle_filter_menu(False)), ft.ElevatedButton("Apply", on_click=lambda e: apply_filters())])]))

    # --- Lists View State & Components ---
    selected_list_name = None
    is_viewing_favourites = False # Special flag
    lists_main_col = ft.Column(scroll=ft.ScrollMode.HIDDEN, expand=True)
    list_detail_col = ft.Column(scroll=ft.ScrollMode.HIDDEN, expand=True)

    # --- New Lists Badge ---
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
        # Read current size from state
        sz = state.nav_badge_size
        radius = sz / 2
        font_sz = max(8, sz / 2) # Heuristic

        # Update Cart Badge
        cart_badge_container.width = sz
        cart_badge_container.height = sz
        cart_badge_container.border_radius = radius
        cart_badge_count.size = font_sz

        # Update Lists Badge
        lists_badge_container.width = sz
        lists_badge_container.height = sz
        lists_badge_container.border_radius = radius
        lists_badge_count.size = font_sz

        if cart_badge_container.page: cart_badge_container.update()
        if lists_badge_container.page: lists_badge_container.update()

    # --- Cart & List Logic ---

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
            title = f"List: {selected_list_name}"

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
        cmd = _build_shell_command_for_items(items, with_wrapper=False)
        page.set_clipboard(cmd)
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
            update_lists_badge() # Update badge on save
            show_toast(f"Saved list: {name}")
            page.close(dlg_ref[0])
            # Refresh card list menus in current view if any
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

        backup_items = list(state.cart_items) # Deep copy not strictly needed if items are dicts, list copy is enough

        def do_clear(e):
            state.clear_cart()
            on_global_cart_change()

            def on_undo():
                state.restore_cart(backup_items)
                on_global_cart_change()

            show_undo_toast("Cart cleared", on_undo)

        show_destructive_dialog("Clear Cart?", "Remove all items from cart?", do_clear)

    # Wire up buttons
    cart_header_save_btn.on_click = save_cart_as_list
    cart_header_clear_btn.on_click = clear_all_cart

    # --- Actions ---

    def update_cart_badge():
        count = len(state.cart_items)
        cart_badge_count.value = str(count)
        if cart_badge_container.page:
            cart_badge_container.visible = count > 0
            cart_badge_container.update()

    def on_global_cart_change():
        update_cart_badge()
        # If we are in cart view, refresh it
        if cart_list.page: refresh_cart_view(update_ui=True)
        # If we are in detail list view, refresh it to update "add/remove" button states on cards
        if list_detail_col.page: refresh_list_detail_view(update_ui=True)

    def refresh_cart_view(update_ui=False):
        total_items = len(state.cart_items)

        # Update Header Logic
        cart_header_title.value = f"Your Cart ({total_items} items)"

        # Update copy tooltip
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

        # Update List Logic
        cart_list.controls.clear()
        if not state.cart_items:
            cart_list.controls.append(ft.Container(content=ft.Text("Your cart is empty.", color="onSurface"), alignment=ft.alignment.center, padding=20))
        else:
            for item in state.cart_items:
                pkg_data = item['package']
                saved_channel = item['channel']
                # Pass on_menu_open callback
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
                # Pass on_menu_open callback
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

    # -- Lists Logic --

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
        backup_items = state.saved_lists.get(name, []) # Backup

        def do_delete(e):
            nonlocal selected_list_name # FIXED: Moved to top
            state.delete_list(name)
            update_lists_badge() # Update badge on delete
            refresh_lists_main_view(update_ui=True)

            # If we are deleting the list we are currently viewing, go back to index
            if selected_list_name == name:
                selected_list_name = None
                content_area.content = get_lists_view()
                content_area.update()

            def on_undo():
                state.restore_list(name, backup_items)
                update_lists_badge() # Update badge on undo
                refresh_lists_main_view(update_ui=True)
                # Note: We don't auto-navigate back to the restored list to avoid jarring UI changes

            show_undo_toast(f"Deleted: {name}", on_undo)

        show_destructive_dialog("Delete List?", f"Are you sure you want to delete '{name}'?", do_delete)

    def refresh_lists_main_view(update_ui=False):
        lists_main_col.controls.clear()

        # --- Favourites Section ---
        fav_count = len(state.favourites)
        if fav_count > 0:
            pkgs_preview = ", ".join([i['package'].get('package_pname', '?') for i in state.favourites[:3]])
            if fav_count > 3: pkgs_preview += "..."
            preview_text = f"{fav_count} packages - {pkgs_preview}"
        else:
            preview_text = "No apps in favourites"

        fav_card = GlassContainer(
            opacity=0.15, padding=15, ink=True, on_click=lambda e: open_list_detail("Favourites", is_fav=True),
            border=ft.border.all(1, ft.Colors.PINK_400), # Highlight border
            content=ft.Row(
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                controls=[
                    ft.Column([
                        ft.Row([ft.Icon(ft.Icons.FAVORITE, color=ft.Colors.PINK_400), ft.Text("Favourites", size=18, weight=ft.FontWeight.BOLD, color="onSurface")]),
                        ft.Text(preview_text, size=12, color="onSurfaceVariant", no_wrap=True)
                    ], expand=True),
                    ft.Icon(ft.Icons.ARROW_FORWARD_IOS, size=14, color="onSurfaceVariant")
                ]
            )
        )
        lists_main_col.controls.append(fav_card)
        lists_main_col.controls.append(ft.Container(height=10)) # Spacer

        # --- Saved Lists Section ---
        if not state.saved_lists:
             lists_main_col.controls.append(ft.Container(content=ft.Text("No custom lists created yet.", color="onSurfaceVariant"), alignment=ft.alignment.center, padding=20))
        else:
            # Sort lists alphabetically
            sorted_lists = sorted(state.saved_lists.items(), key=lambda x: x[0].lower())

            for name, items in sorted_lists:
                count = len(items)
                pkgs_preview = ", ".join([i['package'].get('package_pname', '?') for i in items[:3]])
                if len(items) > 3: pkgs_preview += "..."

                # Merged line format
                display_text = f"{count} packages - {pkgs_preview}"

                # The main card content (clickable to open list)
                info_col = ft.Column([
                    ft.Text(name, size=18, weight=ft.FontWeight.BOLD, color="onSurface"),
                    ft.Text(display_text, size=12, color=ft.Colors.TEAL_200, no_wrap=True)
                ], expand=True)

                card_content = ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    controls=[
                        # Wrap info in a Container to make JUST this part clickable for navigation
                        ft.Container(content=info_col, expand=True, on_click=lambda e, n=name: open_list_detail(n)),
                        # Separate delete button (not wrapped in the nav container)
                        ft.IconButton(ft.Icons.DELETE_OUTLINE, icon_color=ft.Colors.RED_300, data=name, on_click=delete_saved_list)
                    ]
                )

                card = GlassContainer(
                    opacity=0.1, padding=15,
                    content=card_content
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
                # Pass on_menu_open callback
                list_detail_col.controls.append(NixPackageCard(pkg_data, page, saved_channel, on_cart_change=on_global_cart_change, is_cart_view=True, show_toast_callback=show_toast, on_menu_open=None))

        if update_ui and list_detail_col.page: list_detail_col.update()

    def get_home_view():
        # -- Recent Activity Section --
        recent_activity_row = ft.Row(scroll=ft.ScrollMode.HIDDEN, spacing=10)

        def show_pkg_details_dialog(item):
            # Create a simplified dialog showing the package card
            pkg = item['package']
            channel = item['channel']

            # Using NixPackageCard in a dialog might be large, but it's consistent
            # We need to pass None for on_menu_open since it's not in a list context essentially
            card = NixPackageCard(pkg, page, channel, show_toast_callback=show_toast)

            dlg = ft.AlertDialog(
                content=ft.Container(width=400, content=card, padding=0),
                content_padding=0,
                bgcolor=ft.Colors.TRANSPARENT, # Let card handle bg
            )
            page.open(dlg)

        if not state.recent_activity:
            pass # Don't show anything if empty, as requested to be clean
        else:
            for item in state.recent_activity:
                pkg = item['package']
                pname = pkg.get("package_pname", "Unknown")

                # Small card for recent item
                recent_card = GlassContainer(
                    width=140, height=80, padding=10, opacity=0.1,
                    on_click=lambda e, i=item: show_pkg_details_dialog(i),
                    content=ft.Column(
                        alignment=ft.MainAxisAlignment.CENTER,
                        spacing=2,
                        controls=[
                            ft.Icon(ft.Icons.HISTORY, size=16, color=ft.Colors.BLUE_200),
                            ft.Text(pname, weight=ft.FontWeight.BOLD, size=12, no_wrap=True, overflow=ft.TextOverflow.ELLIPSIS, text_align=ft.TextAlign.CENTER),
                            ft.Text(item['channel'], size=9, color="onSurfaceVariant", no_wrap=True, overflow=ft.TextOverflow.ELLIPSIS)
                        ]
                    )
                )
                recent_activity_row.controls.append(recent_card)

        # Removed clear history button and title row to keep it minimal as requested in cleanup
        # Recent items will just appear below welcome text if they exist

        return ft.Container(
            expand=True,
            alignment=ft.alignment.center,
            content=ft.Column(
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                alignment=ft.MainAxisAlignment.CENTER,
                controls=[
                      ft.Icon(ft.Icons.HOME_FILLED, size=60, color=ft.Colors.BLUE_200),
                      ft.Text(f"Hello, {state.username}!", size=32, weight=ft.FontWeight.W_900, color="onSurface"),
                      ft.Text("Welcome to All Might", size=16, color="onSurfaceVariant"),
                      ft.Container(height=30),
                      # Only show row if has content
                      ft.Container(
                          content=recent_activity_row,
                          height=100 if state.recent_activity else 0,
                      )
                ]
            )
        )

    def get_search_view():
        return ft.Stack(
            expand=True,
            controls=[
                ft.Column(
                    expand=True,
                    controls=[
                        ft.Text("Search", size=32, weight=ft.FontWeight.W_900, color="onSurface"),
                        GlassContainer(opacity=0.15, padding=5, content=ft.Row(controls=[channel_dropdown, ft.Container(width=1, height=30, bgcolor="outlineVariant"), search_field, ft.Stack(controls=[ft.IconButton(icon=ft.Icons.FILTER_LIST, icon_color="onSurface", tooltip="Filter", on_click=lambda e: toggle_filter_menu(not filter_menu.visible)), filter_badge_container]), ft.IconButton(icon=ft.Icons.SEARCH, icon_color="onSurface", on_click=perform_search)])),
                        ft.Container(padding=ft.padding.only(left=10), content=result_count_text),
                        results_column
                    ]
                ),
                filter_dismiss_layer, filter_menu
            ]
        )

    def get_cart_view():
        refresh_cart_view(update_ui=False)
        return ft.Column(
            expand=True,
            spacing=0,
            controls=[
                cart_header, # Pinned at top
                cart_list    # Scrollable
            ]
        )

    def get_lists_view():
        if selected_list_name is None:
            # Index View
            refresh_lists_main_view(update_ui=False)
            total_lists = len(state.saved_lists)
            return ft.Column(
                expand=True,
                controls=[
                    ft.Text(f"Saved Lists ({total_lists})", size=32, weight=ft.FontWeight.W_900, color="onSurface"),
                    lists_main_col
                ]
            )
        else:
            # Detail View
            refresh_list_detail_view(update_ui=False)

            items = []
            if is_viewing_favourites:
                items = state.favourites
            elif selected_list_name in state.saved_lists:
                items = state.saved_lists[selected_list_name]

            item_count = len(items)
            display_name = "Favourites" if is_viewing_favourites else selected_list_name

            # Unified List Shell Button (Similar to Cart/App UI)
            list_header_shell_btn_container = ft.Container(
                padding=ft.padding.symmetric(horizontal=12, vertical=8),
                content=ft.Row(spacing=6, controls=[ft.Icon(ft.Icons.TERMINAL, size=16, color=ft.Colors.WHITE), ft.Text(f"Try {display_name} in Shell", weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE, size=12)]),
                on_click=lambda e: run_list_shell(e),
                ink=True
            )

            list_header_copy_btn = ft.IconButton(ft.Icons.CONTENT_COPY, icon_color=ft.Colors.WHITE70, tooltip="Copy List Command", on_click=lambda e: copy_list_command(e), icon_size=16, style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=0)))

            list_header_shell_btn = ft.Container(
                bgcolor=ft.Colors.BLUE_600, border_radius=8,
                content=ft.Row(spacing=0, controls=[
                    list_header_shell_btn_container,
                    ft.Container(width=1, height=20, bgcolor=ft.Colors.WHITE24),
                    list_header_copy_btn
                ])
            )

            # Update tooltip logic for List Copy
            if item_count > 0:
                 cmd_clean = _build_shell_command_for_items(items, with_wrapper=False)
                 cmd_full = _build_shell_command_for_items(items, with_wrapper=True)
                 list_header_copy_btn.tooltip = cmd_clean
                 list_header_shell_btn_container.tooltip = cmd_full
            else:
                 list_header_copy_btn.tooltip = "List is empty"
                 list_header_shell_btn_container.tooltip = ""

            # Control Row: Delete Button (Only for custom lists)
            controls_row_items = [list_header_shell_btn]

            if not is_viewing_favourites:
                 delete_list_btn = ft.ElevatedButton(
                    "Delete List",
                    icon=ft.Icons.DELETE_OUTLINE,
                    bgcolor=ft.Colors.RED_600,
                    color=ft.Colors.WHITE,
                    data=selected_list_name, # Critical for delete_saved_list to work
                    on_click=delete_saved_list
                )
                 controls_row_items.insert(0, delete_list_btn)

            header = ft.Container(
                padding=ft.padding.only(bottom=10, top=10),
                content=ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    controls=[
                        ft.Row([
                            ft.IconButton(ft.Icons.ARROW_BACK, on_click=go_back_to_lists_index, icon_color="onSurface"),
                            ft.Text(f"{display_name} ({item_count} packages)", size=24, weight=ft.FontWeight.BOLD, color="onSurface")
                        ]),
                        ft.Row(spacing=10, controls=controls_row_items)
                    ]
                )
            )
            return ft.Column(
                expand=True,
                spacing=0,
                controls=[
                    header,
                    list_detail_col
                ]
            )

    def get_settings_view():
        channels_row = ft.Row(wrap=True, spacing=10, run_spacing=10)

        def update_username(e):
            state.username = e.control.value
            state.save_settings()
            # Update toast or maybe header if visible?
            show_toast(f"Username updated to {state.username}")

        def update_default_channel(e): state.default_channel = e.control.value; state.save_settings(); refresh_dropdown_options(); show_toast(f"Saved default: {state.default_channel}")

        def update_font_size(e):
            try:
                val = int(e.control.value)
                state.font_size = val
                state.save_settings()
                # To see font changes, we need to refresh views.
                # Simple hack: force refresh current view
                on_nav_change(4) # Reload settings view
                show_toast(f"Font size set to {val}")
            except ValueError:
                pass

        def update_confirm_timer(e):
            try:
                val = int(e.control.value)
                state.confirm_timer = val
                state.save_settings()
                show_toast(f"Confirm timer set to {val}s")
            except ValueError:
                pass

        def update_undo_timer(e):
            try:
                val = int(e.control.value)
                state.undo_timer = val
                state.save_settings()
                show_toast(f"Undo timer set to {val}s")
            except ValueError:
                pass

        def update_badge_size(e):
            try:
                val = int(e.control.value)
                state.nav_badge_size = val
                state.save_settings()
                update_badges_style()
                show_toast(f"Badge size set to {val}px")
            except ValueError:
                pass

        # New Settings Handlers
        def update_search_limit(e):
            try:
                val = int(e.control.value)
                state.search_limit = val
                state.save_settings()
                show_toast(f"Search limit set to {val}")
            except ValueError:
                pass

        def update_floating_nav(e):
            state.floating_nav = e.control.value
            state.save_settings()
            # Force navbar style refresh
            if navbar_ref[0]: navbar_ref[0]()
            show_toast(f"Always floating {'enabled' if state.floating_nav else 'disabled'}")

        def update_adaptive_nav(e):
            state.adaptive_nav = e.control.value
            state.save_settings()
            if navbar_ref[0]: navbar_ref[0]()
            show_toast(f"Adaptive nav {'enabled' if state.adaptive_nav else 'disabled'}")

        def update_nav_radius(e):
            try:
                val = int(e.control.value)
                state.nav_radius = val
                state.save_settings()
                if navbar_ref[0]: navbar_ref[0]()
                # show_toast(f"Nav radius set to {val}") # Too noisy on slide
            except ValueError:
                pass

        def update_glass_nav(e):
            state.glass_nav = e.control.value
            state.save_settings()
            if navbar_ref[0]: navbar_ref[0]()
            show_toast(f"Glass effect {'enabled' if state.glass_nav else 'disabled'}")

        def update_nav_width(e):
            try:
                val = int(e.control.value)
                state.nav_bar_width = val
                state.save_settings()
                if navbar_ref[0]: navbar_ref[0]()
            except ValueError:
                pass

        def update_icon_spacing(e):
            try:
                val = int(e.control.value)
                state.nav_icon_spacing = val
                state.save_settings()
                if navbar_ref[0]: navbar_ref[0]()
            except ValueError:
                pass

        def update_sync_nav_spacing(e):
            state.sync_nav_spacing = e.control.value
            state.save_settings()
            nav_spacing_slider.disabled = state.sync_nav_spacing
            nav_spacing_slider.update()
            if navbar_ref[0]: navbar_ref[0]()
            show_toast(f"Sync spacing {'enabled' if state.sync_nav_spacing else 'disabled'}")

        # Helper to track expanded state
        def on_tile_change(e):
            if e.data == "true":
                settings_ui_state["expanded_tile"] = e.control.data

        # Theme Handlers
        def update_theme_mode(e):
             selected_set = e.control.selected
             if not selected_set: return
             val = list(selected_set)[0]
             state.theme_mode = val
             state.save_settings()

             page.theme_mode = ft.ThemeMode.DARK if val == "dark" else (ft.ThemeMode.LIGHT if val == "light" else ft.ThemeMode.SYSTEM)
             # Ensure we keep the current color seed
             page.theme = ft.Theme(color_scheme_seed=state.theme_color)
             page.update()
             show_toast(f"Theme mode set to {val}")

             # Re-render settings to apply colors and keep state
             on_nav_change(4)
             # Force navbar color update
             if navbar_ref[0]: navbar_ref[0]()

        def update_theme_color(e):
             color_val = e.control.data
             state.theme_color = color_val
             state.save_settings()

             page.theme = ft.Theme(color_scheme_seed=color_val)
             page.update()
             show_toast(f"Theme color set to {color_val}")

             # Re-render settings to apply colors
             on_nav_change(4)
             # Force navbar color update
             if navbar_ref[0]: navbar_ref[0]()


        def update_shell_single_prefix(e): state.shell_single_prefix = e.control.value; state.save_settings(); refresh_cmd_previews()
        def update_shell_single_suffix(e): state.shell_single_suffix = e.control.value; state.save_settings(); refresh_cmd_previews()
        def update_shell_cart_prefix(e): state.shell_cart_prefix = e.control.value; state.save_settings(); refresh_cmd_previews()
        def update_shell_cart_suffix(e): state.shell_cart_suffix = e.control.value; state.save_settings(); refresh_cmd_previews()

        # Command Preview Elements
        cmd_preview_single = ft.Text(size=12, font_family="monospace", color=ft.Colors.GREEN)
        cmd_preview_cart = ft.Text(size=12, font_family="monospace", color=ft.Colors.GREEN)

        def refresh_cmd_previews():
             # Single
             pre = state.shell_single_prefix.strip()
             suf = state.shell_single_suffix.strip()
             base_cmd = "nix run nixpkgs/nixos-unstable#hello"
             cmd_preview_single.value = f"Example: {pre} {base_cmd} {suf}".strip()

             # Cart
             pre_c = state.shell_cart_prefix.strip()
             suf_c = state.shell_cart_suffix.strip()
             base_cmd_c = "nix shell nixpkgs/nixos-unstable#hello"
             cmd_preview_cart.value = f"Example: {pre_c} {base_cmd_c} {suf_c}".strip()

             if cmd_preview_single.page: cmd_preview_single.update()
             if cmd_preview_cart.page: cmd_preview_cart.update()

        def toggle_channel_state(e): channel = e.control.label; is_active = e.control.value; state.toggle_channel(channel, is_active); refresh_dropdown_options()
        def request_delete_channel(e):
            channel_to_delete = e.control.data; dlg_ref = [None]
            def on_confirm(e): state.remove_channel(channel_to_delete); refresh_channels_list(); refresh_dropdown_options(); page.close(dlg_ref[0]); show_toast(f"Deleted: {channel_to_delete}")
            def on_cancel(e): page.close(dlg_ref[0])
            dlg = ft.AlertDialog(modal=True, title=ft.Text("Confirm Deletion"), content=ft.Text(f"Remove '{channel_to_delete}'?"), actions=[ft.TextButton("Yes", on_click=on_confirm), ft.TextButton("No", on_click=on_cancel)]); dlg_ref[0] = dlg; page.open(dlg)

        def refresh_channels_list(update_ui=True):
            channels_row.controls.clear()
            item_width = 210

            for ch in state.available_channels:
                channels_row.controls.append(
                    ft.Container(
                        bgcolor=ft.Colors.with_opacity(0.1, "onSurface"), padding=ft.padding.only(left=5, right=5, top=5, bottom=5), border_radius=5, width=item_width,
                        content=ft.Row(
                            alignment=ft.MainAxisAlignment.START,
                            spacing=2,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            controls=[
                                ft.Checkbox(value=(ch in state.active_channels), on_change=lambda e, c=ch: state.toggle_channel(c, e.control.value) or refresh_dropdown_options()),
                                ft.Container(content=ft.Text(ch, size=12, no_wrap=True, overflow=ft.TextOverflow.ELLIPSIS, weight=ft.FontWeight.BOLD, color="onSurface"), expand=True),
                                ft.IconButton(icon=ft.Icons.DELETE_OUTLINE, icon_color=ft.Colors.RED_400, icon_size=18, data=ch, on_click=request_delete_channel, width=24, style=ft.ButtonStyle(padding=0))
                            ]
                        )
                    )
                )
            if update_ui and channels_row.page: channels_row.update()

        def add_custom_channel(e):
            if new_channel_input.value:
                val = new_channel_input.value.strip(); val = f"nixos-{val}" if not val.startswith("nixos-") and not val.startswith("nixpkgs-") else val
                if state.add_channel(val): refresh_channels_list(); refresh_dropdown_options(); new_channel_input.value = ""; new_channel_input.update(); show_toast(f"Added channel: {val}")

        new_channel_input = ft.TextField(hint_text="e.g. 23.11", width=150, height=40, text_size=12, content_padding=10, filled=True, bgcolor=ft.Colors.with_opacity(0.1, "onSurface"))
        font_size_input = ft.TextField(value=str(state.font_size), hint_text="Default: 14", width=100, height=40, text_size=12, content_padding=10, filled=True, bgcolor=ft.Colors.with_opacity(0.1, "onSurface"), on_submit=update_font_size, on_blur=update_font_size)

        confirm_timer_input = ft.TextField(value=str(state.confirm_timer), hint_text="Default: 5", width=100, height=40, text_size=12, content_padding=10, filled=True, bgcolor=ft.Colors.with_opacity(0.1, "onSurface"), on_submit=update_confirm_timer, on_blur=update_confirm_timer)
        undo_timer_input = ft.TextField(value=str(state.undo_timer), hint_text="Default: 5", width=100, height=40, text_size=12, content_padding=10, filled=True, bgcolor=ft.Colors.with_opacity(0.1, "onSurface"), on_submit=update_undo_timer, on_blur=update_undo_timer)

        badge_size_input = ft.TextField(value=str(state.nav_badge_size), hint_text="Default: 20", width=100, height=40, text_size=12, content_padding=10, filled=True, bgcolor=ft.Colors.with_opacity(0.1, "onSurface"), on_submit=update_badge_size, on_blur=update_badge_size)

        # New Inputs
        search_limit_input = ft.TextField(value=str(state.search_limit), hint_text="Default: 30", width=100, height=40, text_size=12, content_padding=10, filled=True, bgcolor=ft.Colors.with_opacity(0.1, "onSurface"), on_submit=update_search_limit, on_blur=update_search_limit)
        nav_radius_slider = ft.Slider(min=0, max=50, value=state.nav_radius, divisions=50, label="{value}", on_change=update_nav_radius)

        # Nav Size Sliders
        nav_width_slider = ft.Slider(min=200, max=600, value=state.nav_bar_width, divisions=40, label="{value}", on_change=update_nav_width)
        nav_spacing_slider = ft.Slider(min=0, max=50, value=state.nav_icon_spacing, divisions=50, label="{value}", on_change=update_icon_spacing, disabled=state.sync_nav_spacing)

        username_input = ft.TextField(value=state.username, hint_text="user", width=200, height=40, text_size=12, content_padding=10, filled=True, bgcolor=ft.Colors.with_opacity(0.1, "onSurface"), on_submit=update_username, on_blur=update_username)

        # Theme Mode Segmented Button
        theme_mode_segment = ft.SegmentedButton(
            selected={state.theme_mode},
            segments=[
                ft.Segment(value="light", label=ft.Text("Light"), icon=ft.Icon(ft.Icons.WB_SUNNY)),
                ft.Segment(value="dark", label=ft.Text("Dark"), icon=ft.Icon(ft.Icons.NIGHTLIGHT)),
                ft.Segment(value="system", label=ft.Text("System"), icon=ft.Icon(ft.Icons.SETTINGS_SYSTEM_DAYDREAM)),
            ],
            on_change=update_theme_mode
        )

        # Theme Color Swatches
        colors_map = {
            "blue": ft.Colors.BLUE,
            "purple": ft.Colors.PURPLE,
            "pink": ft.Colors.PINK,
            "orange": ft.Colors.ORANGE,
            "green": ft.Colors.GREEN
        }

        color_controls = []
        for name, color_code in colors_map.items():
             color_controls.append(
                 ft.Container(
                     width=30, height=30, border_radius=15, bgcolor=color_code,
                     border=ft.border.all(2, "onSurface" if state.theme_color == name else ft.Colors.TRANSPARENT),
                     on_click=update_theme_color, data=name,
                     ink=True, tooltip=name.capitalize()
                 )
             )


        refresh_channels_list(update_ui=False)
        refresh_cmd_previews() # Init previews

        # -- Organized Settings Layout with ExpansionTiles --

        return ft.Column(
            scroll=ft.ScrollMode.HIDDEN,
            controls=[
                ft.Text("Settings", size=32, weight=ft.FontWeight.W_900, color="onSurface"),

                ft.ExpansionTile(
                    title=ft.Text("User Profile"),
                    leading=ft.Icon(ft.Icons.PERSON),
                    collapsed_text_color="onSurface",
                    text_color="onSurface",
                    icon_color=ft.Colors.BLUE_200,
                    data="profile",
                    initially_expanded=(settings_ui_state["expanded_tile"] == "profile"),
                    on_change=on_tile_change,
                    controls=[
                         GlassContainer(opacity=0.1, padding=15, content=ft.Row([
                            ft.Text("Username:", weight=ft.FontWeight.BOLD, color="onSurface"),
                            username_input
                        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN))
                    ]
                ),

                ft.ExpansionTile(
                    title=ft.Text("Appearance"),
                    leading=ft.Icon(ft.Icons.PALETTE),
                    collapsed_text_color="onSurface",
                    text_color="onSurface",
                    icon_color=ft.Colors.PINK_200,
                    data="appearance",
                    initially_expanded=(settings_ui_state["expanded_tile"] == "appearance"),
                    on_change=on_tile_change,
                    controls=[
                        GlassContainer(opacity=0.1, padding=15, content=ft.Column([
                            ft.Text("Theme Mode", weight=ft.FontWeight.BOLD, color="onSurface"),
                            theme_mode_segment,
                            ft.Container(height=10),
                            ft.Text("Accent Color", weight=ft.FontWeight.BOLD, color="onSurface"),
                            ft.Row(controls=color_controls, spacing=10),
                            ft.Divider(color=ft.Colors.OUTLINE, height=20),
                            ft.Row([
                                ft.Text("Base Font Size:", weight=ft.FontWeight.BOLD, color="onSurface"),
                                font_size_input
                            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                            ft.Container(height=10),
                            ft.Row([
                                ft.Text("Confirm Dialog Timer (s):", weight=ft.FontWeight.BOLD, color="onSurface"),
                                confirm_timer_input
                            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                             ft.Container(height=10),
                            ft.Row([
                                ft.Text("Undo Toast Timer (s):", weight=ft.FontWeight.BOLD, color="onSurface"),
                                undo_timer_input
                            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                            ft.Container(height=10),
                            ft.Row([
                                ft.Text("Nav Badge Size:", weight=ft.FontWeight.BOLD, color="onSurface"),
                                badge_size_input
                            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                            ft.Container(height=10),
                            ft.Row([
                                ft.Text("Always Floating Navigation Bar:", weight=ft.FontWeight.BOLD, color="onSurface"),
                                ft.Switch(value=state.floating_nav, on_change=update_floating_nav)
                            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                            ft.Row([
                                ft.Text("Adaptive Navigation Bar:", weight=ft.FontWeight.BOLD, color="onSurface"),
                                ft.Switch(value=state.adaptive_nav, on_change=update_adaptive_nav)
                            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                             ft.Container(height=10),
                            ft.Text("Nav Bar Total Length (Floating):", weight=ft.FontWeight.BOLD, color="onSurface"),
                            nav_width_slider,
                            ft.Row([
                                ft.Text("Sync Icon Spacing with Length:", weight=ft.FontWeight.BOLD, color="onSurface"),
                                ft.Switch(value=state.sync_nav_spacing, on_change=update_sync_nav_spacing)
                            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                            ft.Text("Nav Bar Icon Spacing (Manual):", weight=ft.FontWeight.BOLD, color="onSurface"),
                            nav_spacing_slider,
                            ft.Text("Nav Bar Radius:", weight=ft.FontWeight.BOLD, color="onSurface"),
                            nav_radius_slider,
                            ft.Container(height=10),
                            ft.Row([
                                ft.Text("Glass Effect on Nav:", weight=ft.FontWeight.BOLD, color="onSurface"),
                                ft.Switch(value=state.glass_nav, on_change=update_glass_nav)
                            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                        ]))
                    ]
                ),

                ft.ExpansionTile(
                    title=ft.Text("Channel & Search"),
                    leading=ft.Icon(ft.Icons.LAYERS),
                    collapsed_text_color="onSurface",
                    text_color="onSurface",
                    icon_color=ft.Colors.ORANGE_200,
                    data="channels",
                    initially_expanded=(settings_ui_state["expanded_tile"] == "channels"),
                    on_change=on_tile_change,
                    controls=[
                        GlassContainer(opacity=0.1, padding=15, content=ft.Column([
                            ft.Text("Search Limit", weight=ft.FontWeight.BOLD, color="onSurface"),
                            ft.Row([
                                ft.Text("Max results:", size=12, color="onSurface"),
                                search_limit_input
                            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                            ft.Container(height=10),
                            ft.Text("Default Search Channel", weight=ft.FontWeight.BOLD, color="onSurface"),
                            ft.Container(height=5),
                            ft.Dropdown(options=[ft.dropdown.Option(c) for c in state.available_channels], value=state.default_channel, on_change=update_default_channel, bgcolor="surfaceVariant", border_color="outline", text_style=ft.TextStyle(color="onSurface"), filled=True),
                            ft.Container(height=15),
                            ft.Text("Available Channels", weight=ft.FontWeight.BOLD, color="onSurface"),
                            ft.Container(height=10),
                            channels_row,
                            ft.Divider(color=ft.Colors.OUTLINE, height=20),
                            ft.Row([ft.Text("Add Channel:", size=12, color="onSurface"), new_channel_input, ft.IconButton(ft.Icons.ADD_CIRCLE, icon_color=ft.Colors.GREEN, on_click=add_custom_channel)])
                        ]))
                    ]
                ),

                ft.ExpansionTile(
                    title=ft.Text("Run Configurations"),
                    leading=ft.Icon(ft.Icons.TERMINAL),
                    collapsed_text_color="onSurface",
                    text_color="onSurface",
                    icon_color=ft.Colors.GREEN_200,
                    data="run_config",
                    initially_expanded=(settings_ui_state["expanded_tile"] == "run_config"),
                    on_change=on_tile_change,
                    controls=[
                        GlassContainer(opacity=0.1, padding=15, content=ft.Column([
                            ft.Text("Run without installing cmd config", weight=ft.FontWeight.BOLD, color="onSurface"),
                            ft.Container(height=5),
                            ft.Text("Prefix", weight=ft.FontWeight.BOLD, color="onSurface"), ft.TextField(value=state.shell_single_prefix, hint_text="nix run", text_size=12, filled=True, bgcolor=ft.Colors.with_opacity(0.1, "onSurface"), on_change=update_shell_single_prefix),
                            ft.Text("Suffix", weight=ft.FontWeight.BOLD, color="onSurface"), ft.TextField(value=state.shell_single_suffix, hint_text="", text_size=12, filled=True, bgcolor=ft.Colors.with_opacity(0.1, "onSurface"), on_change=update_shell_single_suffix),
                            cmd_preview_single,
                            ft.Container(height=15),
                            ft.Text("Cart/List try in shell cmd config", weight=ft.FontWeight.BOLD, color="onSurface"),
                             ft.Container(height=5),
                            ft.Text("Prefix", weight=ft.FontWeight.BOLD, color="onSurface"), ft.TextField(value=state.shell_cart_prefix, hint_text="nix shell", text_size=12, filled=True, bgcolor=ft.Colors.with_opacity(0.1, "onSurface"), on_change=update_shell_cart_prefix),
                            ft.Text("Suffix", weight=ft.FontWeight.BOLD, color="onSurface"), ft.TextField(value=state.shell_cart_suffix, hint_text="", text_size=12, filled=True, bgcolor=ft.Colors.with_opacity(0.1, "onSurface"), on_change=update_shell_cart_suffix),
                            cmd_preview_cart
                        ]))
                    ]
                ),

                ft.Container(height=50),
            ]
        )

    content_area = ft.Container(expand=True, padding=20, content=get_home_view()) # Default to Home

    # Use a mutable list to hold the reference to refresh_navbar function
    navbar_ref = [None]

    def build_custom_navbar(on_change):
        # We need a reference to all button containers to update their state
        nav_button_controls = []
        current_nav_idx = [0] # Mutable to track current selection

        # Base Container for styling updates
        base_container_ref = [None]
        # Main Row for spacing updates
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

                # Unwrap if it's a stack (badge)
                actual_btn_container = control.controls[0] if isinstance(control, ft.Stack) else control

                # Get the column inside the container
                content_col = actual_btn_container.content

                icon_control = content_col.controls[0]
                text_control = content_col.controls[1]

                # Use theme aware colors for nav bar
                active_col = "onSecondaryContainer"
                inactive_col = ft.Colors.with_opacity(0.6, state.get_base_color())

                # Update Icon and Text
                icon_control.name = items[i][1] if is_selected else items[i][0]
                icon_control.color = active_col if is_selected else inactive_col
                text_control.color = active_col if is_selected else inactive_col

                # Active Pill Indicator Logic
                if is_selected:
                    actual_btn_container.bgcolor = "secondaryContainer"
                    # Make icon distinct
                    icon_control.color = "onSecondaryContainer"
                    text_control.color = "onSecondaryContainer"
                else:
                    actual_btn_container.bgcolor = ft.Colors.TRANSPARENT

                # Force update of the specific container/stack
                if control.page:
                    control.update()

        def refresh_navbar():
            update_active_state(current_nav_idx[0])

            # Update Spacing based on Sync Setting
            if main_row_ref[0]:
                if state.sync_nav_spacing:
                    main_row_ref[0].spacing = 0 # Ignored by SPACE_EVENLY
                    main_row_ref[0].alignment = ft.MainAxisAlignment.SPACE_EVENLY
                else:
                    main_row_ref[0].spacing = state.nav_icon_spacing
                    main_row_ref[0].alignment = ft.MainAxisAlignment.CENTER

                if main_row_ref[0].page:
                    main_row_ref[0].update()

            if base_container_ref[0]:
                is_wide = page.width > 600
                is_adaptive_active = state.adaptive_nav and is_wide

                should_float = True
                if state.floating_nav:
                    should_float = True
                elif state.adaptive_nav and is_wide:
                    should_float = False

                # Update Floating / Full Width Style
                if should_float:
                    # Floating Mode
                    base_container_ref[0].width = state.nav_bar_width # Custom width
                    base_container_ref[0].margin = ft.margin.only(bottom=20)
                    base_container_ref[0].border_radius = state.nav_radius
                else:
                    # Full Width Mode
                    base_container_ref[0].width = page.width - 40 # Padding from edges as requested
                    base_container_ref[0].margin = ft.margin.only(bottom=10) # Small bottom margin
                    base_container_ref[0].border_radius = 10 # Normal corners

                # Update Glass / Solid Style
                if state.glass_nav:
                    base_container_ref[0].bgcolor = ft.Colors.with_opacity(0.15, state.get_base_color())
                    base_container_ref[0].blur = ft.Blur(15, 15, ft.BlurTileMode.MIRROR)
                    base_container_ref[0].border = ft.border.all(1, ft.Colors.with_opacity(0.2, state.get_base_color()))
                else:
                    base_container_ref[0].bgcolor = ft.Colors.SURFACE_VARIANT
                    base_container_ref[0].blur = None
                    base_container_ref[0].border = None

                if base_container_ref[0].page:
                    base_container_ref[0].update()

        # Expose this function to main scope via reference
        navbar_ref[0] = refresh_navbar

        def handle_click(e):
            idx = e.control.data
            current_nav_idx[0] = idx # Update current selection
            update_active_state(idx)
            on_change(idx)

        def create_nav_btn(index, icon_off, icon_on, label):
            # Initial Colors (will be updated by update_active_state on init)
            inactive_col = ft.Colors.with_opacity(0.6, state.get_base_color())

            icon = ft.Icon(name=icon_off, color=inactive_col, size=24)
            text = ft.Text(value=label, size=10, color=inactive_col, weight=ft.FontWeight.BOLD)

            # Button Container (The Pill)
            # We initialize it transparent; update_active_state handles the pill shape/color
            btn_container = ft.Container(
                content=ft.Column(
                    controls=[icon, text],
                    alignment=ft.MainAxisAlignment.CENTER,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=0 # Tighter spacing
                ),
                padding=ft.padding.symmetric(horizontal=12, vertical=8),
                border_radius=30, # Pill shape for the active item
                ink=True,
                on_click=handle_click,
                data=index,
                animate=ft.Animation(300, ft.AnimationCurve.EASE_OUT)
            )
            return btn_container

        final_controls = []
        for i, (icon_off, icon_on, label) in enumerate(items):
            btn = create_nav_btn(i, icon_off, icon_on, label)

            # Badge logic wraps the container in a Stack
            if i == 2: # Cart
                wrapper = ft.Stack([btn, cart_badge_container])
                final_controls.append(wrapper)
                nav_button_controls.append(wrapper)
            elif i == 3: # Lists
                wrapper = ft.Stack([btn, lists_badge_container])
                final_controls.append(wrapper)
                nav_button_controls.append(wrapper)
            else:
                final_controls.append(btn)
                nav_button_controls.append(btn)

        # Main Nav Bar Container

        main_row = ft.Row(
                controls=final_controls,
                alignment=ft.MainAxisAlignment.SPACE_EVENLY, # Default sync
                spacing=0
            )
        main_row_ref[0] = main_row

        container = ft.Container(
            content=main_row,
            padding=ft.padding.symmetric(horizontal=10, vertical=5),
            animate=ft.Animation(300, ft.AnimationCurve.EASE_OUT)
        )

        base_container_ref[0] = container

        # Trigger initial style application
        refresh_navbar()

        return ft.Container(
            alignment=ft.alignment.center, # Ensures the bar is centered horizontally
            content=container,
            padding=ft.padding.only(bottom=10) # Padding for floating position
        )

    def on_nav_change(idx):
        if idx == 0: content_area.content = get_home_view()
        elif idx == 1: content_area.content = get_search_view()
        elif idx == 2: content_area.content = get_cart_view()
        elif idx == 3:
            # RESET list view to index whenever tab is clicked
            nonlocal selected_list_name
            selected_list_name = None
            content_area.content = get_lists_view()
        elif idx == 4: content_area.content = get_settings_view()
        content_area.update()

    # Adaptive Resize Handler
    def handle_resize(e):
        if navbar_ref[0]:
            navbar_ref[0]() # Re-run nav styling logic

    page.on_resized = handle_resize

    nav_bar = build_custom_navbar(on_nav_change)
    background = ft.Container(expand=True, gradient=ft.LinearGradient(begin=ft.alignment.top_left, end=ft.alignment.bottom_right, colors=["background", "surfaceVariant"])) # Adaptive gradient
    decorations = ft.Stack(controls=[ft.Container(width=300, height=300, bgcolor="primary", border_radius=150, top=-100, right=-50, blur=ft.Blur(100, 100, ft.BlurTileMode.MIRROR), opacity=0.15), ft.Container(width=200, height=200, bgcolor="tertiary", border_radius=100, bottom=100, left=-50, blur=ft.Blur(80, 80, ft.BlurTileMode.MIRROR), opacity=0.15)])

    # Adding global menu components to the main Stack
    # nav_bar is now wrapped in a container that aligns it at the bottom
    page.add(ft.Stack(expand=True, controls=[background, decorations, ft.Column(expand=True, spacing=0, controls=[content_area, nav_bar]), global_dismiss_layer, global_menu_card, toast_overlay_container]))

if __name__ == "__main__":
    ft.app(target=main)
