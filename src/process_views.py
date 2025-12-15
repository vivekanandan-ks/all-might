import flet as ft
from state import state
from controls import GlassContainer
from process_popup import show_singleton_process_popup


def get_processes_view(show_dialog_callback, refresh_callback_ref=None):
    process_list = ft.Column(spacing=10, scroll=ft.ScrollMode.AUTO)

    current_filter = ["All"]  # Mutable for closure

    def refresh_list():
        process_list.controls.clear()

        filtered_procs = []
        for p in state.active_processes:
            status = p.get("status", "Unknown")
            cat = current_filter[0]

            if cat == "All":
                filtered_procs.append(p)
            elif cat == "Ongoing":
                if status == "Running":
                    filtered_procs.append(p)
            elif cat == "Failed":
                if status in ["Failed", "Error"]:
                    filtered_procs.append(p)
            elif cat == "Cancelled":
                if status == "Cancelled":
                    filtered_procs.append(p)
            elif cat == "History":
                if status == "Completed":
                    filtered_procs.append(p)

        if not filtered_procs:
            msg = (
                "No active processes."
                if current_filter[0] == "All"
                else f"No {current_filter[0].lower()} processes."
            )
            process_list.controls.append(
                ft.Container(
                    content=ft.Text(msg, color="onSurfaceVariant"),
                    alignment=ft.alignment.center,
                    padding=20,
                )
            )
        else:
            # Sort by timestamp desc
            sorted_procs = sorted(
                filtered_procs,
                key=lambda x: x.get("timestamp", 0),
                reverse=True,
            )
            for proc in sorted_procs:
                status = proc.get("status", "Unknown")
                status_color = ft.Colors.BLUE
                if status == "Completed":
                    status_color = ft.Colors.GREEN
                elif status in ["Failed", "Error"]:
                    status_color = ft.Colors.RED
                elif status == "Cancelled":
                    status_color = ft.Colors.GREY
                elif status == "Running":
                    status_color = ft.Colors.ORANGE_400

                def open_details(e, p=proc):
                    _show_process_details(p, show_dialog_callback, refresh_list)

                card = GlassContainer(
                    padding=15,
                    on_click=open_details,
                    content=ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        controls=[
                            ft.Column(
                                [
                                    ft.Text(
                                        proc.get("name", "Process"),
                                        weight=ft.FontWeight.BOLD,
                                        size=16,
                                    ),
                                    ft.Text(
                                        f"ID: {proc['id'][:8]}...",
                                        size=10,
                                        color="grey",
                                    ),
                                ]
                            ),
                            ft.Row(
                                [
                                    ft.Container(
                                        content=ft.Text(
                                            status,
                                            color="white",
                                            size=12,
                                            weight=ft.FontWeight.BOLD,
                                        ),
                                        bgcolor=status_color,
                                        padding=ft.padding.symmetric(
                                            horizontal=8, vertical=4
                                        ),
                                        border_radius=5,
                                    ),
                                    ft.Icon(
                                        ft.Icons.ARROW_FORWARD_IOS,
                                        size=14,
                                        color="grey",
                                    ),
                                ]
                            ),
                        ],
                    ),
                )
                process_list.controls.append(card)

        if process_list.page:
            process_list.update()

    def on_filter_change(e):
        current_filter[0] = list(e.control.selected)[0]
        refresh_list()

    filter_segment = ft.SegmentedButton(
        selected={"All"},
        on_change=on_filter_change,
        show_selected_icon=False,
        segments=[
            ft.Segment(
                value="All",
                label=ft.Container(
                    content=ft.Text("All"), width=80, alignment=ft.alignment.center
                ),
            ),
            ft.Segment(
                value="Ongoing",
                label=ft.Container(
                    content=ft.Text("Ongoing"), width=100, alignment=ft.alignment.center
                ),
            ),
            ft.Segment(
                value="Failed",
                label=ft.Container(
                    content=ft.Text("Failed"), width=90, alignment=ft.alignment.center
                ),
            ),
            ft.Segment(
                value="Cancelled",
                label=ft.Container(
                    content=ft.Text("Cancelled"),
                    width=100,
                    alignment=ft.alignment.center,
                ),
            ),
            ft.Segment(
                value="History",
                label=ft.Container(
                    content=ft.Text("History"), width=90, alignment=ft.alignment.center
                ),
            ),
        ],
    )

    refresh_list()

    if refresh_callback_ref is not None and isinstance(refresh_callback_ref, list):
        refresh_callback_ref[0] = refresh_list

    def safe_refresh():
        try:
            refresh_list()
        except Exception:
            pass

    return ft.Container(
        expand=True,
        padding=20,
        content=ft.Column(
            controls=[
                ft.Text("Background Processes", size=24, weight=ft.FontWeight.BOLD),
                ft.Container(height=10),
                filter_segment,
                ft.Divider(),
                ft.Container(expand=True, content=process_list),
            ]
        ),
    )


def _show_process_details(proc, show_dialog, refresh_list_cb):
    show_singleton_process_popup(proc, show_dialog, refresh_list_cb, allow_clear=False)
