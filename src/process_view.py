import flet as ft
import subprocess
import threading
import shlex
import uuid
import time
from state import state


class ProcessView:
    def __init__(self, title, cmd, on_complete=None):
        self.id = str(uuid.uuid4())
        self.created_at = time.time()
        self.title = title
        self.cmd = cmd
        self.on_complete = on_complete

        self.status = "Pending"
        self.logs = []
        self.return_code = None
        self.process = None
        self.is_running = False

        self.close_dialog_func = None
        self.active_ui_refs = None  # To hold current UI controls (log_view, action_row)

    def _build_ui(self):
        # Create fresh controls populated with current state
        log_view = ft.Column(scroll=ft.ScrollMode.AUTO, expand=True)
        # Populate existing logs
        for line in self.logs:
            col = (
                "red" if "Cancellation requested" in line or "Error:" in line else None
            )
            log_view.controls.append(
                ft.Text(line, font_family="monospace", size=12, color=col)
            )

        status_color = ft.Colors.BLUE_200
        if self.status == "Completed":
            status_color = ft.Colors.GREEN_400
        elif self.status in ["Failed", "Error", "Cancelled"]:
            status_color = (
                ft.Colors.RED_400
                if self.status != "Cancelled"
                else ft.Colors.ORANGE_400
            )

        status_text = ft.Text(
            self.status if self.status != "Pending" else "Pending...",
            color=status_color,
            weight=ft.FontWeight.BOLD,
        )

        btn_minimize = ft.TextButton("Minimize", on_click=lambda e: self.minimize())
        btn_cancel = ft.TextButton(
            "Cancel",
            on_click=lambda e: self.cancel(),
            style=ft.ButtonStyle(color=ft.Colors.RED_400),
        )
        btn_close = ft.TextButton("Close", on_click=lambda e: self.minimize())

        # Set initial visibility
        if self.is_running:
            btn_minimize.visible = True
            btn_cancel.visible = True
            btn_close.visible = False
        else:
            btn_minimize.visible = False
            btn_cancel.visible = False
            btn_close.visible = True

        action_row = ft.Row(
            alignment=ft.MainAxisAlignment.END,
            controls=[btn_minimize, btn_cancel, btn_close],
        )

        content = ft.Container(
            width=600,
            height=400,
            content=ft.Column(
                [
                    ft.Row([status_text, ft.Container(expand=True)]),
                    ft.Divider(height=1, color="white24"),
                    ft.Container(
                        content=log_view,
                        bgcolor=ft.Colors.BLACK54,
                        border_radius=5,
                        padding=10,
                        expand=True,
                        border=ft.border.all(1, "white10"),
                    ),
                    ft.Divider(height=1, color="white24"),
                    action_row,
                ]
            ),
        )

        self.active_ui_refs = {
            "content": content,
            "log_view": log_view,
            "status_text": status_text,
            "action_row": action_row,
            "btn_cancel": btn_cancel,
            "btn_close": btn_close,
            "btn_minimize": btn_minimize,
        }
        return content

    def show(self, show_dialog_func):
        content = self._build_ui()
        self.close_dialog_func = show_dialog_func(
            self.title,
            content,
            [],
            dismissible=False,
        )

    def minimize(self):
        if self.close_dialog_func:
            self.close_dialog_func()
            self.close_dialog_func = None
        self.active_ui_refs = None  # Detach UI refs

    def cancel(self):
        if self.process and self.is_running:
            # Immediate feedback via refs
            if self.active_ui_refs:
                try:
                    refs = self.active_ui_refs
                    refs["btn_cancel"].disabled = True
                    refs["btn_cancel"].text = "Cancelling..."
                    if refs["action_row"].page:
                        refs["action_row"].update()
                except Exception:
                    pass

            try:
                self.process.terminate()
                msg = "Cancellation requested..."
                self.logs.append(msg)

                # Update UI logs
                if self.active_ui_refs:
                    try:
                        refs = self.active_ui_refs
                        txt = ft.Text(
                            msg, color="red", font_family="monospace", size=12
                        )
                        refs["log_view"].controls.append(txt)
                        if refs["log_view"].page:
                            refs["log_view"].update()
                    except Exception:
                        pass

            except Exception as e:
                print(f"Error cancelling: {e}")

    def update_ui_status(self):
        # Refresh UI elements if visible
        if self.active_ui_refs:
            try:
                refs = self.active_ui_refs

                # Buttons
                if self.is_running:
                    refs["btn_minimize"].visible = True
                    refs["btn_cancel"].visible = True
                    refs["btn_close"].visible = False
                else:
                    refs["btn_minimize"].visible = False
                    refs["btn_cancel"].visible = False
                    refs["btn_close"].visible = True

                if refs["action_row"].page:
                    refs["action_row"].update()

                # Status Text
                color = ft.Colors.BLUE_200
                text = "Pending..."
                if self.is_running:
                    text = "Running..."
                    color = ft.Colors.BLUE_400
                elif self.status == "Completed":
                    text = "Completed Successfully"
                    color = ft.Colors.GREEN_400
                elif self.status == "Cancelled":
                    text = "Cancelled"
                    color = ft.Colors.ORANGE_400
                else:
                    text = f"{self.status}"
                    color = ft.Colors.RED_400

                refs["status_text"].value = text
                refs["status_text"].color = color
                if refs["status_text"].page:
                    refs["status_text"].update()

            except Exception:
                pass

    def start(self):
        self.is_running = True
        self.status = "Running"
        # Register in global state
        state.add_process_view(self.id, self)

        # If UI is open (rarely happens on start, usually show then start), update it
        self.update_ui_status()

        threading.Thread(target=self._run_thread, daemon=True).start()

    def _run_thread(self):
        try:
            self.process = subprocess.Popen(
                shlex.split(self.cmd),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )

            if self.process.stdout:
                for line in self.process.stdout:
                    clean_line = line.strip()
                    self.logs.append(clean_line)

                    # Update active UI if exists
                    if self.active_ui_refs:
                        try:
                            refs = self.active_ui_refs
                            if refs["log_view"].page:
                                refs["log_view"].controls.append(
                                    ft.Text(
                                        clean_line, font_family="monospace", size=12
                                    )
                                )
                                refs["log_view"].update()
                        except Exception:
                            pass

            self.process.wait()
            self.return_code = self.process.returncode

            if self.return_code < 0:
                self.status = "Cancelled"
            elif self.return_code == 0:
                self.status = "Completed"
                if self.on_complete:
                    try:
                        self.on_complete(True)
                    except Exception as e:
                        print(f"Error in on_complete: {e}")
            else:
                self.status = "Failed"
                if self.on_complete:
                    try:
                        self.on_complete(False)
                    except Exception as e:
                        print(f"Error in on_complete: {e}")

        except Exception as e:
            self.status = "Error"
            self.logs.append(f"Error: {e}")
            if self.active_ui_refs:
                try:
                    refs = self.active_ui_refs
                    refs["log_view"].controls.append(
                        ft.Text(f"Error: {e}", color="red")
                    )
                    if refs["log_view"].page:
                        refs["log_view"].update()
                except Exception:
                    pass

            if self.on_complete:
                try:
                    self.on_complete(False)
                except Exception as ex:
                    print(f"Error in on_complete: {ex}")

        self.is_running = False
        self.update_ui_status()
        state.notify_process_update()
