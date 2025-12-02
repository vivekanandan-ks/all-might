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

# --- State Management ---
class AppState:
    def __init__(self):
        self.default_channel = "nixos-24.11"
        self.font_size = 14  # Default font size

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
        self.saved_lists = {} # Format: { "list_name": [item1, item2] }
        self.load_settings()

    def load_settings(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r') as f:
                    data = json.load(f)
                    self.default_channel = data.get("default_channel", self.default_channel)
                    self.font_size = data.get("font_size", 14)
                    self.available_channels = data.get("available_channels", self.available_channels)
                    self.active_channels = data.get("active_channels", self.active_channels)

                    # Load extended shell configs
                    self.shell_single_prefix = data.get("shell_single_prefix", data.get("shell_prefix", "x-terminal-emulator -e"))
                    self.shell_single_suffix = data.get("shell_single_suffix", data.get("shell_suffix", ""))
                    self.shell_cart_prefix = data.get("shell_cart_prefix", self.shell_single_prefix)
                    self.shell_cart_suffix = data.get("shell_cart_suffix", self.shell_single_suffix)

                    self.cart_items = data.get("cart_items", [])
                    self.saved_lists = data.get("saved_lists", {})

            except Exception as e:
                print(f"Error loading settings: {e}")

    def save_settings(self):
        try:
            Path(CONFIG_DIR).mkdir(parents=True, exist_ok=True)
            data = {
                "default_channel": self.default_channel,
                "font_size": self.font_size,
                "available_channels": self.available_channels,
                "active_channels": self.active_channels,
                "shell_single_prefix": self.shell_single_prefix,
                "shell_single_suffix": self.shell_single_suffix,
                "shell_cart_prefix": self.shell_cart_prefix,
                "shell_cart_suffix": self.shell_cart_suffix,
                "cart_items": self.cart_items,
                "saved_lists": self.saved_lists
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

state = AppState()

# --- Logic: Search ---

def execute_nix_search(query, channel):
    if not query:
        return []

    command = [
        "nix", "run", "nixpkgs#nh", "--",
        "search", "--channel", channel, "-j", "--limit", "30", query
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
        if "border" not in kwargs:
            kwargs["border"] = ft.border.all(1, ft.Colors.with_opacity(0.2, ft.Colors.WHITE))

        super().__init__(
            content=content,
            bgcolor=ft.Colors.with_opacity(opacity, ft.Colors.WHITE),
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
        super().__init__(
            content=ft.Row([ft.Icon(icon, size=text_size+2, color=color_group[0]), ft.Text(text, size=text_size, color=color_group[1])], spacing=5, alignment=ft.MainAxisAlignment.START),
            on_click=lambda _: os.system(f"xdg-open {url}") if url else None,
            on_hover=self.on_hover,
            tooltip=url,
            ink=True,
            border_radius=5,
            padding=ft.padding.symmetric(horizontal=8, vertical=4),
            bgcolor=ft.Colors.WHITE10, # Differentiate background
            border=ft.border.all(1, ft.Colors.WHITE12) # Differentiate border
        )
        self.target_url = url
        self.text_control = self.content.controls[1] # Reference to text for update

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

class NixPackageCard(GlassContainer):
    def __init__(self, package_data, page_ref, initial_channel, on_cart_change=None, is_cart_view=False, show_toast_callback=None):
        self.pkg = package_data
        self.page_ref = page_ref
        self.on_cart_change = on_cart_change
        self.is_cart_view = is_cart_view
        self.show_toast = show_toast_callback

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

        # Fonts
        base_size = state.font_size

        self.channel_text = ft.Text(f"{self.version} ({self.selected_channel})", size=base_size - 3, color=ft.Colors.WHITE70)
        channel_menu_items = [ft.PopupMenuItem(text=ch, on_click=self.change_channel, data=ch) for ch in state.active_channels]

        self.channel_selector = ft.Container(
            padding=ft.padding.symmetric(horizontal=8, vertical=4),
            border_radius=6,
            border=ft.border.all(1, ft.Colors.WHITE24),
            content=ft.Row(spacing=4, controls=[self.channel_text, ft.Icon(ft.Icons.ARROW_DROP_DOWN, color=ft.Colors.WHITE70, size=14)]),
        )
        self.channel_dropdown = ft.PopupMenuButton(content=self.channel_selector, items=channel_menu_items, tooltip="Select Channel")

        # --- Combined Action Buttons ---
        self.try_btn_icon = ft.Icon(ft.Icons.PLAY_ARROW, size=16, color=ft.Colors.WHITE)
        self.try_btn_text = ft.Text("Try running directly", weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE, size=base_size - 2)

        self.try_btn = ft.Container(
            padding=ft.padding.symmetric(horizontal=12, vertical=8),
            content=ft.Row(spacing=6, controls=[self.try_btn_icon, self.try_btn_text], alignment=ft.MainAxisAlignment.CENTER),
            on_click=lambda e: self.run_action(),
            bgcolor=ft.Colors.TRANSPARENT,
            ink=True
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
                ft.PopupMenuItem(text="Try running directly", icon=ft.Icons.PLAY_ARROW, on_click=lambda e: self.set_mode_and_update_ui("direct")),
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

        # --- List Management Button ---
        self.list_badge_count = ft.Text("0", size=9, color=ft.Colors.WHITE, weight=ft.FontWeight.BOLD)
        self.list_badge = ft.Container(
            content=self.list_badge_count,
            bgcolor=ft.Colors.RED_500, width=14, height=14, border_radius=7,
            alignment=ft.alignment.center, visible=False
        )

        self.lists_menu_btn = ft.PopupMenuButton(
            content=ft.Stack([
                ft.IconButton(ft.Icons.PLAYLIST_ADD, tooltip="Add to List", icon_size=20),
                ft.Container(content=self.list_badge, top=2, right=2)
            ]),
            items=[]
        )
        self.refresh_lists_menu()

        tag_color = ft.Colors.BLUE_GREY_700 if self.attr_set == "No package set" else ft.Colors.TEAL_700
        self.tag_chip = ft.Container(
            padding=ft.padding.symmetric(horizontal=6, vertical=2),
            border_radius=8,
            bgcolor=ft.Colors.with_opacity(0.5, tag_color),
            content=ft.Text(self.attr_set, size=base_size - 5, color=ft.Colors.WHITE70, weight=ft.FontWeight.BOLD),
            visible=bool(self.attr_set)
        )

        # --- Footer Items (Horizontal - 1x4 style) ---
        footer_size = base_size - 3
        footer_items = [
            ft.Container(content=ft.Row([ft.Icon(ft.Icons.VERIFIED_USER_OUTLINED, size=14, color=ft.Colors.GREEN_300), ft.Text(license_text, size=footer_size, color=ft.Colors.GREEN_100)], spacing=4), padding=ft.padding.symmetric(horizontal=4))
        ]
        if programs_str:
            footer_items.append(ft.Container(content=ft.Row([ft.Icon(ft.Icons.TERMINAL, size=14, color=ft.Colors.ORANGE_300), ft.Text(f"Bins: {programs_str}", size=footer_size, color=ft.Colors.ORANGE_100, no_wrap=True, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS)], spacing=4), padding=ft.padding.symmetric(horizontal=4)))
        if homepage_url:
            footer_items.append(HoverLink(ft.Icons.LINK, "Homepage", homepage_url, (ft.Colors.BLUE_300, ft.Colors.BLUE_100), text_size=footer_size))
        if source_url:
            footer_items.append(HoverLink(ft.Icons.CODE, "Source", source_url, (ft.Colors.PURPLE_300, ft.Colors.PURPLE_100), text_size=footer_size))

        content = ft.Column(
            spacing=4,
            controls=[
                # Top Row: Title, Tag, Channel
                ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    controls=[
                        ft.Column(spacing=2, controls=[
                            ft.Row([
                                ft.Text(self.pname, weight=ft.FontWeight.BOLD, size=base_size + 2, color=ft.Colors.WHITE),
                                self.tag_chip
                            ]),
                        ]),
                        # Action Row
                        ft.Row(spacing=5, controls=[
                            self.channel_dropdown, # Moved to action row
                            self.unified_action_bar,
                            self.lists_menu_btn,
                            self.cart_btn
                        ])
                    ]
                ),
                # Description
                ft.Container(content=ft.Text(description, size=base_size - 1, color=ft.Colors.WHITE70, no_wrap=False, max_lines=2, overflow=ft.TextOverflow.ELLIPSIS), padding=ft.padding.only(bottom=5)),
                # Horizontal Footer - 1x4 Style
                ft.Container(
                    bgcolor=ft.Colors.BLACK12, border_radius=6, padding=4,
                    content=ft.Row(wrap=False, scroll=ft.ScrollMode.HIDDEN, controls=footer_items, spacing=10)
                )
            ]
        )
        super().__init__(content=content, padding=12, opacity=0.15)

    def refresh_lists_menu(self):
        containing_lists = state.get_containing_lists(self.pkg, self.selected_channel)
        count = len(containing_lists)
        self.list_badge_count.value = str(count)
        self.list_badge.visible = count > 0

        items = []
        if not state.saved_lists:
            items.append(ft.PopupMenuItem(text="No lists created", enabled=False))
        else:
            for list_name in state.saved_lists.keys():
                is_checked = list_name in containing_lists
                items.append(
                    ft.PopupMenuItem(
                        text=list_name,
                        checked=is_checked,
                        on_click=lambda e, ln=list_name: self.handle_list_toggle(ln)
                    )
                )
        self.lists_menu_btn.items = items
        if self.lists_menu_btn.page:
            self.lists_menu_btn.update()
            self.list_badge.update()

    def handle_list_toggle(self, list_name):
        msg = state.toggle_pkg_in_list(list_name, self.pkg, self.selected_channel)
        if self.show_toast: self.show_toast(msg)
        self.refresh_lists_menu()

    def update_cart_btn_state(self):
        in_cart = state.is_in_cart(self.pkg, self.selected_channel)
        if in_cart:
            self.cart_btn.icon = ft.Icons.REMOVE_SHOPPING_CART
            self.cart_btn.icon_color = ft.Colors.RED_400
            self.cart_btn.tooltip = "Remove from Cart"
        else:
            self.cart_btn.icon = ft.Icons.ADD_SHOPPING_CART
            self.cart_btn.icon_color = ft.Colors.GREEN_400
            self.cart_btn.tooltip = "Add to Cart"
        if self.cart_btn.page:
            self.cart_btn.update()

    def handle_cart_click(self, e):
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
            self.refresh_lists_menu() # Refresh lists state for new channel/version
        except Exception as ex:
            self.channel_text.value = "Error"
            self.channel_text.update()

    def set_mode_and_update_ui(self, mode):
        self.run_mode = mode
        if mode == "direct":
            self.try_btn_text.value = "Try running directly"
            self.try_btn_icon.name = ft.Icons.PLAY_ARROW
        elif mode == "shell":
            self.try_btn_text.value = "Try in a shell"
            self.try_btn_icon.name = ft.Icons.TERMINAL
        self.try_btn_text.update()
        self.try_btn_icon.update()

    def _generate_nix_command(self):
        target = f"nixpkgs/{self.selected_channel}#{self.pname}"

        if self.run_mode == "direct":
            return f"nix run {target}"
        elif self.run_mode == "shell":
            prefix = state.shell_single_prefix.strip()
            suffix = state.shell_single_suffix.strip()
            # STRICTLY prefix + nix shell pkg + suffix (No extra logic)
            nix_cmd = f"nix shell {target}"
            return f"{prefix} {nix_cmd} {suffix}".strip()

    def copy_command(self, e):
        cmd = self._generate_nix_command()
        self.page_ref.set_clipboard(cmd)
        if self.show_toast: self.show_toast(f"Copied: {cmd}")

    def run_action(self):
        display_cmd = self._generate_nix_command()
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
    page.theme_mode = ft.ThemeMode.DARK
    page.padding = 0
    page.window_width = 400
    page.window_height = 800

    current_results = []
    active_filters = set()
    pending_filters = set()

    # --- Custom Toast Logic ---
    toast_overlay_container = ft.Container(bottom=90, left=0, right=0, alignment=ft.alignment.center, visible=False)

    def show_toast(message):
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
            t_container.opacity = 0
            page.update()
            time.sleep(0.3)
            toast_overlay_container.visible = False
            page.update()
        threading.Thread(target=hide, daemon=True).start()

    def show_undo_toast(message, on_undo):
        # Create UndoToast component
        def on_timeout():
            toast_overlay_container.visible = False
            page.update()

        def wrapped_undo():
            on_undo()
            toast_overlay_container.visible = False
            page.update()

        undo_control = UndoToast(message, on_undo=wrapped_undo, on_timeout=on_timeout)
        toast_overlay_container.content = undo_control
        toast_overlay_container.visible = True
        page.update()

    global show_toast_global
    global show_undo_toast_global
    show_toast_global = show_toast
    show_undo_toast_global = show_undo_toast

    # --- Helper: Destructive Action Dialog with Timer ---
    def show_destructive_dialog(title, content_text, on_confirm):
        # Start colorless (Grey)
        confirm_btn = ft.ElevatedButton("Yes (5s)", bgcolor=ft.Colors.GREY_700, color=ft.Colors.WHITE70, disabled=True)
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
            for i in range(5, 0, -1):
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

    cart_header_title = ft.Text("Your Cart (0 items)", size=24, weight=ft.FontWeight.W_900, color=ft.Colors.WHITE)

    # Header Buttons
    cart_header_save_btn = ft.ElevatedButton("Save cart as list", icon=ft.Icons.ADD, bgcolor=ft.Colors.TEAL_700, color=ft.Colors.WHITE)
    cart_header_clear_btn = ft.IconButton(ft.Icons.DELETE_SWEEP, tooltip="Clear Cart", icon_color=ft.Colors.RED_400)

    # Unified Cart Shell Button (Similar to App UI)
    cart_header_shell_btn = ft.Container(
        bgcolor=ft.Colors.BLUE_600, border_radius=8,
        content=ft.Row(spacing=0, controls=[
            ft.Container(
                padding=ft.padding.symmetric(horizontal=12, vertical=8),
                content=ft.Row(spacing=6, controls=[ft.Icon(ft.Icons.TERMINAL, size=16, color=ft.Colors.WHITE), ft.Text("Try Cart in Shell", weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE, size=12)]),
                on_click=lambda e: run_cart_shell(e),
                ink=True
            ),
            ft.Container(width=1, height=20, bgcolor=ft.Colors.WHITE24),
            ft.IconButton(ft.Icons.CONTENT_COPY, icon_color=ft.Colors.WHITE70, tooltip="Copy Command", on_click=lambda e: copy_cart_command(e), icon_size=16, style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=0)))
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

    result_count_text = ft.Text("", size=12, color=ft.Colors.WHITE54, visible=False)

    channel_dropdown = ft.Dropdown(
        width=160, text_size=12, border_color=ft.Colors.TRANSPARENT, bgcolor=ft.Colors.GREY_900,
        value=state.default_channel if state.default_channel in state.active_channels else (state.active_channels[0] if state.active_channels else ""),
        options=[ft.dropdown.Option(c) for c in state.active_channels],
        content_padding=10, filled=True,
    )

    search_field = ft.TextField(hint_text="Search packages...", border=ft.InputBorder.NONE, hint_style=ft.TextStyle(color=ft.Colors.WHITE54), text_style=ft.TextStyle(color=ft.Colors.WHITE), expand=True)

    filter_badge_count = ft.Text("0", size=10, color=ft.Colors.WHITE, weight=ft.FontWeight.BOLD)
    filter_badge_container = ft.Container(content=filter_badge_count, bgcolor=ft.Colors.RED_500, width=16, height=16, border_radius=8, alignment=ft.alignment.center, visible=False, top=0, right=0)

    # FIXED CART BADGE: Ensure stack has room by placing it inside a container with padding/margin logic if needed
    cart_badge_count = ft.Text(str(len(state.cart_items)), size=10, color=ft.Colors.WHITE, weight=ft.FontWeight.BOLD, text_align=ft.TextAlign.CENTER)
    cart_badge_container = ft.Container(
        content=cart_badge_count,
        bgcolor=ft.Colors.RED_500,
        width=20, height=20, border_radius=10, # Increased size
        alignment=ft.alignment.center,
        visible=len(state.cart_items) > 0,
        top=2, right=2 # Adjusted position
    )

    filter_dismiss_layer = ft.Container(expand=True, visible=False, on_click=lambda e: toggle_filter_menu(False), bgcolor=ft.Colors.with_opacity(0.01, ft.Colors.BLACK))
    filter_list_col = ft.Column(scroll=ft.ScrollMode.AUTO)
    filter_menu = GlassContainer(visible=False, width=300, height=350, top=60, right=50, padding=15, border=ft.border.all(1, ft.Colors.WHITE24), content=ft.Column([ft.Text("Filter by Package Set", weight=ft.FontWeight.BOLD, size=16), ft.Divider(height=10, color=ft.Colors.WHITE10), ft.Container(expand=True, content=filter_list_col), ft.Row(alignment=ft.MainAxisAlignment.END, controls=[ft.TextButton("Close", on_click=lambda e: toggle_filter_menu(False)), ft.ElevatedButton("Apply", on_click=lambda e: apply_filters())])]))

    # --- Lists View State & Components ---
    selected_list_name = None
    lists_main_col = ft.Column(scroll=ft.ScrollMode.HIDDEN, expand=True)
    list_detail_col = ft.Column(scroll=ft.ScrollMode.HIDDEN, expand=True)

    # --- Cart & List Logic ---

    def _build_shell_command_for_items(items):
        prefix = state.shell_cart_prefix.strip()
        suffix = state.shell_cart_suffix.strip()

        nix_pkgs_args = []
        for item in items:
            pkg = item['package']
            channel = item['channel']
            nix_pkgs_args.append(f"nixpkgs/{channel}#{pkg.get('package_pname')}")

        nix_args_str = " ".join(nix_pkgs_args)
        nix_cmd = f"nix shell {nix_args_str}"
        return f"{prefix} {nix_cmd} {suffix}".strip()

    def run_cart_shell(e):
        if not state.cart_items: return
        display_cmd = _build_shell_command_for_items(state.cart_items)
        _launch_shell_dialog(display_cmd, "Cart Shell")

    def run_list_shell(e):
        if not selected_list_name or selected_list_name not in state.saved_lists: return
        items = state.saved_lists[selected_list_name]
        if not items: return
        display_cmd = _build_shell_command_for_items(items)
        _launch_shell_dialog(display_cmd, f"List: {selected_list_name}")

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
        cmd = _build_shell_command_for_items(state.cart_items)
        page.set_clipboard(cmd)
        show_toast(f"Copied Cart Command")

    def copy_list_command(e):
        if not selected_list_name or selected_list_name not in state.saved_lists: return
        items = state.saved_lists[selected_list_name]
        cmd = _build_shell_command_for_items(items)
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
        cart_header_save_btn.disabled = (total_items == 0)
        cart_header_clear_btn.disabled = (total_items == 0)

        # Update List Logic
        cart_list.controls.clear()
        if not state.cart_items:
            cart_list.controls.append(ft.Container(content=ft.Text("Your cart is empty.", color=ft.Colors.WHITE54), alignment=ft.alignment.center, padding=20))
        else:
            for item in state.cart_items:
                pkg_data = item['package']
                saved_channel = item['channel']
                cart_list.controls.append(NixPackageCard(pkg_data, page, saved_channel, on_cart_change=on_global_cart_change, is_cart_view=True, show_toast_callback=show_toast))

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
            results_column.controls.append(ft.Container(content=ft.Column([ft.Icon(ft.Icons.ERROR_OUTLINE, color=ft.Colors.RED_400, size=40), ft.Text("Search Failed", color=ft.Colors.RED_400, weight=ft.FontWeight.BOLD), ft.Text(error_msg, color=ft.Colors.WHITE70, size=12, text_align=ft.TextAlign.CENTER)], horizontal_alignment=ft.CrossAxisAlignment.CENTER), alignment=ft.alignment.center, padding=20))
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
             results_column.controls.append(ft.Container(content=ft.Text("No results found.", color=ft.Colors.WHITE54), alignment=ft.alignment.center, padding=20))
        else:
            for pkg in filtered_data:
                results_column.controls.append(NixPackageCard(pkg, page, channel_dropdown.value, on_cart_change=on_global_cart_change, show_toast_callback=show_toast))
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

    def open_list_detail(list_name):
        nonlocal selected_list_name
        selected_list_name = list_name
        content_area.content = get_lists_view()
        content_area.update()

    def go_back_to_lists_index(e):
        nonlocal selected_list_name
        selected_list_name = None
        content_area.content = get_lists_view()
        content_area.update()

    def delete_saved_list(e):
        name = e.control.data
        backup_items = state.saved_lists.get(name, []) # Backup

        def do_delete(e):
            nonlocal selected_list_name # FIXED: Moved to top
            state.delete_list(name)
            refresh_lists_main_view(update_ui=True)

            # If we are deleting the list we are currently viewing, go back to index
            if selected_list_name == name:
                selected_list_name = None
                content_area.content = get_lists_view()
                content_area.update()

            def on_undo():
                state.restore_list(name, backup_items)
                refresh_lists_main_view(update_ui=True)
                # Note: We don't auto-navigate back to the restored list to avoid jarring UI changes

            show_undo_toast(f"Deleted: {name}", on_undo)

        show_destructive_dialog("Delete List?", f"Are you sure you want to delete '{name}'?", do_delete)

    def refresh_lists_main_view(update_ui=False):
        lists_main_col.controls.clear()
        if not state.saved_lists:
             lists_main_col.controls.append(ft.Container(content=ft.Text("No saved lists yet.", color=ft.Colors.WHITE54), alignment=ft.alignment.center, padding=20))
        else:
            for name, items in state.saved_lists.items():
                count = len(items)
                pkgs_preview = ", ".join([i['package'].get('package_pname', '?') for i in items[:3]])
                if len(items) > 3: pkgs_preview += "..."

                card = GlassContainer(
                    opacity=0.1, padding=15, ink=True, on_click=lambda e, n=name: open_list_detail(n),
                    content=ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        controls=[
                            ft.Column([
                                ft.Text(name, size=18, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                                ft.Text(f"{count} packages", size=12, color=ft.Colors.TEAL_200),
                                ft.Text(pkgs_preview, size=12, color=ft.Colors.WHITE54, no_wrap=True)
                            ], expand=True),
                            ft.IconButton(ft.Icons.DELETE_OUTLINE, icon_color=ft.Colors.RED_300, data=name, on_click=delete_saved_list)
                        ]
                    )
                )
                lists_main_col.controls.append(card)
        if update_ui and lists_main_col.page: lists_main_col.update()

    def refresh_list_detail_view(update_ui=False):
        list_detail_col.controls.clear()
        if selected_list_name and selected_list_name in state.saved_lists:
            items = state.saved_lists[selected_list_name]
            for item in items:
                pkg_data = item['package']
                saved_channel = item['channel']
                # Re-using NixPackageCard. The 'Cart' button on it will interact with the Active Cart (Add/Remove),
                # effectively allowing users to move items from a saved list into their current session.
                list_detail_col.controls.append(NixPackageCard(pkg_data, page, saved_channel, on_cart_change=on_global_cart_change, is_cart_view=True, show_toast_callback=show_toast))

        if update_ui and list_detail_col.page: list_detail_col.update()

    # -- Views --

    def get_search_view():
        return ft.Stack(
            expand=True,
            controls=[
                ft.Column(
                    expand=True,
                    controls=[
                        ft.Text(APP_NAME, size=32, weight=ft.FontWeight.W_900, color=ft.Colors.WHITE),
                        GlassContainer(opacity=0.15, padding=5, content=ft.Row(controls=[channel_dropdown, ft.Container(width=1, height=30, bgcolor=ft.Colors.WHITE24), search_field, ft.Stack(controls=[ft.IconButton(icon=ft.Icons.FILTER_LIST, icon_color=ft.Colors.WHITE, tooltip="Filter", on_click=lambda e: toggle_filter_menu(not filter_menu.visible)), filter_badge_container]), ft.IconButton(icon=ft.Icons.SEARCH, icon_color=ft.Colors.WHITE, on_click=perform_search)])),
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
                    ft.Text(f"Saved Lists ({total_lists})", size=32, weight=ft.FontWeight.W_900, color=ft.Colors.WHITE),
                    lists_main_col
                ]
            )
        else:
            # Detail View
            refresh_list_detail_view(update_ui=False)

            # Count items in current list
            item_count = len(state.saved_lists.get(selected_list_name, []))

            # Unified List Shell Button (Similar to Cart/App UI)
            list_header_shell_btn = ft.Container(
                bgcolor=ft.Colors.BLUE_600, border_radius=8,
                content=ft.Row(spacing=0, controls=[
                    ft.Container(
                        padding=ft.padding.symmetric(horizontal=12, vertical=8),
                        content=ft.Row(spacing=6, controls=[ft.Icon(ft.Icons.TERMINAL, size=16, color=ft.Colors.WHITE), ft.Text(f"Try List in Shell", weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE, size=12)]),
                        on_click=lambda e: run_list_shell(e),
                        ink=True
                    ),
                    ft.Container(width=1, height=20, bgcolor=ft.Colors.WHITE24),
                    ft.IconButton(ft.Icons.CONTENT_COPY, icon_color=ft.Colors.WHITE70, tooltip="Copy List Command", on_click=lambda e: copy_list_command(e), icon_size=16, style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=0)))
                ])
            )

            # Red Delete List Button
            delete_list_btn = ft.ElevatedButton(
                "Delete List",
                icon=ft.Icons.DELETE_OUTLINE,
                bgcolor=ft.Colors.RED_600,
                color=ft.Colors.WHITE,
                data=selected_list_name, # Critical for delete_saved_list to work
                on_click=delete_saved_list
            )

            header = ft.Container(
                padding=ft.padding.only(bottom=10, top=10),
                content=ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    controls=[
                        ft.Row([
                            ft.IconButton(ft.Icons.ARROW_BACK, on_click=go_back_to_lists_index, icon_color=ft.Colors.WHITE70),
                            ft.Text(f"{selected_list_name} ({item_count} packages)", size=24, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE)
                        ]),
                        ft.Row(spacing=10, controls=[
                            delete_list_btn,
                            list_header_shell_btn
                        ])
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

        def update_default_channel(e): state.default_channel = e.control.value; state.save_settings(); refresh_dropdown_options(); show_toast(f"Saved default: {state.default_channel}")

        def update_font_size(e):
            try:
                val = int(e.control.value)
                state.font_size = val
                state.save_settings()
                # To see font changes, we need to refresh views.
                # Simple hack: force refresh current view
                on_nav_change(3) # Reload settings view
                show_toast(f"Font size set to {val}")
            except ValueError:
                pass # Ignore invalid input

        def update_shell_single_prefix(e): state.shell_single_prefix = e.control.value; state.save_settings()
        def update_shell_single_suffix(e): state.shell_single_suffix = e.control.value; state.save_settings()
        def update_shell_cart_prefix(e): state.shell_cart_prefix = e.control.value; state.save_settings()
        def update_shell_cart_suffix(e): state.shell_cart_suffix = e.control.value; state.save_settings()
        def toggle_channel_state(e): channel = e.control.label; is_active = e.control.value; state.toggle_channel(channel, is_active); refresh_dropdown_options()
        def request_delete_channel(e):
            channel_to_delete = e.control.data; dlg_ref = [None]
            def on_confirm(e): state.remove_channel(channel_to_delete); refresh_channels_list(); refresh_dropdown_options(); page.close(dlg_ref[0]); show_toast(f"Deleted: {channel_to_delete}")
            def on_cancel(e): page.close(dlg_ref[0])
            dlg = ft.AlertDialog(modal=True, title=ft.Text("Confirm Deletion"), content=ft.Text(f"Remove '{channel_to_delete}'?"), actions=[ft.TextButton("Yes", on_click=on_confirm), ft.TextButton("No", on_click=on_cancel)]); dlg_ref[0] = dlg; page.open(dlg)

        def refresh_channels_list(update_ui=True):
            channels_row.controls.clear()
            # Fixed width to fit approx 3 cols on 400px width.
            item_width = 160 # Increased width

            for ch in state.available_channels:
                channels_row.controls.append(
                    ft.Container(
                        bgcolor=ft.Colors.WHITE10, padding=5, border_radius=5, width=item_width,
                        content=ft.Row(
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            spacing=0,
                            controls=[
                                ft.Container(
                                    content=ft.Checkbox(
                                        label=ch,
                                        value=(ch in state.active_channels),
                                        on_change=toggle_channel_state,
                                        label_style=ft.TextStyle(size=10)
                                    ),
                                    expand=True
                                ),
                                ft.IconButton(icon=ft.Icons.DELETE_OUTLINE, icon_color=ft.Colors.RED_400, icon_size=16, data=ch, on_click=request_delete_channel, width=30)
                            ]
                        )
                    )
                )
            if update_ui and channels_row.page: channels_row.update()

        def add_custom_channel(e):
            if new_channel_input.value:
                val = new_channel_input.value.strip(); val = f"nixos-{val}" if not val.startswith("nixos-") and not val.startswith("nixpkgs-") else val
                if state.add_channel(val): refresh_channels_list(); refresh_dropdown_options(); new_channel_input.value = ""; new_channel_input.update(); show_toast(f"Added channel: {val}")

        new_channel_input = ft.TextField(hint_text="e.g. 23.11", width=150, height=40, text_size=12, content_padding=10, filled=True, bgcolor=ft.Colors.BLACK12)
        font_size_input = ft.TextField(value=str(state.font_size), hint_text="Default: 14", width=100, height=40, text_size=12, content_padding=10, filled=True, bgcolor=ft.Colors.BLACK12, on_submit=update_font_size, on_blur=update_font_size)

        refresh_channels_list(update_ui=False)
        return ft.Column(
            scroll=ft.ScrollMode.HIDDEN,
            controls=[
                ft.Text("Settings", size=32, weight=ft.FontWeight.W_900, color=ft.Colors.WHITE),
                GlassContainer(opacity=0.2, padding=20, content=ft.Row([ft.CircleAvatar(content=ft.Icon(ft.Icons.PERSON), bgcolor=ft.Colors.PURPLE_200, radius=30), ft.Column([ft.Text("User", size=18, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE), ft.Text("System Configuration", color=ft.Colors.WHITE70)], spacing=2)])),
                ft.Container(height=20),

                # --- UI Settings ---
                ft.Text("Appearance", size=16, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE54),
                GlassContainer(opacity=0.1, padding=15, content=ft.Row([
                    ft.Text("Base Font Size:", weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                    font_size_input
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)),
                ft.Container(height=10),

                ft.Text("Channel Management", size=16, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE54),
                GlassContainer(opacity=0.1, padding=15, content=ft.Column([
                    ft.Text("Available Channels", weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                    ft.Container(height=10),
                    channels_row,
                    ft.Divider(color=ft.Colors.WHITE24),
                    ft.Row([ft.Text("Add Channel:", size=12), new_channel_input, ft.IconButton(ft.Icons.ADD_CIRCLE, icon_color=ft.Colors.GREEN_400, on_click=add_custom_channel)])
                ])),
                ft.Container(height=10),
                ft.Text("Run Configurations (Single App)", size=16, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE54),
                GlassContainer(opacity=0.1, padding=15, content=ft.Column([
                    ft.Text("Prefix", weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE), ft.TextField(value=state.shell_single_prefix, hint_text="e.g. kitty -e", text_size=12, filled=True, bgcolor=ft.Colors.BLACK12, on_change=update_shell_single_prefix),
                    ft.Text("Suffix", weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE), ft.TextField(value=state.shell_single_suffix, hint_text="optional", text_size=12, filled=True, bgcolor=ft.Colors.BLACK12, on_change=update_shell_single_suffix)
                ])),
                ft.Container(height=10),
                ft.Text("Run Configurations (Cart)", size=16, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE54),
                GlassContainer(opacity=0.1, padding=15, content=ft.Column([
                    ft.Text("Prefix", weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE), ft.TextField(value=state.shell_cart_prefix, hint_text="e.g. kitty -e", text_size=12, filled=True, bgcolor=ft.Colors.BLACK12, on_change=update_shell_cart_prefix),
                    ft.Text("Suffix", weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE), ft.TextField(value=state.shell_cart_suffix, hint_text="optional", text_size=12, filled=True, bgcolor=ft.Colors.BLACK12, on_change=update_shell_cart_suffix)
                ])),
                ft.Container(height=10),
                ft.Text("Defaults", size=16, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE54),
                GlassContainer(opacity=0.1, padding=15, content=ft.Column([ft.Text("Default Search Channel", weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE), ft.Container(height=5), ft.Dropdown(options=[ft.dropdown.Option(c) for c in state.available_channels], value=state.default_channel, on_change=update_default_channel, bgcolor=ft.Colors.GREY_900, border_color=ft.Colors.WHITE24, text_style=ft.TextStyle(color=ft.Colors.WHITE), filled=True)])),
                ft.Container(height=50),
            ]
        )

    content_area = ft.Container(expand=True, padding=20, content=get_search_view())

    def build_custom_navbar(on_change):
        # We need a reference to all button containers to update their state
        nav_button_controls = []

        items = [
            (ft.Icons.SEARCH_OUTLINED, ft.Icons.SEARCH, "Search"),
            (ft.Icons.SHOPPING_CART_OUTLINED, ft.Icons.SHOPPING_CART, "Cart"),
            (ft.Icons.LIST_ALT_OUTLINED, ft.Icons.LIST_ALT, "Lists"),
            (ft.Icons.SETTINGS_OUTLINED, ft.Icons.SETTINGS, "Settings")
        ]

        def update_active_state(selected_idx):
            for i, control in enumerate(nav_button_controls):
                is_selected = (i == selected_idx)
                # Structure: Container -> Column -> [Icon, Text]
                # If wrapped in Stack (Cart), it's Stack -> Container -> Column -> ...

                if isinstance(control, ft.Stack):
                    content_col = control.controls[0].content
                else:
                    content_col = control.content

                icon_control = content_col.controls[0]
                text_control = content_col.controls[1]

                icon_control.name = items[i][1] if is_selected else items[i][0]
                icon_control.color = ft.Colors.WHITE if is_selected else ft.Colors.WHITE54
                text_control.color = ft.Colors.WHITE if is_selected else ft.Colors.WHITE54

                # Force update of the specific container/stack
                if control.page:
                    control.update()

        def handle_click(e):
            idx = e.control.data
            update_active_state(idx)
            on_change(idx)

        def create_nav_btn(index, icon_off, icon_on, label):
            is_active = (index == 0)

            icon = ft.Icon(
                name=icon_on if is_active else icon_off,
                color=ft.Colors.WHITE if is_active else ft.Colors.WHITE54,
                size=24
            )
            text = ft.Text(
                value=label,
                size=10,
                color=ft.Colors.WHITE if is_active else ft.Colors.WHITE54,
                weight=ft.FontWeight.BOLD
            )

            # Using Container for clickability instead of IconButton for layout control
            btn_container = ft.Container(
                content=ft.Column(
                    controls=[icon, text],
                    alignment=ft.MainAxisAlignment.CENTER,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=2
                ),
                padding=10,
                border_radius=10,
                ink=True,
                on_click=handle_click,
                data=index
            )
            return btn_container

        final_controls = []
        for i, (icon_off, icon_on, label) in enumerate(items):
            btn = create_nav_btn(i, icon_off, icon_on, label)

            if i == 1: # Cart
                # Stack wrapper for badge
                wrapper = ft.Stack([btn, cart_badge_container])
                final_controls.append(wrapper)
                nav_button_controls.append(wrapper) # Store for updates
            else:
                final_controls.append(btn)
                nav_button_controls.append(btn) # Store for updates

        return GlassContainer(
            opacity=0.15,
            border_radius=0,
            blur_sigma=15,
            padding=ft.padding.only(top=5, bottom=5),
            margin=0,
            content=ft.Row(controls=final_controls, alignment=ft.MainAxisAlignment.SPACE_EVENLY)
        )

    def on_nav_change(idx):
        if idx == 0: content_area.content = get_search_view()
        elif idx == 1: content_area.content = get_cart_view()
        elif idx == 2:
            # RESET list view to index whenever tab is clicked
            nonlocal selected_list_name
            selected_list_name = None
            content_area.content = get_lists_view()
        elif idx == 3: content_area.content = get_settings_view()
        content_area.update()

    nav_bar = build_custom_navbar(on_nav_change)
    background = ft.Container(expand=True, gradient=ft.LinearGradient(begin=ft.alignment.top_left, end=ft.alignment.bottom_right, colors=["#1a1b26", "#24283b", "#414868"]))
    decorations = ft.Stack(controls=[ft.Container(width=300, height=300, bgcolor=ft.Colors.CYAN_900, border_radius=150, top=-100, right=-50, blur=ft.Blur(100, 100, ft.BlurTileMode.MIRROR), opacity=0.3), ft.Container(width=200, height=200, bgcolor=ft.Colors.PURPLE_900, border_radius=100, bottom=100, left=-50, blur=ft.Blur(80, 80, ft.BlurTileMode.MIRROR), opacity=0.3)])
    page.add(ft.Stack(expand=True, controls=[background, decorations, ft.Column(expand=True, spacing=0, controls=[content_area, nav_bar]), toast_overlay_container]))

if __name__ == "__main__":
    ft.app(target=main)
