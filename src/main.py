import flet as ft
import time
import threading
import shlex
import subprocess
import difflib
from collections import Counter
from state import state
from constants import APP_NAME
import controls
from controls import (
    GlassContainer,
    GlassButton,
    NixPackageCard,
    UndoToast,
    DelayedActionToast,
)
from views import (
    get_home_view,
    get_search_view,
    get_cart_view,
    get_lists_view,
    get_settings_view,
)
from process_page import get_process_page
from updates import get_installed_view
from utils import execute_nix_search

# --- Main Application ---


def main(page: ft.Page):
    page.title = APP_NAME
    page.theme_mode = ft.ThemeMode.DARK  # Enforce Dark Mode
    page.theme = ft.Theme(color_scheme_seed=state.theme_color)
    page.padding = 0
    page.window_width = 400
    page.window_height = 800

    current_nav_idx = [0]
    current_results = []
    active_filters = {"No package set"}  # Default filter
    pending_filters = set()

    global_menu_card = GlassContainer(
        visible=False,
        width=200,
        padding=10,
        top=0,
        left=0,
        border=ft.border.all(1, "outline"),
        content=ft.Column(spacing=5, tight=True, scroll=ft.ScrollMode.AUTO),
        animate_opacity=150,
    )
    global_menu_card.opacity = 0

    global_dismiss_layer = ft.Container(
        expand=True,
        bgcolor=ft.Colors.TRANSPARENT,
        visible=False,
        on_click=lambda e: close_global_menu(),
    )

    def close_global_menu():
        global_menu_card.opacity = 0
        global_menu_card.visible = False
        global_dismiss_layer.visible = False
        page.update()

    # --- Background Image Handling ---
    bg_image_control = ft.Container(expand=True)

    # Default Background (Gradient + Decorations)
    default_bg_stack = ft.Stack(
        expand=True,
        controls=[
            ft.Container(
                expand=True,
                gradient=ft.LinearGradient(
                    begin=ft.alignment.top_left,
                    end=ft.alignment.bottom_right,
                    colors=["background", "surfaceVariant"],
                ),
            ),
            ft.Stack(
                controls=[
                    ft.Container(
                        width=300,
                        height=300,
                        bgcolor="primary",
                        border_radius=150,
                        top=-100,
                        right=-50,
                        blur=ft.Blur(100, 100, ft.BlurTileMode.MIRROR),
                        opacity=0.15,
                    ),
                    ft.Container(
                        width=200,
                        height=200,
                        bgcolor="tertiary",
                        border_radius=100,
                        bottom=100,
                        left=-50,
                        blur=ft.Blur(80, 80, ft.BlurTileMode.MIRROR),
                        opacity=0.15,
                    ),
                ]
            ),
        ],
    )

    default_bg_container = ft.Container(content=default_bg_stack, expand=True)

    def update_background_image():
        blur_effect = None
        if state.background_blur > 0:
            blur_effect = ft.Blur(
                state.background_blur, state.background_blur, ft.BlurTileMode.MIRROR
            )

        # Use absolute positioning (left/top/right/bottom=0) to force layers to fill the Stack
        blur_layer = (
            ft.Container(blur=blur_effect, left=0, top=0, right=0, bottom=0)
            if blur_effect
            else None
        )

        if state.background_image:
            # External Image
            img_control = ft.Image(
                src=state.background_image,
                fit=ft.ImageFit.COVER,
                opacity=state.background_opacity,
                error_content=ft.Container(bgcolor=ft.Colors.BLACK),
                left=0,
                top=0,
                right=0,
                bottom=0,
            )

            # Stack Image + Blur
            stack_controls = [img_control]
            if blur_layer:
                stack_controls.append(blur_layer)

            bg_image_control.content = ft.Stack(controls=stack_controls, expand=True)
            bg_image_control.blur = None

            default_bg_container.visible = False
        else:
            # Default Background
            bg_image_control.content = None
            default_bg_container.visible = True

            # Apply Opacity (Brightness) to container
            default_bg_container.opacity = state.background_opacity

            # Apply Blur: Add/Update Blur Layer in Default Stack
            # Reset stack to base layers
            default_bg_stack.controls = [
                ft.Container(
                    gradient=ft.LinearGradient(
                        begin=ft.alignment.top_left,
                        end=ft.alignment.bottom_right,
                        colors=["background", "surfaceVariant"],
                    ),
                    left=0,
                    top=0,
                    right=0,
                    bottom=0,
                ),
                ft.Stack(
                    controls=[
                        ft.Container(
                            width=300,
                            height=300,
                            bgcolor="primary",
                            border_radius=150,
                            top=-100,
                            right=-50,
                            blur=ft.Blur(100, 100, ft.BlurTileMode.MIRROR),
                            opacity=0.15,
                        ),
                        ft.Container(
                            width=200,
                            height=200,
                            bgcolor="tertiary",
                            border_radius=100,
                            bottom=100,
                            left=-50,
                            blur=ft.Blur(80, 80, ft.BlurTileMode.MIRROR),
                            opacity=0.15,
                        ),
                    ]
                ),
            ]

            if blur_layer:
                default_bg_stack.controls.append(blur_layer)

            default_bg_container.blur = None  # Ensure container blur is off

        if bg_image_control.page:
            bg_image_control.update()
        if default_bg_container.page:
            default_bg_container.update()

    update_background_image()  # Initial set

    def show_glass_menu(e, content_controls, width=200):
        # Fallback if global_x not present (e.g. some events might differ)
        gx = getattr(e, "global_x", page.window_width / 2)
        gy = getattr(e, "global_y", page.window_height / 2)

        # Consistent logic:
        # If click is on the far right (e.g. > window_width - width), shift left.
        # Otherwise, try to align left edge to gx.

        # Offset slightly to not cover the button completely if possible, or align nicely below.
        # Standard dropdown behavior: Top-Left corner at (gx, gy) usually.
        # But we want to avoid going off screen.

        menu_x = gx
        if menu_x + width > page.window_width - 10:
            menu_x = gx - width

        # Ensure it doesn't go off-screen left
        if menu_x < 10:
            menu_x = 10

        # Vertical positioning
        # Default to below the click
        menu_y = gy + 10

        # Calculate menu height to check bottom overflow
        calc_h = (len(content_controls) * 45) + 20
        menu_height = min(300, calc_h)

        if menu_y + menu_height > page.window_height - 10:
            # If it overflows bottom, try opening above
            menu_y = gy - menu_height - 10
            # If that overflows top, clamp to screen
            if menu_y < 10:
                menu_y = 10

        global_menu_card.width = width
        global_menu_card.left = menu_x
        global_menu_card.top = menu_y

        global_menu_card.content.controls = content_controls

        global_menu_card.height = menu_height

        global_dismiss_layer.visible = True
        global_menu_card.visible = True
        global_menu_card.opacity = 1
        global_menu_card.update()
        if global_dismiss_layer.page:
            global_dismiss_layer.update()

    def open_add_to_list_menu(e, pkg, channel, refresh_callback):
        content_controls = []

        if not state.saved_lists:
            content_controls.append(
                ft.Container(
                    content=ft.Text(
                        "No lists created yet.\nCreate one in Cart.",
                        size=12,
                        color=ft.Colors.GREY_400,
                        text_align=ft.TextAlign.CENTER,
                    ),
                    padding=10,
                    alignment=ft.alignment.center,
                )
            )
        else:
            containing_lists = state.get_containing_lists(pkg, channel)
            sorted_lists = sorted(state.saved_lists.keys(), key=str.lower)

            def on_checkbox_change(e):
                list_name = e.control.label
                state.toggle_pkg_in_list(list_name, pkg, channel)
                if refresh_callback:
                    refresh_callback()

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
                        },
                    ),
                )
                content_controls.append(row)

        show_glass_menu(e, content_controls)

    global global_open_menu_func
    global_open_menu_func = open_add_to_list_menu
    controls.global_open_menu_func = open_add_to_list_menu
    controls.show_glass_menu_global = show_glass_menu

    toast_overlay_container = ft.Container(
        bottom=90, left=0, right=0, alignment=ft.alignment.center, visible=False
    )
    current_toast_token = [0]

    custom_dialog_holder = ft.Container(alignment=ft.alignment.center)

    def close_custom_dialog(e=None):
        custom_dialog_overlay.opacity = 0
        custom_dialog_overlay.visible = False
        if custom_dialog_overlay.page:
            custom_dialog_overlay.update()

    custom_dialog_overlay = ft.Container(
        content=custom_dialog_holder,
        expand=True,
        visible=False,
        on_click=close_custom_dialog,
        bgcolor=ft.Colors.with_opacity(0.3, ft.Colors.BLACK),
        animate_opacity=150,
        opacity=0,
    )

    def show_custom_dialog(title, content, actions, dismissible=True):
        if isinstance(title, str):
            title_control = ft.Text(
                title, size=20, weight=ft.FontWeight.BOLD, color="onSurface"
            )
        else:
            title_control = title

        dialog_content = GlassContainer(
            content=ft.Column(
                [
                    title_control,
                    ft.Divider(height=10),
                    content,
                    ft.Divider(height=10),
                    ft.Row(actions, alignment=ft.MainAxisAlignment.END),
                ],
                spacing=10,
                tight=True,
            ),
            width=400,
            padding=20,
            border_radius=15,
        )

        custom_dialog_holder.content = ft.GestureDetector(
            on_tap=lambda e: None, content=dialog_content
        )
        custom_dialog_overlay.on_click = close_custom_dialog if dismissible else None
        custom_dialog_overlay.visible = True
        custom_dialog_overlay.opacity = 1
        custom_dialog_overlay.update()
        return close_custom_dialog

    controls.show_glass_dialog = show_custom_dialog

    def show_toast(message):
        current_toast_token[0] += 1
        my_token = current_toast_token[0]
        t_text = ft.Text(message, color=ft.Colors.WHITE, weight=ft.FontWeight.BOLD)

        # Use GlassContainer logic manually or use the class if available.
        # Since this is inside main, we can use GlassContainer from controls import.
        t_container = GlassContainer(
            content=t_text,
            bgcolor=ft.Colors.with_opacity(0.15, "#2D3748"),
            padding=ft.padding.symmetric(horizontal=16, vertical=10),
            border_radius=25,
            opacity=0,
            animate_opacity=300,
            alignment=ft.alignment.center,
        )
        # GlassContainer sets shadow and blur by default.
        # We might want to override shadow if needed, but default is fine.

        toast_overlay_container.content = t_container
        toast_overlay_container.visible = True
        page.update()
        t_container.opacity = 1
        t_container.update()

        def hide():
            time.sleep(2.0)
            if current_toast_token[0] != my_token:
                return
            try:
                t_container.opacity = 0
                page.update()
            except Exception:
                pass
            time.sleep(0.3)
            if current_toast_token[0] != my_token:
                return
            try:
                toast_overlay_container.visible = False
                page.update()
            except Exception:
                pass

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

        undo_control = UndoToast(
            message,
            on_undo=wrapped_undo,
            duration_seconds=undo_duration,
            on_timeout=on_timeout,
        )
        toast_overlay_container.content = undo_control
        toast_overlay_container.visible = True
        page.update()

    global show_toast_global
    global show_undo_toast_global
    global show_delayed_toast_global
    show_toast_global = show_toast
    show_undo_toast_global = show_undo_toast
    controls.show_toast_global = show_toast
    controls.show_undo_toast_global = show_undo_toast

    def show_delayed_toast(
        message,
        on_execute,
        duration=None,
        on_cancel=None,
        cancel_text="CANCEL",
        immediate_action_text=None,
        immediate_action_icon=None,
    ):
        current_toast_token[0] += 1
        my_token = current_toast_token[0]
        delay_duration = duration if duration is not None else state.undo_timer

        def wrapped_execute():
            if current_toast_token[0] == my_token:
                on_execute()
                toast_overlay_container.visible = False
                page.update()

        def wrapped_cancel():
            if on_cancel:
                on_cancel()
            if current_toast_token[0] == my_token:
                toast_overlay_container.visible = False
                page.update()

        delayed_control = DelayedActionToast(
            message,
            on_execute=wrapped_execute,
            on_cancel=wrapped_cancel,
            duration_seconds=delay_duration,
            cancel_text=cancel_text,
            immediate_action_text=immediate_action_text,
            immediate_action_icon=immediate_action_icon,
        )
        toast_overlay_container.content = delayed_control
        toast_overlay_container.visible = True
        page.update()

    show_delayed_toast_global = show_delayed_toast
    controls.show_delayed_toast_global = show_delayed_toast

    def show_destructive_dialog(title, content_text, on_confirm):
        duration = state.confirm_timer

        confirm_btn = ft.ElevatedButton(
            f"Yes ({duration}s)",
            bgcolor=ft.Colors.GREY_700,
            color=ft.Colors.WHITE70,
            disabled=True,
        )

        close_dialog_func = [None]

        def handle_confirm(e):
            if close_dialog_func[0]:
                close_dialog_func[0]()
            on_confirm(e)

        def handle_cancel(e):
            if close_dialog_func[0]:
                close_dialog_func[0]()

        cancel_btn = ft.OutlinedButton("No", on_click=handle_cancel)
        confirm_btn.on_click = handle_confirm

        actions = [cancel_btn, confirm_btn]
        content = ft.Text(content_text, color="onSurface")

        close_dialog_func[0] = show_custom_dialog(title, content, actions)

        def timer_logic():
            for i in range(duration, 0, -1):
                if not custom_dialog_overlay.visible:
                    return
                confirm_btn.text = f"Yes ({i}s)"
                try:
                    confirm_btn.update()
                except Exception:
                    pass
                time.sleep(1)

            if custom_dialog_overlay.visible:
                confirm_btn.text = "Yes"
                confirm_btn.disabled = False
                confirm_btn.bgcolor = ft.Colors.RED_700
                confirm_btn.color = ft.Colors.WHITE
                try:
                    confirm_btn.update()
                except Exception:
                    pass

        threading.Thread(target=timer_logic, daemon=True).start()

    results_column = ft.Column(spacing=10)

    active_cart_list_control = [None]

    cart_header_title = ft.Text(
        "Your Cart (0 items)", size=24, weight=ft.FontWeight.W_900, color="onSurface"
    )
    cart_header_save_btn = GlassButton(
        text="Save cart as list",
        icon=ft.Icons.ADD,
        base_color=ft.Colors.TEAL_700,
        opacity=0.8,
    )
    cart_header_clear_btn = ft.IconButton(
        ft.Icons.CLEANING_SERVICES, tooltip="Clear Cart", icon_color=ft.Colors.RED_400
    )
    cart_header_shell_btn_container = ft.Container(
        padding=ft.padding.symmetric(horizontal=12, vertical=8),
        content=ft.Row(
            spacing=6,
            controls=[
                ft.Icon(ft.Icons.TERMINAL, size=16, color=ft.Colors.WHITE),
                ft.Text(
                    "Try Cart in Shell",
                    weight=ft.FontWeight.BOLD,
                    color=ft.Colors.WHITE,
                    size=12,
                ),
            ],
        ),
        ink=True,
    )
    cart_header_copy_btn = ft.IconButton(
        ft.Icons.CONTENT_COPY,
        icon_color=ft.Colors.WHITE70,
        tooltip="Copy Command",
        icon_size=16,
        style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=0)),
    )
    cart_header_shell_btn = ft.Container(
        bgcolor=ft.Colors.with_opacity(0.4, ft.Colors.BLUE_600),
        blur=ft.Blur(15, 15, ft.BlurTileMode.MIRROR),
        border_radius=8,
        content=ft.Row(
            spacing=0,
            controls=[
                cart_header_shell_btn_container,
                ft.Container(width=1, height=20, bgcolor=ft.Colors.WHITE24),
                cart_header_copy_btn,
            ],
        ),
    )

    cart_header_bulk_btn = ft.Container()  # Placeholder for dynamic button

    def global_refresh_action(e=None):
        state.refresh_installed_cache()
        # Refresh current view if applicable
        # We can check `current_nav_idx[0]`
        idx = current_nav_idx[0]
        if idx == 1:  # Search
            # Re-render results?
            # `perform_search` does logic.
            # Just calling `update_results_list` might be enough if it re-reads state?
            # `update_results_list` uses `NixPackageCard`. `NixPackageCard` checks `is_installed` on init.
            # So we must recreate cards. `update_results_list` does that.
            update_results_list()
        elif idx == 2:  # Cart
            refresh_cart_view()
        elif idx == 3:  # Lists
            # Depends on sub-view
            if selected_list_name or is_viewing_favourites:
                refresh_list_detail_view()
            else:
                refresh_lists_main_view()
        elif idx == 4:  # Installed
            content_area.content = get_installed_view(
                page, on_global_cart_change, show_toast, global_refresh_action
            )
            content_area.update()

        show_toast("Status Refreshed")

    cart_header_refresh_btn = ft.IconButton(
        ft.Icons.REFRESH,
        tooltip="Refresh Installed Status",
        on_click=global_refresh_action,
        visible=state.show_refresh_button,
    )

    cart_header = ft.Container(
        padding=ft.padding.only(bottom=10, top=10),
        content=ft.Row(
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            controls=[
                cart_header_title,
                ft.Row(
                    controls=[
                        cart_header_bulk_btn,
                        cart_header_refresh_btn,
                        cart_header_save_btn,
                        cart_header_clear_btn,
                        cart_header_shell_btn,
                    ]
                ),
            ],
        ),
    )

    result_count_text = ft.Text("", size=12, color="onSurfaceVariant", visible=False)

    # Custom Glass Channel Dropdown
    default_ch = (
        state.default_channel
        if state.default_channel in state.active_channels
        else (state.active_channels[0] if state.active_channels else "")
    )
    channel_text = ft.Text(default_ch, size=12)

    def open_channel_menu(e):
        content_controls = []
        for ch in state.active_channels:

            def on_select(e, c=ch):
                channel_text.value = c
                if channel_text.page:
                    channel_text.update()
                # We need to update the value on the container wrapper?
                # channel_dropdown_container.data = c ?
                # channel_dropdown.value was used before.
                # Let's attach value to channel_text or a dedicated state var?
                # refresh_dropdown_options writes to channel_dropdown.value
                channel_dropdown_container.data = c
                close_global_menu()

            row = ft.Container(
                content=ft.Text(ch, size=12),
                padding=10,
                border_radius=5,
                ink=True,
                on_click=on_select,
            )
            content_controls.append(row)

        # Calculate alignment
        # Align to container Top-Left
        # e is from GestureDetector (TapEvent)
        # e.global_x/y is click position. e.local_x/y is click relative to container.
        # Container Top-Left Global = e.global_x - e.local_x
        # Container Height approx 40 (12px text + 8*2 padding = 28 + icon... roughly 40)

        # We construct a dummy event-like object to pass to show_glass_menu
        # so it uses our calculated coordinates.
        class PosEvent:
            pass

        pe = PosEvent()
        # Align X to container left
        pe.global_x = e.global_x - e.local_x
        # Align Y to container bottom (approx)
        pe.global_y = (e.global_y - e.local_y) + 35

        show_glass_menu(pe, content_controls, width=160)

    # Inner Visual
    channel_dropdown_visual = GlassContainer(
        width=160,
        padding=ft.padding.symmetric(horizontal=10, vertical=8),
        content=ft.Row(
            [channel_text, ft.Icon(ft.Icons.ARROW_DROP_DOWN, size=18)],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        ),
        border_radius=state.get_radius("selector"),
        bgcolor=ft.Colors.with_opacity(0.1, state.get_base_color()),
    )

    # Wrapper for Click
    channel_dropdown_container = ft.GestureDetector(
        content=channel_dropdown_visual, on_tap_up=open_channel_menu
    )
    channel_dropdown_container.value = default_ch  # Backwards compatibility for read
    # We assign .value to the wrapper so search logic can read it.
    # Note: GestureDetector doesn't natively have .value, but Python allows dynamic attrs.

    # Update logic also needs to be compatible.
    # The 'channel_dropdown' variable now refers to the GestureDetector wrapper.
    channel_dropdown = channel_dropdown_container

    search_field = ft.TextField(
        hint_text="Search packages...",
        border=ft.InputBorder.NONE,
        hint_style=ft.TextStyle(color="onSurfaceVariant"),
        text_style=ft.TextStyle(color="onSurface"),
        expand=True,
    )
    search_icon_btn = ft.IconButton(
        icon=ft.Icons.SEARCH, on_click=lambda e: perform_search(e)
    )
    filter_badge_count = ft.Text(
        "0", size=10, color=ft.Colors.WHITE, weight=ft.FontWeight.BOLD
    )
    filter_badge_container = ft.Container(
        content=filter_badge_count,
        bgcolor=ft.Colors.RED_500,
        width=16,
        height=16,
        border_radius=8,
        alignment=ft.alignment.center,
        visible=False,
        top=0,
        right=0,
    )
    badge_size_val = state.nav_badge_size
    cart_badge_count = ft.Text(
        str(len(state.cart_items)),
        size=max(8, badge_size_val / 2),
        color=ft.Colors.WHITE,
        weight=ft.FontWeight.BOLD,
        text_align=ft.TextAlign.CENTER,
    )
    cart_badge_container = ft.Container(
        content=cart_badge_count,
        bgcolor=ft.Colors.RED_500,
        width=badge_size_val,
        height=badge_size_val,
        border_radius=badge_size_val / 2,
        alignment=ft.alignment.center,
        visible=len(state.cart_items) > 0,
        top=2,
        right=2,
    )

    filter_dismiss_layer = ft.Container(
        expand=True,
        visible=False,
        bgcolor=ft.Colors.with_opacity(0.01, ft.Colors.BLACK),
    )
    filter_list_col = ft.Column(scroll=ft.ScrollMode.AUTO)
    filter_menu = GlassContainer(
        visible=False,
        width=300,
        height=350,
        top=60,
        right=50,
        padding=15,
        border=ft.border.all(1, "outline"),
        content=ft.Column(
            [
                ft.Text(
                    "Filter by Package Set",
                    weight=ft.FontWeight.BOLD,
                    size=16,
                    color="onSurface",
                ),
                ft.Divider(height=10, color="outline"),
                ft.Container(expand=True, content=filter_list_col),
                ft.Row(
                    alignment=ft.MainAxisAlignment.END,
                    controls=[ft.TextButton("Close"), ft.ElevatedButton("Apply")],
                ),
            ]
        ),
    )

    selected_list_name = None
    is_viewing_favourites = False
    lists_main_col = ft.Column(expand=False)
    list_detail_col = ft.Column(expand=False)
    lists_badge_count = ft.Text(
        str(len(state.saved_lists)),
        size=max(8, badge_size_val / 2),
        color=ft.Colors.WHITE,
        weight=ft.FontWeight.BOLD,
        text_align=ft.TextAlign.CENTER,
    )
    lists_badge_container = ft.Container(
        content=lists_badge_count,
        bgcolor=ft.Colors.RED_500,
        width=badge_size_val,
        height=badge_size_val,
        border_radius=badge_size_val / 2,
        alignment=ft.alignment.center,
        visible=len(state.saved_lists) > 0,
        top=2,
        right=2,
    )

    processes_badge_count = ft.Text(
        "0",
        size=max(8, badge_size_val / 2),
        color=ft.Colors.WHITE,
        weight=ft.FontWeight.BOLD,
        text_align=ft.TextAlign.CENTER,
    )
    processes_badge_container = ft.Container(
        content=processes_badge_count,
        bgcolor=ft.Colors.RED_500,
        width=badge_size_val,
        height=badge_size_val,
        border_radius=badge_size_val / 2,
        alignment=ft.alignment.center,
        visible=False,
        top=2,
        right=2,
        animate_scale=ft.Animation(300, ft.AnimationCurve.EASE_OUT),
        scale=1.0,
    )

    def update_processes_badge():
        running_count = sum(
            1 for v in state.active_process_views.values() if v.is_running
        )
        processes_badge_count.value = str(running_count)
        if processes_badge_container.page:
            processes_badge_container.visible = running_count > 0
            processes_badge_container.update()

    state.add_process_listener(update_processes_badge)

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

        processes_badge_container.width = sz
        processes_badge_container.height = sz
        processes_badge_container.border_radius = radius
        processes_badge_count.size = font_sz

        if cart_badge_container.page:
            cart_badge_container.update()
        if lists_badge_container.page:
            lists_badge_container.update()
        if processes_badge_container.page:
            processes_badge_container.update()

    def _build_shell_command_for_items(items, with_wrapper=True):
        prefix = state.shell_cart_prefix.strip()
        suffix = state.shell_cart_suffix.strip()

        nix_pkgs_args = []
        for item in items:
            pkg = item["package"]
            channel = item["channel"]
            nix_pkgs_args.append(f"nixpkgs/{channel}#{pkg.get('package_pname')}")

        nix_args_str = " ".join(nix_pkgs_args)
        nix_cmd = f"nix shell {nix_args_str} --command bash --noprofile --norc"

        if with_wrapper:
            return f"{prefix} {nix_cmd} {suffix}".strip()
        else:
            return nix_cmd

    def _launch_shell_dialog(display_cmd, title, page):
        cmd_list = shlex.split(display_cmd)

        output_text = ft.Text("Launching process...", font_family="monospace", size=12)

        content = ft.Container(
            width=500,
            height=150,
            content=ft.Column(
                [
                    ft.Text(
                        f"Command: {display_cmd}",
                        color=ft.Colors.BLUE_200,
                        size=12,
                        selectable=True,
                    ),
                    ft.Divider(),
                    ft.Column([output_text], scroll=ft.ScrollMode.AUTO, expand=True),
                ]
            ),
        )

        close_dialog = [None]
        actions = [ft.TextButton("Close", on_click=lambda e: close_dialog[0]())]

        close_dialog[0] = show_custom_dialog(f"Launching {title}", content, actions)

        # We assume show_custom_dialog updates the page to show the dialog.

        try:
            # Use pipes to capture output
            proc = subprocess.Popen(
                cmd_list,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                start_new_session=True,
            )

            # Wait briefly to check for immediate failure
            try:
                outs, errs = proc.communicate(timeout=0.5)
                # If we get here, process exited
                if proc.returncode != 0:
                    err_msg = (
                        errs.decode("utf-8", errors="replace")
                        if errs
                        else "Unknown error"
                    )
                    output_text.value = (
                        f"Process failed (Exit Code {proc.returncode}):\n{err_msg}"
                    )
                else:
                    output_text.value = "Process finished immediately."
            except subprocess.TimeoutExpired:
                # Process is still running (good!)
                output_text.value = "Process started successfully."

            if output_text.page:
                output_text.update()
        except Exception as ex:
            output_text.value = f"Error executing command:\n{str(ex)}"
            if output_text.page:
                output_text.update()

    def run_cart_shell(e):
        if not state.cart_items:
            return
        display_cmd = _build_shell_command_for_items(
            state.cart_items, with_wrapper=True
        )
        _launch_shell_dialog(display_cmd, "Cart Shell", page)

    def run_list_shell(e):
        items = []
        title = ""

        if is_viewing_favourites:
            items = state.favourites
            title = "Favourites"
        elif selected_list_name and selected_list_name in state.saved_lists:
            items = state.saved_lists[selected_list_name]

        if not items:
            return
        display_cmd = _build_shell_command_for_items(items, with_wrapper=True)
        _launch_shell_dialog(display_cmd, title, page)

    def copy_cart_command(e):
        if not state.cart_items:
            return
        cmd = _build_shell_command_for_items(state.cart_items, with_wrapper=False)
        page.set_clipboard(cmd)
        show_toast("Copied Cart Command")

    def copy_list_command(e):
        items = []
        if is_viewing_favourites:
            items = state.favourites
        elif selected_list_name and selected_list_name in state.saved_lists:
            items = state.saved_lists[selected_list_name]

        if not items:
            return
        clean_cmd = _build_shell_command_for_items(items, with_wrapper=False)

        page.set_clipboard(clean_cmd)
        show_toast("Copied List Command")

    def save_cart_as_list(e):
        if not state.cart_items:
            show_toast("Cart is empty")
            return

        list_name_input = ft.TextField(
            hint_text="List Name (e.g., dev-tools)", autofocus=True
        )

        close_dialog = [None]

        def confirm_save(e):
            name = list_name_input.value.strip()
            if not name:
                show_toast("Please enter a name")
                return

            state.save_list(name, list(state.cart_items))
            update_lists_badge()
            show_toast(f"Saved list: {name}")
            if close_dialog[0]:
                close_dialog[0]()
            if active_cart_list_control[0] and active_cart_list_control[0].page:
                refresh_cart_view(update_ui=True)

        actions = [
            ft.TextButton("Cancel", on_click=lambda e: close_dialog[0]()),
            ft.TextButton("Save", on_click=confirm_save),
        ]

        close_dialog[0] = show_custom_dialog(
            "Save Cart as List", list_name_input, actions
        )

    def clear_all_cart(e):
        if not state.cart_items:
            return
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
        if active_cart_list_control[0] and active_cart_list_control[0].page:
            refresh_cart_view(update_ui=True)
        if list_detail_col.page:
            refresh_list_detail_view(update_ui=True)

    def get_bulk_action_button(items, context_name, refresh_cb):
        if not items:
            return ft.Container()

        # Analyze items
        missing_pnames_map = {}  # pname -> channel (for install)
        installed_keys = []  # list of keys (for uninstall)

        all_installed = True
        for item in items:
            pkg = item["package"]
            channel = item["channel"]
            pname = pkg.get("package_pname", "Unknown")

            if not state.is_package_installed(pname):
                all_installed = False
                missing_pnames_map[pname] = channel
            else:
                key = state.get_element_key(pname)
                if key:
                    installed_keys.append(key)

        if all_installed:
            # Uninstall Mode
            # User request: Use full flake path "nixpkgs/channel#pname" instead of element key
            targets = []
            for item in items:
                pkg = item["package"]
                channel = item["channel"]
                pname = pkg.get("package_pname", "Unknown")
                targets.append(f"nixpkgs/{channel}#{pname}")

            if not targets:
                return ft.Container()

            cmd = f"nix profile remove {' '.join(targets)}"

            def run_uninstall_all(e):
                def do_uninstall(e):
                    def actual_execution():
                        show_toast(f"Uninstalling {len(targets)} packages...")
                        try:
                            subprocess.run(shlex.split(cmd), check=True)
                            # Untrack
                            for item in items:
                                p = item["package"].get("package_pname")
                                c = item["channel"]
                                state.untrack_install(p, c)

                            state.refresh_installed_cache()
                            if refresh_cb:
                                refresh_cb()
                            show_toast("Bulk uninstall successful")
                        except Exception as ex:
                            show_toast(f"Bulk uninstall failed: {ex}")

                    show_delayed_toast(
                        f"Uninstalling {len(targets)} apps...", actual_execution
                    )

                show_destructive_dialog(
                    f"Uninstall all from {context_name}?",
                    f"Are you sure you want to remove {len(targets)} apps?",
                    do_uninstall,
                )

            return GlassButton(
                text=f"Uninstall all from {context_name}",
                icon=ft.Icons.DELETE_SWEEP,
                base_color=ft.Colors.RED,
                opacity=0.2,
                tooltip=cmd,
                on_click=run_uninstall_all,
            )

        else:
            # Install Mode
            # Targets are the missing ones
            targets = []
            for pname, channel in missing_pnames_map.items():
                targets.append(f"nixpkgs/{channel}#{pname}")

            if not targets:
                # Should not happen as all_installed was False
                return ft.Container()

            cmd = f"nix profile add {' '.join(targets)}"

            def run_install_all(e):
                def do_install():
                    show_toast(f"Installing {len(targets)} packages...")
                    try:
                        subprocess.run(shlex.split(cmd), check=True)
                        # Track all installed items (only the ones we installed? or all in list? Usually track what we just installed)
                        for pname in missing_pnames_map:
                            channel = missing_pnames_map[pname]
                            state.track_install(pname, channel)

                        state.refresh_installed_cache()
                        show_toast("Bulk install successful")
                        if refresh_cb:
                            refresh_cb()
                    except Exception as ex:
                        show_toast(f"Bulk install failed: {ex}")

                close_dialog = [None]

                def install_and_close(e):
                    if close_dialog[0]:
                        close_dialog[0]()
                    do_install()

                actions = [
                    ft.TextButton("Cancel", on_click=lambda e: close_dialog[0]()),
                    ft.ElevatedButton("Install", on_click=install_and_close),
                ]
                content = ft.Text(
                    f"Install {len(targets)} packages from {context_name}?",
                    color="onSurface",
                )
                close_dialog[0] = show_custom_dialog("Install All?", content, actions)

            return GlassButton(
                text=f"Install all from {context_name}",
                icon=ft.Icons.DOWNLOAD_FOR_OFFLINE,
                base_color=ft.Colors.GREEN,
                opacity=0.6,
                tooltip=cmd,
                on_click=run_install_all,
            )

    def refresh_cart_view(update_ui=False):
        target_list = active_cart_list_control[0]
        if not target_list:
            return

        total_items = len(state.cart_items)
        cart_header_title.value = f"Your Cart ({total_items} items)"
        if total_items > 0:
            cmd_clean = _build_shell_command_for_items(
                state.cart_items, with_wrapper=False
            )
            cmd_full = _build_shell_command_for_items(
                state.cart_items, with_wrapper=True
            )
            cart_header_copy_btn.tooltip = cmd_clean
            cart_header_shell_btn_container.tooltip = cmd_full
        else:
            cart_header_copy_btn.tooltip = "Cart is empty"
            cart_header_shell_btn_container.tooltip = ""

        cart_header_save_btn.disabled = total_items == 0
        cart_header_clear_btn.disabled = total_items == 0
        cart_header_shell_btn.border_radius = state.get_radius("button")

        # Bulk Button
        bulk_btn = get_bulk_action_button(
            state.cart_items, "Cart", lambda: refresh_cart_view(True)
        )
        cart_header_bulk_btn.content = bulk_btn

        target_list.controls.clear()
        if not state.cart_items:
            target_list.controls.append(
                ft.Container(
                    content=ft.Text("Your cart is empty.", color="onSurface"),
                    alignment=ft.alignment.center,
                    padding=20,
                )
            )
        else:
            for item in state.cart_items:
                pkg_data = item["package"]
                saved_channel = item["channel"]
                target_list.controls.append(
                    NixPackageCard(
                        pkg_data,
                        page,
                        saved_channel,
                        on_cart_change=on_global_cart_change,
                        is_cart_view=True,
                        show_toast_callback=show_toast,
                        on_menu_open=None,
                        show_dialog_callback=show_custom_dialog,
                    )
                )

        if update_ui:
            if cart_header.page:
                cart_header.update()
            if target_list.page:
                target_list.update()

    def refresh_dropdown_options():
        if state.default_channel in state.active_channels:
            new_val = state.default_channel
        elif state.active_channels:
            new_val = state.active_channels[0]
        else:
            new_val = ""

        channel_dropdown.value = new_val  # Keep .value for read
        channel_dropdown.data = new_val  # Sync .data
        channel_text.value = new_val
        if channel_dropdown.page:
            channel_dropdown.update()
        if channel_text.page:
            channel_text.update()

    def update_results_list():
        results_column.controls.clear()
        if current_results and "error" in current_results[0]:
            error_msg = current_results[0]["error"]
            results_column.controls.append(
                ft.Container(
                    content=ft.Column(
                        [
                            ft.Icon(
                                ft.Icons.ERROR_OUTLINE, color=ft.Colors.RED_400, size=40
                            ),
                            ft.Text(
                                "Search Failed",
                                color=ft.Colors.RED_400,
                                weight=ft.FontWeight.BOLD,
                            ),
                            ft.Text(
                                error_msg,
                                color="onSurface",
                                size=12,
                                text_align=ft.TextAlign.CENTER,
                            ),
                        ],
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    alignment=ft.alignment.center,
                    padding=20,
                )
            )
            result_count_text.value = "Error"
            if results_column.page:
                results_column.update()
            if result_count_text.page:
                result_count_text.update()
            return

        filtered_data = []
        if not active_filters:
            filtered_data = current_results
            result_count_text.value = f"Showing total {len(current_results)} results"
        else:
            filtered_data = [
                pkg
                for pkg in current_results
                if pkg.get("package_attr_set", "No package set") in active_filters
            ]
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
            results_column.controls.append(
                ft.Container(
                    content=ft.Text(
                        "No results found.",
                        color="onSurface",
                        text_align=ft.TextAlign.CENTER,
                    ),
                    alignment=ft.alignment.center,
                    padding=20,
                )
            )
        else:
            # Use .data if set, else .value fallback
            current_ch = getattr(channel_dropdown, "data", channel_dropdown.value)
            for pkg in filtered_data:
                results_column.controls.append(
                    NixPackageCard(
                        pkg,
                        page,
                        current_ch,
                        on_cart_change=on_global_cart_change,
                        show_toast_callback=show_toast,
                        on_menu_open=None,
                        show_dialog_callback=show_custom_dialog,
                    )
                )
        if results_column.page:
            results_column.update()

    # Search Suggestions Logic
    suggestions_col = ft.Column(scroll=ft.ScrollMode.AUTO, spacing=0)
    suggestions_container = GlassContainer(
        content=suggestions_col,
        visible=False,
        top=60,  # Below header
        left=20,
        right=60,  # Avoid filter button area roughly
        border=ft.border.all(1, ft.Colors.with_opacity(0.2, "white")),
        padding=0,
        blur_sigma=20,
        border_radius=ft.border_radius.only(bottom_left=15, bottom_right=15),
    )

    suggestions_dismiss_layer = ft.Container(
        expand=True,
        visible=False,
        bgcolor=ft.Colors.TRANSPARENT,
    )

    def hide_suggestions(e=None):
        suggestions_container.visible = False
        suggestions_dismiss_layer.visible = False
        suggestions_container.update()
        suggestions_dismiss_layer.update()

    suggestions_dismiss_layer.on_click = hide_suggestions

    def update_suggestions(e=None):
        if not state.enable_search_history:
            if suggestions_container.visible:
                hide_suggestions()
            return

        # Don't show if disabled
        if not state.enable_search_history:
            return

        query = search_field.value.strip() if search_field.value else ""
        history = state.search_history

        matches = []
        if not query:
            matches = history[: state.max_search_suggestions]  # Recent
        else:
            if state.fuzzy_search_history:
                # Exact first
                exact = [h for h in history if query.lower() in h.lower()]
                # Fuzzy
                fuzzy = difflib.get_close_matches(
                    query, history, n=state.max_search_suggestions, cutoff=0.4
                )
                # Merge unique preserving order
                seen = set()
                matches = []
                for x in exact + fuzzy:
                    if x not in seen:
                        matches.append(x)
                        seen.add(x)
            else:
                matches = [h for h in history if query.lower() in h.lower()]

        # Limit
        matches = matches[: state.max_search_suggestions]

        if not matches:
            if suggestions_container.visible:
                hide_suggestions()
            return

        suggestions_col.controls.clear()

        # Clear All Option
        def clear_all_click(e):
            old_hist = list(state.search_history)

            def do_clear(e):
                state.clear_search_history()
                hide_suggestions()

                def on_undo():
                    state.restore_search_history(old_hist)
                    show_toast("History restored")

                show_undo_toast("History cleared", on_undo)

            show_destructive_dialog(
                "Clear History?",
                "Are you sure you want to clear all search history?",
                do_clear,
            )

        suggestions_col.controls.append(
            ft.Container(
                content=ft.Row(
                    [
                        ft.Text("Recent Searches", size=12, color="onSurfaceVariant"),
                        ft.TextButton(
                            "Clear All",
                            on_click=clear_all_click,
                            style=ft.ButtonStyle(color=ft.Colors.RED_400),
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                ),
                padding=ft.padding.symmetric(horizontal=15, vertical=5),
                bgcolor=ft.Colors.with_opacity(0.1, "black"),
            )
        )

        for match in matches:

            def on_click_suggestion(e, m=match):
                search_field.value = m
                hide_suggestions()
                search_field.update()
                perform_search(None)

            def create_delete_handler(m):
                def handler(e):
                    old_history = list(state.search_history)
                    state.remove_from_search_history(m)
                    # Refresh suggestions immediately
                    update_suggestions()

                    def on_undo():
                        state.restore_search_history(old_history)
                        # Refresh suggestions if query context is similar
                        if search_field.value.strip() == query:
                            update_suggestions()
                        show_toast("Restored")

                    show_undo_toast("Deleted", on_undo)

                return handler

            suggestions_col.controls.append(
                ft.Container(
                    content=ft.Row(
                        [
                            ft.Row(
                                [
                                    ft.Icon(
                                        ft.Icons.HISTORY,
                                        size=16,
                                        color="onSurfaceVariant",
                                    ),
                                    ft.Text(match, expand=True, no_wrap=True),
                                ],
                                expand=True,
                            ),
                            ft.IconButton(
                                ft.Icons.CLOSE,
                                icon_size=16,
                                icon_color="onSurfaceVariant",
                                tooltip="Remove from history",
                                on_click=create_delete_handler(match),
                            ),
                        ]
                    ),
                    padding=ft.padding.symmetric(horizontal=15, vertical=10),
                    ink=True,
                    on_click=on_click_suggestion,
                )
            )

        suggestions_container.visible = True
        suggestions_dismiss_layer.visible = True
        suggestions_container.update()
        suggestions_dismiss_layer.update()

    search_field.on_change = update_suggestions
    search_field.on_focus = update_suggestions

    def perform_search(e):
        if suggestions_container.visible:
            hide_suggestions()

        if results_column.page:
            results_column.controls = [
                ft.Container(
                    content=ft.ProgressRing(color=ft.Colors.PURPLE_400),
                    alignment=ft.alignment.center,
                    padding=20,
                )
            ]
            results_column.update()
        if filter_menu.visible:
            toggle_filter_menu(False)
        query = search_field.value
        state.add_to_search_history(query)  # Save history

        current_channel = getattr(channel_dropdown, "data", channel_dropdown.value)
        active_filters.clear()
        active_filters.add("No package set")
        nonlocal current_results
        try:
            current_results = execute_nix_search(query, current_channel)
        finally:
            update_results_list()

    def toggle_filter_menu(visible):
        if visible:
            if not current_results or (
                current_results and "error" in current_results[0]
            ):
                show_toast("No valid search results to filter.")
                return
            pending_filters.clear()
            pending_filters.update(active_filters)
            sets = [
                pkg.get("package_attr_set", "No package set") for pkg in current_results
            ]
            counts = Counter(sets)
            filter_list_col.controls.clear()

            def on_check(e):
                val = e.control.data
                if e.control.value:
                    pending_filters.add(val)
                elif val in pending_filters:
                    pending_filters.remove(val)

            for attr_set, count in counts.most_common():
                filter_list_col.controls.append(
                    ft.Checkbox(
                        label=f"{attr_set} ({count})",
                        value=(attr_set in pending_filters),
                        on_change=on_check,
                        data=attr_set,
                    )
                )
        filter_menu.visible = visible
        filter_dismiss_layer.visible = visible
        filter_menu.update()
        if filter_dismiss_layer.page:
            filter_dismiss_layer.update()

    def apply_filters():
        active_filters.clear()
        active_filters.update(pending_filters)
        toggle_filter_menu(False)
        update_results_list()

    search_field.on_submit = perform_search
    filter_menu.content.controls[3].controls[0].on_click = lambda e: toggle_filter_menu(
        False
    )
    filter_menu.content.controls[3].controls[1].on_click = lambda e: apply_filters()
    filter_dismiss_layer.on_click = lambda e: toggle_filter_menu(False)

    def open_list_detail(list_name, is_fav=False):
        nonlocal selected_list_name
        nonlocal is_viewing_favourites
        selected_list_name = list_name
        is_viewing_favourites = is_fav

        # Generate Bulk Button
        items = []
        context_name = ""
        if is_viewing_favourites:
            items = state.favourites
            context_name = "Favourites"
        elif selected_list_name and selected_list_name in state.saved_lists:
            items = state.saved_lists[selected_list_name]
            context_name = selected_list_name

        bulk_btn = get_bulk_action_button(
            items, context_name, lambda: open_list_detail(list_name, is_fav)
        )

        content_area.content = get_lists_view(
            selected_list_name,
            is_viewing_favourites,
            refresh_list_detail_view,
            list_detail_col,
            go_back_to_lists_index,
            run_list_shell,
            copy_list_command,
            refresh_lists_main_view,
            lists_main_col,
            content_area,
            bulk_action_btn=bulk_btn,
            refresh_callback=global_refresh_action,
        )
        content_area.update()

    def go_back_to_lists_index(e):
        nonlocal selected_list_name
        nonlocal is_viewing_favourites
        selected_list_name = None
        is_viewing_favourites = False
        content_area.content = get_lists_view(
            selected_list_name,
            is_viewing_favourites,
            refresh_list_detail_view,
            list_detail_col,
            go_back_to_lists_index,
            run_list_shell,
            copy_list_command,
            refresh_lists_main_view,
            lists_main_col,
            content_area,
        )
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
                content_area.content = get_lists_view(
                    selected_list_name,
                    is_viewing_favourites,
                    refresh_list_detail_view,
                    list_detail_col,
                    go_back_to_lists_index,
                    run_list_shell,
                    copy_list_command,
                    refresh_lists_main_view,
                    lists_main_col,
                    content_area,
                )
                content_area.update()

            def on_undo():
                state.restore_list(name, backup_items)
                update_lists_badge()
                refresh_lists_main_view(update_ui=True)

            show_undo_toast(f"Deleted: {name}", on_undo)

        show_destructive_dialog(
            "Delete List?", f"Are you sure you want to delete '{name}'?", do_delete
        )

    def refresh_lists_main_view(update_ui=False):
        lists_main_col.controls.clear()
        fav_count = len(state.favourites)
        if fav_count > 0:
            pkgs_preview = ", ".join(
                [i["package"].get("package_pname", "?") for i in state.favourites[:3]]
            )
            if fav_count > 3:
                pkgs_preview += "..."
            preview_text = f"{fav_count} packages - {pkgs_preview}"
        else:
            preview_text = "No apps in favourites"

        fav_card = GlassContainer(
            opacity=0.15,
            padding=15,
            ink=True,
            on_click=lambda e: open_list_detail("Favourites", is_fav=True),
            border=ft.border.all(1, ft.Colors.PINK_400),
            content=ft.Row(
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                controls=[
                    ft.Column(
                        [
                            ft.Row(
                                [
                                    ft.Icon(
                                        ft.Icons.FAVORITE, color=ft.Colors.PINK_400
                                    ),
                                    ft.Text(
                                        "Favourites",
                                        size=18,
                                        weight=ft.FontWeight.BOLD,
                                        color="onSurface",
                                    ),
                                ]
                            ),
                            ft.Text(
                                preview_text,
                                size=12,
                                color="onSurfaceVariant",
                                no_wrap=True,
                            ),
                        ],
                        expand=True,
                    ),
                    ft.Icon(
                        ft.Icons.ARROW_FORWARD_IOS, size=14, color="onSurfaceVariant"
                    ),
                ],
            ),
            border_radius=state.get_radius("card"),
        )
        lists_main_col.controls.append(fav_card)

        if not state.saved_lists:
            lists_main_col.controls.append(
                ft.Container(
                    content=ft.Text(
                        "No custom lists created yet.", color="onSurfaceVariant"
                    ),
                    alignment=ft.alignment.center,
                    padding=20,
                )
            )
        else:
            sorted_lists = sorted(state.saved_lists.items(), key=lambda x: x[0].lower())

            for name, items in sorted_lists:
                count = len(items)
                pkgs_preview = ", ".join(
                    [i["package"].get("package_pname", "?") for i in items[:3]]
                )
                if len(items) > 3:
                    pkgs_preview += "..."
                display_text = f"{count} packages - {pkgs_preview}"
                info_col = ft.Column(
                    [
                        ft.Text(
                            name, size=18, weight=ft.FontWeight.BOLD, color="onSurface"
                        ),
                        ft.Text(
                            display_text,
                            size=12,
                            color=ft.Colors.TEAL_200,
                            no_wrap=True,
                        ),
                    ],
                    expand=True,
                )

                card_content = ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    controls=[
                        ft.Container(
                            content=info_col,
                            expand=True,
                            on_click=lambda e, n=name: open_list_detail(n),
                        ),
                        ft.IconButton(
                            ft.Icons.DELETE_OUTLINE,
                            icon_color=ft.Colors.RED_300,
                            data=name,
                            on_click=delete_saved_list,
                        ),
                    ],
                )

                card = GlassContainer(
                    opacity=0.1,
                    padding=15,
                    content=card_content,
                    border_radius=state.get_radius("card"),
                )
                lists_main_col.controls.append(card)
        if update_ui and lists_main_col.page:
            lists_main_col.update()

    def refresh_list_detail_view(update_ui=False):
        list_detail_col.controls.clear()
        items = []
        if is_viewing_favourites:
            items = state.favourites
        elif selected_list_name and selected_list_name in state.saved_lists:
            items = state.saved_lists[selected_list_name]

        if not items:
            list_detail_col.controls.append(
                ft.Container(
                    content=ft.Text("This list is empty.", color="onSurface"),
                    alignment=ft.alignment.center,
                    padding=20,
                )
            )
        else:
            for item in items:
                pkg_data = item["package"]
                saved_channel = item["channel"]
                list_detail_col.controls.append(
                    NixPackageCard(
                        pkg_data,
                        page,
                        saved_channel,
                        on_cart_change=on_global_cart_change,
                        is_cart_view=True,
                        show_toast_callback=show_toast,
                        on_menu_open=None,
                        show_dialog_callback=show_custom_dialog,
                    )
                )

        if update_ui and list_detail_col.page:
            list_detail_col.update()

    content_area = ft.Container(expand=True, padding=0, content=get_home_view())
    navbar_ref = [None]
    settings_refresh_ref = [None]

    def build_custom_navbar(on_change, current_nav_idx_ref):
        nav_button_controls = []
        # current_nav_idx uses passed ref
        base_container_ref = [None]
        main_row_ref = [None]

        items = [
            (ft.Icons.HOME_OUTLINED, ft.Icons.HOME, "Home"),
            (ft.Icons.SEARCH_OUTLINED, ft.Icons.SEARCH, "Search"),
            (ft.Icons.SHOPPING_CART_OUTLINED, ft.Icons.SHOPPING_CART, "Cart"),
            (ft.Icons.LIST_ALT_OUTLINED, ft.Icons.LIST_ALT, "Lists"),
            (ft.Icons.APPS_OUTLINED, ft.Icons.APPS, "Installed"),
            (ft.Icons.RUN_CIRCLE_OUTLINED, ft.Icons.RUN_CIRCLE, "Processes"),
            (ft.Icons.SETTINGS_OUTLINED, ft.Icons.SETTINGS, "Settings"),
        ]

        def update_active_state(selected_idx):
            for i, control in enumerate(nav_button_controls):
                is_selected = i == selected_idx
                actual_btn_container = (
                    control.controls[0] if isinstance(control, ft.Stack) else control
                )
                content_col = actual_btn_container.content
                icon_control = content_col.controls[0]
                text_control = content_col.controls[1]

                active_col = "onSecondaryContainer"
                inactive_col = ft.Colors.with_opacity(0.6, state.get_base_color())

                icon_control.name = items[i][1] if is_selected else items[i][0]
                icon_control.color = active_col if is_selected else inactive_col
                text_control.color = active_col if is_selected else inactive_col

                text_control.size = state.get_font_size("nav")

                actual_btn_container.bgcolor = (
                    "secondaryContainer" if is_selected else ft.Colors.TRANSPARENT
                )

                if is_selected:
                    icon_control.color = "onSecondaryContainer"
                    text_control.color = "onSecondaryContainer"

                if control.page:
                    control.update()

        def refresh_navbar():
            update_active_state(current_nav_idx_ref[0])

            if main_row_ref[0]:
                main_row_ref[0].spacing = (
                    0 if state.sync_nav_spacing else state.nav_icon_spacing
                )
                main_row_ref[0].alignment = (
                    ft.MainAxisAlignment.SPACE_EVENLY
                    if state.sync_nav_spacing
                    else ft.MainAxisAlignment.CENTER
                )
                if main_row_ref[0].page:
                    main_row_ref[0].update()

            if base_container_ref[0]:
                is_wide = page.width > 600
                should_float = (
                    True
                    if state.floating_nav
                    else (False if state.adaptive_nav and is_wide else True)
                )

                base_container_ref[0].width = (
                    state.nav_bar_width if should_float else page.width - 40
                )
                base_container_ref[0].height = state.nav_bar_height
                base_container_ref[0].margin = (
                    ft.margin.only(bottom=20)
                    if should_float
                    else ft.margin.only(bottom=10)
                )
                base_container_ref[0].border_radius = (
                    state.get_radius("nav") if should_float else 10
                )

                if state.glass_nav:
                    base_container_ref[0].bgcolor = ft.Colors.with_opacity(
                        0.15, state.get_base_color()
                    )
                    base_container_ref[0].blur = ft.Blur(15, 15, ft.BlurTileMode.MIRROR)
                    base_container_ref[0].border = ft.border.all(
                        1, ft.Colors.with_opacity(0.2, state.get_base_color())
                    )
                else:
                    base_container_ref[0].bgcolor = ft.Colors.SURFACE_VARIANT
                    base_container_ref[0].blur = None
                    base_container_ref[0].border = None

                if base_container_ref[0].page:
                    base_container_ref[0].update()

        navbar_ref[0] = refresh_navbar

        def handle_click(e):
            idx = e.control.data
            current_nav_idx_ref[0] = idx
            update_active_state(idx)
            on_change(idx)

        def create_nav_btn(index, icon_off, icon_on, label):
            inactive_col = ft.Colors.with_opacity(0.6, state.get_base_color())
            return ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Icon(name=icon_off, color=inactive_col, size=24),
                        ft.Text(
                            value=label,
                            size=state.get_font_size("nav"),
                            color=inactive_col,
                            weight=ft.FontWeight.BOLD,
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.CENTER,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=0,
                ),
                padding=ft.padding.symmetric(horizontal=12, vertical=8),
                border_radius=30,
                ink=True,
                on_click=handle_click,
                data=index,
                animate=ft.Animation(300, ft.AnimationCurve.EASE_OUT),
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
            elif i == 5:
                wrapper = ft.Stack([btn, processes_badge_container])
                final_controls.append(wrapper)
                nav_button_controls.append(wrapper)
            else:
                final_controls.append(btn)
                nav_button_controls.append(btn)

        main_row = ft.Row(
            controls=final_controls,
            alignment=ft.MainAxisAlignment.SPACE_EVENLY,
            spacing=0,
        )
        main_row_ref[0] = main_row

        container = ft.Container(
            content=main_row,
            padding=ft.padding.symmetric(horizontal=10, vertical=5),
            animate=ft.Animation(300, ft.AnimationCurve.EASE_OUT),
        )
        base_container_ref[0] = container

        refresh_navbar()

        return container

    def on_nav_change(idx):
        if idx != 6:
            settings_refresh_ref[0] = None

        if idx == 0:
            content_area.content = get_home_view()
        elif idx == 1:
            content_area.content = get_search_view(
                perform_search,
                channel_dropdown,
                search_field,
                search_icon_btn,
                results_column,
                result_count_text,
                filter_badge_container,
                toggle_filter_menu,
                global_refresh_action,
                suggestions_overlay=ft.Stack(
                    [suggestions_dismiss_layer, suggestions_container], expand=True
                ),
            )
        elif idx == 2:
            active_cart_list_control[0] = ft.Column(spacing=10)
            content_area.content = get_cart_view(
                lambda: refresh_cart_view(), cart_header, active_cart_list_control[0]
            )
        elif idx == 3:
            nonlocal selected_list_name
            selected_list_name = None
            content_area.content = get_lists_view(
                selected_list_name,
                is_viewing_favourites,
                refresh_list_detail_view,
                list_detail_col,
                go_back_to_lists_index,
                run_list_shell,
                copy_list_command,
                refresh_lists_main_view,
                lists_main_col,
                content_area,
                bulk_action_btn=None,
                refresh_callback=global_refresh_action,
            )
        elif idx == 4:
            content_area.content = get_installed_view(
                page,
                on_global_cart_change,
                show_toast,
                show_dialog_callback=show_custom_dialog,
                refresh_callback=global_refresh_action,
            )
        elif idx == 5:
            content_area.content = get_process_page(
                show_custom_dialog, show_destructive_dialog, show_undo_toast
            )
        elif idx == 6:
            content_area.content = get_settings_view(
                page,
                navbar_ref,
                on_nav_change,
                show_toast,
                show_undo_toast,
                show_destructive_dialog,
                refresh_dropdown_options,
                update_badges_style,
                update_background_image,
            )
        content_area.update()

    def auto_refresh_loop():
        while True:
            if state.auto_refresh_ui:
                try:
                    state.refresh_installed_cache()
                except Exception:
                    pass
            time.sleep(max(1, state.auto_refresh_interval))

    threading.Thread(target=auto_refresh_loop, daemon=True).start()

    def handle_resize(e):
        if navbar_ref[0]:
            navbar_ref[0]()

    page.on_resized = handle_resize

    nav_bar = build_custom_navbar(on_nav_change, current_nav_idx)

    # Initialize Rotation
    bg_image_control.rotate = ft.Rotate(0, alignment=ft.alignment.center)
    bg_image_control.scale = ft.Scale(1)
    default_bg_container.rotate = ft.Rotate(0, alignment=ft.alignment.center)
    default_bg_container.scale = ft.Scale(1)

    def rotation_loop():
        angle = 0.0
        while True:
            if state.bg_rotation:
                angle += state.bg_rotation_speed
                if angle >= 360:
                    angle -= 360

                rad = angle * 3.14159 / 180.0

                scale_val = state.bg_rotation_scale

                # Apply to both
                bg_image_control.rotate.angle = rad
                bg_image_control.scale.scale = scale_val

                default_bg_container.rotate.angle = rad
                default_bg_container.scale.scale = scale_val

                try:
                    if bg_image_control.page and bg_image_control.visible:
                        bg_image_control.update()
                    if default_bg_container.page and default_bg_container.visible:
                        default_bg_container.update()
                except Exception:
                    pass
                time.sleep(0.05)
            else:
                # Reset if needed
                if bg_image_control.scale.scale != 1:
                    bg_image_control.rotate.angle = 0
                    bg_image_control.scale.scale = 1
                    default_bg_container.rotate.angle = 0
                    default_bg_container.scale.scale = 1
                    try:
                        if bg_image_control.page:
                            bg_image_control.update()
                        if default_bg_container.page:
                            default_bg_container.update()
                    except Exception:
                        pass
                time.sleep(1.0)

    threading.Thread(target=rotation_loop, daemon=True).start()

    # Main Page Layout
    # Use a Stack to layer background, main content, and floating nav/overlays
    page.add(
        ft.Stack(
            controls=[
                default_bg_container,
                bg_image_control,
                content_area,
                ft.Container(
                    content=nav_bar,
                    alignment=ft.alignment.bottom_center,
                    bottom=0,
                    left=0,
                    right=0,
                ),
                global_dismiss_layer,
                global_menu_card,
                filter_dismiss_layer,
                filter_menu,
                toast_overlay_container,
                custom_dialog_overlay,
            ],
            expand=True,
            alignment=ft.alignment.bottom_center,
        )
    )

    # Initial Route
    on_nav_change(0)


if __name__ == "__main__":
    ft.app(target=main)
