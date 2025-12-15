import flet as ft
import time
import threading
from state import state


class ProcessPopup:
    @staticmethod
    def show(
        proc, show_dialog, refresh_list_cb=None, reuse_controls=None, allow_clear=True
    ):
        """
        Displays the process logs in a dialog.
        Shared logic for both creating a new process view and viewing an existing one.
        """
        # Ensure 'logs' exists
        if "logs" not in proc:
            proc["logs"] = []

        if reuse_controls:
            title_row = reuse_controls["title"]
            content_container = reuse_controls["content"]
            actions_row = reuse_controls["actions"][0]  # It's a list [actions_row]
            output_column = content_container.content
        else:
            output_column = ft.Column(scroll=ft.ScrollMode.AUTO, expand=True)

            # Populate initial logs
            for line in proc.get("logs", []):
                output_column.controls.append(
                    ft.Text(line, font_family="monospace", size=12)
                )

            content_container = ft.Container(
                width=600, height=300, content=output_column
            )
            actions_row = ft.Row()

            # Placeholder for title, will be defined below
            title_row = None

        # Determine if running
        loop_state = {"running": proc.get("status") == "Running"}

        # References for closure
        close_func = [None]
        listener_ref = [None]

        def close_dlg(e=None):
            loop_state["running"] = False
            if listener_ref[0]:
                state.remove_process_listener(listener_ref[0])
            if close_func[0]:
                close_func[0]()

        def refresh_actions_ui():
            actions_row.controls.clear()
            status = proc.get("status")

            if status == "Running":
                is_cancelling = proc.get("user_cancelled", False)
                btn = ft.TextButton(
                    "Cancelling..." if is_cancelling else "Cancel Process",
                    on_click=cancel_process_action,
                    disabled=is_cancelling,
                )
                actions_row.controls.append(btn)
            else:
                if allow_clear:
                    actions_row.controls.append(
                        ft.TextButton("Clear", on_click=clear_process_action)
                    )
                actions_row.controls.append(ft.TextButton("Close", on_click=close_dlg))

            if actions_row.page:
                actions_row.update()

        def cancel_process_action(e):
            # Set flag for backend logic
            proc["user_cancelled"] = True

            # Update UI immediately
            refresh_actions_ui()

            # Add immediate feedback to logs
            msg = "Process cancelled by user."
            if not proc["logs"] or proc["logs"][-1] != msg:
                proc["logs"].append(msg)

            if proc.get("proc_ref") and proc["proc_ref"][0]:
                try:
                    proc["proc_ref"][0].terminate()
                except Exception as ex:
                    print(f"Error terminating: {ex}")

        def clear_process_action(e):
            state.remove_active_process(proc["id"])
            # Remove from cache if cleared
            if proc["id"] in state.active_process_popups:
                del state.active_process_popups[proc["id"]]
            close_dlg()
            if refresh_list_cb:
                refresh_list_cb()

        def minimize_action(e):
            close_dlg(e)
            if state.on_pulse_request:
                state.on_pulse_request()

        if not reuse_controls:
            # Build Title with Minimize
            minimize_icon = ft.Container(
                content=ft.Icon(ft.Icons.REMOVE, size=16, color="white"),
                width=30,
                height=30,
                border=ft.border.all(1, ft.Colors.WHITE54),
                border_radius=5,
                alignment=ft.alignment.center,
                on_click=minimize_action,
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

            # Cache the newly created controls
            if "id" in proc:
                state.active_process_popups[proc["id"]] = {
                    "title": title_row,
                    "content": content_container,
                    "actions": [actions_row],
                }

        refresh_actions_ui()

        # Event-driven status update
        def on_process_update_listener():
            if not output_column.page:
                return

            current_status = proc.get("status")
            if loop_state["running"] and current_status != "Running":
                loop_state["running"] = False
                refresh_actions_ui()

        listener_ref[0] = on_process_update_listener
        state.add_process_listener(on_process_update_listener)

        # Update Loop (Polling) - Primarily for logs
        def update_loop():
            # Wait for controls to be mounted
            attempts = 0
            while not output_column.page and attempts < 50:
                time.sleep(0.1)
                attempts += 1

            if not output_column.page:
                return  # Failed to mount or closed too fast

            # Use visual count as baseline to avoid duplicate logs if reusing controls
            last_len = len(output_column.controls)

            # Initial scroll
            if output_column.page:
                output_column.scroll_to(offset=-1, duration=0)
                output_column.update()

            while True:
                if not output_column.page:
                    break

                # Check status change (Fallback)
                current_status = proc.get("status")
                if loop_state["running"] and current_status != "Running":
                    loop_state["running"] = False
                    refresh_actions_ui()

                # Check logs
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
                        output_column.scroll_to(offset=-1, duration=300)

                # Loop termination check
                if not loop_state["running"] and len(current_logs) == last_len:
                    time.sleep(1)
                else:
                    time.sleep(0.5)

        threading.Thread(target=update_loop, daemon=True).start()

        close_func[0] = show_dialog(
            title_row,
            content_container,
            [actions_row],
            dismissible=False,
        )

        # Force update immediately if reusing controls to ensure new event handlers are active
        if reuse_controls and actions_row.page:
            actions_row.update()

        return close_func[0]


def show_singleton_process_popup(
    proc, show_dialog, refresh_list_cb=None, allow_clear=True
):
    """
    Shows a singleton popup for a given process.
    If the popup already exists (cached in state), it is re-displayed.
    Otherwise, a new one is created and cached.
    """
    proc_id = proc["id"]

    # Check if we have an active popup UI cached
    if proc_id in state.active_process_popups:
        cached = state.active_process_popups[proc_id]
        return ProcessPopup.show(
            proc,
            show_dialog,
            refresh_list_cb,
            reuse_controls=cached,
            allow_clear=allow_clear,
        )

    return ProcessPopup.show(
        proc, show_dialog, refresh_list_cb, allow_clear=allow_clear
    )
