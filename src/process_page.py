import flet as ft
from state import state
from controls import GlassContainer


def get_process_page(
    show_dialog_func, show_destructive_dialog=None, show_undo_toast=None
):
    list_col = ft.Column(
        spacing=10,
        expand=True,
        scroll=ft.ScrollMode.AUTO,
        alignment=ft.MainAxisAlignment.START,
    )

    current_filter = ["All"]

    def refresh_list():
        list_col.controls.clear()

        filter_val = current_filter[0]

        # Sort: Active first, then by creation time (descending - newest first)
        all_views = sorted(
            state.active_process_views.values(),
            key=lambda v: (0 if v.is_running else 1, -getattr(v, "created_at", 0)),
        )

        # Filter
        sorted_views = []
        if filter_val == "All":
            sorted_views = all_views
        elif filter_val == "Running":
            sorted_views = [v for v in all_views if v.is_running]
        elif filter_val == "Completed":
            sorted_views = [v for v in all_views if v.status == "Completed"]
        elif filter_val == "Cancelled":
            sorted_views = [v for v in all_views if v.status == "Cancelled"]
        elif filter_val == "Failed":
            # Failed or Error
            sorted_views = [
                v
                for v in all_views
                if v.status.startswith("Failed")
                or v.status.startswith("Error")
                or v.status == "Interrupted"
            ]

        if not sorted_views:
            list_col.controls.append(
                ft.Container(
                    content=ft.Text(
                        f"No {filter_val.lower() if filter_val != 'All' else ''} processes found.",
                        color="white54",
                    ),
                    alignment=ft.alignment.center,
                    padding=20,
                )
            )

        for view in sorted_views:
            # Capture view in closure
            def restore_click(e, v=view):
                v.show(show_dialog_func)

            def dismiss_click(e, v=view):
                # e.control.disabled = True # Not needed if we open dialog

                def do_dismiss(e):
                    # Backup for undo
                    backup_view = v
                    state.remove_process_view(v.id)
                    refresh_list()

                    def undo():
                        state.add_process_view(backup_view.id, backup_view)
                        refresh_list()

                    if show_undo_toast:
                        show_undo_toast(f"Removed: {v.title}", undo)

                if show_destructive_dialog:
                    show_destructive_dialog(
                        "Remove Process?",
                        f"Remove '{v.title}' from history?",
                        do_dismiss,
                    )
                else:
                    # Fallback if dialog not available
                    state.remove_process_view(v.id)
                    refresh_list()

            icon = ft.Icons.RUN_CIRCLE_OUTLINED
            color = ft.Colors.BLUE_200
            if view.status == "Completed":
                icon = ft.Icons.CHECK_CIRCLE_OUTLINE
                color = ft.Colors.GREEN_400
            elif (
                view.status.startswith("Failed")
                or view.status.startswith("Error")
                or view.status == "Cancelled"
                or view.status == "Interrupted"
            ):
                icon = ft.Icons.ERROR_OUTLINE
                color = (
                    ft.Colors.RED_400
                    if view.status != "Cancelled"
                    else ft.Colors.ORANGE_400
                )

            row_content = ft.Row(
                [
                    ft.Icon(icon, color=color, size=30),
                    ft.Column(
                        [
                            ft.Text(view.title, weight=ft.FontWeight.BOLD, size=16),
                            ft.Text(view.status, size=12, color="white70"),
                        ],
                        expand=True,
                        spacing=2,
                    ),
                    ft.IconButton(
                        ft.Icons.CLOSE,
                        tooltip="Dismiss",
                        on_click=dismiss_click,
                        icon_color="white54",
                    )
                    if not view.is_running
                    else ft.Container(),
                ],
                alignment=ft.MainAxisAlignment.START,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            )

            card = GlassContainer(
                padding=10,
                content=row_content,
                border_radius=10,
                on_click=restore_click,
                ink=True,
                tooltip="Click to view details",
            )
            list_col.controls.append(card)

        if list_col.page:
            list_col.update()

    def on_filter_change(e):
        current_filter[0] = e.control.data
        # Update tab styles
        for ctrl in tabs_row.controls:
            is_selected = ctrl.data == current_filter[0]
            ctrl.style = ft.ButtonStyle(
                color=ft.Colors.WHITE if is_selected else ft.Colors.WHITE54,
                bgcolor=ft.Colors.WHITE10 if is_selected else ft.Colors.TRANSPARENT,
            )
        tabs_row.update()
        refresh_list()

    def create_filter_tab(text):
        return ft.TextButton(
            text,
            data=text,
            on_click=on_filter_change,
            style=ft.ButtonStyle(
                color=ft.Colors.WHITE if text == "All" else ft.Colors.WHITE54,
                bgcolor=ft.Colors.WHITE10 if text == "All" else ft.Colors.TRANSPARENT,
            ),
        )

    tabs_row = ft.Row(
        controls=[
            create_filter_tab("All"),
            create_filter_tab("Running"),
            create_filter_tab("Completed"),
            create_filter_tab("Cancelled"),
            create_filter_tab("Failed"),
        ],
        scroll=ft.ScrollMode.HIDDEN,
    )

    def clear_history(e):
        if not state.active_process_views:
            return

        # Collect non-running processes
        to_remove = [v for v in state.active_process_views.values() if not v.is_running]

        if not to_remove:
            return  # Nothing to clear

        def do_clear(e):
            # Backup for undo
            backup = {}
            for v in to_remove:
                backup[v.id] = v
                state.remove_process_view(v.id)  # logic: removes one by one

            # Since remove_process_view calls notify/save, we are good.
            # But iterating and modifying might be slow for UI if many.
            # State remove logic is safe (dict del).

            refresh_list()

            def undo():
                for v in backup.values():
                    state.add_process_view(v.id, v)
                refresh_list()

            if show_undo_toast:
                show_undo_toast(f"Cleared {len(to_remove)} items", undo)

        if show_destructive_dialog:
            show_destructive_dialog(
                "Clear History?",
                f"Remove {len(to_remove)} completed/failed items?",
                do_clear,
            )

    header = ft.Row(
        controls=[
            ft.Text("Processes", size=24, weight=ft.FontWeight.BOLD),
            ft.Container(expand=True),
            ft.IconButton(
                ft.Icons.DELETE_SWEEP, tooltip="Clear History", on_click=clear_history
            ),
        ],
        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
    )

    main_col = ft.Column(
        controls=[header, tabs_row, ft.Divider(height=1, color="white10"), list_col],
        expand=True,
        spacing=10,
    )

    # Initial load
    refresh_list()

    def on_update():
        try:
            if list_col.page:
                refresh_list()
        except Exception:
            pass

    state.add_process_listener(on_update)

    class ProcessPageWrapper(ft.Container):
        def will_unmount(self):
            state.remove_process_listener(on_update)

    wrapper = ProcessPageWrapper(
        content=main_col,
        expand=True,
        padding=ft.padding.only(left=10, top=10, right=10, bottom=120),
        alignment=ft.alignment.top_center,
    )
    return wrapper
