import flet as ft
import threading
import time
from state import state
from controls import GlassContainer


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
            elif cat == "History":
                if status in ["Completed", "Cancelled"]:
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
                elif status == "Failed" or status == "Cancelled" or status == "Error":
                    status_color = ft.Colors.RED
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
        segments=[
            ft.Segment(
                value="All",
                label=ft.Container(
                    content=ft.Text("All"), width=60, alignment=ft.alignment.center
                ),
            ),
            ft.Segment(
                value="Ongoing",
                label=ft.Container(
                    content=ft.Text("Ongoing"), width=80, alignment=ft.alignment.center
                ),
            ),
            ft.Segment(
                value="Failed",
                label=ft.Container(
                    content=ft.Text("Failed"), width=70, alignment=ft.alignment.center
                ),
            ),
            ft.Segment(
                value="History",
                label=ft.Container(
                    content=ft.Text("History"), width=70, alignment=ft.alignment.center
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
    output_column = ft.Column(scroll=ft.ScrollMode.AUTO, expand=True)

    # Populate initial logs
    for line in proc.get("logs", []):
        output_column.controls.append(ft.Text(line, font_family="monospace", size=12))

    is_running = [proc.get("status") == "Running"]

    actions_row = ft.Row()

    content_container = ft.Container(width=600, height=300, content=output_column)
    close_func = [None]

    def close_dlg(e=None):
        is_running[0] = False  # Stop loop
        if close_func[0]:
            close_func[0]()

    def cancel_proc(e):
        btn = e.control
        btn.disabled = True
        btn.text = "Cancelling..."
        btn.update()
        if proc.get("proc_ref") and proc["proc_ref"][0]:
            try:
                proc["proc_ref"][0].terminate()
            except Exception:
                pass

    def clear_proc(e):
        state.remove_active_process(proc["id"])
        close_dlg()
        if refresh_list_cb:
            refresh_list_cb()

    def minimize_process(e):
        close_dlg(e)

    minimize_icon = ft.Container(
        content=ft.Icon(ft.Icons.REMOVE, size=16, color="white"),
        width=30,
        height=30,
        border=ft.border.all(1, ft.Colors.WHITE54),
        border_radius=5,
        alignment=ft.alignment.center,
        on_click=minimize_process,
        ink=True,
        tooltip="Minimize",
    )

    title_row = ft.Row(
        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        controls=[
            ft.Text(
                proc.get("name", "Process"),
                size=20,
                weight=ft.FontWeight.BOLD,
                color="onSurface",
            ),
            minimize_icon,
        ],
    )

    def refresh_actions():
        actions_row.controls.clear()
        status = proc.get("status")
        if status == "Running":
            actions_row.controls.append(
                ft.TextButton("Cancel Process", on_click=cancel_proc)
            )
        else:
            actions_row.controls.append(ft.TextButton("Clear", on_click=clear_proc))
            actions_row.controls.append(ft.TextButton("Close", on_click=close_dlg))
        if actions_row.page:
            actions_row.update()

    refresh_actions()

    def update_loop():
        last_len = len(proc.get("logs", []))
        stopping = False
        while True:
            if not output_column.page:
                break

            current_logs = proc.get("logs", [])
            if len(current_logs) > last_len:
                new_lines = current_logs[last_len:]
                for line in new_lines:
                    output_column.controls.append(
                        ft.Text(line, font_family="monospace", size=12)
                    )
                last_len = len(current_logs)
                if output_column.page:
                    output_column.update()
                    # Scroll to bottom
                    output_column.scroll_to(offset=-1, duration=300)

            if stopping:
                break

            if proc.get("status") != "Running":
                is_running[0] = False
                refresh_actions()
                stopping = True

            time.sleep(0.5)

        # Final check for logs
        if output_column.page:
            current_logs = proc.get("logs", [])
            if len(current_logs) > last_len:
                new_lines = current_logs[last_len:]
                for line in new_lines:
                    output_column.controls.append(
                        ft.Text(line, font_family="monospace", size=12)
                    )
                output_column.update()
                output_column.scroll_to(offset=-1, duration=300)

    # Start loop if running
    if is_running[0]:
        threading.Thread(target=update_loop, daemon=True).start()

    close_func[0] = show_dialog(
        title_row, content_container, [actions_row], dismissible=False
    )
