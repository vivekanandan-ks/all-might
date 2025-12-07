import flet as ft
import os
import shlex
import threading
import time
import subprocess
from state import state
from utils import execute_nix_search

# --- Global Callback Reference ---
global_open_menu_func = None

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
        self.cancelled = False
        threading.Thread(target=self.run_timer, daemon=True).start()

    def will_unmount(self):
        self.cancelled = True

    def run_timer(self):
        step = 0.1
        total_steps = int(self.duration_seconds / step)
        for i in range(total_steps):
            if self.cancelled: return
            time.sleep(step)
            remaining = self.duration_seconds - (i * step)
            
            if not self.page: return
            try:
                self.progress_ring.value = remaining / self.duration_seconds
                self.counter_text.value = str(int(remaining) + 1)
                self.update()
            except:
                return

        if not self.cancelled:
            if not self.page: return
            try:
                self.progress_ring.value = 0
                self.counter_text.value = "0"
                self.update()
            except:
                pass
            
            time.sleep(0.5)
            if self.on_timeout and not self.cancelled:
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
        if self.page:
            try:
                self.update()
            except:
                pass

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
        # 3. Top Bar shrinks (0.75 -> 0.50)
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
            try:
                self.border_bottom.update()
                self.border_right.update()
                self.border_top.update()
                self.border_left.update()
            except:
                pass

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
        self.channel_text.value = "Fetching..."
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
            core_cmd = f"nix shell {target} --command {self.pname}"
        elif self.run_mode == "shell":
            # Use --noprofile --norc to avoid issues with user config in the restricted env
            core_cmd = f"nix shell {target} --command bash --noprofile --norc"

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
        
        content_controls = [
            ft.Text(f"Command: {display_cmd}", color=ft.Colors.BLUE_200, size=12, selectable=True)
        ]
        
        if self.run_mode == "direct":
             content_controls.append(ft.Container(height=10))
             content_controls.append(ft.Text("Note: CLI apps might not work well when running directly. Use 'Try in a shell' for best results.", size=12, color=ft.Colors.ORANGE_400, italic=True))

        content_controls.append(ft.Divider())
        content_controls.append(ft.Column([output_text], scroll=ft.ScrollMode.AUTO, expand=True))

        dlg = ft.AlertDialog(
            title=ft.Text(f"Launching: {self.run_mode.capitalize()}"),
            content=ft.Container(width=500, height=150, content=ft.Column(content_controls)),
            actions=[ft.TextButton("Close", on_click=lambda e: self.page_ref.close(dlg))]
        )
        self.page_ref.open(dlg)
        self.page_ref.update()

        try:
            # Use pipes to capture output
            proc = subprocess.Popen(cmd_list, stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
            
            # Wait briefly to check for immediate failure
            try:
                outs, errs = proc.communicate(timeout=0.5)
                # If we get here, process exited
                if proc.returncode != 0:
                    err_msg = errs.decode('utf-8', errors='replace') if errs else "Unknown error"
                    output_text.value = f"Process failed (Exit Code {proc.returncode}):\n{err_msg}"
                else:
                    output_text.value = "Process finished immediately."
            except subprocess.TimeoutExpired:
                # Process is still running (good!)
                output_text.value = "Process started successfully."
            
            self.page_ref.update()
        except Exception as ex:
            output_text.value = f"Error executing command:\n{str(ex)}"
            self.page_ref.update()
