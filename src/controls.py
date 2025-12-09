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

class DelayedActionToast(ft.Container):
    def __init__(self, message, on_execute, duration_seconds=5, on_cancel=None):
        self.duration_seconds = duration_seconds
        self.on_execute = on_execute
        self.on_cancel = on_cancel
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
                    content=ft.Row([ft.Icon(ft.Icons.CANCEL, size=text_sz*1.2), ft.Text("CANCEL", weight=ft.FontWeight.BOLD, size=text_sz)], spacing=5),
                    style=ft.ButtonStyle(color=ft.Colors.RED_200),
                    on_click=self.handle_cancel
                )
            ]
        )
        super().__init__(
            content=content,
            bgcolor=ft.Colors.with_opacity(0.95, "#742a2a"), # Reddish tint for destructive delay
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
        # If unmounted before completion without explicit cancel, we assume cancelled to be safe? 
        # Or should we execute? Typically if UI disappears, we shouldn't trigger background side effects.
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
            if not self.cancelled and self.on_execute:
                self.on_execute()
            
            # Auto close self after execution
            try:
                 self.visible = False
                 self.update()
            except:
                 pass

    def handle_cancel(self, e):
        self.cancelled = True
        if self.on_cancel:
            self.on_cancel()
        try:
             self.visible = False
             self.update()
        except:
             pass

class AutoCarousel(ft.Container):
    def __init__(self, data_list):
        super().__init__(
            width=400, height=160,
            border_radius=20,
            animate_opacity=300,
            on_hover=self.handle_hover,
            clip_behavior=ft.ClipBehavior.HARD_EDGE,
            shadow=ft.BoxShadow(
                blur_radius=15,
                spread_radius=1,
                color=ft.Colors.with_opacity(0.1, "black"),
                offset=ft.Offset(0, 4)
            )
        )
        self.data_list = data_list
        self.current_index = 0
        self.running = False
        self.paused = False

        self.title_text = ft.Text("", weight=ft.FontWeight.BOLD, size=20, color=ft.Colors.WHITE)
        self.desc_text = ft.Text("", size=14, color=ft.Colors.WHITE70, max_lines=2, overflow=ft.TextOverflow.ELLIPSIS)
        self.icon_view = ft.Icon(ft.Icons.INFO_OUTLINE, size=48, color=ft.Colors.WHITE30)

        self.progress_bar = ft.ProgressBar(value=1.0, height=4, color=ft.Colors.WHITE, bgcolor=ft.Colors.TRANSPARENT, border_radius=0)
        
        self.content_container = ft.Container(
            padding=25,
            expand=True,
            content=ft.Row([
                ft.Column([self.title_text, self.desc_text], alignment=ft.MainAxisAlignment.CENTER, expand=True, spacing=5),
                self.icon_view
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
        )

        self.content = ft.Stack([
            self.content_container,
            ft.Container(content=self.progress_bar, bottom=0, left=0, right=0)
        ])
        
        self.update_content()

    def update_content(self):
        item = self.data_list[self.current_index]
        base_color = item.get("color", ft.Colors.BLUE)
        
        # Gradient background
        self.gradient = None
        self.bgcolor = ft.Colors.with_opacity(0.15, base_color)
        
        if state.carousel_glass:
             self.blur = ft.Blur(20, 20, ft.BlurTileMode.MIRROR)
             self.border = ft.border.all(1, ft.Colors.with_opacity(0.2, ft.Colors.WHITE))
        else:
             self.blur = None
             self.border = None

        self.title_text.value = item.get("title", "")
        self.desc_text.value = item.get("desc", "")
        self.icon_view.name = item.get("icon", ft.Icons.INFO_OUTLINE)
        
        if self.page: self.update()

    def did_mount(self):
        self.running = True
        threading.Thread(target=self.loop, daemon=True).start()

    def will_unmount(self):
        self.running = False

    def handle_hover(self, e):
        self.paused = (e.data == "true")
        if self.paused:
            self.progress_bar.value = 1.0
            self.update_content()
            if self.page: self.progress_bar.update()
        
    def loop(self):
        step = 0.05
        while self.running:
            if self.paused:
                time.sleep(0.1)
                continue
                
            duration = max(1, state.carousel_timer)
            steps_total = int(duration / step)
            
            for i in range(steps_total):
                if not self.running: return
                if self.paused: break
                
                time.sleep(step)
                # Count down
                progress = 1.0 - ((i + 1) / steps_total)
                self.progress_bar.value = progress
                if self.page: self.progress_bar.update()
                
            if self.paused: continue
            
            self.current_index = (self.current_index + 1) % len(self.data_list)
            self.update_content()
            self.progress_bar.value = 1.0
            if self.page: self.progress_bar.update()

show_toast_global = None
show_undo_toast_global = None
show_delayed_toast_global = None

class NixPackageCard(GlassContainer):
    def __init__(self, package_data, page_ref, initial_channel, on_cart_change=None, is_cart_view=False, show_toast_callback=None, on_menu_open=None, on_install_change=None):
        self.pkg = package_data
        self.page_ref = page_ref
        self.on_cart_change = on_cart_change
        self.is_cart_view = is_cart_view
        self.show_toast = show_toast_callback
        self.on_menu_open = on_menu_open
        self.on_install_change = on_install_change
        self.selected_channel = initial_channel

        self.pname = self.pkg.get("package_pname", "Unknown")
        self.attr_name = self.pkg.get("package_attr_name", self.pname)
        self.version = self.pkg.get("package_pversion", "?")
        description = self.pkg.get("package_description") or "No description available."
        homepage_list = self.pkg.get("package_homepage", [])
        homepage_url = homepage_list[0] if isinstance(homepage_list, list) and homepage_list else ""
        license_list = self.pkg.get("package_license_set", [])
        license_text = license_list[0] if isinstance(license_list, list) and license_list else "Unknown"

        self.programs_list = self.pkg.get("package_programs", [])
        programs_str = ", ".join(self.programs_list) if self.programs_list else None
        
        # New: Tracking & Installed Status
        self.is_installed = state.is_package_installed(self.pname)
        self.is_all_might = state.is_tracked(self.pname, self.selected_channel)
        
        # Fallback: If installed and tracked on another channel, consider it All-Might managed
        if self.is_installed and not self.is_all_might:
             if state.get_tracked_channel(self.pname):
                 self.is_all_might = True

        self.element_name = self.pkg.get("package_element_name", "")

        # Fallback: if tracked but not in cache (maybe cache stale), trust tracking?
        # No, cache is truth. If tracking says yes but cache no, it's uninstalled externally.
        # But if tracking says yes, we should probably mark it installed until refresh confirms otherwise?
        # Let's stick to cache as truth for "Installed" status.
        
        # Consistency: If is_all_might is true but is_installed is false, it means it was removed externally.
        # We might want to auto-untrack? Or just show "Install" button again.
        
        file_path = self.pkg.get("package_position", "").split(":")[0]
        source_url = f"https://github.com/NixOS/nixpkgs/blob/master/{file_path}" if file_path else ""
        self.attr_set = self.pkg.get("package_attr_set", "No package set")

        self.run_mode = "direct"

        text_col = "onSurfaceVariant"
        size_norm = state.get_font_size('body')
        size_sm = state.get_font_size('small')
        size_lg = state.get_font_size('title')
        size_tag = state.get_font_size('small') * 0.9

        self.channel_text = ft.Text(f"{self.version} ({self.selected_channel})", size=size_sm, color=text_col)
        
        self.installed_version = state.get_installed_version(self.pname)
        
        self.channel_dropdown = ft.PopupMenuButton(
            content=ft.Container(
                padding=ft.padding.symmetric(horizontal=8, vertical=4),
                border_radius=state.get_radius('selector'),
                border=ft.border.all(1, ft.Colors.with_opacity(0.3, state.get_base_color())),
                content=ft.Row(spacing=4, controls=[
                    self.channel_text,
                    ft.Icon(ft.Icons.ARROW_DROP_DOWN, color=text_col, size=size_sm)
                ]),
            ),
            items=self.build_channel_menu_items(),
            tooltip="Select Channel"
        )

        self.channel_control_area = ft.Column(
             spacing=0,
             controls=[self.channel_dropdown],
             horizontal_alignment=ft.CrossAxisAlignment.CENTER,
             alignment=ft.MainAxisAlignment.CENTER
        )

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
        
        # Install / Uninstall Buttons
        # Command strings for tooltips
        install_cmd_tooltip = f"nix profile add nixpkgs/{self.selected_channel}#{self.pname}"
        uninstall_cmd_tooltip = f"nix profile remove nixpkgs/{self.selected_channel}#{self.pname}"

        self.install_btn = ft.ElevatedButton(
            text="Install",
            icon=ft.Icons.DOWNLOAD, 
            color=ft.Colors.WHITE,
            bgcolor=ft.Colors.GREEN_600,
            tooltip=install_cmd_tooltip,
            on_click=self.handle_install_request,
            visible=not self.is_installed
        )
        
        self.uninstall_btn = ft.OutlinedButton(
            text="Uninstall",
            icon=ft.Icons.DELETE, 
            icon_color=ft.Colors.RED_400,
            style=ft.ButtonStyle(color=ft.Colors.RED_400, side=ft.BorderSide(1, ft.Colors.RED_400)),
            tooltip=uninstall_cmd_tooltip,
            on_click=self.handle_uninstall_request,
            visible=self.is_installed
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
        
        # Tracking Tags
        self.installed_chip = None
        if self.is_installed:
             display_version = self.installed_version if self.installed_version else "?"
             manager = "All-Might" if self.is_all_might else "External"
             
             # Try to get a cleaner origin/channel string
             # self.selected_channel usually holds "nixos-unstable" or "nixos-24.11"
             # If external, it might be the inferred channel.
             origin = self.selected_channel
             
             chip_text = f"Installed ({display_version}) with {manager} from {origin}"
             
             bg_col = ft.Colors.PURPLE_700 if self.is_all_might else ft.Colors.GREY_700
             
             self.installed_chip = ft.Container(
                padding=ft.padding.symmetric(horizontal=6, vertical=2),
                border_radius=state.get_radius('chip'),
                bgcolor=ft.Colors.with_opacity(0.8, bg_col),
                content=ft.Text(chip_text, size=size_tag, color=ft.Colors.WHITE, weight=ft.FontWeight.BOLD)
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

        # 1. License, Homepage, Source (Fixed order)
        footer_items = [
            create_footer_chip(ft.Icons.VERIFIED_USER_OUTLINED, license_text, (ft.Colors.GREEN, ft.Colors.GREEN))
        ]
        if homepage_url:
            footer_items.append(HoverLink(ft.Icons.LINK, "Homepage", homepage_url, (ft.Colors.BLUE, ft.Colors.BLUE), text_size=footer_size))
        if source_url:
            footer_items.append(HoverLink(ft.Icons.CODE, "Source", source_url, (ft.Colors.PURPLE_200, ft.Colors.PURPLE_200), text_size=footer_size))

        # 2. Bins (Expandable section at the bottom)
        bins_control = None
        if self.programs_list:
            bin_chips = [
                ft.Container(
                    content=ft.Text(prog, size=size_tag, color=ft.Colors.ORANGE_100, font_family="monospace"),
                    bgcolor=ft.Colors.with_opacity(0.1, ft.Colors.ORANGE),
                    padding=ft.padding.symmetric(horizontal=6, vertical=3),
                    border_radius=4,
                ) for prog in self.programs_list
            ]
            
            bins_control = ft.Container(
                content=ft.Column([
                     ft.Row([
                        ft.Icon(ft.Icons.TERMINAL, size=size_sm, color=ft.Colors.ORANGE),
                        ft.Text(f"Binaries ({len(self.programs_list)})", size=size_sm, color="onSurfaceVariant")
                    ], spacing=5),
                    ft.Row(controls=bin_chips, wrap=True, spacing=5, run_spacing=5)
                ], spacing=10),
                padding=ft.padding.only(top=10, bottom=5)
            )

        # Header Row Construction
        header_row_controls = [ 
            ft.Text(self.attr_name, weight=ft.FontWeight.BOLD, size=size_lg, color="onSurface"),
            self.tag_chip
        ]
        
        left_col_controls = [ft.Row(header_row_controls)]
        if self.installed_chip:
            left_col_controls.append(ft.Row([self.installed_chip]))

        # Description Rendering
        # Filter out "Installed from..." or "Installed via..." descriptions if we are showing the chip
        is_default_desc = description.startswith("Installed from") or description.startswith("Installed via") or description.startswith("flake:") or "/" in description and len(description) < 60 and " " not in description
        
        desc_control = None
        if not is_default_desc:
             desc_control = ft.Container(content=ft.Text(description, size=size_norm, color="onSurfaceVariant", no_wrap=False, max_lines=2, overflow=ft.TextOverflow.ELLIPSIS), padding=ft.padding.only(bottom=5))

        card_content_controls = [
            ft.Row(
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                controls=[
                    ft.Column(spacing=2, controls=left_col_controls),
                    ft.Row(spacing=5, controls=[
                        self.channel_control_area,
                        self.install_btn,
                        self.uninstall_btn,
                        self.unified_action_bar,
                        self.lists_btn_container,
                        self.fav_btn,
                        self.cart_btn
                    ])
                ]
            )
        ]
        
        if desc_control:
            card_content_controls.append(desc_control)
            
        card_content_controls.append(
            ft.Container(
                bgcolor=ft.Colors.with_opacity(0.05, state.get_base_color()),
                border_radius=state.get_radius('footer'),
                padding=4,
                content=ft.Row(wrap=False, scroll=ft.ScrollMode.HIDDEN, controls=footer_items, spacing=10)
            )
        )

        if bins_control:
            card_content_controls.append(
                ft.Container(
                    content=bins_control,
                    margin=ft.padding.only(top=5)
                )
            )

        content = ft.Column(spacing=4, controls=card_content_controls)
        super().__init__(content=content, padding=12, opacity=0.15, border_radius=state.get_radius('card'))
        self.update_copy_tooltip()

    def build_channel_menu_items(self):
        tracked_channel = state.get_tracked_channel(self.pname)
        items = []
        for ch in state.active_channels:
             content_row = ft.Row([ft.Text(ch)], alignment=ft.MainAxisAlignment.START, spacing=5)
             
             items.append(
                 ft.PopupMenuItem(content=content_row, on_click=self.change_channel, data=ch)
             )
        return items

    def handle_install_request(self, e):
        # Confirmation Dialog (Simple)
        def confirm_install(e):
            self.page_ref.close(dlg)
            self.run_install_logic()

        def close_dlg(e):
            self.page_ref.close(dlg)

        dlg = ft.AlertDialog(
            title=ft.Text("Install App?"),
            content=ft.Text(f"Install {self.pname} using 'nix profile add'?"),
            actions=[
                ft.TextButton("Cancel", on_click=close_dlg),
                ft.ElevatedButton("Install", bgcolor=ft.Colors.GREEN_600, color=ft.Colors.WHITE, on_click=confirm_install)
            ],
            actions_alignment=ft.MainAxisAlignment.END
        )
        self.page_ref.open(dlg)

    def run_install_logic(self):
        # Command: nix profile add nixpkgs/channel#pname
        target = f"nixpkgs/{self.selected_channel}#{self.pname}"
        cmd = f"nix profile add {target}"
        
        # Output Dialog
        output_column = ft.Column(scroll=ft.ScrollMode.AUTO, expand=True)
        output_dlg = ft.AlertDialog(
            title=ft.Text(f"Installing {self.pname}..."),
            content=ft.Container(width=600, height=300, content=output_column),
            actions=[], # No actions while running
            modal=True
        )
        self.page_ref.open(output_dlg)
        self.page_ref.update()

        def run():
            try:
                process = subprocess.Popen(
                    shlex.split(cmd),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1
                )
                
                for line in process.stdout:
                    output_column.controls.append(ft.Text(line.strip(), font_family="monospace", size=12))
                    output_dlg.update()
                
                process.wait()
                
                if process.returncode == 0:
                    output_column.controls.append(ft.Text("Installation Successful!", color="green", weight="bold"))
                    
                    file_path = self.pkg.get("package_position", "").split(":")[0]
                    source_url = f"https://github.com/NixOS/nixpkgs/blob/master/{file_path}" if file_path else ""
                    
                    state.track_install(
                        self.pname, 
                        self.selected_channel,
                        attr_name=self.attr_name,
                        version=self.version,
                        description=self.pkg.get("package_description"),
                        homepage=self.pkg.get("package_homepage", []),
                        license_set=self.pkg.get("package_license_set", []),
                        source_url=source_url,
                        programs=self.programs_list
                    )
                    state.refresh_installed_cache()
                    
                    self.is_installed = True
                    self.is_all_might = True
                    
                    self.installed_version = state.get_installed_version(self.pname)
                    
                    self.channel_dropdown.items = self.build_channel_menu_items()
                    self.channel_dropdown.update()

                    self.install_btn.visible = False
                    self.uninstall_btn.visible = True
                    self.update()
                    if self.on_cart_change: self.on_cart_change()
                    if self.on_install_change: self.on_install_change()
                else:
                    output_column.controls.append(ft.Text(f"Process exited with code {process.returncode}", color="red"))

            except Exception as ex:
                output_column.controls.append(ft.Text(f"Error: {ex}", color="red"))
            
            # Add close button
            output_dlg.actions.append(ft.TextButton("Close", on_click=lambda e: self.page_ref.close(output_dlg)))
            output_dlg.modal = False
            output_dlg.update()

        threading.Thread(target=run, daemon=True).start()

    def handle_uninstall_request(self, e):
        # Target: User requested flake ref format for tooltip/display, 
        # but 'nix profile remove' requires the installed element name/key.
        # We try to find the element key from state cache.
        element_key = state.get_element_key(self.pname)
        target = element_key if element_key else self.pname
        final_cmd = f"nix profile remove {target}"

        def do_uninstall():
            if self.show_toast: self.show_toast(f"Uninstalling {self.pname}...")
            try:
                subprocess.run(shlex.split(final_cmd), check=True)
                
                # Smart Untrack
                if state.is_tracked(self.pname, self.selected_channel):
                    state.untrack_install(self.pname, self.selected_channel)
                else:
                    tracked_ch = state.get_tracked_channel(self.pname)
                    if tracked_ch:
                        state.untrack_install(self.pname, tracked_ch)

                state.refresh_installed_cache() # Refresh cache
                
                if self.show_toast: self.show_toast(f"Uninstalled {self.pname}")
                self.is_installed = False
                
                self.channel_dropdown.items = self.build_channel_menu_items()
                self.channel_dropdown.update()

                self.install_btn.visible = True
                self.uninstall_btn.visible = False
                self.update()
                if self.on_cart_change: self.on_cart_change()
                if self.on_install_change: self.on_install_change()
            except Exception as ex:
                if self.show_toast: self.show_toast(f"Uninstall failed: {ex}")

        def confirm_action(e):
             if show_delayed_toast_global:
                 show_delayed_toast_global(f"Uninstalling {self.pname}...", do_uninstall)
        
        duration = state.confirm_timer
        confirm_btn = ft.ElevatedButton(f"Yes ({duration}s)", bgcolor=ft.Colors.GREY_700, color=ft.Colors.WHITE70, disabled=True)
        cancel_btn = ft.OutlinedButton("No")
        dlg = ft.AlertDialog(
            title=ft.Text("Uninstall App?"),
            content=ft.Text(f"Are you sure you want to uninstall {self.pname}?"),
            actions=[confirm_btn, cancel_btn],
            actions_alignment=ft.MainAxisAlignment.END
        )

        def close_dlg(e):
            self.page_ref.close(dlg)

        def handle_confirm(e):
            self.page_ref.close(dlg)
            if show_delayed_toast_global:
                 show_delayed_toast_global(f"Uninstalling {self.pname}...", do_uninstall)

        cancel_btn.on_click = close_dlg
        
        def timer_logic():
            for i in range(duration, 0, -1):
                if not dlg.open: return
                confirm_btn.text = f"Yes ({i}s)"
                try:
                    confirm_btn.update()
                except:
                    pass
                time.sleep(1)

            if dlg.open:
                confirm_btn.text = "Yes"
                confirm_btn.disabled = False
                confirm_btn.bgcolor = ft.Colors.RED_700
                confirm_btn.color = ft.Colors.WHITE
                confirm_btn.on_click = handle_confirm
                try:
                    confirm_btn.update()
                except:
                    pass

        self.page_ref.open(dlg)
        threading.Thread(target=timer_logic, daemon=True).start()

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
            if self.show_toast: self.show_toast(msg)
            self.update_cart_btn_state()
            if self.on_cart_change: self.on_cart_change()
        else:
            # Remove with Undo
            state.remove_from_cart(self.pkg, self.selected_channel)
            self.update_cart_btn_state()
            if self.on_cart_change: self.on_cart_change()
            
            def on_undo():
                state.add_to_cart(self.pkg, self.selected_channel)
                self.update_cart_btn_state()
                if self.on_cart_change: self.on_cart_change()
            
            if show_undo_toast_global:
                show_undo_toast_global(f"Removed {self.pname} from cart", on_undo)
            elif self.show_toast:
                self.show_toast(f"Removed {self.pname} from cart")

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
                # Priority 1: Match by exact package_attr_name
                found = False
                for r in results:
                    if r.get("package_attr_name") == self.attr_name:
                        new_version = r.get("package_pversion", "?")
                        found = True
                        break
                
                # Priority 2: Fallback to pname match if not found
                if not found:
                    for r in results:
                        if r.get("package_pname") == self.pname:
                            new_version = r.get("package_pversion", "?")
                            break
                    else:
                        if results: new_version = results[0].get("package_pversion", "?")

                self.version = new_version
                self.channel_text.value = f"{self.version} ({new_channel})"

            self.selected_channel = new_channel
            self.channel_text.update()
            
            # Update tracking status for new channel
            self.is_all_might = state.is_tracked(self.pname, self.selected_channel)
            # is_installed check remains same (based on pname in profile)
            
            self.install_btn.visible = not self.is_installed
            self.uninstall_btn.visible = self.is_installed
            
            self.update_cart_btn_state()
            self.update_fav_btn_state()
            self.refresh_lists_state()
            self.update_copy_tooltip()
            
            # Update install/uninstall tooltips
            self.install_btn.tooltip = f"nix profile add nixpkgs/{self.selected_channel}#{self.pname}"
            self.uninstall_btn.tooltip = f"nix profile remove nixpkgs/{self.selected_channel}#{self.pname}"
            
            if self.install_btn.page: self.install_btn.update()
            if self.uninstall_btn.page: self.uninstall_btn.update()
            
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
