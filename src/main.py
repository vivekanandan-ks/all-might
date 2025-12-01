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
        self.shell_prefix = "x-terminal-emulator -e"
        self.shell_suffix = ""
        self.available_channels = [
            "nixos-25.05", "nixos-unstable", "nixos-24.11", "nixos-24.05"
        ]
        self.active_channels = [
            "nixos-25.05", "nixos-unstable", "nixos-24.11"
        ]
        self.cart_items = []
        self.load_settings()

    def load_settings(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r') as f:
                    data = json.load(f)
                    self.default_channel = data.get("default_channel", self.default_channel)
                    self.available_channels = data.get("available_channels", self.available_channels)
                    self.active_channels = data.get("active_channels", self.active_channels)

                    if "shell_prefix" in data:
                        self.shell_prefix = data.get("shell_prefix", "")
                        self.shell_suffix = data.get("shell_suffix", "")
                    elif "shell_template" in data:
                        self.shell_prefix = data.get("shell_template", "")
                        self.shell_suffix = ""

                    self.cart_items = data.get("cart_items", [])

            except Exception as e:
                print(f"Error loading settings: {e}")

    def save_settings(self):
        try:
            Path(CONFIG_DIR).mkdir(parents=True, exist_ok=True)
            data = {
                "default_channel": self.default_channel,
                "available_channels": self.available_channels,
                "active_channels": self.active_channels,
                "shell_prefix": self.shell_prefix,
                "shell_suffix": self.shell_suffix,
                "cart_items": self.cart_items
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
        """Helper to get a unique identifier for a package"""
        # Prefer package_attr_name if available (most unique)
        if "package_attr_name" in package:
            return package["package_attr_name"]
        # Fallback to pname + version
        return f"{package.get('package_pname')}-{package.get('package_pversion')}"

    def is_in_cart(self, package, channel):
        pkg_id = self._get_pkg_id(package)
        for item in self.cart_items:
            # Check ID and channel match
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

        # Deduplication Logic
        seen = set()
        unique_results = []
        for pkg in raw_results:
            # Create a unique signature based on name and version
            # Use pname and version to filter out exact duplicates from different attr paths
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

# Define Toast function placeholder
show_toast_global = None

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
        license_text = license_list[0] if isinstance(license_list, list) and license_list else "Unknown License"

        self.programs_list = self.pkg.get("package_programs", [])
        programs_str = ", ".join(self.programs_list) if self.programs_list else "None"

        file_path = self.pkg.get("package_position", "").split(":")[0]
        source_url = f"https://github.com/NixOS/nixpkgs/blob/master/{file_path}" if file_path else ""
        self.attr_set = self.pkg.get("package_attr_set", "No package set")

        self.selected_channel = initial_channel
        self.run_mode = "direct"

        self.channel_text = ft.Text(f"{self.version} ({self.selected_channel})", size=12, color=ft.Colors.WHITE70)
        channel_menu_items = [ft.PopupMenuItem(text=ch, on_click=self.change_channel, data=ch) for ch in state.active_channels]

        self.channel_selector = ft.Container(
            padding=ft.padding.symmetric(horizontal=10, vertical=5),
            border_radius=8,
            border=ft.border.all(1, ft.Colors.WHITE24),
            content=ft.Row(spacing=5, controls=[self.channel_text, ft.Icon(ft.Icons.ARROW_DROP_DOWN, color=ft.Colors.WHITE70, size=16)]),
        )
        self.channel_dropdown = ft.PopupMenuButton(content=self.channel_selector, items=channel_menu_items, tooltip="Select Channel")

        self.try_btn_icon = ft.Icon(ft.Icons.PLAY_ARROW, size=16, color=ft.Colors.WHITE)
        self.try_btn_text = ft.Text("Try running directly", weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE, size=12)

        self.try_btn = ft.Container(
            padding=ft.padding.symmetric(horizontal=12, vertical=8),
            content=ft.Row(spacing=8, controls=[self.try_btn_icon, self.try_btn_text], alignment=ft.MainAxisAlignment.CENTER),
            on_click=lambda e: self.run_action(self.run_mode),
            border_radius=ft.border_radius.only(top_left=8, bottom_left=8),
            bgcolor=ft.Colors.BLUE_700,
            ink=True
        )

        self.action_menu = ft.PopupMenuButton(
            icon=ft.Icons.ARROW_DROP_DOWN, icon_color=ft.Colors.WHITE,
            items=[
                ft.PopupMenuItem(text="Try running directly", icon=ft.Icons.PLAY_ARROW, on_click=lambda e: self.set_mode_and_run("direct")),
                ft.PopupMenuItem(text="Try in a shell", icon=ft.Icons.TERMINAL, on_click=lambda e: self.set_mode_and_run("shell")),
            ]
        )

        self.action_split_btn = ft.Container(
            bgcolor=ft.Colors.BLUE_700, border_radius=8,
            content=ft.Row(spacing=0, controls=[self.try_btn, ft.Container(width=1, height=20, bgcolor=ft.Colors.WHITE24), self.action_menu])
        )

        # Dynamic Cart Button
        self.cart_btn = ft.IconButton(
            on_click=self.handle_cart_click,
            tooltip="Add/Remove Cart"
        )
        self.update_cart_btn_state()

        tag_color = ft.Colors.BLUE_GREY_700 if self.attr_set == "No package set" else ft.Colors.TEAL_700
        self.tag_chip = ft.Container(
            padding=ft.padding.symmetric(horizontal=8, vertical=4),
            border_radius=12,
            bgcolor=ft.Colors.with_opacity(0.5, tag_color),
            content=ft.Text(self.attr_set, size=10, color=ft.Colors.WHITE70, weight=ft.FontWeight.BOLD),
            visible=bool(self.attr_set)
        )

        content = ft.Column(
            spacing=8,
            controls=[
                ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    controls=[
                        ft.Column(
                            spacing=4,
                            controls=[
                                ft.Text(self.pname, weight=ft.FontWeight.BOLD, size=18, color=ft.Colors.WHITE),
                                self.tag_chip
                            ]
                        ),
                        ft.Row(spacing=10, controls=[
                            self.channel_dropdown,
                            self.action_split_btn,
                            self.cart_btn
                        ])
                    ]
                ),
                ft.Text(description, size=14, color=ft.Colors.WHITE70, no_wrap=False),
                ft.Divider(color=ft.Colors.WHITE10, height=5),
                ft.Row(visible=bool(self.programs_list), controls=[ft.Icon(ft.Icons.TERMINAL, size=14, color=ft.Colors.ORANGE_300), ft.Text("Programs: ", size=12, weight=ft.FontWeight.BOLD, color=ft.Colors.ORANGE_100), ft.Text(programs_str, size=12, color=ft.Colors.WHITE60, expand=True, no_wrap=False)], vertical_alignment=ft.CrossAxisAlignment.START),
                ft.Row(
                    wrap=True, run_spacing=10,
                    controls=[
                        ft.Container(content=ft.Row([ft.Icon(ft.Icons.VERIFIED_USER_OUTLINED, size=14, color=ft.Colors.GREEN_300), ft.Text(license_text, size=12, color=ft.Colors.GREEN_100)], spacing=5)),
                        ft.Container(visible=bool(homepage_url), content=ft.Row([ft.Icon(ft.Icons.LINK, size=14, color=ft.Colors.BLUE_300), ft.Text("Homepage", size=12, color=ft.Colors.BLUE_100)], spacing=5), on_click=lambda _: os.system(f"xdg-open {homepage_url}") if homepage_url else None),
                        ft.Container(visible=bool(source_url), content=ft.Row([ft.Icon(ft.Icons.CODE, size=14, color=ft.Colors.PURPLE_300), ft.Text("Source", size=12, color=ft.Colors.PURPLE_100)], spacing=5), on_click=lambda _: os.system(f"xdg-open {source_url}") if source_url else None),
                    ]
                )
            ]
        )
        super().__init__(content=content, padding=15, opacity=0.15)

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
        # Safe update: Check if attached to page
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

        if self.show_toast:
            self.show_toast(msg)

        self.update_cart_btn_state()

        if self.on_cart_change:
            self.on_cart_change()

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
        except Exception as ex:
            self.channel_text.value = "Error"
            self.channel_text.update()

    def set_mode_and_run(self, mode):
        self.run_mode = mode
        if mode == "direct":
            self.try_btn_text.value = "Try running directly"
            self.try_btn_icon.name = ft.Icons.PLAY_ARROW
        elif mode == "shell":
            self.try_btn_text.value = "Try in a shell"
            self.try_btn_icon.name = ft.Icons.TERMINAL
        self.try_btn_text.update()
        self.try_btn_icon.update()

    def run_action(self, mode):
        target = f"nixpkgs/{self.selected_channel}#{self.pname}"
        cmd_list = []
        display_cmd = ""

        if mode == "direct":
            cmd_list = ["nix", "run", target]
            display_cmd = f"nix run {target}"
        elif mode == "shell":
            prefix = state.shell_prefix.strip()
            suffix = state.shell_suffix.strip()
            if not prefix:
                 if self.show_toast: self.show_toast("Please configure Shell Prefix in Settings!")
                 return
            nix_cmd = f"nix shell {target}"
            if self.programs_list:
                prog_to_run = self.programs_list[0]
                nix_cmd += f" --command {prog_to_run}"
            display_cmd = f"{prefix} {nix_cmd} {suffix}".strip()
            cmd_list = shlex.split(display_cmd)

        output_text = ft.Text("Launching process in background...", font_family="monospace", size=12)
        dlg = ft.AlertDialog(
            title=ft.Text(f"Launching: {mode.capitalize()}"),
            content=ft.Container(width=500, height=150, content=ft.Column([ft.Text(f"Command: {display_cmd}", color=ft.Colors.BLUE_200, size=12, selectable=True), ft.Divider(), ft.Column([output_text], scroll=ft.ScrollMode.AUTO, expand=True), ft.Text("Note: GUI apps appear shortly. For TUI apps, use 'Try in a shell'.", size=10, color=ft.Colors.GREY_500)])),
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

    # --- Custom Toast Logic ---
    toast_text = ft.Text("", color=ft.Colors.WHITE, weight=ft.FontWeight.BOLD)
    toast_container = ft.Container(
        content=toast_text,
        bgcolor=ft.Colors.with_opacity(0.9, "#2D3748"),
        padding=ft.padding.symmetric(horizontal=16, vertical=10),
        border_radius=25,
        shadow=ft.BoxShadow(blur_radius=10, color=ft.Colors.with_opacity(0.3, ft.Colors.BLACK), offset=ft.Offset(0, 5)),
        opacity=0,
        animate_opacity=300,
        alignment=ft.alignment.center,
    )

    # Non-expanding, positioned container for toast
    toast_overlay = ft.Container(
        content=toast_container,
        bottom=90, # Positioned above bottom nav
        left=0, right=0, # Center horizontally
        alignment=ft.alignment.center,
        height=50, # Fixed height to avoid blocking clicks elsewhere
        visible=False
    )

    def show_toast(message):
        toast_text.value = message
        toast_overlay.visible = True
        toast_container.opacity = 1
        page.update()

        def hide():
            time.sleep(2.0)
            toast_container.opacity = 0
            page.update()
            time.sleep(0.3)
            toast_overlay.visible = False
            page.update()

        threading.Thread(target=hide, daemon=True).start()

    global show_toast_global
    show_toast_global = show_toast

    # --- UI Elements ---
    results_column = ft.Column(spacing=10, scroll=ft.ScrollMode.HIDDEN, expand=True)
    cart_column = ft.Column(spacing=10, scroll=ft.ScrollMode.HIDDEN, expand=True)
    result_count_text = ft.Text("", size=12, color=ft.Colors.WHITE54, visible=False)

    channel_dropdown = ft.Dropdown(
        width=160, text_size=12, border_color=ft.Colors.TRANSPARENT, bgcolor=ft.Colors.GREY_900,
        value=state.default_channel if state.default_channel in state.active_channels else (state.active_channels[0] if state.active_channels else ""),
        options=[ft.dropdown.Option(c) for c in state.active_channels],
        content_padding=10, filled=True,
    )

    search_field = ft.TextField(
        hint_text="Search packages...", border=ft.InputBorder.NONE,
        hint_style=ft.TextStyle(color=ft.Colors.WHITE54), text_style=ft.TextStyle(color=ft.Colors.WHITE),
        expand=True,
    )

    # Badges
    filter_badge_count = ft.Text("0", size=10, color=ft.Colors.WHITE, weight=ft.FontWeight.BOLD)
    filter_badge_container = ft.Container(
        content=filter_badge_count, bgcolor=ft.Colors.RED_500, width=16, height=16, border_radius=8,
        alignment=ft.alignment.center, visible=False, top=0, right=0
    )

    # Cart Badge - Centered content, adjusted position relative to icon
    cart_badge_count = ft.Text(str(len(state.cart_items)), size=10, color=ft.Colors.WHITE, weight=ft.FontWeight.BOLD, text_align=ft.TextAlign.CENTER)
    cart_badge_container = ft.Container(
        content=cart_badge_count, bgcolor=ft.Colors.RED_500, width=18, height=18, border_radius=9,
        alignment=ft.alignment.center, visible=len(state.cart_items) > 0, top=2, right=2
    )

    filter_dismiss_layer = ft.Container(
        expand=True, visible=False, on_click=lambda e: toggle_filter_menu(False),
        bgcolor=ft.Colors.with_opacity(0.01, ft.Colors.BLACK)
    )

    filter_list_col = ft.Column(scroll=ft.ScrollMode.AUTO)
    filter_menu = GlassContainer(
        visible=False, width=300, height=350, top=60, right=50, padding=15, border=ft.border.all(1, ft.Colors.WHITE24),
        content=ft.Column([
            ft.Text("Filter by Package Set", weight=ft.FontWeight.BOLD, size=16),
            ft.Divider(height=10, color=ft.Colors.WHITE10),
            ft.Container(expand=True, content=filter_list_col),
            ft.Row(alignment=ft.MainAxisAlignment.END, controls=[ft.TextButton("Close", on_click=lambda e: toggle_filter_menu(False)), ft.ElevatedButton("Apply", on_click=lambda e: apply_filters())])
        ])
    )

    # --- Actions ---

    def update_cart_badge():
        count = len(state.cart_items)
        cart_badge_count.value = str(count)
        if cart_badge_container.page:
            cart_badge_container.visible = count > 0
            cart_badge_container.update()

    def on_global_cart_change():
        update_cart_badge()
        if cart_column.page:
            refresh_cart_view(update_ui=True)

    def refresh_cart_view(update_ui=False):
        cart_column.controls.clear()
        if not state.cart_items:
            cart_column.controls.append(ft.Container(content=ft.Text("Your cart is empty.", color=ft.Colors.WHITE54), alignment=ft.alignment.center, padding=20))
        else:
            for item in state.cart_items:
                pkg_data = item['package']
                saved_channel = item['channel']
                cart_column.controls.append(
                    NixPackageCard(
                        pkg_data,
                        page,
                        saved_channel,
                        on_cart_change=on_global_cart_change,
                        is_cart_view=True,
                        show_toast_callback=show_toast
                    )
                )
        if update_ui and cart_column.page:
            cart_column.update()

    def refresh_dropdown_options():
        channel_dropdown.options = [ft.dropdown.Option(c) for c in state.active_channels]
        if state.default_channel in state.active_channels: channel_dropdown.value = state.default_channel
        elif state.active_channels: channel_dropdown.value = state.active_channels[0]
        if channel_dropdown.page: channel_dropdown.update()

    def update_results_list():
        results_column.controls.clear()

        if current_results and "error" in current_results[0]:
            error_msg = current_results[0]["error"]
            results_column.controls.append(
                ft.Container(
                    content=ft.Column([
                        ft.Icon(ft.Icons.ERROR_OUTLINE, color=ft.Colors.RED_400, size=40),
                        ft.Text("Search Failed", color=ft.Colors.RED_400, weight=ft.FontWeight.BOLD),
                        ft.Text(error_msg, color=ft.Colors.WHITE70, size=12, text_align=ft.TextAlign.CENTER)
                    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                    alignment=ft.alignment.center, padding=20
                )
            )
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

        if result_count_text.page:
            result_count_text.update()

        if not filtered_data:
             results_column.controls.append(ft.Container(content=ft.Text("No results found.", color=ft.Colors.WHITE54), alignment=ft.alignment.center, padding=20))
        else:
            for pkg in filtered_data:
                results_column.controls.append(
                    NixPackageCard(
                        pkg,
                        page,
                        channel_dropdown.value,
                        on_cart_change=on_global_cart_change,
                        show_toast_callback=show_toast
                    )
                )
        if results_column.page:
            results_column.update()

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

    pending_filters = set()

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

    # -- Views --

    def get_search_view():
        return ft.Stack(
            expand=True,
            controls=[
                ft.Column(
                    expand=True,
                    controls=[
                        ft.Text(APP_NAME, size=32, weight=ft.FontWeight.W_900, color=ft.Colors.WHITE),
                        GlassContainer(
                            opacity=0.15, padding=5,
                            content=ft.Row(
                                controls=[
                                    channel_dropdown,
                                    ft.Container(width=1, height=30, bgcolor=ft.Colors.WHITE24),
                                    search_field,
                                    ft.Stack(controls=[ft.IconButton(icon=ft.Icons.FILTER_LIST, icon_color=ft.Colors.WHITE, tooltip="Filter", on_click=lambda e: toggle_filter_menu(not filter_menu.visible)), filter_badge_container]),
                                    ft.IconButton(icon=ft.Icons.SEARCH, icon_color=ft.Colors.WHITE, on_click=perform_search)
                                ]
                            )
                        ),
                        ft.Container(padding=ft.padding.only(left=10), content=result_count_text),
                        results_column
                    ]
                ),
                filter_dismiss_layer,
                filter_menu
            ]
        )

    def get_cart_view():
        refresh_cart_view(update_ui=False)
        return ft.Column(
            expand=True,
            controls=[
                ft.Text("Your Cart", size=32, weight=ft.FontWeight.W_900, color=ft.Colors.WHITE),
                cart_column
            ]
        )

    def get_settings_view():
        channels_list_col = ft.Column()
        def update_default_channel(e):
            state.default_channel = e.control.value
            state.save_settings()
            refresh_dropdown_options()
            show_toast(f"Saved default: {state.default_channel}")
        def update_shell_prefix(e): state.shell_prefix = e.control.value; state.save_settings()
        def update_shell_suffix(e): state.shell_suffix = e.control.value; state.save_settings()
        def toggle_channel_state(e):
            channel = e.control.label; is_active = e.control.value; state.toggle_channel(channel, is_active); refresh_dropdown_options()
        def request_delete_channel(e):
            channel_to_delete = e.control.data; dlg_ref = [None]
            def on_confirm(e):
                state.remove_channel(channel_to_delete); refresh_channels_list(); refresh_dropdown_options()
                if dlg_ref[0]: page.close(dlg_ref[0])
                show_toast(f"Deleted: {channel_to_delete}")
            def on_cancel(e):
                if dlg_ref[0]: page.close(dlg_ref[0])
            dlg = ft.AlertDialog(modal=True, title=ft.Text("Confirm Deletion"), content=ft.Text(f"Remove '{channel_to_delete}'?"), actions=[ft.TextButton("Yes", on_click=on_confirm), ft.TextButton("No", on_click=on_cancel)])
            dlg_ref[0] = dlg; page.open(dlg)
        def refresh_channels_list(update_ui=True):
            channels_list_col.controls.clear()
            for ch in state.available_channels:
                channels_list_col.controls.append(ft.Row(alignment=ft.MainAxisAlignment.SPACE_BETWEEN, controls=[ft.Checkbox(label=ch, value=(ch in state.active_channels), on_change=toggle_channel_state), ft.IconButton(icon=ft.Icons.DELETE_OUTLINE, icon_color=ft.Colors.RED_400, data=ch, on_click=request_delete_channel)]))
            if update_ui and channels_list_col.page: channels_list_col.update()
        def add_custom_channel(e):
            if new_channel_input.value:
                val = new_channel_input.value.strip()
                if not val.startswith("nixos-") and not val.startswith("nixpkgs-"): val = f"nixos-{val}"
                if state.add_channel(val): refresh_channels_list(); refresh_dropdown_options(); new_channel_input.value = ""; new_channel_input.update(); show_toast(f"Added channel: {val}")
        new_channel_input = ft.TextField(hint_text="e.g. 23.11", width=150, height=40, text_size=12, content_padding=10, filled=True, bgcolor=ft.Colors.BLACK12)
        refresh_channels_list(update_ui=False)
        return ft.Column(
            scroll=ft.ScrollMode.HIDDEN,
            controls=[
                ft.Text("Settings", size=32, weight=ft.FontWeight.W_900, color=ft.Colors.WHITE),
                GlassContainer(opacity=0.2, padding=20, content=ft.Row([ft.CircleAvatar(content=ft.Icon(ft.Icons.PERSON), bgcolor=ft.Colors.PURPLE_200, radius=30), ft.Column([ft.Text("User", size=18, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE), ft.Text("System Configuration", color=ft.Colors.WHITE70)], spacing=2)])),
                ft.Container(height=20),
                ft.Text("Channel Management", size=16, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE54),
                GlassContainer(opacity=0.1, padding=15, content=ft.Column([ft.Text("Available Channels", weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE), ft.Container(height=10), ft.Container(height=150, content=ft.Column(scroll=ft.ScrollMode.AUTO, controls=[channels_list_col])), ft.Divider(color=ft.Colors.WHITE24), ft.Row([ft.Text("Add Channel:", size=12), new_channel_input, ft.IconButton(ft.Icons.ADD_CIRCLE, icon_color=ft.Colors.GREEN_400, on_click=add_custom_channel)])])),
                ft.Container(height=10),
                ft.Text("Run Configurations", size=16, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE54),
                GlassContainer(opacity=0.1, padding=15, content=ft.Column([ft.Text("Command Prefix", weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE), ft.Text("e.g. gnome-terminal --", size=12, color=ft.Colors.WHITE54), ft.TextField(value=state.shell_prefix, hint_text="e.g. x-terminal-emulator -e", text_size=12, filled=True, bgcolor=ft.Colors.BLACK12, on_change=update_shell_prefix), ft.Container(height=5), ft.Text("Command Suffix", weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE), ft.Text("e.g. suffix arguments", size=12, color=ft.Colors.WHITE54), ft.TextField(value=state.shell_suffix, hint_text="optional suffix", text_size=12, filled=True, bgcolor=ft.Colors.BLACK12, on_change=update_shell_suffix)])),
                ft.Container(height=10),
                ft.Text("Defaults", size=16, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE54),
                GlassContainer(opacity=0.1, padding=15, content=ft.Column([ft.Text("Default Search Channel", weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE), ft.Container(height=5), ft.Dropdown(options=[ft.dropdown.Option(c) for c in state.available_channels], value=state.default_channel, on_change=update_default_channel, bgcolor=ft.Colors.GREY_900, border_color=ft.Colors.WHITE24, text_style=ft.TextStyle(color=ft.Colors.WHITE), filled=True)])),
                ft.Container(height=50),
            ]
        )

    content_area = ft.Container(expand=True, padding=20, content=get_search_view())

    def build_custom_navbar(on_change):
        buttons = []
        items = [
            (ft.Icons.SEARCH_OUTLINED, ft.Icons.SEARCH, "Search"),
            (ft.Icons.SHOPPING_CART_OUTLINED, ft.Icons.SHOPPING_CART, "Cart"),
            (ft.Icons.SETTINGS_OUTLINED, ft.Icons.SETTINGS, "Settings")
        ]

        def create_nav_btn(i, icon_off, icon_on, label):
            btn = ft.IconButton(
                icon=icon_on if i == 0 else icon_off,
                icon_color=ft.Colors.WHITE if i == 0 else ft.Colors.WHITE54,
                data=i,
                on_click=handle_click,
                tooltip=label,
                style=ft.ButtonStyle(shape=ft.CircleBorder(), padding=10)
            )

            if label == "Cart":
                return ft.Stack(
                    controls=[
                        btn,
                        cart_badge_container
                    ]
                )
            return btn

        def handle_click(e):
            idx = e.control.data
            for j, btn_stack in enumerate(buttons):
                btn = btn_stack.controls[0] if isinstance(btn_stack, ft.Stack) else btn_stack
                is_selected = (j == idx)
                btn.icon = items[j][1] if is_selected else items[j][0]
                btn.icon_color = ft.Colors.WHITE if is_selected else ft.Colors.WHITE54
                btn.update()
            on_change(idx)

        for i, (icon_off, icon_on, label) in enumerate(items):
            buttons.append(create_nav_btn(i, icon_off, icon_on, label))

        return GlassContainer(opacity=0.15, border_radius=0, blur_sigma=15, padding=15, margin=0, content=ft.Row(controls=buttons, alignment=ft.MainAxisAlignment.SPACE_EVENLY))

    def on_nav_change(idx):
        if idx == 0: content_area.content = get_search_view()
        elif idx == 1: content_area.content = get_cart_view()
        elif idx == 2: content_area.content = get_settings_view()
        content_area.update()

    nav_bar = build_custom_navbar(on_nav_change)
    background = ft.Container(expand=True, gradient=ft.LinearGradient(begin=ft.alignment.top_left, end=ft.alignment.bottom_right, colors=["#1a1b26", "#24283b", "#414868"]))
    decorations = ft.Stack(controls=[ft.Container(width=300, height=300, bgcolor=ft.Colors.CYAN_900, border_radius=150, top=-100, right=-50, blur=ft.Blur(100, 100, ft.BlurTileMode.MIRROR), opacity=0.3), ft.Container(width=200, height=200, bgcolor=ft.Colors.PURPLE_900, border_radius=100, bottom=100, left=-50, blur=ft.Blur(80, 80, ft.BlurTileMode.MIRROR), opacity=0.3)])

    # Toast Overlay Layer
    page.add(
        ft.Stack(
            expand=True,
            controls=[
                background,
                decorations,
                ft.Column(expand=True, spacing=0, controls=[content_area, nav_bar]),
                toast_overlay # Add toast layer on top
            ]
        )
    )

if __name__ == "__main__":
    ft.app(target=main)
