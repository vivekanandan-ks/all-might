import flet as ft
from state import state
from controls import GlassContainer


def get_process_page(show_dialog_func):
    list_col = ft.Column(
        spacing=10,
        expand=True,
        scroll=ft.ScrollMode.AUTO,
        alignment=ft.MainAxisAlignment.START,
    )

    def refresh_list():
        list_col.controls.clear()

        # Sort: Active first, then by creation time (descending - newest first)
        sorted_views = sorted(
            state.active_process_views.values(),
            key=lambda v: (0 if v.is_running else 1, -getattr(v, "created_at", 0)),
        )

        if not sorted_views:
            list_col.controls.append(
                ft.Container(
                    content=ft.Text("No active or recent processes.", color="white54"),
                    alignment=ft.alignment.center,
                    padding=20,
                )
            )

        for view in sorted_views:
            # Capture view in closure
            def restore_click(e, v=view):
                v.show(show_dialog_func)

            def dismiss_click(e, v=view):
                e.control.disabled = True  # Prevent double click?
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
        content=list_col,
        expand=True,
        padding=ft.padding.only(left=10, top=10, right=10, bottom=120),
        alignment=ft.alignment.top_center,
    )
    return wrapper
