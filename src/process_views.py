import flet as ft
import threading
import time
from state import state
from controls import GlassContainer


def get_processes_view(show_dialog_callback, refresh_callback_ref=None):
    process_list = ft.Column(spacing=10, scroll=ft.ScrollMode.AUTO)

    def refresh_list():
        process_list.controls.clear()
        if not state.active_processes:
            process_list.controls.append(
                ft.Container(
                    content=ft.Text("No active processes.", color="onSurfaceVariant"),
                    alignment=ft.alignment.center,
                    padding=20,
                )
            )
        else:
            # Sort by timestamp desc
            sorted_procs = sorted(
                state.active_processes,
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

    def refresh_actions():
        actions_row.controls.clear()
        status = proc.get("status")
        if status == "Running":
            actions_row.controls.append(ft.TextButton("Minimize", on_click=close_dlg))
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
        while is_running[0]:
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
                output_column.update()

            if proc.get("status") != "Running":
                is_running[0] = False
                refresh_actions()

            time.sleep(0.5)

    # Start loop if running
    if is_running[0]:
        threading.Thread(target=update_loop, daemon=True).start()

    close_func[0] = show_dialog(
        proc.get("name", "Process"), content_container, [actions_row], dismissible=False
    )
